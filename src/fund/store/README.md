# `store/` — what the fund remembers

One SQLite file. It records; it decides nothing.

| File | What it keeps |
|---|---|
| `schema.sql` | the tables, and the constraints that make an impossible row impossible |
| `db.py` | the connection and one transaction helper |
| `orders.py` | every order and its state, written **before** the act it describes |
| `journal.py` | the append-only event log: openings, fills, transfers, fees, inference costs |
| `positions.py` | the book, read back out of the journal |
| `reports.py` | every analyst reply as it arrived, by id |

**Nothing is edited.** The journal only ever gains a row. A position is not stored — it
is derived by folding the journal, every time. If the two ever disagreed, there would
be a question about which was right; there is only one place a figure can come from.

**State is written before the act, not after.** An order is `prepared` before it is
admitted and `submitted` before it is sent, so a crash mid-send leaves evidence that
something may have gone out — which is recoverable. The opposite order loses money
silently.

**The fill and the state are one write.** A confirmed order and the fill it produced go
into the database in a single transaction, so there is no moment where the books and
the orders disagree.

**Not built:** `publish.py`, which will write signed records under their own hash for
sale (Phase 7).
