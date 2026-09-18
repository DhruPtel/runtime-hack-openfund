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
| `registry/` | the allowlist. The raw bytes of the pinned issuer registry and Chainlink feed directory, each named by its sha256, which is its version. `pins.json`: those versions, plus our own pins — issuer beacon, USDG cash leg, gas. `feed_map.json`: which feed marks which asset, by address, reviewed. Replaces the retired `universe.json` | pinned (unit 1.2) |
| `analysts.json` | the roster and its scope partition | provisional until checkpoint 2.1 |
| `thresholds.json` | staleness, divergence, quote age, impact, turnover, cash floor, quorum | divergence, quote age and impact set, provisionally; staleness rule and margin set; position limits and quorum unresolved |
| `mandate.json` | bounds, wallet, chain, allowed assets, budget, expiry, revocation | wallet named; bounds, budget and approval unresolved (unit 4.1) |
| `models.json` | pinned model ids, token caps, deadlines | analyst model, worker deadline and transport timeout provisional; the rest unresolved |
| `cadence.json` | schedule, confirmation depth, retry budgets | schedule set |
