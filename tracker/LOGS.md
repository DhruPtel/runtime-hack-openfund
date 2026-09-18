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

---

## State at close — 2026-09-18 (third session)

**Done.** 0.1 through 0.8, the out-of-order Testnet probe, and 0.7's follow-ups
b–e. 0.9 was run early as a labelled floor; the full cost probe is still unit
1.7, against the real snapshot. 32 tests, offline, no credentials. Every probe
has a verdict in `research/findings.md`, marked measured / documented / inferred.

**Decided since the last note.** At the 0.4 checkpoint: a Chainlink feed is a
membership condition (35 markable assets), divergence is tiered by corroborator
liquidity, and depth returns as corroborator quality only. At the close of 0.8:
registry membership on `(chain_id, address)` is the identity test, pinned by
sha256; `uiMultiplier()` and the name marker are retired; the beacon is a
cross-check that fails the cycle loudly; feed presence is markability, not
identity.

**Measured since the last note.** 0.6: provider cost is attributable only in
aggregate. 0.7–0.7d: our endpoint settles, revenue is an on-chain
`PaymentSettled`, and a paid round trip is ~4.6 s. 0.7e: the v1 x402 clients
cannot pay us, while the v2 client `@x402/fetch` can — signed by Bankr's service,
so a third-party buyer is inferred. 0.9: an analyst call costs $0.0134 and takes
58 s at the floor, and a single-block snapshot gives a trend analyst nothing.

**Open.**

- Whether the feed already includes `uiMultiplier` is still **not** measured
  (F0.4.4); 1.4 follows the documented rule and must say so.
- Whether `BANKR_KEY_EXEC` can **transact** is still unproven (F0.5.5). 0.10 is
  the first unit that can show it.
- The 0.7 checkpoint's price question: $0.05 needs 1.3–2.3 sales a day to cover
  inference at the floor (F0.9.4), and no third party has ever paid us.
- Config values still null whose named resolver has already run:
  `feed_staleness_max_seconds`, `quote_max_age_seconds`, `impact_max_bps`,
  `worker_deadline_seconds`, `analyst_model`.

**Not run.** 0.10 (idempotency and rate limits; spends) and the 0.11 checkpoint.

**Funding**, wallet balances re-read over RPC. Base: 0.000241 ETH, 0.107346
USDC, 10 USER. Robinhood Chain: 0.000490 ETH and no USDG, against the ~$200 in
`planning/PLAN.md` §11. LLM gateway: $2.799976 as last measured, at 0.9 (F0.9.3).

**Next.** Sync the plan docs to the decisions above, run 0.10, then hold the
0.11 checkpoint. Unit 1.5 must still re-run probe 0.3 against a USDG-funded
wallet before its numbers count as evidence about liquidity.
