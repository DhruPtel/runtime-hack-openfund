# Working on openfund

## Verification scales with risk (operator, 2026-09-18, at the Phase 1 gate)

**High risk: keep the full discipline.** Money, identity, spend authority and
the signed record. Break the rule in a copy, confirm a test fails, and show it.
- **Money:** marks, valuation, sizing, orders, the books.
- **Identity:** the registry, the beacon, the address table.
- **Spend authority:** keys, roles, the one signing path.
- **The signed record:** snapshots, decisions and what they cite.

**Lower risk: a passing test is enough.** Presentation, formatting, plumbing,
and rules already guarded elsewhere. Do not break the code to prove the test
works.

This changes the pace, not the standard. If something looks wrong while moving
quickly, stop and say so.

The plan is `planning/` (PLAN, ROADMAP, PHASE-0-1). The history is `tracker/`:
LOGS records what was built, LESSONS what changed and why.
