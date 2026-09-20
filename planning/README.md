# `planning/` — the plan, and how it changed

The plan is not a record of what was intended. It is a record of what was **decided**,
including the decisions that reversed earlier ones, with the reason attached.

| Document | What it is for |
|---|---|
| `PLAN.md` | the current plan. §2 holds the invariants that never bend, §13 every stated limitation |
| `PLAN-v1.md` | the first plan, kept because several of its claims were wrong and the corrections are traceable |
| `PLAN-technical-review.md` | an outside technical review of v1 |
| `REVIEW-RESPONSE.md` | what was accepted from that review, and what was not |
| `ROADMAP.md` | every unit and checkpoint, with what each was actually cut down to |
| `SIMPLIFICATION.md` | the pivot: for every unit, the minimal version, the full version, and **what was given up** |
| `PHASE-0-1.md`, `PHASE-2.md`, `PHASE-4.md` | the detail for those phases |
| `PHASE-1-GATE.md` | the gate review at the end of Phase 1 |
| `CODEBASE.md` | the target file tree and the one-way dependency rule, stated as tests |
| `REPORT-FORMAT.md` | what an analyst report must contain, approved before any code read one |
| `JUDGING-CRITERIA.md` | the six criteria, and where the record stands against each |

**Read `SIMPLIFICATION.md` first** if you want to know what this project is *not*. Every
row names what was given up to ship, which is more useful than a feature list: the
crash drill that became two kill drills, the reorg handling that became a fixed
confirmation depth, the attribution that became shares rather than dollars.

**Decisions are dated and attributed.** "The live leg is a demonstration of the money
path that no analyst chose" is a decision with a date, and when it was built differently
from the proposal, the document was corrected and says why — appending a real-book order
to a paper plan would have counted the wallet's USDG as paper cash.
