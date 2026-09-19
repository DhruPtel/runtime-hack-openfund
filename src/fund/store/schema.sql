-- The fund's durable state: one SQLite file (PLAN §13, a single runner). Written only
-- by store/. Every table is created if absent, so opening a file is idempotent.

-- Orders (4.3). Each row is one Order, canonical JSON in `body`, its state repeated
-- in `state` for queries. A row is written only through core/orders.transition, and
-- each write is committed before the act its state names (PLAN §4).
CREATE TABLE IF NOT EXISTS orders (
    order_id        TEXT PRIMARY KEY,
    idempotency_key TEXT NOT NULL UNIQUE,
    state           TEXT NOT NULL CHECK (state IN
                        ('prepared', 'submitted', 'unknown', 'confirmed', 'failed', 'refused')),
    revision        INTEGER NOT NULL,
    body            TEXT NOT NULL
);

-- An order's moves are not kept: the state it is in, and why, is the row above, and
-- nothing in the fund reads a history (CLAUDE.md, no function without a caller). The
-- journal keeps what moved value.

-- The journal (4.6): every event that moves value, appended in order and never edited.
-- `body` is core/ledger.encode's document; `kind` and `order_id` are repeated from it
-- for the one rule the store itself keeps: an order is filled at most once.
CREATE TABLE IF NOT EXISTS events (
    seq      INTEGER PRIMARY KEY AUTOINCREMENT,
    kind     TEXT NOT NULL CHECK (kind IN ('opening', 'fill', 'fee', 'inference')),
    order_id TEXT,
    body     TEXT NOT NULL
);
CREATE UNIQUE INDEX IF NOT EXISTS one_fill_per_order ON events (order_id) WHERE kind = 'fill';
CREATE TRIGGER IF NOT EXISTS events_append_only_update BEFORE UPDATE ON events
    BEGIN SELECT RAISE(ABORT, 'the journal is append-only'); END;
CREATE TRIGGER IF NOT EXISTS events_append_only_delete BEFORE DELETE ON events
    BEGIN SELECT RAISE(ABORT, 'the journal is append-only'); END;

-- The single-owner lock (4.10). One row, so two runners cannot both spend (PLAN §4).
-- `host` and `pid` are there so a runner that died on this host can be taken over;
-- a holder anywhere else never is.
CREATE TABLE IF NOT EXISTS runner_lock (
    id    INTEGER PRIMARY KEY CHECK (id = 1),
    owner TEXT NOT NULL,
    host  TEXT NOT NULL,
    pid   INTEGER NOT NULL
);
