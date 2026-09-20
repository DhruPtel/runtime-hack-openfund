"""Cheap tick, overlap fencing, kill switch.

**Not built, and nothing calls this.** Unit 8.1 owns it (`planning/ROADMAP.md`).
Until it exists the fund has no scheduler: every cycle is started by hand, with
`python3 -m fund.run.cycle` for a paper cycle and `python3 -m fund.run.liveleg` for
the live leg, and the guards a scheduler would need are already elsewhere — one
runner at a time and what the last run left are `run/startup.py`'s (4.9, 4.10), and
the cycle's own deadline is `config/cadence.json`.

This file is a placeholder for the unit, not a missing import.
"""
