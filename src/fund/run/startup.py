"""Before a cycle: the lock, and whatever the last run left (units 4.9 and 4.10).

Two units, one module. Both are what a runner does before a cycle is accepted, both
work on the one connection, and both refuse a cycle the same way (`CLAUDE.md`: a plan
naming a unit is not a reason for a module).

**The lock (4.10).** One row. A second runner finds it and refuses, so two runners
cannot both spend (PLAN §4). A runner that died on this host leaves its row behind,
and the next start takes it over, because the process it names is gone. A holder on
another host is never taken over: the fund would rather stop than guess.

**What the last run left (4.9).** No new cycle until every order is resolved:
- an order left `submitted` or `unknown` is resolved from the journal. A paper fill
  and its order's state are written in one transaction (4.5), so a paper order the
  journal has no fill for never filled: it is `failed`, and one with a fill is
  `confirmed`. The journal is the receipt;
- a **live** order left in flight is read from the chain (5.3), when the caller
  passes a `read` that can: its receipt says whether it filled, what it moved and
  what gas it paid, and the fill, the gas and the order's new state are written in
  one transaction here, exactly as the executor's caller writes them. Without a
  reader, or while the chain has not settled it, the cycle is refused — the honest
  answer rather than a guess about money. It is never re-sent under a new key;
- a `prepared` order was never sent, and the evidence it was decided on is a cycle
  old. It is `refused` as stale, and the next cycle decides again on fresh evidence.
  S11 bounds how old a snapshot may be when it is decided on; this is that rule at a
  restart, which is where the operator put it.
"""

from __future__ import annotations

import os
import socket
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from fund.core import ledger
from fund.core.types import ExecutionMode, OrderState
from fund.store.db import transaction
from fund.store.journal import Journal
from fund.store.orders import OrderStore

STALE_INTENT = ("stale-intent: found at startup, never sent, and decided on evidence a cycle "
                "old; the next cycle decides again")
NO_FILL = ("found at startup with no fill: a paper fill and its order's state are one write, "
           "so it never filled")
ITS_FILL = "found at startup: the journal holds its fill"


class NotReady(ValueError):
    """The cycle is refused: the reason is named."""


@dataclass(frozen=True)
class Resolved:
    """One order the startup settled, and how."""

    order_id: str
    state: OrderState
    why: str


def _alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


@contextmanager
def owning(conn: sqlite3.Connection) -> Iterator[str]:
    """Hold the single-owner lock for as long as the block runs."""
    host, pid = socket.gethostname(), os.getpid()
    me = f"{host}:{pid}"
    with transaction(conn):
        held = conn.execute("SELECT owner, host, pid FROM runner_lock WHERE id = 1").fetchone()
        if held is None:
            conn.execute("INSERT INTO runner_lock (id, owner, host, pid) VALUES (1, ?, ?, ?)",
                         (me, host, pid))
        elif held[0] != me:
            if held[1] != host or _alive(held[2]):
                raise NotReady(f"another runner holds the lock: {held[0]}. One runner spends, "
                               "or none.")
            conn.execute("UPDATE runner_lock SET owner = ?, host = ?, pid = ? WHERE id = 1",
                         (me, host, pid))
    try:
        yield me
    finally:
        with transaction(conn):
            conn.execute("DELETE FROM runner_lock WHERE id = 1 AND owner = ?", (me,))


def resolve(conn: sqlite3.Connection,
            read: Callable[[Any], Any] | None = None) -> list[Resolved]:
    """Settle every order the last run left, or refuse the cycle.

    `read` is how a live order in flight is settled: given the order, it returns the
    executor's own `Outcome` from the chain, or None when there is nothing to read.
    `run/liveleg.py` passes one built on `treasurer/reconcile.py`."""
    store, journal = OrderStore(conn), Journal(conn)
    filled = ledger.booked(journal.events())
    settled = []
    for order in store.all():
        if order.state is OrderState.PREPARED:
            store.move(order.order_id, OrderState.REFUSED, reason=STALE_INTENT)
            settled.append(Resolved(order.order_id, OrderState.REFUSED, STALE_INTENT))
        elif order.state in (OrderState.SUBMITTED, OrderState.UNKNOWN):
            if order.order_id in filled:  # booked: the fill settles it, whichever book
                store.move(order.order_id, OrderState.CONFIRMED, reason=ITS_FILL)
                settled.append(Resolved(order.order_id, OrderState.CONFIRMED, ITS_FILL))
            elif order.mode is not ExecutionMode.PAPER:
                outcome = read(order) if read is not None else None
                if outcome is None or outcome.state is OrderState.UNKNOWN:
                    raise NotReady(f"order {order.order_id} is a live order left "
                                   f"{order.state.value} with no fill, and the chain has not "
                                   f"settled it: "
                                   f"{'no reader' if outcome is None else outcome.reason}")
                with transaction(conn):  # the fill, its gas and the state, one write
                    if outcome.fill is not None:
                        journal.append(outcome.fill)
                    if outcome.fee is not None:
                        journal.append(outcome.fee)
                    store.move(order.order_id, outcome.state, reason=outcome.reason,
                               execution=outcome.execution)
                settled.append(Resolved(order.order_id, outcome.state, outcome.reason or ""))
            else:
                store.move(order.order_id, OrderState.FAILED, reason=NO_FILL)
                settled.append(Resolved(order.order_id, OrderState.FAILED, NO_FILL))
    return settled
