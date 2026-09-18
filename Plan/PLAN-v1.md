# Build plan

An onchain fund for tokenized stocks on Robinhood Chain, managed by a
supervisor/worker agent system that publishes its own audited books and sells
its research to other agents.

Status: planning. Nothing built. This document is expected to change as probes
return real answers.

---

## 1. What we're building, in one paragraph

A fund holds a basket of tokenized equities on Robinhood Chain (chain 4663).
Each cycle, a set of read-only analyst agents receives one frozen market
snapshot and returns structured reports. A deterministic aggregator turns those
reports into proposed weights. A risk agent reads every report in full and can
veto. A treasurer — the only component in the system that can sign anything —
converts approved weights into trades and executes them. An accountability layer
then publishes an income statement and a portfolio report: x402 revenue, LLM
cost, P&L, and which analyst's calls made or lost money. The signed decision
record is sold to other agents over an x402 endpoint, and shown to humans on a
public page.

The one-line pitch: **a fund that shows its work.**

Not to be called a swarm in the architecture docs. It is a supervisor with
read-only workers and a single writer, which is the pattern the 2026 literature
actually endorses. "Swarm" is marketing vocabulary only.

---

## 2. Architecture

```
                  ┌─────────────────────┐
                  │  Snapshot builder    │  ← adapters (read-only)
                  └──────────┬──────────┘
                             │  snapshot_id (immutable, hashed)
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
          Analyst 1      Analyst 2      Analyst N     (read-only, parallel,
              │              │              │          bounded width)
              └──────────────┼──────────────┘
                             ▼
                    Report store (full text)
                             │  condensed summaries + ids
                             ▼
                   Aggregator (deterministic)
                             │  proposed weights
                             ▼
                  Risk agent (sees ALL reports)
                             │  approve / veto + reason
                             ▼
                 Decision record → signed envelope
                             │
              ┌──────────────┴──────────────┐
              ▼                             ▼
         Treasurer (ONLY writer)      x402 endpoint / page
              │
              ▼
         Trade ledger → Books
```

### Invariants

These are structural, not policy. Each should be impossible to violate by
accident, not merely discouraged.

1. **One writer.** Only the treasurer module imports a signing path. The
   analyst and snapshot modules must not be able to import it at all — enforced
   by separate entrypoints, the way AgentOS separates `lp_read` / `lp_write` /
   `ratchet`.
2. **One frozen snapshot per cycle.** Every analyst receives the same immutable
   object, addressed by a content hash. Analysts never fetch their own data.
3. **Full reports reach the risk agent.** Not summaries. This is the shared-
   context checkpoint that prevents analysts' conflicting implicit assumptions
   from reaching a trade.
4. **Three-valued verification.** Every check is true / false / null, where null
   means "could not determine," not "false." A network fault is not evidence
   about a contract.
5. **`NO_CALL` is a valid analyst output.** An analyst forced to always produce
   conviction will manufacture it.
6. **Everything stochastic is seeded.** Two runs of one config must be
   comparable.
7. **Assets are pinned by address, never ticker.** 4663 is permissionless and
   has impersonator tokens (there is a fake GME).

---

## 3. What we take from each repo

| Source | What we take | Where it lands |
|---|---|---|
| **AgentOS** (`agent-os`) | Chainlink feed reads on 4663 (`latestRoundData`, `0xfeaf968c`); GeckoTerminal `robinhood` slug; Uniswap v4 addresses on 4663; USDG address + decimals; EIP-1967 beacon-slot impersonator check | Adapters |
| AgentOS | Mandate authorization: human approves a plan hash once with declared bounds; unattended runner replays only against plans re-proven against fresh chain state | Treasurer |
| AgentOS | Three entrypoints, not three flags (read path never imports signing) | Repo layout |
| AgentOS | Three-valued verification; partial-failure disclosure flag on fan-in | Analyst runner, risk agent |
| AgentOS | Scheduler: prefer a cheap script tick over an agent turn for cycles that are usually no-ops | Cycle runner |
| **aero-stock-lp** | Declarative gate array `{name, pass, value, limit}`, fail-closed on first miss | Risk agent |
| aero-stock-lp | Validating `tx()` chokepoint with regression vectors before any transaction | Treasurer |
| aero-stock-lp | `selftest --live` attesting the address table against chain | Adapters, CI |
| aero-stock-lp | `{ok, ..., report, next}` output contract carrying computed values forward | Stage outputs |
| **MiroShark** | `signed_result.py` — canonical JSON + signed envelope with `schema_version`, graceful `signed=false` | Decision record |
| MiroShark | `run_summary.py` / `cost_service.py` — per-call LLM cost by caller and phase, with `is_estimate` / `pricing_basis` honesty flags | Books |
| MiroShark | Polymarket `trade.sql` / `position.sql` — append-only trade ledger | Ledger |
| MiroShark | `signal_service.py` style — pure, tie-broken, reproducible derivation with no LLM | Aggregator |
| MiroShark | Bi-temporal `valid_at` / `invalid_at` edges | Analyst track record |
| MiroShark | ThreadPoolExecutor fan-out with pre-allocated result slots and per-worker fallback | Analyst runner |
| **Bankr skills** | Explicit null output per skill (`NO_PICK`, "silence is correct") | Analyst contract |
| Bankr skills | x402 client preflight: validate version, scheme, network, asset, `payTo`, timeout, amount before paying | x402 client |
| **openclaude** | Descriptor-derived secret redaction (adding a credential cannot create an unredacted path) | Config |
| openclaude | `validateInput()` strictly before any confirmation or signing step | Treasurer |

### Explicitly not copied

- Substring matching on base URLs to route credentials (openclaude) — exact
  hostname only.
- Flat-percentage slippage with no price-impact term, and zero minimums on
  liquidity operations (aero-stock-lp).
- LLM-computed realized P&L (aero-stock-lp) — arithmetic is code's job.
- Marking the book at pool spot (aero-stock-lp) — see §5.
- Knowledge graph as the home for position history (MiroShark) — its write path
  is prose→NER, so numbers degrade on ingest.
- Unbounded fan-out width and permission-bypassing scheduled jobs (AgentOS
  defaults).
- Unrotated append-only event logs read in full on every request (MiroShark).

---

## 4. Verified facts the build depends on

**Execution.** `POST /wallet/swap-quote` then `POST /wallet/swap`. Chain
`"robinhood"`. Contract addresses, not tickers. `minBuyAmount` and
`idempotencyKey` required. The route handles USDG itself, so we can fund from
ETH or USDG in one call. Tokenized stocks have no AMM pool — they're quoted by
RFQ makers and settle against USDG.

**Gating.** Quotes are ungated and work with a read-only key. Execution requires
location verification and is unavailable in the US/UK. A failed execution
returns 403 with seven possible causes behind one status, so the error message
must be parsed and surfaced.

**Slippage.** Our `slippageBps` shapes `minBuyAmount`, but the execution re-quote
on tokenized-stock legs is clamped to 200 bps regardless.

**Price impact.** Two layers: venue refusal is 400; our own wallet's limit
rejecting the fresh execution quote is 403. Execution gates on `swapImpactBps`;
`priceImpactBps` is display-only.

**Platform guardrails.** $500/24h and $500/tx by default, 15% price-impact
limit, fail-closed when USD pricing is unavailable. Our own caps sit on top.

**LLM.** `llm.bankr.bot` authenticates with `X-API-Key` (Bearer alongside it is
harmless but insufficient on at least one client path). Credit balance is not
programmatically readable, so our cost figures are our own token counts and must
be labelled as estimates.

**Rate limits.** Agent API is 100 messages/day standard on a rolling window. No
code in any repo we read handles `Retry-After`. We build backoff ourselves and
cap fan-out width.

**x402.** Handlers are bare `Request → Response`; the platform builds the 402
challenge and settles. First 1,000 requests/month are fee-free. 30-second
handler ceiling. `x402-fetch`'s network enum excludes 4663, so **our endpoint is
priced in USDC on Base**, not USDG. The handler serves the latest cached
decision record; the cycle runs on its own schedule.

**Chain data (4663).** Chainlink feeds exist for Robinhood Stock Tokens and the
feed price already incorporates `uiMultiplier()` — do not apply it twice.
GeckoTerminal's network slug is `robinhood`. Uniswap v4 is deployed; the v3
factory address is *not* canonical. USDG is `0x5fc5…d168`, 18 decimals.
Tokenized stocks are 18 decimals on 4663 (Base B20 equities are 8).

---

## 5. Two decisions made now

**Mark the book against Chainlink, not pool spot.** Pool spot is what the market
will pay right now and is the right input for execution sizing. Chainlink tracks
the underlying equity, which is what a share is worth. Marking to a thin pool
means our statements swing on someone else's slippage, and it is the more
forgeable of the two on a permissionless chain. The quote is used for execution;
the feed is used for the books; **divergence between them past a threshold is
itself a veto condition.**

**Value is computed in exactly one place.** aero-stock-lp memorialized a P&L bug
in its docs and the fix never reached the per-position path. Our accounting has
one valuation function, and a test asserts it against a position with a loose
remainder balance.

---

## 6. Repo layout

```
src/
  adapters/          all external I/O, one file per source, returns plain data
    chain_4663.py      RPC reads: Chainlink feeds, token metadata, beacon check
    gecko.py           USD prices via the "robinhood" network slug
    bankr_quote.py     /wallet/swap-quote  (READ ONLY — no signing import)
    bankr_exec.py      /wallet/swap        (the ONLY signing path)
    bankr_llm.py       llm.bankr.bot client: backoff, token accounting
    cache.py           timestamped snapshots to disk
  core/                pure logic, no network, fully testable
    types.py           Snapshot, AnalystReport, Proposal, Decision, Trade, Statement
    snapshot.py        build + freeze + hash
    universe.py        tradeability filter (depth, staleness, verification)
    aggregate.py       reports → proposed weights (deterministic, tie-broken)
    gates.py           the risk gate array
    valuation.py       the one valuation function
    books.py           income statement + portfolio report
  agents/
    runner.py          bounded parallel fan-out, per-worker fallback
    analyst.py         prompt + parse + validate
    risk.py            prompt + gate evaluation
    briefs/            one prompt file per role, versioned
  ledger/
    schema.sql         append-only trades, derived positions
    store.py
  treasurer/
    plan.py            weights → ordered trade list, sized from quotes
    mandate.py         plan hash + declared bounds + replay check
    execute.py         validating chokepoint → bankr_exec
  surfaces/
    x402/              the paid handler
    page/              the public page
    skill/             SKILL.md
  run/
    cycle.py           snapshot → analysts → aggregate → risk → execute → books
    schedule.py
fixtures/              frozen snapshots for offline demo + tests
config/                tickers, thresholds, risk rules, models, cadence
research/              the seven discovery reports
tests/
```

**The rule that keeps it legible:** `core/` never imports from `adapters/`, and
nothing under `agents/` or `core/` imports `treasurer/` or `bankr_exec`.

---

## 7. Data flow, hop by hop

1. **Adapters** read: universe (addresses + verification), Chainlink prices,
   GeckoTerminal USD, wallet balances, Bankr fee/LLM data. Each response is
   validated at the boundary and cached with a code-generated timestamp (never
   agent-reported).
2. **Snapshot builder** merges them into one object, applies the tradeability
   filter, hashes it. Output: `snapshot_id`.
3. **Analyst runner** fans out N analysts, each with a brief: mandate, scope
   boundaries, the snapshot (by id), and an explicit output schema. Full
   reasoning is written to the report store; a condensed summary plus a
   reference id comes back.
4. **Aggregator** — deterministic code — turns validated reports into proposed
   weights. Ties broken by a documented rule. No LLM.
5. **Risk agent** receives the proposed weights *and every full report*.
   Evaluates the gate array, may veto with a named reason.
6. **Decision record** assembles: snapshot id, report ids, proposed weights,
   gate results, verdict, token cost. Canonical JSON, signed envelope.
7. **Treasurer** converts approved weights into an ordered trade list, sizes
   each from a live quote, checks the plan against its mandate bounds,
   validates, then executes with an idempotency key.
8. **Ledger** appends trades; positions derive from trades.
9. **Books** compute revenue, cost, P&L, attribution; publish.
10. **Surfaces** serve the latest signed record and the page.

---

## 8. Credentials

| Name | What for | Scope |
|---|---|---|
| `BANKR_API_KEY_READ` | quotes, market data, fee reads | read-only, Agent API off |
| `BANKR_API_KEY_EXEC` | the treasurer's swaps | read-write, IP allowlist, recipient allowlist, low platform caps |
| `BANKR_LLM_KEY` | `llm.bankr.bot`, header `X-API-Key` | gateway only |
| `RPC_4663` | Chainlink + token reads | public RPC, with timeout and failover |
| `SIGNING_SECRET` | decision-record envelope | never leaves the signer |

Two separate Bankr accounts, not one key with two roles — a compromised analyst
path must not be able to trade. Redaction is derived from this table, so adding
a credential cannot create an unredacted log path.

---

## 9. Build phases

Each phase ends in something demonstrable. Do not start a phase before the
previous one's exit condition is met.

**Phase 0 — probes (§10).** No product code. Answer the empirical questions.
Exit: every probe has a recorded answer in `research/findings.md`.

**Phase 1 — adapters + snapshot.** Universe loading with address verification,
Chainlink prices, GeckoTerminal cross-check, quote reads, disk cache, fixture
generation. Exit: `make snapshot` produces a hashed snapshot from live data, and
the same command replays a fixture offline.

**Phase 2 — analysts + contract.** Brief format, output schema with hard
validation, `NO_CALL` path, bounded fan-out, per-worker fallback, token
accounting per call. Exit: N analysts run against a fixture and produce N valid
reports, with one deliberately broken model response handled cleanly.

**Phase 3 — aggregator + risk gate.** Deterministic weights, the gate array,
veto with reason, decision record assembled and signed. Exit: a signed decision
record on disk, reproducible byte-for-byte from the same snapshot and reports.

**Phase 4 — treasurer (paper).** Trade planning, sizing from live quotes,
mandate bounds, validating chokepoint, ledger writes. Exit: a full cycle ends in
paper fills and a correct ledger.

**Phase 5 — treasurer (live).** Same interface, real execution, small size.
Exit: at least one real on-chain trade on 4663, with its transaction in the
ledger and the 403 path exercised and understood.

**Phase 6 — books.** Revenue, cost with estimate flags, P&L against Chainlink,
per-analyst attribution. Exit: a statement covering real cycles.

**Phase 7 — surfaces.** x402 handler serving the cached signed record, public
page, skill. Exit: an agent pays and receives the record; the page is live.

**Phase 8 — cycle runner + demo.** Schedule, resumability, kill switch, demo
script running entirely from fixtures.

Phases 1–4 are the critical path. If time runs short, 5 and 7 are what make it a
product; 6 is what makes it ours.

---

## 10. Probes to run first

Each is a throwaway script under `probes/`, with its answer recorded in
`research/findings.md`. Several could invalidate a design choice, so they come
before any product code.

1. **Key permissions.** `bankr whoami`; confirm Agent API and LLM Gateway
   toggles; confirm which header each surface accepts (`X-API-Key` vs Bearer).
2. **Quote from a read-only key, from here.** `POST /wallet/swap-quote`,
   `fromChain: "robinhood"`, USDG → a stock address. Record the full response
   shape and which fields are actually present.
3. **Execution gate.** Attempt a minimal swap. Capture the exact 403 body and
   which of the seven causes is distinguishable from it.
4. **Chainlink on 4663.** Read `latestRoundData` for one stock feed over RPC.
   Confirm decimals, staleness fields, and that the price already includes
   `uiMultiplier` (compare against GeckoTerminal for the same asset).
5. **Impersonator check.** Run the EIP-1967 beacon-slot check against a known
   good token and against the fake GME. Confirm it distinguishes them.
6. **x402 round trip.** Deploy a trivial handler; time an unpaid call and a paid
   call end to end. Confirm the 30-second ceiling is not a problem for a cached
   response, and capture what `x-402-payer` looks like.
7. **x402 pricing.** Confirm a USDC-on-Base endpoint is payable by a standard
   client, and record what happens if priced in USDG on 4663.
8. **LLM cost per analyst call.** One realistic analyst prompt against a real
   snapshot; record input/output tokens and latency. Multiply out to a cycle
   budget and a per-request price for the endpoint.
9. **Rate-limit behaviour.** Deliberately exceed a limit on a cheap endpoint;
   record the response body, headers, and whether `Retry-After` is present.
10. **Idempotency.** Submit the same swap twice with the same
    `idempotencyKey`; record whether the second is rejected, deduped, or filled.

Probes 2, 3 and 4 are the ones that could force a redesign. Run them first.

---

## 11. Preliminary tests

Written alongside Phase 1–4 code, all runnable offline against fixtures.

**Snapshot**
- Same inputs produce the same hash; any field change produces a different one.
- A stale price is excluded, not silently used.
- An unverified token address never enters the universe.
- A failed adapter yields `null` (unknown), never `false` (disproven).

**Analyst contract**
- A valid report parses and validates.
- Malformed JSON is retried once, then recorded as a failed worker — the cycle
  continues with a partial-failure flag.
- `NO_CALL` is accepted and excluded from weighting.
- A report referencing a ticker not in its scope is rejected.
- All N analysts provably received the same `snapshot_id`.

**Aggregator**
- Deterministic: same reports, same weights, byte-identical.
- Ties broken by the documented rule.
- Weights sum to 1 within tolerance; no negative weights.
- One missing analyst does not silently reweight the rest without disclosure.

**Risk gate**
- Fails closed on the first failing gate, and names it.
- A quote/feed divergence past threshold vetoes.
- A proposal breaching max position, min liquidity, turnover, or cash floor is
  vetoed.
- A veto blocks execution — asserted by the treasurer refusing an unapproved
  decision.

**Treasurer**
- Trade list never exceeds mandate bounds.
- A plan whose hash doesn't match its approval is refused.
- An invalid trade object fails validation before any signing call is reached.
- Paper and live executors satisfy the same interface against the same fixture.

**Ledger and books**
- Positions derived from trades match an independently computed balance.
- Valuation is correct for a position holding a loose remainder.
- Cost figures carry `is_estimate` and a pricing basis.
- Revenue, cost and P&L reconcile to the trade and event logs.

**Structural**
- An import test asserting that `core/` and `agents/` cannot reach the signing
  path.
- A redaction test asserting no declared credential appears in any log output.
- A live selftest attesting every address in the table against chain.

---

## 12. Open questions

- Does execution need a non-US operator, and is one available on the team?
- Actual liquidity: how many of the ~190 tickers are tradeable enough to hold?
- Do we launch a token, and if so, does a stock-paired launch with quote-only
  fees make the treasury's income arrive in equity?
- Cycle cadence: what's frequent enough to look alive without burning quota?
