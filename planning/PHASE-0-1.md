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

**Run 2026-09-18 — half met.** Idempotency half, measured with one 0.00003 ETH
(~$0.08) sell into USDG on 4663:

- **Same-key replay is safe once the original has completed.** The repeat
  returned the original result in 178 ms, and the chain shows one fill
  (F0.10.1).
- **The in-flight `409` path is still documented only.**
- **The execution key can transact** (F0.10.2).
- **The swap is not a transaction from our wallet.** It is a sponsored
  UserOperation inside an EIP-7702 transaction, and the wallet is now delegated
  on 4663 (F0.10.3).

Rate-limit half: **unresolved**. No 429 and no rate-limit header of any kind
appeared within 150 requests in 4.1 s. So the backoff signal is only the
documented bare 429 (F0.10.5).

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

**Held 2026-09-18.** The page is the "Phase 0 exit summary" at the head of
`research/findings.md`. Every probe has a verdict, 0.4 and 0.10 are half met,
and twelve assumptions are listed as dead. Four decisions came out of it
(`tracker/LESSONS.md`):

- **Freshness binds a series' newest point only.** This closes the 1.11 gap.
- **Config values.** Feed staleness is each feed's heartbeat plus a margin,
  and the margin is not yet given. Quote age is 60 s. Impact is 50 bps,
  compared signed. The worker deadline is 120 s. The analyst model is
  `claude-sonnet-5`, provisionally. All are provisional and in `config/`.
- **The live leg is ETH→USDG on 4663.** It was proven for one sell (F0.10.1–
  F0.10.3); the return leg is still unexercised.
- **§11's x402 rationale stays marked contradicted, and $0.05 stays
  provisional.** Neither blocks Phase 1.

**Phase 0 is closed.**

**Phase 0 exit:** every probe has a recorded verdict, including fail and
unresolved; findings written.

---

# Phase 1 — adapters and snapshot

**Purpose:** turn a permissionless chain and its data sources into one frozen,
hashed, trustworthy object that an analyst can reason over and a judge can
verify. The sources, as Phase 0 measured them, fall into three groups:

- **the chain itself**, over the public 4663 RPC;
- **two inputs pinned by content hash**: the issuer registry and Chainlink's
  feed directory;
- **two live offchain sources**: GeckoTerminal and Bankr quotes.

**Replanned 2026-09-18 against the Phase 0 record.** Every unit below was drafted
before any probe ran, and each now names the findings and decisions that changed
it (`research/findings.md`, `tracker/LESSONS.md`). No unit is added or removed.
Four are bigger than drafted:

- **1.2** carries two rules and pinned raw snapshots.
- **1.3** reads a price series.
- **1.8** has to book cash and gas, and four different ways out of the universe.
- **1.11** has seven cases instead of four.

What Phase 1 still cannot do is listed after 1.11. Where `PLAN.md` §8's one-line
Phase 1 summaries disagree with the units below, these are newer; that fold is
pending.

**Estimated:** a day to a day and a half. That was drafted before the replan,
and is now an underestimate by an amount nobody has measured.

---

### 1.1 Types

**Goal:** the contracts everything imports, defined once.

**Build:** `core/types.py`: `Observation` (value, source, source_time,
fetch_time, block), `Asset`, `Snapshot` and `Order`, with the leaf types they
need. Every numeric field carries units and decimals explicitly. Verification
fields are three-valued: true / false / null.

**Narrowed while building** (LESSONS 2026-09-18). `AnalystReport`, `Proposal`,
`Plan`, `Decision`, `JournalEvent` and `Statement` are deferred to 2.1–2.2, 3.1,
3.3, 3.7, 4.6 and 6.1. Nothing in the record fixes their shapes, and 2.1 requires
the report format be designed by hand before any code.

What the record adds:

- **A series type.** The snapshot carries history up to its pinned block
  (invariant 2), so an asset holds an ordered series of `Observation`s per
  source, not one reading. Freshness is a property of the series' newest point
  only (staleness decision), so that point is addressable directly.
- **Identity and markability are separate fields on `Asset`, never one
  verdict.** Identity is registry membership on `(chain_id, address)`;
  markability is a pinned Chainlink feed; the beacon cross-check is a third,
  three-valued result (0.8 decisions; F0.8.3 is why they cannot be merged). The
  registry's own fields ride along as given — ISIN, `status`, `deployments`,
  current and pending multiplier, decimals. Nothing assumes `status` is always
  `ACTIVE` or that `deployments` has length 1 (F0.8.1).
- **No default decimals.** Amounts are raw integer, decimals and asset id: USDG
  is 6, stock tokens 18, feed answers 8 (F0.3.1, F0.4.7). A "tokens on 4663 are
  18" default is exactly the error F0.3.1 caught.
- **`Order` and `JournalEvent` must not assume a swap is a transaction from our
  wallet.** On 4663 it is a UserOperation inside a bundler's EIP-7702
  transaction (F0.10.3). Its identity is a UserOperation hash and its outcome is
  the operation's own `success`. The outer transaction's sender and status, and
  the wallet's nonce, describe the bundle rather than our swap. Their full
  shape is Phase 4's to finish; 1.1 must not preclude it.

**Artifact:** one module, no imports from `adapters/`.

**Done when:** the types compile and a round-trip serialization test passes with
stable numeric encoding. The test covers a series, and an asset whose identity is
true and markability false (CRM's shape, F0.8.2).

**Risk:** getting `Observation` wrong makes every later timestamp argument
harder. Source time and fetch time are separate fields, always.

**Changed by:** the price-history and staleness decisions; 0.8's identity
decisions and F0.8.1–F0.8.3; F0.3.1 and F0.4.7 (decimals); F0.10.3
(UserOperations); F0.6.4, F0.7b.6. **Size:** a little bigger than drafted.

---

### 1.2 Universe allowlist

**Goal:** an asset enters the system only if we know it is the real one, and is
held only if it can be marked independently of the venue.

**Build:** `core/universe.py` plus `config/registry/`, from a pinned snapshot
of the issuer registry, `GET https://api.robinhood.com/rhj/assets`. It needs no
authentication and lists 194 assets, all on 4663 (F0.8.1).

- **The snapshot is the raw response bytes, and it lives in `config/registry/`**
  as `rhj_assets.<sha256>.json`. `config/registry/pins.json` records the URL,
  fetch time, byte count and sha256; `feed_map.json` holds the reviewed
  address-to-feed map. Together they are the allowlist, and
  `config/universe.json`, never built, is retired. The
  registry carries no version, `ETag` or `Last-Modified`, so the sha256 of those
  bytes **is** the version. The rules, per the 0.8 decision:
  - pin it, and diff it on refresh;
  - treat a hash change as a version bump that needs an explicit config change;
  - never look the registry up live at cycle time.
- **Why raw bytes.** Probe 0.8 kept the parsed assets, not the bytes it hashed,
  so its recorded sha256 (`442718b5…`) could not be re-verified from anything
  kept. *Built:* 1.2's fresh fetch hashed to exactly that version, so it is now
  verified against stored bytes, and the registry was byte-identical five hours
  later (LESSONS 2026-09-18).
- **Identity: registry membership on `(chain_id, address)`**, compared
  case-insensitively, since the registry uses EIP-55 mixed case (F0.8.1). It was
  necessary and sufficient against every counterfeit tested (F0.8.5).
- **Markability is a separate rule, never collapsed into identity.** A Chainlink
  equity feed exists for 35 of the 194 (F0.4.1).
  - Each asset's feed is pinned by its proxy address, never joined on ticker at
    cycle time. The directory carries **no token address**, so the address-keyed
    `feed_map.json` began as a name match. It was proposed from the registry's
    own records, so a counterfeit can never be proposed a feed, and it was
    reviewed. 32 were exact; DELL (`RHDELL`), SGOV and USAR (no base asset,
    F0.8.1) were reviewed by hand (LESSONS 2026-09-18).
  - Feed presence carries zero identity weight: it admitted both GME
    counterfeits (F0.8.3).
  - CRM proves the two rules differ: it is genuine, and unmarkable.
- **Chainlink's feed directory is pinned the same way** — bytes, sha256 and fetch
  time. Unlike the registry, it sends an `ETag` and `Last-Modified`. It supplies each feed's proxy address, decimals and heartbeat, and 1.3's
  staleness rule reads the heartbeat from it (staleness config decision; F0.4.1).
  It returns 403 without a `User-Agent` (probe 0.3).
- **The beacon is a cross-check with an independent trust root, not a filter.**
  Each stock's EIP-1967 beacon slot must resolve to the issuer's beacon
  (`0xe10b…1b00`, F0.8.2). A disagreement with the registry fails the cycle
  loudly, never as a warning (0.8 decision). Registry and beacon agreed on all
  381 addresses swept (F0.8.4), so this is insurance, not detection.
- **Retired:** `uiMultiplier()` and the `• Robinhood Token` name marker carry no
  identity weight and are not read for identity (0.8 decision; F0.T.4 measured
  140 forgeries carrying the marker).
- **The cash leg is not a stock.** USDG is genuine, but it is not in the registry
  and every check rejects it as a stock (F0.8.2). It is pinned separately by
  `(chain_id, address)`, with its on-chain decimals (6, F0.3.1) and its own
  provenance. Native ETH is the gas token and, since the 0.11 decision, the live
  leg's sell asset.
- **The corroborator line is not a static property.** Below $1M of 24h volume an
  asset is excluded from the universe (0.4 decision), but volume is measured per
  snapshot (1.4). So that exclusion is applied in 1.6, not frozen into the
  allowlist. This unit supplies the two static rules.
- **The I/O seam.** The refresh fetch and the beacon read are network I/O, so
  `core/universe.py` takes their results as arguments. The beacon read is
  1.3's. The registry and directory fetch has **no unit that owns it yet**; the
  initial pin used a one-off fetch.
- Do not assume `status` is always `ACTIVE` or that `deployments` has length 1.
  Neither has been observed otherwise, and neither is guaranteed (F0.8.1).

**Artifact:** under `config/registry/`, the raw registry and directory
snapshots, `pins.json` and `feed_map.json`, which together are the versioned
allowlist; and a loader.

**Done when:**
- an address outside the pinned snapshot cannot enter a snapshot;
- a counterfeit whose ticker has a feed is refused;
- CRM is admitted as genuine and excluded as unmarkable;
- a simulated beacon disagreement fails the cycle by name;
- a version bump requires an explicit config change.

**Risk:** the temptation to resolve by ticker for convenience — that is how the
fake GME gets bought. There is also a ceiling we cannot raise. A proxy-cloning
forgery would be caught only by the registry, and a counterfeit inside the
registry would defeat every check we have (F0.8.5 and its limitations).

**Changed by:** 0.8's four decisions and F0.8.1–F0.8.5; the 0.4 membership and
tier decisions; F0.3.1; F0.T.4. **Size:** bigger than drafted — a second rule, a
second pinned input, and the cash leg.

---

### 1.3 Chain adapter

**Goal:** reads that are internally consistent and honest about age, history
included.

**Build:** `adapters/chain_4663.py`. Return `Observation`s, never bare numbers.

- **One pinned block per snapshot, and everything read at it**, multicall where
  possible. The endpoint honours the block parameter: F0.4.7 falsified that
  directly.
- **The endpoint, as configured and as recorded.** `RPC_4663_MAINNET` is the
  public `robinhood.com` RPC (checked 2026-09-18). The record says it is the only
  documented endpoint and carries no archive data (`research/agent-os.md` §8;
  LESSONS 2026-09-17). So: explicit timeouts on every call, fail loudly, no
  archive read assumed. **Built:** every request has a whole-request deadline.
  Failover runs over an ordered endpoint list and advances on a hang, shown
  live against a silent socket. With one endpoint it has nowhere to go, so
  this is still fail loudly (LESSONS 2026-09-18, the public RPC). 0.10 read balances one block back
  (F0.10.4); that is recent state, not archive, and nothing relies on it.
  **Unverified:** the operator's note of a failover endpoint (Alchemy) with
  archive access. It is neither configured nor measured, so it is not built on.
  If one is added, measure it first; this unit, 1.9 and PLAN §13 change with it.
- **A `User-Agent` on every request.** The 4663 RPC, the CoinGecko list and the
  Chainlink directory all return 403 without one, and that 403 is not an auth
  failure (probe 0.3).
- **Feeds:** `latestRoundData`, `decimals` (8 on every equity feed, F0.4.7),
  paused-oracle detection, and market-session awareness — the equity feeds are
  `us_equities_24/5` (F0.4.1). **Built:** `latestRoundData` and each proxy's
  own `decimals()`, which agreed with the directory on all 37 feeds. Neither
  paused-oracle detection nor market-session awareness is a separate check:
  a paused feed shows up only as a stale newest point, and the session is named
  in the verdict but does not change it (LESSONS 2026-09-18, "1.3 leaves two
  layout questions open").
- **Staleness binds the newest point only** (staleness decision). A newest
  observation is stale when its age exceeds its own feed's documented
  heartbeat, read from the pinned directory (86,400 s for equities), plus
  `feed_staleness_margin_seconds` (3,600 s, provisional) — so an equity feed's
  newest point is stale past 90,000 s. An `updatedAt` 3.6 h old is normal in
  market hours (F0.4.7).
  **Measured in 1.3.** The largest weekday gap was 24.0 h, inside the limit.
  Over one weekend, every equity feed was silent for 48–59 h, so the rule
  judges them all stale for about 23–35 h each weekend. The rule stands, and
  what to do about it is 1.11's question (LESSONS 2026-09-18). The comparison
  is in the adapter, while CODEBASE says only `gates.py` makes one; that is
  open.
- **The price series** (invariant 2). This unit chose the series and its
  window, under the no-archive rule. **Chosen:** the feed's own rounds, read
  at the pinned block via `getRoundData` (DECISION, LESSONS 2026-09-18). They
  need no archive (all 645 of AAPL's rounds were readable at a recent block),
  and they hold the one-block rule.
  - **Window.** 7 days, capped at 1,000 rounds, with one anchor round at or
    before the window start.
  - **Coverage.** `Series.coverage` says whether the window was reached: all
    37 feeds did, with 7–361 points.
  - **Scale breaks.** A 10,000× step between consecutive answers stops the
    walk. 32 of 37 feeds began life about 1e8 too large.
  - **GeckoTerminal OHLCV** was not measured and is not ruled out for 1.4.

  Historical points are not staleness-checked; they are history.
- **Balances over RPC only.** `/wallet/portfolio` returned an empty
  `tokenBalances` for every ERC-20 the wallet has held (F0.7b.8). Its native
  balances were exact, but the adapter reads the chain.
- **The execution wallet is not an EOA on 4663.** Since 0.10 it carries an
  EIP-7702 delegation to a Bankr contract (code `0xef0100…`, F0.10.3). Balance
  reads are unaffected. Nothing may test "is an EOA" on it.
- **Beacon slots** (`eth_getStorageAt` at the pinned block), for 1.2's
  cross-check.
- **Rate limits.** The public RPC is documented as rate-limited
  (`research/agent-os.md`), and the 46630 endpoint returned 429 under batching
  (Testnet limitations). **Measured in 1.3:**
  - a JSON-RPC batch of 100 drew an immediate 429 with no `Retry-After`;
  - one Multicall3 `aggregate3` of 215 reads was accepted, so reads go through
    it, paced at 500 ms with a doubling backoff;
  - storage reads cannot be multicalled, so 35 beacon slots take about 18 s;
  - a rare "historical state not available" at the pinned block is retried,
    which is safe because every read is by block hash. Bankr's API showed no rate-limit headers at all
  (F0.10.5).

**Artifact:** a module that, given a block, returns prices, a price series per
asset, balances and beacon slots, each with full provenance.

**Done when:**
- two consecutive calls at the same block return identical values, series
  included;
- a stale newest point returns a labelled observation rather than a silent
  number;
- a series whose historical points are old but whose newest point is fresh is
  accepted.

**Met**, by `python -m fund.adapters.chain_4663 --prove`, live at block
66652203:
- all 37 feeds and the AAPL series read identically twice;
- AAPL's oldest point, 7 days old, would judge stale alone, while the series
  judges fresh on its newest;
- a staleness verdict is a `Check` with its age, heartbeat and margin in the
  reason, never a bare number;
- a real two-block read is refused at `block-pin`;
- a refused socket yields undetermined, not false.

Offline, 39 tests in `tests/test_chain_4663.py` assert each refusal at its own
rule; every rule was mutated and its test failed.

**Risk:** a public RPC with no timeout is the exact failure `aero-stock-lp` has,
so set timeouts first. The weekend is the other risk: a 24/5 feed may
legitimately go longer than its heartbeat while markets are shut. That is
measured on one weekend in 1.3 (48–59 h), and remains 1.11's checkpoint
question. Historical reproducibility comes
from 1.9's fixtures, not from re-reading the chain.

**Changed by:** the price-history and staleness decisions; the staleness config
decision; probe 0.3's User-Agent note; F0.4.1, F0.4.7; F0.7b.8; F0.10.3–F0.10.5;
and 1.3's own measurements (LESSONS 2026-09-18).
**Size:** bigger than drafted — the series, and the measurement to choose it.

---

### 1.4 Price cross-check

**Goal:** two independent sources, one of which marks the book.

**Build:** `adapters/gecko.py`, for GeckoTerminal's `robinhood` network. It prices
32 of 32 addressable stock tokens off real pools and is independent of the
execution venue (F0.4.2–F0.4.3), so the sized-Bankr-quote fallback does not fire.
`core/valuation.py` computes the mark in exactly one function:

- **Mark = raw units × the Chainlink answer**, with the feed matched to the asset
  by the proxy address pinned in 1.2, never by ticker (F0.8.1). **The multiplier
  is not applied again.** That rule is documented by two sources and
  corroborated, but **not measured**: 0.4 could not see a 22 bps effect under a
  142 bps noise floor (F0.4.4). The comment in `core/valuation.py` must say
  exactly that and point at F0.4.4.
- **The Bankr quote is never the corroborator.** Its price is the venue's own
  (F0.3.5). The venue also applies the multiplier itself, so comparing against it
  would answer the multiplier question circularly (F0.4.4).
- **Recorded per asset:** the divergence in bps against GeckoTerminal, the
  independence flag, and the 24h volume that selects the tier in
  `config/thresholds.json`. Above $1M the veto fires past 100 bps. Below it the
  asset is excluded from the universe (0.4 decision), and that exclusion is
  applied in 1.6. Depth, in its one remaining role, is this: a measure of the
  corroborator's quality, never of tradeability (0.4 depth decision).
- **Use the volume the tier was set on.** The $1M line was decided on F0.4.5's
  numbers, which are GeckoTerminal's token-level `volume_usd.h24` from its batch
  tokens endpoint (`probes/feed.py`), not one pool's volume. Measuring
  differently changes what $1M means. The batch endpoint also lists only one of
  a token's pools (F0.4 limitations).
- **The tier does not make a liquid name safe.** AMZN diverged 499 bps on $2.19M
  of volume, while feed and quote agreed to 20 bps (F0.4.5). The veto has to
  fire there.
- **Cash and gas are marked too.** The wallet holds USDG and ETH on 4663, and
  Chainlink publishes ETH and USDG feeds there alongside the equity ones
  (F0.4.1). Both are valued by those feeds. USDG is not assumed to be $1; the
  venue priced it at 1.0022 (F0.3.5).

**Artifact:** for each asset, the mark, the corroboration, the divergence in bps,
the independence flag, and the 24h volume and tier; for each non-stock holding,
its mark.

**Done when:** the mark is computed in exactly one function, for stocks and cash
alike; divergence and volume are populated for every markable asset; and the
tier comes from config.

**Risk:** applying `uiMultiplier` twice (F0.4.4). The tail is the other risk.
Every divergence number is one block during US market hours; overnight and at
weekends, when 24/5 feeds and 24/7 pools drift furthest apart, nothing bounds it
(F0.4 limitations).

**Changed by:** F0.4.1–F0.4.5, F0.3.5, F0.8.1; the 0.4 tier and depth decisions.
Three findings tables cite "1.4" for the x402 cached-record design (§0.7, §0.7b,
§0.7d). That design concerns 7.x and changes nothing here. **Size:** a little
bigger than drafted, because of the cash and gas marks.

---

### 1.5 Quote adapter

**Goal:** the venue's price at our intended size, labelled as a price and as
nothing more. A quote is not evidence that we could trade (F0.3.3), and for
stocks we cannot (F0.5.1).

**Build:** `adapters/bankr_quote.py`, with `BANKR_KEY_READ` and no signing import.
Read keys may quote (documented), and probe 0.3 quoted with this one. Quotes are
USDG→stock at the **$25 intended size**, never a token size.

- **Sizing.** $25 nominal is about 24.94 USDG, because the venue priced USDG at
  1.0022 (F0.3.5); the adapter owns that conversion. The request `amount` is
  human-readable.
- **The response mixes formats** (probe 0.3's six responses, re-read while
  building 1.1; LESSONS 2026-09-18):
  - `from.amount` echoes the human request;
  - `to.amount` is raw;
  - `to.formattedAmount` is lossy, a digit short, so it is never read;
  - `minBuyAmount` is human text;
  - the two USD prices are JSON floats, converted exactly from their shortest
    text with `Price.parse`.
- **Decimals are per asset and read on chain:** USDG is 6, stock tokens 18
  (F0.3.1).
- **Fields.** All 12 documented fields appeared in all 6 responses (F0.3.2). That
  is not a guarantee: an absent field is null, never zero, and a null impact
  blocks.
- **Impact is signed** and gated as `impact > impact_max_bps` (50), never
  `abs(impact)`, because negative impact is price improvement (F0.3.4). The field
  that gates is `swapImpactBps` (documented). The two impact fields have never
  differed in a measurement (F0.3.4).
- **Age.** `quote_max_age_seconds` is 60. A stale or unknown `quoteId` "falls
  back silently" (documented), so a quote's age comes from our own clock, not
  from reusing its id.
- **Errors.** A malformed body gets an identical `{"message":"Invalid request
  body"}` whatever is wrong (probe 0.3), so the adapter validates its own
  request. Amounts below a venue minimum are refused as "too small to swap"
  (§0.10). A 429 carries no rate-limit headers (F0.10.5).

**Artifact:** sized quotes attached to each asset, with age, fees and signed
impact.

**Done when:** a $25 quote succeeds or fails explicitly for every asset, a
missing impact is null and blocks, and a negative impact passes the gate.

**What funding does and does not change.** The draft had this unit re-run probe
0.3 "against a funded wallet, which is when its numbers first mean anything
about liquidity". The record does not support that, for two reasons:

- **Quotes are not balance-checked.** A $25 quote priced normally against a
  wallet holding no USDG (F0.3.3), so a funded wallet sends the same request
  and, as far as anything measured shows, gets the same answer.
- **No stock quote can be tested against a fill**, because stock execution is
  gated for this operator (F0.5.1).

So funding does not turn these numbers into evidence about liquidity, and nothing
in Phase 1 can. What the unfunded wallet does block is 3.3's sizing against
reconciled holdings, and Phase 5's volume.

The same reasoning applies to the impact fields. F0.3.4 said separating them
"needs a funded wallet". F0.3.3 suggests a larger quote prices unfunded, so this
unit can test that with a read-only quote above $25. That is inferred, and
untested.

**Risk:** reading a successful quote as tradeability on its own. It is one of
three conditions (1.6), and never proof of a fill.

**Changed by:** F0.3.1–F0.3.5, F0.5.1, the documented gating field (the note
under F0.5), F0.10.5, and the quote-age and impact config decisions. **Size:** as
drafted, and smaller in one respect: it no longer waits on funding.

---

### 1.6 ▶ Snapshot builder

**Goal:** the frozen object: one per cycle, containing history up to a pinned
block (invariant 2).

**Build:** `core/snapshot.py`. It merges observations that are already fetched
(no network in `core/`): each asset's feed reading and price series, its
corroboration, its quote, and the wallet's holdings. Nothing dated after the
pinned block may enter. Then it applies, in order:

1. **Identity and markability** (1.2), with the beacon cross-check failing the
   cycle loudly on disagreement.
2. **The corroborator line** (1.4, `config/thresholds.json`): below $1M of 24h
   volume, the asset is excluded from the universe.
3. **The divergence veto** above that line, past 100 bps.
4. **Tradeability**, defined operationally: a quote at the intended size
   succeeded; its age is within 60 s; and its impact is known and at most 50 bps
   signed, **or null — and null blocks**. There is no depth term. Pools exist
   (F0.4.3), but execution is RFQ against USDG, so depth grades only the
   corroborator (0.4 decision).

Each asset gets a status with a named reason, and each holding gets a holding
status (1.8). The inputs' provenance goes at the top: the block, the registry and
directory sha256s, and the config version. Then canonicalize and hash.

**Artifact:** a real snapshot JSON on disk, plus its hash.

**Done when:** identical inputs produce an identical hash, any field change
produces a different one, and an observation dated after the pinned block is
refused.

**Checkpoint:** you read a real snapshot and judge whether an analyst could say
anything intelligent from it. The prior evidence is F0.9.6: given a single
reading per asset, a trend analyst correctly returned `NO_CALL` on all six. The
history this snapshot carries is the decided response to that. If it is still
not enough, we add data sources before writing a single analyst, because the
report is the product.

**Risk:** size. The snapshot is loaded as bytes into every prompt (invariant 2).
With ~19–35 assets and a series each, it will be far larger than the only
measured prompt, which was 1,793 tokens for six single readings (F0.9.1,
F0.9.4). Its token count sets 1.7's cost and 2.4's context budget.

**Changed by:** the price-history and staleness decisions; the 0.4 tier and depth
decisions; 0.8's decisions; the quote-age and impact config decisions; F0.9.4,
F0.9.6. **Size:** the same shape as drafted, with more content.

---

### 1.7 Analyst cost

*Relocated from probe 0.9, which then also ran early as a floor on six
hand-assembled assets (LESSONS 2026-09-18). This unit still owns the number.*

**Goal:** a real number for the cycle budget and the endpoint price.

**Build:** reuse `probes/llm_cost.py`, which exists from 0.9, with the real
snapshot from 1.6 embedded, run against `analyst_model` (`claude-sonnet-5`,
provisionally, per the config decision). What 0.9 established about how to
measure:

- **Timeouts.** `transport_timeout_seconds` is 180, above the measured call
  latency (58 s at the floor). A call timed out client-side is still billed
  (F0.9.1, F0.9.3): 0.9's first call was cut off by `_capture`'s 20 s default and
  charged anyway. `worker_deadline_seconds` is 120. That is shorter than the
  transport timeout, which matters to 2.4's runner, not to this unit's single
  calls (LESSONS 2026-09-18).
- **Cost from the response's own `usage` block**, not from a `/v1/usage` delta
  around the call, because the aggregate went backwards (F0.9.2). Reconcile
  against settled windows, reading `days`, `startDate` and `endDate` back
  (F0.6.5).
- **At least two identical calls.** Output varied 14% between two calls at
  temperature 0 (F0.9.3), so cost per call is a distribution, not a constant.
- **Price the same tokens across the catalogue.** The model pin is a 139× lever
  (F0.9.5), and 2.4 needs that comparison to choose.
- **Price the risk call separately.** It reads four reports and the sized plan,
  and 0.9 priced it as if it were an analyst call (F0.9 limitations). Until
  Phase 2 produces real reports, its input size is an estimate and must be
  labelled one.

**Artifact:** measured calls, multiplied out into:
- cost per analyst call;
- cost per cycle, at four analysts plus one risk call;
- cost per day, at daily cadence, and per 30 days;
- the implied floor under the $0.05 price.

**Done when:** the numbers exist and are in findings, and the operator has
confirmed or revised the $0.05 price against them. The price stays provisional
until then (0.11 decision).

**Risk:** the prompt is still a draft until checkpoint 2.1, so the number is a
floor, and retries and the risk bundle come on top. Latency, not cost, was the
binding number at 0.9 (F0.9.1).

**Changed by:** F0.9.1–F0.9.6, F0.6.4–F0.6.5, the model and deadline config
decisions, and the 0.11 price decision. **Size:** as drafted; 0.9 has already
built and debugged the method.

---

### 1.8 Held-but-untradeable

**Goal:** a holding never leaves the book, whatever takes it out of the buy
universe.

**Build:** separate `universe_status` (can we buy it) from `holding_status` (do we
own it, what is it worth, can we exit). A holding excluded from trading is valued
where it can be, flagged, and never dropped. What the record adds:

- **Holdings come from the chain.** Balances are read over RPC (1.3), because
  `/wallet/portfolio` omits every token (F0.7b.8).
- **There are five ways out of the buy universe, and each gets its own status**,
  because each means something different for valuation:
  - **Not tradeable this snapshot** (quote, age or impact; 1.6). The asset is
    still marked.
  - **Below the corroborator line** (0.4 decision). It is excluded from buying
    and still marked by Chainlink. The decision says such an asset is not held;
    this unit is what keeps an existing position in the book instead of dropping
    it.
  - **No longer markable**, because its feed is gone. There is then no mark
    independent of the venue, and the record rules out the venue's own quote as
    a substitute (F0.3.5, F0.4.4, 0.4 decision). How such a holding is shown is
    this unit's decision, with two constraints: it may not be the venue quote,
    and it may not silently become zero.
  - **Listed but not ACTIVE** (`LISTED_NOT_ACTIVE`). The registry still lists
    it, so identity passes, but its status is something other than `ACTIVE` —
    a form never observed (F0.8.1). It is refused for buying at 1.2's standing
    rule, and it keeps its registry record and its mark.
  - **Identity in doubt** (`IDENTITY_IN_DOUBT`). The registry no longer lists
    the asset, or its beacon read is undetermined. A beacon that disagrees fails
    the cycle outright (0.8 decision).
- **Cash and gas are holdings.** Since 0.10 the wallet holds USDG (0.078742) and
  ETH on 4663. Neither is in the registry, and both are in the book, valued by
  their Chainlink feeds (1.4). Base holdings, which are x402 revenue in USDC,
  belong to Phase 6's reporting entity, not to this snapshot.

**Artifact:** both statuses on every holding, cash and gas included.

**Done when:** tests take a held asset out of the universe each of the five ways,
and each time the position survives with its named status. USDG and ETH appear
in the book, valued from their feeds.

**Risk:** this is the quiet bug that makes a portfolio report lie, and there are
now five doors instead of one.

**Changed by:** F0.7b.8, F0.4.1, F0.3.5, F0.8.1–F0.8.2 (CRM), and the 0.10 swap
that made USDG a holding; the 0.4 membership and tier decisions; 0.8's beacon
decision. **Size:** bigger than drafted.

---

### 1.9 ▶ Fixtures and replay

**Goal:** the demo never depends on the network.

**Build:** a fixture writer that captures raw source responses, not just the
normalized snapshot, and a replay mode that rebuilds from them. What the record
adds:

- **Fixtures are the only historical reproducibility.** The configured RPC is
  the public endpoint, which is documented to carry no archive data (LESSONS
  2026-09-17), and nothing in Phase 0 measured otherwise (1.3).
- **Capture the series.** With history in the snapshot (invariant 2), a fixture
  holds each asset's series exactly as fetched: chain reads at the pinned block,
  or offchain bodies with their own source times.
- **Capture the offchain sources whole.** GeckoTerminal and Bankr quotes are not
  block-pinned. Replay reproduces what was captured and never re-fetches, so
  live-versus-replay equality holds against the same capture, not against a
  later live fetch.
- **Reference the pinned inputs; don't copy them.** They already sit in
  `config/registry/` (1.2) and are referenced by sha256.
- **Replay never refreshes a fetch time.** Source and fetch time come from the
  capture.
- **Captures pass through the redaction derived from the credential table**
  (0.1). The RPC URL is itself a declared credential.

**Artifact:** `fixtures/snapshots/` with at least one full capture.

**Done when:** live and replayed builds produce identical hashes with the network
disabled.

**Checkpoint:** you watch it build offline. Judge how much of the demo should run
from fixtures versus live.

**Changed by:** the 2026-09-17 RPC lesson, the price-history decision, 1.2's
pinned snapshots, and 0.1's redaction. **Size:** bigger than drafted, by the
series.

---

### 1.10 Address selftest

**Goal:** the address table is attested, not trusted.

**Build:** a `--live` selftest that checks every address in config against chain,
at one pinned block:

- **Each stock token** exists, has 18 decimals, and is in the pinned registry
  snapshot by `(chain_id, address)`. Its EIP-1967 beacon slot resolves to the
  issuer's beacon, and a mismatch fails loudly (0.8 decision).
- **Each feed proxy** exists, reports 8 decimals, and is the feed pinned for its
  asset — matched by address, never by ticker (F0.8.1, F0.4.7).
- **USDG** exists and has 6 decimals (F0.3.1).
- **The execution wallet**, named in `config/mandate.json`
  (`0x93fa…a3da`). On 4663 it carries an EIP-7702 delegation to a Bankr contract, so the
  selftest records the delegate and flags any change rather than expecting an
  EOA. On Base it is an EOA (F0.10.3).

`uiMultiplier()` and the name marker are not attested, because they carry no
identity weight (0.8 decision).

**Artifact:** a pass/fail report per address.

**Done when:** it runs green, and flipping one address to a wrong value turns it
red.

**Changed by:** F0.3.1, F0.4.7, F0.8.1–F0.8.2, 0.8's decisions, and F0.10.3.
**Size:** about as drafted.

---

### 1.11 ▶ Skew rejection

**Goal:** prove the snapshot refuses inconsistency, and does not refuse history.

**Build:** tests written against the staleness decision (freshness binds a
series' newest point only) and invariant 2:

1. **Mixed blocks.** Observations read at two different blocks are refused.
2. **Stale newest point.** A series whose newest observation is older than its
   feed's heartbeat plus `feed_staleness_margin_seconds` is refused as stale.
3. **Old history, fresh newest point.** This one is **accepted**. It is the case
   the drafted rules would have refused, and it proves they no longer reject
   every series.
4. **Replayed offchain body.** An offchain response whose newest point's source
   time is old relative to its fetch time is refused.
5. **From the future.** An observation dated after the pinned block is refused.
6. **Paused feed.** It is refused, excluded and labelled.
7. **Market-closed feed.** A `us_equities_24/5` feed outside market hours
   (F0.4.1) is labelled; whether it is also refused is the checkpoint's
   question.

**Artifact:** six named refusals and one named acceptance.

**Done when:** each refusal is named and reaches the caller rather than being
logged and swallowed, and the acceptance case passes.

**Checkpoint:** you see the refusals. Judge whether the strictness is right, or
whether it will block every cycle on a weekend. That question is now measured.
1.3 read one weekend: every `us_equities_24/5` feed was silent for 48–59 h, from
Friday's close to Monday 00:00Z. So the rule as decided (heartbeat + 3,600 s)
judges them all stale for about 23–35 h each weekend (LESSONS 2026-09-18). The
margin is a lever, but no margin short of about 35 h clears a weekend.

**Changed by:** the staleness decision, which closes the gap this unit carried;
the price-history decision; the staleness config decision; F0.4.1, F0.4.7.
**Size:** bigger than drafted — seven cases, not four.

**Phase 1 exit:**
- a hashed snapshot from live data, with history up to its pinned block;
- byte-identical replay from a fixture;
- bad inputs rejected by name, and old history accepted;
- every address attested, the beacon included.

---

## What Phase 1 still cannot do

Stated before the code, so that no unit's done-condition quietly assumes it:

- **Show that a stock could be traded at its quoted price.** Stock execution is
  location-gated (F0.5.1), and quotes are not balance-checked (F0.3.3). Funding
  the wallet does not change either; 1.5's quotes are prices, not fills.
- **Size against real capital.** The wallet holds 0.078742 USDG and 0.000460 ETH
  on 4663, against a ~$200 target. That does not block 1.5, because quotes price
  unfunded. It leaves 3.3's sizing against reconciled holdings, and Phase 5's
  volume, with almost nothing to size.
- **Measure whether the feed already includes the multiplier** (F0.4.4). No
  asset's multiplier clears the noise, and there is no archive to read across a
  change, so 1.4 runs on documentation.
- **Say what every weekend or holiday does to a 24/5 feed.** 1.3 measured one
  weekend (48–59 h silent, LESSONS 2026-09-18). Holidays and other weekends are
  unmeasured.
- **Settle Phase 2's model settings.** `risk_model`, `max_output_tokens`,
  `context_budget_tokens` and `cycle_deadline_seconds` are still null. They
  block Phase 2, not Phase 1. The transport timeout (180 s) is longer than the
  worker deadline (120 s), which 2.4 has to resolve.
- **Read an old block, or fail over to anything.** There is one configured
  endpoint, the public one, and it has no archive on the record. Past feed
  rounds are current state, so the series needs no archive: it is read at the
  pinned block (1.3). But a pinned block was re-read for only 9 minutes, and
  whether it can be re-read later is unmeasured. Failover is built (1.3) with
  nothing to fail over to. A failover endpoint with archive access is
  unverified.
- **Catch a counterfeit that is inside the registry, or one that clones the
  proxy with its own beacon, except via the registry** (F0.8.5). Neither is
  testable.
- **Know Bankr's or the RPC's rate limit.** Bankr returned no limit headers
  (F0.10.5). The RPC refused a batch of 100 with a bare 429 and no
  `Retry-After` (1.3), but its actual limit is unknown. So 1.3 and 1.5 back off
  on a bare 429.
- **Book the 6 bps that left the 0.10 sale unaccounted for** (F0.10.4). It is not
  a Phase 1 input, but it is the first thing 5.3's reconciliation will meet.

---

## Re-evaluation gate

At the end of Phase 1, before detailing Phase 2, we answer:

1. Is the snapshot rich enough for an analyst to be worth paying for?
2. Did anything Phase 1 measured change the marking, veto, or universe
   decisions, the way Phase 0's findings did (0.4 and 0.8 checkpoints)?
3. Does the paper/live split change what the demo is? The live-leg asset
   itself was decided at 0.11: ETH→USDG on 4663, proven for one sell, with the
   return leg still unexercised.
4. What did Phases 0 and 1 actually cost in time, and what does that imply for
   the remaining seven?
