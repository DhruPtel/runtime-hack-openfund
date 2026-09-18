# config/

Every tunable value in the system. planning/CODEBASE.md section 8 lists "a threshold
appearing as a literal anywhere outside `config/`" as a sign we got it wrong.

## The null convention

A value of `null` means **unresolved**, not zero and not "no limit". It is the
three-valued rule from planning/PLAN.md section 2 invariant 5 applied to configuration:
a required check must be explicitly true, and null blocks execution.

Code that reads a null threshold must refuse to run the check that depends on
it. It must never substitute a default. Each null below carries a
`_resolved_by` note naming the probe or unit that will supply it.

## Files

| File | Holds | State |
|---|---|---|
| `universe.json` | issuer allowlist, `(chain_id, address)` to feed and decimals | empty until probe 0.8 |
| `analysts.json` | the roster and its scope partition | provisional until checkpoint 2.1 |
| `thresholds.json` | staleness, divergence, quote age, impact, turnover, cash floor, quorum | mostly unresolved |
| `mandate.json` | bounds, wallet, chain, allowed assets, budget, expiry, revocation | wallet unresolved |
| `models.json` | pinned model ids, token caps, deadlines | unresolved until unit 1.7 |
| `cadence.json` | schedule, confirmation depth, retry budgets | schedule set |
