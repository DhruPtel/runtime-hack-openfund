"""Units 4.3 to 4.6 together: one order from prepared to booked, or refused. H.

The order is written prepared before anything is attempted, submitted before it is
sent, and its fill and its new state are written in one transaction.
"""

from __future__ import annotations

import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from decimal import localcontext

from fund.core import cash, ledger, orders as moves
from fund.core.types import OrderState
from fund.adapters.fake_venue import FakeVenue
from fund.store import db
from fund.store.journal import Journal
from fund.store.orders import OrderStore
from fund.treasurer import execute
from test_chokepoint import (
    AT, DECISION, LIMITS, MANDATE, PUBLISHED, SIX, SNAPSHOT, THRESHOLDS, opened,
)

REPO = Path(__file__).resolve().parents[1]


def fund(tmp_path, usdg="200"):
    conn = db.connect(tmp_path / "fund.sqlite")
    store, journal = OrderStore(conn), Journal(conn)
    for event in opened(usdg):
        journal.append(event)
    for order in SIX:
        store.add(order)
    return store, journal


def run(store, journal, order, executor=None, **rest):
    venue = FakeVenue(SNAPSHOT, lambda: Instant_at())
    admission = execute.by_record(DECISION, public_key=PUBLISHED, mandate=MANDATE,
                                  limits=LIMITS, at=AT, journal=journal)
    return execute.run_order(order.order_id, admission=admission, thresholds=THRESHOLDS,
                             venue=venue, executor=executor or execute.PaperExecutor(SNAPSHOT),
                             store=store, journal=journal, at=AT, **rest)


class Watching:
    """The paper executor, recording what the database says about the order at the
    moment it is asked to send it."""

    mode = execute.PaperExecutor.mode

    def __init__(self, path):
        self.path, self.inner, self.seen = path, execute.PaperExecutor(SNAPSHOT), []

    def submit(self, order, quote):
        conn = db.connect(self.path)
        self.seen.append((OrderStore(conn).get(order.order_id).state,
                          len(Journal(conn).events())))
        return self.inner.submit(order, quote)


def Instant_at():
    from fund.core.types import Instant
    return Instant(AT.epoch_ms - 5_000)


def test_an_order_is_prepared_then_submitted_then_confirmed_with_its_fill(tmp_path):
    store, journal = fund(tmp_path)
    seen, watching = [], Watching(tmp_path / "fund.sqlite")
    assert store.get(SIX[0].order_id).state is OrderState.PREPARED
    done = run(store, journal, SIX[0], executor=watching,
               checkpoint=lambda step, order: seen.append(
                   (step, OrderStore(db.connect(tmp_path / "fund.sqlite"))
                    .get(order.order_id).state)))
    # when the executor was asked to send it, submitted was already on disk, and
    # nothing was booked: the state is written before the act it names
    assert watching.seen == [(OrderState.SUBMITTED, 1)]
    assert seen == [("submitted", OrderState.SUBMITTED)]
    assert done.order.state is OrderState.CONFIRMED and done.booked
    reopened = Journal(db.connect(tmp_path / "fund.sqlite")).events()
    assert reopened[-1] == done.outcome.fill


def test_the_six_orders_fill_once_each_and_the_book_follows_the_ledger(tmp_path):
    store, journal = fund(tmp_path)
    for order in SIX:
        assert run(store, journal, order).booked
    events = journal.events()
    assert len([e for e in events if isinstance(e, ledger.Fill)]) == 6
    book = ledger.value(events, book="paper", snapshot=SNAPSHOT)
    assert len(book.positions) == 6
    with localcontext(cash.EXACT):  # the ledger's figures are exact; the default rounds
        assert book.nav_usd == (book.opened_usd + book.realised_usd + book.unrealised_usd
                                - book.costs_usd)


def test_an_order_already_finished_is_not_sent_again_and_books_nothing(tmp_path):
    store, journal = fund(tmp_path)
    first = run(store, journal, SIX[0])
    again = run(store, journal, SIX[0])
    assert again.outcome is None and again.admission is None
    assert again.order.state is OrderState.CONFIRMED
    assert len(journal.events()) == 2  # the opening and one fill
    assert first.outcome.fill == journal.events()[-1]


def test_an_order_left_in_flight_is_not_sent_again_here_but_left_to_startup(tmp_path):
    """4.9 resolves a submitted or unknown order. `run_order` never re-sends one."""
    store, journal = fund(tmp_path)
    store.move(SIX[0].order_id, OrderState.SUBMITTED)
    done = run(store, journal, SIX[0])
    assert done.outcome is None and done.order.state is OrderState.SUBMITTED
    store.move(SIX[0].order_id, OrderState.UNKNOWN, reason="constructed")
    assert run(store, journal, SIX[0]).order.state is OrderState.UNKNOWN
    assert len(journal.events()) == 1


def test_a_refused_order_is_written_refused_with_its_reasons_and_nothing_is_sent(tmp_path):
    store, journal = fund(tmp_path, usdg="30")  # too little cash for six buys
    done = [run(store, journal, order) for order in SIX]
    refused = [d for d in done if d.order.state is OrderState.REFUSED]
    assert refused and all(d.outcome is None for d in refused)
    assert all("cash-floor" in d.order.state_reason for d in refused)
    fills = [e for e in journal.events() if isinstance(e, ledger.Fill)]
    assert len(fills) == len(done) - len(refused)


def test_a_fill_and_its_state_are_one_write(tmp_path):
    """The journal refuses a second fill for an order. When it does, the order's state
    does not move either: the write is one or none."""
    store, journal = fund(tmp_path)
    quote = execute.requote(SIX[0], FakeVenue(SNAPSHOT, Instant_at), AT, THRESHOLDS)
    journal.append(execute.PaperExecutor(SNAPSHOT).submit(
        moves.transition(SIX[0], OrderState.SUBMITTED), quote.observation.value).fill)
    with pytest.raises(Exception, match="already filled"):
        run(store, journal, SIX[0])
    assert store.get(SIX[0].order_id).state is OrderState.SUBMITTED  # not confirmed
    assert len([e for e in journal.events() if isinstance(e, ledger.Fill)]) == 1


def test_nothing_is_attempted_before_every_order_is_written_prepared(tmp_path):
    """The run is killed at the checkpoint after the orders are written and before the
    first is admitted. On reopen every order is prepared, the venue was never asked,
    and nothing is booked."""
    marker = tmp_path / "venue-asked"
    script = textwrap.dedent(f"""
        import os, signal, sys
        sys.path[:0] = [{str(REPO / 'src')!r}, {str(REPO / 'tests')!r}]
        from fund.store import db
        from fund.store.journal import Journal
        from fund.store.orders import OrderStore
        from test_chokepoint import SIX
        from test_run_order import fund
        store, journal = fund(__import__("pathlib").Path({str(tmp_path)!r}))
        os.kill(os.getpid(), signal.SIGKILL)   # between the writes and the first attempt
    """)
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == -signal.SIGKILL, done.stderr
    conn = db.connect(tmp_path / "fund.sqlite")
    assert [o.state for o in OrderStore(conn).all()] == [OrderState.PREPARED] * 6
    assert not marker.exists()
    assert [type(e).__name__ for e in Journal(conn).events()] == ["Opening"]
