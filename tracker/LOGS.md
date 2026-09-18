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
**Date:** 2026-09-18 · **Commit:** uncommitted

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
**Date:** 2026-09-18 · **Commit:** uncommitted

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

---

## State at close — 2026-09-18 (second session)

**Done.** Units 0.1, 0.2, 0.3, 0.4 (Chainlink feeds, coverage and the
multiplier) and 0.5 (execution eligibility). 32 tests, offline, no credentials.
Findings for 0.2–0.5 are in `research/findings.md`, each marked measured /
documented / inferred with a pass / fail / unresolved verdict.

**0.5 is settled: stock execution is refused for region.** 403, pre-broadcast,
no gas, body naming both gate and asset. planning/PLAN.md §13 and the
2026-09-17 decision to make stock legs paper are both confirmed on evidence
rather than documentation. Nothing in the plan changes.

**0.4 is still at its checkpoint, undecided.** Three decisions remain open and
none has been taken:

- **Does "depth" return?** Deleted on 2026-09-17 because the plan said tokenized
  stocks have no AMM pool to measure. They do — SPY holds $9.16M in one USDG
  pool (F0.4.3). The false clause in §13 is corrected; the operational
  definition of tradeable is untouched pending this call.
- **What does `divergence_max_bps` become?** Still null. A flat threshold cannot
  work: 19.5 bps median on liquid names, 164.7 on illiquid, worst case 610
  (F0.4.5).
- **Is a Chainlink feed a membership condition at 1.2?** Only 35 of 187 marked
  tokens have one (F0.4.8).

**Carried forward as unresolved.**

- Whether the feed already includes `uiMultiplier` is **not** measured (F0.4.4);
  the effect is 22 bps against a 142 bps noise floor. 1.4 follows the two
  documented sources and must label them documented.
- Whether `BANKR_KEY_EXEC` can **transact** is still unproven (F0.5.5). The
  location gate fired first, so the read-only-key cause was never reached.
  **Phase 5's live leg rests on this and should not be treated as de-risked.**
  One ungated ETH→USDG swap with the same key settles it; it is a second spend,
  was not authorised by 0.5, and belongs at the head of Phase 5.

**Blocked.** 0.10 (idempotency and rate limits) has not been run and needs
explicit per-probe authorization. 0.7 (x402 round trip) needs USDC on Base.

**Funding.** $0.63 of ETH on Base and $1.28 on Robinhood Chain — funded since
0.2, which is what made 0.5 runnable. No USDG or other tokens on any chain,
against the ~$200 in planning/PLAN.md §11. The LLM gateway holds $3.00.

**Next.** 0.6 (credits and usage) and 0.8 (issuer allowlist and the beacon
check) both run today with what is already in `.env`; 0.8 has a concrete case in
the three GME tokens and a working discriminator in `uiMultiplier()` (F0.4.6).
Unit 1.5 must re-run probe 0.3 against a wallet funded with USDG before any of
its numbers count as evidence about liquidity, and 0.4's divergence numbers are
one block on one day during market hours — they do not bound the overnight or
weekend tail.
