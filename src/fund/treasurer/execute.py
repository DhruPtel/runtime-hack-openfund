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

**`run_order`** is the caller both share: it takes one `prepared` order, admits it or
refuses it by name, writes `submitted` before the act, sends it, and writes the fill
and the order's new state in one transaction, so a crash can never leave a fill
without its order or an order confirmed without its fill. An order already finished
is not sent again and books nothing; one left `submitted` or `unknown` is 4.9's to
resolve, and `run_order` leaves it alone.

**The treasurer is its own process** (4.12). `python -m fund.treasurer.execute` reads
the decision's approved orders from SQLite and runs them. It is started from an empty
environment, so nothing is handed to it, and it loads its own credentials itself —
`SIGNING_KEY` and `BANKR_KEY_EXEC`, which only the treasurer role may hold, from the
treasurer's own file where the operator has split them (`config.env_file_for`). It
reports the names it was given and the names it holds, and never a value. So spend
authority lives in one process, and the cycle that starts it has none.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path
from decimal import Decimal
from typing import Any, Collection, Mapping, Protocol, Sequence

from fund.adapters import bankr_quote
from fund.core import cash, gates, ledger, orders, plan
from fund.core.types import (
    Amount, AssetId, Execution, ExecutionMode, Instant, Observation, Order, OrderState, Quote,
)
from fund.store.db import transaction
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


# --- one order, from prepared to its end ----------------------------------------------------------

@dataclass(frozen=True)
class Done:
    """What became of one order: it was admitted or refused, and if admitted, what the
    submission came to."""

    order: Order
    admission: Admission | None
    outcome: Outcome | None

    @property
    def booked(self) -> bool:
        return self.outcome is not None and self.outcome.fill is not None


def _index(order_id: str) -> int:
    return int(order_id.rpartition("/")[2])


def run_order(order_id: str, *, decision: Decision, public_key: str | None,
              mandate: Mapping[str, Any], limits: gates.Limits, thresholds: Mapping[str, Any],
              venue: Venue, executor: Executor, store: Any, journal: Any, at: Instant,
              checkpoint: Any = None) -> Done:
    """One order through the chokepoint and, if it passes, to the venue and the books."""
    order = store.get(order_id)
    if order is None:
        raise ValueError(f"no order {order_id} is written: nothing is sent unprepared")
    if order.state is not OrderState.PREPARED:
        return Done(order, None, None)  # finished, or in flight and 4.9's to resolve

    mine = [o for o in store.all() if o.order_id.rpartition("/")[0] == order_id.rpartition("/")[0]]
    filled = [_index(o.order_id) for o in mine if o.state is OrderState.CONFIRMED]
    gone = [_index(o.order_id) for o in mine
            if o.state in (OrderState.REFUSED, OrderState.FAILED)]
    fresh = requote(order, venue, at, thresholds)
    admission = admit(order, decision, public_key=public_key, mandate=mandate, limits=limits,
                      fresh=fresh, at=at, events=journal.events(), filled=filled, refused=gone)
    if not admission.admitted:
        return Done(store.move(order_id, OrderState.REFUSED, reason=admission.reason),
                    admission, None)

    order = store.move(order_id, OrderState.SUBMITTED)  # durable, before the act
    if checkpoint is not None:
        checkpoint("submitted", order)
    outcome = executor.submit(order, fresh.observation.value)
    with transaction(store.conn):  # the fill and the state it belongs to, one write
        if outcome.fill is not None:
            journal.append(outcome.fill)
        order = store.move(order_id, outcome.state, reason=outcome.reason,
                           execution=outcome.execution)
    return Done(order, admission, outcome)


# --- the treasurer's own process (4.12) ------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    """The treasurer, alone:

        python -m fund.treasurer.execute --db FUND.sqlite --decision DIR --snapshot PATH
            --at EPOCH_MS --config-dir DIR [--env-file PATH] [--venue-fetched-at EPOCH_MS]

    It reads the decision's approved orders from the database, admits or refuses each,
    fills the paper ones and books them, and prints what it did as JSON. The live
    executor is 5.1's; until then every order is a stock leg, which is paper."""
    import argparse

    from fund import config
    from fund.adapters import fake_venue
    from fund.credentials import Role
    from fund.store import db
    from fund.store.journal import Journal
    from fund.store.orders import OrderStore
    from fund.treasurer import keys as published
    from fund.treasurer import mandate as mandates

    inherited = sorted(os.environ)  # what the caller handed us, before we load anything
    parser = argparse.ArgumentParser(prog="fund.treasurer.execute")
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--decision", required=True, type=Path,
                        help="the decision's directory: record.json and envelope.json")
    parser.add_argument("--snapshot", required=True, type=Path)
    parser.add_argument("--at", required=True, type=int, help="the cycle's clock, epoch ms")
    parser.add_argument("--config-dir", type=Path, default=None)
    parser.add_argument("--env-file", type=Path, default=None, help="the treasurer's own")
    parser.add_argument("--venue-fetched-at", type=int, default=None,
                        help="when the fake venue answers; the default is 5s before --at")
    args = parser.parse_args(argv)

    held = config.load(Role.TREASURER, require=False, env_file=args.env_file)
    at = Instant(args.at)
    fetched = Instant(args.venue_fetched_at if args.venue_fetched_at else at.epoch_ms - 5_000)
    snapshot_bytes = args.snapshot.read_bytes()
    decision = Decision((args.decision / "record.json").read_bytes(),
                        json.loads((args.decision / "envelope.json").read_text()), snapshot_bytes)
    snapshot = decision.snapshot
    conn = db.connect(args.db)
    store, journal = OrderStore(conn), Journal(conn)
    mandate = mandates.load(args.config_dir)
    limits = gates.Limits.from_config(config.load_json("thresholds.json", args.config_dir),
                                      mandate, config.load_json("models.json", args.config_dir))
    venue = fake_venue.FakeVenue(snapshot, lambda: fetched)
    executor = PaperExecutor(snapshot)
    decision_id = decision.envelope["decision_id"]

    ran = []
    for order in store.all():
        if order.order_id.rpartition("/")[0] != decision_id:
            continue
        done = run_order(order.order_id, decision=decision, public_key=published.published_key(
            args.config_dir), mandate=mandate, limits=limits,
            thresholds=config.load_json("thresholds.json", args.config_dir), venue=venue,
            executor=executor, store=store, journal=journal, at=at)
        ran.append({"order_id": done.order.order_id, "state": done.order.state.value,
                    "reason": done.order.state_reason, "booked": done.booked})
    print(json.dumps({"orders": ran, "environment_given": inherited,
                      "credentials_held": sorted(held.credentials)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
