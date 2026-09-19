"""Orders, durable (unit 4.3; PLAN §4).

Each order is one row, written `prepared` before anything is attempted, and moved
only through `core/orders.transition`, the one table of moves (4.0, P1 and P12).
This module persists what `transition` returns and never decides a state itself.
Every write is committed before `add` or `move` returns, so the state a move names is
on disk before the act it describes.

Two writers cannot both move one order: each move names the revision it moves from,
and a row another writer moved first refuses. An order added again, after a restart
lists a decision's orders again, keeps the state it has: it is never written back to
`prepared`, and its key never changes.

The row holds the state an order is in and why. No history is kept: nothing reads one
(CLAUDE.md). What moved value is the journal's, and it is append-only.
"""

from __future__ import annotations

import sqlite3
from fund.core import orders
from fund.core.types import Execution, Order, OrderState, from_canonical, to_canonical
from fund.store.db import transaction


class StoreError(ValueError):
    """The store refused a write: the reason is named."""


def _body(order: Order) -> str:
    return to_canonical(order).decode()


def _order(body: str) -> Order:
    return from_canonical(body.encode())


class OrderStore:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def _row(self, order_id: str) -> tuple[Order, int] | None:
        row = self.conn.execute("SELECT body, revision FROM orders WHERE order_id = ?",
                                (order_id,)).fetchone()
        return None if row is None else (_order(row[0]), row[1])

    def add(self, order: Order) -> Order:
        """Write an order `prepared`. If it is already here, the stored order stands,
        in whatever state it has reached."""
        with transaction(self.conn):
            found = self._row(order.order_id)
            if found is not None:
                stored = found[0]
                if stored.idempotency_key != order.idempotency_key or stored.sell != order.sell:
                    raise StoreError(f"order {order.order_id} is stored as another order")
                return stored
            if order.state is not OrderState.PREPARED:
                raise StoreError(f"order {order.order_id} is {order.state.value}: an order is "
                                 "written prepared, before anything is attempted")
            self.conn.execute("INSERT INTO orders (order_id, idempotency_key, state, revision, "
                              "body) VALUES (?, ?, ?, 0, ?)",
                              (order.order_id, order.idempotency_key, order.state.value,
                               _body(order)))
        return order

    def get(self, order_id: str) -> Order | None:
        found = self._row(order_id)
        return None if found is None else found[0]

    def move(self, order_id: str, to: OrderState, *, reason: str | None = None,
             execution: Execution | None = None) -> Order:
        """The order moved to `to`, by `core/orders.transition`, and committed."""
        with transaction(self.conn):
            found = self._row(order_id)
            if found is None:
                raise StoreError(f"no order {order_id}")
            current, revision = found
            moved = orders.transition(current, to, reason=reason, execution=execution)
            done = self.conn.execute(
                "UPDATE orders SET state = ?, revision = ?, body = ? "
                "WHERE order_id = ? AND revision = ?",
                (moved.state.value, revision + 1, _body(moved), order_id, revision))
            if done.rowcount != 1:
                raise StoreError(f"order {order_id} was moved by another writer")
        return moved

    def all(self) -> list[Order]:
        """Every order, in the order it was written."""
        return [_order(body) for (body,) in
                self.conn.execute("SELECT body FROM orders ORDER BY rowid")]
