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
- `LiveExecutor` (5.1) takes the same order and quote, sends `/wallet/swap` once with
  the treasurer's key, and answers the same way — except that what it answers with is
  read from the chain (5.3), never from the reply: `confirmed` with the fill the logs
  show and the gas the EntryPoint charged, `failed` for a mined revert, which costs
  gas and buys nothing, and `unknown` for everything not yet settled. Nothing that
  calls an executor knows which it has.

**Two authorities, one chokepoint.** An analyst-driven order is authorized by the
signed decision record (`admit`). The live leg is authorized by a signed instruction
(`admit_instruction`, `treasurer/instruct.py`): the same gates on the same fresh
quote, less the four that ask about a vote, a plan and the paper book's floor, and
plus the instruction's own expiry. `run_order` takes whichever as an argument, so
there is one path from `prepared` to the books and not two.

**`run_order`** is the caller they share: it takes one `prepared` order, admits it or
refuses it by name, writes `submitted` before the act, sends it, and writes the fill,
any gas it paid and the order's new state in one transaction, so a crash can never
leave a fill without its order or an order confirmed without its fill. An order
already finished is not sent again and books nothing; one left `submitted` or
`unknown` is 4.9's to resolve, and `run_order` leaves it alone.

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
import time
from dataclasses import dataclass
from pathlib import Path
from decimal import Decimal
from typing import Any, Collection, Mapping, Protocol, Sequence

from fund.adapters import bankr_exec, bankr_quote
from fund.core import cash, gates, ledger, orders, plan
from fund.core.types import (
    Amount, AssetId, ChainAddress, Execution, ExecutionMode, Instant, Observation, Order,
    OrderState, Quote,
)
from fund.store.db import transaction
from fund.treasurer import reconcile, sign

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


def judge(observation: Observation, sell: Amount, at: Instant,
          thresholds: Mapping[str, Any]) -> plan.QuoteSeen:
    """One quote and its verdict at `at`, by the one definition of quote age, size and
    impact (`adapters/bankr_quote.tradeability`). The chokepoint judges its fresh
    quote with this, and the live leg's command judges the quote it writes into an
    instruction with the same one, so both are held to the same age."""
    verdict = bankr_quote.tradeability(observation, sell, at,
                                       bankr_quote.Limits.from_thresholds(thresholds))
    return plan.QuoteSeen(observation, verdict.verdict, verdict.rule, verdict.age_ms)


def requote(order: Order, venue: Venue, at: Instant,
            thresholds: Mapping[str, Any]) -> plan.QuoteSeen:
    """A fresh quote for exactly this order, judged at `at`."""
    observation = venue.quote(bankr_quote.QuoteRequest(sell=order.sell, buy=order.buy_asset,
                                                       buy_decimals=order.min_buy.decimals))
    return judge(observation, order.sell, at, thresholds)


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


RULE_IN_INSTRUCTION = "in-instruction"
RULE_INSTRUCTION_TERM = "instruction-term"


def admit_instruction(order: Order, instruction_bytes: bytes, envelope: Mapping[str, Any], *,
                      public_key: str | None, mandate: Mapping[str, Any], limits: gates.Limits,
                      fresh: plan.QuoteSeen, at: Instant, events: Sequence[ledger.Event],
                      snapshot_bytes: bytes) -> Admission:
    """The chokepoint for the live leg (5.2): the order one signed instruction
    authorizes, checked again, now, on a fresh quote.

    It is the same chokepoint as `admit` — the same `core/gates.py` comparisons, the
    same fresh quote, the same ledger — over a different authority. What differs, and
    why:
    - `quorum`, `turnover`, `position-weight` and `tradeable` are **not asked**. No
      analyst proposed this and no risk agent voted, there is no plan to turn over,
      and a sale of what the wallet already holds is not a position to open. A gate
      claiming a vote that never happened would be a false record;
    - the `cash-floor` is not asked either: it is the *paper* book's floor
      (`gates.cash_floor` says so), and this order trades the real one. Paper and
      real never add;
    - `live-budget` is asked, against what the real book has already traded, and it
      is the ceiling the operator set on this whole path.
    Everything else an order must pass, it passes."""
    gates.known(limits)
    doc = json.loads(instruction_bytes)
    checks: list[gates.Gate] = []
    signed = sign.authorizes(envelope, instruction_bytes, public_key or "")
    checks.append(gates.Gate(RULE_SIGNATURE, signed.value if public_key else None,
                             signed.reason if public_key else "no key is published"))
    same = hashlib.sha256(snapshot_bytes).hexdigest() == doc["snapshot"]["sha256"]
    checks.append(gates.Gate(RULE_SNAPSHOT, same, "the snapshot the instruction was written on"
                             if same else "not the snapshot the instruction names"))
    mine = _instructed(order, doc, envelope.get("decision_id") or "")
    checks.append(gates.Gate(RULE_IN_INSTRUCTION, mine is not None,
                             "the order the instruction authorizes, as it authorizes it"
                             if mine is not None else f"order {order.order_id} is not the order "
                             "the instruction authorizes, as it authorizes it"))
    live = doc["issued_at_ms"] <= at.epoch_ms <= doc["expires_at_ms"]
    checks.append(gates.Gate(RULE_INSTRUCTION_TERM, live,
                             f"issued {doc['issued_at_ms']}, expires {doc['expires_at_ms']}, "
                             f"now {at.epoch_ms}"))
    if mine is None or not same:
        return Admission(order, tuple(checks), None)

    snapshot = json.loads(snapshot_bytes)
    judged = dict(mine, quote=plan.quote_record(fresh, mine["side"]))  # judged on the fresh quote
    worth = cash.order_worth(judged, snapshot)
    checks += [gates.snapshot_age(snapshot["block"]["time"], at.epoch_ms, limits),
               gates.mandate_term(mandate, at),
               gates.priced(judged, snapshot), gates.mandate_in_force(judged, mandate),
               gates.mandate_legs(judged, mandate), gates.order_size(worth, limits),
               gates.sell_quote(judged)]
    book = ledger.book_for(order.mode)
    holding = ledger.holdings(events, book=book).get(order.sell.asset)
    checks.append(gates.held({"address": order.sell.asset.address, "raw": str(order.sell.raw)},
                             None if holding is None else holding.raw))
    checks.append(gates.live_budget(mandate, ledger.traded_usd(events, book=book), worth))
    return Admission(order, tuple(checks), fresh)


def _instructed(order: Order, doc: Mapping[str, Any], instruction_id: str) -> Mapping | None:
    """The instruction's order this one is, with its id, key and amounts: or None."""
    mine = doc["order"]
    chain = order.sell.asset.chain_id
    sold = mine["sell"]
    same = (order.order_id == orders.order_id(instruction_id, mine["index"])
            and order.idempotency_key == orders.idempotency_key(instruction_id, mine["index"])
            and order.mode is ExecutionMode.LIVE
            and order.sell == Amount.from_units(sold["amount"], sold["decimals"],
                                                AssetId(chain, sold["address"]))
            and order.buy_asset == AssetId(chain, mine["buy"]["address"]))
    return mine if same else None


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
    fee: ledger.Fee | None = None

    def __post_init__(self):
        if self.state not in (OrderState.CONFIRMED, OrderState.FAILED, OrderState.UNKNOWN):
            raise ValueError("a submission ends confirmed, failed or unknown")
        if (self.state is OrderState.CONFIRMED) != (self.fill is not None):
            raise ValueError("a fill, and only a confirmed submission's")
        if self.fee is not None and self.state is OrderState.UNKNOWN:
            raise ValueError("an unknown submission books nothing, its gas included")


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


class LiveExecutor:
    """The live leg (5.1): one swap, sent once, and then read from the chain (5.3).

    The venue's reply is used for one thing only — the transaction hash to read. What
    was given, what was received and whether it happened at all come from the receipt:
    - **no hash, whatever the status:** `unknown`. Nothing is booked and the order
      stays in flight. This is the honest answer even for a 4xx, because nothing in
      the record measures a status that proves no submission, and the cost of being
      wrong is a broadcast nobody reconciled. Resolving it is the operator's and
      4.9's, under the same key, never under a new one (PLAN §4).
    - **a hash:** reconciled to `cadence.confirmation_depth`, polled until the
      settlement deadline. Confirmed books the fill the logs show, and the gas the
      EntryPoint charged; a reverted operation books that gas with no fill; anything
      still unsettled at the deadline is `unknown`, not failed.
    - **evidence the ledger refuses** — amounts in other assets, or more given than
      the order authorised — is `unknown` too: the money has moved, and this process
      will not guess what it was."""

    mode = ExecutionMode.LIVE

    def __init__(self, secret: str, *, settings: bankr_exec.Settings, rpc: Any,
                 wallet: ChainAddress, chain_id: int, confirmations: int | None,
                 snapshot: Mapping[str, Any], deadline_s: float, poll_s: float,
                 sleep=time.sleep, monotonic=time.monotonic, watch: Any = None,
                 transport: Any = None):
        self._secret = secret
        self.settings, self.rpc, self.wallet, self.chain_id = settings, rpc, wallet, chain_id
        self.confirmations, self.snapshot = confirmations, snapshot
        self.deadline_s, self.poll_s = deadline_s, poll_s
        self._sleep, self._monotonic, self._transport = sleep, monotonic, transport
        self._watch = watch or (lambda *_: None)
        self.sent: dict[str, Outcome] = {}
        self.replies: dict[str, bankr_exec.SwapReply] = {}

    def submit(self, order: Order, quote: Quote) -> Outcome:
        if order.mode is not self.mode:
            raise ValueError(f"order {order.order_id} is {order.mode.value}: the live "
                             "executor sends live orders only")
        if order.idempotency_key in self.sent:  # sent once in this process, as on the venue
            return self.sent[order.idempotency_key]
        request = bankr_exec.SwapRequest(sell=order.sell, buy=order.buy_asset,
                                         idempotency_key=order.idempotency_key,
                                         min_buy=order.min_buy, quote_id=quote.quote_id)
        self._watch("sending", request.body(self.settings))
        reply = bankr_exec.submit(request, self._secret, settings=self.settings,
                                  transport=self._transport)
        self.replies[order.idempotency_key] = reply
        self._watch("replied", {"status": reply.status, "success": reply.success,
                                "hash": reply.tx_hash, "detail": reply.detail})
        outcome = self._read(order, reply)
        self.sent[order.idempotency_key] = outcome
        return outcome

    def _read(self, order: Order, reply: bankr_exec.SwapReply) -> Outcome:
        if not reply.tx_hash:
            return Outcome(OrderState.UNKNOWN, f"HTTP {reply.status}, no transaction to read: "
                           f"{reply.detail}. The order stays in flight under its own key")
        until = self._monotonic() + self.deadline_s
        while True:
            seen = reconcile.read(self.rpc, reply.tx_hash, wallet=self.wallet,
                                  chain_id=self.chain_id, confirmations=self.confirmations,
                                  sell=order.sell.asset, sell_decimals=order.sell.decimals,
                                  buy=order.buy_asset, buy_decimals=order.min_buy.decimals)
            self._watch("reconciling", {"state": seen.state.value, "why": seen.why})
            if seen.state is not OrderState.UNKNOWN or self._monotonic() >= until:
                break
            self._sleep(self.poll_s)
        return booked(order, reply.tx_hash, seen, self.snapshot)


def booked(order: Order, tx_hash: str | None, seen: reconcile.Reconciled,
           snapshot: Mapping[str, Any]) -> Outcome:
    """What one reconciled swap books: the fill its logs evidence, the gas the
    EntryPoint charged, or neither. The executor calls it when it sends, and
    `run/startup.py` calls it when it finds an order in flight at a restart, so an
    order settles the same way whichever found it."""
    where = f"{tx_hash}: {seen.why}"
    try:
        fee = (ledger.gas_fee(order, seen.gas, snapshot, f"gas on {tx_hash}")
               if seen.gas is not None else None)
        if seen.state is OrderState.CONFIRMED:
            fill = ledger.live_fill(order, seen.paid, seen.received, snapshot)
        elif seen.state is OrderState.FAILED:
            return Outcome(OrderState.FAILED, where, execution=seen.execution, fee=fee)
        else:
            return Outcome(OrderState.UNKNOWN, where, execution=seen.execution)
    except (ledger.LedgerError, cash.NoMark) as refused:
        return Outcome(OrderState.UNKNOWN, f"{where}; the ledger will not book it: {refused}",
                       execution=seen.execution)
    short = ("" if seen.received.raw >= order.min_buy.raw else
             f"; under the order's minimum of {order.min_buy.raw}")
    return Outcome(OrderState.CONFIRMED, where + short, fill=fill, execution=seen.execution,
                   fee=fee)


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


#: One order, its fresh quote, and the other orders of the same authority, admitted or
#: refused. Which authority it is — a signed decision or a signed instruction — is the
#: one thing that differs between the paper path and the live leg, so it is the one
#: thing `run_order` takes as an argument.
Admitting = Any  # Callable[[Order, plan.QuoteSeen, Sequence[Order]], Admission]


def by_record(decision: Decision, *, public_key: str | None, mandate: Mapping[str, Any],
              limits: gates.Limits, at: Instant, journal: Any) -> Admitting:
    """Admission for an order a signed decision approved (4.4)."""
    def admitting(order: Order, fresh: plan.QuoteSeen, siblings: Sequence[Order]) -> Admission:
        filled = [_index(o.order_id) for o in siblings if o.state is OrderState.CONFIRMED]
        gone = [_index(o.order_id) for o in siblings
                if o.state in (OrderState.REFUSED, OrderState.FAILED)]
        return admit(order, decision, public_key=public_key, mandate=mandate, limits=limits,
                     fresh=fresh, at=at, events=journal.events(), filled=filled, refused=gone)
    return admitting


def by_instruction(instruction_bytes: bytes, envelope: Mapping[str, Any], snapshot_bytes: bytes,
                   *, public_key: str | None, mandate: Mapping[str, Any], limits: gates.Limits,
                   at: Instant, journal: Any) -> Admitting:
    """Admission for the live leg, authorized by a signed instruction (5.2)."""
    def admitting(order: Order, fresh: plan.QuoteSeen, siblings: Sequence[Order]) -> Admission:
        return admit_instruction(order, instruction_bytes, envelope, public_key=public_key,
                                 mandate=mandate, limits=limits, fresh=fresh, at=at,
                                 events=journal.events(), snapshot_bytes=snapshot_bytes)
    return admitting


def run_order(order_id: str, *, admission: Admitting, thresholds: Mapping[str, Any],
              venue: Venue, executor: Executor, store: Any, journal: Any, at: Instant,
              checkpoint: Any = None) -> Done:
    """One order through the chokepoint and, if it passes, to the venue and the books."""
    order = store.get(order_id)
    if order is None:
        raise ValueError(f"no order {order_id} is written: nothing is sent unprepared")
    if order.state is not OrderState.PREPARED:
        return Done(order, None, None)  # finished, or in flight and 4.9's to resolve

    mine = [o for o in store.all() if o.order_id.rpartition("/")[0] == order_id.rpartition("/")[0]]
    fresh = requote(order, venue, at, thresholds)
    admitted = admission(order, fresh, mine)
    if not admitted.admitted:
        return Done(store.move(order_id, OrderState.REFUSED, reason=admitted.reason),
                    admitted, None)

    order = store.move(order_id, OrderState.SUBMITTED)  # durable, before the act
    if checkpoint is not None:
        checkpoint("submitted", order)
    outcome = executor.submit(order, fresh.observation.value)
    with transaction(store.conn):  # the fill and the state it belongs to, one write
        if outcome.fill is not None:
            journal.append(outcome.fill)
        if outcome.fee is not None:  # gas, whether it filled or reverted (5.1)
            journal.append(outcome.fee)
        order = store.move(order_id, outcome.state, reason=outcome.reason,
                           execution=outcome.execution)
    return Done(order, admitted, outcome)


def live_executor(held: Any, snapshot: Mapping[str, Any], mandate: Mapping[str, Any],
                  config_dir: Path | None) -> LiveExecutor:
    """The live executor from the treasurer's own credentials and the config: the
    chain's RPC endpoints, which the treasurer role may hold; the wallet the mandate
    names; and the confirmation depth and settlement bound `config/cadence.json`
    states. `BANKR_KEY_EXEC` is read here and passed to nothing but the adapter."""
    from fund import config
    from fund.adapters import chain_4663

    chain = chain_4663.Settings.load()
    cadence = config.load_json("cadence.json", config_dir)
    return LiveExecutor(
        held.secret("BANKR_KEY_EXEC"), settings=bankr_exec.Settings.load(),
        rpc=chain.client(held.secret), chain_id=chain.chain_id,
        wallet=ChainAddress(chain.chain_id, mandate["execution_wallet"]),
        confirmations=cadence["confirmation_depth"], snapshot=snapshot,
        deadline_s=cadence["settlement_deadline_seconds"],
        poll_s=cadence["settlement_poll_seconds"])


# --- the treasurer's own process (4.12) ------------------------------------------------------------

def main(argv: Sequence[str] | None = None) -> int:
    """The treasurer, alone:

        python -m fund.treasurer.execute --db FUND.sqlite --snapshot PATH --at EPOCH_MS
            (--decision DIR | --instruction DIR) --config-dir DIR [--env-file PATH]
            [--venue-fetched-at EPOCH_MS]

    With `--decision`, it reads that decision's approved orders from the database,
    admits or refuses each, fills the paper ones at the fake venue and books them.

    With `--instruction`, it runs the live leg (5.2): the one order that instruction
    authorizes, admitted by `admit_instruction` against the quote the instruction
    carries, sent once by `LiveExecutor`, and booked from the chain. **This is the
    only mode in which this repository spends.** It is the same process, the same
    chokepoint and the same one write.

    Either way it prints what it did as JSON, with the environment it was given and
    the names — never the values — of the credentials it loaded itself."""
    import argparse

    from fund import config
    from fund.adapters import fake_venue
    from fund.credentials import Role
    from fund.store import db
    from fund.store.journal import Journal
    from fund.store.orders import OrderStore
    from fund.treasurer import instruct
    from fund.treasurer import keys as published
    from fund.treasurer import mandate as mandates

    inherited = sorted(os.environ)  # what the caller handed us, before we load anything
    parser = argparse.ArgumentParser(prog="fund.treasurer.execute")
    parser.add_argument("--db", required=True, type=Path)
    authority = parser.add_mutually_exclusive_group(required=True)
    authority.add_argument("--decision", type=Path,
                           help="the decision's directory: record.json and envelope.json")
    authority.add_argument("--instruction", type=Path,
                           help="the live leg's: instruction.json and envelope.json (5.2)")
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
    snapshot = json.loads(snapshot_bytes)
    conn = db.connect(args.db)
    store, journal = OrderStore(conn), Journal(conn)
    mandate = mandates.load(args.config_dir)
    thresholds = config.load_json("thresholds.json", args.config_dir)
    limits = gates.Limits.from_config(thresholds, mandate,
                                      config.load_json("models.json", args.config_dir))
    public_key = published.published_key(args.config_dir)

    if args.instruction is not None:  # the live leg: the only mode that spends
        instruction_bytes, envelope = instruct.read(args.instruction)
        admission = by_instruction(instruction_bytes, envelope, snapshot_bytes,
                                   public_key=public_key, mandate=mandate, limits=limits,
                                   at=at, journal=journal)
        venue = instruct.Carried(instruct.carried_quote(json.loads(instruction_bytes)))
        executor = live_executor(held, snapshot, mandate, args.config_dir)
        authorized = [orders.order_id(envelope["decision_id"],
                                      json.loads(instruction_bytes)["order"]["index"])]
    else:
        decision = Decision((args.decision / "record.json").read_bytes(),
                            json.loads((args.decision / "envelope.json").read_text()),
                            snapshot_bytes)
        admission = by_record(decision, public_key=public_key, mandate=mandate, limits=limits,
                              at=at, journal=journal)
        venue = fake_venue.FakeVenue(snapshot, lambda: fetched)
        executor = PaperExecutor(snapshot)
        decision_id = decision.envelope["decision_id"]
        authorized = [o.order_id for o in store.all()
                      if o.order_id.rpartition("/")[0] == decision_id]

    ran = []
    for order_id in authorized:
        done = run_order(order_id, admission=admission, thresholds=thresholds, venue=venue,
                         executor=executor, store=store, journal=journal, at=at)
        ran.append({"order_id": done.order.order_id, "state": done.order.state.value,
                    "reason": done.order.state_reason, "booked": done.booked,
                    "fee_booked": done.outcome is not None and done.outcome.fee is not None,
                    "tx_hash": None if done.order.execution is None else
                    done.order.execution.transaction.tx_hash})
    print(json.dumps({"orders": ran, "environment_given": inherited,
                      "credentials_held": sorted(held.credentials)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
