"""The operator's signed instruction for the live leg (5.2).

Every order this fund sends is authorized in writing, and the chokepoint verifies
that writing against the published key before anything is submitted. An
analyst-driven order's authority is the signed decision record (4.2, 4.4).

**The live leg has no analyst behind it.** It is *a demonstration of the money path
that no analyst chose* (`planning/SIMPLIFICATION.md`, DECISION 2026-09-19), and the
same decision says no decision is manufactured to justify it. Two things follow: a
record cannot be written for it without inventing reports and a risk vote that never
happened, and it cannot go unauthorized either — it is the one path that spends real
money. So it carries its own artefact: **one order, in the plan's own layout, signed
by the same key, in the same envelope, verified the same way.**

What it is not is a decision. It carries no reports, no weights and no risk vote, and
`quorum` does not apply to it: nobody voted, and a gate that claimed otherwise would
be false. What it *is* judged against is the mandate the operator approved — the
chain, the wallet, the legs, the per-trade limit, the cumulative live budget and the
expiry — plus the same fresh-quote, price, holding and snapshot-age gates every order
passes. Each of those comparisons is still made by `core/gates.py`, the one module
that makes them; this module names which of them an instruction must pass
(`treasurer/execute.py:admit_instruction`).

**Identity.** The instruction's id is the sha256 of its own bytes, which is what
`sign.sign` puts in the envelope, so the order's id and idempotency key (4.0 P2)
derive from exactly what was authorized and no more. Re-deriving them after a crash
gives the same key, and there is still no way to mint a new one.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping

from fund.core import cash, orders, plan
from fund.core.types import (
    Amount, AssetId, ChainAddress, ExecutionMode, Instant, Observation, Order, OrderState,
    from_canonical,
)
from fund.treasurer import sign
from fund.treasurer import mandate as mandates

SCHEMA = "openfund.instruction/1"

#: The only reason an instruction exists. It is written into every one of them.
DEMONSTRATION = ("a demonstration of the money path that no analyst chose "
                 "(planning/SIMPLIFICATION.md, DECISION 2026-09-19)")


class InstructionError(ValueError):
    """The instruction cannot become an order: the reason is named."""


def document(*, sell: Amount, symbol: str, buy: AssetId, buy_decimals: int,
             quote: plan.QuoteSeen, snapshot: Mapping[str, Any], snapshot_sha256: str,
             mandate: Mapping[str, Any], issued_at: Instant, expires_at: Instant,
             reason: str = DEMONSTRATION) -> dict[str, Any]:
    """One instruction, as a plain document. Its order is written in the plan's own
    layout so that the gates read it exactly as they read a planned order."""
    if expires_at.epoch_ms <= issued_at.epoch_ms:
        raise InstructionError("an instruction expires after it is issued")
    order = {  # index 1: an order's index is its plan index, a whole number from one
        "index": 1, "side": "sell",
        "asset": {"chain_id": snapshot["block"]["chain_id"], "address": sell.asset.address,
                  "symbol": symbol},
        "sell": {"address": sell.asset.address, "decimals": sell.decimals,
                 "amount": format(Decimal(sell.raw).scaleb(-sell.decimals), "f")},
        "buy": {"address": buy.address, "decimals": buy_decimals},
        "quote": plan.quote_record(quote, "sell"),
    }
    order["usd"] = format(cash.order_worth(order, snapshot), "f")
    return {
        "schema": SCHEMA,
        "issued_at_ms": issued_at.epoch_ms,
        "expires_at_ms": expires_at.epoch_ms,
        "book": "real",
        "reason": reason,
        "mandate": {"chain_id": mandate["chain_id"],
                    "execution_wallet": mandate["execution_wallet"],
                    "approved_by": mandate.get("approved_by")},
        "snapshot": {"sha256": snapshot_sha256, "block": snapshot["block"]},
        "order": order,
        "not_a_decision": "no analyst proposed this order and no risk agent voted on it, so it "
                          "carries no reports and no vote, and the quorum gate does not apply. "
                          "Its authority is this signature and the mandate.",
    }


def write(directory: Path, doc: Mapping[str, Any]) -> tuple[Path, Path]:
    """Write `instruction.json`, and say where it and its envelope belong. The
    envelope is the signing process's to write (`run/decide.py:signed`): the key is
    the treasurer's, and no other process holds it."""
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / "instruction.json"
    path.write_text(json.dumps(doc, indent=1, sort_keys=True, ensure_ascii=False) + "\n")
    return path, directory / "envelope.json"


def read(directory: Path) -> tuple[bytes, dict[str, Any]]:
    return ((directory / "instruction.json").read_bytes(),
            json.loads((directory / "envelope.json").read_text()))


def order_of(instruction_bytes: bytes, envelope: Mapping[str, Any], *, public_key: str | None,
             mandate: Mapping[str, Any], at: Instant) -> Order:
    """The live order one signed instruction authorizes, `prepared`.

    It refuses, by name, exactly as `intent.intents` does for a record: an
    unpublished key, a signature that does not verify, a mandate out of force, and a
    chain that is not the mandate's. It adds the instruction's own expiry: authority
    to spend does not outlive the window the operator gave it."""
    if public_key is None:
        raise InstructionError("no key is published in keys.json, so nothing authorizes")
    signed = sign.authorizes(envelope, instruction_bytes, public_key)
    if not signed.passes:
        raise InstructionError(f"the instruction does not authorize: {signed.reason}")
    try:
        mandates.in_force(mandate, at)
    except mandates.MandateError as refused:
        raise InstructionError(f"the mandate is not in force: {refused}") from None
    doc = json.loads(instruction_bytes)
    if doc.get("schema") != SCHEMA:
        raise InstructionError(f"{doc.get('schema')!r} is not {SCHEMA}")
    if at.epoch_ms > doc["expires_at_ms"]:
        raise InstructionError(f"the instruction expired at {doc['expires_at_ms']}, and it is "
                               f"{at.epoch_ms}")
    chain = doc["snapshot"]["block"]["chain_id"]
    if chain != mandate["chain_id"]:
        raise InstructionError(f"the instruction is on chain {chain}, the mandate on "
                               f"{mandate['chain_id']}")
    order = doc["order"]
    if order["quote"] is None:
        raise InstructionError("the instruction carries no quote for its order")
    quote = from_canonical(json.dumps(order["quote"]["observation"]).encode()).value
    sold = order["sell"]
    return Order(
        order_id=orders.order_id(envelope["decision_id"], order["index"]),
        idempotency_key=orders.idempotency_key(envelope["decision_id"], order["index"]),
        mode=ExecutionMode.LIVE,
        wallet=ChainAddress(chain, mandate["execution_wallet"].lower()),
        sell=Amount.from_units(sold["amount"], sold["decimals"],
                               AssetId(chain, sold["address"].lower())),
        buy_asset=AssetId(chain, order["buy"]["address"].lower()),
        min_buy=quote.min_buy, state=OrderState.PREPARED)


def carried_quote(doc: Mapping[str, Any]) -> Observation:
    """The observation the instruction carries for its order, as it was taken."""
    return from_canonical(json.dumps(doc["order"]["quote"]["observation"]).encode())


@dataclass(frozen=True)
class Carried:
    """The venue's interface over the quote an instruction carries.

    The treasurer holds no read key — `BANKR_KEY_READ` is the analyst's, and the quote
    adapter refuses any credential that can transact — so on the live leg the
    chokepoint cannot fetch a quote of its own. It judges the one the instruction
    carries instead, through the same `requote` and the same
    `bankr_quote.tradeability`: the quote must be for this exact order, and it must
    still be fresh at the clock the treasurer runs at. One that aged past
    `quote_max_age_seconds` between the signature and the chokepoint is refused by the
    `quote` gate, exactly as a stale live quote would be.

    **The limitation is real, and stated:** on the live leg the chokepoint re-judges
    the quote but cannot re-take it. What bounds it is that quote's own age limit and
    the instruction's expiry, both measured at the moment of admission, and the
    instruction is signed seconds before it runs.
    """

    observation: Observation

    def quote(self, request: Any) -> Observation:
        value = self.observation.value
        if value is None or value.sell != request.sell or value.buy.asset != request.buy:
            raise InstructionError("the instruction's quote is not for the order being admitted")
        return self.observation
