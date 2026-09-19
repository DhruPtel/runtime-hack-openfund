"""Positions, derived from the journal and never written (unit 4.7).

There is no positions table. A position is what the journal's events add up to, read
by `core/ledger.py` (4.0: P4 holdings, P6 basis, P7 value, P10 the book), valued only
by `core/valuation.value` through `cash.worth`. So a position cannot disagree with the
events it came from, and nothing can set one.

`statement` writes a book out for a reader, and checks the arithmetic while it does:

    NAV = what opened the book + realised + unrealised − costs

exactly, in the ledger's own arithmetic, before anything is printed. The printed
figures are rounded to the cent; the check is not. Paper and real are separate books
and are never added (SIMPLIFICATION 6.1). Inference costs are an expense beside the
NAV, never in it.
"""

from __future__ import annotations

from decimal import ROUND_HALF_EVEN, Decimal, localcontext
from typing import Any, Mapping

from fund.core import cash, ledger
from fund.store.journal import Journal

CENTS = Decimal("0.01")


class BooksDisagree(ValueError):
    """A book's NAV is not what its own lines add up to. Nothing is shown."""


def read(journal: Journal, *, book: str, snapshot: Mapping[str, Any]) -> ledger.BookValue:
    """One book's positions, from the journal's events alone."""
    return ledger.value(journal.events(), book=book, snapshot=snapshot)


def reconciles(value: ledger.BookValue) -> Decimal:
    """The difference between the book's NAV and its lines: zero, or it raises."""
    with localcontext(cash.EXACT):
        residual = value.nav_usd - (value.opened_usd + value.realised_usd
                                    + value.unrealised_usd - value.costs_usd)
    if residual != 0:
        raise BooksDisagree(f"the {value.book_name} book's NAV is {value.nav_usd}, and its lines "
                            f"make {value.nav_usd - residual}: a difference of {residual}")
    return residual


def _usd(amount: Decimal) -> str:
    """To the cent, for a reader. The arithmetic behind it is exact."""
    return f"${amount.quantize(CENTS, rounding=ROUND_HALF_EVEN):,.2f}"


def _units(amount) -> str:
    return format(Decimal(amount.raw).scaleb(-amount.decimals).normalize(), "f")


def _row(name: str, units: str, *figures: str) -> str:
    return f"  {name:<6}{units:>24}" + "".join(f"{figure:>14}" for figure in figures)


def statement(value: ledger.BookValue, snapshot: Mapping[str, Any]) -> str:
    """The book, one line a position, with its cash and its NAV. It reconciles first."""
    reconciles(value)
    symbols = {a["asset"]["address"]: a["asset"]["symbol"]
               for a in [*snapshot["assets"], *snapshot["holdings"]]}
    block = snapshot["block"]
    lines = [f"the {value.book_name} book at block {block['number']} ({block['time']})",
             _row("asset", "units", "value", "basis", "unrealised")]
    for asset, position in sorted(value.positions.items(),
                                  key=lambda p: symbols.get(p[0].address, p[0].address)):
        lines.append(_row(symbols.get(asset.address, asset.address[:10]), _units(position.amount),
                          _usd(position.value_usd), _usd(position.basis_usd),
                          _usd(position.unrealised_usd)))
    lines += [_row("cash", _units(value.cash.amount), _usd(value.cash.value_usd),
                   _usd(value.cash.basis_usd), _usd(value.cash.unrealised_usd)),
              _row("NAV", "", _usd(value.nav_usd)),
              "",
              f"  opened {_usd(value.opened_usd)} + realised {_usd(value.realised_usd)}"
              f" + unrealised {_usd(value.unrealised_usd)} − costs {_usd(value.costs_usd)}"
              f" = NAV {_usd(value.nav_usd)}, exactly",
              f"  inference {_usd(value.expenses_usd)}, an expense beside the NAV, never in it"]
    return "\n".join(lines)
