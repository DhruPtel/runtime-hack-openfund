"""The risk agent: every full report and the sized plan in, a vote per order out (unit 3.5).

**Gates decide, the model explains, and it can only add vetoes.**
- `review` calls `core/gates.evaluate`, the same gate array the treasurer will
  call at 4.4, and measures the whole bundle against the context budget before
  any call (3.6). Over budget, no call is made and every order is vetoed.
- The model then votes approve or veto on each order, and overall.
- In code, an order is approved only when every gate passed, the model approved
  it, and the model approved overall. A failed or null gate is a veto whatever
  the model says. The model may veto what the gates pass, and never the reverse.
- A reply that is missing, late, refused or in the wrong shape is a veto of
  every order. Nothing is retried: a timeout is billed (F0.9.3), and the risk
  call is one per cycle.

**The risk agent runs as its own process,** exactly as an analyst does (2.4).
Its environment is built from nothing: its one gateway key, `PATH` and
`PYTHONPATH`. The key is checked against every credential only the treasurer may
hold before the process starts, so the signing key and the execution key never
reach it. Its seat is `risk`, its model is `models.json`'s `risk_model`, and
its key source is the same parameter the runner takes. 2.0's per-agent choice is
open, so today that is the shared `BANKR_LLM_KEY` and the agent is
`unassigned`.

**Its reply is kept.** The text goes into the report store under its own hash,
and the decision names it, so a replay can use the recorded reply instead of a
new call (PLAN §2 invariant 7).

**Prompts are files:** `briefs/risk.v1.md` is the system message. The user
message is the plan, the gates' verdicts and every accepted report in full, in
that order.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from fund import config
from fund.adapters import bankr_llm
from fund.agents import analyst, runner
from fund.core import context, gates
from fund.store import reports as report_store

SEAT = "risk"
#: The system brief this fund's risk seat reads now. A record names the brief it was
#: decided under (`risk.brief.files`), and a replay rebuilds with *that* one, so
#: changing this never changes what an older record rebuilds to (`run/decide.replay`).
#: v2 (2026-09-20) says when an overall veto applies: v1 said only that one vetoes
#: every order, and the agent read that as a rule to veto the plan whenever a single
#: order deserved a veto (F8.R.4).
BRIEF = "risk.v2.md"

RULE_RISK = "risk"  # the model vetoed this order
RULE_RISK_OVERALL = "risk-overall"  # the model vetoed the whole plan
RULE_RISK_UNREADABLE = "risk-unreadable"  # the reply broke its shape
RULE_RISK_UNAVAILABLE = "risk-unavailable"  # no reply: timeout, refusal, transport, crash
RULE_RISK_NO_VOTE = "risk-no-vote"  # the reply was read, and this order had no clear vote

#: The reply's lines, read tolerantly: no real model had read `risk.v1.md` before
#: the 3.8 sweep, and a parser that vetoes everything on a shape it did not
#: expect looks exactly like a risk agent doing its job (S6). Each is matched on
#: the line with emphasis, bullets and indentation removed, case aside.
_SEP = r"[\s:.)\-–—|]*"
_HEAD = re.compile(r"^RISK" + _SEP + r"([0-9a-fA-F]{64})\b", re.I)
_ORDER = re.compile(r"^ORDER" + _SEP + r"#?(\d+)" + _SEP + r"(?:([A-Z][A-Z0-9.]*)" + _SEP + r")?"
                    r"(approved?|vetoe?d?)\b" + _SEP + r"(.*)$", re.I)
_OVERALL = re.compile(r"^OVERALL(?:\s+(?:VERDICT|VOTE))?" + _SEP + r"(approved?|vetoe?d?)\b"
                      + _SEP + r"(.*)$", re.I)
_BULLET = re.compile(r"^(?:[-*•+]|\d+[.)])\s+")


@dataclass(frozen=True)
class Settings:
    model: str
    max_tokens: int
    transport_timeout_s: float
    worker_deadline_s: float
    bytes_per_token: Decimal
    pricing: Mapping[str, str] = field(default_factory=dict)
    gateway_url: str = bankr_llm.GATEWAY

    @classmethod
    def from_config(cls, config_dir: Path | None = None) -> "Settings":
        """From `models.json` in `config_dir`, or `config/` without one. A replay
        passes the copy its cycle carries (3.9), never the working tree."""
        models = config.load_json("models.json", config_dir)
        return cls(model=models["risk_model"], max_tokens=models["max_output_tokens"],
                   transport_timeout_s=models["transport_timeout_seconds"],
                   worker_deadline_s=models["worker_deadline_seconds"],
                   bytes_per_token=Decimal(models["context_bytes_per_token"]),
                   pricing=models["pricing_per_million"][models["risk_model"]])


@dataclass(frozen=True)
class Brief:
    system: str
    user: str
    plan_sha256: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256((self.system + "\x00" + self.user).encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class ReportText:
    """One accepted report as risk reads it: exactly the text its seat wrote."""

    seat: str
    text: str

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.text.encode("utf-8")).hexdigest()


def render(plan: Mapping[str, Any], plan_sha256: str, gate_report: Mapping[str, Any],
           reports: Sequence[ReportText], briefs: Path = analyst.BRIEFS,
           brief_name: str | None = None) -> Brief:
    """The whole bundle risk reads: the plan, the gates, and every report in full."""
    parts = [f"PLAN {plan_sha256}", json.dumps(plan, indent=1, sort_keys=True), "END PLAN", "",
             "GATES", json.dumps(gate_report, indent=1, sort_keys=True), "END GATES", ""]
    for report in reports:
        parts += [f"REPORT FROM {report.seat} sha256 {report.sha256}", report.text.rstrip("\n"),
                  f"END REPORT FROM {report.seat}", ""]
    parts += [f"Vote now. Your reply's first line must be exactly:\nRISK {plan_sha256}"]
    return Brief(system=(briefs / (brief_name or BRIEF)).read_text(),
                 user="\n".join(parts), plan_sha256=plan_sha256)


# --- the reply ------------------------------------------------------------------------------------

@dataclass(frozen=True)
class Votes:
    orders: Mapping[int, tuple[str, str]]  # index -> (vote, why): the orders clearly voted on
    overall: tuple[str, str] | None  # None when the reply gave no overall line
    notes: tuple[str, ...] = ()  # each way the reply departed from the brief's shape


def _plain(line: str) -> str:
    """A reply line as the parser reads it: no emphasis, bullet or indentation."""
    return _BULLET.sub("", line.replace("*", "").replace("`", "").strip()).strip()


def _vote(word: str) -> str:
    return "approve" if word.lower().startswith("approv") else "veto"


def parse(text: str, plan: Mapping[str, Any], plan_sha256: str) -> tuple[Votes | None, str | None]:
    """The model's votes, read tolerantly, or why the reply cannot be read at all.

    Accepted, and noted:
    - emphasis, bullets and indentation;
    - `ORDER 1: AMD — Veto (quote-age)`, with the rest of the line joining the
      reason;
    - `approved` and `vetoed`;
    - `OVERALL: approve.`;
    - a missing symbol on an ORDER line.

    **Fail closed per order, not for the whole reply.** An order with no clear
    vote is left out of `orders`, and `decide` vetoes that order alone. Its vote
    may be missing, given twice with different words, or given under another
    order's symbol. With no OVERALL line, the orders' own votes stand.

    **Unreadable, which vetoes every order:**
    - no ORDER line at all;
    - a first RISK line naming a different plan."""
    lines = [line.rstrip() for line in text.strip().split("\n")]
    if lines and lines[0].strip().startswith("```") and lines[-1].strip() == "```":
        lines = lines[1:-1]
    plain = [_plain(line) for line in lines]
    notes: list[str] = []
    head = next((match for match in map(_HEAD.match, plain) if match), None)
    if head is None:
        notes.append("no RISK line naming the plan")
    elif head.group(1).lower() != plan_sha256:
        return None, f"the reply names plan {head.group(1)[:12]}…, not {plan_sha256[:12]}…"
    symbols = {o["index"]: o["asset"]["symbol"] for o in plan["orders"]}
    votes: dict[int, tuple[str, list[str]]] = {}
    unclear: set[int] = set()
    overall: tuple[str, list[str]] | None = None
    current: list[str] | None = None
    for line in plain:
        order = _ORDER.match(line)
        closing = _OVERALL.match(line)
        if order:
            index, symbol = int(order.group(1)), order.group(2)
            vote, rest = _vote(order.group(3)), order.group(4).strip()
            if index not in symbols:
                notes.append(f"a vote on order {index}, which the plan does not have, is ignored")
                current = None
                continue
            if symbol and symbol.upper() != symbols[index].upper():
                notes.append(f"order {index} was voted under {symbol}, not {symbols[index]}: "
                             "no clear vote")
                unclear.add(index)
                current = None
                continue
            if index in votes and votes[index][0] != vote:
                notes.append(f"order {index} was voted both ways: no clear vote")
                unclear.add(index)
            current = [rest] if rest else []
            votes.setdefault(index, (vote, current))
        elif closing and overall is None:
            current = [closing.group(2).strip()] if closing.group(2).strip() else []
            overall = (_vote(closing.group(1)), current)
        elif current is not None and line:
            current.append(line)
    if not votes and symbols:
        return None, "no ORDER line could be read"
    clear = {i: (v, " ".join(w).strip()) for i, (v, w) in votes.items() if i not in unclear}
    missing = sorted(set(symbols) - set(votes) - unclear)
    if missing:
        notes.append(f"no vote on order(s) {missing}: each is vetoed")
    if overall is None:
        notes.append("no OVERALL line: the orders' own votes stand")
    return Votes(clear, None if overall is None else (overall[0], " ".join(overall[1]).strip()),
                 tuple(notes)), None


def decide(gate_report: Mapping[str, Any], votes: Votes | None,
           no_votes: tuple[str, str] | None = None, *, plan: Mapping[str, Any],
           snapshot: Mapping[str, Any], limits: gates.Limits) -> dict[str, Any]:
    """The override rule, then the cash floor on what it approved.

    An order is approved only when its gates cleared, the model approved it, and
    the model approved overall. A failed or null gate vetoes whatever the model
    says; the model can only add vetoes. Then `gates.settle` judges the cash floor
    on the orders so approved (R1). A buy is dropped, last first, while they would
    leave less than the floor, and a sell never is. So a vetoed sell cannot leave
    approved the buys it was paying for."""
    decided = []
    for order in gate_report["orders"]:
        index = order["index"]
        by = list(order["blocked_by"])
        vote = why = None
        if votes is None:
            rule = no_votes[0] if no_votes else RULE_RISK_UNAVAILABLE
            if rule not in by:
                by.append(rule)
        elif index not in votes.orders:
            by.append(RULE_RISK_NO_VOTE)  # read, but no clear vote on this order: it alone
        else:
            vote, why = votes.orders[index]
            if vote != "approve":
                by.append(RULE_RISK)
            if votes.overall is not None and votes.overall[0] != "approve":
                by.append(RULE_RISK_OVERALL)
        approved = bool(order["cleared"]) and not by
        entry = {"index": index, "symbol": order["symbol"], "approved": approved,
                 "vetoed_by": by, "model_vote": vote, "model_why": why}
        if vote == "approve" and not order["cleared"]:
            entry["note"] = ("the model approved; a gate refused, and the gates decide: "
                             + ", ".join(order["blocked_by"]))
        decided.append(entry)
    kept, dropped, floor = gates.settle(plan, [o["index"] for o in decided if o["approved"]],
                                        snapshot=snapshot, limits=limits)
    for entry in decided:
        if entry["index"] in dropped:
            entry["approved"] = False
            entry["vetoed_by"].append(gates.RULE_CASH_FLOOR)
            entry["note"] = ("approved, then dropped: the approved orders would leave less "
                             "cash than the floor")
    return {"orders": decided,
            "approved": [o["index"] for o in decided if o["approved"]],
            "vetoed": [o["index"] for o in decided if not o["approved"]],
            "cash_floor": floor.as_dict(),
            "overall": None if votes is None or votes.overall is None else {
                "vote": votes.overall[0], "why": votes.overall[1]},
            "reply_notes": [] if votes is None else list(votes.notes),
            "no_votes": None if votes is not None else {
                "rule": (no_votes or (RULE_RISK_UNAVAILABLE, ""))[0],
                "why": (no_votes or ("", "no reply"))[1]}}


# --- the call, in its own process ----------------------------------------------------------------

def call(brief: Brief, credential: runner.SeatCredential, settings: Settings, *,
         work_dir: Path, environ: Mapping[str, str],
         python: str = sys.executable) -> dict[str, Any]:
    """One risk call in its own process, its environment built from nothing.
    Raises SpendAuthorityError, and only before starting, if the key is one only
    the treasurer may hold."""
    runner.refuse_spend_authority(credential, environ)
    work_dir.mkdir(parents=True, exist_ok=True)
    result_path = work_dir / "risk-result.json"
    job = {"seat": SEAT, "agent": credential.agent, "system": brief.system, "user": brief.user,
           "model": settings.model, "max_tokens": settings.max_tokens,
           "transport_timeout_s": settings.transport_timeout_s,
           "gateway_url": settings.gateway_url, "pricing": dict(settings.pricing),
           "result_path": str(result_path)}
    job_path = work_dir / "risk-job.json"
    job_path.write_text(json.dumps(job, indent=1) + "\n")
    result_path.write_text(json.dumps({"status": "pending"}) + "\n")
    process = subprocess.Popen([python, "-m", "fund.agents.risk", "--job", str(job_path)],
                               env=runner.child_environment(credential),
                               stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
    try:
        process.wait(timeout=settings.worker_deadline_s)
        killed = None
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()
        killed = "worker deadline"
    stderr = (process.stderr.read() if process.stderr else b"").decode(errors="replace")
    try:
        result = json.loads(result_path.read_text())
    except ValueError:
        result = {"status": "pending"}
    if killed or result.get("status") == "pending":
        result = {**result, "status": "failed", "reason": killed or "crashed",
                  "detail": killed and f"killed at the {killed}" or stderr[-600:]}
    text = json.dumps(result).replace(credential.key, "[GATEWAY_KEY]")
    return {**json.loads(text), "agent": credential.agent, "key_source": credential.source}


def _worker(job: Mapping[str, Any], key: str) -> dict[str, Any]:
    at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
    reply = bankr_llm.complete(key, model=job["model"], system=job["system"], user=job["user"],
                               max_tokens=job["max_tokens"], timeout_s=job["transport_timeout_s"],
                               base_url=job["gateway_url"])
    if reply.error == "timeout" or (reply.error or "").startswith("transport"):
        status, reason = "failed", "timeout" if reply.error == "timeout" else "transport"
    elif reply.status != 200:
        status, reason = "failed", "refused"
    elif reply.error or reply.finish_reason == "length":
        status, reason = "failed", reply.error or "truncated"
    else:
        status, reason = "replied", None
    return {"status": status, "reason": reason, "at": at, "reply_text": reply.text,
            "http_status": reply.status, "error": reply.error,
            "finish_reason": reply.finish_reason, "usage": dict(reply.usage),
            "request_id": reply.request_id, "elapsed_ms": reply.elapsed_ms,
            "cost": bankr_llm.cost(reply.usage, job["pricing"]), "body": reply.body}


def main(argv: list[str] | None = None) -> int:
    """`python -m fund.agents.risk --job <path>`, as `call` starts it."""
    args = sys.argv[1:] if argv is None else argv
    job = json.loads(Path(args[args.index("--job") + 1]).read_text())
    key = os.environ.get(analyst.KEY_VARIABLE, "")
    try:
        result = _worker(job, key)
    except Exception as error:  # a bug in the worker vetoes the plan, it does not crash the cycle
        result = {"status": "failed", "reason": "crashed",
                  "detail": f"{type(error).__name__}: {error}"}
    result["environment_names"] = sorted(os.environ)  # names only: the isolation evidence
    text = json.dumps(result, indent=1, sort_keys=True)
    if key:
        text = text.replace(key, "[GATEWAY_KEY]")
    Path(job["result_path"]).write_text(text + "\n")
    return 0


# --- the review ---------------------------------------------------------------------------------

def review(plan: Mapping[str, Any], plan_sha256: str, *, reports: Sequence[ReportText],
           snapshot: Mapping[str, Any], mandate: Mapping[str, Any], limits: gates.Limits,
           settings: Settings, work_dir: Path, credential: runner.SeatCredential | None = None,
           environ: Mapping[str, str] | None = None, recorded_reply: str | None = None,
           store: report_store.ReportStore | None = None,
           brief_name: str | None = None) -> dict[str, Any]:
    """Gate the plan, measure the bundle, ask the model unless the budget or an
    empty plan says not to, and decide by the override rule.

    With `recorded_reply`, no call is made: the recorded text is read as the
    reply (replay, invariant 7). Otherwise `credential` is required."""
    reported = len(reports)
    first = gates.evaluate(plan, snapshot=snapshot, mandate=mandate, limits=limits,
                           reported=reported)
    brief = render(plan, plan_sha256, first, reports, brief_name=brief_name)
    estimate = context.measure(brief.system + brief.user, reserved_tokens=settings.max_tokens,
                               bytes_per_token=settings.bytes_per_token)
    budget = gates.context_budget(estimate.tokens, limits)
    gate_report = gates.evaluate(plan, snapshot=snapshot, mandate=mandate, limits=limits,
                                 reported=reported, extra=[budget])

    reply: dict[str, Any] | None = None
    votes, no_votes = None, None
    if not budget.passes:
        no_votes = (gates.RULE_CONTEXT_BUDGET, "no call was made: " + budget.reason)
    elif not plan["orders"]:
        no_votes = ("no-orders", "the plan has no orders, so there is nothing to vote on")
    else:
        if recorded_reply is not None:
            reply = {"status": "replied", "reply_text": recorded_reply, "recorded": True}
        else:
            if credential is None:
                raise ValueError("a live review needs the risk seat's credential")
            reply = call(brief, credential, settings, work_dir=work_dir,
                         environ=os.environ if environ is None else environ)
        if reply.get("status") != "replied":
            no_votes = (RULE_RISK_UNAVAILABLE, f"{reply.get('reason')}: "
                        f"{str(reply.get('detail') or reply.get('body') or '')[:300]}")
        else:
            votes, why = parse(reply["reply_text"], plan, plan_sha256)
            if votes is None:
                no_votes = (RULE_RISK_UNREADABLE, why)
    if reply is not None and reply.get("reply_text") and store is not None:
        reply["report_id"] = store.put({
            "seat": SEAT, "agent": reply.get("agent"), "text": reply["reply_text"],
            "text_sha256": hashlib.sha256(reply["reply_text"].encode("utf-8")).hexdigest(),
            "plan_sha256": plan_sha256, "readable": votes is not None,
            "brief_sha256": brief.sha256, "request_id": reply.get("request_id"),
            "sent_at": reply.get("at"), "cost": reply.get("cost")})
    return {"gates": gate_report, "budget": {**estimate.as_dict(), "gate": budget.as_dict()},
            "brief": {"files": [brief_name or BRIEF], "sha256": brief.sha256},
            "reply": None if reply is None else {
                k: reply.get(k) for k in ("status", "reason", "recorded", "report_id", "agent",
                                          "key_source", "request_id", "elapsed_ms", "cost",
                                          "http_status", "environment_names")},
            "reply_text": None if not (reply and reply.get("reply_text")) else reply["reply_text"],
            "reply_sha256": None if not (reply and reply.get("reply_text")) else hashlib.sha256(
                reply["reply_text"].encode("utf-8")).hexdigest(),
            "decision": decide(gate_report, votes, no_votes, plan=plan, snapshot=snapshot,
                               limits=limits)}


if __name__ == "__main__":
    raise SystemExit(main())
