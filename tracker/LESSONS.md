# Lessons

A history of what went wrong, what surprised us, and what changed as a result.

**This file is history, not authority.** [planning/PLAN.md](../planning/PLAN.md),
[planning/ROADMAP.md](../planning/ROADMAP.md) and [planning/PHASE-0-1.md](../planning/PHASE-0-1.md) are the
authoritative plan; every change recorded here has been folded into them. An
entry says what we believed, what reality said, and what we did about it — it is
the record a judge reads to see whether the plan bent when it should have.

The honest counterpart is [LOGS.md](LOGS.md), which records what was built.

## When an entry gets written

A probe contradicts a claim we had documented as fact; a phase or unit changes
shape; an approach is abandoned; or a checkpoint sends us back. Not for ordinary
bugs fixed in the normal course of work — those belong in the commit history.

## Entry format

```
## YYYY-MM-DD — <short title>
<What happened, what changed, what it affects. Three sentences unless the change
is genuinely complex. Evidence compressed to a file reference.>
**Affects:** <units>
```

---

## 2026-09-17 — Operator is in the US; tokenized-stock execution is unavailable
Bankr gates tokenized-stock trades behind location verification with the US
excluded, and the operator is US-based, so live stock fills are unreachable for
this build — the plan's largest binary unknown resolved against us before a line
of code was written (`research/bankr-skills.md`, quoting Bankr's
`tokenized-stocks.md:73-79`; anticipated by `PLAN-technical-review.md` finding
12). Stock legs become paper, sized and priced from real live quotes through the
same executor interface, while real on-chain activity now comes from ungated
memecoin/USDG swaps on 4663, so the order state machine, receipts,
reconciliation and explorer evidence are genuine rather than mocked. Probe 0.5
still runs to capture the exact 403 and confirm the gate; its expected verdict is
now **fail**, not unresolved.
**Affects:** Phase 5 (renamed and rescoped), probe 0.5, planning/PLAN.md §13, the demo story.

## 2026-09-17 — Capital and trade size fixed at ~$200 and $25
Nothing in the plan gave a capital figure or a trade size, which blocked unit
1.5's requirement to quote at intended size, the cost model, and every
dollar-denominated gate. Capital is ~$200 with a $25 nominal per-trade quoting
size, both well inside Bankr's documented $500/24h and $500/tx platform caps, so
the platform caps are a backstop rather than a binding constraint.
**Affects:** 1.5, 3.3, 3.4, 4.1; `config/thresholds.json`, `config/mandate.json`.

## 2026-09-17 — Cadence set to daily, plus a manual trigger
Cadence was open in planning/PLAN.md §12 and blocked `config/cadence.json`, the scheduler
and the cost-per-day figure. It is now a daily scheduled cycle plus a manual "run
cycle now" trigger that goes through the identical code path — a trigger, not a
demo mode. At $25 trades a higher frequency would burn inference budget against
trades too small to justify it, which is the same economics behind
`research/agent-os.md`'s advice to prefer a cheap script tick over an agent turn
on a job that is usually a no-op.
**Affects:** 8.1, 8.3; `config/cadence.json`.

## 2026-09-17 — x402 price set at $0.05 per decision record
The endpoint had no price, so revenue could not be modelled and checkpoint 0.7
had nothing concrete to judge. Priced at $0.05 per decision record in USDC on
Base, the rail being fixed by `research/x402-cli-example.md` §7, which shows the
standard client's network enum rejects 4663 outright. Provisional until the
relocated analyst-cost probe (now unit 1.7) reports real per-cycle inference
cost.
**Affects:** 0.7, 1.7, 6.1, 7.2–7.4.

## 2026-09-17 — Roster fixed at four analysts, with scopes partitioned in config
Nothing stated how many analysts there are or what they do, leaving the
product's core shape to be decided under time pressure at checkpoint 2.1. The
roster is four analysts, one risk agent and one treasurer, with scopes declared
deterministically in `config/analysts.json` rather than decomposed by a lead
model at runtime: the universe is known in advance, so the partition is disjoint
by construction, not by instruction. Scopes are disjoint in **question**, not
necessarily in asset set — two analysts may both look at every asset provided
they ask different things of it, and the failure mode is two analysts asking the
same question of overlapping assets. Bounding fan-out explicitly rather than by
default is the lesson from `research/agent-os.md` (width unbounded unless
configured) and `research/miroshark.md` (personas divided by instruction,
divergence unbounded).
**Affects:** 2.1, 2.3, 2.4, 3.1, 6.4; `config/analysts.json`.

## 2026-09-17 — Repo layout: `research/`, `src/fund/`, and docs in `planning/`
The actual layout (`Plan/`, `Research/`) contradicted the target tree in
planning/CODEBASE.md §2, and unit 0.1 builds the skeleton, so building against
the wrong layout would have guaranteed a later move. `Research/` was renamed to
`research/` and the package placed at `src/fund/` per planning/CODEBASE.md §2,
which wins over planning/PLAN.md §7's bare `src/`. Planning documents were first
moved to the repository root, then into `planning/` so that only README.md sits
at the top level; PLAN-v1.md was restored from history to sit alongside v2 for
comparison.
**Affects:** 0.1 and every relative doc link. No behavioural change.

## 2026-09-17 — "Depth" removed as a concept
The tradeability filter gated on depth while the plan simultaneously asserted
that tokenized stocks have no AMM pool of their own, so it was gating on a number
that cannot exist — precisely the failure `PLAN-technical-review.md` finding 3
predicted, an AMM-liquidity filter excluding every RFQ-tradeable stock
(`research/bankr-skills.md`, quoting `tokenized-stocks.md:42`). Depth is deleted
from the vocabulary; **tradeable** now means a quote at intended size succeeded,
quote age is within bound, and impact is either known and within limit or null —
and null blocks. This keeps the liquidity requirement but defines it against the
venue we actually trade on rather than inventing reserves.
**Affects:** 1.5, 1.6, 3.4, 3.8; planning/PLAN.md §9; `config/thresholds.json`.

## 2026-09-17 — Probe 0.4 tests GeckoTerminal coverage before divergence
Probe 0.4 was specified as a Chainlink-versus-GeckoTerminal divergence table, but
GeckoTerminal prices come from pools and RH stock tokens have no pool of their
own, so the probe assumed coverage that no research report demonstrates — every
GeckoTerminal use across `research/` is pool-derived. 0.4 now tests coverage
first and divergence only if coverage exists; if coverage is absent the
corroborating source becomes a Bankr quote at size, recorded explicitly as **not
independent of the execution venue**, and the divergence veto changes from
cross-source to quote-versus-feed, which is a weaker check and must be labelled
as one.
**Affects:** 0.4, 1.4, 3.4; planning/PLAN.md §11.

## 2026-09-17 — Probe order: 0.8 before 0.3, and 0.9 relocated to unit 1.7
Probe 0.3 quoted against a stock address that probe 0.8 is what establishes,
which on a permissionless chain carrying a known fake GME meant quoting against
an unverified address; separately probe 0.9 measured analyst token cost from "a
real snapshot" that does not exist until unit 1.6, and snapshot bytes dominate
the count being measured. 0.8 now runs before 0.3, and 0.9 moves into Phase 1 as
unit 1.7, immediately after the snapshot builder. Phase 0 unit numbers are
otherwise unchanged so existing references stay valid; the 0.9 slot is marked
relocated rather than reused.
**Affects:** Phase 0 order and exit, Phase 1 (1.7 new, old 1.7–1.10 shift to
1.8–1.11), and the 0.7 price, which stays provisional until 1.7 reports.

## 2026-09-17 — Agent API stays off on both Bankr keys
Unit 0.2's done-condition required confirming the Agent API toggle is **on**,
while planning/PLAN.md §6 specifies it off and nothing in the system calls
`/agent/prompt` — a leftover from an earlier design that bounded fan-out on the
Agent API's 100/day quota (`PLAN-technical-review.md` finding 13; the figure is
sourced to Agent API documentation in `research/bankr-claude.md`). Agent API is
off on both keys, and 0.2 now confirms the gateway toggle on for `BANKR_LLM_KEY`,
Agent API off for both Bankr keys, and which auth header each surface accepts.
Leaving an unused write-capable surface enabled is exactly what
`PLAN-technical-review.md` finding 2 warns about.
**Affects:** 0.2; planning/PLAN.md §6 and §10.

## 2026-09-17 — RPC requirement reduced to timeout plus fail loudly
Unit 1.3 required RPC failover that advances on hang, but exactly one public 4663
endpoint is documented and it carries no archive data (`research/agent-os.md`
§8), so the plan specified a resilience mechanism with nowhere to fail over to.
The requirement reduces to explicit request timeouts plus fail loudly, no archive
reads are assumed anywhere, and historical reproducibility comes from the fixture
capture in unit 1.9 rather than from re-reading the chain. This is a reduction
and is stated in planning/PLAN.md §13.
**Affects:** 1.3, 1.9, 1.10; planning/PLAN.md §13.

## 2026-09-17 — Every "first in the ecosystem" claim removed
The plan claimed the first non-zero x402 revenue line in the ecosystem, which our
own evidence folder contradicts: `research/bankr-skills.md` documents `urizen`
describing itself as the first autonomous fund on Robinhood Chain, already
serving book, trades, mirror and signals endpoints. Removed from planning/ROADMAP.md
checkpoint 7.5, which now asks whether revenue reconciles from settlement
evidence rather than from a handler log. The differentiator is reconciled books
with visible exceptions and a veto that is a code path, none of which depends on
being first.
**Affects:** planning/ROADMAP.md 7.5, README.md, 8.6.

## 2026-09-17 — Invariant 6 reworded: replay from recorded outputs, not seeds
"Everything stochastic is seeded" implied that seeding produces comparable model
runs, which it does not, while unit 3.9 already specified the correct mechanism
(`PLAN-technical-review.md` finding 9). The invariant now reads: deterministic
replay comes from recorded model outputs including the risk output, and seeds
apply to our own code only. Fresh inference against a recorded snapshot is a
separate experiment and is labelled as one, never presented as a replay.
**Affects:** planning/PLAN.md §2; 2.5, 3.7, 3.9; `config/models.json`.

## 2026-09-17 — New unit 4.12: treasurer as its own process
planning/PLAN.md invariant 1 requires the treasurer to run as its own process, proven by
an environment test rather than an import graph, and planning/CODEBASE.md §3 calls that
"the one that matters most" — but no unit in any phase built it, so the strongest
safety claim in the plan had nothing behind it (`PLAN-technical-review.md`
finding 2). Unit 4.12 is added at the end of Phase 4: the treasurer as its own
process with its own credentials, reading approved intents from SQLite, plus the
deployed-isolation test asserting that execution and signing credentials are
unreadable from the analyst process and a raw HTTP swap from there fails.
**Affects:** Phase 4 exit, `tests/test_boundaries.py`, Phase 5 (no real
submission before 4.12 passes), planning/PLAN.md §5.

## 2026-09-17 — Phase 5 renamed "live chain activity" and rescoped
Phase 5 was gated on probe 0.5 passing with an exit of a live stock buy-and-sell
round trip, which with stock execution unavailable would have left the build with
no real chain activity, no genuine receipt and nothing on an explorer. Phase 5
becomes **live chain activity**, exiting on a real transaction on 4663 executed
through the treasurer, reconciled from its receipt and booked exactly once; live
stock fills are out of scope and stated in planning/PLAN.md §13. Unit 5.6 still runs, and
the 403 is now the expected result for the stock path rather than an error case.
**Affects:** Phase 5 name, units 5.1–5.7 and its exit; planning/PLAN.md §13; 8.4 and 8.6,
which must state the paper/live split without burying it.
