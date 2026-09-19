"""Units 4.9 and 4.10: the lock, and what the last run left. H: spend authority.

One runner spends, or none. And no new cycle until every order the last one left is
settled — from the journal, which is the paper receipt, or not at all when the answer
is on the chain.
"""

from __future__ import annotations

import dataclasses
import os
import socket
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from fund.core import ledger, orders as moves
from fund.core.types import ExecutionMode, OrderState
from fund.run import startup
from fund.store import db
from fund.store.journal import Journal
from fund.store.orders import OrderStore
from fund.treasurer import execute
from test_chokepoint import SIX, SNAPSHOT, THRESHOLDS
from test_run_order import Instant_at, fund

QUOTE_FOR_FILLED = execute.requote(
    SIX[0], __import__("fund.adapters.fake_venue", fromlist=["FakeVenue"]).FakeVenue(
        SNAPSHOT, Instant_at), Instant_at(), THRESHOLDS).observation.value

REPO = Path(__file__).resolve().parents[1]
P, S, U, C, F, R = (OrderState.PREPARED, OrderState.SUBMITTED, OrderState.UNKNOWN,
                    OrderState.CONFIRMED, OrderState.FAILED, OrderState.REFUSED)


def dead_pid() -> int:
    """A pid that has certainly exited."""
    gone = subprocess.Popen([sys.executable, "-c", "pass"])
    gone.wait()
    return gone.pid


# --- 4.10: one runner spends, or none -------------------------------------------------------------

def another_runner(tmp_path) -> subprocess.CompletedProcess:
    """A second runner, in its own process, trying to take the lock."""
    script = textwrap.dedent(f"""
        import sys
        sys.path[:0] = [{str(REPO / 'src')!r}]
        from fund.run import startup
        from fund.store import db
        conn = db.connect({str(tmp_path / 'fund.sqlite')!r})
        try:
            with startup.owning(conn):
                print("took the lock")
        except startup.NotReady as refused:
            print(refused)
            sys.exit(1)
    """)
    return subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)


def test_a_second_runner_refuses_while_the_first_holds_the_lock(tmp_path):
    conn = db.connect(tmp_path / "fund.sqlite")
    with startup.owning(conn) as owner:
        assert owner.endswith(str(os.getpid()))
        refused = another_runner(tmp_path)
        assert refused.returncode == 1 and "another runner holds the lock" in refused.stdout
    took = another_runner(tmp_path)  # released, so the next runner may have it
    assert took.returncode == 0 and "took the lock" in took.stdout


def test_a_lock_left_by_a_dead_runner_here_is_taken_over_and_one_elsewhere_is_not(tmp_path):
    conn = db.connect(tmp_path / "fund.sqlite")
    here, gone = socket.gethostname(), dead_pid()
    conn.execute("INSERT INTO runner_lock (id, owner, host, pid) VALUES (1, ?, ?, ?)",
                 (f"{here}:{gone}", here, gone))
    with startup.owning(conn):  # its process is gone: the lock is ours
        held = conn.execute("SELECT owner FROM runner_lock").fetchone()[0]
        assert held.endswith(str(os.getpid()))
    conn.execute("INSERT INTO runner_lock (id, owner, host, pid) VALUES (1, ?, ?, ?)",
                 ("elsewhere:1", "elsewhere", 1))
    with pytest.raises(startup.NotReady):  # another host is never taken over
        with startup.owning(conn):
            pass


# --- 4.9: what the last run left ------------------------------------------------------------------

def test_an_order_left_in_flight_is_confirmed_by_its_fill_and_failed_without_one(tmp_path):
    store, journal = fund(tmp_path)
    filled, empty = SIX[0], SIX[1]
    store.move(filled.order_id, S)
    journal.append(ledger.paper_fill(moves.transition(filled, S), QUOTE_FOR_FILLED, SNAPSHOT))
    store.move(empty.order_id, S)

    settled = {r.order_id: r for r in startup.resolve(store.conn)}
    assert settled[filled.order_id].state is C and "holds its fill" in settled[filled.order_id].why
    assert settled[empty.order_id].state is F and "never filled" in settled[empty.order_id].why
    assert store.get(filled.order_id).state is C and store.get(empty.order_id).state is F
    assert startup.resolve(store.conn) == []  # once settled, there is nothing to settle


def test_a_prepared_order_found_at_startup_is_refused_as_stale(tmp_path):
    store, journal = fund(tmp_path)
    settled = startup.resolve(store.conn)
    assert [r.state for r in settled] == [R] * len(SIX)
    assert all("never sent" in r.why for r in settled)
    assert {o.state for o in store.all()} == {R}
    assert [type(e).__name__ for e in journal.events()] == ["Opening"]


def test_a_live_order_left_in_flight_refuses_the_cycle(tmp_path):
    store, journal = fund(tmp_path)
    live = dataclasses.replace(SIX[0], order_id="live/1", idempotency_key="live-key",
                               mode=ExecutionMode.LIVE)
    store.add(live)
    store.move(live.order_id, S)
    with pytest.raises(startup.NotReady, match="on the chain"):
        startup.resolve(store.conn)
