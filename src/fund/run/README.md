# `run/` — the commands

Each file is one command a person types. They compose the layers below; they own no
rule of their own.

| Command | What it does | Spends? |
|---|---|---|
| `python3 -m fund.run.snapshot` | build one live snapshot, capture it, and replay it from its own capture | no |
| `python3 -m fund.run.selftest --live` | attest all 235 configured addresses against the chain | no |
| `python3 -m fund.run.decide` | reports → weights → plan → gates → risk → a signed record. Executes nothing | only with `--confirm` |
| `python3 -m fund.run.cycle` | the whole thing: a decision, then the chokepoint, fills and the book | only with `--live` |
| `python3 -m fund.run.liveleg` | **the one that moves real money:** one ETH↔USDG swap | only with `--confirm` |
| `python3 -m fund.run.serve` | the dashboard and its small backend | the buttons do |
| `python3 -m fund.run.dashboard --export` | rewrite the page's data from the artifacts | no |
| `python3 -m fund.run.isolation --live` | try a swap with each analyst key and record the refusal | no |
| `startup.py` | (not a command) the lock, and resolving whatever the last run left | no |

**Every command that spends says so first.** `liveleg` prints the asset, the size, the
wallet and the chain, then stops unless `--confirm` is present. `cycle --live` needs the
flag. The dashboard's two buttons open a dialog naming the cost and refuse any request
that does not explicitly confirm — an earlier version spent $1.33 on a request nobody
meant to send, which is why that gate exists.

**One runner at a time.** `startup.py` takes a lock, and resolves every order the last
run left before a new one is accepted. A live order still in flight stops the fund: its
outcome is on the chain, and guessing is not an option.

**Not built:** `schedule.py` (Phase 8). There is no scheduler; cycles are started by
hand.
