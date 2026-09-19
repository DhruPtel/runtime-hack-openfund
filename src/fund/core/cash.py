"""What an order is worth, and what cash a set of orders leaves. One definition.

The 3.8 sweep found three money bugs with one cause. The aggregator, the planner
and the gates each counted cash their own way (LESSONS 2026-09-19, the design
lesson):
- the planner wrote plans its own floor gate refused (R2);
- a vetoed sell left the buys it funded approved (R1);
- a full exit sold more than its $25 label (R3).

This module is the one place that knows what an order is worth and what cash
orders leave. The planner calls it to size and fund a plan, and the gates call
it to judge one. The aggregator works in weights, and no longer counts cash at
all.

- **`worth`** is an amount at its mark, through `valuation.value()`, the one
  place a quantity becomes USD. An order is worth what it sells:
  - USDG at USDG's own mark, for a buy;
  - the stock at its Chainlink mark, for a sell.
- **`units`** is the inverse, rounded down: the most of an asset a sum is
  worth. A sized order never names more than its dollars.
- **`order_worth`** reads an order's sold amount and values it at the
  snapshot's mark. The per-trade limit and the cash floor are judged on this,
  never on a label the planner wrote.
- **`cash_after`** is the book's paper cash, less what each buy sells, plus
  what each sell sells, for the orders given. The plan's funding and the floor
  on the approved orders both use it. It is a projection: partway through a
  decision, what has filled counts at what it booked instead (`gates.settle`,
  4.0 P11).
- **`cash_leg`** says which asset is cash: USDG. Every other holding is a
  position, the gas asset ETH included (4.0 P10).
- **`nav`** is a book's net asset value: its cash plus each position's worth.
  The planner's book and the ledger's both come from it (4.0 P10).

Money here is exact: `worth` and `nav` never round, and an inexact step raises
(`EXACT`). A limit is never compared here. Limits are `gates.py`'s, which calls
this module.
"""

from __future__ import annotations

from decimal import (
    ROUND_DOWN, Context, Decimal, DivisionByZero, Inexact, InvalidOperation, Overflow,
    localcontext,
)
from typing import Any, Iterable, Mapping

from . import valuation
from .types import USD, Amount, AssetId, Price


#: Arithmetic that never rounds: an inexact step raises instead. Money is summed in
#: it, so a figure is exact or it is an error, never quietly rounded.
EXACT = Context(prec=100, traps=[Inexact, InvalidOperation, DivisionByZero, Overflow])


class NoMark(ValueError):
    """The snapshot has no usable mark for an amount, so its worth is unknown."""


def worth(amount: Amount, mark: Price) -> Decimal:
    """An amount at its mark, in USD, exact. Built from its digits, never through the
    context, which rounded any worth past 28 significant digits: a stock position
    worth $100 or more, at 18 decimals and an 8-decimal mark (fixed at 4.0). No
    position of the $200 book has reached that."""
    value = valuation.value(amount, mark)
    return Decimal(f"{value.raw}E-{value.decimals}")


def cash_leg(snapshot: Mapping[str, Any]) -> tuple[AssetId, int]:
    """The asset that is cash, and its decimals: the snapshot's one holding of kind
    `cash`, USDG, pinned by config (F0.8.2). Every other holding is a position, the
    gas asset ETH included. This is the one place that asks (4.0 P10)."""
    found = [h["asset"] for h in snapshot["holdings"] if h["asset"]["kind"] == "cash"]
    if len(found) != 1:
        raise ValueError(f"a snapshot holds exactly one cash asset, not {len(found)}")
    return AssetId(snapshot["block"]["chain_id"], found[0]["address"].lower()), found[0]["decimals"]


def nav(cash_usd: Decimal, values_usd: Iterable[Decimal]) -> Decimal:
    """A book's net asset value: its cash plus each position's worth, summed exactly.
    `plan.book` and `ledger.value` both call it, so the planner and the ledger never
    disagree about what a book is worth (4.0 P10)."""
    with localcontext(EXACT):
        return cash_usd + sum(values_usd, Decimal(0))


def units(usd: Decimal, mark: Price, decimals: int) -> int:
    """The raw units `usd` is worth at `mark`, rounded down."""
    price = Decimal(mark.raw).scaleb(-mark.decimals)
    return int((usd / price).scaleb(decimals).to_integral_value(rounding=ROUND_DOWN))


def mark_of(snapshot: Mapping[str, Any], address: str) -> Price:
    """The mark an amount of this asset is valued at: a stock's from its entry,
    the cash leg's or the gas asset's from the snapshot's holdings."""
    address = address.lower()
    chain_id = snapshot["block"]["chain_id"]
    entry = next((e for e in [*snapshot["assets"], *snapshot["holdings"]]
                  if e["asset"]["address"].lower() == address), None)
    if entry is None:
        raise NoMark(f"{address} is not in the snapshot")
    mark = entry.get("mark") or {}
    if (mark.get("verdict") or {}).get("verdict") is not True or not mark.get("price_usd"):
        raise NoMark(f"{entry['asset']['symbol']} has no usable mark in the snapshot: "
                     f"{(mark.get('verdict') or {}).get('reason')}")
    return Price.parse(mark["price_usd"], AssetId(chain_id, address), USD)


def order_worth(order: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Decimal:
    """What an order sells, at the snapshot's mark. Raises NoMark if unknown."""
    sold = order["sell"]
    mark = mark_of(snapshot, sold["address"])
    amount = Amount.from_units(sold["amount"], sold["decimals"], mark.base)
    return worth(amount, mark)


def cash_after(cash_usd: Decimal, orders: Iterable[Mapping[str, Any]],
               snapshot: Mapping[str, Any]) -> Decimal:
    """The paper cash left once these orders run: less each buy, plus each sell,
    each at what it sells."""
    cash = cash_usd
    for order in orders:
        value = order_worth(order, snapshot)
        cash += value if order["side"] == "sell" else -value
    return cash
