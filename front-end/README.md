# `front-end/` — the dashboard

One HTML file, no build step, no framework. It reads what the fund wrote.

```bash
PYTHONPATH=src python3 -m fund.run.serve     # → http://127.0.0.1:8000
#                             /?empty        → nothing decided yet, for a demo
# or just open front-end/Openfund.html       → no server; everything still renders
```

```
  the fund's artifacts                 the exporter                 the page
  ────────────────────                 ────────────                 ────────
  record.json    (signed)      ┐
  book.json      (paper+real)  ├──►  run/dashboard.py  ──►  data/openfund-data.js
  results/*.json (the seats)   │     reads and renames;      ──►  Openfund.setData()
  outcome.json   (each swap)   │     computes nothing             ──►  seven sections
  snapshot.json  (the marks)   ┘
```

**The exporter never computes.** Every figure on the page is read off an artifact — a
record the treasurer signed, a book the ledger reconciled, a receipt read from the
chain. Where the fund produces no figure, the payload carries `null` and a reason, and
the page shows a dash beside it. Two exceptions, both stated in the code: a position's
share of NAV, and the sum of one asset's own orders.

## The seven sections

| Section | What it shows | Read from |
|---|---|---|
| **Overview** | the **paper** portfolio: NAV, cash, positions, each price naming its Chainlink feed | `book.json` (paper), the snapshot's marks |
| **Swarm** | the four seats, their reports in full, cost and latency — including a seat that **failed**, with the validator's reason | the runner's results, the record's reports |
| **Decision** | how calls became weights, per asset. Click a row for its contract, feed address, round id, pinned block, and three prices from three sources | the record's proposal and plan |
| **Risk** | every order with the agent's own sentence. Click one for the gates with what they measured, the fresh quote with its age and endpoint, and the agent's model, cost and latency | the record's gates and risk verdict |
| **Books** | **both books, side by side, never added:** paper and real, each with its identity reconciling | `book.json` for each |
| **Record** | the signed decision: its id, signature, and what a buyer would get | the record and its envelope |
| **Chain** | **all four real swaps**, newest first, with hashes and explorer links | each swap's `outcome.json` |

## What the page says plainly rather than hiding

- **Stock fills are paper**, with the measured 403 quoted where the holdings are shown.
- **Revenue is a dash.** The journal has no settled-revenue event, so there is no
  revenue and no net income — shown as absent with the reason, not as zero dollars.
- **The record's price and endpoint are dashes.** The live x402 endpoint sells a Phase 0
  probe response at 0.001 USDC, not this record.
- **No per-agent wallets, and no per-report signatures.** Reports are *validated*
  against the snapshot, not signed; only the record is signed.

## Files

| | |
|---|---|
| `Openfund.html` | the page. Its data comes only through `Openfund.setData(name, payload)` |
| `wire.js` | hands the export to the page, drives the two buttons, and disables them with a reason when there is no server |
| `data/` | the committed export, as a `.js` assignment — because `fetch` cannot read a local file, and the page must work from `file://` |
| `CONNECTIONS.md` | the map written **before** the wiring: every display against the artifact it comes from |
| `checks/` | headless renders that assert what the page shows. 12 offline, 9 served, 17 for the demo states |

**The two buttons spend real money** and both confirm first, naming the cost, the size,
the wallet and the chain. The backend refuses any request that does not explicitly say
`{"confirm": "spend"}`.
