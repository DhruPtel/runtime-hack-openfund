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
- `Fee`: what was paid, in what, at what mark.
- `Inference`: a model call's cost, in USD, paid from LLM credits.

**Two books, never added (P9).** A paper fill belongs to the `paper` book and a live
one to the `real` book; an opening and a fee name theirs; inference is real.
`book_of` is the one place that says so, and every reader takes `book=`, with no
default and no way to sum across books.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Union

from . import cash, orders
from .types import USD, Amount, AssetId, ExecutionMode, Order, OrderState, Price, Quote

PAPER, REAL = BOOKS = ("paper", "real")


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


Event = Union[Opening, Fill, Fee, Inference]


def book_of(event: Event) -> str:
    """The book an event belongs to (P9): a fill by its mode, an opening or a fee by
    the book it names, and inference to the real book, whose money paid for it."""
    if isinstance(event, Fill):
        return PAPER if event.mode is ExecutionMode.PAPER else REAL
    if isinstance(event, Inference):
        return REAL
    if isinstance(event, (Opening, Fee)):
        return event.book
    raise LedgerError(f"not a ledger event: {type(event).__name__}")


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
    if not orders.quote_is_for(order, quote):
        raise LedgerError(f"the quote is for another order than {order.order_id}")
    if quote.buy < order.min_buy:
        raise LedgerError(f"the quote buys less than order {order.order_id}'s minimum")
    cash_asset, _ = cash.cash_leg(snapshot)
    return Fill(order_id=order.order_id, mode=ExecutionMode.PAPER, gave=quote.sell,
                got=quote.buy, gave_mark=cash.mark_of(snapshot, quote.sell.asset.address),
                got_mark=cash.mark_of(snapshot, quote.buy.asset.address),
                cash_asset=cash_asset)
