# Build plan v2

An onchain fund for tokenized stocks on Robinhood Chain, managed by a
supervisor/worker agent system that publishes reconciled books and sells its
research to other agents.

Revised against the technical review. Dispositions for every finding are in
`REVIEW-RESPONSE.md`. Stated limitations are in §13.

---

## 1. The product, in one paragraph

A fund holds tokenized equities on Robinhood Chain (chain 4663). Each cycle, a
set of read-only analyst agents receives one frozen, block-pinned market
snapshot and returns structured reports. A deterministic aggregator turns those
reports into proposed weights. A planner sizes those weights into candidate
orders using live quotes against the fund's actual reconciled holdings. A risk
agent then reads every full report **and the sized plan**, and may veto. A
treasurer, the only component with spend authority, revalidates the same gates
against fresh evidence, persists a durable order intent, and executes. An
accounting layer publishes reconciled statements: revenue, cost, P&L, and two
separate analyst measures. The signed decision record is sold over x402 and
shown on a public page.

**The pitch: a fund that shows its work.**

Architecture vocabulary: supervisor with read-only workers and a single writer.
"Swarm" is marketing language only, never a description of the design.

---

## 2. Invariants

Each is structural where possible, and tested where not.

1. **One spend authority.** The treasurer runs as its own process with its own
   credentials. Analyst processes never receive execution or signing secrets.
   Proven by an environment test from the deployed analyst process, not by an
   import graph alone.
2. **One frozen snapshot per cycle**, pinned to a single block, content-hashed,
   loaded into each analyst's prompt as bytes. Passing an id to a tool-less
   model is not data delivery.
3. **Risk sees every full report and the sized plan.** If the bundle exceeds the
   context budget, the cycle vetoes. It never silently summarizes.
4. **Gates exist once.** One module, called by both risk and treasurer. Never
   two interpretations of the same limit.
5. **Unknown blocks execution.** Every check is true / false / null. Null is not
   false. A required check must be explicitly true.
6. **`NO_CALL` is valid**, and the aggregator is a total function that handles
   all-abstain without liquidating anything.
7. **Assets are pinned by `(chain_id, address)`** from a versioned,
   issuer-derived allowlist with recorded provenance.
8. **Nothing is booked from an HTTP status.** A fill is evidenced by a receipt;
   revenue is evidenced by settlement.
9. **Everything published is immutable and addressed by content id.**

---

## 3. Corrected flow

```
  adapters ──► snapshot (block-pinned, hashed)
                   │
                   ├──► analysts (parallel, read-only, deadline-bounded)
                   │         │ full reports → immutable report store
                   │         ▼
                   └──► aggregator (deterministic, total function)
                             │ weights or no-rebalance
                             ▼
                        planner: sized candidate orders
                             │ live quotes, reconciled holdings, reservations
                             ▼
                   risk agent: all reports + sized plan → approve / veto
                             │
                             ▼
                   decision record (ed25519-signed, immutable id)
                        │                          │
                        ▼                          ▼
              treasurer: regate on fresh    publish → x402 handler
              evidence, persist intent,              → public page
              submit, reconcile receipt
                        │
                        ▼
              accounting journal ──► reconciled statements
```

The change from v1: risk receives sized orders, not bare weights, and the
treasurer regates immediately before submission.

---

## 4. Execution state machine

The single most likely real failure is a successful swap that never reaches the
ledger. Every order moves through durable states, written before the action they
describe.

| State | Meaning | Written when |
|---|---|---|
| `prepared` | intent, exact payload, idempotency key, mandate ref, balance reservation | **before** any HTTP call |
| `submitted` | request sent, no outcome yet | immediately before send |
| `unknown` | timeout, dropped connection, or `409` in-flight | on ambiguous response |
| `confirmed` | receipt with tx hash at or beyond confirmation depth | after receipt check |
| `failed` | explicit rejection, or `200 success:false` (mined revert: failed, real gas spent) | on evidenced failure |

Rules:

- An `unknown` order keeps its reservation. We never mint a new idempotency key
  to escape uncertainty.
- On restart, unresolved intents reconcile before any new cycle is accepted.
- A dependent buy waits for **confirmed** sale proceeds. A partial basket stays
  explicitly partial.
- One execution owner, enforced by a lock row. Two runners cannot both spend.
- The kill switch stops new submissions. It never stops reconciliation.

---

## 5. Deployment

Named concretely, because "it runs locally" is not a deployment.

- **Runner host:** one small always-on Linux host. Runs the cycle, analysts,
  planner, risk, treasurer, publisher.
- **State:** SQLite file, single writer, WAL. Authoritative for orders, reports,
  journal, positions.
- **Published records:** immutable JSON blobs on a public read-only HTTPS path
  served by the runner host, addressed by decision id, with a `latest.json`
  pointer advanced atomically after the record bytes land.
- **x402 handler:** small TypeScript handler on Bankr x402 Cloud. Fetches a
  published record by id over HTTPS. Holds no state, does no inference, makes no
  trades. Upstream timeout well under the 30s ceiling.
- **Public page:** static page reading the same published records.

Egress IP is fixed and added to the execution key's allowlist.

---

## 6. Credentials

| Name | Used by | Scope |
|---|---|---|
| `BANKR_KEY_READ` | analyst + snapshot process | read-only, Agent API off |
| `BANKR_KEY_EXEC` | treasurer process only | read-write, IP allowlist, low platform caps |
| `BANKR_LLM_KEY` | analyst + risk inference | gateway only, header `X-API-Key` |
| `RPC_4663` | chain reads | timeout + failover, block-pinned |
| `SIGNING_KEY` | treasurer process only | ed25519 private key; public key published |

Two separate Bankr accounts. The **execution wallet address is named explicitly
in config** and its balances are read via RPC. We never assume another account's
portfolio describes it.

---

## 7. Repo layout

```
src/
  adapters/       chain_4663, gecko, bankr_quote, bankr_exec, bankr_llm, cache
  core/           types, snapshot, universe, aggregate, gates, plan, valuation, books
  agents/         runner, analyst, risk, briefs/
  store/          schema.sql, orders, reports, journal, positions, publish
  treasurer/      mandate, intent, execute, reconcile
  surfaces/       x402/, page/, skill/
  run/            cycle, schedule, reconcile_startup
fixtures/         frozen snapshots + a known-answer accounting fixture
config/           universe allowlist, thresholds, mandate, models, cadence
probes/           throwaway scripts from Phase 0
research/         the seven discovery reports + findings.md
tests/
```

`core/` never imports `adapters/`. `agents/` and `core/` never import
`treasurer/` or `bankr_exec`.

---

## 8. Phases and units

Each phase has numbered units, three **playtime checkpoints** (marked ▶) where
you get a real artifact to look at, and an exit gate. At the end of each phase we
re-evaluate before detailing the next.

### Phase 0 — probes (no product code)

- **0.1** Repo skeleton, config loader, `.env`, secret redaction derived from the
  credential table.
- **0.2** Key permissions: Agent API and gateway toggles; which auth header each
  surface accepts.
- **0.3** Quote probe: `/wallet/swap-quote`, chain `robinhood`, USDG → one stock
  address. Record the full response and which fields actually appear.
- **0.4** ▶ **Chain probe:** read a Chainlink feed on 4663 at a pinned block.
  Confirm decimals, staleness fields, and whether the price already includes
  `uiMultiplier` by comparing against GeckoTerminal for the same asset.
- **0.5** Execution eligibility: attempt a minimal swap with the intended
  execution identity. Record the exact 403 body. Resolves to **pass / fail /
  unresolved**.
- **0.6** Credits probe: `GET /v1/credits` and `GET /v1/usage`.
- **0.7** ▶ **x402 probe:** deploy a trivial handler, time an unpaid and a paid
  call, capture `x-402-payer`, confirm USDC-on-Base is payable by a standard
  client.
- **0.8** Identity probe: issuer allowlist source, plus the beacon check against
  a good token and the fake GME.
- **0.9** LLM cost probe: one realistic analyst prompt; record tokens and
  latency; multiply into a cycle budget and a per-request price.
- **0.10** Idempotency and rate-limit behaviour: same key twice; deliberately
  exceed a cheap limit and record headers.
- **0.11** ▶ **`research/findings.md`:** every probe recorded as measured,
  documented or inferred, with pass/fail/unresolved and redacted bodies.

**Exit:** every probe resolved. 0.5 decides whether Phase 5 exists.

### Phase 1 — adapters and snapshot

- **1.1** Types module: Snapshot, Observation, AnalystReport, Proposal, Plan,
  Decision, Order, JournalEvent, Statement.
- **1.2** Universe: versioned issuer allowlist keyed by `(chain_id, address)`,
  provenance recorded, beacon check as secondary.
- **1.3** Chain adapter: block-pinned reads, feed staleness and pause rules,
  source time separate from fetch time.
- **1.4** Price cross-check: Chainlink as the accounting mark, GeckoTerminal as
  corroboration, divergence recorded.
- **1.5** Quote adapter (read-only): sized quotes with quote age.
- **1.6** ▶ **Snapshot builder:** merge, filter, hash. *Show: a real snapshot
  JSON, with per-asset tradeable/thin/excluded status and every timestamp
  visible.*
- **1.7** Held-but-untradeable handling: an asset out of the buy universe remains
  a holding with explicit valuation and execution status.
- **1.8** ▶ **Fixture generation and offline replay:** *Show: the same command
  producing a byte-identical snapshot from a fixture, network off.*
- **1.9** Adapter selftest attesting every address in the table against chain.
- **1.10** ▶ **Two-block skew test:** *Show: a deliberately inconsistent snapshot
  rejected with a named reason.*

**Exit:** hashed snapshot from live data; identical replay from fixture; bad
inputs rejected, not absorbed.

### Phase 2 — analyst contract and fan-out

- **2.1** ▶ **Report format designed first.** Sections, depth, how evidence cites
  snapshot fields, how a reader tells conviction from speculation. *Show: a
  hand-written model report, before any code, for you to approve.*
- **2.2** Output schema, hard validation, `NO_CALL`, address-scoped assertions.
- **2.3** Brief format: mandate, explicit scope boundaries, snapshot bytes,
  output schema, effort scaling.
- **2.4** Runner: bounded width, per-worker deadline, transport timeout, retry
  budget, pre-allocated result slots, per-worker fallback, partial-failure
  disclosure.
- **2.5** Token accounting per call, reconciled against `/v1/usage`.
- **2.6** ▶ **First real report:** *Show: an analyst running on a real snapshot,
  full output, cost and latency printed.*
- **2.7** Immutable report store, content-addressed.
- **2.8** ▶ **Failure drill:** *Show: one worker returning malformed JSON, one
  hanging, one abstaining, with the cycle completing and disclosing it.*

**Exit:** N analysts produce N valid reports from one snapshot id; failures are
visible and non-fatal; you have approved the report format.

### Phase 3 — aggregation, planning, risk

- **3.1** Aggregator as a total function: equation, confidence scale, horizon,
  quorum, cash weight, tie-break, rounding residual, all-abstain →
  no-rebalance.
- **3.2** ▶ **Aggregation table:** *Show: reports in, weights out, each analyst's
  contribution and the residual line visible.*
- **3.3** Planner: weights + reconciled holdings + reservations → sized orders
  with live quotes, quote age, fees, minimum proceeds, projected post-trade
  holdings.
- **3.4** Gate module: declarative array, fail-closed, named failures. Shared by
  risk and treasurer.
- **3.5** Risk agent: full reports + sized plan → verdict; fixed gates cannot be
  overridden by model text.
- **3.6** Context budget enforcement: veto if the full bundle does not fit.
- **3.7** Decision record: content hashes of snapshot, reports, config, proposal,
  plan, verdict. Ed25519 signature. `signed=false` never authorizes.
- **3.8** ▶ **A veto happening:** *Show: a cycle where divergence or depth trips a
  gate, the named reason, and execution refused.*
- **3.9** ▶ **Byte-stable replay:** *Show: the same decision record reproduced
  from recorded model outputs.*

**Exit:** a signed decision record; a veto that blocks; replay that matches.

### Phase 4 — treasurer (paper) and the journal

- **4.1** Mandate object: bounds, wallet, chain, allowed assets, cumulative
  budget, version, expiry, revocation.
- **4.2** Execution intent: exact ordered orders, fresh mandate validation,
  stable idempotency key.
- **4.3** Order state machine (§4) with durable writes before action.
- **4.4** Validating chokepoint before any submission, with regression vectors.
- **4.5** Paper executor satisfying the live interface.
- **4.6** Accounting journal: opening balances, transfers, fills, fees, gas,
  settlements, credit purchase and consumption, valuation marks. Chain events
  carry chain id, tx hash, log index, block hash, raw units, decimals.
- **4.7** Positions derived from journal; one valuation function.
- **4.8** ▶ **A full paper cycle:** *Show: snapshot → reports → weights → plan →
  verdict → paper fills → positions, end to end.*
- **4.9** Startup reconciliation of unresolved intents; single-owner lock.
- **4.10** ▶ **Crash drill:** *Show: the runner killed mid-submit, restarted, and
  resolving the order without double-spending.*
- **4.11** ▶ **Known-answer accounting fixture:** *Show: opening capital, a
  partial sale, an external transfer, a reverted transaction's gas, a settled and
  an unsettled payment, a credit purchase and consumption, all reconciling.*

**Exit:** a complete paper cycle, a survived crash drill, a reconciling fixture.

### Phase 5 — live execution *(opens only if probe 0.5 passed)*

- **5.1** Live executor behind the same interface.
- **5.2** Small buy **and** sell round trip with production-shaped permissions.
- **5.3** Receipt reconciliation, confirmation depth, `200 success:false`.
- **5.4** ▶ **A real trade:** *Show: the transaction on the explorer, and the same
  order in the ledger with its receipt.*
- **5.5** Access-expiry behaviour: pause new attempts, preserve holdings, expose
  remediation state.
- **5.6** ▶ **A real 403:** *Show: the exact body and which cause it maps to.*
- **5.7** ▶ **Live cycle:** *Show: a scheduled cycle executing a small real
  rebalance and booking it.*

**Exit:** both directions executed live and booked once.

### Phase 6 — books and attribution

- **6.1** Statement builder: income statement plus portfolio report, sealed
  inputs, versioned policy.
- **6.2** Reconciliation against independent wallet balances and provider
  settlement evidence; unresolved items shown, not absorbed.
- **6.3** Cost with `is_estimate` and pricing basis, reconciled to `/v1/usage`.
- **6.4** Funded contribution: realized P&L allocated once by executed weight,
  with a residual line.
- **6.5** Call accuracy: hit rate against a stated horizon and benchmark,
  labelled hypothetical, never mixed into fund profit.
- **6.6** ▶ **The first statement:** *Show: a real income statement and portfolio
  report from real cycles.*
- **6.7** ▶ **Attribution table:** *Show: two analysts recommending the same
  asset, credited once between them, residual reconciling.*
- **6.8** ▶ **Reconciliation exception:** *Show: a deliberate mismatch surfacing
  as an exception rather than disappearing.*

**Exit:** statements reconcile to balances and settlements within declared
rounding.

### Phase 7 — surfaces

- **7.1** Publisher: immutable record bytes, manifest, atomic `latest` pointer.
- **7.2** x402 handler: resolve `latest` to an immutable decision id **before**
  purchase; serve by id; no inference; no state.
- **7.3** Purchase binding: request, decision id, payer, price, asset, network,
  delivery status, settlement reference.
- **7.4** Revenue booked from settlement evidence, ingested separately from
  handler logs.
- **7.5** ▶ **A real purchase:** *Show: a client paying and receiving the record,
  and the payment appearing in the books.*
- **7.6** Public page reading the same published records.
- **7.7** ▶ **The page:** *Show: basket, weights, latest decision with reasoning,
  veto history, statements.*
- **7.8** Skill manifest so other Bankr agents can call it.
- **7.9** ▶ **Recovery drill:** *Show: a response dropped after settlement, and
  the buyer retrieving the paid record by id without paying again.*

**Exit:** an agent pays and receives; the page shows the same record; revenue
reconciles.

### Phase 8 — schedule, demo, submission

- **8.1** Scheduler: cheap script tick, agent turn only when inputs changed,
  overlap fencing, no permission bypass.
- **8.2** Kill switch that stops submissions but not reconciliation.
- **8.3** ▶ **Unattended run:** *Show: several cycles with no hands on the
  keyboard, including a no-rebalance cycle.*
- **8.4** Demo script running from fixtures with a live section.
- **8.5** ▶ **Dry run of the demo**, timed.
- **8.6** Submission: architecture note, limitations section, the six judging
  criteria addressed.
- **8.7** ▶ **Final read-through** of the page and books as a judge would see
  them.

---

## 9. Preliminary tests

Written alongside the code they cover, runnable offline.

**Snapshot:** identical inputs produce an identical hash; mixed blocks rejected;
stale or paused feeds excluded and labelled; a replayed old HTTP body with a
fresh fetch timestamp rejected; a held asset excluded from trading remains in the
book.

**Identity:** an unlisted clone with a matching ticker and beacon is refused; a
correct token on the wrong chain is refused; an address change requires explicit
version acceptance.

**Analyst contract:** valid reports validate; malformed output retries once then
records a failed worker; `NO_CALL` accepted; out-of-scope assertions rejected;
all analysts provably received the same snapshot id; a hung worker hits its
deadline and the cycle still terminates.

**Aggregator:** deterministic and byte-stable; all-abstain yields no-rebalance
and preserves holdings; quorum shortfall does not execute; duplicate reports
counted once; weights and residual sum correctly.

**Gates and risk:** fails closed on the first failure and names it; unknown
blocks; quote/feed divergence vetoes; model text cannot override a fixed gate; an
over-budget report bundle vetoes rather than summarizing.

**Treasurer:** a plan exceeding mandate bounds is refused; a plan whose hash does
not match its approval is refused; an invalid order fails validation before any
signing path; kill during submit leaves exactly one economic order; `409`,
`200 success:false`, and a delayed receipt each resolve to the right state; two
runners cannot both spend.

**Books:** the known-answer fixture reconciles; contributions never become
income; expense recognized once; valuation correct with a loose remainder;
attribution allocates realized P&L once with a reconciling residual; published
historical scores cannot be rewritten by later information.

**Structural:** the deployed analyst process cannot read execution credentials or
submit a swap by raw HTTP; no declared credential appears in any log; live
selftest attests every address.

---

## 10. Cost and quota budget

Analysts and risk run on the LLM gateway, which is credit-metered, so the Agent
API's 100/day figure does not bound fan-out. Budgets are per service: gateway
credits, wallet and quote request rates, RPC calls, x402 platform requests. Each
cycle declares a token budget covering analysts, retries, risk and the context
bundle. Insufficient inference capacity fails the cycle closed rather than
half-running it. Auto top-up, if enabled, is spend authority and stays under the
mandate.

---

## 11. Decisions already made

- **Chainlink marks the book; quotes size the trade.** Divergence past a
  threshold is a veto condition, not a silent reconciliation.
- **Value is computed in exactly one place**, tested against a position with a
  loose remainder.
- **The paid endpoint prices in USDC on Base**, because the standard client's
  network enum excludes 4663. The fund trades on 4663; the research sells on
  Base.
- **No-rebalance preserves holdings.** It never means liquidate.
- **Published, reconciled books.** Not "audited."

---

## 12. Open questions

- Is an eligible execution operator available? This decides whether Phase 5
  exists.
- How many of the ~190 tickers are actually tradeable at our size?
- Do we launch a token, and would a stock-paired launch with quote-only fees make
  the treasury's own income arrive in equity?
- Cadence: frequent enough to look alive, cheap enough to sustain.

---

## 13. Stated limitations

Published with the project, not hidden.

- No independent audit. Books are internally reconciled against wallet balances
  and settlement evidence, and signed for provenance only.
- Reorg handling is limited to a confirmation depth. A receipt becoming
  noncanonical surfaces as a reconciliation exception, not an automatic
  correction.
- No archive RPC and no sequencer-uptime attestation. We require demonstrated
  chain progress and halt on uncertainty.
- Single runner, single SQLite file, no high availability, no automated backup.
- One signing key, published, rotated manually. No trust chain.
- Refunds for paid-but-undelivered records are manual, though retrieval by
  decision id is automatic.
- Call accuracy is hypothetical by construction and never enters fund profit.
- Reporting entity is the execution wallet plus one Base receiving address. No
  wider consolidation.
