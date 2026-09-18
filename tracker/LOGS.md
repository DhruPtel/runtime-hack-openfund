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

---

## State at close — 2026-09-18

**Done.** Units 0.1 (repo skeleton, config loader, credential redaction), 0.2
(auth headers and key permissions), 0.3 (quote shape) and 0.4 (Chainlink feeds,
coverage and the multiplier). 32 tests, offline, no credentials. Findings for
0.2, 0.3 and 0.4 are in `research/findings.md`, each marked measured /
documented / inferred with a pass / fail / unresolved verdict.

**At the checkpoint, undecided.** 0.4 is a ▶ checkpoint and its table has been
shown but not ruled on. Three decisions are open and none has been taken inside
the probe:

- **Does "depth" return?** It was deleted on 2026-09-17 because the plan said
  tokenized stocks have no AMM pool to measure. They do — SPY holds $9.16M in one
  USDG pool (F0.4.3). The false clause in planning/PLAN.md §13 is corrected; the
  operational definition of tradeable is untouched pending this call.
- **What does `divergence_max_bps` become?** Still null. A flat threshold cannot
  work: divergence runs 19.5 bps median on liquid names and 164.7 on illiquid
  ones, worst case 610 (F0.4.5).
- **Is a Chainlink feed a membership condition at 1.2?** Only 35 of 187 marked
  tokens have one (F0.4.8).

**Carried forward as unresolved.** Whether the feed answer already includes
`uiMultiplier` is **not** measured and 0.4's done-condition is half met
(F0.4.4). Two documented sources say it is already applied and 1.4 follows them,
labelled documented. Settling it needs a multiplier large enough to clear a 142
bps noise floor, or an archive read the one public 4663 endpoint cannot serve.

**Blocked.**

- **0.5 (execution eligibility)** and **0.10 (idempotency and rate limits)** have
  not been run. Both spend real money with real credentials and need explicit
  per-probe authorization. 0.5's expected verdict is **fail** — the operator is in
  the US and tokenized-stock execution is location-gated — but it is run to
  capture the exact 403, not skipped because the answer is predicted.
- **Funding.** The wallet holds ~$2 of ETH on Base and nothing on Robinhood
  Chain, against the ~$200 in planning/PLAN.md §11. The LLM gateway holds $3.00,
  clearing the 402 that blocked Phase 2.

**Next.** 0.6 (credits and usage) and 0.8 (issuer allowlist and the beacon check)
both run today with what is already in `.env`; 0.8 now has both a concrete case
to solve in the three GME tokens and a working discriminator in `uiMultiplier()`
(F0.4.6). 0.7 (x402 round trip) needs USDC on Base. Unit 1.5 must re-run probe
0.3 against a funded wallet before any of its numbers count as evidence about
liquidity, and 0.4's divergence numbers are one block on one day during market
hours — they do not bound the overnight or weekend tail.
