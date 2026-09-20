# `core/` — the rules

Pure Python. **No network, no clock, no filesystem.** Every function here takes values
that were already read and written down, and returns a figure or a refusal. That is the
whole reason a decision made on Saturday can be rebuilt, byte for byte, on Sunday.

| File | The rule it owns |
|---|---|
| `types.py` | what an amount, a price, an order, a receipt *is*. Exact decimals; never a float |
| `snapshot.py` | assembling one frozen, hashed document of everything known at one block |
| `valuation.py` | what a holding is worth, and when it cannot be said |
| `aggregate.py` | four analysts' calls → proposed weights, or a recorded refusal to rebalance |
| `plan.py` | weights → sized orders against real quotes |
| `gates.py` | every fixed limit, in one place: tradeability, the mandate, order size, quote age, position weight, the cash floor, quorum |
| `orders.py` | which states an order may move through, and how its id and idempotency key are derived |
| `ledger.py` | the one fold over the journal: holdings, basis, realised, unrealised, and the identity `opened + realised + unrealised − costs = NAV` |
| `cash.py` | the one definition of cash, after three components once counted it three ways |
| `record.py` | what a decision record contains, and which schema it is |
| `context.py` | how large the risk agent's bundle is, measured before it is sent |
| `universe.py` | which assets exist, pinned by address |

**Why "no network" is load-bearing.** A gate that could fetch a price would give a
different verdict on a Tuesday. Every gate here reads a number that is already in the
snapshot or the plan, so the same inputs always produce the same verdict — which is
what makes the replay test meaningful rather than decorative.

**False refuses, and unknown refuses too.** A gate returns true, false, or null. Null
means the fund could not establish the thing, and it blocks exactly like a false. There
is no path where uncertainty becomes permission.

**Not built:** `books.py` (the income statement) and `attribution.py` (which analyst
earned what) are Phase 6 and say so.
