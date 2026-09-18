# Phase 0 and Phase 1 — detailed

Unit-level detail for the first two phases. Every unit states its goal, what
gets built, the artifact it leaves behind, its done condition, and the risk that
could derail it.

Conventions:
- Probes live in `probes/` and are throwaway. Nothing in `src/` depends on them.
- Every probe writes its result to `research/findings.md` marked **measured**,
  **documented**, or **inferred**, with redacted request and response bodies and
  a timestamp.
- A probe that cannot reach a verdict is **unresolved**. Unresolved is a valid
  outcome and is never rounded up to pass.

---

# Phase 0 — probes

**Purpose:** replace assumptions with recorded answers. No product code. Nothing
here is built to last.

**Estimated:** half a day to a day, depending on how much is blocked on funding
the wallet and on eligibility.

---

### 0.1 Skeleton and redaction

**Goal:** a repo we can work in, where a credential cannot accidentally be
logged.

**Build:** directory skeleton per `PLAN.md` §7 (empty modules are fine), a config
loader reading `.env`, and a log filter whose denylist is **derived** from the
credential table rather than hand-written, so adding a credential cannot create
an unredacted path.

**Artifact:** `config/`, `.env.example`, a redaction unit test.

**Done when:** a test that logs a string containing each declared credential
value shows it masked.

**Risk:** low.

---

### 0.2 Key permissions and auth headers

**Goal:** know exactly which header each Bankr surface accepts, and which
toggles are on.

**Build:** `probes/keys.py`. Call `bankr whoami` equivalent, then hit one read
endpoint on each surface (wallet, agent, gateway) with `X-API-Key`, then again
with `Authorization: Bearer`.

**Artifact:** a table in findings: surface × header × result.

**Done when:** every surface has a confirmed working header, and the Agent API
and LLM Gateway toggles are confirmed on for the right keys.

**Risk:** the CLI-minted key has Agent API off by default. Fix in the web console
before assuming a failure is a bug.

---

### 0.3 Quote shape

**Goal:** the real response shape for a stock quote on 4663, not the documented
one.

**Build:** `probes/quote.py`. `POST /wallet/swap-quote`, `fromChain: "robinhood"`,
USDG → one stock contract address, small size. Then repeat at a larger size and
for a second stock.

**Artifact:** full redacted responses in findings, plus a list of which fields
were actually present versus documented-but-absent.

**Done when:** we can state which fields we may rely on. Documented guarantees
only three: `from`, `to`, `minBuyAmount`.

**Risk:** a stock with no quote returns an error that looks like a bug. Try
several tickers before concluding anything.

---

### 0.4 ▶ Chainlink and the multiplier

**Goal:** settle how the accounting mark is computed.

**Build:** `probes/feed.py`. Read `latestRoundData` for five stock feeds at one
pinned block over `RPC_4663`. Record answer, decimals, `updatedAt`, and round id.
Fetch the same five from GeckoTerminal using the `robinhood` network slug.
Compute divergence. Then read `uiMultiplier()` on each token and check whether
applying it changes agreement.

**Artifact:** the comparison table, plus a written conclusion: is the feed price
already multiplier-adjusted?

**Done when:** the table exists and the multiplier question has a measured
answer, not an inferred one.

**Risk:** the highest-value unit in Phase 0. If the two sources disagree wildly,
the marking decision needs revisiting before Phase 1 is designed. Also watch for
feeds that return a stale `updatedAt` outside market hours; that's expected, and
it's what the staleness rule in 1.3 is for.

**Checkpoint:** you see the table. Judge whether the two sources agree closely
enough to trust either one, and whether the divergence threshold we chose for a
veto is realistic.

---

### 0.5 Execution eligibility

**Goal:** the binary that decides whether Phase 5 exists.

**Build:** `probes/execute.py`. With the **intended execution identity and
production-shaped permissions**, attempt the smallest viable swap. Capture the
full response body, status, and headers.

**Artifact:** the exact 403 body (or the success), recorded verbatim, and a
mapping attempt against the seven documented causes.

**Done when:** the result is recorded as **pass**, **fail**, or **unresolved**,
with the evidence.

**Risk:** a quote succeeding proves nothing about execution. A pass here must be
an actual fill, not an absence of error. If this is fail or unresolved, say so
immediately; the plan branches on it.

---

### 0.6 Credits and usage

**Goal:** confirm cost can be reconciled rather than only estimated.

**Build:** `probes/credits.py`. `GET /v1/credits` and `GET /v1/usage` with the
gateway key. Record the field set of each.

**Artifact:** both response shapes, and a note on granularity: can usage be
attributed to a single request, or only aggregated?

**Done when:** we know what reconciliation evidence is available.

**Risk:** if usage is only aggregate, per-analyst cost stays an estimate and the
books must say so.

---

### 0.7 ▶ x402 round trip

**Goal:** know the real timing and payment behaviour before designing around it.

**Build:** reuse the already-deployed `stockwatch` handler or deploy a trivial
one. Time: an unpaid call (402), a paid call (cold), a paid call (warm). Print
`x-402-payer`. Price it in USDC on Base and pay with a standard client.

**Artifact:** three timings, the payer header, the 402 challenge body.

**Done when:** we can state the end-to-end latency of a paid call and confirm a
standard client can pay us.

**Risk:** the handler must not do work. If cold start alone eats seconds, the
cached-record design is confirmed necessary rather than merely prudent.

**Checkpoint:** you see the timings and the payment landing. Judge whether this
feels like a product an agent would call repeatedly, and what a fair price is.

---

### 0.8 Asset identity

**Goal:** establish how we know a token is the real one.

**Build:** `probes/identity.py`. Find the issuer's canonical asset list (Robinhood
publishes deployments per chain). Record it as a snapshot with provenance. Then
run the EIP-1967 beacon-slot check against a known-good token and the known fake
GME, and record whether it distinguishes them.

**Artifact:** the allowlist snapshot file, plus the beacon check result for both
tokens.

**Done when:** we have a pinned list keyed by `(chain_id, address)` with a
recorded source, and we know what the beacon check adds on top.

**Risk:** the beacon check is a consistency test, not proof of issuer. Do not let
a pass here become the authority.

---

### 0.9 Analyst cost

**Goal:** a real number for the cycle budget and the endpoint price.

**Build:** `probes/llm_cost.py`. Take one realistic analyst prompt (the hand
format from 2.1 can be sketched roughly here) with a real snapshot embedded. Run
it against the intended model. Record input tokens, output tokens, latency, and
cost.

**Artifact:** one measured call, multiplied out: cost per analyst, per cycle at N
analysts, per day at the intended cadence.

**Done when:** the numbers exist and are in findings.

**Risk:** the prompt here is a rough draft, so treat the number as a floor. Risk
inference and retries are additional.

---

### 0.10 Idempotency and rate limits

**Goal:** know what a retry actually does before relying on one.

**Build:** `probes/idempotency.py`. Submit the same swap payload twice with the
same key (paper-safe size, or on a non-stock asset if execution is blocked).
Record whether the second is rejected, deduped, or filled. Separately, exceed a
cheap endpoint's limit and record the status, body, and whether `Retry-After` is
present.

**Artifact:** both behaviours recorded verbatim.

**Done when:** we know whether same-key replay is safe, and what backoff signal
we get.

**Risk:** if execution is blocked, this is partially unresolved. Record it as
such rather than assuming documented behaviour.

---

### 0.11 ▶ findings.md

**Goal:** one page that the rest of the build trusts.

**Build:** consolidate every probe: question, method, result, confidence
(measured / documented / inferred), verdict (pass / fail / unresolved), and any
plan change it forces.

**Artifact:** `research/findings.md`.

**Done when:** no probe is missing and no result is stated with more confidence
than it earned.

**Checkpoint:** you read the page. Judge which assumptions died, and decide
whether Phase 5 is in or out.

**Phase 0 exit:** every probe resolved; findings written; the Phase 5 branch
decided.

---

# Phase 1 — adapters and snapshot

**Purpose:** turn a permissionless chain and three data sources into one frozen,
hashed, trustworthy object that an analyst can reason over and a judge can
verify.

**Estimated:** a day to a day and a half.

---

### 1.1 Types

**Goal:** the contracts everything imports, defined once.

**Build:** `core/types.py`. `Observation` (value, source, source_time,
fetch_time, block), `Asset`, `Snapshot`, `AnalystReport`, `Proposal`, `Plan`,
`Decision`, `Order`, `JournalEvent`, `Statement`. Every numeric field carries
units and decimals explicitly. Verification fields are three-valued: true /
false / null.

**Artifact:** one module, no imports from `adapters/`.

**Done when:** the types compile and a round-trip serialization test passes with
stable numeric encoding.

**Risk:** getting `Observation` wrong makes every later timestamp argument
harder. Source time and fetch time are separate fields, always.

---

### 1.2 Universe allowlist

**Goal:** an asset can only enter the system if we know it's the real one.

**Build:** `core/universe.py` plus `config/universe.json`. The allowlist from
probe 0.8, keyed by `(chain_id, address)`, with issuer source, snapshot date, and
a version. A loader that refuses unknown addresses. The beacon check wired as a
secondary consistency flag, not the authority.

**Artifact:** the versioned allowlist file and a loader.

**Done when:** an address outside the list cannot enter a snapshot, and a version
bump requires an explicit config change.

**Risk:** the temptation to resolve by ticker for convenience. Don't; that's how
the fake GME gets bought.

---

### 1.3 Chain adapter

**Goal:** reads that are internally consistent and honest about age.

**Build:** `adapters/chain_4663.py`. Pin one block per snapshot and read
everything at it. Multicall where possible. Per-feed rules: max age, market
session awareness, paused-oracle detection. Explicit request timeouts and RPC
failover that advances on hang as well as rejection. Return `Observation`s, never
bare numbers.

**Artifact:** a module that, given a block, returns prices and balances with full
provenance.

**Done when:** two consecutive calls at the same block return identical values,
and a stale feed returns a labelled observation rather than a silent number.

**Risk:** public RPC with no timeout is the exact failure `aero-stock-lp` has. Set
timeouts first, not later.

---

### 1.4 Price cross-check

**Goal:** two independent sources, one of which marks the book.

**Build:** `adapters/gecko.py` for the `robinhood` slug. `core/valuation.py`
computing the mark from Chainlink (raw units × feed, multiplier handled per probe
0.4) and recording divergence against GeckoTerminal as a field on the asset.

**Artifact:** per-asset mark, corroboration, divergence in basis points.

**Done when:** the mark is computed in exactly one function, and the divergence
field is populated for every asset.

**Risk:** applying `uiMultiplier` twice. Probe 0.4 settles this; the code should
carry a comment pointing at the finding.

---

### 1.5 Quote adapter

**Goal:** know what we could actually trade, at size.

**Build:** `adapters/bankr_quote.py`, read-only key only, no signing import.
Request quotes at the intended size, not a token size. Record quote age, fees,
and the impact fields when present. Handle absent fields as null, not zero.

**Artifact:** sized quotes attached to each asset.

**Done when:** a quote at intended size succeeds or fails explicitly, and a
missing impact figure is null rather than assumed safe.

**Risk:** a small quote passing tells you nothing about a real position. Size the
probe to the real intended order.

---

### 1.6 ▶ Snapshot builder

**Goal:** the frozen object.

**Build:** `core/snapshot.py`. Merge observations (already fetched; no network in
`core/`), apply the tradeability filter (depth or quote success, staleness,
verification status), assign each asset a status, canonicalize, hash.

**Artifact:** a real snapshot JSON on disk plus its hash.

**Done when:** identical inputs produce an identical hash and any field change
produces a different one.

**Checkpoint:** you read a real snapshot. Judge whether an analyst could say
anything intelligent from it. If not, we add data sources before writing a single
analyst, because the report is the product.

---

### 1.7 Held-but-untradeable

**Goal:** an asset leaving the buy universe must not leave the book.

**Build:** separate `universe_status` (can we buy it) from `holding_status` (do
we own it, what's it worth, can we exit). A holding excluded from trading is
valued and flagged, never dropped.

**Artifact:** both statuses on every asset.

**Done when:** a test removes an asset from the allowlist and the position
survives with a labelled status.

**Risk:** this is the quiet bug that makes a portfolio report lie.

---

### 1.8 ▶ Fixtures and replay

**Goal:** the demo never depends on the network.

**Build:** a fixture writer that captures raw source responses (not just the
normalized snapshot), and a replay mode that rebuilds from them.

**Artifact:** `fixtures/` with at least one full capture.

**Done when:** live and replayed builds produce identical hashes with the network
disabled.

**Checkpoint:** you watch it build offline. Judge how much of the demo should run
from fixtures versus live.

---

### 1.9 Address selftest

**Goal:** the address table is attested, not trusted.

**Build:** a `--live` selftest that checks every address in config against chain:
it exists, has expected decimals, matches its expected feed, and passes the
beacon consistency check.

**Artifact:** a pass/fail report per address.

**Done when:** it runs green, and flipping one address to a wrong value turns it
red.

---

### 1.10 ▶ Skew rejection

**Goal:** prove the snapshot refuses inconsistency.

**Build:** tests that construct: observations from two different blocks, an
offchain body with an old source time and a fresh fetch time, a paused feed, and
a market-closed feed.

**Artifact:** four named rejections.

**Done when:** each is refused by name, and the refusal reaches the caller rather
than being logged and swallowed.

**Checkpoint:** you see the refusals. Judge whether the strictness is right, or
whether it will block every cycle on a weekend.

**Phase 1 exit:** a hashed snapshot from live data; byte-identical replay from
fixture; bad inputs rejected by name; every address attested.

---

## Re-evaluation gate

At the end of Phase 1, before detailing Phase 2, we answer:

1. Is the snapshot rich enough for an analyst to be worth paying for?
2. Did any probe finding change the marking, veto, or universe decisions?
3. Is Phase 5 in or out, and does that change what the demo is?
4. What did Phases 0 and 1 actually cost in time, and what does that imply for
   the remaining seven?
