"""Unit 4.3: orders, durable before the act each state names. H: order state.

The store writes what `core/orders.transition` returns and never decides a state.
"""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from fund.core import orders as moves
from fund.core.types import OrderState
from fund.store import db
from fund.store.orders import OrderStore, StoreError
from test_orders import prepared
from test_types import swap_execution, swap_order

REPO = Path(__file__).resolve().parents[1]
P, S, U, C, F, R = (OrderState.PREPARED, OrderState.SUBMITTED, OrderState.UNKNOWN,
                    OrderState.CONFIRMED, OrderState.FAILED, OrderState.REFUSED)


def opened(path: Path) -> OrderStore:
    return OrderStore(db.connect(path))


def test_an_order_is_written_prepared_and_is_there_after_a_reopen(tmp_path):
    store = opened(tmp_path / "fund.sqlite")
    order = store.add(prepared(1))
    again = opened(tmp_path / "fund.sqlite")  # another connection: what is on disk
    assert again.get(order.order_id) == order and again.get(order.order_id).state is P
    with pytest.raises(StoreError, match="written prepared"):
        store.add(moves.transition(prepared(2), S))


def test_each_move_is_on_disk_before_it_returns(tmp_path):
    store = opened(tmp_path / "fund.sqlite")
    order = store.add(prepared(1))
    store.move(order.order_id, S)
    assert opened(tmp_path / "fund.sqlite").get(order.order_id).state is S
    store.move(order.order_id, U, reason="timeout")
    assert opened(tmp_path / "fund.sqlite").get(order.order_id).state is U
    assert [(h["from"], h["to"]) for h in store.history(order.order_id)] == [
        (None, "prepared"), ("prepared", "submitted"), ("submitted", "unknown")]


def test_a_move_the_table_does_not_allow_is_refused_and_nothing_is_written(tmp_path):
    store = opened(tmp_path / "fund.sqlite")
    order = store.add(prepared(1))
    with pytest.raises(moves.IllegalMove, match="prepared → confirmed"):
        store.move(order.order_id, C)
    assert store.get(order.order_id).state is P and len(store.history(order.order_id)) == 1


def test_an_unknown_order_keeps_its_key_across_a_restart_and_is_sent_again_under_it(tmp_path):
    store = opened(tmp_path / "fund.sqlite")
    order = store.add(prepared(1))
    store.move(order.order_id, S)
    store.move(order.order_id, U, reason="the connection dropped")
    restarted = opened(tmp_path / "fund.sqlite")
    resent = restarted.move(order.order_id, S, reason="sent again with its key")
    assert resent.idempotency_key == order.idempotency_key == moves.idempotency_key(
        order.order_id.split("/")[0], 1)


def test_an_order_added_again_keeps_the_state_it_reached(tmp_path):
    store = opened(tmp_path / "fund.sqlite")
    order = store.add(prepared(1))
    store.move(order.order_id, R, reason="constructed refusal")
    assert store.add(prepared(1)).state is R  # never written back to prepared
    impostor = prepared(1).__class__(**{**{f: getattr(prepared(1), f) for f in (
        "order_id", "mode", "wallet", "sell", "buy_asset", "min_buy", "state")},
        "idempotency_key": "another-key"})
    with pytest.raises(StoreError, match="stored as another order"):
        store.add(impostor)


def test_two_writers_cannot_both_move_one_order(tmp_path):
    first, second = opened(tmp_path / "fund.sqlite"), opened(tmp_path / "fund.sqlite")
    order = first.add(prepared(1))
    first.move(order.order_id, S)
    with pytest.raises(moves.IllegalMove):  # the second reads the state the first wrote
        second.move(order.order_id, S)
    # a writer that read before the other moved is refused at the write
    stale = second._row(order.order_id)
    first.move(order.order_id, U, reason="timeout")
    second._row = lambda order_id: stale
    with pytest.raises(StoreError, match="another writer"):
        second.move(order.order_id, C, execution=None)


def test_a_live_orders_evidence_is_kept_with_its_state(tmp_path):
    store = opened(tmp_path / "fund.sqlite")
    live = swap_order(state=P)
    store.add(live)
    store.move(live.order_id, S)
    store.move(live.order_id, C, execution=swap_execution())
    assert opened(tmp_path / "fund.sqlite").get(live.order_id).execution == swap_execution()


def test_the_order_moves_are_append_only(tmp_path):
    store = opened(tmp_path / "fund.sqlite")
    store.add(prepared(1))
    for sql in ("UPDATE order_moves SET to_state = 'confirmed'", "DELETE FROM order_moves"):
        with pytest.raises(Exception, match="append-only"):
            store.conn.execute(sql)


def test_a_prepared_order_survives_the_process_being_killed_right_after_the_write(tmp_path):
    """The write returns, then the process is killed before it can do anything else.
    On reopen, the order is there, prepared."""
    script = textwrap.dedent(f"""
        import os, signal, sys
        sys.path[:0] = [{str(REPO / 'src')!r}, {str(REPO / 'tests')!r}]
        from fund.store import db
        from fund.store.orders import OrderStore
        from test_orders import prepared
        OrderStore(db.connect({str(tmp_path / 'fund.sqlite')!r})).add(prepared(1))
        os.kill(os.getpid(), signal.SIGKILL)
    """)
    done = subprocess.run([sys.executable, "-c", script], capture_output=True, text=True)
    assert done.returncode == -signal.SIGKILL, done.stderr
    assert opened(tmp_path / "fund.sqlite").get(prepared(1).order_id).state is P
