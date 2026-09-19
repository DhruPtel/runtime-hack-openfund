# Working on openfund

## Build mode from Phase 2: minimal versions (operator, 2026-09-19)

Before building any unit from 2.1 on, read its row in
`planning/SIMPLIFICATION.md` and build the minimal version. PLAN §8 states the
pivot, and `planning/PHASE-2.md` details Phase 2, which opens with 2.0 (the
SIWE agent-wallet proof). Keys, signing and spend authority keep their full
guard. Stop at 2.1, 3.8, 5.4, 6.6, 7.5 and 8.5. 2.1 is the report format:
the operator reads it before any code consumes it.

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

## Dated obligations

- **Monday 2026-11-09: re-derive the closed session.** US clocks go back on
  2026-11-01. If the equity feeds follow New York time, from Saturday
  2026-11-07 they publish until 01:00Z, inside the span in
  `config/sessions.json`, and every equity price is undetermined until the
  span is re-derived. Run `python -m fund.adapters.chain_4663 --sessions`,
  review it, and write it into `config/sessions.json` by hand (PLAN §13).
- **From Monday 2026-09-21 00:00Z: the weekday capture.** Take it during an
  open session, ideally 13:30–20:00Z:
  `PYTHONPATH=src python3 -m fund.run.snapshot --capture fixtures/snapshots`.
  Scan it for every declared credential value, then commit it beside the
  weekend capture, which stays.

The plan is `planning/` (PLAN, ROADMAP, PHASE-0-1, SIMPLIFICATION;
JUDGING-CRITERIA for the submission). The history is `tracker/`: LOGS records
what was built, LESSONS what changed and why.
