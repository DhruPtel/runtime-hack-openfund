"""The one SQLite file the fund's durable state lives in (PLAN §13: a single runner,
a single file). Opening it applies `schema.sql`, which creates what is absent.

Writes are explicit transactions: `transaction` begins one, commits it before
returning, and rolls it back on any error. Inside another transaction it joins that
one, so a caller can make several writes one atomic act, as the executor does with a
fill and its order's new state (4.5, 4.6). `synchronous = FULL`: a commit is on disk
when it returns, so a state written before an act survives a crash after it.
"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Iterator

SCHEMA = Path(__file__).with_name("schema.sql")


def connect(path: Path | str) -> sqlite3.Connection:
    """The fund's database at `path`, created if absent, with every table present."""
    conn = sqlite3.connect(str(path), isolation_level=None)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA synchronous = FULL")
    conn.executescript(SCHEMA.read_text())
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """One atomic, durable write. Joins a transaction already open."""
    if conn.in_transaction:
        yield conn
        return
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield conn
    except BaseException:
        conn.execute("ROLLBACK")
        raise
    conn.execute("COMMIT")
