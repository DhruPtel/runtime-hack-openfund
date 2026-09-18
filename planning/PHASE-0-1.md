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
  outcome and is never rounded up to pass. A recorded **fail** is a completed
  probe, not a blocked one.
- Run order is **0.8 before 0.3**: an address must be established as real before
  we quote against it.

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

**Build:** directory skeleton per `CODEBASE.md` §2 (empty modules are fine), a config
loader reading `.env`, and a log filter whose denylist is **derived** from the
credential table in `PLAN.md` §6 rather than hand-written, so adding a credential
cannot create an unredacted path.

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

**Done when:** every surface has a confirmed working header; the LLM Gateway
toggle is confirmed **on** for `BANKR_LLM_KEY`; and the Agent API is set off in
the console with **no call to `/agent/prompt` anywhere in the system**, asserted
in code.

The Agent API half changed after measurement (finding F0.2.5): a read against
`/agent/job/{id}` returns 404 with a body that conflates missing-job with
no-permission, so the toggle state cannot be confirmed from a read, and settling
it would need a write that consumes quota. We assert the property we actually
care about — that nothing calls it — rather than a toggle we cannot observe.

**Risk:** the CLI-minted key has Agent API off by default, which is what we want.
Do not "fix" it in the web console.

---

### 0.3 Quote shape

**Goal:** the real response shape for a stock quote on 4663, not the documented
one.

**Build:** `probes/quote.py`. `POST /wallet/swap-quote`, `fromChain: "robinhood"`,
USDG → one stock contract address **taken from the 0.8 allowlist**, at the $25
intended size. Then repeat at a larger size and for a second stock. A small quote
passing tells us nothing about a real position, so $25 is the figure that matters.

**Artifact:** full redacted responses in findings, plus a list of which fields
were actually present versus documented-but-absent.

**Done when:** we can state which fields we may rely on.

Measured (F0.3.2): all 12 documented fields were present in all 6 responses,
none absent and none undocumented. That does not make nine of them guarantees —
six responses at one moment is not a contract — so 1.5 still treats an absent
field as `null`, never as zero. Note `amount` is **human-readable** in the
request while the response carries both raw `amount` and `formattedAmount`; the
adapter owns that conversion.

**Risk:** a stock with no quote returns an error that looks like a bug. Try
several tickers before concluding anything. A quote is also not balance-checked
(F0.3.3): a size the wallet cannot cover still prices, so a successful quote is
never evidence of executability.

---

### 0.4 ▶ Chainlink and the multiplier

**Goal:** settle how the accounting mark is computed.

**Build:** `probes/feed.py`, in two steps.

*Step 1 — coverage.* Does GeckoTerminal return a price for RH stock tokens at
all, using the `robinhood` network slug? Record the answer per asset, measured.
GeckoTerminal prices come from pools, and Robinhood's tokenized stocks have no
pool of their own, so coverage is a question and not an assumption.

*Step 2 — divergence,* only if step 1 found coverage. Read `latestRoundData` for
five stock feeds at one pinned block over `RPC_4663_MAINNET`, recording answer,
decimals, `updatedAt` and round id. Compare against GeckoTerminal, compute divergence, then
read `uiMultiplier()` on each token and check whether applying it changes
agreement.

*If coverage is absent,* the corroborating source becomes a **Bankr quote at the
$25 size**, recorded explicitly as **not independent of the execution venue**, and
the divergence veto changes shape from cross-source to quote-versus-feed. That is
a weaker check and the finding must say so.

**Artifact:** the coverage result, the comparison table, and a written
conclusion: is the feed price already multiplier-adjusted, and what corroborates
it?

**Done when:** coverage has a measured answer, and the multiplier question has a
measured answer rather than an inferred one.

**Run 2026-09-18 — half met.** Coverage is measured and total: 35 of the 57
directory feeds are equity feeds, and GeckoTerminal prices 32 of 32 addressable
tokens, so the fallback corroborator does not fire. The multiplier question is
**not** measured and is recorded unresolved: nine tokens carry a multiplier other
than 1.0, the largest is 22.1 bps, and the feed-to-corroborator noise floor
averages 141.9 bps, so neither hypothesis can be rejected (`research/findings.md`
F0.4.4). The done-condition is **not** rewritten to match what was achieved —
what would settle it is an asset whose multiplier clears the noise, or an archive
read across a multiplier change, and neither is available today.

**Risk:** the highest-value unit in Phase 0. If the two sources disagree wildly,
the marking decision needs revisiting before Phase 1 is designed. Also watch for
feeds that return a stale `updatedAt` outside market hours; that's expected, and
it's what the staleness rule in 1.3 is for.

**Checkpoint:** you see the table. Judge whether the two sources agree closely
enough to trust either one, and whether the divergence threshold we chose for a
veto is realistic.

**Checkpoint held 2026-09-18 — three decisions** (`tracker/LESSONS.md`):

- **Feed presence is a membership condition.** With no feed there is no mark
  independent of the venue, which leaves 35 assets.
- **Divergence is tiered by corroborator liquidity.** The veto fires at ~100 bps
  where the pool does over $1M a day; below that line the asset is excluded from
  the universe. Both numbers are provisional, in `config/thresholds.json`.
- **Depth returns as corroborator quality only, never as a tradeability term.**
  This reverses the 2026-09-17 deletion, which rested on the false no-pool
  premise.

The multiplier question stays unresolved, and 1.4 follows the documentation.

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

**Expected outcome: fail.** The operator is in the US and tokenized-stock
execution is location-gated, so this probe exists to capture the exact 403 body
and confirm the gate empirically, not to discover whether we can trade. A
predicted answer is still a probe we run: recording the real error is what lets
unit 5.6 decode it and what keeps PLAN.md §13 honest.

**Run 2026-09-18 — fail, as expected.** One attempt selling 0.0001 ETH into
AAPL returned 403 in 115 ms, `{"message":"Tokenized stocks (AAPL) are not
available in your region."}`, before anything was broadcast and at no gas cost
(F0.5.1–F0.5.2). Three things follow. First, the seven causes were never listed
in this repository; they are now pinned in `probes/execute.py`, six quoted from
Bankr's Errors table and the seventh reconstructed (F0.5.4). Second, the body is
prose with no machine-readable cause, so 5.6's decoder fails closed on any 403 it
does not recognise (F0.5.3). Third, the location gate fired first, so this does
**not** show that `BANKR_KEY_EXEC` can transact (F0.5.5), and Phase 5's live leg
is not de-risked until an ungated swap with that key settles.

**Risk:** a quote succeeding proves nothing about execution. A pass here would
have to be an actual fill, not an absence of error.

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

**Run 2026-09-18.** Both endpoints answer, and the balance reads in 132 ms,
which confirms `REVIEW-RESPONSE.md` finding 13 (F0.6.1). The risk above came
true: usage is attributable to (API key × model × day-window) and nothing finer
(F0.6.4). The run also found two things the unit did not anticipate:

- Credits are **wallet**-scoped and usage is **key**-scoped, so the two cannot
  be reconciled against each other (F0.6.6).
- Out-of-range `days` values are silently coerced, so the window must be read
  back from the response (F0.6.5).

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

**Run 2026-09-18, across 0.7, 0.7b, 0.7c, 0.7d and 0.7e.** `stockwatch` no longer
existed, so a trivial handler was deployed in its place.

- **Timings.** Unpaid 402: 107–280 ms. Paid call: ~4.6 s end to end,
  ~1.5 s of it inside the platform. Cold start: ~0.5 s (F0.7d.5). That
  confirms the cached-record design.
- **What made it settle.** The first paid call failed because our handler
  returned a plain object rather than a `Response` (F0.7d.2).
- **The payer header.** `x-402-payer` is a bare payer address that the
  platform asserts. `X-PAYMENT` is not forwarded to the handler (F0.7d.7).
- **Revenue evidence.** Revenue is an on-chain `PaymentSettled` with the fund
  as `owner` (F0.7b.5–F0.7b.6).
- **"A standard client can pay us" needed a second probe.** The published v1
  clients cannot pay, failing on the network enum alone. The v2 client
  `@x402/fetch` 2.26.0 pays unmodified (F0.7e). The Bankr CLI implements no
  x402; it asks Bankr's server to pay (F0.7e.4).

The checkpoint's price question — what a fair price is — has not been decided.

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

**Run 2026-09-18 — done, and decided.** The issuer registry is
`GET api.robinhood.com/rhj/assets`: 194 assets, all on 4663, with no version, no
`ETag` and no `Last-Modified`, so the snapshot's sha256 serves as its version
(F0.8.1). Five checks were run against nine candidates (F0.8.2):

- Feed presence **admits both GME counterfeits** (F0.8.3).
- The registry and the beacon agree on all 381 addresses swept (F0.8.4).

Decisions (`tracker/LESSONS.md` 2026-09-18):

- Registry membership is the identity test.
- `uiMultiplier()` and the name marker are retired.
- The beacon is a cross-check that fails the cycle loudly.
- Feed presence is markability, not identity.

The ceiling on all of this: both counterfeits were crude. A proxy-cloning forgery
would be caught only by the registry, and a counterfeit that got into the
registry would defeat every check. The snapshot this probe took is in the
gitignored `probes/out/`; 1.2 pins its own.

---

### 0.9 — relocated to unit 1.7

The analyst cost probe needs a real snapshot, and snapshot bytes dominate the
token count it is trying to measure. It moves to Phase 1, immediately after the
snapshot builder, as **unit 1.7**. The 0.9 number is not reused.

**Run anyway, 2026-09-18, as a floor** (`tracker/LESSONS.md`). The run was one
brief over six hand-assembled assets at `claude-sonnet-5` and measured:

- **Cost:** 1,793 tokens in and 982 out, **$0.013406**, which agrees with the
  published rate, the response's own usage block and the credit balance to the
  last digit.
- **Latency:** **58 s** for the call.
- **Timeouts:** a client-side timeout was still billed.
- **`/v1/usage`:** the aggregate went backwards.
- **Model choice** swings the monthly budget 139×.
- **The snapshot:** a single-block snapshot gave the trend analyst nothing to
  answer.

This does not replace 1.7; it gives 1.7 a floor to beat. The numbers are quoted
only as floors (`research/findings.md` §0.9).

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

**Checkpoint:** you read the page. Judge which assumptions died, and decide which
ungated 4663 asset carries the live leg in Phase 5.

**Phase 0 exit:** every probe has a recorded verdict, including fail and
unresolved; findings written.

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
probe 0.8, keyed by `(chain_id, address)`, with issuer source, fetch time, and
the snapshot's sha256 as its version. The registry has no version of its own
(F0.8.1), so the rule is: pin a snapshot, diff it on refresh, never look it up
live. A loader that refuses unknown addresses. Rules from the 0.8 decisions:

- **Two rules, evaluated separately and never collapsed.** Identity is registry
  membership. Markability is a Chainlink feed (0.4 decision). CRM is the case
  that proves they differ: genuine, and unmarkable.
- **The beacon is a cross-check with an independent trust root.** If it
  disagrees with the registry, the cycle fails loudly. A warning is not enough.
- `uiMultiplier()` and the name marker carry no identity weight.
- Never join the registry to the feed directory on ticker (F0.8.1: `RHDELL`).
- Do not assume `status` is always `ACTIVE` or that `deployments` has length 1.
  Neither has been observed otherwise, and neither is guaranteed.

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
session awareness, paused-oracle detection. Explicit request timeouts on every
call, and **fail loudly** — exactly one public 4663 endpoint is documented and it
carries no archive data, so no failover is claimed and no archive read is assumed
anywhere in the system. Return `Observation`s, never bare numbers.

**Artifact:** a module that, given a block, returns prices and balances with full
provenance.

**Done when:** two consecutive calls at the same block return identical values,
and a stale feed returns a labelled observation rather than a silent number.

**Risk:** public RPC with no timeout is the exact failure `aero-stock-lp` has. Set
timeouts first, not later. Historical reproducibility comes from the fixture
capture in 1.9, not from re-reading the chain.

---

### 1.4 Price cross-check

**Goal:** two independent sources, one of which marks the book.

**Build:** the corroborating adapter probe 0.4 established — `adapters/gecko.py`
for the `robinhood` slug. 0.4 measured coverage for 32 of 32 addressable tokens,
so the sized-Bankr-quote fallback does not fire. `core/valuation.py` computes the
mark from Chainlink (raw units × feed, multiplier handled per probe 0.4). It
records three fields on each asset: the divergence against the corroborator,
whether that corroborator is independent of the execution venue, and the
corroborating pool's 24h volume. The volume selects the divergence tier in
`config/thresholds.json` (0.4 checkpoint).

**Artifact:** per-asset mark, corroboration, divergence in basis points, and the
independence flag.

**Done when:** the mark is computed in exactly one function, and the divergence
field is populated for every asset.

**Risk:** applying `uiMultiplier` twice. **Probe 0.4 did not settle this**
(F0.4.4), so the code follows the documented rule — do not apply it again — and
its comment must point at F0.4.4 and state that the basis is documented and
corroborated by two sources but **not measured**, rather than implying a probe
resolved it.

---

### 1.5 Quote adapter

**Goal:** know what we could actually trade, at size.

**Build:** `adapters/bankr_quote.py`, read-only key only, no signing import.
Request quotes at the **$25 intended size**, never a token size. Record quote
age, fees, and the impact fields when present. Handle absent fields as null, not
zero.

**Artifact:** sized quotes attached to each asset.

**Done when:** a quote at intended size succeeds or fails explicitly, and a
missing impact figure is null rather than assumed safe.

**Risk:** a small quote passing tells you nothing about a real position. $25 is
the number in `config/thresholds.json`; the probe uses it, not a convenient
smaller one.

---

### 1.6 ▶ Snapshot builder

**Goal:** the frozen object.

**Build:** `core/snapshot.py`. Merge observations (already fetched; no network in
`core/`), apply the tradeability filter, assign each asset a status, canonicalize,
hash.

**Tradeable** means all three of: a quote at the intended size succeeded; quote
age is within bound; and impact is either known and within limit, **or null — and
null blocks**. There is no depth term in tradeability. Tokenized stocks do have
AMM pools (F0.4.3 — SPY holds $9.16M in one USDG pool), but execution is RFQ
against USDG rather than against those pools, so pool depth says nothing about
our fill. Depth is used for one thing only: grading the GeckoTerminal
corroborator in 1.4 (0.4 checkpoint decision).

**Artifact:** a real snapshot JSON on disk plus its hash.

**Done when:** identical inputs produce an identical hash and any field change
produces a different one.

**Checkpoint:** you read a real snapshot. Judge whether an analyst could say
anything intelligent from it. If not, we add data sources before writing a single
analyst, because the report is the product.

---

### 1.7 Analyst cost

*Relocated from probe 0.9, because snapshot bytes dominate the token count being
measured and no snapshot exists until 1.6.*

**Goal:** a real number for the cycle budget and the endpoint price.

**Build:** `probes/llm_cost.py`. Take one realistic analyst prompt with the real
snapshot from 1.6 embedded, and run it against the intended model. Record input
tokens, output tokens, latency and cost.

**Artifact:** one measured call, multiplied out: cost per analyst, cost per cycle
at **four analysts plus one risk call**, cost per day at daily cadence, and the
implied floor under the $0.05 endpoint price.

**Done when:** the numbers exist and are in findings, and the $0.05 price is
either confirmed or revised against them.

**Risk:** the prompt is still a draft until checkpoint 2.1, so treat the number as
a floor. Retries and the risk context bundle are additional.

**What 0.9 already showed.** Set the client timeout from the measured 58 s, not
from `_capture`'s 20 s default, because a timed-out call is still billed. Read
cost from the response's own `usage` block, and never from a `/v1/usage` delta
taken around the call. Price the same token counts across the catalogue as
well, since the model pin is the largest cost lever (F0.9.1–F0.9.5).

---

### 1.8 Held-but-untradeable

**Goal:** an asset leaving the buy universe must not leave the book.

**Build:** separate `universe_status` (can we buy it) from `holding_status` (do
we own it, what's it worth, can we exit). A holding excluded from trading is
valued and flagged, never dropped.

**Artifact:** both statuses on every asset.

**Done when:** a test removes an asset from the allowlist and the position
survives with a labelled status.

**Risk:** this is the quiet bug that makes a portfolio report lie.

---

### 1.9 ▶ Fixtures and replay

**Goal:** the demo never depends on the network.

**Build:** a fixture writer that captures raw source responses (not just the
normalized snapshot), and a replay mode that rebuilds from them.

**Artifact:** `fixtures/` with at least one full capture.

**Done when:** live and replayed builds produce identical hashes with the network
disabled.

**Checkpoint:** you watch it build offline. Judge how much of the demo should run
from fixtures versus live.

---

### 1.10 Address selftest

**Goal:** the address table is attested, not trusted.

**Build:** a `--live` selftest that checks every address in config against chain:
it exists, has expected decimals, matches its expected feed, and passes the
beacon consistency check.

**Artifact:** a pass/fail report per address.

**Done when:** it runs green, and flipping one address to a wrong value turns it
red.

---

### 1.11 ▶ Skew rejection

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
3. Which ungated 4663 asset carries the live leg in Phase 5, and does the
   paper/live split change what the demo is?
4. What did Phases 0 and 1 actually cost in time, and what does that imply for
   the remaining seven?
