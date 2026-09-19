"""Calls to a signed decision, in one command (units 3.1 to 3.7).

    PYTHONPATH=src python3 -m fund.run.decide --snapshot CAPTURE_OR_FILE
        (--approved-reports | --cycle DIR)
        (--quotes FILE | --live-quotes)
        (--risk-reply FILE | --confirm)
        [--holdings FILE] [--cash USD] [--out DIR] [--env-file PATH]

In order:
1. **The reports.** Either the four written by hand and approved at 2.1, or the
   accepted reports of a runner cycle. Each is checked again by 2.2's validator
   against this snapshot, and only an accepted report counts.
2. **The weights,** from `core/aggregate` (3.1), printed as 3.2's table.
3. **The orders,** from `core/plan` (3.3). Each order gets a fresh quote,
   judged by `adapters/bankr_quote.tradeability` at one instant, `judged_at`:
   - `--live-quotes` asks the venue, read-only, and spends nothing;
   - `--quotes FILE` replays quotes recorded earlier.
   Either way, the quotes used are written to the output as `quotes.json`.
4. **The gates, the budget and the risk vote** (3.4 to 3.6), through
   `agents/risk.review`. That means:
   - `--confirm` makes one live risk call, which is billed;
   - `--risk-reply FILE` reads a recorded reply instead.
5. **The record** (3.7), written as its exact bytes. The treasurer's own signing
   process then signs it: `python -m fund.treasurer.sign`, started with an empty
   environment, reads `SIGNING_KEY` itself. This process never holds the key,
   and nothing outside `treasurer/` imports the signer. Without a key the
   envelope says `signed: false`, and that never authorizes.

**Nothing is executed.** No order is sent, no journal is written, and no book
changes. The paper holdings are an input, as `--holdings`.

Keys are read from `.env` into a mapping, never into this process's
environment, as `agents/runner.py` does. Only the analyst role's keys are used
here: `BANKR_KEY_READ` for quotes and `BANKR_LLM_KEY` for the risk call.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

from fund import config, credentials
from fund.adapters import bankr_quote
from fund.agents import risk, runner, schema
from fund.core import aggregate, gates, plan, record
from fund.core.types import (
    Amount, AssetId, Instant, Observation, document_id, from_canonical, to_canonical,
)
from fund.store import reports as report_store

ROOT = config.REPO_ROOT
SRC = ROOT / "src"
FORMAT = ROOT / "planning" / "REPORT-FORMAT.md"
SEATS = ("price-trend", "cross-asset-macro", "execution-quality", "price-integrity")
LIVE_DECISIONS = ROOT / "fixtures" / "live" / "decisions"  # gitignored


@dataclass(frozen=True)
class Offered:
    """One report offered to the decision, before it is checked again."""

    seat: str
    agent: str
    text: str
    source: str


def approved_reports(path: Path = FORMAT) -> list[Offered]:
    """The four reports written by hand and approved at 2.1, each with the agent
    its own first line names."""
    text = path.read_text()
    out = []
    for seat in SEATS:
        body = text.split(f". {seat}\n", 1)[1].split("```\n", 2)[1]
        agent = body.split("\n", 1)[0].split()[2]
        out.append(Offered(seat, agent, body, "hand-written, approved at 2.1 "
                                              "(planning/REPORT-FORMAT.md)"))
    return out


def cycle_reports(cycle_dir: Path) -> list[Offered]:
    """The accepted reports of one runner cycle, with the agent the runner assigned."""
    out = []
    for path in sorted((cycle_dir / "results").glob("*.json")):
        result = json.loads(path.read_text())
        if result.get("status") in ("ok", "no_call") and result.get("report_text"):
            out.append(Offered(result["seat"], result["agent"], result["report_text"],
                               f"runner cycle {cycle_dir.name}"))
    return out


def check(offered: Sequence[Offered], snapshot: Mapping[str, Any], snapshot_sha256: str
          ) -> tuple[list[tuple[Offered, schema.Verdict]], list[tuple[Offered, str]]]:
    """Every report checked again against this snapshot. Only accepted ones count,
    each with its verdict, which records any citation that was loose."""
    accepted, refused = [], []
    for report in offered:
        verdict = schema.validate(report.text, snapshot,
                                  contract=schema.Contract.load(report.seat),
                                  agent=report.agent, snapshot_sha256=snapshot_sha256)
        if verdict.ok:
            accepted.append((report, verdict))
        else:
            refused.append((report, "; ".join(str(r) for r in verdict.refusals)))
    return accepted, refused


def load_holdings(path: Path | None, snapshot: Mapping[str, Any]) -> dict[str, Amount]:
    """Paper holdings: `{address: amount text}`. Decimals come from the snapshot."""
    if path is None:
        return {}
    chain_id = snapshot["block"]["chain_id"]
    decimals = {a["asset"]["address"].lower(): a["asset"]["decimals"] for a in snapshot["assets"]}
    return {address.lower(): Amount.from_units(units, decimals[address.lower()],
                                               AssetId(chain_id, address.lower()))
            for address, units in json.loads(path.read_text()).items()}


# --- quotes: fetched here, where I/O is allowed --------------------------------------------------

def _analyst_secret(environ: Mapping[str, str]) -> Callable[[str], str]:
    """A secret the analyst role may hold, from a mapping, and no other."""
    def secret(name: str) -> str:
        if credentials.Role.ANALYST not in credentials.by_name(name).used_by:
            raise config.CredentialNotPermittedError(f"{name} is not the analyst role's")
        if not environ.get(name):
            raise config.MissingCredentialError(f"{name} is not set")
        return environ[name]
    return secret


def live_quotes(intents: Sequence[plan.Intent], environ: Mapping[str, str]
                ) -> tuple[dict[int, Observation], Instant]:
    """Each order quoted by the venue, read-only, then one judging instant."""
    adapter = bankr_quote.Settings.load().adapter(_analyst_secret(environ))
    seen = {i.index: adapter.quote(bankr_quote.QuoteRequest(sell=i.sell, buy=i.buy,
                                                            buy_decimals=i.buy_decimals))
            for i in intents}
    return seen, Instant(time.time_ns() // 1_000_000)


def recorded_quotes(path: Path) -> tuple[dict[int, Observation], Instant]:
    data = json.loads(path.read_text())
    return ({q["index"]: from_canonical(json.dumps(q["observation"]).encode())
             for q in data["quotes"]}, Instant(data["judged_at_ms"]))


def quotes_file(observations: Mapping[int, Observation], judged_at: Instant, label: str
                ) -> dict[str, Any]:
    return {"judged_at_ms": judged_at.epoch_ms, "label": label,
            "quotes": [{"index": i, "observation": json.loads(to_canonical(o))}
                       for i, o in sorted(observations.items())]}


def judge(intents: Sequence[plan.Intent], observations: Mapping[int, Observation],
          judged_at: Instant) -> dict[int, plan.QuoteSeen]:
    """Every fresh quote judged at one instant by the one definition of quote age
    and impact. An order with no quote is left out, and its gate blocks."""
    limits = bankr_quote.Limits.from_thresholds(config.load_json("thresholds.json"))
    out = {}
    for intent in intents:
        if intent.index in observations:
            verdict = bankr_quote.tradeability(observations[intent.index], intent.sell,
                                               judged_at, limits)
            out[intent.index] = plan.QuoteSeen(verdict.quote, verdict.verdict, verdict.rule,
                                               verdict.age_ms)
    return out


# --- signing: the treasurer's own process -------------------------------------------------------

def signed(record_path: Path, envelope_path: Path, env_file: Path | None,
           python: str = sys.executable) -> dict[str, Any]:
    """The treasurer signs the record in its own process, from an empty environment.
    This process never holds the key."""
    command = [python, "-m", "fund.treasurer.sign", "--sign", str(record_path),
               "--out", str(envelope_path)]
    if env_file is not None:
        command += ["--env-file", str(env_file)]
    empty = {"PATH": os.environ.get("PATH", os.defpath), "PYTHONPATH": str(SRC)}
    subprocess.run(command, env=empty, check=True, capture_output=True, timeout=120)
    return json.loads(envelope_path.read_text())


def verified(record_path: Path, envelope_path: Path, public_key: str | None,
             python: str = sys.executable) -> dict[str, Any]:
    empty = {"PATH": os.environ.get("PATH", os.defpath), "PYTHONPATH": str(SRC)}
    done = subprocess.run([python, "-m", "fund.treasurer.sign", "--verify", str(record_path),
                           str(envelope_path), "--public-key", public_key or ""],
                          env=empty, capture_output=True, text=True, timeout=120)
    return json.loads(done.stdout)


# --- the decision --------------------------------------------------------------------------------

def _write(path: Path, document: Any) -> None:
    path.write_text(json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False) + "\n")


def decide(*, snapshot_path: Path, offered: Sequence[Offered], holdings: Mapping[str, Amount],
           cash_usd: Decimal, out_dir: Path,
           quotes: Callable[[Sequence[plan.Intent]], tuple[dict[int, Observation], Instant]],
           quote_label: str, risk_settings: risk.Settings,
           risk_credential: runner.SeatCredential | None, risk_agent: str,
           environ: Mapping[str, str],
           recorded_reply: str | None, store: report_store.ReportStore,
           env_file: Path | None) -> dict[str, Any]:
    """The whole path from calls to a signed record. Returns what it wrote.

    `risk_agent` is the risk seat's identity from its key source, the same whether
    the vote is asked live or read from a recording. Until the 3.8 sweep it was
    taken from the live credential, so a replay recorded none where the live run
    recorded `unassigned`, and the same inputs gave two records (R4)."""
    snapshot_bytes = snapshot_path.read_bytes()
    snapshot = json.loads(snapshot_bytes)
    snapshot_sha256 = hashlib.sha256(snapshot_bytes).hexdigest()
    out_dir.mkdir(parents=True, exist_ok=True)

    accepted, refused = check(offered, snapshot, snapshot_sha256)
    thresholds, mandate = config.load_json("thresholds.json"), config.load_json("mandate.json")
    models, analysts = config.load_json("models.json"), config.load_json("analysts.json")
    limits = gates.Limits.from_config(thresholds, mandate, models)

    the_book = plan.book(holdings, cash_usd, snapshot)
    symbols = {a["asset"]["address"].lower(): a["asset"]["symbol"] for a in snapshot["assets"]}
    proposal = aggregate.aggregate(
        [v.report.as_dict() for _, v in accepted],
        kinds={a["id"]: a["vocabulary"] for a in analysts["analysts"]},
        current=the_book.weights, cash_weight=the_book.cash_weight,
        limits=limits, symbols=symbols,
        confidence_weights={w: Decimal(v) for w, v in analysts["confidence_weights"].items()})
    table = aggregate.table(proposal, list(SEATS), the_book.nav_usd)

    intents = plan.size(proposal, the_book, snapshot, limits)
    observations, judged_at = quotes(intents)
    _write(out_dir / "quotes.json", quotes_file(observations, judged_at, quote_label))
    written = plan.write(intents, judge(intents, observations, judged_at), proposal=proposal,
                         the_book=the_book, snapshot=snapshot, snapshot_sha256=snapshot_sha256,
                         judged_at=judged_at)
    plan_sha256 = document_id(written)

    outcome = risk.review(written, plan_sha256, snapshot=snapshot, mandate=mandate,
                          limits=limits, settings=risk_settings, work_dir=out_dir / "risk",
                          reports=[risk.ReportText(o.seat, o.text) for o, _ in accepted],
                          credential=risk_credential, environ=environ,
                          recorded_reply=recorded_reply, store=store)

    config_sha256 = {name: hashlib.sha256((config.CONFIG_DIR / name).read_bytes()).hexdigest()
                     for name in record.CONFIG_FILES}
    the_record = record.build(
        snapshot=snapshot, snapshot_sha256=snapshot_sha256,
        reports=[{"seat": o.seat, "agent": o.agent, "text": o.text,
                  "imprecise_citations": [i.as_dict() for i in v.imprecisions]}
                 for o, v in accepted],
        config_sha256=config_sha256, proposal=proposal.as_dict(), plan=written, review=outcome,
        risk_agent=risk_agent,
        risk_reply=outcome["reply_text"])
    record_path = out_dir / "record.json"
    record_path.write_bytes(record.encode(the_record))
    envelope = signed(record_path, out_dir / "envelope.json", env_file)
    check_ = verified(record_path, out_dir / "envelope.json", envelope.get("public_key"))

    (out_dir / "table.txt").write_text(table + "\n")
    _write(out_dir / "reports.json", {
        "accepted": [{"seat": o.seat, "agent": o.agent, "source": o.source} for o, _ in accepted],
        "refused": [{"seat": o.seat, "why": why} for o, why in refused]})
    _write(out_dir / "proposal.json", proposal.as_dict())
    _write(out_dir / "plan.json", written)
    _write(out_dir / "risk.json", {k: v for k, v in outcome.items() if k != "reply_text"})
    return {"snapshot_sha256": snapshot_sha256, "accepted": [o.seat for o, _ in accepted],
            "refused": [(o.seat, why) for o, why in refused], "table": table,
            "plan": written, "plan_sha256": plan_sha256, "review": outcome,
            "record": the_record, "decision_id": record.decision_id(the_record),
            "envelope": envelope, "authorizes": check_, "out_dir": str(out_dir)}


def summary(done: Mapping[str, Any]) -> str:
    lines = [f"snapshot   {done['snapshot_sha256']}",
             f"reports    accepted: {', '.join(done['accepted']) or 'none'}"]
    lines += [f"           refused: {seat}: {why[:120]}" for seat, why in done["refused"]]
    lines += ["", done["table"], ""]
    review = done["review"]
    for plan_gate in review["gates"]["plan"]:
        lines.append(f"plan gate  {plan_gate['rule']:16} {plan_gate['value']!s:5}  "
                     f"{plan_gate['reason']}")
    orders = {o["index"]: o for o in done["plan"]["orders"]}
    decided = {o["index"]: o for o in review["decision"]["orders"]}
    lines.append("")
    for order in review["gates"]["orders"]:
        o, d = orders[order["index"]], decided[order["index"]]
        lines.append(f"order {o['index']:>2}   {o['side']:4} {o['asset']['symbol']:5} "
                     f"${Decimal(o['usd']):>6.2f}  gates {'cleared' if order['cleared'] else 'BLOCKED by ' + ', '.join(order['blocked_by'])}"
                     f"  risk {d['model_vote'] or '-'}  => "
                     f"{'APPROVED' if d['approved'] else 'VETOED by ' + ', '.join(d['vetoed_by'])}")
        if d.get("model_why"):
            lines.append(f"            risk: {d['model_why'][:150]}")
    budget = review["budget"]
    funding = done["plan"].get("funding") or {}
    if funding.get("share_funded") is not None:
        lines.append(f"funding    the plan funds {Decimal(funding['share_funded']) * 100:.2f}% of "
                     f"the raises the calls want, from cash above the floor")
    floor = review["decision"].get("cash_floor") or {}
    lines += [f"cash       after the approved orders: {floor.get('reason')}",
              "", f"risk       bundle: {budget['gate']['reason']}"]
    if review["decision"]["overall"]:
        lines.append(f"           overall {review['decision']['overall']['vote']}: "
                     f"{review['decision']['overall']['why'][:150]}")
    if review["decision"]["no_votes"]:
        lines.append(f"           no votes: {review['decision']['no_votes']}")
    envelope = done["envelope"]
    lines += ["", f"record     decision {done['decision_id']}",
              f"           signed {envelope['signed']}"
              + (f" by {envelope['public_key']}" if envelope["signed"] else
                 f": {envelope.get('why')}"),
              f"           authorizes {done['authorizes']['authorizes']}: "
              f"{done['authorizes']['reason']}",
              f"           nothing was executed. Files in {done['out_dir']}"]
    return "\n".join(lines)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fund.run.decide")
    parser.add_argument("--snapshot", required=True, type=Path,
                        help="a capture directory or a snapshot.json")
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--approved-reports", action="store_true",
                        help="the four hand-written reports approved at 2.1")
    source.add_argument("--cycle", type=Path, help="a runner cycle's directory")
    quoting = parser.add_mutually_exclusive_group(required=True)
    quoting.add_argument("--quotes", type=Path, help="recorded quotes, replayed")
    quoting.add_argument("--live-quotes", action="store_true", help="read-only venue quotes")
    voting = parser.add_mutually_exclusive_group(required=True)
    voting.add_argument("--risk-reply", type=Path, help="a recorded risk reply, replayed")
    voting.add_argument("--confirm", action="store_true", help="one live risk call; it is billed")
    parser.add_argument("--holdings", type=Path, help="paper holdings, {address: amount}")
    parser.add_argument("--cash", type=Decimal, default=None,
                        help="paper cash in USD; default thresholds.json capital_usd")
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--env-file", type=Path, default=None, help="for the signer only")
    args = parser.parse_args(argv)

    snapshot_path = args.snapshot / "snapshot.json" if args.snapshot.is_dir() else args.snapshot
    snapshot = json.loads(snapshot_path.read_bytes())
    environ = {**config.parse_env_file(config.ENV_FILE), **os.environ}
    offered = approved_reports() if args.approved_reports else cycle_reports(args.cycle)
    cash = args.cash if args.cash is not None else Decimal(
        config.load_json("thresholds.json")["capital_usd"])
    if args.quotes:
        quotes, label = (lambda intents: recorded_quotes(args.quotes)), f"replayed: {args.quotes}"
    else:
        quotes, label = (lambda intents: live_quotes(intents, environ)), "live, read-only"
    credential = None
    reply = None
    if args.confirm:
        credential = runner.SharedGatewayKey(environ).for_seat(risk.SEAT)
        runner.refuse_spend_authority(credential, environ)
    else:
        reply = args.risk_reply.read_text()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    out_dir = args.out or LIVE_DECISIONS / stamp
    store = report_store.ReportStore(runner.LIVE_REPORTS if args.confirm else out_dir / "store")
    done = decide(snapshot_path=snapshot_path, offered=offered,
                  holdings=load_holdings(args.holdings, snapshot), cash_usd=cash,
                  out_dir=out_dir, quotes=quotes, quote_label=label,
                  risk_settings=risk.Settings.from_config(), risk_credential=credential,
                  risk_agent=runner.SharedGatewayKey(environ).for_seat(risk.SEAT).agent,
                  environ=environ, recorded_reply=reply, store=store, env_file=args.env_file)
    print(summary(done))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
