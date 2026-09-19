# Build log

One entry per unit, appended as the build proceeds. Written to be skimmed: scan
it top to bottom and watch the system being assembled.

Each entry is a single paragraph of at most three sentences — what was built,
what the artifact is, how it was verified. Unit numbers are `<phase>.<unit>` and
match [planning/ROADMAP.md](../planning/ROADMAP.md); units marked ▶ there are playtime checkpoints,
and their entry records what was shown and what was decided.

The honest counterpart to this file is [LESSONS.md](LESSONS.md), which records
what went wrong and what changed as a result.

## Entry format

```
## <phase>.<unit> — <short description>
**Date:** YYYY-MM-DD · **Commit:** <sha>

<One paragraph. Three sentences maximum. No bullets, no sub-headers.>
```

---

## 0.0 — Onboarding: plan read, tracker established
**Date:** 2026-09-17 · **Commit:** bbe824e

Read planning/PLAN.md, planning/REVIEW-RESPONSE.md, planning/ROADMAP.md, planning/PHASE-0-1.md, planning/CODEBASE.md and the
seven discovery reports in `research/`, then created `tracker/` and rewrote
README.md from a placeholder into a judge-facing overview. Recorded fifteen
decisions and plan changes in LESSONS.md, the largest being that the operator is
US-based, so tokenized-stock execution is unavailable and stock legs are paper.
planning/PLAN.md v2 and planning/REVIEW-RESPONSE.md were absent at the start of the session and
supplied during it; planning/PLAN-v1.md was superseded and removed.

## 0.1 — Repo skeleton and credential redaction
**Date:** 2026-09-17 · **Commit:** bbe824e

Built the target tree from planning/CODEBASE.md — package at `src/fund/`, a
placeholder module for every file the tree names —
plus the three modules that carry real code: `credentials.py` (the planning/PLAN.md §6
table as the single source of truth, with a role on every row), `redaction.py`
(denylist derived from that table; a filter masks message and arguments, a
formatter masks the formatted record including tracebacks) and `config.py`
(role-scoped access, so an analyst asking for `BANKR_KEY_EXEC` raises rather
than returning it). The artifacts are `make test`, `make check-env`,
`.env.example` as a manifest with no values, and `config/`, where every
unresolved value is explicitly null and null blocks the check that reads it.
Verified by `tests/test_redaction.py`, 25 tests passing offline, the
load-bearing one adding a credential that did not exist when `redaction.py` was
written and asserting it is masked anyway.

## 0.2 — Auth headers and key permissions
**Date:** 2026-09-17 · **Commit:** 692c58e

Built `probes/_capture.py`, a stdlib HTTP harness that masks every declared
credential before returning anything and turns a transport failure into a result
rather than an exception, and `probes/keys.py`, which calls one read endpoint on
each of the wallet, gateway and agent surfaces with `X-API-Key` and again with
`Authorization: Bearer`, for each key plus a never-issued key as a negative
control. The artifact is `research/findings.md` §0.2 — seven findings from 20
read-only requests, each marked measured, documented or inferred — with raw
captures in the gitignored `probes/out/keys.json`. Verified by the control
returning 401 on all three surfaces, which is what makes the 200s evidence of
authorization rather than of a surface ignoring the header, and by checking that
no declared credential value appears anywhere in the findings file.

## 0.3 — Quote shape
**Date:** 2026-09-17 · **Commit:** ebfded4

Built `probes/assets.py`, which pins candidate addresses from the CoinGecko
discovery list with their provenance and reads `decimals()` on chain for each
before use, and `probes/quote.py`, which posts `/wallet/swap-quote` for USDG into
AAPL, NVDA and TSLA at both $5 and $25; the request schema came from the Bankr
docs because the endpoint answers every malformed body with an identical
`{"message":"Invalid request body"}`. The artifact is `research/findings.md` §0.3
— six findings, each bounded by an explicit sizing caveat that this is a shape
probe against an empty wallet and that unit 1.5 must re-run it once funded — with
captures in the gitignored `probes/out/quote.json`. Verified by three independent
sources agreeing that USDG is 6 decimals against two documented sources that say
18, by all 12 documented response fields being present in all 6 responses, and by
checking that no declared credential value appears in the findings file.

## 0.4 ▶ — Chainlink equity feeds, coverage, and the multiplier
**Date:** 2026-09-18 · **Commit:** 5f3ac1b

Built `probes/feed.py` in four steps — enumerate the reference directory in
full, ask GeckoTerminal for coverage before asking about divergence, read
`latestRoundData`, `decimals` and `uiMultiplier` for 33 tickers at one pinned
block, then compare using the 23 tokens whose multiplier is exactly 1.0 as a
control group for the noise floor. The artifact is `research/findings.md` §0.4 —
eight findings, captures in the gitignored `probes/out/feed.json` — of which the
headline reverses the previous session's own observation: 35 of the 57 feeds are
equity feeds, so `planning/PLAN.md` §11 survives, and GeckoTerminal covers 32 of
32 tokens because tokenized stocks do have AMM pools, which §13 stated they did
not. Verified by falsifying the block pin directly rather than assuming it (a
feed read at block 1 returns nothing), by recomputing every selector from its
signature, and by the control group, which is what forced the multiplier
question to be recorded **unresolved** — at 22 bps against a 142 bps noise floor
the probe cannot see the effect it was built to measure.

## 0.5 — Execution eligibility
**Date:** 2026-09-18 · **Commit:** a4fe453

Built `probes/execute.py`, the only probe that spends: it refuses to send
without `--confirm`, refuses to send at all if the 4663 native balance is below
the sell amount plus a gas reserve, and narrows the seven documented 403 causes
to three *before* spending — a free quote rules out the banned-token and
price-impact causes, the $0.26 size rules out the spend limit, and the
fee-beneficiary cause is structural. One attempt was sent once, selling 0.0001
ETH into AAPL from `0x93fa…a3da` on chain 4663, and returned **403** in 115 ms:
`{"message":"Tokenized stocks (AAPL) are not available in your region."}` — the
expected verdict, now measured rather than documented, with the body naming both
the gate and the asset. The artifact is `research/findings.md` §0.5, five
findings with the refusal verbatim; verified by the wallet's native balance
being identical to the wei before and after and no `hash` in the response, so
the gate fires pre-broadcast and costs no gas, and by four separate confounds —
balance, address, price impact and spend limit — each being excluded by evidence
rather than assumed.


## Testnet — can chain 46630 host an execution demo?
**Date:** 2026-09-18 · **Commit:** 0d36743

Built `probes/testnet.py`, an out-of-order read-only probe run because 0.5 closed
the mainnet stock gate and testnet was still open at the Phase 1 gate: it
establishes the endpoint is live and advancing before drawing any negative from
it, then answers the three questions from an issuer deployment list rather than
a sample — the trap 0.4 fell into. The artifact is `research/findings.md`
§Testnet, six findings, with captures in the gitignored
`probes/out/testnet.json`; the headline is that `GET api.robinhood.com/rhj/assets`
returns 194 assets whose deployments are **all** on chain 4663 and none on
46630, while five equity-named tokens on testnet nonetheless run the issuer's own
`Stock` contract behind an EIP-1967 beacon. Verified two ways that do not share a
failure mode — the issuer registry and an exhaustive same-address check over all
194 issuer addresses plus 187 discovery-list tokens and 35 feed proxies, none of
which has code on testnet — with a positive control on `eth_getCode` (20 of 20
recently-touched addresses have code) and a positive control on the Chainlink
directory (`feeds-ethereum-testnet-sepolia.json` returns 60 feeds, so a 404 on
the Robinhood testnet spellings is absence and not a wrong guess).


## 0.6 — Credits and usage
**Date:** 2026-09-18 · **Commit:** 0d36743

Built `probes/credits.py`, which reads `GET /v1/credits` and `GET /v1/usage` with
`BANKR_LLM_KEY` across six `days` values, carrying forward probe 0.2's two
controls — an invalid key, refused 401 on both endpoints, and `BANKR_KEY_READ`,
refused 403 with the gateway toggle named — because a 200 is only evidence of
authorization if something is refused. The artifact is `research/findings.md`
§0.6, six findings with both raw shapes recorded as returned rather than as
documented; the verdict is that `planning/REVIEW-RESPONSE.md` finding 13 is
confirmed and `planning/PLAN-v1.md` §4's "balance is not programmatically
readable" is refuted, but attribution stops at an (API key × model × day-window)
aggregate with no per-request row and no request id, so per-analyst cost stays an
estimate. Verified that the probe cost nothing by reading `balanceUsd` before and
after all thirteen calls — 2.825608 both times, delta 0.0 — and by confirming no
declared credential value appears in the findings file.


## 0.7 ▶ — x402 round trip
**Date:** 2026-09-18 · **Commit:** 906041c

Checked first that no endpoint already existed on this wallet (`stockwatch` is
gone), then deployed `probes/x402/roundtrip/index.ts` — a handler that returns a
frozen literal and does no work, so the timings measure the platform rather than
our code — at $0.001 USDC on Base, and ran `probes/x402_roundtrip.py`, which
prints the endpoint, price, wallet and RPC-read balance before it is allowed to
pay. The artifact is `research/findings.md` §0.7, six findings with the full 402
challenge verbatim; **the paid call failed** — `x402 payment failed (status 500)`
after 2,849 ms — so the probe stopped without retrying or adjusting the price,
and the cold and warm timings do not exist. What it did establish is that the
challenge advertises `x402Version: 2` and `network: "eip155:8453"` while the
latest published `x402` is 1.2.0 with `x402Versions = [1]` and a closed network
enum containing `base` but not `eip155:8453`, so no standard client can pay us;
that `payTo` is a shared Bankr contract rather than the fund's wallet; and that
`/wallet/portfolio` reported `tokenBalances: []` for Base while USDC `balanceOf`
returned $0.108346. Verified nothing was spent — USDC identical before and after,
0 requests and $0 earned on the endpoint.


## 0.7b/c — The payment failure, separated; revenue and portfolio probed
**Date:** 2026-09-18 · **Commit:** 1c22f32

Built `probes/x402_thirdparty.py`, which paid a third-party endpoint once at the
same $0.001 as our own — deliberately not the marketplace's cheapest, since one
base unit would have changed the amount as well as the owner — and it **settled**
(200, 4,589 ms), so the client, wallet and facilitator all work and 0.7's 500 is
specific to our endpoint; the mechanism stays unresolved, and a settlement found
on chain where payer and owner are the same address weakens the self-payment
explanation and points at our hand-written deploy config instead. Reading the
settlement transaction **corrected our own F0.7.6**: `payTo` is
`BankrFeeRouterV2`, a verified pass-through splitter, and the seller's share
moves to the seller's own wallet in the same transaction, so revenue is an
on-chain receipt and `planning/PLAN.md` invariant 9 is satisfiable as written —
with `PaymentSettled(token, payer, owner, …)` carrying gross, net and fee, and
`owner` indexed so every sale is queryable by our address. Built
`probes/portfolio_check.py`, which shows the portfolio endpoint reporting native
balances identical to the chain while returning an empty `tokenBalances` for
every ERC-20 the wallet holds, eliminating staleness as the cause; F0.2.6's "the
wallet is empty" still stands on the transfer history, though the evidence it was
originally drawn from never supported it.


## 0.7d — The endpoint fixed, and which hypothesis was right
**Date:** 2026-09-18 · **Commit:** 7d5d1ae

Read the endpoint's logs first — the CLI has no `logs` command, so the path came
from the installed CLI's own endpoint list — and they refuted the task's leading
hypothesis outright: the handler **ran and threw** `fetch() did not return a
Response`, so the platform had routed the request, priced it and accepted the
payment authorization, and the deploy config was never at fault; `bankr x402
revenue` showing 0 requests had been a filter artefact, since only settled
requests are counted. Diffing the hand-written config against `bankr x402 add`
plus `configure` driven through a pty confirmed it field by field — the wizard
sets nothing we lacked that mattered, currency and network being inherited and
`paymentScheme` defaulting to the `exact` the live 402 already advertised — while
the real divergence was the handler, ours returning a plain object where the
platform's own scaffold returns `Response.json(...)`. Changing only that, the
payment settled: `PaymentSettled` with the fund as `owner`, verified on chain
rather than from the 200, which is the first revenue evidence this project has
produced, alongside a real cold start of ~513 ms and an `x-402-payer` header that
turns out to be a bare payer address the handler cannot verify, since `X-PAYMENT`
is not forwarded. Three self-payments, all fee-free and netting to zero, so the
unit cost nothing.


## 0.8 — Asset identity
**Date:** 2026-09-18 · **Commit:** 7581628

Built `probes/identity.py`, which snapshots the issuer registry with its own
provenance — the endpoint carries no version, no `ETag` and no `Last-Modified`,
so the snapshot's sha256 and fetch time have to serve as the version invariant 8
asks for — and then runs five candidate checks against nine candidates, six of
which the checks are supposed to admit, because a check only ever pointed at
things it obviously catches proves nothing. The artifact is
`research/findings.md` §0.8 with the full matrix; the finding that needed the
whole matrix is that **feed presence admits both GME counterfeits**, since a feed
exists for the ticker and a forger picks its own ticker, so it carries no
identity weight at all while remaining required for markability — a separation
CRM demonstrates, being genuine, registry-listed, beacon-backed and correctly
unmarkable. Verified beacon resolution on **mainnet** rather than inheriting the
testnet result, and swept both available populations exhaustively — 194 of 194
registry assets sit behind the issuer's beacon and 187 of 187 marked
discovery-list addresses are admitted by both checks, zero disagreements in 381
addresses — which is recorded as *no evidence separating them* rather than as the
beacon earning its place. The conclusion is that registry membership keyed by
`(chain_id, address)` is necessary and sufficient, `uiMultiplier()` and the name
marker are dropped, and the beacon is worth keeping only as an independent trust
root that should fail a cycle loudly if it ever disagrees.


## 0.9 — Analyst cost
**Date:** 2026-09-18 · **Commit:** 498237b

Built `probes/llm_cost.py`, which runs one rough price-trend brief over six
assets hand-assembled from real 0.4 numbers against `claude-sonnet-5` and labels
every figure it emits a floor, because PHASE-0-1 relocated this unit to 1.7
precisely on the grounds that snapshot bytes dominate the count and no snapshot
exists until 1.6. The artifact is `research/findings.md` §0.9 — 1,793 input
tokens, 982 output, **$0.013406** and **58,070 ms** for one call, which multiplies
to $0.067 per five-call cycle and $2.01 per thirty days, against an extrapolated
~$0.117 per cycle once the universe is the 35 markable assets rather than six.
Verified three ways that agree to the last digit — the published rate, the
response's own `usage` block and the credit balance — and cross-checked against
`/v1/usage`, which is where the unit found what it was not looking for: the
aggregate was observed going **backwards**, reporting 0 requests then 1 then 0
then 2, so a before/after delta around a single call is not a sound
reconciliation technique and 6.3 must compare settled windows instead. Two
further incidental findings: the first attempt was cut off client-side by
`_capture`'s 20-second default and **was billed anyway**, so a timed-out analyst
call is a cost with no report; and two identical calls at temperature 0 returned
864 and 982 output tokens, corroborating the invariant 6 rewording by measurement
rather than argument. Latency rather than cost is the binding constraint, and
model choice swings the monthly budget 139× across the 68 models the gateway
lists.


## 0.7e — Who can pay us: the x402 client gap
**Date:** 2026-09-18 · **Commit:** 0adc360

Built `probes/x402_clients/`: pinned, unpatched copies of the v1 client
(`x402-fetch` 1.2.0) and the v2 client (`@x402/fetch` 2.26.0), driven against a
byte-for-byte replay of our live 402 that refuses any paid request. The replay
showed four things: the v1 client, which is the one Bankr's own docs recommend,
fails on the network identifier alone; a buyer-side adapter reaches signing
without breaking the signature; Bankr's CLI implements no x402 and pays
server-side through an undocumented `/wallet/x402-pay`; and the v2 client, which
F0.7.3 never looked at, reaches signing unmodified. The artifact is
`research/findings.md` §0.7e, which opens with a verdict table. The one
authorised payment went through the unmodified `@x402/fetch` and settled,
verified on chain by `PaymentSettled` and by USDC's `AuthorizationUsed`
carrying the exact nonce the client signed, which refutes F0.7.3's headline and
narrows the honest claim to "payable by any x402 v2 client and by Bankr users" —
with the non-Bankr buyer inferred rather than measured, because the signer was
the fund's Bankr-custodied EOA, and a net spend of $0.00.


## 0.10 — Idempotency and rate limits
**Date:** 2026-09-18 · **Commit:** fa272d0

Built `probes/idempotency.py`, which made the wallet's first transaction on 4663.
It sold 0.00003 ETH (~$0.08) into USDG with `BANKR_KEY_EXEC`, then sent the
identical body with the same `idempotencyKey`. The repeat returned the original
result in 178 ms and the chain shows one fill, which also settles F0.5.5: the
execution key can transact. Built `probes/idempotency_evidence.py` after the
probe's own verdict came back "transacted: False". The swap had arrived as a
gas-sponsored ERC-4337 UserOperation inside an EIP-7702 transaction from a
bundler, which delegated the fund's wallet to a Bankr contract on 4663, so
`tx.from` and the nonce the probe trusted described the bundle and not our swap.
Built `probes/ratelimit.py`, whose 150 reads in 4.1 s drew no 429 and no
rate-limit header, recorded as a lower bound. The artifact is
`research/findings.md` §0.10, with the in-flight `409` path and the 6 bps missing
from the sale left **unresolved**.


## 0.11 ▶ — Phase 0 exit summary
**Date:** 2026-09-18 · **Commit:** 70fd168

Consolidated `research/findings.md` into a Phase 0 exit summary at its head. It
gives one row per probe with its question, method, result, confidence and
verdict, and marks 0.4 and 0.10 half met rather than rounding them up. It lists
twelve assumptions that died, the five config values a probe was named to
resolve and did not (`feed_staleness_max_seconds`, `quote_max_age_seconds`,
`impact_max_bps`, `worker_deadline_seconds`, `analyst_model`), and the open
decisions. Before it, the plan docs were brought back into agreement with the
record: eleven LESSONS entries dating from 09:10 and three from before it were
folded, and two operator decisions were recorded — the snapshot carries price
history, and the buyer client is `@x402/fetch` 2.26.0. One contradiction (PLAN
§11's v1-client reason for selling on Base) and one gap (how staleness rules
bind a price series) are marked and not reconciled. **Shown and awaiting the
operator: nothing at this checkpoint has been decided yet, including the
live-leg asset.**


## Phase 1 replan — units rewritten against the Phase 0 record
**Date:** 2026-09-18 · **Commit:** 221e747

Recorded the four 0.11 checkpoint decisions in LESSONS:
- freshness binds a series' newest point;
- five config values, provisional, with the staleness margin still unset;
- ETH→USDG is Phase 5's live leg;
- §11 stays contradicted.

The config values were set in `config/`. Then every Phase 1 unit in
`planning/PHASE-0-1.md` was rewritten against the record: no unit was added or
removed, and each names the findings that changed it. The artifact is that
section, ending in a twelve-item list of what Phase 1 still cannot do. The
record overruled three drafted or briefed assumptions: 1.5 does not need a
funded wallet (F0.3.3); 0.8's registry hash cannot be re-verified, so 1.2
re-fetches raw bytes into `config/registry/`; and a failover RPC with archive
access is unverified, since the configured endpoint is the public one.


## 1.1 — Types
**Date:** 2026-09-18 · **Commit:** 1665fcf

Built `src/fund/core/types.py`, stdlib only. Its one serialisation is canonical
JSON: floats are refused both ways, and integers that can pass 2**53 are
encoded as strings. On top of that it defines:
- signed fixed-point quantities with no default decimals;
- `(chain_id, address)` identity;
- three-valued checks;
- an `Observation` whose fetch status keeps "unreachable" apart from "false";
- a `Series` whose freshness is judged on its newest point;
- an `Asset` that keeps identity, markability and the beacon as three verdicts;
- a signed, nullable `Quote`;
- a `Holding` that is never silently valued at zero;
- a hash-stable `Snapshot`;
- an `Order` attributed through the UserOperation's sender and `Transfer` logs,
  never a bundler's `from` or the wallet nonce.

The artifact is that module, with `tests/test_types.py`: 54 tests, built from
recorded data — CRM's registry record, the real GME counterfeit, probe 0.3's
TSLA quote, a Chainlink round id above 2**53, and the 0.10 swap read back from
its receipt. They prove a byte-stable round trip, and that all five measured
cases coexist in one hashed snapshot. The unit was narrowed on the record's
evidence: six listed containers wait for the units that design them. Building
`Quote` from the recorded bytes also showed that the quote response mixes human,
raw and lossy amount formats, a refinement of F0.3.2 recorded for 1.5.


## 1.2 — Universe
**Date:** 2026-09-18 · **Commit:** e3e294a

Built `src/fund/core/universe.py` and pinned `config/registry/`: the issuer
registry and Chainlink's directory stored as raw bytes named by their sha256,
through the unit's own plan–store–accept refresh path. The fresh registry
hashes to exactly the `442718b5…` 0.8 recorded, so that version is now verified.
The module also has:
- identity, standing and markability as separate checks;
- a beacon cross-check that raises on disagreement;
- `held_asset()`, which never refuses;
- a feed map keyed by address, which is the one place a name meets an address,
  because the directory carries no token address.

The artifact is that module with 36 tests on the real pin, each refusal asserted
at its own rule:
- the real GME is admitted, and both counterfeits are refused at identity;
- CRM passes identity and is refused at markability;
- a changed byte is refused at the pin;
- a constructed disagreement stops the cycle;
- a constructed `DELISTED` status is refused at standing while the holding keeps
  its description.

The network reads — the registry fetch and the beacon slot — are adapter work
outside this unit's paths. The core takes their results as arguments. Several
folds and LESSONS entries are owed, listed in the state note below.

## 1.3 — Chain adapter
**Date:** 2026-09-18 · **Commit:** 807fbc1

Built `src/fund/adapters/chain_4663.py`, stdlib only: every read of 4663, as
`Observation`s and `Series` at one pinned block, each read addressed by hash.
It has:
- a JSON-RPC client with a whole-request deadline, failover that advances on a
  hang, pacing, and a doubling backoff on a bare 429;
- Multicall3 reads of feed rounds, decimals and balances, and paced
  beacon-slot reads for 1.2's cross-check;
- `require_one_block`, which refuses a mixed bundle at `block-pin`;
- a freshness verdict per feed: its heartbeat plus the margin, judged at the
  block's time, on the newest point only;
- a seven-day series of the feed's own rounds, whose `coverage` says when it
  is short.

The artifact is that module with 39 offline tests. They run against a fake
chain that speaks the real `aggregate3` ABI, and every rule was mutated and
caught. `--prove` was run live at block 66652203:
- 37 feeds fresh, and read identically twice;
- 35 of 35 beacons agreeing with the issuer's;
- AAPL's week-old oldest point stale on its own, while its series judges fresh;
- a real two-block read refused;
- a refused socket read as undetermined;
- a silent socket passed over in 3.2 s.

Measuring as it went, the unit found every equity feed silent for 48–59 h over
a weekend, against a 25 h rule. That finding and four others are in LESSONS.

## 1.3 close-out — one decision recorded, one stopped
**Date:** 2026-09-18 · **Commit:** 09409fe

**Recorded.** The operator's decision that the feed staleness comparison stays
in the chain adapter, as a named exception to "gates exist once" in CODEBASE §3
and PLAN §2 invariant 4. The decision's "1.8" is marked open, because
`gates.py` is 3.4's.

**Stopped.** The weekend-staleness decision is not recorded, as instructed. It
depended on the verdict naming the market session, and the verdict names only
the feed's schedule label. Nothing on record says when that schedule is open.

**Already there.** The four owed 1.3 entries were already in LESSONS from
`c551edc`, so none was rewritten. The state note below replaces the one written
at 1.3's close.

---

## 1.4 — Price cross-check
**Date:** 2026-09-18 · **Commit:** 6200d18

Built, on two operator decisions recorded first: `adapters/http.py`, the shared
transport lifted from 1.3 (GeckoTerminal's measured `Retry-After: 0` read as
no hint); staleness in open-session time, with the closed session (Sat 00:05Z
to Sun 23:55Z) inferred by `chain_4663 --sessions` from 86,606 rounds over
twelve weeks; `adapters/gecko.py`; and `core/valuation.py`, whose `value()` is
the only place a quantity becomes USD, whose `mark()` takes only the fresh
answer of the feed pinned to the asset's address, and whose `cross_check()`
excludes below the $1M line and vetoes past 100 bps above it. The artifact is
`python -m fund.adapters.gecko --prove` at block 66689567, inside the closed
session: all 35 markable stocks carried a mark, corroboration, divergence,
volume and tier; 19 passed, 15 fell below the line, MSTR was vetoed at
−122.87 bps on $4.76M and the recorded AMZN case at −499.47 bps; USDG marked
at $0.99995, CRM was carried with no value, and a removed GeckoTerminal entry
was undetermined at `corroboration`. Verified by 78 new offline tests, each
refusal asserted at its own rule, and by 1.3's `--prove` matching its pre-move
output line for line after the HTTP move; replayed over history, the new
staleness rule is stale only on the two holidays in range, and the tier's
comparisons sitting outside `gates.py` are recorded open.

---

## 1.5 — Quote adapter
**Date:** 2026-09-18 · **Commit:** 629ed14

Recorded two operator decisions first, then built `adapters/bankr_quote.py`.
The decisions: in a closed session, divergence is a finding carried to the
decision record, not a veto (recorded and folded, and owed in
`core/valuation.py`, which was outside this pass); and the threshold
comparisons in 1.3, 1.4 and 1.5 are named exceptions that 3.4 sweeps into
`gates.py`. The adapter runs on the shared transport, read-only under the
analyst role. Its decimals come from the pins and are checked against the
response, its four number formats are converted exactly, absent stays null,
and its `tradeability()` names its rule (`quote`, `size`, `quote-age` or
`impact`), compares `swapImpactBps` signed, and carries `executable` as
undetermined on every verdict. The artifact is
`python -m fund.adapters.bankr_quote --prove` at Sat 01:52Z: all 35 markable
stocks were quoted at 25.001227 USDG ($25 at USDG's own mark); 31 were
tradeable, four of them admitted at negative impact; four were refused at
`impact` at the nominal size; a tradeable quote was refused at `quote-age`
after 64.6 s; the venue's HTTP 500 "No quote available" was refused at `quote`;
and a dead port was undetermined there. Verified by 39 offline tests, six rule
mutations each caught, and a subprocess check that importing the module loads
no `bankr_exec`, treasurer or signing module; at 25,000 USDG the two impact
fields still never differed, up to 7,084 bps against the venue's own 1,500 bps
cap.

---

## 1.6 ▶ — Snapshot builder
**Date:** 2026-09-18 · **Commit:** 65b3495

Built `core/snapshot.py`, which turns the typed readings and the adapters'
verdicts into one readable document, hashed as the bytes on disk. It replaces
1.1's `Snapshot` type, whose encoding was 831 bytes a series point. Alongside it:
- `run/snapshot.py`, the live read, decided as the seam where the adapters
  meet core;
- the two owed `valuation.py` changes: a closed-session divergence is now a
  finding carried in the entry, and the docstring names the tier's
  comparisons a named exception.

The artifact is `fixtures/live/snapshot-4374db7b….json`, at block 66716733,
Sat 02:13Z: 347,648 bytes; 35 assets, each with its four admission rules,
mark, corroboration, quote, findings, named status, and a timeline of
`[updated_at, price_usd]` pairs, 4,753 rounds in all; 20 tradeable, 15 below
the line, 20 closed-session findings, three of them past 100 bps; CRM among
the 159 listed outside the universe. It was verified by 25 offline tests, each
refusal at its rule, with seven mutations each caught. A fresh chain re-read at
the same block rebuilt to the identical hash, and one nudged price changed it.
**Shown at the checkpoint and waiting for the operator: nothing has been
judged yet.**

---

## 1.7 — Analyst cost against a real snapshot
**Date:** 2026-09-18 · **Commit:** bcf1d81

After two changes to 1.6 — closed-session findings only past the open-session
limit, and an offline test of `run/snapshot.py` that found and fixed an unread
beacon on held stocks outside the universe — built `probes/analyst_cost.py`. It
embeds snapshot `7eba6212…` byte for byte, hash checked, and made four calls at
`claude-sonnet-5`: two identical analyst calls, one with the timeline removed,
and one risk call. The artifact is `research/findings.md` §1.7:
- $0.454 an analyst call (185,168 tokens in; 7,725 and 9,087 out; 62 and 75 s);
- $1.87 a cycle, $56 over 30 days, 28 times 0.9's floor, and 37 records at
  $0.05 to cover one cycle;
- the timeline, 66.8% of the input and 53% of a cycle;
- the timeouts: they cover these calls but are not sized for an uncapped reply
  at the slowest rate measured, with values recommended and not set.

It was verified by the credit balance and a settled `/v1/usage` window, which
agree with the listed price to the last digit ($1.080114 spent). The price
awaits the operator.

---

## 1.8 — Held-but-untradeable
**Date:** 2026-09-18 · **Commit:** ea8398f

Built on four decisions taken first:
- the price is raised to $0.25;
- the timeouts are set to 600 s and 630 s, with a 12,000-token output cap;
- daily closes over 30 days, adopted after measuring them at 94,716 input
  tokens and $0.264 a call against 1.7's 185,168 and $0.454, with reports as
  history-minded;
- a caching test, which found the gateway ignores cache control.

Two fixes came with them: the missing-state retry for `missing trie node`, and
a `history` rule so a short series is not tradeable, which was a separate
defect.

1.8 itself gives every holding row a `universe_status` and a `holding_status`
(owned, valued, exit). It closes the one quiet way out of the book: an asset
the registry drops while held is now written to `pins.json`'s `carried` list,
and its balance is still read.

The artifact is `tests/test_holdings.py`. It takes a held NVDA out of the buy
universe ten ways — the five the unit names, with identity in doubt both ways,
and four per-snapshot statuses — and each time the holding keeps its row,
balance and status, valued at its own mark or carried at null with a reason. It
was verified in four ways:
- the set of holdings is identical before and after every change;
- a test fails if a way-out status lacks a case;
- three mutations that drop or zero a holding were each caught;
- a live build at block 66750551 carried USDG and ETH with both statuses and
  rebuilt to the identical hash.

---

## Test audit — 354 cases cut to 313, and the boundary tests CODEBASE §3 promised
**Date:** 2026-09-18 · **Commit:** a535c17

Each of the 126 tests the audit called incidental was cut only if every
behaviour it checks, broken in a copy of HEAD, still failed a test that stays:
34 went, and 92 stayed as the only guard for something, with the audit's 8 kept.
Of nine tests that could not fail for their rule, five were fixed (the
multiplier on AMZN's 1.0, the chain settings, role scoping, the absent field,
the misnamed from_units test) and four dropped where another test carries the
rule, as were the four per-module purity tests. `tests/test_boundaries.py` adds
ten tests for recorded rules that had none — spend authority, core purity, one
signer, one gate and its three named exceptions, threshold literals, the timeout
order, `/agent/prompt`, the status order, several deployments — each shown to
fail with its rule broken, and none found a violation in `src/`.

---

## 1.9 ▶ — Fixtures and offline replay
**Date:** 2026-09-18 · **Commit:** a96f021

Built `adapters/cache.py`, which records every exchange and clock reading at the
transport the adapters already take, and gave `run/snapshot.py` a capture on
every live build and a `--replay` that rebuilds from a capture alone, from its
own config, the registry by hash and each source's clock tape, with every socket
refused; no adapter changed shape. The artifact is
`fixtures/snapshots/66812461-8afe38a38b03/`, 1.03 MB, committed after a check
for all six declared credentials: 189 chain, 2 GeckoTerminal and 35 quote
exchanges, 20,036 clock readings and snapshot `8afe38a3…`. `make replay`
rebuilds it byte for byte in 0.4 s inside a network namespace with no route and
no credentials, while a live build there fails at its first RPC call; a changed
byte in any source's answers changes the hash, and one the snapshot does not
carry fails the replay by name. **Shown at the checkpoint and waiting for the
operator.**

---

## 1.10 — Address selftest, after 1.9's checkpoint changes
**Date:** 2026-09-18 · **Commit:** 6c58156

At the operator's request the snapshot now names its capture's raw answers by
hash (schema /3, null with a reason when nothing was recorded), and the
committed fixture's snapshot was rebuilt from its unchanged answers as
`daafd945…`; the weekday capture waits for the feeds to reopen at Mon 00:00Z.
`make selftest` attests 235 addresses at one block (194 tokens by decimals,
symbol and beacon, 37 feeds by decimals and their own description, USDG, the
issuer beacon, Multicall3 and the wallet's 7702 delegate) and was green in
102 s over 204 requests, all HTTP 200, with no 429. With GME's address pointed
at the GameStop counterfeit it fails one row, named, at the beacon after passing
decimals and symbol, and each check, broken in a copy, failed a test.

---

## State at close — 2026-09-18, after 1.10

**Read this first.** This note describes the repository at the commit that last
changed it: run `git log -1 -- tracker/LOGS.md`. If `git log` shows later
commits, this note is older than the code, so read those commits before trusting
it. Where this note and git disagree, git is right.

**Check it in a minute.** Nothing here spends.
- `git log --oneline -15` and `git status -sb`.
- `make test`: 347 passed when this was written.
- `make replay`: rebuilds the committed capture offline, byte for byte, in
  under a second. Needs no credential.
- `make check-env`: which credentials are present, by name only.
- `make selftest` attests every address in config against the chain in about
  100 s. It needs the RPC URL and spends nothing.
- `make snapshot` builds a live snapshot in about 2.5 minutes, captures it
  under `fixtures/live/captures/`, and replays it; `python3 -m
  fund.run.snapshot --prove` also re-reads the chain at the same block.
- `probes/analyst_cost.py` **spends** with `--confirm`, in its default,
  `--one` or `--cache` mode.

### Done, through 1.10
- **Phase 0, the Phase 1 replan, units 1.1-1.8, the test audit, 1.9 with the
  operator's changes from its checkpoint, and 1.10.**
- **Decisions this far into Phase 1:**
  - staleness in open-session time, with sessions inferred from rounds;
  - the shared `adapters/http.py`;
  - closed-session divergence is a finding, only past the limit;
  - three named threshold exceptions, which 3.4 sweeps into `gates.py`;
  - the live read lives in `run/snapshot.py`;
  - the price is $0.25, provisional;
  - the timeouts are 600 s and 630 s, with a 12,000-token output cap;
  - the series is daily closes over 30 days, adopted on measurement;
  - captures are recorded at the transport, and the repository keeps them in
    `fixtures/snapshots/`;
  - the snapshot names its capture's answers by hash.
- **The whole of what is built.** Under `src/fund/`: `config.py`,
  `credentials.py`, `redaction.py`, `core/types.py`, `core/universe.py`,
  `core/valuation.py`, `core/snapshot.py`, `adapters/http.py`,
  `adapters/chain_4663.py`, `adapters/gecko.py`, `adapters/bankr_quote.py`,
  `adapters/cache.py`, `run/snapshot.py` and `run/selftest.py`. Every other
  module is a stub; `grep -l "Not yet built" -r src/` lists 28.

### The numbers that stand
- **Snapshot:** schema `openfund.snapshot/3`, about 189 KB with 763 daily
  closes. The committed one is `daafd945…` at block 66812461, rebuilt from the
  capture whose live build was `8afe38a3…`, in `fixtures/snapshots/`.
- **Selftest:** 235 addresses, about 102 s and 204 requests, set by 500 ms
  pacing. No 429.
- **Analyst call:** $0.264 at Sonnet 5, uncached (§1.8a).
- **Cycle:** about $1.11, $33 over 30 days, covered by 4.4 records at $0.25.
- **Caching:** not honoured by the gateway, measured.
- **LLM credits:** $0.937148 left, after 1.7 and 1.8 spent $1.862828.

### Next: the weekday capture, then unit 1.11
- **The weekday capture is owed** (1.9's checkpoint). It waits for the equity
  feeds to reopen at Mon 2026-09-21 00:00Z, ideally 13:30–20:00Z. To take it:
  - run `PYTHONPATH=src python3 -m fund.run.snapshot --capture
    fixtures/snapshots`;
  - scan the capture for every declared credential value, `set-cookie`,
    `X-API-Key` and `Authorization`;
  - commit it beside the weekend capture, which stays.
- **Not answered from 1.9's checkpoint:** how much of the demo runs from
  fixtures and how much live.
- **1.11, skew rejection,** is not started.

### Open items, none resolved
1. **Owed in code:** two `http.py` changes (LESSONS preamble).
2. **The daily cut's daylight saving.** 20:00Z is 16:00 New York only in
   daylight time. The closed span needs re-deriving after 2026-11-01.
3. **Holidays fail closed,** by decision. Daily closes skip them honestly.
4. **Exit is not assessed** for ETH and stocks: no sell quote is read in
   Phase 1.
5. **One daily-close call** was set against 1.7's two. The report-shape proxy
   is not a grade.
6. **Caching in other request shapes** is untested.
7. **About 37–50% of billed analyst output does not appear in the reply,**
   inferred to be hidden reasoning.
8. **AMZN's GeckoTerminal price alternates** between two levels; unresolved.
9. **$25 is sized at USDG's Chainlink mark,** a 1.5 choice for the operator.
10. **The quote-age budget.** The oldest quote was 21–25 s old at `built_at`.
11. **Nine feeds describe themselves `RH<ticker> / USD` on chain,** against
    F0.4.1's `Robinhood <TICKER> / USD`. `research/findings.md` is not
    updated (LESSONS).
12. **Unchanged:** paused-oracle detection; the unowned registry refresh fetch;
    six types waiting for 2.1-6.1; one RPC endpoint; which impact field gates;
    the stale README line 9.

### Config
- **Changed in 1.10's pass:** `mandate.json` pins
  `execution_wallet_delegate_4663`, the wallet's 7702 delegate.
- **Changed in 1.8's pass:**
  - `models.json`: `max_output_tokens` 12000, transport 600 s, worker
    deadline 630 s;
  - `chain.json`: `series_sampling` `daily_close`, window 30 days, 5,000
    rounds, cut 20:00Z;
  - `registry/pins.json`: an empty `carried` list.
- **Still null, which blocks whatever reads it:**
  - `cadence.json`: `confirmation_depth`, `cycle_deadline_seconds` and
    `retry_budget_per_worker`;
  - `models.json`: `risk_model` and `context_budget_tokens`;
  - `thresholds.json`: `max_position_weight`, `turnover_max_bps`,
    `cash_floor_usd` and `quorum_min_analysts`;
  - `mandate.json`: `cumulative_budget_usd`, `approved_by`, `approved_at`,
    `expires_at`, and an empty `allowed_assets`.

### Committed versus pushed
Checked locally, with no fetch. `origin/main` is `9e734fa`, 1.9 as shown at its
checkpoint; this session did not push it. Every commit after it, from
`8df6d7b` to the one that adds this note, is committed and **not pushed**. To
re-check, run `git fetch` and then `git log origin/main..HEAD`.

### What this note does not cover
- **Decisions.** It does not restate any in full; LESSONS holds them.
- **The plan.** PLAN, ROADMAP and PHASE-0-1 are the plan.
- **Credentials.** It checks none beyond `make check-env`'s names.
- **The remote.** Its check is one local read of the remote-tracking ref.
- **Unrecorded conversation.** Anything not written into `tracker/`,
  `planning/`, `config/` or `research/` is lost on restart.
