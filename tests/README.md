# `tests/` — what the suite proves

**795 tests, about 42 seconds, no network and no credentials.** `make test` on a fresh
clone.

```bash
make test                                   # everything
PYTHONPATH=src python3 -m pytest tests/test_accounting.py -q   # the ledger against a hand-computed answer
```

## Two kinds of test, and the difference matters

**Tests that guard money** — marks, valuation, sizing, orders, the books, keys, the
signature, the signed record. These are held to a harder standard: the rule is broken
in a scratch copy of the repository and the suite is re-run to confirm a test actually
fails. A test that passes whether or not the code is correct is worse than no test,
because it is believed. Every unit that touches money records how many breaks were
tried and how many were caught — and the cases where a break was *not* caught are in
`tracker/LESSONS.md`.

**Tests that guard plumbing** — presentation, formatting, wiring, and rules already
guarded elsewhere on the same path. A passing test is enough. Nothing is deliberately
broken to prove them, because the ceremony costs more than it earns.

## What is worth opening

| File | What it establishes |
|---|---|
| `test_accounting.py` | the ledger against an answer worked out **by hand** in `fixtures/accounting/answer.md`, to the last digit, including a rounding that happens once |
| `test_replay_cycle.py` | a recorded decision rebuilds byte for byte from its own carried inputs — including the config and the brief it was decided under, not today's |
| `test_boundaries.py` | the import graph: `core/` cannot reach the network, an analyst cannot reach a signing path. The rules in `planning/CODEBASE.md`, as tests |
| `test_chokepoint.py` | known-bad orders, each refused by the rule it breaks |
| `test_reconcile.py` | the receipt reader, against a **real recorded receipt** from a real swap |
| `test_liveleg.py` | the live executor: a 200 is not a fill, a mined revert is a cost with no fill, an unsettled swap is unknown |
| `test_cycle.py` | a whole paper cycle, and that a veto stops the order it names and no other |

`tests/data/` holds two recordings from real transactions, so the tests that decide what
gets booked are held against what the chain actually returned, not a mock someone wrote
to agree with the code.

**What the suite does not do:** reach the network, spend anything, or prove the live
paths end to end. Those were exercised by hand and are recorded in `tracker/LOGS.md`.
