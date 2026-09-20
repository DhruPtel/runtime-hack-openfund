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

## 1.11 ▶ — Skew rejection
**Date:** 2026-09-18 · **Commit:** 0c071cc

Mixed blocks, an observation from after the pin, a stale newest point and a
holiday are each refused at their own rule, and a weekend and old history are
accepted. Breaking each guard in a copy found one gap: the builder's block-pin
was tested at one of the four places it checks, so one parametrized test now
attacks all four (350 tests). A replayed offchain body cannot be built from a
real source, since neither offchain body carries a source time, and a paused
feed is not refused, since to the fund it is silence like a closed market,
though every stock token answers `oraclePaused()` (all 35 false at block
66841212); both are open. **Shown at the checkpoint and waiting for the
operator.**

---

## 1.11's checkpoint, and the Phase 1 gate
**Date:** 2026-09-18 · **Commit:** 2d57446

Every stock token's `oraclePaused()` is now read at the pinned block, and a
paused feed is `no_mark` at its own rule, judged before freshness, with an
unreadable flag undetermined (schema /4; eight breaks, each caught); 1.9's
capture never recorded that read, so it was retired, not rebuilt, and a new
weekend capture, `66852293-253315c0e691`, checked for every credential, replays
byte for byte. The two decisions are recorded where they will be seen:
GeckoTerminal's `Date` is unchecked, with its fail-open direction in PLAN §13,
and the closed session is re-derived on Monday 9 November, not "Monday 3
November", which is a Tuesday. `planning/PHASE-1-GATE.md` answers the gate:
Phase 1's exit is met, the snapshot fully feeds one of four analyst seats,
Phase 5 stays in cut to one round trip, and 60 units remain at about 0.7 h
each, with 15 named to cut or fold.

---

## Simplification plan — Phases 2 to 8 at reduced depth
**Date:** 2026-09-19 · **Commit:** 57f9fda

Wrote `planning/SIMPLIFICATION.md` as a proposal for the operator. Every unit in
Phases 2 to 8 is kept, each with its minimal version, its full version and what
the minimal one gives up, marked H or L by the risk rule in `CLAUDE.md`. From
the record it:
- repoints the fourth seat to price integrity;
- builds the closed-session veto on the five divergence findings, where the
  venue sides with the market on AMD and MSTR and with the frozen mark on AMZN,
  GOOGL and SGOV;
- gives each agent its own read-only Bankr account, which pays for its inference
  but never transacts or signs.

It proposed five build stages, each ending in a state a judge could watch.

## The scope pivot, recorded across the plan
**Date:** 2026-09-19 · **Commit:** 25b3e39

LESSONS records the operator's approval of `SIMPLIFICATION.md` as analysis, and
seven decisions with it, each with its reasoning:
- minimal versions from Phase 2, with keys, signing and spend authority intact;
- two report vocabularies;
- the fourth seat as price integrity;
- five agent wallets from `bankr login siwe`, unverified;
- the live leg labelled a demonstration;
- a public preview with a paid full record;
- execution before the sale.

The six judging criteria are now in `planning/JUDGING-CRITERIA.md`.

The pivot is stated where PLAN §8's phase list begins and in `CLAUDE.md`. ROADMAP
gives every unit from 2.1 a minimal line. Contradictions are marked in place
rather than reconciled; the main ones are the 3.4 sweep, the public record in
PLAN §5, and the page arriving at 7.6, after four of the five stops.

SIMPLIFICATION's five-stage build order is marked superseded. The installed
CLI's help shows the SIWE path exists, but lists no LLM gateway option and
leaves the Agent API on by default, so the path stays unverified.

## Phase 2 plan — the swarm at minimal depth
**Date:** 2026-09-19 · **Commit:** 5de21a2

Wrote `planning/PHASE-2.md`, awaiting the operator: 2.1 to 2.8 at the approved
minimal scope, each with goal, build, artifact, done condition, risk and full
version. It adds 2.0 first, to prove one SIWE agent account can reach the
gateway before anything assumes five, because the installed CLI's source shows
SIWE never requests gateway access and would overwrite the fund's CLI session.
It sets the four values blocking 2.4 from measurement (1,800 s, 1 retry,
`claude-sonnet-5`, 70,000 tokens), keeps every other key out of each analyst
process despite `config.load()` merging all of `.env`, recommends pulling a
page slice forward to watch the swarm, and treats 2.1 as a stop against what the
pivot recorded.

## The 2.1 stop restored, and unit 2.0 added
**Date:** 2026-09-19 · **Commit:** f87d427

At the operator's word, 2.1 is a stop and always was, because the report format
is the product and is read before any code consumes it. It is restored to the
stop list in `CLAUDE.md`, PLAN §8, ROADMAP, SIMPLIFICATION and the gate report's
marker. The same pass added unit 2.0 to all four and corrected the context
budget to 70,000, which the earlier 60,000 figure had set without the risk
reply.

## 2.0 — SIWE agent wallet, proven once
**Date:** 2026-09-19 · **Commit:** a1db746

One account was made with `bankr login siwe` under a separate CLI config.
`probes/siwe/hook.mjs` fed the key in from a file and kept the login's own
answer, and `probes/siwe_agent.py` tested the new key by what it does. The
artifact is `research/findings.md` §2.0:
- its own address, `0x42a9…3d27`, a new Bankr wallet;
- a signature and a quoted swap each refused 403 "Read-only API key";
- `/agent/prompt` refused 403 "Agent API access not enabled";
- but **every gateway call refused 403 "does not have LLM Gateway access
  enabled"**, the body of the known gateway-off control, and the credit top-up
  refused at the same toggle.

Verified against a never-issued key (401 everywhere), with the agent wallet read
empty on every chain before and after, the fund's CLI config hashing the same
before and after, and neither secret in the working tree. $0 spent; the verdict
is that SIWE alone cannot carry the five-wallet plan, and the options are the
operator's.

## The fund's keys, identified by measurement
**Date:** 2026-09-19 · **Commit:** c6adedf

For the operator to match the dashboard, `probes/keymap.py` measured each `.env`
Bankr key with reads alone, plus a message-less sign that cannot sign:
- the wallet;
- the gateway, from `/v1/credits`;
- the Agent API, from `/agent/profile`, calibrated against the 2.0 key whose
  Agent API was measured off;
- read-only, from the sign request.

All three keys resolve to `0x93fa…a3da`:

| Key | Read-only | LLM gateway | Agent API |
|---|---|---|---|
| `BANKR_KEY_READ` | yes | off | on |
| `BANKR_KEY_EXEC` | no | on | on |
| `BANKR_LLM_KEY` | **no** | on | on |

Token launch is not measurable by any read. Two results contradict the plan's
unmeasured claims: `BANKR_LLM_KEY`, which the analyst role holds, is not
read-only, and the Agent API is on for all three. Recorded in LESSONS and PLAN
§6; no setting was changed.

## 2.1 ▶ — The report format, shown
**Date:** 2026-09-19 · **Commit:** aecf511

`planning/REPORT-FORMAT.md` holds four reports written by hand against the
weekend capture, one per seat, every figure cited to its snapshot field and
rechecked against the capture: two figures were corrected. They take two
vocabularies, a machine-read first line and `CALL` lines, at most six calls on
tradeable assets, silence or `NO CALLS` to abstain, three-word confidence, and
a "wrong if" per call. **Shown at the stop and waiting for the operator.**

## 2.2 — Report schema and validation
**Date:** 2026-09-19 · **Commit:** 5f108aa

Built `agents/schema.py`, stdlib only. It parses a report into what the
aggregator reads (seat, agent, snapshot; per call the address, word and
confidence) and refuses a bad report by a named rule, never an exception: header,
call shape, vocabulary, confidence, asset, coverage, no-calls, citation or
figure. The artifact is `tests/test_schema.py`, 31 tests
that parse the four approved examples straight from `REPORT-FORMAT.md` and catch
five fabricated figures, each named with its field and true value. The examples
also caught a wrong rounding rule in the validator: AMZN's 266.085 is correctly
written 266.08, so a figure now matches within half a unit of its last digit.

## 2.3 — The briefs
**Date:** 2026-09-19 · **Commit:** de1a6af

Built one versioned brief per seat under `agents/briefs/`, plus the shared
contract `analyst.v1.md`, and `analyst.render()`. The seat's question and the
questions it leaves to others come from `config/analysts.json` v2, and the
snapshot goes in as byte-identical text named by its sha256. `tests/test_briefs.py`
(17) shows four distinct questions, each seat speaking only its own vocabulary,
the same snapshot bytes for every seat, and the approved NVDA call as the shared
example.

## 2.4 — The runner
**Date:** 2026-09-19 · **Commit:** f38596f

Built `agents/runner.py`, `agents/analyst.py`'s worker and
`adapters/bankr_llm.py`:
- four analyst processes at bounded width, each environment built from nothing
  with only its own key;
- the key source a parameter, per agent or shared;
- per-worker and cycle deadlines, and pre-allocated result slots;
- one retry for a malformed reply, never for a timeout;
- a gateway client that makes one request per call;
- a check that refuses any treasurer key before anything starts.

`tests/test_runner.py` runs real subprocesses against a fake gateway on
127.0.0.1: one seat ok, one abstaining, one malformed and retried once, one
hung and not retried. The cycle completes, marked partial. Verified H:
- with isolation removed, every analyst could see `BANKR_KEY_EXEC`,
  `SIGNING_KEY` and the other agents' keys, and the test failed;
- six other guards, each broken in a copy, were caught by their own tests;
- nothing ran live.

## 2.5 — Cost accounting
**Date:** 2026-09-19 · **Commit:** 4b02ed7

Each call's cost now comes from its own usage block at the listed price
(`bankr_llm.cost`), and per call, per analyst and per cycle it is labelled an
estimate, with calls of unknown cost counted, not zeroed.
`adapters/bankr_usage.py` reads `/v1/usage` once, takes the window from the
provider's answer, and compares aggregate to aggregate only once the window has
settled, never as a before-and-after delta. `tests/test_cost.py` (10)
reproduces 1.8a's $0.264272 to the digit, and reconciles the recorded settled
window against its six recorded calls exactly: $1.105746.

## 2.6 ▶ — The first real analyst report
**Date:** 2026-09-19 · **Commit:** 8d5c026

With `BANKR_LLM_KEY` measured first as refused by the Wallet API and the Agent
API, the runner's new `--confirm` entry point sent one price-integrity call on
the committed capture: $0.273156, 78.6 s, 98,438 tokens in and 7,628 out, 77%
of the output reasoning. `research/findings.md` §2.6 holds the report unedited,
byte-identical to the recorded reply. It was refused on its first line, where
it filled the unassigned `0x…` with the fund's wallet, and on five correct
computed bps figures that 2.2's bps rule wrongly checks; no figure was
fabricated, and with the rule corrected in a scratch copy only the header
refusal remains. Judged a real view reached mechanically: the same five calls
as the hand-written example, thinner, and with two unsupported prose claims.
**Shown, and waiting for the operator.**

## After 2.6 — Display, the validator loosened, the entry point tested
**Date:** 2026-09-19 · **Commit:** eba2e75

`python -m fund.agents.show <cycle dir or result>` prints a stored report
exactly as the model wrote it, and every attempt now keeps its reply whole.
2.2's bps rule now checks a bps figure only when its line cites a field in bps,
and a seat with no wallet is written `unassigned`, never `0x…`. On the same
recorded 2.6 reply, kept in `tests/data/`, with no new call, the six refusals
became one: the header its old placeholder provoked, and with that token alone
restored the report is accepted. The runner's `main()` has its tests; 449 pass,
and no rule was added.

## 2.6, finished — The other three seats, one call each
**Date:** 2026-09-19 · **Commit:** 8de9a14

With the key measured first, as before, price-trend, cross-asset-macro and
execution-quality ran once each on the same capture, at 15:58:33Z.
`research/findings.md` §2.6, continued, holds the two reports unedited, with a
table and judgements.
- **Price-trend: refused, for errors that are its own.** A META address
  invented after its first 8 digits, GME's feed address given for the token,
  and a mis-dated GME close. It cost $0.273142 and took 83.3 s. Its NVDA call
  repeats the brief's own example, which comes from this capture.
- **Cross-asset-macro: no report.** The gateway returned HTTP 504 after
  113.3 s. It was not retried.
- **Execution-quality: accepted,** the first reply to pass. It cost $0.249594
  and took 58.2 s, and cautions MSTR only.

**Judged:** three different views; the fourth is untested. Both condition seats
caution MSTR on one gap.

## 2.7 — The report store
**Date:** 2026-09-19 · **Commits:** b417caa, db51f8d

`store/reports.py` keeps each report once. The file is named by the sha256 of
its canonical bytes and checked against it on every read. A different byte at a
known id raises, and nothing is rewritten.
- **The runner stores every reply that arrives,** accepted or refused, and puts
  its `report_id` on the seat's result. The live entry point writes to the
  gitignored `fixtures/live/reports/`.
- **The three real replies are stored,** each byte-identical to its recording:
  price-integrity `569d406…`, price-trend `9398838…` and execution-quality
  `1b9f7a7…`.
- **Minimal:** storage and retrieval only, with no query layer. 455 tests pass.

## 3.1 — Aggregator
**Date:** 2026-09-19 · **Commits:** a4c2bf6, 498f52e, 0d9b388, 7e11edf, 657833b

`core/aggregate.py` scores each asset direction × (1 − caution), with confidence
words at 0.25, 0.5 and 0.75, and moves the target from the weight held: a buy
raises it by score × the 0.25 position limit, a sell cuts it, and hold, silence
and caution alone keep it. Below the quorum of 3, when every seat abstains, or
with a limit unset, every holding is kept, and new buys are paid only from cash
above the $20 floor. `tests/test_aggregate.py` (11) runs the four approved
reports with a non-empty book for cycle two, and the boundary test now refuses a
comparison with any limit outside `core/gates.py`.

## 3.2 ▶ — The aggregation table, shown
**Date:** 2026-09-19 · **Commits:** 5b47867, d5560c9

`aggregate.table` prints, per asset, each seat's word and what it adds, the
direction, caution and score, and the weight moved from and to, in dollars of
the $200 paper book. Cash and the rounding residual close it. On the four
approved reports it gives META 12.5%, AMD, INTC and USO 6.25% each, and 68.75%
cash. Judged a cautious trend tilt a person could hold, but price-trend's view
with haircuts, and blind to co-movement (LESSONS 2026-09-19); shown, not
stopped.

## 3.3 — Planner
**Date:** 2026-09-19 · **Commits:** a1e782a, d577a52

`core/plan.py` values the paper book at the snapshot's marks through
`valuation.value()` and sizes each move into orders of at most $25, sells
first, with dust under $1 dropped. It writes each order with its fresh quote
exactly as fetched, the verdict `bankr_quote.tradeability` gave it at the
recorded `judged_at`, and the mark, corroboration, venue price and findings risk
reads. No live leg, which is Phase 5's. Verified H with the tests' fake venue,
labelled in every quote it makes: six rules broken in a copy and caught. The
sell guard went uncaught until a test gave the planner a proposal made on
another book.

## 3.4 — Gates
**Date:** 2026-09-19 · **Commits:** dbe3295, f7faf77

`gates.evaluate` checks each order:
- tradeable in the snapshot;
- allowed by the mandate;
- within the order size;
- the fresh quote's own verdict, and that the quote is this order's;
- position weight.

It checks the plan for quorum, cash floor and turnover, recomputing each figure
from the book and the orders. Null blocks, and an order clears only if every
gate passes. The mandate holds the capture's 20 tradeable assets and placeholder
approvals, provisional until 4.1. Verified H: seven rules broken in a copy and
caught. One was a limit compared inside `plan.py`, which the boundary test
refused.

## 3.6 — Context budget
**Date:** 2026-09-19 · **Commit:** e1d5213

Built before 3.5, as the batch brief ordered. `core/context.measure` estimates
risk's bundle from its bytes over 1.8, rounded up, plus the reply's
12,000-token cap, and `gates.context_budget` holds it to 70,000. Over budget,
no call is made and every order is vetoed. `tests/test_context.py` holds the
budget to the byte; the four approved reports' bundle is about 32,400 tokens.

## 3.5 — Risk agent
**Date:** 2026-09-19 · **Commits:** 5865108, ea1dab0, e95cf35

`agents/risk.py` calls `gates.evaluate`, measures the bundle, and asks the model
in its own process, from an empty environment, for a vote per order and
overall, with `briefs/risk.v1.md` as its prompt. An order is approved only when
every gate passed and the model approved both it and the plan. A missing, late,
refused or misshapen reply vetoes everything and is never retried, and a stored
reply replays without a call. Verified H on 2.4's fake gateway: six rules broken
in a copy and caught, among them the model overriding a gate and the child
inheriting its parent's environment. No real model has seen the brief.

## 3.7 — The signed decision record
**Date:** 2026-09-19 · **Commits:** 6381ff9, 96aee3f, b352463, 6663c16

`core/record.py` holds:
- the snapshot, every report, the config, and the proposal, plan, gates and
  risk reply, with the sha256 of each;
- every closed-session finding;
- each order approved or vetoed, by name.

Its only time is the plan's recorded `judged_at`. `treasurer/sign.py` signs its
exact bytes with ed25519, and nothing unsigned, altered or signed by another key
authorizes: three rules broken and caught. `python -m fund.run.decide` takes the
reports to a signed record, with the treasurer's own process signing, and
executes nothing. Offline, with the fake venue, scripted risk replies and a
scratch key:
- AMD was vetoed by risk and three orders approved;
- in cycle two, NVDA on hold and TSLA unmentioned were not traded, and a stale
  META quote was vetoed by `quote-age`;
- with no key the record was `signed: false` and did not authorize;
- the same inputs gave the same decision id.

## 3.8 ▶ — The exit run, and no veto: shown at the stop
**Date:** 2026-09-19 · **Commits:** f619d61, f2c457e, acde7f3

With the brief's example relabelled, four live calls ran on the committed
capture, one per seat, for $1.087706, and all four replied. Cross-asset-macro
answered in 89 s, with no 504 this time. All four were refused: no figure was
invented, but each report cited real values under the wrong path. Two of the
defects are the validator's own, and fixing them would rescue one report, not a
quorum. So the fund's real decision, signed with its key as `2c9c1a79…`, is no
rebalance: no order, no risk call and no veto (`research/findings.md` §3.8;
`fixtures/cycles/20260919T171351Z/`). **Shown, and waiting for the operator.**

## After 3.8 — Check by value, the validator's two faults, one brief line
**Date:** 2026-09-19 · **Commits:** 013257a, 60375c3, 45b4575, ff1bff4, df7cf74, d426bc8

`agents/schema.py` now:
- reads thousands separators;
- treats a bracket that is not a field reference as prose;
- accepts a real value cited under a loose reference, recording the imprecision
  in the parsed result and the signed record. A figure matching no value of the
  assets its line is about still refuses.

The shared brief gained its one line: name the other asset, and write the full
path. On the stored 3.8 replies, with no new call, three of four now pass.
Cross-asset-macro is still refused on `+(-0.09)%`. Six of their figures changed
to values the snapshot does not hold all refuse, and the fabrication check broken
four ways in a copy was caught each time (`research/findings.md` §3.8,
revisited).

## After the sweep — Cash as one definition, the replay blocker, the validator holes
**Date:** 2026-09-19 · **Commits:** 8a1a2a1, 9c54202, 0dcbd8a, 0b87581, e52e157, b191a85, 177554c

The design lesson was recorded first: a value computed in more than one place is
one function, defined before any of them. `core/cash.py` is that definition:
- **The planner** funds buys only from cash above the floor plus what its
  sells are worth.
- **The gates** judge what each order sells, not its label.
- **The floor** is judged on the orders approved, after the gates and the risk
  vote. The last buy is dropped until it holds, and a sell never is.

R1, R2 and R3 each reproduced before the fix (−$17.49; $19.38 under a $20
floor; $25.90 under a $25 label), and each was caught when broken again in a
copy. Also closed:
- **R4:** a live vote and its replay now give the same record bytes;
- **R5 and R6:** uncited figures, a decimal before a full stop, and an
  indented or bolded CALL. Each was attacked;
- **R7:** a rule named twice;
- **S1:** computed ratios, and one-step derivations from cited fields.

All four stored 3.8 replies now pass, with no new call, and 572 tests pass.
S2 to S13 are recorded in LESSONS with their owners.

## S8 and the parser fixes — selling what the fund holds; a risk reply read tolerantly
**Date:** 2026-09-19 · **Commits:** 52b05a4, afe950e, 143c6fe, 264eb56, 70f3ae5, 9e538c0, 2db8289

A sell now needs:
- a price to value it;
- a fresh quote at its size;
- the mandate in force, and the order within the per-trade limit.

A buy keeps every check. A held DELL outside the buy universe is sold, and a buy
into it is still refused (seven breaks in a copy, each caught). The parser fixes:
- **S6:** the risk reply parser reads variations and vetoes only an order it
  has no clear vote for (four breaks, each caught);
- **S5:** `NO CALLS` is read however dressed;
- **S2:** bps figures are read in either sign or as computed from cited
  prices, and the brief states `divergence_bps`'s sign.

## 3.8 ▶ finished — The exit run that ends Phase 3, shown at the stop
**Date:** 2026-09-19 · **Commits:** cbd871d, a1dd8db, fbe160e

The fresh snapshot `c06abd9e…` was taken at 20:20Z Saturday. Four live analyst
calls were all accepted, then live quotes and one live risk call, $1.142846 in
all. Of eight buys, six were approved, and the risk agent vetoed two, the second
legs of GME and INTC. It judged them duplicates that would breach the 0.25 cap.
That is false: each pair is one $37.50 move split by the $25 limit, and the plan
did not say so. The decision is signed as `732161de…`, and its cycle, committed
in `fixtures/cycles/20260919T202259Z/`, rebuilds byte for byte offline for 3.9
(`research/findings.md` §3.8, finished). **Shown, and waiting for the operator.**

## 3.3 amended — Each part of a split move shows its part
**Date:** 2026-09-19 · **Commit:** 45f1e2d

A move the per-trade limit splits now shows each order as its part: "part 1 of
2", the weight before and after that order, and the whole move in words. On the
3.8 cycle, GME's two halves now read 0 → 0.09375 → 0.1875, not two orders each
reaching 0.1875. As plan layout 2 and record schema `/2`, it is written from now
on. Layout 1 is kept for replay, and both presentation rules broken in a copy
were caught.

## 2.3 amended — The shared example replaced
**Date:** 2026-09-19 · **Commit:** bf19606

The NVDA hold is gone. The example is a caution on ORCL, outside the buy
universe in both captures, so no seat can make it as its own answer. Its figures
are the 06:01Z capture's, and the validator refuses it only for the asset.

## 3.9 ▶ — Byte-stable replay, shown
**Date:** 2026-09-19 · **Commit:** be6be2e

`tests/test_replay_cycle.py` rebuilds the exit run's signed record byte for
byte from its recorded inputs alone, with every network connection refused. The
plan is written in the layout the record's schema names. Its signature verifies
over those bytes and fails on one changed; a changed recorded input changes the
rebuild; and today's layout gives different bytes. Three ways of breaking the
guarantee, each caught in a copy. Phase 3 is closed.

## Phase 4 plan — The treasurer and the ledger, primitives first
**Date:** 2026-09-19 · **Commits:** 717492a, c0e8fe6

`planning/PHASE-4.md` names, before any unit, the seven values Phase 4 would
otherwise compute in several places:
- order state;
- order identity;
- a fill;
- holdings;
- cash;
- cost basis;
- realised and unrealised value.

Each is one function in `core/`, built as the new unit 4.0. It then plans 4.1 to
4.12 at minimal scope in four sequential batches, with the stop at 4.11, and
carries S10 to S13, the mandate's approval and the `.env` split to their units.
Six decisions wait on the operator before 4.0.

## 3.9 hardened — A replay reads the config its cycle carries, and judges by the gates its record names
**Date:** 2026-09-19 · **Commits:** 0f64916, 51f3ff2, ecc4f67, 30c2c77, bf7611a, 6de24c3

The orientation after Phase 3 found the replay read the working tree's config, and
4.1's first edit to `mandate.json` would have failed 3.9's test. Building the fix
found two more such reads: the validator's contract and the quote verdicts.
- **Config:** a decision reads its four config files once, from one directory, and
  writes the copy beside its record. Both recorded cycles carry theirs, and
  `decide.replay` reads that copy and refuses one its record does not name.
- **Gates:** a record's schema names its gate set beside its plan's layout, and a
  replay judges by that set. Set 1 is Phase 3's; S10 and S11 make set 2 at 4.4.
- **Verified H:** nine rules broken in a copy, each caught. Among them, a replay
  reading any one of the four files from the tree, and one taking today's gates.

## 4.0 — Twelve shared values, one definition each
**Date:** 2026-09-19 · **Commits:** 9057dbe, cbd0193, 7329920, 38915d3, 8467648, c8fc7d2, dbdd3cf, 6b27b64, de7a9ec

Built before any Phase 4 unit, and consumed by none yet:
- **`core/orders.py`:** the moves an order may make, with `prepared → refused`
  for a chokepoint refusal, and its id and key from the decision and plan index.
- **`core/ledger.py`:** the four events and which book, paper or real, each is in;
  a paper fill that is its quote exactly; and one fold that gives holdings, cash
  as USDG at its own mark, average-cost basis, realised and unrealised value, costs
  and expenses. A fee is never basis. Each book's NAV is `cash.nav`, the sum the
  planner uses, and equals opened + realised + unrealised − costs, exactly.
- **`core/cash.py`:** which holding is cash, and the NAV. `gates.settle` now counts
  filled orders at what they booked and the rest at their projection.

Verified H: 51 rules broken in a copy as each primitive was built, each caught by
its own test. The five values the orientation found missing are held to one
module each by `tests/test_boundaries.py`. 674 tests pass. **Stopped before 4.1.**

## 4.1 — The mandate the operator approved
**Date:** 2026-09-19 · **Commits:** 26d049f, 0e53157

`config/mandate.json` is approved: by the operator, expiring 7 days later, allowing
the 35 markable stocks with ETH and USDG, which is `config/registry/feed_map.json`'s
37 exactly. `treasurer/mandate.py` loads it and refuses a null or placeholder field,
and `core/gates.py` judges its term (approved, not revoked, not expired), S10's check
of every leg an order trades — a held stock stays sellable (S8) — and the live budget,
null until Phase 5, which blocks a live order and no paper one. Verified H: eight
rules broken in a copy, each caught.

## 4.2 — The intent, and the published key (S13)
**Date:** 2026-09-19 · **Commits:** 542aa3d, 76e1d69

`config/keys.json` publishes the fund's public key, and a record authorizes only
against it, never against the key its envelope names: the signer's check, the intent,
the chokepoint and `run/decide.py` all read it there. `treasurer/intent.py` turns a
signed record into exactly the orders it approved, in the plan's order, each
`prepared` with 4.0's id and key, and refuses the record whole unless it verifies and
the mandate is in force. On the exit run's record: six orders, stable keys. Verified
H: seven rules broken in a copy, each caught.

## 4.3 — Orders, durable before the act
**Date:** 2026-09-19 · **Commit:** 4fd5174

One SQLite file (`store/schema.sql`, `store/db.py`). `store/orders.py` writes an
order `prepared` and moves it only through 4.0's `transition`, committing before it
returns and appending the move to the order's history. A restart keeps each order's
state and key, an order added again keeps the state it reached, and two writers
cannot both move one. Verified H: five rules broken in a copy, each caught, and a
process killed straight after the write leaves the order `prepared` on disk.

## 4.4 — The chokepoint, and gate set 2
**Date:** 2026-09-19 · **Commits:** 85afba5, f548b11, be214c1

Gate set 2 is S11 (a decision judged at most 15 minutes after its snapshot's block),
the mandate's term at decision, and S10 on every order; records are
`openfund.decision/3`. `treasurer/execute.admit` trusts nothing the decision computed:
the published key, the record's own snapshot, the order as the record approved it, the
mandate in force now, every gate again on a quote taken now through the venue's own
interface, what the book holds (P4), and the floor on what has booked (P11). The exit
run's six orders pass on fresh fake quotes; nine known-bad orders were each refused by
their own rule, and seventeen rules broken in a copy were each caught.

## 4.5, 4.6 — The paper executor, the journal, and the one path between them
**Date:** 2026-09-19 · **Commits:** 67fa2b1, e2f4ffc, 5d07fd4

`submit(order, quote) -> Outcome` is the interface the live executor will satisfy;
the paper one fills at the quote's amounts exactly, marked paper, and a repeat under
the same key returns the first outcome as Bankr's key does (F0.10.1). `store/journal.py`
appends every event 4.0 defines and never edits one: the database refuses an edit, a
delete, and a second fill for an order. `run_order` writes `submitted` before the act,
which the executor sees on disk when it is asked to send, and writes the fill with the
order's new state in one transaction. Verified H: fourteen rules broken in a copy,
each caught.

## 4.7 — Positions, derived and never written
**Date:** 2026-09-19 · **Commits:** 687a22b, 6b5b1df

`store/positions.py` has no table: a position is what the journal's events add up to,
read through the ledger and valued only by `valuation.value`. Its statement reconciles
the book exactly before printing anything — opened plus realised plus unrealised less
costs equals NAV — and refuses to print a book that does not, down to 10⁻²⁰ of a
dollar. Paper and real are separate statements and are never added. Verified H: four
rules broken in a copy, each caught.

## 4.8 ▶ — A whole paper cycle, from a capture to a book
**Date:** 2026-09-19 · **Commits:** 477a50b, 7ae33cd, 6fb7047

`make cycle-demo` runs two cycles on the committed capture and the exit run's four
real reports, with the fake venue, a scripted vote and a scratch key of its own: no
model call, no chain, nothing spent. Cycle one signed a `/3` record, wrote eight
orders `prepared`, admitted and filled each on paper, and left a book of six positions
and $35.97 cash at a NAV of $200.14; cycle two planned from that book and left $20.04
against the $20 floor at $200.17. Both reconcile exactly. S12 is closed: a holding the
snapshot cannot mark still signs a no-rebalance record that says why. Verified: six
rules broken in a copy, each caught, among them orders written as they are attempted
rather than before, which the kill drill catches. **Shown, not stopped.**

## The audit's four cuts, and the rules that follow them
**Date:** 2026-09-19 · **Commits:** 4992d62, ef51a93, a0afb5b, cb7fdab, and `CLAUDE.md`

The Batch B audit found 33 rules expressed 61 times, six ledger readers and one table
nothing called, and four rules defined twice. `CLAUDE.md` now carries the six pace
rules that follow, and its stop list finally names 4.11. Four cuts taken, and no more:
`order_moves` and `history()`, which nothing read; the six ledger readers, since every
consumer reads the book `value()` returns, which also ends the two ways unrealised was
summed; S12's no-rebalance record, which now reuses the head and tail every decision
shares instead of repeating 62 lines; and `orders.quote_is_for`, the second definition
of a rule `gates.fresh_quote` owns. The module folding and the exact arithmetic stay:
the unit-to-module map is worth more for now, and 4.11 is what cashes the arithmetic
in. Two tests went with them, 756 to 754.

## 4.9, 4.10 — The lock, and what the last run left
**Date:** 2026-09-19 · **Commit:** 5ad09fd

One module, because both are what a runner does before a cycle is accepted, on one
connection (`CLAUDE.md`: a plan naming a unit is not a reason for a module).
`run/startup.py` holds the single-owner lock — a second runner refuses, and a row left
by a process that died on this host is taken over, never one from another host — and
settles what the last run left: an order in flight is confirmed when the journal holds
its fill and failed when it does not, because a paper fill and its state are one
write; a `prepared` order is refused as stale, since nothing was sent and the evidence
is a cycle old, which is S11's rule at a restart; and a live order in flight refuses
the cycle, because its outcome is on the chain and reading it is 5.3's. Verified H:
eight rules broken in a copy, each caught, among them the lock never taken and a
holder elsewhere taken over.

## 4.12 — The treasurer alone, and the keys that cannot spend
**Date:** 2026-09-19 · **Commits:** 17bc915, d1f7b42, 14eae92

`python -m fund.treasurer.execute` is the treasurer's own process: it reads the
decision's approved orders from SQLite, admits or refuses each, fills the paper ones
and books them. The cycle starts it from an empty environment and hands it no
credential — it reported being given `PATH`, `PYTHONPATH` and `LC_CTYPE`, and loading
`SIGNING_KEY` itself — and `config.env_file_for` reads the treasurer's own file where
the operator splits them. Then the claim invariant 1 makes, measured rather than
asserted: one real swap request per analyst key, authorized by the operator and costing
nothing because both were refused — `BANKR_KEY_READ` 403 "Read-only API key … cannot
execute swaps", `BANKR_LLM_KEY` 403 "Wallet API access not enabled"
(`python -m fund.run.isolation --live`). Verified H: four rules broken in a copy, each
caught, among them the treasurer's key being sent and a request that went through
counted as refused.

## 4.11 ▶ — The known answer, shown at the stop
**Date:** 2026-09-19 · **Commits:** 22fcfa0, 8620b5a

`fixtures/accounting/` holds thirteen constructed events — opening capital, two paper
buys and a partial sale, a contribution in, a live fill with its gas, gas on a
transaction that reverted, a withdrawal, and two inference costs — and `answer.md`
works out by hand, in exact rationals and without running the ledger, what a book that
tells economic truth must say about them. The ledger met it figure by figure at the
first run: paper NAV **$183.64629364**, real NAV **$4.26567681261301**, and in each
book opened + realised + unrealised − costs equals NAV to the last digit, including
the one basis share that does not divide, rounded half-even to 10⁻³⁰. A contribution
moved what was put in and no income; the reverted transaction's gas is a cost with no
fill; the two inference costs are one expense line, in neither NAV. 4.11 added the
transfer event, capital in and out. Verified H: eight rules broken in a copy — basis at
the last price, a fee capitalised, a contribution as income, a withdrawal as a loss,
the share rounded to the cent, a fill valued at its stock leg, inference inside the
book, and the two books read together — each caught. **Shown, and waiting for the
operator.**

---

## 5.1, 5.3 — The one path that can spend, and the chain as the only answer
**Date:** 2026-09-19 · **Commits:** 5dc4b77, 2c8d243, 2329034

`adapters/bankr_exec.py` sends one swap and never retries; `treasurer/reconcile.py`
says what became of it, from the receipt and not the reply. A swap on 4663 is a
gas-sponsored 4337 UserOperation inside a bundler's transaction, so who swapped is the
EntryPoint's `UserOperationEvent.sender`, whether it filled is that event's `success`,
what moved is the wallet's `Transfer` logs — and, for the native leg, which emits none,
its own balance across the block less any gas. Unsettled is `unknown`, never `failed`.
`LiveExecutor` satisfies the paper executor's `submit(order, quote) -> Outcome`
unchanged; what changed in the caller is only the authority, which `run_order` now
takes as an argument. Gas is booked as a cost whether the swap filled or reverted.
`config/cadence.json`'s `confirmation_depth` is **100 blocks**, about ten seconds at
the 102 ms blocks measured, and it is a choice, not a measurement. The swap body is
the one that filled on chain — `minBuyAmount` and `quoteId`, no slippage figure — so
the venue enforces the floor the order was authorized with. Verified H: 8 breaks on
the reconciler, 12 on the leg, each caught, against probe 0.10's real recorded
receipt in `tests/data/`.

## 5.2 — A signed instruction, because no analyst chose this trade
**Date:** 2026-09-19 · **Commit:** 2c8d243

Every order this fund sends is authorized in writing and verified at the chokepoint.
The live leg has no analyst behind it — SIMPLIFICATION calls it a demonstration of the
money path that no analyst chose, and forbids manufacturing a decision for it — so it
carries its own artefact: `treasurer/instruct.py` writes one order in the plan's own
layout, signed by the same key in the same envelope, its id the sha256 of its own
bytes, so the order's id and idempotency key derive from exactly what was authorized.
`admit_instruction` is the same chokepoint on a different authority: it drops `quorum`,
`turnover`, `position-weight`, `tradeable` and the paper cash floor — nobody voted,
there is no plan to turn over, and that floor is the paper book's — and adds the
instruction's own expiry. Everything else an order passes, it passes. The treasurer
cannot fetch a live quote (the quote adapter refuses a key that can transact), so it
judges the one the instruction carries, by the same age rule, and a stale one is
refused. `mandate.json` v3 sets `cumulative_budget_usd` to **$1**, the ceiling on
everything the live leg may ever trade.

## 5.2 ▶ — Two real swaps, reconciled and booked
**Date:** 2026-09-20 · **Commit:** a3809ef

On a snapshot 142 s old, `python3 -m fund.run.liveleg` printed the asset, size, wallet
and chain, and stopped; run again with `--confirm` it sent one swap, once.

- **ETH → USDG:** `0x9c8ea67dd8c17c9a7315f38ad427f8e0b3852d55b68af463d5f17027d3cfbbfa`,
  block 67,501,588, 119 confirmations deep. Gave 30,000,000,000,000 wei, got 78,714
  USDG, gas sponsored. 18 gwei the logs do not name (F5.2.3, F0.10.4 again).
- **USDG → ETH:** `0x737e32b4ea091110fa0dc42daf8992c705a5d89edc24c5bdd4fae3553a802a27`,
  block 67,501,988, 119 deep. Gave 100,000 USDG, got 38,026,356,590,733 wei, sponsored.

The real book: **NAV $1.28581522201804455630**, opened $1.28604122805670792085 +
realised −$0.0000015775 + unrealised −$0.0002244285 − costs $0 = NAV, exactly. The
paper book in the same journal is empty: two books, never added. $0.1787 of the $1
budget is used. Each order booked one fill, under its own key, and the instruction,
its signature and its outcome are committed in `fixtures/liveleg/`.

**Two bugs the run found.** An unsettled receipt returned no transaction reference, so
an order left in flight carried no hash and a restart had nothing to read; and
`live_fill` refused an order in state `unknown`, which is exactly the state a restart
finds one in. Both fixed, each with a break to prove it. 4.9 left reading the chain to
this unit: `startup.resolve` now takes a reader, and books the fill, its gas and the
state in one write.

---

## Stocktake before the demo — what works, what the front end can read, what is missing
**Date:** 2026-09-20 · Read-only inventory at `8bec05f`, about two and a half hours
before submission. No code changed.

**Works on a fresh clone with no credentials** (checked by exporting `HEAD` to a clean
directory and running each): `make test` 793 passed in 41 s; `make replay` 1.0 s, both
committed captures rebuilt byte-identical with every connection refused; `make
cycle-demo` 1.3 s, two whole paper cycles ending in a book that reconciles exactly
(NAV $200.17). **Works live, with credentials:** `make selftest` 103 s, 235 addresses
attested at block 67,510,242, 235 pass 0 fail (run today); `make snapshot` ~150 s;
`run/isolation --live`; `run/liveleg` dry ~3 s and ~15 s to settle with `--confirm`
($0.82 of the $1 budget left); the analysts and the risk call, which spend. **Recorded
only:** the x402 sale. Its endpoint is still live and answers 402 for 0.001 USDC, but
the resource it sells is *"Phase 0 probe: static response, no work"*, and `payTo` is
`0x8AEE62…`, not the fund's wallet.

**What a front end can read.** Committed, static, no server needed: two snapshots
(`fixtures/snapshots/<block>-<sha12>/snapshot.json`), two whole cycles with their
signed records (`fixtures/cycles/<ts>/decision/{record,envelope,plan,proposal,reports,
quotes,risk}.json`), the live leg's authority and result
(`fixtures/liveleg/leg{1,2}-*/{instruction,envelope,outcome}.json`, the outcome
carrying the chain evidence and the real book as text lines), and the known-answer
fixture. **Not readable:** every book. `positions.statement` returns a string,
`BookValue` has no dict form, the paper cycle writes `book.txt` under the gitignored
`fixtures/live/`, and the live book is SQLite, also gitignored. There is also no index
across cycles — `latest.json` is 7.1's. `probes/out/` is gitignored too, so the probe
evidence exists only as prose in `research/findings.md`.

**Correction to the note below.** It said everything from `4992d62` was committed and
**not pushed**. That is wrong: `git ls-remote` puts `origin/main` at `8bec05f`, the
same commit as local `HEAD`, and the reflog records it as a push. The repository is
public at `github.com/DhruPtel/runtime-hack-openfund`, all of Phase 5 included, with
GitHub Pages off. The claim closing the previous batch — "nothing pushed" — was wrong
in the same way, and this corrects it.

**Ranked for what a judge sees:** the README still says *"Status: building, Phase 0"*
and lists four working commands as "the intended surface when finished"; there is no
page; there is no book in JSON for a page to read; nothing serves a record over HTTP,
so *sells its research* is the one claim of the three not demonstrable end to end.

---

## Presentation pass — the repository says what it is, and the book became data
**Date:** 2026-09-20 · **Commits:** 23a2c4b, 444f66e, 5e314e6, 605fb06, 14cc01d, aae44ed

No feature was added and no money path was touched. What changed is what a reader is
told.

**The README** said *"Status: building, Phase 0"* and listed four working commands as
"the intended surface when finished". It now opens with what the fund is, the pipeline
in eight lines, and two tables: what runs on a fresh clone with no credentials — `make
test` 794 in 41 s, `make replay` 1 s, `make cycle-demo` 1 s, the hand-computed
accounting fixture under a second — and what runs live, with what each needs and
roughly how long it takes. Then the two transactions with their hashes, and **what the
fund does not do**: stock fills are paper, revenue is not booked at all, the x402
endpoint sells a Phase 0 probe response and not a record, there is no page and no
scheduler. Every claim in it is a command or a file. Verified by exporting `HEAD` to a
clean directory with no `.env` and running each: 41.3 s, 1.0 s, 1.2 s, 0.2 s.

**The stale documents.** JUDGING-CRITERIA described "Phases 0 and 1 built, Phase 2 not
started"; it now describes what the record holds at 5.3 and names revenue as the one
claim of the three that is not demonstrable. PHASE-4 said the live budget stays null
until Phase 5; 5.1 set it to $1 and 5.2 used $0.18. PLAN §13 gained Phase 5's own
limits: the confirmation depth is a **choice**, not a measurement; the live chokepoint
re-judges its quote but cannot re-take one, because the quote adapter refuses any key
that can transact; and the explorer answers 200 for any hash, so its links are for a
human and the RPC receipt is the evidence. SIMPLIFICATION's *"proposed mechanics, not
decided"* — the planner appending a live order to each cycle — is replaced by what was
built and the operator confirmed, with the reason: a plan is one book's rebalance, so
appending a real-book order would have counted the wallet's USDG as paper cash.
`.env.example` now says one file is enough and what the optional `.env.treasurer`
splits; it had never been mentioned. `fixtures/README.md` describes `liveleg/`.

**The code.** Three docstrings described a world two phases old: the paper cycle said
the live path *was Phase 5's*, the ledger said a live fill *would come* from receipts
at 5.3, and the live leg's usage example sold an amount it never sold. `run/schedule.py`
now says plainly that it is not built, that cycles are started by hand, and which
module holds each guard a scheduler would need — a placeholder, not a missing import.
One property elsewhere has no caller (`bankr_exec.SwapReply.claims_a_transaction`); its
file was outside this batch's paths and it was left alone.

**The book as data** (the one exception to "no new features", because the page needs it
and nothing else provided it). `ledger.as_document` renders a `BookValue` as JSON — the
block, NAV, cash and every position with units, value, basis and unrealised, and the
identity's own terms — exact, not rounded to the cent, and computing nothing: every
figure is read off the value the one fold already produced. `run/cycle.py` writes
`book.json` beside `book.txt`, and the live leg's `outcome.json` carries it too, so the
two committed ones now hold the real book as data. One test holds the JSON to saying
exactly what the text says, row by row, once rounded the way that file rounds. 794
tests pass.

---

## The rehearsal — three live runs, and what Bankr actually carries
**Date:** 2026-09-20 · **Commits:** e54e61b, 2678b52 · Findings F8.R.1 to F8.R.6

Three runs of the live pipeline back to back, changing nothing between them, plus one
real round trip. State before spending: credits **$12.447837**; the wallet holding
0.000468188843098662 ETH and 0.057456 USDG on 4663 and 5.079910 USDC on Base; the read
key read-only, the LLM key gateway-only, the exec key able to transact, a never-issued
control key answering 401 to everything; and a fresh clone passing 794 tests.

| Run | Analysts | Decision | Record | Replays | Cost |
|---|---|---|---|---|---|
| 1 | 2 of 4 — two HTTP 504 | **no rebalance**, below the quorum of 3 | `b6f0f50d…` | byte-identical | $1.212898 |
| 2 | 4 of 4 | 5 orders, every gate cleared, **all vetoed by risk** (INTC's mark) | `5264a64e…` | byte-identical | $1.412568 |
| 3 | 4 of 4 | 8 orders, every gate cleared, **all vetoed by risk** (MSTR's mark) | `4103752c…` | byte-identical | $1.149473 |

**Three for three on the thing that matters:** every run produced a signed decision
record that rebuilds byte for byte from its own carried inputs. Two of three reached
quorum. None executed a stock order — twice because the risk agent vetoed the plan on a
price-integrity mark flag, once because two analyst calls were lost. Each is a valid
outcome, and each is recorded as what it was. A whole run is about four minutes.

**The round trip,** between runs 2 and 3, on run 2's snapshot: `0x2d543870…23aa` (block
67,532,677, 0.00003 ETH into 0.078760 USDG, 17.1 s) and `0x871944…21a0` (block
67,532,956, 0.10 USDG into 0.000038077691442267 ETH, 19.9 s). Both gas-sponsored, both
confirmed from the EntryPoint event and the wallet's own logs. The real book now holds
four live fills, reconciles exactly at NAV $1.29, and has used $0.357 of the $1 budget.
The paper book in the same database is empty: two books, never added.

### Bankr, named surface by surface

| Surface | What the three runs did | Evidence |
|---|---|---|
| **LLM gateway** `llm.bankr.bot/v1` | 12 analyst calls and 2 risk calls, `claude-sonnet-5` | each run's `results/*.json` with status, tokens and cost; the record's risk section; the balance falling $3.774939 |
| **Credits** `/v1/credits` | read before and after each run | $12.447837 → $8.672898 |
| **Quotes** `api.bankr.bot/wallet/swap-quote` | 13 live quotes for plan sizing (0, 5, 8) and 3 for the live leg | each decision's `quotes.json`, labelled "live, read-only"; each instruction's carried `quoteId` |
| **Swap** `api.bankr.bot/wallet/swap` | 2 submissions, one each way | the two transaction hashes |
| **The wallet** `0x93faecde…a3da` | Bankr-custodied and EIP-7702-delegated to a Bankr contract; both swaps ran as 4337 UserOperations with this wallet as `sender`, submitted by a Bankr bundler | `make selftest`'s delegation check; each `outcome.json`'s `user_operation` |

**Not Bankr:** the chain itself is `rpc.mainnet.chain.robinhood.com`, the corroborating
prices are GeckoTerminal's, and the marks are Chainlink feeds read on chain.

**What would still work if Bankr vanished:** the snapshot, the 235-address attestation,
the registry and beacon checks, every gate, the ledger and both books, the signing, the
byte-identical replay, the order state machine, and the receipt reconciler — which reads
the chain directly. The fund could still publish a signed record saying it did not
trade, and still value what it holds.

**What would not:** every analyst report and the risk vote, because inference is the
gateway's; every quote, so the planner could not size or gate a single order; every
execution, because `/wallet/swap` is the only path that spends; and custody itself, since
the wallet is Bankr's. Bankr is the fund's brain, its price feed for execution, and its
hands. The books, the evidence discipline and the refusals are the fund's own.

### What the rehearsal exposed, and was not fixed
- **The gateway loses calls.** Two of twelve, both in run 1. Nothing in this repository
  can fix that; the retry budget deliberately does not cover a timeout, which is billed
  anyway. Below quorum the fund refuses to rebalance, which is the right failure.
- **The cost estimate is 12% low** over the three runs, and low *because* a lost call
  counts as zero. 6.3 must reconcile against `/v1/credits`, not trust the estimate.
- **No command runs a live cycle end to end** (F8.R.5): `decide` decides live and
  executes nothing, `cycle` executes but always decides offline with a scripted vote.
  The fills-and-book half has never run against a live record. That is 5.7 and 8.3, and
  nothing was built here to close it.
- **The risk agent vetoes a whole plan for one bad order.** Twice in two chances. In a
  closed session the equity marks are frozen and divergence grows, so price-integrity
  reliably has something to flag. Whether one veto should carry the plan is the
  operator's call; the brief was not touched.

---

## A live cycle in one command, and a veto that stops one order
**Date:** 2026-09-20 · **Commits:** b86bff4, 9eab5b7, 314a25d · Findings F8.L.1, F8.L.2

**One command, end to end.** `python3 -m fund.run.cycle --live --db PATH --out DIR`
ran a live snapshot, four live analyst seats, aggregation, live quotes, one live risk
call, a signed record, the chokepoint, ten paper fills and the book — **252 seconds,
$1.606257**, on the first attempt. Record `c55400f8…`, signed, authorizing, and it
replays byte for byte. The paper book closed at NAV **$200.03**, exact, beside the real
book's **$1.2858** in the same database: 14 confirmed orders, ten paper and four live,
two books never added.

The change is four arguments, not a pipeline. `cycle()` already took a venue; it now
also takes a risk credential, and with both it decides live. Everything after the
decision — the chokepoint, the treasurer in its own process, the one write that keeps a
fill with its order — is the code a paper cycle runs. `--live` composes the three
modules that already existed and reimplements none of them.

One bug caught before it cost anything: the cycle judged quotes at the instant it
*started*, so a live fetch — which takes seconds — would have been judged before it
happened, leaving every quote's age undetermined, which blocks. A live cycle now judges
after the fetch; the paper path is unchanged, because the fake venue answers at the
cycle's clock.

**The veto was the brief.** F8.R.4 recorded two whole plans vetoed over one flagged
mark each. `briefs/risk.v1.md` said "An overall veto vetoes every order" and never said
when one is warranted, so the agent treated a single bad order as grounds to veto the
plan — run 3 wrote that out in full. The parser was faithful: the model really did emit
`OVERALL veto`.

`risk.v2.md` says what was missing: an overall veto is for a plan unsafe as a whole, and
vetoing one order is not a reason to veto the plan, because the per-order veto has
already stopped it. **No code changed** — a vetoed order is still blocked, an overall
veto still carries. On the first live run under v2, META was blocked by the impact gate
at 238 bps against a 50 bps limit *and* vetoed, MSTR was vetoed on price-integrity's
flag, and the other ten filled. The overall line read: "the two flawed orders are
stopped individually and the rest stand on their own merits."

A record names the brief it was decided under, and a replay rebuilds with **that** one,
so every record written under v1 still replays; the pinning was broken in a copy and
three replay tests caught it. One test covers the blast radius offline: one order
vetoed by its own vote, seven approved, seven filled, the book reconciling. 795 tests.

---

## State at close — 2026-09-20, Phase 5 built to 5.3; the live leg has run, and 5.4 is the stop

**Read this first.** This note describes the repository at the commit that last
changed it: run `git log -1 -- tracker/LOGS.md`. If `git log` shows later
commits, this note is older than the code, so read those commits before trusting
it. Where this note and git disagree, git is right.

**The build mode.** From Phase 2, every unit is built at its minimal version.
- Each unit's minimal, full and given-up versions are in
  `planning/SIMPLIFICATION.md`. PLAN §8 states the pivot, and `CLAUDE.md`
  carries the rule.
- Keys, signing and spend authority keep their full guard.
- The operator is stopped at 2.1, 3.8, 4.11, 5.4, 6.6, 7.5 and 8.5. 2.1 was
  approved, and past 3.8 the operator asked for Phase 3's close. Then for the
  orientation's fixes and 4.0, then for Batch B, 4.1 to 4.8, then for the audit, its
  four cuts, 4.9, 4.10 and 4.12, then 4.11 — shown and approved by the operator's next
  batch — and then Phase 5, 5.1 to 5.4. **5.4 is shown, and waits for the operator.**

**The deadline** was given at about 11:00Z on 2026-09-19 as "about 16 hours":
about Sun 2026-09-20 03:00Z. That is this note's arithmetic, not a time the
operator wrote down. This note was rewritten at about 00:40Z on 2026-09-20.

**Check it in a minute.** Nothing here spends unless marked. The `python3 -m`
commands need `PYTHONPATH=src`.
- `git log --oneline -25` and `git status -sb`.
- `make test`: 795 passed when this was written, in about 38 s. The runner and
  risk tests start real subprocesses against a fake gateway on 127.0.0.1.
- `python3 -m fund.run.cycle --live --db PATH --out DIR` is the whole thing live in
  one act, and it **spends** about $1.20 to $1.60: a live snapshot, four analyst calls,
  one risk call, then the chokepoint, the fills and the book. About four minutes.
- `make cycle-demo`: two whole paper cycles on the committed capture and the exit
  run's four real reports, in about 8 s. A fake venue, a scripted risk vote and a
  scratch signing key of its own: no model call, no chain, nothing spent. It writes
  under `fixtures/live/cycle-demo/`, which is gitignored, and prints each cycle's
  table, gates, orders and book.
- `python3 -m fund.run.decide --snapshot fixtures/snapshots/66852293-253315c0e691
  --approved-reports --quotes Q --risk-reply R [--env-file E]` takes reports to
  a signed record and executes nothing. The flags:
  - offline, it needs a recorded quotes file and a recorded risk reply;
  - `--live-quotes` reads the venue, read-only;
  - `--confirm` makes one live risk call, which **spends**;
  - `--cycle DIR` takes a runner cycle's accepted reports instead.

  It signs with `.env`'s `SIGNING_KEY` unless `--env-file` names another. Do
  not sign fake inputs with the fund's key. It writes the config it read beside
  the record, as `config/`.
- `decide.replay(cycle, snapshot, out)` rebuilds a recorded cycle's record from
  what the cycle carries, its config included, and never signs
  (`tests/test_replay_cycle.py`).
- `python3 -m fund.agents.show <cycle dir>` prints a stored report as written.
- `python3 -m fund.agents.runner --snapshot <path> ...` **spends** with
  `--confirm`.
- `python3 -m probes.keymap`: each key's measured capabilities, read-only. Run it
  before any live call.
- `python3 -m fund.run.isolation [--live]`: one swap request per analyst key, to
  measure that neither can transact. `--live` sends them; without it nothing is
  sent. A refusal costs nothing, and a request that goes through is the finding.
- `python3 -m fund.run.liveleg --snapshot PATH --sell ETH --amount 0.00003 --db PATH
  --out DIR [--confirm]`: **the only command that spends on chain.** Without
  `--confirm` it quotes, writes and signs the instruction, prints the asset, size,
  wallet and chain, and stops. With it, the treasurer's own process sends one swap,
  once, and books what the chain says. It needs a snapshot minutes old (S11 gives it
  15) and the mandate's live budget, which is $1 and $0.18 used.
- `make replay` rebuilds the committed capture offline. `make check-env` names
  the credentials present. `make selftest` needs the RPC URL. `make snapshot`
  builds a live snapshot in about 2.5 minutes.

### Done
- **Phases 0 and 1,** at full depth.
- **Phase 2, 2.0 to 2.7.** 2.8 is not closed, though its three cases exist as
  2.4's tests. Phase 2's exit is not met: all four seats had real reports
  accepted at 3.8's exit run, but no seat has its own account. (Until this note,
  this line still said the exit run had not happened: stale since 3.8.)
- **Phase 3, 3.1 to 3.7,** offline, in one pass (entries above). It was built on
  the four approved reports, the committed capture, a labelled fake venue,
  scripted risk replies and 2.4's fake gateway.
- **3.8's run** (entry above; `research/findings.md` §3.8):
  - the exit run, four live calls on the committed capture, all replied and
    all refused;
  - so no quorum;
  - the fund's real decision, `2c9c1a79…`, signed with its key: no rebalance,
    no order, no risk call and no veto.

  Recorded in `fixtures/cycles/20260919T171351Z/`, now history: it predates
  the sweep, and nothing rebuilds it.
- **3.8's exit run and Phase 3's close** (entries above):
  - the exit run's decision, `732161de…`, in `fixtures/cycles/20260919T202259Z/`;
  - 3.9's test rebuilds it byte for byte, network refused;
  - plans are written in layout 2, and records as `openfund.decision/2`.
- **3.9 hardened** (entry above): each recorded cycle carries the config it was
  decided under, a replay reads that copy, and a record's schema names its gate
  set as well as its layout.
- **4.0** (entry above): twelve shared values in `core/orders.py`,
  `core/ledger.py`, `core/cash.py` and `gates.settle`.
- **Batch B, 4.1 to 4.8** (entries above). The fund acts on paper: an approved
  mandate, intents from a signed record, durable order states, a chokepoint that
  regates on a fresh quote, paper fills, a journal, positions derived from it, and
  one command that runs the whole cycle. Gate set 2 (S10, S11, the mandate's term)
  and records as `openfund.decision/3`.
- **The audit, its four cuts, and `CLAUDE.md`'s six pace rules** (entry above).
- **4.9, 4.10 and 4.12** (entries above): the lock and the startup, and the
  treasurer in its own process, with both analyst keys measured refusing a swap.
- **4.11** (entry above): the ledger meets a hand-computed answer, figure by
  figure, in `fixtures/accounting/`. Shown at the stop.
- **Decisions of 2026-09-19** (LESSONS): the pivot, and the Phase 2 decisions.
  Then the Phase 3 batch's:
  - a target starts at the weight held;
  - config set;
  - the mandate provisional;
  - the live leg is Phase 5's;
  - 3.6 before 3.5;
  - three files outside the batch's paths, approved.
- **What is built,** under `src/fund/`. Phases 0 to 2 as before, plus:
  - `core/aggregate.py`, `core/plan.py`, `core/gates.py`, `core/context.py`,
    `core/record.py`, and `core/cash.py`, the one definition of cash (after the
    3.8 sweep);
  - `agents/risk.py` and `agents/briefs/risk.v1.md`;
  - `treasurer/sign.py`;
  - `run/decide.py`;
  - `core/orders.py` and `core/ledger.py` (4.0);
  - `treasurer/mandate.py`, `treasurer/keys.py`, `treasurer/intent.py`,
    `treasurer/execute.py`;
  - `store/db.py`, `store/schema.sql`, `store/orders.py`, `store/journal.py`,
    `store/positions.py`;
  - `run/cycle.py`, `run/startup.py` and `run/isolation.py`;
  - `adapters/fake_venue.py`, where the fake venue moved at 4.12.

  - `adapters/bankr_exec.py`, `treasurer/reconcile.py`, `treasurer/instruct.py` and
    `run/liveleg.py` (Phase 5).

  Every other module is a stub: `grep -l "Not yet built" -r src/` lists 6 —
  `core/books.py` and `core/attribution.py` (Phase 6), `store/publish.py` and the two
  surfaces (Phase 7), `run/schedule.py` (Phase 8).

### Next
- **Phase 5 is built to 5.3, the round trip has run on chain, and 5.4 waits for the
  operator.** Past it, 5.5 (access lost), 5.6 (the recorded 403) and 5.7 (a live
  cycle) remain, and Phase 6 opens: the statement, the reconcile and attribution.
- **The live leg carries its own signed authority** (`treasurer/instruct.py`), and not
  the appended plan order `planning/SIMPLIFICATION.md` proposed. LESSONS 2026-09-20
  says why, and the operator should confirm it: `planning/` was outside this batch's
  paths, so the plan still says what it said.
- **What 4.11 found the ledger still cannot say:** settled revenue has no event and
  the identity no line for it (6.1, on 7.2's settlement evidence); unsettled revenue
  is not an event at all and must not become one (invariant 9); LLM credits are
  bought inside the agents' own accounts, so neither book sees the purchase (6.3);
  and the journal's schema keeps four kinds, so it cannot yet persist the transfer
  the ledger now computes (4.6's full version).
- **All six decisions are applied,** the refused swaps included (4.12, measured).
- **Owed to the plan docs, outside this batch's paths:** `planning/` still says
  4.10 is the crash drill. The operator reassigned it to the single-owner lock in
  this batch; the crash drill is covered by the kill drills at 4.3 and 4.8, which
  leave a store on disk and nothing booked. PHASE-4, ROADMAP and SIMPLIFICATION
  need that, and `.env.example` needs the treasurer's file named.
- **Stops:** 2.1, 3.8, **4.11**, 5.4, 6.6, 7.5 and 8.5. 4.11 was added by the
  operator on 2026-09-19. `CLAUDE.md`'s list is owed the same; it was outside
  this pass's paths.
- **From the sweep, owned by Phase 4:**
  - S10 and S11, at 4.4;
  - S12, at 4.8;
  - S13, at 4.2 and 4.4.

  S3, S4 and S7 stay with 2.2 and 2.3.
- **Owed from Phase 2, unchanged:**
  - the settled `/v1/usage` cross-check for the 15:39Z and 15:58Z calls, and
    whether the 504 was billed;
  - the 504: cross-asset-macro answered in 89 s at 3.8, so the limit is
    neither shown nor ruled out;
  - 2.0's choice, (a), (b) or (c);
  - 2.8;
  - the page slice.
- **Owed to later Phase 4 units, after Batch B:**
  - the paper book opens with `capital_usd` of USDG — 200 USDG, $199.98 at the
    exit run's mark — chosen at 4.8 and open to the operator;
  - the snapshot's age at submission, and a `prepared` order found at startup: 4.9;
  - `.env` split per role, and the treasurer as its own process: 4.12;
  - no cycle books a fee or an inference cost yet: the journal keeps both, and
    4.11's fixture is where they are first used.
- **Owed from Phase 3:**
  - the mandate is provisional: 4.1 replaces the allowed assets and the
    placeholder approvals;
  - the confidence mapping is provisional, to be tuned after a real cycle;
  - one real risk call so far, the exit run's, on `risk.v1.md`: one veto, which
    rested on the split-order misreading now fixed;
  - the aggregator is blind to co-movement (LESSONS 2026-09-19).
- **The keys, measured on 2026-09-19 after the operator's fix:**
  - `BANKR_LLM_KEY`: the gateway on, refused by the Wallet API and the Agent
    API;
  - `BANKR_KEY_READ`: read-only, gateway and Agent API off;
  - `BANKR_KEY_EXEC`: read-write, gateway and Agent API off.
- **The agent account's secrets:** `~/.openfund/agents/price-integrity/`, mode
  0600, four files: `siwe.key`, `bankr-config.json`, `siwe-login.json`,
  `login-stdout.txt`. The backup of the fund's CLI config in
  `~/.openfund/backup/`, which an earlier note listed, no longer exists.
- **Owed, and each a spend:**
  - agent credits, about $22 plus 5.8%;
  - a buyer key with about $1 of USDC on Base (7.5);
  - the live round trip (5.2);
  - one refused swap per agent key (4.12).
- **Owed outside the plan docs:**
  - `credentials.py` and `.env.example`: per-agent key names, once 2.0's
    choice is made;
  - `BANKR_LLM_KEY`'s scope text in `credentials.py` still describes the key
    before the operator's fix.
- **Dated** (`CLAUDE.md`): the weekday capture from Mon 2026-09-21 00:00Z; the
  closed-session re-derivation on 2026-11-09.

### Open items, none resolved
1. **The page lands at 7.6,** after the stops at 3.8, 5.4, 6.6 and 7.5, unless
   the operator pulls a slice forward.
2. **The five-wallet plan** waits on 2.0's choice. Risk, too, runs on the shared
   key, as `unassigned`.
3. **`config.load()` merges all of `.env` into the caller's environment.**
   - Every agent process is built from an empty environment, analysts and risk
     alike.
   - The signer reads the key itself, in its own process.
   - `.env` is still readable on disk; 4.12 owns the split.
4. **The preview as decided** names no decision id, hashes or signature, and
   7.2 serves by id. The record now carries every report and the risk reply
   whole; what the preview shows of it is 7.x's.
5. **How the handler holds the full record:** bundled per deploy, or a private
   URL.
6. **The live leg's mechanics,** now Phase 5's.
7. **Token design** is a judging criterion that no unit covers (PLAN §12).
8. **The 3.4 sweep.** Minimal 3.4 consumes the three older verdicts, so
   invariant 4's "one module" does not hold; the sweep is 3.4's full version.
9. **Carried from 2026-09-18:**
   - two `http.py` changes;
   - daylight saving;
   - holidays fail closed;
   - exit is not assessed;
   - one daily-close call was set against 1.7's two;
   - caching in other request shapes is untested;
   - billed output missing from the reply;
   - AMZN's two GeckoTerminal levels;
   - $25 sized at USDG's mark;
   - the quote-age budget;
   - nine `RH<ticker> / USD` feeds;
   - no offchain source time;
   - the registry refresh owner;
   - one RPC endpoint;
   - which impact field gates;
   - the README status line.

### The numbers that stand
- **Snapshot:** schema `openfund.snapshot/4`, about 195 KB with 763 daily
  closes. Two are committed in `fixtures/snapshots/`: `253315c0…` at block
  66852293, and the exit run's `c06abd9e…` at block 67364057.
- **Analyst call:** $0.264 at Sonnet 5, uncached. A cycle is about $1.11.
- **Real analyst calls:**

  | Seat | Result | Cost | Time |
  |---|---|---|---|
  | price-integrity | refused | $0.273156 | 78.6 s |
  | price-trend | refused | $0.273142 | 83.3 s |
  | execution-quality | accepted | $0.249594 | 58.2 s |
  | cross-asset-macro | a 504 | unknown | 113.3 s |

  At 3.8, one each: price-integrity $0.265618, 71.9 s; price-trend $0.260564,
  76.5 s; execution-quality $0.288326, 103.6 s; cross-asset-macro $0.273198,
  89.4 s. All four were refused.
- **LLM credits:** $14.678389 before 3.8's first four calls ($1.087706). The
  exit run then spent $1.142846: four analysts at $1.043392 and one risk call at
  $0.099454, 45.9 s, 29,202 tokens in. The balance was not re-read.
- **The exit run's decision:** eight buys of $164.06 planned, six approved,
  and two vetoed by the risk agent. It leaves $73.44 of paper cash.
- **The paper cycles of 4.8's demo,** on the same capture and reports, with the
  vote scripted to approve: cycle one filled eight buys of $164.01 and left six
  positions and 35.97734 USDG, a NAV of $200.14; cycle two planned from that book,
  filled six more and left 20.046113 USDG at the $20 floor, a NAV of $200.17. Both
  reconcile exactly.
- **The same six, filled on paper in 4.0's tests** from 200 USDG at the recorded
  quotes: 73.430231 USDG left, $73.42 at the snapshot's USDG mark of 0.99992279.
  The 200 USDG itself is $199.98.
- **Phase 3, offline, on the four approved reports:**
  - META 12.5%, AMD, INTC and USO 6.25% each, 68.75% cash;
  - four buys totalling $62.50 of the $200 paper book;
  - a risk bundle of about 32,400 tokens, 12,000 of them reserved.
- **Wallet, after the rehearsal (2026-09-20 01:04Z):** 0.000476266534540929 ETH and
  0.036216 USDG on 4663, plus 5.079910 USDC on Base. The real book's NAV is **$1.28581522201804455630**, and
  opened + realised + unrealised − costs equals it exactly. The paper book in that
  same journal (`fixtures/live/live.sqlite`, gitignored) is empty: two books, never
  added. Before the leg it was 0.000460162486507929 ETH and 0.078742 USDG.
- **Four live swaps, two round trips.** 5.2: `0x9c8ea67d…cfbbfa` (block 67,501,588,
  0.00003 ETH into 0.078714 USDG) and `0x737e32b4…02a27` (block 67,501,988, 0.10 USDG
  into 0.000038026356590733 ETH). The rehearsal: `0x2d543870…23aa` (block 67,532,677)
  and `0x871944…21a0` (block 67,532,956). All four gas-sponsored. **$0.357 of the $1
  live budget used**, and the real book holds four fills at NAV $1.29.
- **Credits:** $8.672898, after the rehearsal's three runs spent $3.774939.

### Config
- **Set in the 2.2–2.5 batch:**
  - `analysts.json` v2;
  - `cadence.json`'s deadline, retry and width;
  - `models.json`'s risk model, context budget, price and settle window.
- **Set in the Phase 3 batch, all provisional:**
  - `thresholds.json`: `quorum_min_analysts` 3, `max_position_weight` "0.25",
    `cash_floor_usd` "20", `min_order_usd` "1", `turnover_max_bps` 10000;
  - `analysts.json`: `confidence_weights`;
  - `models.json`: `context_bytes_per_token` "1.8";
  - `mandate.json`: 20 allowed assets and placeholder approvals.
- **Set in Phase 5 (2026-09-19/20):**
  - `cadence.json`: `confirmation_depth` 100 blocks (a choice, about ten seconds at
    the measured 102 ms block), `settlement_poll_seconds` 2,
    `settlement_deadline_seconds` 180;
  - `mandate.json` v3: `cumulative_budget_usd` **1**, the ceiling on everything the
    live leg may ever trade;
  - `execute.json`: the swap endpoint, its credential and its timeout. No slippage
    figure — the body carries the order's own authorized floor.
- **Still null:** nothing that blocks. Every figure a live order needs is set.

### Committed versus pushed
`git ls-remote origin main` is `8bec05f`, the same commit as local `HEAD`: **everything
is pushed**, Phase 5 included, and the repository is public at
`github.com/DhruPtel/runtime-hack-openfund` with Pages off. An earlier version of this
section said the opposite, from a stale reading; the stocktake above corrects it.

### What this note does not cover
- **Decisions.** LESSONS holds them in full.
- **The plan.** PLAN, ROADMAP, PHASE-0-1, PHASE-2 and SIMPLIFICATION are the
  plan.
- **Credentials.** It checks none beyond `make check-env`'s names.
- **Unrecorded conversation.** Anything not written into `tracker/`,
  `planning/`, `config/` or `research/` is lost on restart.
