"""One analyst: brief, call, parse, validate (units 2.3 and 2.4).

**The brief (2.3).** What each seat receives is built from versioned files, not
inline strings:
  - the seat's own file, `briefs/<seat>.v1.md`: its mandate, its vocabulary,
    what to read, and effort guidance. Its question and the questions it leaves
    to the others come from `config/analysts.json` and are written into the
    file's `{question}` and `{not_asked}` markers, so the brief and the config
    cannot drift apart;
  - the part every seat shares, `briefs/analyst.v1.md`: the output contract
    approved at 2.1;
  - the snapshot, as its own bytes, between `SNAPSHOT <sha256> <n> bytes` and
    `END SNAPSHOT`. It is byte-identical for every seat and named by its hash
    (invariant 2);
  - the exact first line the report must begin with.

The system message is the seat's file plus the shared part. The user message is
the snapshot plus the first line.
"""

from __future__ import annotations

import hashlib
import json
import os
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from fund import config
from fund.adapters import bankr_llm
from fund.agents import schema

BRIEFS = Path(__file__).resolve().parent / "briefs"
SHARED_BRIEF = "analyst.v1.md"


@dataclass(frozen=True)
class Brief:
    seat: str
    system: str
    user: str
    files: tuple[str, ...]  # the versioned files it was built from
    snapshot_sha256: str
    header: str  # the first line the report must carry

    @property
    def sha256(self) -> str:
        return hashlib.sha256((self.system + "\x00" + self.user).encode("utf-8")).hexdigest()


def snapshot_section(snapshot: bytes) -> str:
    """The snapshot as every seat receives it: its own bytes, named by their hash."""
    digest = hashlib.sha256(snapshot).hexdigest()
    return f"SNAPSHOT {digest} {len(snapshot)} bytes\n{snapshot.decode('utf-8')}\nEND SNAPSHOT"


def render(seat: str, snapshot: bytes, agent: str, *, analysts: Mapping[str, Any] | None = None,
           briefs: Path = BRIEFS) -> Brief:
    """The brief for one seat on one snapshot. Raises for a seat the config does not
    define or does not give a question: a vague brief is what makes two seats do
    the same work."""
    analysts = config.load_json("analysts.json") if analysts is None else analysts
    entry = next((a for a in analysts["analysts"] if a["id"] == seat), None)
    if entry is None:
        raise KeyError(f"{seat} is not a seat in config/analysts.json")
    if not entry.get("question") or not entry.get("not_asked"):
        raise ValueError(f"{seat} has no question, or no list of the questions it leaves "
                         "to others, in config/analysts.json")
    own = (briefs / entry["brief"]).read_text()
    not_asked = "\n".join(f"- {question}" for question in entry["not_asked"])
    system = (own.replace("{question}", entry["question"]).replace("{not_asked}", not_asked)
              + "\n\n" + (briefs / SHARED_BRIEF).read_text())
    digest = hashlib.sha256(snapshot).hexdigest()
    header = f"REPORT {seat} {agent} {digest}"
    user = (snapshot_section(snapshot)
            + f"\n\nWrite your report now. Its first line must be exactly:\n{header}\n")
    return Brief(seat=seat, system=system, user=user, files=(entry["brief"], SHARED_BRIEF),
                 snapshot_sha256=digest, header=header)


# --- the worker (unit 2.4) -----------------------------------------------------------------------
#
# Each analyst runs as its own process, started by `agents/runner.py` with an
# environment built from nothing: its one gateway key under KEY_VARIABLE, plus
# PATH and PYTHONPATH. It takes that key from its environment and nowhere else.
# It never calls `config.load()` or `config.load_environment()`, which would merge
# the whole of `.env`, execution and signing keys included, into its environment.
# What it is given arrives in a job file with no secret in it. What it writes goes
# to the result slot the runner allocated before starting it.
#
# One call, then at most one retry, and only for a reply that arrived and was
# refused as malformed: unparseable, cut off at the output cap, or refused by the
# 2.2 checks. Never for a timeout, a transport failure or a refusal from the
# gateway. A timed-out call is still billed (F0.9.3), and retrying it doubles the
# bill for nothing. The retry must fit in what is left of the worker's deadline.

KEY_VARIABLE = "OPENFUND_GATEWAY_KEY"


def _attempt_record(number: int, at: str, reply: bankr_llm.Reply, price: Mapping[str, Any],
                    refusals: tuple = ()) -> dict:
    """One call, as the record keeps it: the reply's text in full, exactly as the model
    wrote it (what `agents/show.py` prints), and its cost, an estimate from its own
    usage block (2.5). `at` is when it was sent, which places it in a usage window."""
    return {"attempt": number, "at": at, "elapsed_ms": reply.elapsed_ms,
            "reply_text": reply.text,
            "http_status": reply.status, "error": reply.error,
            "finish_reason": reply.finish_reason, "usage": dict(reply.usage),
            "request_id": reply.request_id, "cost": bankr_llm.cost(reply.usage, price),
            "refusals": [str(r) for r in refusals], "body": reply.body}


def seat_cost(attempts: list[dict]) -> dict[str, Any]:
    """What one analyst's turn cost: the sum of its calls' estimates. A per-analyst
    figure is an estimate, and says so. The provider never splits spend by analyst
    (F0.6.4)."""
    known = [a["cost"]["usd"] for a in attempts if a["cost"]["usd"] is not None]
    usd = sum((Decimal(u) for u in known), Decimal(0))
    return {"usd": f"{usd.normalize():f}", "calls": len(attempts),
            "calls_of_unknown_cost": len(attempts) - len(known), **bankr_llm.ESTIMATE,
            "basis": "the sum of this analyst's calls, each from its own usage block"}


def run(job: Mapping[str, Any], key: str, *, send: Any = None,
        clock: Any = None) -> dict[str, Any]:
    """One analyst's whole turn. Returns its result, never raises for anything the
    model or the network does."""
    clock = time.monotonic if clock is None else clock
    started = clock()
    snapshot = Path(job["snapshot_path"]).read_bytes()
    result: dict[str, Any] = {
        "seat": job["seat"], "agent": job["agent"], "status": "failed", "reason": None,
        "detail": None, "attempts": [], "report": None, "report_text": None,
        "snapshot_sha256": hashlib.sha256(snapshot).hexdigest(),
    }
    if result["snapshot_sha256"] != job["snapshot_sha256"]:
        result.update(reason="snapshot", detail="the snapshot on disk is not the one named")
        return result

    brief = render(job["seat"], snapshot, job["agent"])
    contract = schema.Contract.load(job["seat"])
    document = json.loads(snapshot)
    result.update(brief_files=list(brief.files), brief_sha256=brief.sha256)
    margin = job["worker_deadline_s"] - job["transport_timeout_s"]
    user = brief.user
    for number in range(1, 2 + job["retry_budget"]):
        left = job["worker_deadline_s"] - (clock() - started) - margin
        timeout_s = min(job["transport_timeout_s"], left)
        if timeout_s <= 0:
            result.update(reason="no time", detail="no time left in the worker deadline "
                          "for another attempt")
            break
        at = datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")
        reply = bankr_llm.complete(key, model=job["model"], system=brief.system, user=user,
                                   max_tokens=job["max_tokens"], timeout_s=timeout_s,
                                   base_url=job["gateway_url"], send=send)
        if reply.error == "timeout" or (reply.error or "").startswith("transport"):
            result["attempts"].append(_attempt_record(number, at, reply, job["pricing"]))
            result.update(reason="timeout" if reply.error == "timeout" else "transport",
                          detail=reply.error)
            break  # billed or not, a lost call is never retried
        if reply.status != 200:
            result["attempts"].append(_attempt_record(number, at, reply, job["pricing"]))
            result.update(reason="refused", detail=f"HTTP {reply.status}: {reply.body[:300]}")
            break
        if reply.error or reply.finish_reason == "length":
            refusals = (schema.Refusal("truncated" if reply.finish_reason == "length"
                                       else "unreadable",
                                       reply.error or "the reply stopped at the output cap"),)
            verdict = None
        else:
            verdict = schema.validate(reply.text, document, contract=contract,
                                      agent=job["agent"], snapshot_sha256=brief.snapshot_sha256)
            refusals = verdict.refusals
        result["attempts"].append(_attempt_record(number, at, reply, job["pricing"], refusals))
        if verdict is not None and verdict.ok:
            result.update(status="no_call" if verdict.report.no_calls else "ok", reason=None,
                          detail=None, report=verdict.report.as_dict(),
                          report_text=verdict.report.text)
            break
        result.update(reason="invalid", detail="; ".join(str(r) for r in refusals),
                      last_reply_text=reply.text)
        user = (brief.user + "\n\nYour previous reply was refused: "
                + "; ".join(str(r) for r in refusals)
                + "\nWrite the whole report again, in the required format.\n")
    result["cost"] = seat_cost(result["attempts"])
    return result


def main(argv: list[str] | None = None) -> int:
    """`python -m fund.agents.analyst --job <path>`, as the runner starts it."""
    args = sys.argv[1:] if argv is None else argv
    job = json.loads(Path(args[args.index("--job") + 1]).read_text())
    key = os.environ.get(KEY_VARIABLE, "")
    try:
        result = run(job, key)
    except Exception as error:  # a bug in the worker fails its seat, not the cycle
        result = {"seat": job.get("seat"), "agent": job.get("agent"), "status": "failed",
                  "reason": "crashed", "detail": f"{type(error).__name__}: {error}",
                  "attempts": []}
    # Names only, never values: the evidence the isolation test reads.
    result["environment_names"] = sorted(os.environ)
    text = json.dumps(result, indent=1, sort_keys=True)
    if key:
        text = text.replace(key, "[GATEWAY_KEY]")
    Path(job["result_path"]).write_text(text + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
