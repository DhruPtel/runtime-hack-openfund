"""The decision record (unit 3.7). Kept whole: this is what the fund sells.

One canonical JSON document holds the decision and everything it stands on:
- **the snapshot:** its sha256, block and build time;
- **every accepted report:** its seat, agent, text and the sha256 of the text,
  and every citation in it that was loose: a real value cited under an imprecise
  reference, which 2.2 accepts and records (since 3.8);
- **the config the decision read:** the sha256 of each file;
- **the proposal, the plan, the gates' verdicts and the risk agent's output:**
  its reply in full, its sha256, and the decision the override rule reached;
- **every closed-session finding the snapshot carries,** so a buyer sees what
  was judged expected rather than refused (DECISION 2026-09-18);
- **the decision:** each order approved or vetoed, and by what.

A `hashes` block repeats the sha256 of each part, so a buyer can check any part
separately.

**Nothing in it was executed.** It is a decision, signed. Orders are Phase 4's,
and fills are Phase 4's and 5's.

**No clock time that is not a recorded input.** The record's only time is the
plan's `judged_at_ms`, recorded when the fresh quotes were judged. It holds no
call timings, costs or request ids; those stay in the cycle's own files. So the
same recorded inputs rebuild the same bytes (3.9).

The bytes are `types.document_bytes` of the record, and the decision id is
their sha256. `treasurer/sign.py` signs exactly those bytes.
"""

from __future__ import annotations

import hashlib
from typing import Any, Mapping, Sequence

from .types import document_bytes, document_id

SCHEMA = "openfund.decision/1"

#: The config files a decision reads.
CONFIG_FILES = ("analysts.json", "mandate.json", "models.json", "thresholds.json")


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build(*, snapshot: Mapping[str, Any], snapshot_sha256: str,
          reports: Sequence[Mapping[str, str]], config_sha256: Mapping[str, str],
          proposal: Mapping[str, Any], plan: Mapping[str, Any], review: Mapping[str, Any],
          risk_agent: str | None, risk_reply: str | None) -> dict[str, Any]:
    """The record, as a plain document. `reports` are the accepted ones, each
    with `seat`, `agent`, `text` and its `imprecise_citations`. `review` is
    `agents/risk.review`'s result."""
    carried = sorted(({"seat": r["seat"], "agent": r["agent"], "text": r["text"],
                       "sha256": _sha256(r["text"]),
                       "imprecise_citations": list(r.get("imprecise_citations") or ())}
                      for r in reports),
                     key=lambda r: r["seat"])
    findings = [{"symbol": a["asset"]["symbol"], "address": a["asset"]["address"], **finding}
                for a in snapshot["assets"] for finding in a.get("findings") or ()]
    orders = {o["index"]: o for o in plan["orders"]}
    decided = review["decision"]
    decision = {
        "rebalance": proposal["rebalance"],
        "approved": [{"index": o["index"], "symbol": o["symbol"], "side": orders[o["index"]]["side"],
                      "usd": orders[o["index"]]["usd"]} for o in decided["orders"] if o["approved"]],
        "vetoed": [{"index": o["index"], "symbol": o["symbol"], "side": orders[o["index"]]["side"],
                    "usd": orders[o["index"]]["usd"], "vetoed_by": o["vetoed_by"]}
                   for o in decided["orders"] if not o["approved"]],
        "executed": "nothing: a signed decision, not a trade (execution is Phases 4 and 5)"}
    risk = {"seat": "risk", "agent": risk_agent, "brief": review["brief"],
            "budget": review["budget"],
            "reply_status": None if review["reply"] is None else review["reply"]["status"],
            "reply_text": risk_reply,
            "reply_sha256": None if risk_reply is None else _sha256(risk_reply),
            "decision": decided}
    return {
        "schema": SCHEMA,
        "decided_at_ms": plan["judged_at_ms"],
        "snapshot": {"sha256": snapshot_sha256, "schema": snapshot["schema"],
                     "block": snapshot["block"], "built_at": snapshot["built_at"]},
        "reports": carried,
        "config": dict(sorted(config_sha256.items())),
        "proposal": proposal,
        "plan": plan,
        "gates": review["gates"],
        "risk": risk,
        "findings": findings,
        "decision": decision,
        "hashes": {"snapshot": snapshot_sha256,
                   "reports": {r["seat"]: r["sha256"] for r in carried},
                   "config": dict(sorted(config_sha256.items())),
                   "proposal": document_id(proposal), "plan": document_id(plan),
                   "gates": document_id(review["gates"]),
                   "risk_reply": risk["reply_sha256"]},
    }


def encode(record: Mapping[str, Any]) -> bytes:
    """The bytes that are hashed, signed and sold."""
    return document_bytes(record)


def decision_id(record: Mapping[str, Any]) -> str:
    return hashlib.sha256(encode(record)).hexdigest()
