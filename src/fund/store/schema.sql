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

-- Every move an order made, appended, never edited: the order's history.
CREATE TABLE IF NOT EXISTS order_moves (
    order_id  TEXT NOT NULL REFERENCES orders (order_id),
    revision  INTEGER NOT NULL,
    from_state TEXT,
    to_state  TEXT NOT NULL,
    reason    TEXT,
    PRIMARY KEY (order_id, revision)
);
CREATE TRIGGER IF NOT EXISTS order_moves_append_only_update BEFORE UPDATE ON order_moves
    BEGIN SELECT RAISE(ABORT, 'order_moves is append-only'); END;
CREATE TRIGGER IF NOT EXISTS order_moves_append_only_delete BEFORE DELETE ON order_moves
    BEGIN SELECT RAISE(ABORT, 'order_moves is append-only'); END;
