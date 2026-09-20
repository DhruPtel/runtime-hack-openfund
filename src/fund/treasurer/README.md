# `treasurer/` — the only thing that can spend

One process, its own credentials, and a rule it applies to itself: **trust nothing the
decision computed.**

| File | What it does |
|---|---|
| `execute.py` | the **chokepoint** — the one function every order passes before it is sent — and the two executors, paper and live |
| `mandate.py` | the operator's signed permission: which chain, which wallet, which assets, how much, until when |
| `intent.py` | a signed decision record → the orders it approved, each with a stable id |
| `instruct.py` | the live leg's own signed authority, for the one trade no analyst chose |
| `sign.py` | ed25519 over the record's exact bytes. `signed: false` never authorizes |
| `keys.py` | the published public key a record is checked against — never the key the envelope names |
| `reconcile.py` | what actually happened on chain, read from the receipt |

**The chokepoint re-checks everything, now.** The signature, that the snapshot is the
one the record names, that the order is one the record approved with those exact
amounts, that the mandate is still in force, every gate again on a *fresh* quote, that
the book holds what the order gives, and that the live budget is not exceeded. An order
that was fine when it was decided can be refused here, by name.

**A 200 is not a fill.** The venue answers `200` with `success: false` for a swap that
mined and reverted, and charges gas for it. So the outcome is read from the chain: the
EntryPoint's `UserOperationEvent`, the wallet's own `Transfer` logs, and its balance
across the block — never `tx.from`, never the HTTP status. Unsettled is **unknown**,
which stops the fund; it is never quietly treated as failed.

**One send.** No retry, ever. A repeat under the same idempotency key is the only safe
repeat, and minting a new key to escape uncertainty is the one thing this layer exists
to prevent.
