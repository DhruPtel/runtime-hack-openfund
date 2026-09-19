"""Unit 4.7: positions derived from the journal, never written. H for the arithmetic.

There is no positions table: a position is what the events add up to. The statement
reconciles before it prints, in the ledger's exact arithmetic.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal, localcontext
from pathlib import Path

import pytest

from fund.core import cash, ledger
from fund.store import db, positions
from fund.store.journal import Journal
from test_journal import EVERY_KIND, GAS, SOLD_ETH
from test_ledger import ETH, OPEN_PAPER, SIX, SNAPSHOT, USDG, mark_of, units


def kept(tmp_path) -> Journal:
    journal = Journal(db.connect(tmp_path / "fund.sqlite"))
    for event in EVERY_KIND:
        journal.append(event)
    return journal


def test_a_position_is_what_the_journals_events_add_up_to(tmp_path):
    paper = positions.book(kept(tmp_path), book="paper", snapshot=SNAPSHOT)
    held = {asset.address: position for asset, position in paper.positions.items()}
    for fill in SIX:
        bought = held[fill.got.asset.address]
        assert bought.amount.raw == fill.got.raw - (  # GME: half of it was sold again
            SOLD_ETH.gave.raw if False else 0) - (
            fill.got.raw // 2 if fill.order_id.endswith("/1") else 0)
        with localcontext(cash.EXACT):
            assert bought.value_usd == units(bought.amount) * mark_of(fill.got.asset)
    assert USDG not in paper.positions  # cash is cash, never a position
    assert paper.cash.amount.asset == USDG


def test_the_two_books_are_kept_apart_and_never_added(tmp_path):
    journal = kept(tmp_path)
    paper = positions.book(journal, book="paper", snapshot=SNAPSHOT)
    real = positions.book(journal, book="real", snapshot=SNAPSHOT)
    assert ETH in real.positions and ETH not in paper.positions
    assert real.expenses_usd == Decimal("0.099454") and paper.expenses_usd == 0
    shown = positions.statement(paper, SNAPSHOT) + positions.statement(real, SNAPSHOT)
    assert "paper book" in shown and "real book" in shown
    assert str(paper.nav_usd + real.nav_usd) not in shown  # no blended NAV


def test_the_statement_reconciles_before_it_prints(tmp_path):
    paper = positions.book(kept(tmp_path), book="paper", snapshot=SNAPSHOT)
    assert positions.reconciles(paper) == 0
    shown = positions.statement(paper, SNAPSHOT)
    assert "= NAV" in shown and "exactly" in shown
    assert f"NAV ${paper.nav_usd.quantize(Decimal('0.01')):,.2f}, exactly" in shown
    doctored = dataclasses.replace(paper, nav_usd=paper.nav_usd + Decimal("0.01"))
    with pytest.raises(positions.BooksDisagree, match="a difference of 0.01"):
        positions.statement(doctored, SNAPSHOT)
    # and a difference far below a cent: the check is on the exact figures
    hair = dataclasses.replace(paper, realised_usd=paper.realised_usd + Decimal("1E-20"))
    with pytest.raises(positions.BooksDisagree, match="difference of -1.0*E-20"):
        positions.statement(hair, SNAPSHOT)


def test_the_costs_of_the_real_book_come_off_its_nav_and_inference_never_does(tmp_path):
    real = positions.book(kept(tmp_path), book="real", snapshot=SNAPSHOT)
    with localcontext(cash.EXACT):
        assert real.nav_usd == (real.opened_usd + real.realised_usd + real.unrealised_usd
                                - real.costs_usd)
        assert real.costs_usd == units(GAS.amount) * mark_of(ETH)
    assert real.expenses_usd not in (real.nav_usd, Decimal(0))


def test_there_is_no_positions_table_to_write(tmp_path):
    conn = db.connect(tmp_path / "fund.sqlite")
    tables = {name for (name,) in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
    assert "positions" not in tables and {"orders", "events"} <= tables
    source = Path(positions.__file__).read_text()
    assert "INSERT" not in source and "UPDATE" not in source
