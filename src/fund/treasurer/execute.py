"""The one path every order takes to the venue: admission, then execution (4.4, 4.5).

**The chokepoint** (4.4) is `admit`. Nothing is attempted unless it passes, and it
trusts nothing the decision computed: it checks again, now, from the signed record,
the ledger and a fresh quote. An order is admitted only when all of these pass, each a
named gate, and each comparison made by `core/gates.py`, the one module that makes
them:
- `signature`: the record verifies against the published key (S13);
- `snapshot`: the snapshot is the one the record was decided on, by its sha256;
- `in-record`: the order is one the record approved, with its id, key and amounts;
- `mandate-term`: the mandate is in force now (4.1);
- every gate of the decision, again, by today's gate set, on a fresh quote taken now:
  the record's plan with this order's quote replaced, through `gates.evaluate`. That
  includes S11, the snapshot's age when the decision was judged, and S10's legs;
- `held`: the book holds what the order gives (4.0, P4);
- `cash-floor`: the floor holds on what is still approved, the orders already filled
  counted at what they booked (`gates.settle`, 4.0 P11);
- `live-budget`: a live order stays within the live budget, null until Phase 5.

`requote` takes the fresh quote through the venue's own interface,
`quote(QuoteRequest) -> Observation`: the live adapter's, or the fake venue's for a
paper cycle. The quote is judged at `at` by the one definition of quote age and
impact, `adapters/bankr_quote.tradeability`.

**The executor** (4.5) is anything with `submit(order, quote) -> Outcome`. It sends an
admitted, submitted order at its fresh quote, under the order's idempotency key, and
says what came of it: `confirmed` with its fill, `failed` with why, or `unknown` with
why. It never books and never moves a state; the caller does both, in one write.
- `PaperExecutor` fills a stock leg at its quote's amounts exactly, marked paper
  (4.0, P3). A repeat under the same key returns the first outcome, as Bankr's
  `idempotencyKey` does (F0.10.1). A paper submission is never `unknown`.
- The live executor (5.1) takes the same order and quote, sends `/wallet/swap` with
  the key, and answers the same way: `confirmed` with the chain evidence and the fill
  its `Transfer` logs show (5.3), `failed` on `success: false`, `unknown` on a timeout
  or a 409. Nothing that calls an executor knows which it has.
"""

from __future__ import annotations

import copy
import hashlib
import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Collection, Mapping, Protocol, Sequence

from fund.adapters import bankr_quote
from fund.core import cash, gates, ledger, orders, plan
from fund.core.types import (
    Amount, AssetId, Execution, ExecutionMode, Instant, Observation, Order, OrderState, Quote,
)
from fund.treasurer import sign

RULE_SIGNATURE = "signature"
RULE_SNAPSHOT = "snapshot"
RULE_IN_RECORD = "in-record"


class Venue(Protocol):
    """Where a quote comes from: the live adapter, or the fake venue offline."""

    def quote(self, request: bankr_quote.QuoteRequest) -> Observation: ...


@dataclass(frozen=True)
class Decision:
    """A signed decision as the treasurer holds it: the record's exact bytes, its
    envelope, and the snapshot's bytes it was decided on."""

    record_bytes: bytes
    envelope: Mapping[str, Any]
    snapshot_bytes: bytes

    @property
    def record(self) -> Mapping[str, Any]:
        return json.loads(self.record_bytes)

    @property
    def snapshot(self) -> Mapping[str, Any]:
        return json.loads(self.snapshot_bytes)


@dataclass(frozen=True)
class Admission:
    """Every check the chokepoint made on one order, and the fresh quote it made them
    on. Admitted only when every check passed."""

    order: Order
    checks: tuple[gates.Gate, ...]
    fresh: plan.QuoteSeen | None

    @property
    def refusals(self) -> list[gates.Gate]:
        return [g for g in self.checks if not g.passes]

    @property
    def admitted(self) -> bool:
        return not self.refusals

    @property
    def reason(self) -> str:
        return "; ".join(f"{g.rule}: {g.reason}" for g in self.refusals) or "admitted"


def requote(order: Order, venue: Venue, at: Instant,
            thresholds: Mapping[str, Any]) -> plan.QuoteSeen:
    """A fresh quote for exactly this order, judged at `at`."""
    observation = venue.quote(bankr_quote.QuoteRequest(sell=order.sell, buy=order.buy_asset,
                                                       buy_decimals=order.min_buy.decimals))
    verdict = bankr_quote.tradeability(observation, order.sell, at,
                                       bankr_quote.Limits.from_thresholds(thresholds))
    return plan.QuoteSeen(observation, verdict.verdict, verdict.rule, verdict.age_ms)


def _gate(result: Mapping[str, Any]) -> gates.Gate:
    return gates.Gate(result["rule"], result["value"], result["reason"])


def admit(order: Order, decision: Decision, *, public_key: str | None,
          mandate: Mapping[str, Any], limits: gates.Limits, fresh: plan.QuoteSeen,
          at: Instant, events: Sequence[ledger.Event], filled: Collection[int] = (),
          refused: Collection[int] = ()) -> Admission:
    """Every check on one order, now. `events` is the ledger; `filled` and `refused`
    are the plan indices of this decision's orders already filled or refused."""
    record, envelope, snapshot = decision.record, decision.envelope, decision.snapshot
    checks: list[gates.Gate] = []

    signed = sign.authorizes(envelope, decision.record_bytes, public_key or "")
    checks.append(gates.Gate(RULE_SIGNATURE, signed.value if public_key else None,
                             signed.reason if public_key else "no key is published"))
    same = hashlib.sha256(decision.snapshot_bytes).hexdigest() == record["snapshot"]["sha256"]
    checks.append(gates.Gate(RULE_SNAPSHOT, same, "the snapshot the record was decided on"
                             if same else "not the snapshot the record names"))

    planned = _planned(order, record, envelope.get("decision_id") or "")
    checks.append(gates.Gate(RULE_IN_RECORD, planned is not None,
                             "an order the record approved, as it approved it"
                             if planned is not None else f"order {order.order_id} is not an "
                             "order the record approved, as it approved it"))
    if planned is None or not same:
        return Admission(order, tuple(checks), None)
    index = planned["index"]
    approved = {o["index"] for o in record["decision"]["approved"]}
    checks.append(gates.mandate_term(mandate, at))

    regated = copy.deepcopy(record["plan"])
    mine = next(o for o in regated["orders"] if o["index"] == index)
    mine["quote"] = plan.quote_record(fresh, mine["side"])
    result = gates.evaluate(regated, snapshot=snapshot, mandate=mandate, limits=limits,
                            reported=len(record["reports"]))
    verdict = next(o for o in result["orders"] if o["index"] == index)
    checks += [_gate(g) for g in verdict["gates"]] + [_gate(g) for g in result["plan"]]

    book = ledger.book_for(order.mode)
    holding = ledger.holdings(events, book=book).get(order.sell.asset)
    checks.append(gates.held({"address": order.sell.asset.address, "raw": str(order.sell.raw)},
                             None if holding is None else holding.raw))

    booked = ledger.cash_held(events, book=book, snapshot=snapshot)[1]
    still = [i for i in sorted(approved) if i not in set(refused)]
    kept, dropped, floor = gates.settle(record["plan"], still, snapshot=snapshot,
                                        limits=limits, booked_usd=booked,
                                        filled=[i for i in filled if i in still])
    # `settle` drops only buys, last first, and never a sell (S9): refused by the floor
    # means dropped by it.
    checks.append(gates.Gate(gates.RULE_CASH_FLOOR, index not in dropped,
                             floor.reason if index not in dropped else f"dropped: {floor.reason}"))

    if order.mode is ExecutionMode.LIVE:
        checks.append(gates.live_budget(mandate, Decimal(0), cash.order_worth(mine, snapshot)))
    return Admission(order, tuple(checks), fresh)


def _planned(order: Order, record: Mapping[str, Any], decision_id: str) -> Mapping | None:
    """The record's approved order this one is, with its id, key and amounts: or None."""
    index_text = order.order_id.rpartition("/")[2]
    if not index_text.isdigit():
        return None
    index = int(index_text)
    planned = next((o for o in record["plan"]["orders"] if o["index"] == index), None)
    if planned is None or index not in {o["index"] for o in record["decision"]["approved"]}:
        return None
    chain = order.sell.asset.chain_id
    sold = planned["sell"]
    same = (order.order_id == orders.order_id(decision_id, index)
            and order.idempotency_key == orders.idempotency_key(decision_id, index)
            and order.sell == Amount.from_units(sold["amount"], sold["decimals"],
                                                AssetId(chain, sold["address"]))
            and order.buy_asset == AssetId(chain, planned["buy"]["address"]))
    return planned if same else None


# --- the executor (4.5) --------------------------------------------------------------------------

@dataclass(frozen=True)
class Outcome:
    """What came of one submission: the state the order moves to, why, and what it
    booked. Confirmed carries a fill; failed and unknown carry a reason."""

    state: OrderState
    reason: str | None
    fill: ledger.Fill | None = None
    execution: Execution | None = None

    def __post_init__(self):
        if self.state not in (OrderState.CONFIRMED, OrderState.FAILED, OrderState.UNKNOWN):
            raise ValueError("a submission ends confirmed, failed or unknown")
        if (self.state is OrderState.CONFIRMED) != (self.fill is not None):
            raise ValueError("a fill, and only a confirmed submission's")


class Executor(Protocol):
    """Sends a submitted order at its quote, under its idempotency key."""

    mode: ExecutionMode

    def submit(self, order: Order, quote: Quote) -> Outcome: ...


class PaperExecutor:
    """A stock leg filled on paper at its quote's amounts, never sent (PLAN §13)."""

    mode = ExecutionMode.PAPER

    def __init__(self, snapshot: Mapping[str, Any]):
        self.snapshot = snapshot
        self.sent: dict[str, Outcome] = {}

    def submit(self, order: Order, quote: Quote) -> Outcome:
        if order.mode is not self.mode:
            raise ValueError(f"order {order.order_id} is {order.mode.value}: the paper "
                             "executor fills paper orders only")
        if order.idempotency_key in self.sent:  # the key deduplicates, as Bankr's does
            return self.sent[order.idempotency_key]
        try:
            outcome = Outcome(OrderState.CONFIRMED, "filled on paper at its quote",
                              fill=ledger.paper_fill(order, quote, self.snapshot))
        except ledger.LedgerError as refused:
            outcome = Outcome(OrderState.FAILED, str(refused))
        self.sent[order.idempotency_key] = outcome
        return outcome
