"""Unit 4.11: the known answer. H: this is the arithmetic the books rest on.

`fixtures/accounting/events.json` is a constructed list of events, and
`fixtures/accounting/answer.md` works out by hand what a ledger that tells economic
truth must say about them — average cost through a partial sale, a contribution that
is not income, gas on a transaction that reverted, an expense recognised once, and
two books that are never added. `expected.json` is that hand answer as data.

These tests hold `core/ledger.py` to it, figure by figure, to the last digit. Nothing
here recomputes an expectation: every number compared comes out of the fixture.
"""

from __future__ import annotations

import json
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from fund.core import cash, ledger

REPO = Path(__file__).resolve().parents[1]
FIXTURE = REPO / "fixtures" / "accounting"
DOCUMENT = json.loads((FIXTURE / "events.json").read_text())
EXPECTED = json.loads((FIXTURE / "expected.json").read_text())["books"]
SNAPSHOT = json.loads((REPO / "fixtures" / "snapshots" / DOCUMENT["snapshot"]
                       / "snapshot.json").read_text())
EVENTS = [ledger.decode(event) for event in DOCUMENT["events"]]
SYMBOL = {entry["asset"]["address"]: entry["asset"]["symbol"]
          for entry in [*SNAPSHOT["assets"], *SNAPSHOT["holdings"]]}


def book(name: str) -> ledger.BookValue:
    return ledger.value(EVENTS, book=name, snapshot=SNAPSHOT)


@pytest.mark.parametrize("name", ["paper", "real"])
def test_every_figure_matches_the_hand_computed_answer(name):
    """Position by position, and line by line, to the last digit."""
    computed, expected = book(name), EXPECTED[name]
    held = {SYMBOL[asset.address]: position for asset, position in computed.positions.items()}
    held[SYMBOL[computed.cash.amount.asset.address]] = computed.cash
    assert set(held) == set(expected["positions"])
    for symbol, position in expected["positions"].items():
        mine = held[symbol]
        units = Decimal(mine.amount.raw).scaleb(-mine.amount.decimals)
        assert units == Decimal(position["units"]), symbol
        assert mine.value_usd == Decimal(position["value_usd"]), symbol
        assert mine.basis_usd == Decimal(position["basis_usd"]), symbol
        assert mine.unrealised_usd == Decimal(position["unrealised_usd"]), symbol
    for line in ("nav_usd", "opened_usd", "realised_usd", "unrealised_usd", "costs_usd",
                 "expenses_usd"):
        assert getattr(computed, line) == Decimal(expected[line]), line


@pytest.mark.parametrize("name", ["paper", "real"])
def test_the_identity_holds_to_the_last_digit(name):
    """opened + realised + unrealised − costs = NAV, in the ledger's own arithmetic,
    where an inexact step raises rather than rounding."""
    computed = book(name)
    with localcontext(cash.EXACT):
        assert computed.nav_usd == (computed.opened_usd + computed.realised_usd
                                    + computed.unrealised_usd - computed.costs_usd)


def test_a_contribution_is_not_income():
    """The 5 USDG transferred in is capital: it is in what was put in, and in no
    realised figure. Taking 2 USDG out again takes only the basis it carries."""
    without = [e for e in EVENTS if not isinstance(e, ledger.Transfer)]
    contributed = ledger.value(EVENTS, book="real", snapshot=SNAPSHOT)
    neither = ledger.value(without, book="real", snapshot=SNAPSHOT)
    with localcontext(cash.EXACT):
        assert contributed.opened_usd - neither.opened_usd == Decimal("4.99975") - Decimal(
            "1.9998944273195657167270790474")
    assert contributed.realised_usd == neither.realised_usd  # neither in nor out is income
    assert contributed.costs_usd == neither.costs_usd        # nor a cost


def test_the_gas_on_a_reverted_transaction_is_a_cost_with_no_fill():
    """Event 9 pays gas and buys nothing: it is in costs, and no order was filled for
    it. The fund's ETH falls by what it paid."""
    reverted = next(e for e in EVENTS if isinstance(e, ledger.Fee)
                    and "reverted" in e.what)
    assert reverted.order_id not in ledger.booked(EVENTS)
    paid = cash.worth(reverted.amount, reverted.mark)
    assert paid == Decimal("0.010548")
    without = [e for e in EVENTS if e is not reverted]
    with_it, less = (ledger.value(events, book="real", snapshot=SNAPSHOT)
                     for events in (EVENTS, without))
    with localcontext(cash.EXACT):
        assert with_it.costs_usd - less.costs_usd == paid
        assert less.nav_usd - with_it.nav_usd == cash.worth(reverted.amount, cash.mark_of(
            SNAPSHOT, reverted.amount.asset.address))


def test_an_expense_is_recognised_once_and_is_in_no_nav():
    """Two inference costs, 0.099454 and 0.260564. They are the expense line, once
    each, and they move no holding: the NAV is the same without them."""
    spent = [e for e in EVENTS if isinstance(e, ledger.Inference)]
    assert [str(e.usd) for e in spent] == ["0.099454", "0.260564"]
    real = book("real")
    assert real.expenses_usd == Decimal("0.360018") == sum(e.usd for e in spent)
    without = ledger.value([e for e in EVENTS if e not in spent], book="real",
                           snapshot=SNAPSHOT)
    assert without.nav_usd == real.nav_usd and without.expenses_usd == 0


def test_the_two_books_are_two_figures_and_the_fund_has_no_third():
    paper, real = book("paper"), book("real")
    assert paper.nav_usd == Decimal("183.64629364")
    assert real.nav_usd == Decimal("4.26567681261301")
    assert set(SYMBOL[a.address] for a in paper.positions) == {"GME"}
    assert set(SYMBOL[a.address] for a in real.positions) == {"ETH"}
    assert ledger.value(EVENTS, book="paper", snapshot=SNAPSHOT).nav_usd == paper.nav_usd
