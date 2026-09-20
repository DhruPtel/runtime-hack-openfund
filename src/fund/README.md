# `src/fund/` — the fund

Six layers. Each may only reach *downward*, and two of the arrows that are missing
matter more than the ones that are there.

```
   run/          one command each: a snapshot, a cycle, the live leg, the dashboard
    │            orchestrates. Owns no rule of its own.
    ├────────────┬──────────────┬─────────────┐
    ▼            ▼              ▼             ▼
  agents/     treasurer/      store/      adapters/
  think       spends          remembers   read the outside world
    │            │              │             │
    └────────────┴──────┬───────┴─────────────┘
                        ▼
                      core/      decides. Pure. No network, no clock, no files.
```

**The two rules that shape everything:**

1. **`core/` never reaches the network.** Every figure the fund acts on is computed
   from values that were already read, written down and hashed. This is why a decision
   can be rebuilt byte for byte a week later: nothing in the deciding path can ask the
   world a second question and get a different answer.
2. **An analyst can never reach a signing path.** The agent processes cannot import
   `treasurer/`, and the credential table refuses to hand them a key that can transact.
   Spend authority lives in one process. A model that decides what to buy is never the
   thing that can buy it.

Both are enforced as tests, not conventions — `tests/test_boundaries.py` reads the
import graph and fails the build if an arrow appears that should not exist.

| Layer | Owns | Must never |
|---|---|---|
| [`adapters/`](adapters/README.md) | every byte that comes from outside: the chain, prices, quotes, models | interpret. It reports what it heard, including refusals |
| [`core/`](core/README.md) | the rules: marks, weights, sizing, gates, the ledger | touch the network, the clock, or the filesystem |
| [`agents/`](agents/README.md) | the four analysts and the risk agent, each in its own process | hold a key that can spend or sign |
| [`treasurer/`](treasurer/README.md) | the mandate, the chokepoint, the signature, execution | trust anything the decision computed without checking it again |
| [`store/`](store/README.md) | durable memory: orders, the journal, reports | decide anything; it records what it is told |
| [`run/`](run/README.md) | the commands a person types | invent a rule that belongs in `core/` |

`config.py`, `credentials.py` and `redaction.py` sit at the root: which process may hold
which secret, and a redactor that keeps a credential out of a log even in a traceback.

**Not built:** `core/books.py` and `core/attribution.py` (Phase 6, the income statement
and per-agent attribution), `store/publish.py` and `surfaces/` (Phase 7, selling the
record over x402), `run/schedule.py` (Phase 8, unattended cycles). Each file says so at
the top rather than looking like something missing.
