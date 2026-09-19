"""The ledger's values, one definition each (unit 4.0: P3 to P10, `planning/PHASE-4.md`).

Nothing here writes. The ledger's store is 4.6's (`store/journal.py`), and it keeps
the events this module defines, in order, never edited. Every figure a Phase 4 unit
needs from them is computed here, from the events alone, and nowhere else: the
design lesson of the 3.8 sweep, where three components counted cash three ways
(LESSONS 2026-09-19).

**The events.**
- `Opening`: a balance a book starts with, and the mark it came in at.
- `Fill` (P3): what an order gave and got, the marks at fill time, and which leg
  is cash. `paper_fill` builds one from a quote; a live one comes from receipts
  at 5.3.
- `Transfer`: value into or out of a book that is not a trade — a contribution or a
  withdrawal. Capital, never income and never a cost (4.11).
- `Fee`: what was paid, in what, at what mark.
- `Inference`: a model call's cost, in USD, paid from LLM credits.

**Two books, never added (P9).** A paper fill belongs to the `paper` book and a live
one to the `real` book; an opening and a fee name theirs; inference is real.
`book_of` is the one place that says so, and every reader takes `book=`, with no
default and no way to sum across books.

**One fold (P8).** `_walk` applies a book's events in the ledger's order, and every
figure comes from it: holdings (P4), cash (P5), and `value`, which is the whole book
at once — each position with its basis (P6) and its unrealised value, and the book's
opened, realised, costs and expenses (P7, P8). P6 and P7 had a reader each until the
audit: nothing called them, because every consumer reads the book (CLAUDE.md, no
function without a caller). What each event does:

    event      holdings            basis                          value
    opening    + the amount        + its worth at its mark        what opened the book
    fill       − gave, + got       gave: − its average cost;      realised += value − that basis
                                   got: + the fill's value
    transfer   + or − the amount   in: + its worth; out: − its    capital in or out: it moves
                                   average cost                   `opened`, never realised
    fee        − the amount paid   − the average cost of what     cost += its worth at its mark;
                                   paid it; never any position's  realised += that − that basis
    inference  none                none                           expense += its USD

Every asset is held at average cost, USDG and ETH included, so a move in USDG's own
mark is value like any other. `opened` is what was put in less what was taken out: an
opening balance and a transfer in add to it, a transfer out takes the basis it
carries away with it, and neither is ever income. Then, per book and exactly:

    NAV = opened + realised + unrealised − costs

Inference is paid from LLM credits, which neither book holds: an expense beside the
NAV, never in it. The basis a disposal removes is rounded half-even to 10⁻³⁰ USD;
every other figure is exact, and an inexact step raises (`cash.EXACT`). A book that
would hold less than nothing, or an order filled twice, refuses at that event.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import (
    ROUND_HALF_EVEN, Context, Decimal, DivisionByZero, InvalidOperation, Overflow, localcontext,
)
from typing import Any, Iterable, Mapping, Union

import json

from . import cash, orders, plan
from .types import (
    USD, Amount, AssetId, ExecutionMode, Order, OrderState, Price, Quote, from_canonical,
    to_canonical,
)

PAPER, REAL = BOOKS = ("paper", "real")
IN, OUT = DIRECTIONS = ("in", "out")

#: The basis a partial disposal removes is its share of the basis, rounded half-even
#: to this, the one rounding in the ledger. Every other figure is exact.
QUANTUM = Decimal("1E-30")
_SHARE = Context(prec=100, rounding=ROUND_HALF_EVEN,
                 traps=[InvalidOperation, DivisionByZero, Overflow])


class LedgerError(ValueError):
    """Events that cannot be what happened: the ledger refuses them rather than
    report a figure built on them."""


def _book(book: str) -> str:
    if book not in BOOKS:
        raise ValueError(f"a book is {' or '.join(BOOKS)}, not {book!r}")
    return book


def _given(name: str, amount: Amount) -> None:
    if not isinstance(amount, Amount):
        raise TypeError(f"{name} is an Amount")
    if amount.raw <= 0:
        raise LedgerError(f"{name} is a positive amount, not {amount.raw}")


def _marks(name: str, mark: Price, amount: Amount) -> None:
    if not isinstance(mark, Price):
        raise TypeError(f"{name} is a Price")
    if mark.base != amount.asset or mark.quote_unit != USD:
        raise LedgerError(f"{name} is not a USD mark of the asset it values")
    if mark.raw <= 0:
        raise LedgerError(f"{name} is a positive price")


# --- the events ----------------------------------------------------------------------------------

@dataclass(frozen=True)
class Opening:
    """A balance a book starts with, or is given later: its amount, and the mark it
    came in at, which is its basis."""

    book: str
    amount: Amount
    mark: Price

    def __post_init__(self):
        _book(self.book)
        _given("an opening", self.amount)
        _marks("an opening's mark", self.mark, self.amount)


@dataclass(frozen=True)
class Fill:
    """What an order gave and got, and the marks it was valued at when it filled (P3).

    Its value is its cash leg at that leg's recorded mark: what a buy paid, and what
    a sell received. So it is never valued again later at another price."""

    order_id: str
    mode: ExecutionMode
    gave: Amount
    got: Amount
    gave_mark: Price
    got_mark: Price
    cash_asset: AssetId

    def __post_init__(self):
        if not isinstance(self.order_id, str) or not self.order_id:
            raise ValueError("a fill names its order")
        if not isinstance(self.mode, ExecutionMode):
            raise TypeError("a fill's mode is paper or live")
        _given("what a fill gave", self.gave)
        _given("what a fill got", self.got)
        if self.gave.asset == self.got.asset:
            raise LedgerError("a fill gives one asset for another")
        _marks("the given leg's mark", self.gave_mark, self.gave)
        _marks("the got leg's mark", self.got_mark, self.got)
        if self.cash_asset not in (self.gave.asset, self.got.asset):
            raise LedgerError("every trade has a cash leg, and it prices the fill")

    @property
    def value_usd(self) -> Decimal:
        """The cash leg at its recorded mark."""
        if self.cash_asset == self.gave.asset:
            return cash.worth(self.gave, self.gave_mark)
        return cash.worth(self.got, self.got_mark)


@dataclass(frozen=True)
class Transfer:
    """Value into or out of a book that is not a trade: a contribution, or a
    withdrawal. It is capital, so it moves what the book was given and never what it
    earned: a contribution is not income, and a withdrawal is not a loss (4.11)."""

    book: str
    direction: str  # "in" or "out"
    amount: Amount
    mark: Price
    what: str

    def __post_init__(self):
        _book(self.book)
        if self.direction not in DIRECTIONS:
            raise LedgerError(f"a transfer goes {' or '.join(DIRECTIONS)}, not {self.direction!r}")
        _given("a transfer", self.amount)
        _marks("a transfer's mark", self.mark, self.amount)
        if not isinstance(self.what, str) or not self.what:
            raise ValueError("a transfer says what it was")


@dataclass(frozen=True)
class Fee:
    """A fee paid from a book: the amount, in the asset that paid it, and the mark it
    was paid at. Never part of any position's basis (P8)."""

    book: str
    amount: Amount
    mark: Price
    what: str
    order_id: str | None = None

    def __post_init__(self):
        _book(self.book)
        _given("a fee", self.amount)
        _marks("a fee's mark", self.mark, self.amount)
        if not isinstance(self.what, str) or not self.what:
            raise ValueError("a fee says what it paid for")


@dataclass(frozen=True)
class Inference:
    """A model call's cost, in USD. It is paid from LLM credits, which neither book
    holds, so it is an expense and never a holding (P8)."""

    seat: str
    usd: Decimal

    def __post_init__(self):
        if not isinstance(self.seat, str) or not self.seat:
            raise ValueError("an inference cost names its seat")
        if not isinstance(self.usd, Decimal) or not self.usd.is_finite() or self.usd.is_signed():
            raise LedgerError("an inference cost is a non-negative Decimal of USD")


Event = Union[Opening, Fill, Transfer, Fee, Inference]


def book_for(mode: ExecutionMode) -> str:
    """The book an order of this mode trades in (P9): paper, or real for live."""
    return PAPER if mode is ExecutionMode.PAPER else REAL


def book_of(event: Event) -> str:
    """The book an event belongs to (P9): a fill by its mode, an opening or a fee by
    the book it names, and inference to the real book, whose money paid for it."""
    if isinstance(event, Fill):
        return book_for(event.mode)
    if isinstance(event, Inference):
        return REAL
    if isinstance(event, (Opening, Transfer, Fee)):
        return event.book
    raise LedgerError(f"not a ledger event: {type(event).__name__}")


# --- how the ledger's store keeps an event (4.6) -------------------------------------------------

def _plain(value: Any) -> Any:
    return json.loads(to_canonical(value))


def _typed(value: Any) -> Any:
    return from_canonical(json.dumps(value).encode())


def encode(event: Event) -> dict[str, Any]:
    """An event as a plain document, for `store/journal.py` to keep. Its amounts and
    marks keep their raw units and decimals exactly."""
    if isinstance(event, Opening):
        return {"kind": "opening", "book": event.book, "amount": _plain(event.amount),
                "mark": _plain(event.mark)}
    if isinstance(event, Fill):
        return {"kind": "fill", "order_id": event.order_id, "mode": event.mode.value,
                "gave": _plain(event.gave), "got": _plain(event.got),
                "gave_mark": _plain(event.gave_mark), "got_mark": _plain(event.got_mark),
                "cash_asset": _plain(event.cash_asset)}
    if isinstance(event, Transfer):
        return {"kind": "transfer", "book": event.book, "direction": event.direction,
                "amount": _plain(event.amount), "mark": _plain(event.mark), "what": event.what}
    if isinstance(event, Fee):
        return {"kind": "fee", "book": event.book, "amount": _plain(event.amount),
                "mark": _plain(event.mark), "what": event.what, "order_id": event.order_id}
    if isinstance(event, Inference):
        return {"kind": "inference", "seat": event.seat, "usd": format(event.usd, "f")}
    raise LedgerError(f"not a ledger event: {type(event).__name__}")


def decode(document: Mapping[str, Any]) -> Event:
    """The event `encode` kept, exactly."""
    kind = document.get("kind")
    if kind == "opening":
        return Opening(document["book"], _typed(document["amount"]), _typed(document["mark"]))
    if kind == "fill":
        return Fill(order_id=document["order_id"], mode=ExecutionMode(document["mode"]),
                    gave=_typed(document["gave"]), got=_typed(document["got"]),
                    gave_mark=_typed(document["gave_mark"]), got_mark=_typed(document["got_mark"]),
                    cash_asset=_typed(document["cash_asset"]))
    if kind == "transfer":
        return Transfer(document["book"], document["direction"], _typed(document["amount"]),
                        _typed(document["mark"]), document["what"])
    if kind == "fee":
        return Fee(document["book"], _typed(document["amount"]), _typed(document["mark"]),
                    document["what"], document.get("order_id"))
    if kind == "inference":
        return Inference(document["seat"], Decimal(document["usd"]))
    raise LedgerError(f"not a ledger event: {kind!r}")


# --- P3: a paper fill ----------------------------------------------------------------------------

def paper_fill(order: Order, quote: Quote, snapshot: Mapping[str, Any]) -> Fill:
    """A paper order filled at its fresh quote: the quote's `sell` and `buy` amounts
    exactly, valued at the snapshot's marks. "A paper fill is the quote." Refused
    for a live order, an order not yet submitted, a quote for another order, and a
    quote that buys less than the order's minimum."""
    if order.mode is not ExecutionMode.PAPER:
        raise LedgerError(f"order {order.order_id} is live: a live fill comes from its "
                          "receipt (5.3), never from a quote")
    if order.state is not OrderState.SUBMITTED:
        raise LedgerError(f"order {order.order_id} is {order.state.value}: only a submitted "
                          "order fills, so its state is written before the fill")
    if quote.sell != order.sell or quote.buy.asset != order.buy_asset:
        raise LedgerError(f"the quote is for another order than {order.order_id}")
    if quote.buy < order.min_buy:
        raise LedgerError(f"the quote buys less than order {order.order_id}'s minimum")
    cash_asset, _ = cash.cash_leg(snapshot)
    return Fill(order_id=order.order_id, mode=ExecutionMode.PAPER, gave=quote.sell,
                got=quote.buy, gave_mark=cash.mark_of(snapshot, quote.sell.asset.address),
                got_mark=cash.mark_of(snapshot, quote.buy.asset.address),
                cash_asset=cash_asset)


# --- P8: the one fold ----------------------------------------------------------------------------

@dataclass(frozen=True)
class _Walked:
    held: Mapping[AssetId, tuple[Amount, Decimal]]  # each asset held: its amount and basis
    opened: Decimal
    realised: Decimal
    costs: Decimal
    expenses: Decimal


def _walk(events: Iterable[Event], book: str) -> _Walked:
    """One book's events applied in order, as the table above says."""
    book = _book(book)
    held: dict[AssetId, tuple[Amount, Decimal]] = {}
    filled: set[str] = set()
    opened = realised = costs = expenses = Decimal(0)

    def acquire(amount: Amount, value: Decimal) -> None:
        had, basis = held.get(amount.asset, (Amount(0, amount.decimals, amount.asset), Decimal(0)))
        if had.decimals != amount.decimals:
            raise LedgerError(f"{amount.asset.address} is held with two decimal counts")
        held[amount.asset] = (Amount(had.raw + amount.raw, had.decimals, had.asset), basis + value)

    def dispose(amount: Amount, at: int) -> Decimal:
        """Give up `amount`, and return the basis it takes with it: all of it for all
        the units, otherwise its share at average cost."""
        had, basis = held.get(amount.asset, (Amount(0, amount.decimals, amount.asset), Decimal(0)))
        if had.decimals != amount.decimals:
            raise LedgerError(f"{amount.asset.address} is held with two decimal counts")
        if amount.raw > had.raw:
            raise LedgerError(f"event {at} gives {amount.raw} of {amount.asset.address}, and the "
                              f"{book} book holds {had.raw}")
        if amount.raw == had.raw:
            del held[amount.asset]
            return basis
        with localcontext(_SHARE):
            removed = (basis * amount.raw / had.raw).quantize(QUANTUM)
        held[amount.asset] = (Amount(had.raw - amount.raw, had.decimals, had.asset), basis - removed)
        return removed

    with localcontext(cash.EXACT):
        for at, event in enumerate(events):
            if book_of(event) != book:
                continue
            if isinstance(event, Opening):
                value = cash.worth(event.amount, event.mark)
                acquire(event.amount, value)
                opened += value
            elif isinstance(event, Fill):
                if event.order_id in filled:
                    raise LedgerError(f"event {at} fills order {event.order_id} a second time")
                filled.add(event.order_id)
                value = event.value_usd
                realised += value - dispose(event.gave, at)
                acquire(event.got, value)
            elif isinstance(event, Transfer):
                if event.direction == IN:
                    value = cash.worth(event.amount, event.mark)
                    acquire(event.amount, value)
                    opened += value
                else:  # what leaves takes the basis it carries: capital out, not a loss
                    opened -= dispose(event.amount, at)
            elif isinstance(event, Fee):
                paid = cash.worth(event.amount, event.mark)
                realised += paid - dispose(event.amount, at)
                costs += paid
            else:
                expenses += event.usd
    return _Walked(held, opened, realised, costs, expenses)


# --- P4, P5: what the fold says; the rest is `value`, below --------------------------------------

def holdings(events: Iterable[Event], *, book: str) -> dict[AssetId, Amount]:
    """P4: what the book holds of each asset, in raw units. The only way a quantity
    held is known. An asset it no longer holds is absent, never zero."""
    return {asset: amount for asset, (amount, _) in _walk(events, book).held.items()}


@dataclass(frozen=True)
class Position:
    """One holding at the snapshot's mark, with what it cost."""

    amount: Amount
    value_usd: Decimal
    basis_usd: Decimal

    @property
    def unrealised_usd(self) -> Decimal:
        with localcontext(cash.EXACT):
            return self.value_usd - self.basis_usd


def _position(amount: Amount, cost: Decimal, snapshot: Mapping[str, Any]) -> Position:
    """The one way the ledger values a holding: through `cash.worth`, at the
    snapshot's mark. A holding with no usable mark refuses (`cash.NoMark`)."""
    return Position(amount, cash.worth(amount, cash.mark_of(snapshot, amount.asset.address)), cost)


def booked(events: Iterable[Event]) -> dict[str, Fill]:
    """Every order the ledger holds a fill for, by order id. A restart reads it to
    learn whether an order it left in flight was booked (4.9), which is the only
    thing that can tell it apart from one that never filled."""
    return {event.order_id: event for event in events if isinstance(event, Fill)}


def cash_held(events: Iterable[Event], *, book: str,
              snapshot: Mapping[str, Any]) -> tuple[Amount, Decimal]:
    """P5: the book's cash, the cash leg it holds (USDG), and what that is worth at
    the cash leg's own mark in the snapshot: never assumed to be a dollar."""
    asset, decimals = cash.cash_leg(snapshot)
    held = _walk(events, book).held.get(asset, (Amount(0, decimals, asset), Decimal(0)))
    return held[0], _position(*held, snapshot).value_usd


# --- P10: a book's NAV, and the planner's view of the paper book ---------------------------------

@dataclass(frozen=True)
class BookValue:
    """One book at the snapshot's marks: its cash, every other holding as a position
    (ETH included), its NAV, and the lines that explain it."""

    book_name: str  # not `book`: only an event has one, and only this module reads it (P9)
    cash: Position
    positions: Mapping[AssetId, Position]
    nav_usd: Decimal
    opened_usd: Decimal
    realised_usd: Decimal
    costs_usd: Decimal
    expenses_usd: Decimal

    @property
    def unrealised_usd(self) -> Decimal:
        with localcontext(cash.EXACT):
            return self.cash.unrealised_usd + sum(
                (p.unrealised_usd for p in self.positions.values()), Decimal(0))


def value(events: Iterable[Event], *, book: str, snapshot: Mapping[str, Any]) -> BookValue:
    """P10: the book at the snapshot's marks. The cash leg (`cash.cash_leg`) is its
    cash, and every other holding a position. Its NAV is `cash.nav`, the sum the
    planner's book uses too. Refuses if any holding has no usable mark."""
    walked = _walk(events, book)
    asset, decimals = cash.cash_leg(snapshot)
    held = dict(walked.held)
    money = _position(*held.pop(asset, (Amount(0, decimals, asset), Decimal(0))), snapshot)
    positions = {a: _position(amount, cost, snapshot) for a, (amount, cost) in held.items()}
    return BookValue(book_name=book, cash=money, positions=positions,
                     nav_usd=cash.nav(money.value_usd, [p.value_usd for p in positions.values()]),
                     opened_usd=walked.opened, realised_usd=walked.realised,
                     costs_usd=walked.costs, expenses_usd=walked.expenses)


def planner_book(events: Iterable[Event], snapshot: Mapping[str, Any]) -> plan.Book:
    """P10: the paper book as the planner takes it: its stocks, and its cash as a USD
    figure at the cash leg's own mark. What 4.8's next cycle plans from. `plan.book`
    refuses any holding outside the snapshot's assets, so ETH never reaches it."""
    events = list(events)
    money, usd = cash_held(events, book=PAPER, snapshot=snapshot)
    stocks = {asset.address: amount for asset, amount in holdings(events, book=PAPER).items()
              if asset != money.asset}
    return plan.book(stocks, usd, snapshot)
