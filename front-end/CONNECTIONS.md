# The connection map

What the page displays, what the fund writes, and where the two do not meet.
Written before any wiring (2026-09-20). **No design is changed by this document.**

## The seam the page already has

`Openfund.setData(name, payload)` replaces one of eight named objects —
`app, overview, swarm, decision, risk, books, record, chain` — and re-renders.
`Openfund.applyProgressEvent(e)` drives the flow diagram from real stages.
The page makes **no network requests** and works from `file://`. So wiring means:
build eight JSON payloads, hand them to `setData`, and stream progress events.

**Two constraints the page imposes, which shape everything below:**

1. `setData` **throws while a cycle is running** (`Finish or cancel the active
   cycle before replacing data`). New data can only be applied after `cycle.done`
   or `cancelCycle()`. A live run therefore animates first and repaints after.
2. `cycle.done` **requires a chain receipt** (`chain.done` must have fired, which
   requires `treasurer.done`). A paper cycle produces no transaction — see
   §Chain.

## The artifacts the fund writes

Per cycle, in `--out DIR` (gitignored `fixtures/live/decisions/<name>/`):

| File | What it holds |
|---|---|
| `record.json` | `schema, decided_at_ms, snapshot{sha256,block{number,time,chain_id}}, reports[{seat,agent,text,sha256}], proposal{rows[],cash,quorum,reported}, plan{orders[],book,funding,cash_after_usd,turnover_usd,judged_at_ms}, gates{plan[],orders[]}, decision{approved[],vetoed[],rebalance,cash_floor}, risk{agent,brief,budget,reply_text,decision{orders[],overall,...}}, hashes{}` |
| `envelope.json` | `decision_id` (= sha256 of record.json), `signed`, `algorithm`, `public_key`, `signature` |
| `book.json` | `book, block{number,time,chain_id}, nav_usd, cash{...}, positions[{symbol,address,units,raw,decimals,value_usd,basis_usd,unrealised_usd}], identity{opened_usd,realised_usd,unrealised_usd,costs_usd,nav_usd,rule}, expenses_usd` |
| `orders.json` | `[{order_id,state,reason,booked,fee_booked,tx_hash}]` |
| `book.txt`, `table.txt`, `plan.json`, `proposal.json`, `quotes.json`, `risk.json`, `reports.json` | the same content for a reader |

Per runner cycle (`fixtures/live/cycles/<stamp>/`): `cycle.json{cost,counts,seats}`
and `results/<seat>.json{seat,status,reason,cost,report_text,report{calls[]},attempts[{http_status,elapsed_ms,cost}]}`.

Per live swap (committed, `fixtures/liveleg/<name>/`): `instruction.json`,
`envelope.json`, `outcome.json{state,reason,execution{transaction{tx_hash,block},user_operation,transfers},book{…}}`.

---

## Section by section

### Chrome — `app`

| Page field | Shape | From |
|---|---|---|
| `product` | string | constant |
| `network` | string | constant — "Robinhood Chain" |
| `mode` | string | **must become "Mainnet"** — chain 4663 is mainnet; the page ships "Testnet" |
| `cycle` | string | the runner cycle's stamp, e.g. `20260920T012716Z` |
| `decisionId` | string | `envelope.decision_id` — **64 hex, not `OF-0042`**; needs a short form (`c55400f8…`) or it will overflow every label |
| `timestamp` | string | `record.decided_at_ms`, formatted |
| `nav` | 7 strings | constant |
| `snapshotHash` / `snapshotBlock` | string / int | `record.snapshot.sha256` / `.block.number` |
| `fundWallet` | string | `config/mandate.json:execution_wallet` |
| `demoNotice` | string | **must be rewritten** — it currently says the data is illustrative |

**Buttons:** `demo-info` → dialog over `demoNotice` (local).

### Overview — `overview`

| Page field | Shape | From |
|---|---|---|
| `nav`, `cash`, `positionCount` | numbers | `book.json` (paper) `nav_usd`, `cash.value_usd`, `len(positions)` |
| `holdings[].ticker/value/pnl` | string/number | `book.json` positions `symbol`, `value_usd`, `unrealised_usd` |
| `holdings[].price` | number | the snapshot's mark for that asset |
| `latest.approved` / `latest.vetoed` | int | `len(record.decision.approved)` / `len(.vetoed)` |
| `latest.summary` | string | `record.risk.decision.overall.why` — a sentence the risk agent actually wrote |
| `provenance.*` | strings | `envelope` + `record.snapshot` |

**Needs reshaping:** `holdings[].weight` is a share of NAV, and `latest.headline`
is a sentence — neither exists as a field. Weight is `value ÷ nav`; a headline
would be assembled from the approved/vetoed counts. **`holdings[].name`
(company name) does not exist anywhere** — the registry carries symbols only.

**⚠️ The blur risk.** Overview has *one* `nav`, one `cash`, one holdings table.
The fund has two books that must never be summed: paper **$200.03** (10 fills)
and real **$1.2858** (4 live fills). Recommendation, for the operator to confirm:
Overview shows the **paper** book, labelled as such in `subtitle`, because
holdings and weights only exist there; the real book gets its own row in Books
and the real transactions get Chain. No field anywhere adds the two.

### Swarm — `swarm`

| Page field | From |
|---|---|
| `snapshot.hash/block` | `record.snapshot.sha256` / `.block.number` |
| `reportCost` | `cycle.json:cost.usd` (an estimate — label it) |
| `signedReports` | `len(record.reports)` |
| `weights` | `record.proposal.rows` → "SPY 12.5% · GME 12.5% · …" |
| `agents[].id/seat` | the four seats, mapped `price-trend→trend`, `cross-asset-macro→macro`, `execution-quality→execution`, `price-integrity→integrity` |
| `agents[].cost` | `results/<seat>.json:cost` |
| `agents[].latency` | `attempts[].elapsed_ms` |
| `agents[].primaryCall/calls` | `results/<seat>.json:report.calls[{symbol,word,confidence}]` |
| `agents[].paragraphs` | `report_text`, split on blank lines |

**Does not exist:**
- `agents[].wallet` — the seats share one gateway key. Per-agent wallets were a
  Phase 0 probe, not built.
- `agents[].signature` — reports are **validated, not signed**; only the record
  is signed. `report.sha256` exists and is a different claim.
- `snapshot.elapsed`, `parallelTime` — build and wall-clock timings are printed,
  not written into an artifact.
- `agents[].confidence`, `.perspective`, `.summary` — per-*call* confidence
  exists; a seat-level one does not.

**⚠️ Shape mismatch:** `agents` is a fixed list of four with no failure state. In
the live cycle **three seats reported and `execution-quality` failed** (its reply
was refused twice by the validator). The page cannot currently say that.

**Buttons:** `source-reports` → dialog listing agents (local); `snapshot-details`
→ dialog (local).

### Decision — `decision`

| Page field | From |
|---|---|
| `rows[].asset/score/current/target` | `record.proposal.rows[]:symbol,score,current,target` |
| `rows[].trend/macro/execution/integrity{call,score}` | `proposal.rows[].contributions[{seat,word,value}]`, pivoted by seat |
| `cash{current,target,move}` | `record.proposal.cash` |
| `explanation` | `proposal.rows[].why` and `confidence_weights` |

**Needs reshaping:** `rows[].move` is USD per asset; the plan carries USD per
*order*, and an asset may have two (a split move), so move = the sum of that
asset's orders. **Does not exist:** `trendContribution`/`macroContribution`
(60/40) — our aggregator weights by confidence, not by a fixed seat split;
`step`/`threshold` are partly in `proposal.confidence_weights`.

### Risk — `risk`

| Page field | From |
|---|---|
| `orders[].asset/side` | `record.plan.orders[]:asset.symbol,side` |
| `orders[].amount` | `plan.orders[].usd` |
| `orders[].status` | `record.risk.decision.orders[].approved` → `approved`/`vetoed` |
| `orders[].paragraphs` | `risk.decision.orders[].model_why` — the agent's own sentence |
| `orders[].rule` | `decision.vetoed[].vetoed_by`, e.g. `["impact","risk"]` |
| `gates[]` | `record.gates.plan[].reason` — the five plan-level gates |
| `outcome` | assembled from the approved/vetoed counts |

**Needs reshaping:** `orders[].id` must be a stable string (`order-9`), because
the `order.resolved` progress event matches on it.
**Does not exist:** `risk.wallet` (no per-agent wallet); `orders[].proposed` and
`.allowed` as numbers — the limit and the measured value live inside the gate's
`reason` string (`"238bps > 50bps limit"`), not as fields.

### Books — `books`

**The cleanest match on the page.** `books[]` is already two entries, `paper` and
`real`, described as separate. Straight from each `book.json`:

| Page field | From |
|---|---|
| `nav` | `nav_usd` |
| `opening` / `realised` / `unrealised` / `reconcileCosts` | `identity.opened_usd` / `.realised_usd` / `.unrealised_usd` / `.costs_usd` |
| `costs` | `identity.costs_usd` |
| `expenses` | `expenses_usd` |
| `identity` (string) | `identity.rule` |

**Does not exist: `revenue`, and therefore `net`.** The journal has no
settled-revenue event and the identity has no line for it (4.11, 7.4). The honest
fill is `0` with the label saying why — not a number.

### Record — `record`

| Page field | From |
|---|---|
| `id` | `envelope.decision_id` |
| `signature` | `envelope.signature` |
| `snapshot` | `record.snapshot.sha256` |
| `approved` / `vetoed` / `signedReports` | counts from `record.decision` / `.reports` |
| `quote` | `record.risk.decision.overall.why` |

**Mismatches:** `signer` is drawn as a `0x…` address; ours is an **ed25519 public
key**, not an address. `payloadHash` and `id` are *the same value* — the decision
id is the sha256 of the record's bytes. `price` (0.25) — the live x402 challenge
asks **0.001 USDC**, and what that endpoint serves is a Phase 0 probe response,
not a record. `endpoint` exists but does not serve records.

**Buttons:** `verify-record` — currently presentational; a backend could really
run `python -m fund.treasurer.sign --verify`. `checkout`/`unlock-demo` — no
payment path is wired and none should be. `download-record` — can serve the real
`record.json`.

### Chain — `chain`

**⚠️ The biggest structural mismatch.** The page models *one transaction produced
by the cycle*: an asset, a quantity, a reference price, and weight `changes[]`.
The fund's cycle fills **on paper** (stock execution is location-gated), and its
real transactions are ETH↔USDG swaps from a **separate** command, authorized by a
signed instruction rather than by a decision.

What maps, from `fixtures/liveleg/*/outcome.json`:

| Page field | From |
|---|---|
| `transaction` | `execution.transaction.tx_hash` |
| `block` | `execution.transaction.block.number` |
| `timestamp` | `execution.transaction.block.timestamp` |
| `wallet` | `execution.user_operation.sender` |
| `explorerUrl` | `https://robinhoodchain.blockscout.com/tx/<hash>` (the page already opens it) |
| `asset` / `quantity` | the swap's legs, e.g. ETH → USDG, 0.00003 |

**Does not map:** `decisionId` — a swap is authorized by an instruction, not a
decision; `referencePrice`/`paperValue`; `changes[]` (weight moves) — a swap
changes no weights. There are **four** real transactions, and the section holds
one.

### The flow diagram

Progress events the page accepts, and what emits them:

| Event | Real source |
|---|---|
| `snapshot.start` / `.done{hash,elapsed}` | the snapshot build |
| `analysts.start`, `analyst.done{agent,elapsed}` | each `results/<seat>.json` as it lands |
| `aggregate.start` / `.done` | the decision's aggregation step |
| `risk.start`, `risk.done` | around the risk call |
| `order.resolved{order,verdict}` | **cannot fire during a live run** — the orders are not known until the record exists, and `setData` is refused while running |
| `treasurer.start` / `.done` | the treasurer subprocess |
| `chain.start` / `.done` | **a paper cycle has none** |
| `cycle.done` | requires `chain.done` first |

**The one flow problem to decide:** a real cycle ends at `treasurer.done`. Either
the run is shown as complete with the chain node still pending, or `chain.*` is
emitted only when a live leg ran. Both are honest; neither is a design change I
would make without asking.

---

## Summary of the three buckets

**Already match (wire directly):** both books and the whole identity; NAV, cash,
positions, basis and unrealised; the decision id, signature, snapshot hash and
block; approved and vetoed counts; every order with its side, USD and the risk
agent's own sentence; the plan-level gates; the proposal's rows and contributions;
per-seat cost, latency and parsed calls; report text; the transaction hash, block
and explorer link.

**Need a reshaping exporter (reads and renames only):** seat ids, order ids,
contributions pivoted by seat, report text split into paragraphs, the weights
string, headline and outcome sentences assembled from counts, per-asset move as
the sum of that asset's orders, `weight` as value ÷ NAV.

**The fund does not produce these at all:**
- per-agent wallets (Swarm, Risk)
- per-report signatures — reports are validated, not signed
- company names for tickers
- revenue, and therefore net income
- seat-level confidence, `perspective`, `summary`
- snapshot build time and analyst parallel time
- `proposed`/`allowed` as numbers (they are inside gate reason strings)
- a fixed trend/macro contribution split
- a cycle-produced chain transaction, a reference price, or weight `changes[]`
- a record-selling endpoint (the live one sells a probe at 0.001 USDC)

## Decisions I need before wiring

1. **Overview shows which book?** Recommendation: paper, labelled, with both in
   Books and the real money in Chain. It must never be a sum.
2. **The flow's chain step** for a paper cycle: end at `treasurer.done`, or emit
   `chain.*` from the most recent real swap?
3. **Chain section:** show the latest of the four real swaps, or all four?
4. **Empty fields** (revenue, wallets, signatures, names): show `0`/`—` with a
   one-line reason, or hide the control? I will not invent values.
