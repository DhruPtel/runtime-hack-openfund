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

---

## State at close — 2026-09-19, after 3.8's run: no quorum, no veto, waiting at the stop

**Read this first.** This note describes the repository at the commit that last
changed it: run `git log -1 -- tracker/LOGS.md`. If `git log` shows later
commits, this note is older than the code, so read those commits before trusting
it. Where this note and git disagree, git is right.

**The build mode.** From Phase 2, every unit is built at its minimal version.
- Each unit's minimal, full and given-up versions are in
  `planning/SIMPLIFICATION.md`. PLAN §8 states the pivot, and `CLAUDE.md`
  carries the rule.
- Keys, signing and spend authority keep their full guard.
- The operator is stopped at 2.1, 3.8, 5.4, 6.6, 7.5 and 8.5. 2.1 was approved.
  **3.8 has run and is shown, waiting for the operator.**

**The deadline** was given at about 11:00Z on 2026-09-19 as "about 16 hours":
about Sun 2026-09-20 03:00Z. That is this note's arithmetic, not a time the
operator wrote down. This note was written at about 17:40Z.

**Check it in a minute.** Nothing here spends unless marked. The `python3 -m`
commands need `PYTHONPATH=src`.
- `git log --oneline -25` and `git status -sb`.
- `make test`: 521 passed when this was written, in about 24 s. The runner and
  risk tests start real subprocesses against a fake gateway on 127.0.0.1.
- `python3 -m fund.run.decide --snapshot fixtures/snapshots/66852293-253315c0e691
  --approved-reports --quotes Q --risk-reply R [--env-file E]` takes reports to
  a signed record and executes nothing. The flags:
  - offline, it needs a recorded quotes file and a recorded risk reply;
  - `--live-quotes` reads the venue, read-only;
  - `--confirm` makes one live risk call, which **spends**;
  - `--cycle DIR` takes a runner cycle's accepted reports instead.

  It signs with `.env`'s `SIGNING_KEY` unless `--env-file` names another. Do
  not sign fake inputs with the fund's key.
- `python3 -m fund.agents.show <cycle dir>` prints a stored report as written.
- `python3 -m fund.agents.runner --snapshot <path> ...` **spends** with
  `--confirm`.
- `python3 -m probes.keymap`: each key's measured capabilities, read-only. Run it
  before any live call.
- `make replay` rebuilds the committed capture offline. `make check-env` names
  the credentials present. `make selftest` needs the RPC URL. `make snapshot`
  builds a live snapshot in about 2.5 minutes.

### Done
- **Phases 0 and 1,** at full depth.
- **Phase 2, 2.0 to 2.7.** 2.8 is not closed, though its three cases exist as
  2.4's tests. The exit run has not happened, so Phase 2's exit is not met: one
  seat of four has had an accepted real report, and no seat has its own account.
- **Phase 3, 3.1 to 3.7,** offline, in one pass (entries above). It was built on
  the four approved reports, the committed capture, a labelled fake venue,
  scripted risk replies and 2.4's fake gateway.
- **3.8's run** (entry above; `research/findings.md` §3.8):
  - the exit run, four live calls on the committed capture, all replied and
    all refused;
  - so no quorum;
  - the fund's real decision, `2c9c1a79…`, signed with its key: no rebalance,
    no order, no risk call and no veto.

  Recorded in `fixtures/cycles/20260919T171351Z/`.
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
    `core/record.py`;
  - `agents/risk.py` and `agents/briefs/risk.v1.md`;
  - `treasurer/sign.py`;
  - `run/decide.py`.

  Every other module is a stub: `grep -l "Not yet built" -r src/` lists 17.

### Next
- **3.8 waits on the operator.** No veto happened, because no report was
  accepted. The choices, in `research/findings.md` §3.8 and LESSONS:
  - fix the two validator defects: thousands separators, and brackets read as
    citations. That rescues price-integrity alone;
  - whether a real value cited under the wrong path should refuse a report;
  - a brief line on citing other assets by symbol and fields by full path;
  - the refused replies carried in the signed record;
  - another exit run, about $1.10, then the decision with a live risk call,
    about $0.05.
- **3.9 after that.** It replays the recorded cycle's record byte for byte.
  `fixtures/cycles/20260919T171351Z/` is a recorded cycle, though of a no-op.
- **Owed from Phase 2, unchanged:**
  - the settled `/v1/usage` cross-check for the 15:39Z and 15:58Z calls, and
    whether the 504 was billed;
  - the 504: cross-asset-macro answered in 89 s at 3.8, so the limit is
    neither shown nor ruled out;
  - 2.0's choice, (a), (b) or (c);
  - 2.8;
  - the page slice.
- **Owed from Phase 3:**
  - the mandate is provisional: 4.1 replaces the allowed assets and the
    placeholder approvals;
  - the confidence mapping is provisional, to be tuned after a real cycle;
  - no real model has seen `risk.v1.md`;
  - `run/decide.py`'s `--live-quotes` and `--confirm` ran at 3.8, but with no
    order, so no quote and no risk call was made;
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
  closes. The committed one is `253315c0…` at block 66852293, in
  `fixtures/snapshots/`.
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
- **LLM credits:** $14.678389 before 3.8's four calls, which cost $1.087706.
  It was not re-read after them.
- **Phase 3, offline, on the four approved reports:**
  - META 12.5%, AMD, INTC and USO 6.25% each, 68.75% cash;
  - four buys totalling $62.50 of the $200 paper book;
  - a risk bundle of about 32,400 tokens, 12,000 of them reserved.
- **Wallet:** about $1.29, as 0.078742 USDG and 0.000460 ETH on 4663.

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
- **Still null:** `cadence.json`'s `confirmation_depth`; `mandate.json`'s
  `cumulative_budget_usd`.

### Committed versus pushed
Checked locally, with no fetch. `origin/main` is `837a6ce`, pushed by the
operator. Every commit from `a4c2bf6` (3.1's config) to the one that last
changed this note is committed and **not pushed**.

### What this note does not cover
- **Decisions.** LESSONS holds them in full.
- **The plan.** PLAN, ROADMAP, PHASE-0-1, PHASE-2 and SIMPLIFICATION are the
  plan.
- **Credentials.** It checks none beyond `make check-env`'s names.
- **Unrecorded conversation.** Anything not written into `tracker/`,
  `planning/`, `config/` or `research/` is lost on restart.
