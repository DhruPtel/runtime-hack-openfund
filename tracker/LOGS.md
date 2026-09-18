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
