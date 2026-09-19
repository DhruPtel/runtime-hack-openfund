"""The journal: every event that moves value, appended and never edited (unit 4.6).

Minimal (SIMPLIFICATION 4.6): opening balances, fills, fees and inference costs, the
four events `core/ledger.py` defines. Transfers, credit purchases and marks as events
are the full version's.

The journal keeps events in order and reads them back exactly; it computes nothing.
Every figure is `core/ledger.py`'s, from `events()`: holdings, cash, basis, value. An
edit or a delete is refused by the database itself, and so is a second fill for one
order, so a crash and a retry can never book an order twice.
"""

from __future__ import annotations

import json
import sqlite3

from fund.core import ledger
from fund.store.db import transaction


class JournalError(ValueError):
    """The journal refused an event: the reason is named."""


class Journal:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def append(self, event: ledger.Event) -> int:
        """Keep one event, after every event before it. Returns its place."""
        document = ledger.encode(event)
        with transaction(self.conn):
            try:
                done = self.conn.execute(
                    "INSERT INTO events (kind, order_id, body) VALUES (?, ?, ?)",
                    (document["kind"], document.get("order_id"),
                     json.dumps(document, sort_keys=True, separators=(",", ":"))))
            except sqlite3.IntegrityError as refused:
                raise JournalError(f"order {document.get('order_id')} is already filled: "
                                   "an order is booked once") from refused
        return done.lastrowid

    def events(self) -> list[ledger.Event]:
        """Every event, in the order it was kept."""
        return [ledger.decode(json.loads(body)) for (body,) in
                self.conn.execute("SELECT body FROM events ORDER BY seq")]
