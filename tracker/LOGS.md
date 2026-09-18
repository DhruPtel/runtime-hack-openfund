# Build log

A running record of what was built, one entry per unit, appended as the build
proceeds. Written to be skimmed: a reader should be able to scan it top to bottom
and watch the system being assembled.

Entries are factual. What exists, what you can look at, what proves it works. No
narrative. The honest counterpart to this file is [LESSONS.md](LESSONS.md), which
records what went wrong and what changed in the plan as a result.

Unit numbers are `<phase>.<unit>` and match [ROADMAP.md](../Plan/ROADMAP.md).
Units marked ▶ in the roadmap are playtime checkpoints: the entry for one records
what the human saw and what they decided.

## Entry format

```
## <phase>.<unit> — <short description>
**Date:** YYYY-MM-DD
**Commit:** <sha>
**Built:** what now exists that didn't before.
**Artifact:** the file, command, or output a reader can look at.
**Verified by:** the test or check that proves it works.
```

---

## 0.0 — Onboarding: plan read, tracker established
**Date:** 2026-09-17
**Commit:** bbe824e
**Built:** `tracker/` with this log and `tracker/LESSONS.md`. `README.md` expanded
from placeholder to a judge-facing overview: the cycle, the three differentiators,
the architecture line, intended run commands, and an explicit planning status.
No `src/`, no `probes/`, no product code.
**Artifact:** `tracker/LOGS.md`, `tracker/LESSONS.md`, `README.md`.
**Verified by:** Read of `PLAN.md`, `REVIEW-RESPONSE.md`, `ROADMAP.md`,
`PHASE-0-1.md`, `CODEBASE.md`, `PLAN-technical-review.md` and the seven reports
in `research/`. Fifteen decisions and plan changes recorded in
`tracker/LESSONS.md`, the largest being that the operator is US-based, so
tokenized-stock execution is unavailable and stock legs are paper. PLAN.md v2 and
REVIEW-RESPONSE.md were absent at the start of the session and supplied during
it; PLAN-v1.md was superseded and removed.

## 0.1 — Repo skeleton and credential redaction
**Date:** 2026-09-17
**Commit:** bbe824e
**Built:** The target tree from CODEBASE.md, with docs moved to the repository
root and the package at `src/fund/`. Placeholder modules for every file the tree
names, each stating the unit that fills it, so an empty file is legible rather
than mysterious. Three modules carry real code:

- `src/fund/credentials.py` — the credential table from PLAN.md §6 as the single
  source of truth, with a `Role` (analyst / treasurer) on every row.
- `src/fund/redaction.py` — denylist built by reading the table out of the
  environment. A filter masks message and arguments; a formatter masks the
  fully formatted record, which is what covers exception tracebacks.
- `src/fund/config.py` — `.env` loader (real environment always wins) and
  role-scoped credential access. An analyst process asking for `BANKR_KEY_EXEC`
  or `SIGNING_KEY` raises rather than returning it.

Plus `config/` with the locked decisions recorded and every unresolved value
explicitly `null` (null means unresolved and blocks the check that reads it,
never a default), `.env.example` as a manifest with no values, `pyproject.toml`,
`Makefile`, and a `.gitignore` covering `.env`, database files and
`fixtures/live/`.

**Artifact:** `make test`, `make check-env`, `src/fund/credentials.py`,
`tests/test_redaction.py`, `config/README.md`.

**Verified by:** `tests/test_redaction.py`, 25 tests, all passing offline.
Covers each declared credential masked in a log line; masking when passed as a
logging argument; masking inside an exception traceback; role scoping in both
directions; `Config.__repr__` containing names but no values; and
`.env.example` matching the table with empty values. The load-bearing test is
`test_a_new_credential_is_masked_without_touching_the_filter`: it adds a
credential that did not exist when `redaction.py` was written and asserts it is
masked anyway, which is the property PHASE-0-1.md asks for — adding a credential
cannot create an unredacted path.

**Not done:** no dependency lockfile yet (unit 0.1 is stdlib only, so there is
nothing to lock beyond pytest). Redaction covers literal occurrences only; a
secret that is URL-encoded or base64'd before being logged is not caught, and
`adapters/http.py` (unit 1.3) owns the rule that raw request bodies are never
logged.
