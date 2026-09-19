"""Unit 4.6: the journal, at minimal scope. H for what it keeps, L for how.

Every value is computed by `core/ledger.py` from `events()`; the journal only keeps
them, in order, and refuses to edit one, delete one, or fill an order twice.
"""

from __future__ import annotations

import sqlite3
from decimal import Decimal

import pytest

from fund.core import ledger
from fund.core.types import Amount, ExecutionMode
from fund.store import db
from fund.store.journal import Journal, JournalError
from test_ledger import ETH, ETH_MARK, OPEN_PAPER, SIX, SNAPSHOT, USDG, sold_half_of_gme, usd_mark

GAS = ledger.Fee("real", Amount(3_000_000_000_000, 18, ETH), usd_mark(ETH, ETH_MARK), "gas",
                 order_id="test/eth")
SPENT = ledger.Inference("risk", Decimal("0.099454"))
SOLD_ETH = ledger.Fill(order_id="test/eth", mode=ExecutionMode.LIVE,
                       gave=Amount(200_000_000_000_000, 18, ETH), got=Amount(525_000, 6, USDG),
                       gave_mark=usd_mark(ETH, ETH_MARK), got_mark=usd_mark(USDG, "0.99992279"),
                       cash_asset=USDG)
EVERY_KIND = [OPEN_PAPER, *SIX, sold_half_of_gme(),
              ledger.Opening("real", Amount(460_000_000_000_000, 18, ETH), usd_mark(ETH, "2600")),
              ledger.Opening("real", Amount(78_742, 6, USDG), usd_mark(USDG, "0.99995")),  # F0.10.1
              SOLD_ETH, GAS, SPENT]


def journal(tmp_path) -> Journal:
    return Journal(db.connect(tmp_path / "fund.sqlite"))


def test_every_kind_of_event_is_kept_exactly_and_read_back_in_order(tmp_path):
    kept = journal(tmp_path)
    places = [kept.append(e) for e in EVERY_KIND]
    assert places == sorted(places)
    assert Journal(db.connect(tmp_path / "fund.sqlite")).events() == EVERY_KIND
    for event in EVERY_KIND:
        assert ledger.decode(ledger.encode(event)) == event


def test_the_ledger_reads_the_same_figures_from_the_journal_as_from_the_events(tmp_path):
    kept = journal(tmp_path)
    for event in EVERY_KIND:
        kept.append(event)
    for book in ledger.BOOKS:
        assert ledger.value(kept.events(), book=book, snapshot=SNAPSHOT) == ledger.value(
            EVERY_KIND, book=book, snapshot=SNAPSHOT)


def test_an_event_is_never_edited_or_deleted(tmp_path):
    kept = journal(tmp_path)
    kept.append(OPEN_PAPER)
    for sql in ("UPDATE events SET body = '{}'", "DELETE FROM events"):
        with pytest.raises(sqlite3.DatabaseError, match="append-only"):
            kept.conn.execute(sql)
    assert kept.events() == [OPEN_PAPER]


def test_an_order_is_booked_once_and_a_second_fill_writes_nothing(tmp_path):
    kept = journal(tmp_path)
    kept.append(OPEN_PAPER)
    kept.append(SIX[0])
    with pytest.raises(JournalError, match="already filled"):
        kept.append(SIX[0])
    with pytest.raises(JournalError):  # another fill for that order, however it is dressed
        kept.append(ledger.Fill(order_id=SIX[0].order_id, mode=ExecutionMode.PAPER,
                                gave=Amount(1, 6, USDG), got=SIX[0].got, gave_mark=SIX[0].gave_mark,
                                got_mark=SIX[0].got_mark, cash_asset=USDG))
    assert kept.events() == [OPEN_PAPER, SIX[0]]
    kept.append(GAS)
    kept.append(GAS)  # fees are not fills: one order may pay several
    assert len(kept.events()) == 4
