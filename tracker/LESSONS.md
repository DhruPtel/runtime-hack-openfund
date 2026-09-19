# Lessons

A history of what went wrong, what surprised us, and what changed as a result.

**This file is history, not authority.** [planning/PLAN.md](../planning/PLAN.md),
[planning/ROADMAP.md](../planning/ROADMAP.md) and [planning/PHASE-0-1.md](../planning/PHASE-0-1.md) are the
authoritative plan; every change recorded here has been folded into them —
checked entry by entry on 2026-09-18, after this claim had been false since
before 09:10 that day. Where a fold exposes a contradiction, the plan doc marks
it open rather than reconciling it.

**Pending folds: none, as of 2026-09-18, after 1.4.** The two folds owed in
`planning/PHASE-0-1.md` 1.3 since 1.3's close-out were made in 1.4's pass: the
staleness-exception DECISION, and the verdict naming a schedule, not a
session. Every 1.4 entry was folded in the same pass, into PLAN, PHASE-0-1,
CODEBASE and `config/`. Two entries leave questions marked open in the plan
docs rather than reconciled: where the divergence tier is compared, and which
unit revisits the staleness exception.

Every earlier entry was checked as folded: the 1.2 and 1.3 entries in their own
passes, and the older ones entry by entry before unit 1.1.

That older check has its own history. The Phase 1 replan could write only to
`planning/PHASE-0-1.md`, `config/` and `tracker/`, so three entries below carry
a *fold pending* marker. Those folds were made in the next pass, into PLAN §8,
§9, §12 and the Phase 5 text, and into ROADMAP's Phase 1 and Phase 5 text. The
markers are left in place as the record of when each fold was late. An
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

## 2026-09-17 — All three Bankr keys come from one account
`make check-env` reported four credentials present but only three distinct
masked values: `BANKR_KEY_EXEC` and `BANKR_LLM_KEY` were the same string, which
would have put the fund's spend credential in every analyst process and made
planning/PLAN.md §2 invariant 1 decorative. The decision is three scoped keys
from **one** Bankr account rather than two separate accounts, so account-level
separation does not exist and the whole boundary now rests on per-key toggles:
`BANKR_KEY_READ` and `BANKR_LLM_KEY` carry Read Only ON, only `BANKR_KEY_EXEC`
has the Wallet API with Read Only OFF, and no key the analyst role can load may
transact. What this weakens: a compromised analyst path is one console action or
one mistaken toggle away from spend authority, whereas separate accounts would
have made that a second credential the attacker does not have; the blast radius
of the account owner's own credentials is now the whole fund; and revoking the
execution key cannot be done without touching the account the analysts depend
on. The rule is enforced by a `can_transact` field asserted in tests rather than
by prose, and probe 0.2 verifies the toggles against the live surfaces rather
than trusting the console.
**Affects:** 0.2, 4.12 (the isolation test now proves a per-key rather than a
per-account boundary), planning/PLAN.md §6 and §13.

## 2026-09-17 — Probe 0.2: key scoping is by capability, not by surface
`BANKR_LLM_KEY`, scoped "gateway only" in planning/PLAN.md §6, returned 200 and a
full portfolio from `GET /wallet/portfolio`; both Bankr keys reached the Agent
API's job endpoint; and every authorized call resolved to the same wallet
(`research/findings.md` F0.2.2–F0.2.3). Scoping on this account separates
*reading from transacting* via the Read Only toggle, not one surface from
another, so §6's scope column now states the toggles rather than a surface. This
does not breach invariant 1 — read access to a portfolio is not spend authority,
and the analyst role could already read holdings via `BANKR_KEY_READ` — but it
does retire planning/PLAN-technical-review.md finding 2 as a risk, since with one
account there is no second portfolio to mistake for the execution wallet.
**Affects:** planning/PLAN.md §6, `src/fund/credentials.py`, 4.12.

## 2026-09-17 — Probe 0.2 contradicts the openclaude gateway-header finding
`research/openclaude.md`'s headline correction was that the LLM gateway "does
**not** take `Authorization: Bearer`. It takes `X-API-Key`," documented as a
named protocol exception alongside Azure's. Measured: `Authorization: Bearer`
reaches the gateway and returns a byte-identical response to `X-API-Key`, and the
same holds on the wallet and agent surfaces, with a never-issued key refused 401
on all three to prove the header is read at all. The report's evidence was
`openclaude`'s own client code — honest evidence about what that client *sends*,
over-read into a claim about what the gateway *accepts*; we keep sending
`X-API-Key` because it is what both discovery reports observed in production, but
it is a preference now, not a constraint.
**Affects:** planning/PLAN.md §6; the reliability weighting we give a scoped
negative in any discovery report.

## 2026-09-17 — Probe 0.2: Agent API toggle is unresolved, and the check changed
Unit 0.2's done-condition required confirming the Agent API is **off** for both
Bankr keys, but `GET /agent/job/{unissued}` returns 404 "Job not found or you
don't have permission to access it" — a body that conflates the two outcomes the
check exists to separate, where the gateway by contrast names the missing toggle
in an explicit 403. Settling it would need `POST /agent/prompt`, a write that
consumes the daily quota, for a surface nothing in the system calls. The
done-condition now asserts the property we actually care about — no call to
`/agent/prompt` exists in the codebase — rather than a toggle we cannot observe.
**Affects:** 0.2 done-condition in planning/PHASE-0-1.md.

## 2026-09-17 — Probe 0.2: the fund wallet and the LLM balance are both empty
The portfolio reports zero on every chain (`base`, `robinhood`, `mainnet`,
`polygon`), and every gateway call returns `402 insufficient_credits`
(`research/findings.md` F0.2.6–F0.2.7). Nothing is wrong with the code or the
keys; the account simply has no funds and no inference credits, so §11's "~$200
capital" is aspirational until it is funded. Blocks probe 0.3's realistic $25
quote, probe 0.5, unit 1.7's cost measurement, and all of Phase 2.
**Affects:** 0.3, 0.5, 0.6, 1.7, Phase 2, Phase 5; planning/PLAN.md §11.

## 2026-09-17 — Probe 0.3: USDG is 6 decimals, and two documented sources said 18
`research/agent-os.md` (citing `poolsfun/chains.py:70`) and planning/PLAN-v1.md §4
both state USDG is 18 decimals; the chain says **6**, and so do the CoinGecko
discovery list and the `/wallet/swap-quote` response (`research/findings.md`
F0.3.1). Robinhood stock tokens really are 18, so a single "tokens on 4663 are 18
decimals" model produces exactly this error — off by 10^12 in whichever direction
the sizing code multiplied. Nothing in planning/PLAN.md stated the number, so
there was nothing to correct there; it is pinned in `probes/assets.py` with its
on-chain provenance and belongs in `config/universe.json` at 1.2. The general
lesson is that a value copied from a research report into a plan is not evidence,
and every address-scoped number now gets an on-chain read before first use.
**Affects:** 1.2, 1.5, 3.3; `config/universe.json`.

## 2026-09-17 — Probe 0.3: a successful quote proves nothing about executability
A $25 quote priced fine against a wallet holding no USDG at all, confirming that
quotes are ungated *and* unchecked against balances (`research/findings.md`
F0.3.3). A quote returning 200 is therefore evidence about a price and about
nothing else, which is the concrete instance of
planning/PLAN-technical-review.md finding 3 — a small quote supporting a stock
that the eventual position cannot actually fill. Unit 1.5 must size against
reconciled holdings rather than against the fact that a quote came back, and the
risk gate must treat quote success as an input to sizing, never as a
tradeability verdict on its own.
**Affects:** 1.5, 3.3, 3.4.

## 2026-09-17 — Probe 0.3: price impact is signed, and a magnitude gate is wrong
`priceImpactBps` came back **negative** on four of six quotes — AAPL 0, NVDA −2,
TSLA −12 and −15 — because negative impact is price improvement, not a problem
(`research/findings.md` F0.3.4). A gate written `abs(impact) > limit` would
therefore refuse the best fills the fund gets; it must compare the signed value,
`impact > limit`. The two impact fields were identical in all six responses, so
planning/PLAN-v1.md §4's claim that execution gates on `swapImpactBps` while
`priceImpactBps` is display-only remains **unresolved** until a size large enough
to separate them is quotable, which needs a funded wallet.
**Affects:** `core/gates.py` (3.4), 1.5.

## 2026-09-17 — Probe 0.3: three discovery sources need a User-Agent
`tokens.coingecko.com`, `reference-data-directory.vercel.app` and
`RPC_4663_MAINNET` each returned 403 to a bare `urllib` request and answered
normally once a `User-Agent` was set. A 403 from any of them is not an auth
failure, and unit 1.3's HTTP client must send one by default or it will fail at
first contact in a way that looks like a credential problem.
**Affects:** 1.3, 1.4.

## 2026-09-17 — Probe 0.3: three tokens answer to GME on 4663
The discovery list carries `GameStop • Robinhood Token` (`0x1b0e…`), `GameStop`
(`0x7e86…`) and `Greatest Meme Ever` (`0xef67…`), all on 4663, all 18 decimals,
and all answering `decimals()` on chain indistinguishably (`research/findings.md`
F0.3.6). The only thing separating the issuer's token from the other two is the
`• Robinhood Token` name marker — and `research/agent-os.md` records that the
same list truncates `name` at 60 characters, chopping that marker off longer
entries, so the one distinguishing feature is not reliably present. Probe 0.8
cannot lean on the discovery list, the name, or a decimals read; it needs the
issuer's own deployment list plus the beacon check, and 1.2's loader must refuse
any address not on the resulting versioned allowlist.
**Affects:** 0.8, 1.2; `config/universe.json`.

## 2026-09-18 — Chainlink equity feeds do exist; the 0.3 observation was a sampling artifact
The 0.3 session fetched the Robinhood mainnet reference directory, saw 57 feeds,
sampled BTC, ETH, LINK and USDG, found no equity feed, and recorded that as an
*observation, not a finding* because the other 53 were never enumerated — the
caution was right, and the observation was wrong. Enumerated in full: **35 of the
57 are equity feeds**, named `Robinhood <TICKER> / USD` with
`docs.assetClass: "Equity"`, a naming a crypto-ticker sample cannot hit
(`research/findings.md` F0.4.1). planning/PLAN.md §11's "Chainlink marks the
book" survives, §2's invariants keep a mark independent of the execution venue,
and 1.4's design is unchanged in shape. The general lesson is that a negative
from a sample is not a negative about the population, and the repo's habit of
labelling it as such is what made this recoverable in one step.
**Affects:** 0.4, 1.4, planning/PLAN.md §11. No plan change; a blocker cleared.

## 2026-09-18 — Tokenized stocks do have AMM pools, and GeckoTerminal covers all of them
planning/PLAN.md §13 states as fact that "tokenized stocks have no AMM pool of
their own", sourced to `bankr/references/tokenized-stocks.md:42` via
`research/bankr-skills.md`; on chain, SPY has a `SPY / USDG 0.3%` pool holding
$9.16M and AAPL twenty pools, and GeckoTerminal prices **32 of 32** addressable
stock tokens off them (`research/findings.md` F0.4.2–F0.4.3). The contingency in
the 2026-09-17 coverage entry therefore does not fire: the corroborator stays
GeckoTerminal, it *is* independent of the execution venue, and the divergence
veto stays cross-source instead of degrading to quote-versus-feed. The false
clause is corrected in §13, but the consequence is left open — the 2026-09-17
entry deleted "depth" because the plan said there was nothing to measure, and
whether depth returns is a decision for the 0.4 checkpoint, not a repair to make
inside the probe that found this.
**Affects:** planning/PLAN.md §13, 1.4, 3.4, 3.8; `config/thresholds.json`
(unchanged pending the checkpoint).

## 2026-09-18 — Probe 0.4 cannot settle the multiplier; 1.4 proceeds on documentation
0.4's done-condition required a **measured** answer to whether the Chainlink
answer already incorporates `uiMultiplier()`, and it is not met: nine of 33
tokens carry a multiplier other than 1.0, the largest is ORCL at 22.1 bps, and
the noise floor between feed and corroborator — measured on the 23 tokens whose
multiplier is exactly 1.0, where both hypotheses coincide — averages 141.9 bps
(`research/findings.md` F0.4.4). The effect is an order of magnitude below the
measurement error, so the question is recorded **unresolved** rather than
resolved in favour of the two documented sources that agree it is already
applied; the Bankr quote cannot break the tie because
`tokenized-stocks.md:67` has the venue applying the multiplier itself, which
makes that comparison circular as well as venue-dependent. 1.4 must follow the
documented rule — do not apply it twice — and `core/valuation.py`'s comment must
point at F0.4.4 and say the basis is documented and corroborated but not
measured, rather than implying a probe settled it.
**Affects:** 0.4 done-condition, 1.4; `core/valuation.py`.

## 2026-09-18 — A flat divergence threshold cannot work; it tracks the corroborator's liquidity
`config/thresholds.json` carries `divergence_max_bps: null` for probe 0.4 to
resolve, on the assumption that one number would do. Measured at one block,
divergence between feed and pool is 19.5 bps median for the 19 assets with over
$1M of 24h volume and 164.7 bps for the 13 below it, worst cases EWY 610 bps on
$3.5k of volume and CLSK 507 bps on $0.01 — the *pool* is wrong, not the feed
(`research/findings.md` F0.4.5). A threshold at 50 bps vetoes eleven of 32 assets
on a quiet day; one above 610 bps to accommodate EWY will not catch a genuinely
broken mark, and AMZN diverging 499 bps on $2.19M of volume shows liquidity alone
does not separate them. The threshold must be conditioned on corroborator
liquidity, or illiquid names excluded at 1.2 so the veto only runs where the
corroborator is worth comparing against — recommended, **not decided**, because
it changes 3.4's gate shape.
**Affects:** 3.4, 1.2; `config/thresholds.json` (still null pending the
checkpoint).

## 2026-09-18 — `uiMultiplier()` answering is the impersonator test 0.8 was missing
The 2026-09-17 GME entry concluded that probe 0.8 "cannot lean on the discovery
list, the name, or a decimals read", leaving it with only the issuer's deployment
list and the beacon check. A fourth test works: the ERC-8056 `uiMultiplier()`
selector `0xa60bf13d` answered on all 32 addressable RH stock tokens and
**reverted** on both GME impersonators and on USDG (`research/findings.md`
F0.4.6), which is the check `research/agent-os.md:374` predicted and the first
one that is positive evidence rather than an absence. It is necessary and not
sufficient — nothing stops a counterfeit implementing a function that returns a
number — so it joins the beacon check as a second consistency flag a forgery must
also defeat, and the issuer's deployment list stays the authority.
**Affects:** 0.8, 1.2; `config/universe.json`.

## 2026-09-18 — Chainlink covers 19% of the tokens, which caps the universe at ~35
The discovery list carries 187 tokens bearing the `• Robinhood Token` marker and
Chainlink publishes 35 equity feeds, so 81% of the apparent universe has no feed
(`research/findings.md` F0.4.8). Under planning/PLAN.md §11 an asset with no feed
cannot be marked and therefore cannot be held, which makes feed presence a
membership condition at 1.2 rather than a property discovered later, and shrinks
the investable set from ~190 names to ~35 before tradeability is asked at all.
This partly answers planning/PLAN.md §12's "how many of the ~190 tickers are
actually tradeable at our $25 size" — markability removes most of them first, and
a four-analyst roster now divides 35 assets rather than 190.
**Affects:** 1.2, 2.1, 3.1; planning/PLAN.md §12; `config/universe.json`.

## 2026-09-18 — The "seven causes" were carried in the plan without the list
planning/PLAN-v1.md §4 and planning/PHASE-0-1.md 0.5 both instruct probe 0.5 to
map a refusal "against the seven documented causes", and no file in this
repository enumerates them — the count survived three plan revisions while its
content did not, so the probe was told to check against a list that had to be
re-fetched from the vendor before it could run. Recovered from
`https://docs.bankr.bot/wallet-api/swap/`: six are quoted from the Errors table,
and the seventh is **reconstructed** from the Access Control section, which
extends token-security refusals to execution although the table omits them
(`research/findings.md` F0.5.4). The list is now pinned in `probes/execute.py`
with the quoted/reconstructed split preserved, and the general lesson is that a
count is not a citation: a number in a plan that no file can expand is a
dependency we have not actually recorded.
**Affects:** 0.5, 5.6; `probes/execute.py`.

## 2026-09-18 — The swap 403 carries no machine-readable cause, so the decoder fails closed
The refusal body is `{"message":"Tokenized stocks (AAPL) are not available in
your region."}` — clear to a human, and clearer than expected, but a single prose
field with no code, no type, and not even the flat `error` key the same Wallet
API returns on a 401, while the LLM gateway on the same platform returns a typed
`auth_error` (`research/findings.md` F0.5.3). Unit 5.6's decoder can therefore
only match English, and a reworded message breaks the match silently, so it must
**fail closed on any unrecognised 403** and surface the raw body rather than
assume the one cause it can parse. Six of the seven causes were never triggered,
so nothing measured says whether they are distinguishable from each other, and
the decoder must not be written as though they are.
**Affects:** 5.6, 4.x treasurer error surfacing; `core/errors.py`.

## 2026-09-18 — 0.5 confirms the stock gate but leaves Phase 5's live leg unproven
The location refusal fired, which means the read-only-key cause was never
reached: Bankr's check ordering is not observable from one response, so
`BANKR_KEY_EXEC`'s ability to **transact** is exactly as unresolved as probe 0.2
left it (`research/findings.md` F0.5.5, F0.2.2). Phase 5 was rescoped on
2026-09-17 around an ungated 4663 swap through the treasurer, so that receipts,
reconciliation and the order state machine run against a real chain — and that
path rests on a capability no probe has yet demonstrated. Settling it needs one
ungated swap with the same key, ETH into USDG at the same size, which is a
second spend that unit 0.5 does not authorise; it belongs at the head of Phase 5
rather than bolted onto 0.5, and Phase 5 should not be treated as de-risked
until it passes.
**Affects:** Phase 5 entry, 4.12; planning/PLAN.md §13.

## 2026-09-18 — DECISION: a Chainlink feed is a membership condition, capping the universe at 35
*Operator decision at the 0.4 checkpoint, not a probe result.* An asset with no
Chainlink feed cannot be marked independently of the venue we trade on, and
without an independent mark the books are not honest — which is the project's
differentiator, so the mark is not a detail to compromise on. Feed presence
therefore becomes a **membership condition** enforced at 1.2 rather than a
property discovered later: the investable universe is the **35 equity feeds**
`research/findings.md` F0.4.1 enumerated, out of the issuer's **194** assets
(F0.T.2), so 82% of the apparent universe is excluded before tradeability is
asked at all.

**This changes what carries identity, and it contradicts F0.3.6.** That finding
made the `• Robinhood Token` name marker the load-bearing discriminator, because
it was the only thing separating the real GME from two impersonators. The testnet
probe then measured the marker as an *anti-signal* — 140 Robinhood-named tokens
on 46630 and not one of them genuine (F0.T.4). The marker is not retired because
it was wrong on mainnet; it is retired because it is forgeable and we now have
three better anchors: the issuer's own registry (F0.T.2), the EIP-1967 beacon,
and feed presence. F0.3.6 stands as the record of why we ever leaned on a name.
**Affects:** 1.2, 2.1, 3.1, 0.8; `config/universe.json`.

## 2026-09-18 — DECISION: divergence is tiered by corroborator liquidity, not one flat number
*Operator decision at the 0.4 checkpoint.* `config/thresholds.json` carried
`divergence_max_bps: null` on the assumption that one number would serve, and
F0.4.5 measured why it cannot: agreement runs ~20 bps median on assets whose
GeckoTerminal pool does over $1M of daily volume and up to 610 bps on thin ones,
with the divergence tracking **the corroborator's liquidity rather than the feed
being wrong**. A flat threshold either vetoes a third of the universe every cycle
or never fires at all.

The rule is two-tier: roughly **100 bps** for assets above the **$1M daily pool
volume** line, and below that line the asset is **not held at all** rather than
vetoed per cycle — a thin corroborator is a reason to exclude an asset from the
universe, not a reason to re-litigate it every day. Both numbers are
**provisional** and live in `config/thresholds.json`, never in code, so tightening
them is a config change and not a release. Note this does not make every liquid
name safe: AMZN diverged 499 bps on $2.19M of volume while feed and quote agreed
to 20 bps, so the tier bounds the common case and the veto still has to fire.
**Affects:** 3.4, 1.2, 1.4; `config/thresholds.json`.

## 2026-09-18 — DECISION: depth returns, as corroborator quality only — reversing the 2026-09-17 deletion
*Operator decision at the 0.4 checkpoint, and it reverses an earlier entry in
this file.* The 2026-09-17 entry *"'Depth' removed as a concept"* deleted depth
from the vocabulary because the plan asserted tokenized stocks have no AMM pool
of their own, so the filter was gating on a number that could not exist. **The
premise was false.** F0.4.3 measured SPY holding $9.16M in one USDG pool and AAPL
twenty pools — the assertion came from `tokenized-stocks.md:42` via
`research/bankr-skills.md` and was taken as fact without being checked on chain.

Depth returns in a **strictly narrower role than it had before**: a
corroborator-quality signal that tiers the divergence rule above, and nothing
more. It is **not** a tradeability gate, because execution is RFQ against USDG
rather than against these pools, so pool size describes how much to trust
GeckoTerminal's price and says nothing about our fill. **Tradeability is
unchanged**: a quote at intended size succeeded, quote age within bound, and
impact known-and-within-limit or null — and null blocks. The 2026-09-17 entry
keeps its place as the record of a correct decision taken on a false premise,
which is the failure mode worth remembering: it was good reasoning about a fact
nobody had measured.
**Affects:** 1.4, 3.4, 3.8, 1.2; planning/PLAN.md §13; `config/thresholds.json`.

## 2026-09-18 — Probe 0.6: credits and usage are different accounting boundaries
planning/REVIEW-RESPONSE.md finding 13's correction of planning/PLAN-v1.md §4 is
now **measured** rather than documented — `GET /v1/credits` returns a balance in
132 ms, so cost can be reconciled against provider totals (`research/findings.md`
F0.6.1). What finding 13 does not promise, and what 0.6 measured, is that the
attribution stops at an **(API key × model × day-window) aggregate**: no
per-request rows, no request id, so a per-analyst cost line can only ever be our
own token count allocated across a measured total, and must carry
`is_estimate: true` (F0.6.4). PHASE-0-1 0.6 anticipated that branch; what it did
not anticipate is that `/v1/credits` is scoped to the **wallet** while
`/v1/usage` is scoped to the **key**, and the wallet's spend includes every other
key it owns plus Max Mode and agent runs — so the two endpoints cannot be
reconciled against each other, and the balance today is already $0.17 below what
this key's usage explains (F0.6.6, recorded unresolved). 6.3 must reconcile
aggregate-to-aggregate within one key and treat the wallet balance as a separate
account, not as a check on our own arithmetic.
**Affects:** 6.3, 2.5, 1.7; planning/PLAN.md §2.5.

## 2026-09-18 — DECISION: registry membership is the identity test, pinned and hash-versioned
*Operator decision at the close of 0.8, on measured evidence.* An asset is
admissible only if it appears in the issuer registry
(`api.robinhood.com/rhj/assets`) keyed by **`(chain_id, address)`**. It is
necessary and sufficient: it admitted every genuine asset and rejected every
counterfeit tested, and it is the only source that supplies the address-to-asset
mapping itself along with ISIN, status, decimals and multiplier
(`research/findings.md` F0.8.1, F0.8.5) — the other checks can opine on an asset
but cannot name one.

The registry carries **no version, no `ETag` and no `Last-Modified`**, so the
**sha256 of the snapshot is its version**: 1.2 pins a snapshot and diffs on
refresh, and a live lookup at cycle time is **forbidden**, because it would put
the universe on an unversioned third-party endpoint with no integrity signal and
fail planning/PLAN.md §2 invariant 8.

**The limit, recorded with the decision rather than under it.** Both counterfeits
tested were crude ERC-20s with no beacon slot; nothing tested a forgery that
clones the proxy and points at its own beacon, which is what a serious attacker
would deploy and which **only the registry would catch**. And a counterfeit that
reached the registry would defeat every check we have. That is the issuer's
control, not ours, and it is the ceiling on this decision's strength.
**Affects:** 1.2, 3.4, 6.x; `config/universe.json`; planning/PLAN.md §2 invariant 8.

## 2026-09-18 — DECISION: `uiMultiplier()` and the name marker are retired as identity signals
*Operator decision at the close of 0.8.* Both are trivially forgeable and neither
caught anything the registry did not: the testnet probe measured **140 tokens
carrying the `• Robinhood Token` marker with none genuine** (F0.T.4), and five
tokens answering `uiMultiplier()` because they run the issuer's own contract
(F0.T.3). They are deleted from the identity vocabulary rather than kept for
reassurance, which would cost code and hide which check is load-bearing.

**This supersedes F0.3.6 and F0.4.6, and the way it does matters.** F0.3.6 made
the name marker the discriminator for the three GME tokens; F0.4.6 offered
`uiMultiplier()` as the check 0.8 needed. Neither was wrong about mainnet — the
marker is accurate today across **all 187** marked tokens (F0.8.4), and
`uiMultiplier()` still separates the genuine GME from both fakes. They are
retired because *being right today on one chain is not the same as being hard to
forge*, which is precisely the comfortable position that made F0.3.6 trust a
string in the first place. The findings stand as the record of what we believed
and why.
**Affects:** 1.2, 0.8; supersedes part of F0.3.6 and F0.4.6.

## 2026-09-18 — DECISION: the beacon is a cross-check that fails loudly, not a filter
*Operator decision at the close of 0.8.* Registry and beacon agreed on **all 381
addresses swept** — 194 of 194 registry assets and 187 of 187 marked
discovery-list addresses — so no evidence separates them and the beacon is not
doing discrimination work (F0.8.4). It is kept for one reason only: its **trust
root is independent**. The registry rests on TLS to `api.robinhood.com`; the
beacon rests on the chain and the beacon contract's owner. They fail differently,
and the beacon is also the only check that speaks to the contract's state *now*,
where a pinned snapshot is by construction historical.

Because it is insurance and not detection, its failure mode is the whole point: a
disagreement means **one of the two is compromised**, so it must **fail the cycle
loudly** rather than log a warning and continue. A cross-check that degrades to a
warning is not a cross-check.
**Affects:** 1.2, 3.4; `config/universe.json`.

## 2026-09-18 — DECISION: feed presence is markability, not identity
*Operator decision at the close of 0.8.* Feed presence **admitted both GME
counterfeits** (F0.8.3), because a Chainlink feed exists for the *ticker* and a
forger picks its own ticker — so the check asks whether a feed exists for the
symbol a contract merely claims, which is satisfied by typing three characters.
It carries **zero identity weight** and must never appear in an admissibility
rule.

It remains a membership condition for *holding* an asset, per the 0.4 checkpoint
decision: no feed, no independent mark, so the asset is not held. **1.2 therefore
needs two independent rules — registry for identity, feed for markability —
evaluated separately and never collapsed.** CRM is the case that proves they are
distinct: genuine, registry-listed, behind the issuer's beacon, and correctly
**unmarkable**. The general lesson is that a check can look decisive purely
because it was only ever pointed at things it obviously catches.
**Affects:** 1.2, 1.4, 3.4; `config/universe.json`, `config/thresholds.json`.

## 2026-09-18 — F0.7.3 corrected: the v1 client rejects one field, and the Bankr CLI is not an x402 client
F0.7.3 recorded that no standard published x402 client can pay our endpoint,
and that the client throws for two reasons: the protocol version and the network
identifier. Probe 0.7e measured both claims as too broad. `x402-fetch@1.2.0`
rejects on the network enum alone and passes `x402Version: 2` straight into its
own header. The v2 client line F0.7.3 never looked at — `@x402/fetch` 2.26.0,
published by the same maintainers since 2025-12-11 — paid us unmodified
(`research/findings.md` F0.7e.1, F0.7e.5). The Bankr CLI, whose payments were the
only ones that had worked, contains no x402 client at all: it sends the URL to
Bankr's undocumented `/wallet/x402-pay`, and Bankr's server pays from the
custodial wallet (F0.7e.4). So "the CLI works" was only ever evidence about
Bankr users. This is the lesson F0.2.1 and F0.6.1 already taught: a negative
about the packages examined was recorded as a negative about the ecosystem.
**Affects:** 0.7 checkpoint, 7.2, 7.3, the pitch; supersedes F0.7.3's headline.

## 2026-09-18 — 0.9 was run in Phase 0 after all, as a floor; 1.7 still owns the number
The 2026-09-17 entry relocated the analyst-cost probe to unit 1.7, because
snapshot bytes dominate the token count and no snapshot exists before 1.6, and
`planning/PHASE-0-1.md` added that "the 0.9 number is not reused". 0.9 was run
on 2026-09-18 regardless, on six hand-assembled assets with every figure labelled
a floor (`research/findings.md` §0.9), and nothing recorded the change of plan at
the time. It found three things 1.7 would otherwise have met late:
- 58 s per call, against deadlines that are still null in config (F0.9.1);
- a client-side timeout is still billed (F0.9.3);
- `/v1/usage` can go backwards (F0.9.2).

It also found one thing 1.7 could not have found in time: a single-block
snapshot gives a trend analyst nothing to answer (F0.9.6). The relocation itself
is unchanged. 1.7 still measures against the real snapshot, and 0.9's numbers
are quoted only as floors.
**Affects:** 0.9, 1.7, 2.4, 6.3; `planning/PHASE-0-1.md` 0.9, `planning/ROADMAP.md`.

## 2026-09-18 — DECISION: the snapshot carries price history up to its pinned block
*Operator decision on F0.9.6.* Invariant 2 specified one frozen snapshot per
cycle, pinned to a single block, and 0.9 measured what that gives an analyst.
Asked for a price-trend brief over six assets, it returned `NO_CALL` on all six,
and it was right to: a single block-pinned reading carries no price history
(`research/findings.md` F0.9.6). A price-trend analyst has nothing to answer
from one block, and the roster in `config/analysts.json` has one.

Invariant 2 therefore rewords to **one frozen snapshot per cycle, containing
history up to a pinned block**, and the adapter reads a series. Which series and
what window are unit 1.3's work, not this decision's. What does not change: the
snapshot is still frozen, content-hashed and loaded into every analyst's prompt
as bytes, and nothing after the pinned block may enter it.
**Affects:** `planning/PLAN.md` §2 invariant 2, 1.3, 1.6, 1.7 (the token count
grows), 1.11, §9; `config/analysts.json` (`price-trend`).

## 2026-09-18 — DECISION: the x402 buyer client is @x402/fetch 2.26.0, and the claim narrows to match
*Operator decision on 0.7e.* Probe 0.7e found:
- `@x402/fetch` 2.26.0 with `@x402/evm`, unmodified, paid our endpoint, and the
  payment settled on chain (`research/findings.md` F0.7e.5).
- `x402-fetch` / `x402` 1.2.0 cannot pay it; they throw before signing (F0.7e.1).
- Bankr's own documentation points buyers at `x402-fetch` 1.2.0 (F0.7e.4).

So the buyer instructions name `@x402/fetch` 2.26.0 explicitly rather than
leaving buyers to follow Bankr's docs into a client that fails. The claim is
**"payable by any x402 v2 client, and by Bankr users"** — not "payable by any
x402 client".

**The open inference, recorded with the decision rather than under it.** The
test payment was signed by Bankr's signing service (`/wallet/sign`) for the
fund's own custodial wallet, not by a locally held key, and it was self-paid
(F0.7e.6). The server saw only the library's payload and an EOA signature, so a
buyer holding their own key should look identical to it. That remains an
inference until a fresh key pays us, which is planned for Phase 7 (7.5).
**Affects:** 7.2, 7.5, 7.8, 8.6, the pitch; `planning/PLAN.md` §11, §13.

## 2026-09-18 — Probe 0.10: the execution key can transact, but not as a transaction from our wallet
0.10's one ungated swap settles F0.5.5: `BANKR_KEY_EXEC` can transact, and a
repeat with the same `idempotencyKey` returned the original result without
broadcasting again (`research/findings.md` F0.10.1–F0.10.2). It also broke an
assumption the plan never wrote down. We expected an ordinary transaction from
the fund's wallet. What went on chain was an EIP-7702 transaction from a
bundler, carrying an authorization our wallet signed, running the swap as a
gas-sponsored ERC-4337 UserOperation. The wallet is now delegated to a Bankr
contract on 4663 (F0.10.3). So `tx.from`, the outer receipt's status and the
wallet's nonce describe the bundle, not our swap, and the probe's own first
verdict ("transacted: False") came from exactly that. Reconciliation (5.3) has
to key on `UserOperationEvent` and `Transfer` logs. A quote's `feeBps: 0` did
not mean the fill was fee-free: 6 bps went unaccounted for (F0.10.4).
**Affects:** Phase 5 entry, 5.2, 5.3, 4.6, 6.2; `planning/PLAN.md` §6, §13.

## 2026-09-18 — DECISION: freshness applies to a series' newest point only
*Operator decision at the 0.11 checkpoint*, resolving the gap left open when
invariant 2 gained history. A price series is mostly old data by definition. The
freshness rule governs its **most recent observation**; historical points carry
their own timestamps, and being old is what makes them history. The staleness
and replay rules in `planning/PHASE-0-1.md` 1.11 and `planning/PLAN.md` §9 were
written for single readings and, applied point by point, would have rejected
every series. They now bind the newest point.
**Affects:** 1.3, 1.6, 1.11; `planning/PLAN.md` §9 (*fold pending*: PLAN.md was
outside the 0.11 follow-up's paths); `config/thresholds.json`.

## 2026-09-18 — DECISION: five config values set, all provisional
*Operator decision at the 0.11 checkpoint*, on the five values a probe had been
named to resolve and had not (`research/findings.md`, Phase 0 exit summary):

- **Feed staleness is not a constant.** Each feed's own documented heartbeat
  (86,400 s for the equity feeds, F0.4.1), plus a margin. This is what F0.4.7
  recommended over one global number, since an `updatedAt` 3.6 hours old is
  normal in market hours. The decision did not give the margin. It stays
  `null`, and the check blocks until it is set.
- **`quote_max_age_seconds`: 60.**
- **`impact_max_bps`: 50**, compared signed. It is loose on purpose: measured
  impact ran −15 to +2 bps on stock quotes (F0.3.4) and 13 bps at most (F0.5.1).
- **`worker_deadline_seconds`: 120**, against 58 s measured for one analyst call
  (F0.9.1).
- **`analyst_model`: `claude-sonnet-5`, provisionally**, because that is what 0.9
  measured. The final choice stays at 2.4, where the 139× cost spread across
  models (F0.9.5) gets tested against output quality.
**Affects:** 1.3, 1.5, 1.6, 1.7, 1.11, 2.4; `config/thresholds.json`,
`config/models.json`.

## 2026-09-18 — DECISION: Phase 5's live leg is ETH→USDG on 4663
*Operator decision at the 0.11 checkpoint*, answering the question
`planning/PHASE-0-1.md` 0.11 and `planning/PLAN.md` §12 left open. The live leg
is **ETH→USDG on 4663**. It is proven ungated and working: 0.10's one sell
executed through `BANKR_KEY_EXEC`, deduplicated on its `idempotencyKey`, and
cost the wallet no gas (`research/findings.md` F0.10.1–F0.10.3).

**The record's caveat, stated with the decision.** What 0.10 proved is one
direction at $0.08. The return leg, USDG→ETH, has not been exercised, and 5.2's
round trip needs it. Its sponsorship, its 7702 path and its fee (F0.10.4 found
6 bps unaccounted for on the sell) are therefore inferred from the sell and not
measured. This replaces the plan's earlier "memecoin/USDG" wording for the
ungated leg.
**Affects:** Phase 5, 5.2, 5.4, 5.7; `planning/PHASE-0-1.md` 0.11 and the
re-evaluation gate; `planning/PLAN.md` §12 and Phase 5 text, `planning/ROADMAP.md`
Phase 5 (*fold pending*: outside this pass's paths).

## 2026-09-18 — DECISION: §11's x402 rationale stays marked contradicted, and $0.05 stays provisional
*Operator decision at the 0.11 checkpoint.* `planning/PLAN.md` §11 justifies
selling on Base with a property of the v1 x402 client, while the decided buyer
client is v2 (F0.7e.2, F0.7e.5). That stays marked *contradicted, not
reconciled*. The Base decision is not revisited. The $0.05 price stays
provisional: F0.9.4 shows it needs 1.3–2.3 sales a day to cover inference at the
floor, and 1.7 is where it is next confirmed or revised. Neither blocks Phase 1.
**Affects:** 1.7, 7.2; `planning/PLAN.md` §11 (already marked; no change).

## 2026-09-18 — Phase 1 replanned against the Phase 0 record
Every Phase 1 unit in `planning/PHASE-0-1.md` was drafted before any probe ran.
Each has been rewritten against `research/findings.md` and this file, and each
now names what changed it. No unit is added or removed. Four are bigger than
drafted:
- **1.2:** two rules, and pinned raw snapshots of the registry and of
  Chainlink's directory.
- **1.3:** reads a price series.
- **1.8:** four ways out of the universe, plus USDG and ETH as holdings.
- **1.11:** seven cases, not four.

Three places where the record overruled the draft, or the brief:
- **1.5 no longer waits on a funded wallet.** Quotes are not balance-checked
  (F0.3.3), and stock fills are gated (F0.5.1). So funding cannot make a stock
  quote evidence about liquidity. The unfunded wallet blocks 3.3's sizing and
  Phase 5's volume, not 1.5.
- **Probe 0.8 kept parsed JSON, not the bytes it hashed.** The registry version
  F0.8.1 recorded (`442718b5…`) cannot be re-verified from anything kept, since
  re-serialising gives the same length and a different hash. 1.2 therefore
  re-fetches and stores raw bytes in `config/registry/`.
- **A failover RPC with archive access** was put forward for 1.3. It is neither
  on the record nor in the environment: `RPC_4663_MAINNET` is the public
  endpoint, which is documented as having no archive. It is recorded as
  unverified, not built on.

Two smaller catches: the $1M tier was set on GeckoTerminal's token-level
volume, so 1.4 must use that measure; and three findings tables cite "1.4" for
the x402 cached-record design, which is a 7.x concern.
**Affects:** 1.1–1.11, Phase 1 exit, the re-evaluation gate; `config/README.md`;
`planning/PLAN.md` §8's Phase 1 summaries and `planning/ROADMAP.md`'s Phase 1
table (*fold pending*: outside this pass's paths).

## 2026-09-18 — DECISION: the three remaining config values
*Operator decision before unit 1.1.* These are the three values the Phase 1
replan left null:
- **`feed_staleness_margin_seconds`: 3600.** One hour on top of each feed's own
  heartbeat, which is 86,400 s for the equity feeds (F0.4.1). Provisional.
- **`transport_timeout_seconds`: 180.** It must exceed the 58 s a single analyst
  call took (F0.9.1), because a client-side timeout is still billed and so is a
  cost with no report (F0.9.3).
- **`execution_wallet`: `0x93faecde3c88a713e1edddf417c02c326889a3da`.** It is the
  one wallet all three Bankr keys resolve to (F0.2.3), and since 0.10 it is
  EIP-7702-delegated on 4663 (F0.10.3).

**An interaction, recorded and not resolved.** The 180 s transport timeout is
longer than the 120 s `worker_deadline_seconds` decided at 0.11. Inside the 2.4
runner, the deadline would therefore always fire first, and the transport
timeout never would. Either one moves, or the two are defined to mean different
things. That is 2.4's decision, and it does not affect 1.7, which makes single
calls with no runner.
**Affects:** 1.3, 1.7, 1.10, 1.11, 2.4; `config/thresholds.json`,
`config/models.json`, `config/mandate.json`.

## 2026-09-18 — Unit 1.1 narrowed: six types wait for the units that design them
`planning/PHASE-0-1.md` 1.1 listed ten types, including `AnalystReport`,
`Proposal`, `Plan`, `Decision`, `JournalEvent` and `Statement`. Building 1.1
found that nothing in the record fixes those six shapes. Worse, PLAN 2.1
requires the report format to be designed by hand "before any code", so an
`AnalystReport` defined in Phase 1 would pre-empt that checkpoint, and the other
five would be guesses. A type that reads well but cannot express the case it
later meets is the failure 1.1 exists to avoid.

1.1 therefore defines what the record *has* fixed:
- the snapshot side — observations, series, assets, quotes, holdings, the
  snapshot;
- `Order`, with its execution evidence shaped by F0.10.3.

The six wait for their units: `AnalystReport` for 2.1–2.2, `Proposal` for 3.1,
`Plan` for 3.3, `Decision` for 3.7, `JournalEvent` for 4.6, and `Statement` for
6.1. The facts already fixed for them stay where they are recorded. For
example, chain events carry a UserOperation hash (F0.10.3), and cost lines carry
`is_estimate` (F0.6.4); `core/types.py` supplies the leaf types those facts need.
**Affects:** 1.1, 2.1–2.2, 3.1, 3.3, 3.7, 4.6, 6.1; `planning/PHASE-0-1.md` 1.1,
`planning/PLAN.md` §8, `planning/CODEBASE.md` §2.

## 2026-09-18 — The quote response mixes raw and human amounts, and one of them is lossy
F0.3.2 recorded that the quote *response* carries a raw `amount` and a
`formattedAmount`. Building 1.1's `Quote` type from probe 0.3's six recorded
responses (`probes/out/quote.json`) showed that this is true of one side only.

The response's formats, field by field:

| Field | What it carries | Example (TSLA, $25) |
|---|---|---|
| `from.amount` | the human request echoed back | `"25"` |
| `to.amount` | raw units | `"67948238487403141"` |
| `to.formattedAmount` | a **lossy**, float-style rendering | `"0.06794823848740314"`, one digit short |
| `minBuyAmount` | human decimal text | — |
| `sellTokenPriceUsd`, `buyTokenPriceUsd` | JSON floats | — |

So 1.5 reads `to.amount` for the bought quantity and never `formattedAmount`. It
converts `from.amount` and `minBuyAmount` from decimal text at each asset's own
decimals, and turns the two prices into exact decimals from their shortest text.
The general lesson is the one F0.3.1 taught about decimals: a field's
*documented* shape is not its measured shape until someone reads the bytes.
**Affects:** 1.5; refines F0.3.2.

## 2026-09-18 — 0.8's registry version is verified: the registry was byte-identical five hours later
The Phase 1 replan recorded that 0.8's registry hash (`442718b5…`) could not be
re-verified, because 0.8 kept the parsed JSON and not the bytes it hashed.
Building 1.2, a fresh fetch at 23:13Z hashed to exactly that version. So the
version is now verified against real bytes, which sit in `config/registry/`
under that name, and the registry did not change between 18:24Z and 23:13Z. The
lesson stands anyway: a hash whose bytes were not kept could not be verified,
and was verified only because the source happened not to change.
**Affects:** 1.2; `config/registry/pins.json`.

## 2026-09-18 — Chainlink's directory carries no token address, so markability's link is a reviewed name match
0.8 recorded "never join the registry to the feed directory on ticker"
(F0.8.1). Building 1.2 found that nothing else *can* join them. The directory's
57 entries carry proxy, aggregator and secondary-proxy addresses, and nothing
that names a token contract; a feed names its asset only by `baseAsset`,
entity id and name. So the address-keyed `config/registry/feed_map.json` has to
start from a name match. It does, once, under review, never at cycle time. It
is safe from F0.8.3's failure because `propose_feed_map` iterates the
**registry's** records: the symbol it matches is the issuer's, for an address
the issuer lists, and a counterfeit can never be proposed a feed. 32 feeds
matched exactly, and 3 were reviewed by hand. The loader refuses any map entry
naming an unlisted asset.
**Affects:** 1.2, 1.4, 1.10; refines the F0.8.1 rule.

## 2026-09-18 — Unlike the registry, the feed directory sends ETag and Last-Modified
F0.8.1 measured the issuer registry sending no version, no `ETag` and no
`Last-Modified`. Chainlink's directory, fetched for 1.2, sends both — `ETag
"2a7c7d90…"`, `Last-Modified` 23:10:03Z on the day of the fetch — so it did
change that day. It is still pinned by the sha256 of its bytes, which is what
the loader verifies, but a refresh can ask whether it changed without
downloading it. 57 feeds and 35 equity feeds, the same counts F0.4.1 measured.
**Affects:** 1.2 refresh.

## 2026-09-18 — SGOV and USAR carry no assetClass; filtering on it dropped them silently
The first cut of `propose_feed_map` selected equity feeds by
`docs.assetClass == "Equity"` and found 33, not F0.4.1's 35. SGOV and USAR's
entries carry no `assetClass` at all, only `us_equities_24/5` market hours. So
they were not reported as unmatched; they vanished. It was caught only because
the count disagreed with a measured number. The filter now counts either
signal, giving 35: 32 exact matches and 3 for review. This is the silent
truncation the whole build guards against, surfacing in the code meant to
prevent it.
**Affects:** 1.2; `src/fund/core/universe.py`.

## 2026-09-18 — DECISION: listed but not ACTIVE is refused for buying, and never dropped as a holding
*Decided in 1.2, as delegated.* The registry carries a `status`, and only
`ASSET_STATUS_ACTIVE` has ever been observed (F0.8.1). An asset listed with any
other status keeps its identity, because identity is registry membership (0.8
decision). It is refused for buying at a separate **standing** rule, and it
books as `UniverseStatus.LISTED_NOT_ACTIVE`, which is not `IDENTITY_IN_DOUBT`.
As a holding it keeps its registry record and its mark. An asset dropped from
the registry entirely is also never dropped from the book:
- `held_asset()` never refuses;
- `accept()` refuses a refresh that removes a held asset unless acknowledged.
**Affects:** 1.2, 1.6, 1.8; `src/fund/core/types.py`, `src/fund/core/universe.py`.

## 2026-09-18 — The registry fetch and the beacon read are adapter work; core takes their results as arguments
`core/` makes no network calls (CODEBASE §1), and 1.2 needs two network reads.
The first is fetching the registry and directory for a refresh; the second is
reading each token's EIP-1967 beacon slot. So `core/universe.py` takes both as
arguments — fetched bytes into `plan_refresh`, and slot observations into
`cross_check_beacons` — and its only I/O is its own files under
`config/registry/`. The beacon read belongs to 1.3's chain adapter. The
registry and directory fetch has **no unit that owns it**; 1.2's initial pin
used a one-off fetch standing in for it. This is a finding about the layout,
not a workaround.
**Affects:** 1.2, 1.3; the refresh path; `planning/PHASE-0-1.md` 1.2.

## 2026-09-18 — Every equity feed goes quiet for about 52 hours each weekend, so the decided staleness rule marks them all stale for a day or more
1.3 read seven days of rounds for every mapped feed, up to block 66642089
(Sat 2026-09-19 00:08Z). All 35 `us_equities_24/5` feeds went quiet on Friday
2026-09-11: their last rounds fell between 12:49Z Friday and 00:01Z Saturday.
None published again until Monday 00:00Z, which is Sunday 20:00 ET. That is a
gap of **48.0–59.2 h**, against the decided limit of 25 h (heartbeat 86,400 s
+ margin 3,600 s). So from Saturday afternoon UTC until Monday 00:00Z, about
23–35 h each weekend, the rule as decided judges every equity feed's newest
point stale.
- **Weekdays stay inside the limit.** The largest weekday gap was 24.0 h (SPY,
  QQQ, SGOV), which update on the heartbeat alone, so the 1 h margin is what
  keeps them fresh.
- **The crypto feeds are different.** ETH/USD's largest gap was 12.9 h and
  USDG/USD's 24.0 h.

The rule is not changed. This is the measurement behind the question left for
1.11, not a contradiction of the decision, which recorded weekend behaviour as
unmeasured. Only one weekend was observed, and holidays are unmeasured. Whether
a feed that is stale over the weekend should block valuation, trading or
neither is the operator's call.
**Affects:** 1.8, 1.11; `config/thresholds.json`; the weekend cycle.

## 2026-09-18 — DECISION: the price series is Chainlink's own rounds, read at the pinned block over seven days
*Decided in 1.3, as delegated.* The candidates were a feed's stored rounds and
GeckoTerminal's OHLCV, and neither had been measured. Rounds won:
- they are read at the same pinned block as everything else, so the one-block
  rule holds for history too;
- they need no archive, because past rounds are current state: all 645 of
  AAPL's rounds were readable at a recent block;
- each carries its own `updatedAt`.

The window is 7 days, capped at 1,000 rounds. The walk keeps one anchor round
at or before the window start, and `Series.coverage` says whether the window
was reached. At block 66651154 all 37 feeds covered it, with 7 (SGOV) to 361
(CLSK) points. GeckoTerminal OHLCV was not measured and is not ruled out for
1.4. A feed publishes on a 0.5% deviation or on the heartbeat, so the series is
an irregular step function: SPY published 13 rounds that week. Anything that
treats it as evenly spaced is wrong.
**Affects:** 1.6, 1.9, 2.x (analysts); `config/chain.json`.

## 2026-09-18 — 32 of 37 feeds began life reporting answers about 1e8 too large
Measured while choosing the series: AAPL's rounds 1–17, for example, answer
around 1e8 times the price their 8 decimals imply, and 32 of the 37 mapped
feeds show the same early regime. A raw walk of round history would therefore
read a launch-week price 100,000,000× too high as if it were real. The walk
treats any 10,000× step between consecutive answers as a **scale break**. It
stops there, leaves the older rounds out, and reports coverage False with the
round named. No 7-day window reaches back to a launch today, so the guard has
not fired live. Any longer window, or a backfill, will hit it.
**Affects:** 1.3; any longer series window; 1.9's fixtures.

## 2026-09-18 — The public 4663 RPC, measured: batching refused, Multicall3 accepted, one endpoint, no Retry-After
Measured in 1.3 against `RPC_4663_MAINNET`:
- **Batching.** A JSON-RPC batch of 100 `eth_call`s drew an immediate 429,
  returned as JSON-RPC error 429 through Cloudflare with no `Retry-After`. One
  Multicall3 `aggregate3` of 215 reads was accepted. So reads go through
  Multicall3 with 500 ms pacing and a doubling backoff. No proof run failed on
  a 429, but retries are not logged, so how many the backoff absorbed is
  unknown.
- **Storage.** Storage cannot be read through Multicall3, so the 35 beacon
  slots are 35 paced calls, about 18 s. That is a real cost for 1.6's snapshot.
- **Missing state.** A pinned block stayed readable for 9 minutes (326 of 326
  reads). Once, though, a read at a block a minute old got `-32000: historical
  state … is not available` while the next read at the same block succeeded.
  It is now retried, which is safe because reads are by block hash. The first
  proof run also left 2 of 35 beacon slots unread, and their cause was not
  captured. They came back undetermined, as they must.
- **Failover.** It is built over an ordered endpoint list and advances on a
  hang: the proof put a silent local socket ahead of the real RPC and got the
  same round in 3.2 s. But there is still one real endpoint, so PLAN §13's
  "fail loudly" is still what happens. The Alchemy note remains unverified.
**Affects:** 1.6, 1.10; PLAN §13; `config/chain.json`.

## 2026-09-18 — 1.3 leaves two layout questions open, and two listed feed checks unbuilt
**Where the staleness comparison lives.** CODEBASE §3 says `core/gates.py` is
"the only module defining a threshold comparison". The record puts the
staleness rule in 1.3: PHASE-0-1 1.3, `config/thresholds.json`, and the
`Series` docstring. So `chain_4663.freshness()` compares age against heartbeat
plus margin. Either 1.8 moves the comparison into `gates.py` and the adapter
reports only age and heartbeat, or the rule gets a named exception. This pass
does not decide which. *(Correction, 2026-09-18: `gates.py` is built at 3.4,
not 1.8. ROADMAP, PLAN §8 and the stub all say so; 1.8 is held-but-untradeable.
See the DECISION below.)*

**Where the HTTP client lives.** CODEBASE lists `adapters/http.py`, "one HTTP
client: timeouts, retries, Retry-After, redaction", as 1.3's. This pass was
scoped to `chain_4663.py`, so the deadline, failover and backoff live there,
and `http.py` is still the stub. `gecko.py` (1.4) and `bankr_quote.py` (1.5)
need the same behaviour. Either it is lifted into `http.py` or they import it
from the chain adapter.

**The two unbuilt checks.** PHASE-0-1 1.3 lists "paused-oracle detection" and
"market-session awareness".
- **Paused oracles.** Neither is built as a separate check. A paused feed
  shows up only as a stale newest point, plus Chainlink's round sanity rules.
  Whether these proxies expose a pause flag was not probed.
- **Market sessions.** The freshness verdict names the feed's `market_hours`,
  but it does not vary by session. Making it vary would change the decided rule
  (the weekend entry above).
**Affects:** 1.4, 1.5, 1.8; `planning/CODEBASE.md`.

## 2026-09-18 — The feed verdict names a schedule, not a session, so the weekend decision is not recorded
**What we believed.** 1.3's closing summary told the operator that "the market
session is named in each verdict". A weekend decision was drafted on that
premise:
- a gap inside a closed session is expected, and the last round stands as the
  mark;
- a gap during an open session stays stale and blocks.

**What the record holds.** The verdict's reason carries the feed's
`marketHours` from the pinned Chainlink directory: `us_equities_24/5` for 35
feeds and `Crypto` for 22. That names a schedule. Nothing pinned, configured or
measured says when the schedule is open. There are no hours, no timezone or
daylight-saving rule, and no holiday calendar.

**What one weekend showed.**
- Every equity feed's first round came at Monday 00:00Z (Sunday 20:00 EDT).
- Friday's last rounds fell between 12:49Z and 00:01Z Saturday. A quiet feed's
  last round says when its price last moved, not when the session closed.
- SGOV, which updates on its heartbeat alone, published at 00:01Z Saturday. So
  the feed was still running at 20:01 ET on Friday.
- If the schedule follows New York time, its UTC boundaries move by an hour on
  1 November 2026. That is unmeasured.

**What we did.** The operator's instruction was to stop if the session data
could not carry the rule, and it cannot, so we stopped. The weekend decision is
**not recorded**, and PLAN §13 is unchanged. The rule in force is still the
feed's heartbeat plus 3,600 s. Under it, every equity feed's newest point goes
stale for about 23–35 h each weekend. To carry the decision, a closed session
needs a definition the operator chooses: a documented schedule pinned as the
directory is, with daylight saving and holidays, or a rule drawn from observed
rounds.
**Affects:** 1.4 (whether a weekend price may be a mark), 1.6, 1.8, 1.11; PLAN §13.

## 2026-09-18 — DECISION: the feed staleness comparison stays in the chain adapter, as a named exception to "gates exist once"
*Decided by the operator after 1.3.* Two places state the rule:
- CODEBASE §3 and its rules table: `core/gates.py` is the only module defining
  a threshold comparison;
- PLAN §2 invariant 4, "Gates exist once".

1.3 built the feed staleness comparison in `adapters/chain_4663.py`
(`freshness()`), where the record placed it: PHASE-0-1 1.3 and
`config/thresholds.json`. It stays there for now, as a recorded exception, not
an unmarked contradiction.

**The reason.** The plan assigned the rule to 1.3, and `gates.py` does not
exist until 3.4. The comparison is still defined in one place, and its margin
is still read from `config/thresholds.json`.

**Still open.** Whether a later unit moves it into `gates.py`, leaving the
adapter to report only age and heartbeat.

**Open, not reconciled.** The decision as given says "whether 1.8 moves it".
That unit number came from 1.3's summary, and it was wrong: `gates.py` is 3.4's
(the correction above). Which unit revisits the location is the operator's to
say.

When the "one gate definition" test is written, it must name this exception or
it will fail on it.
**Affects:** 3.4; CODEBASE §3 and rules table; PLAN §2 invariant 4; PHASE-0-1
1.3 (*fold pending*: outside this pass's paths).

## 2026-09-18 — DECISION: a closed session is inferred from the feeds' own rounds, not a pinned calendar
*Decided by the operator before 1.4.* This settles the question the entry "The
feed verdict names a schedule, not a session" left open. The directory's label
(`us_equities_24/5`) names a schedule, and nothing we hold says when it is open.
So the session is inferred from when the feeds actually publish, and not from a
pinned calendar of hours, timezone and holidays:
- a gap that matches the inferred closed session is expected, and the last
  published round stands as the mark;
- a gap during an inferred open session is stale, and blocks.

**The cost, stated with the decision.** Holidays are not modelled. A holiday
looks like an unexpected gap in an open session, so the fund treats it as stale
and refuses to value. That fails closed rather than open, and PLAN §13 says so.

**The condition.** Measure the pattern before writing the rule. If the observed
rounds do not support a clean inference, stop rather than fit a rule to one
weekend.
**Affects:** 1.3's `freshness()`, 1.4, 1.6, 1.8, 1.11; PLAN §13;
`config/thresholds.json`.

## 2026-09-18 — DECISION: the HTTP client moves to `adapters/http.py`
*Decided by the operator before 1.4.* 1.3 built the deadline, failover on a
hang, pacing, doubling backoff, User-Agent and redaction inside
`chain_4663.py`, because that pass was scoped to one file. 1.4 (`gecko.py`) and
1.5 (`bankr_quote.py`) need the same behaviour, and an adapter importing another
adapter is worse than a shared transport. So it moves to `adapters/http.py`, the
chain adapter imports it, and 1.3's `--prove` must still pass unchanged.
CODEBASE says `http.py` also handles Retry-After, which the inline client never
did, because the 4663 RPC sends none. Whether GeckoTerminal does was unmeasured,
so it is measured first and handled if so.
**Affects:** 1.3, 1.4, 1.5; `planning/CODEBASE.md` §2.

## 2026-09-18 — Twelve weekends measured: every equity feed stops by Sat 00:02Z and restarts at Mon 00:00Z, and both holidays closed a whole session
The weekend decision required measuring the pattern before writing a rule.
`python -m fund.adapters.chain_4663 --sessions` read every round of all 35
`us_equities_24/5` feeds at block 66681376: 86,606 rounds from 2026-06-23 13:50Z,
when the launch regime's scale break ends, to 2026-09-19 00:01Z.
- **Pooled over every week, no round was ever published between Sat 00:01:45Z
  and Mon 00:00:16Z.** That held in each of 12 complete weeks. The last round
  before the gap fell between Fri 23:13Z and Sat 00:01:45Z (SGOV's heartbeat
  lands just after 00:00Z). The first round after it fell between Mon 00:00:16Z
  and 00:00:24Z, most feeds within the first minute. That is Friday 20:00 to
  Sunday 20:00 in New York, in daylight time.
- **The proposed span is Sat 00:05Z to Sun 23:55Z.** The quiet span is shrunk
  by a 60 s guard on each side, then to whole 5 minutes. That counts 10 minutes
  a week less as closed, which fails closed.
- **Both holidays in range closed a whole session.** Fri 3 July (Independence
  Day observed) and Mon 7 September (Labor Day) each silenced every feed for 24
  more hours: 72.0 h and 72.6 h quiet. Replayed over all history, the rule with
  the span is never stale on any weekday or weekend except these two holidays:
  - on 3 July, 28 of the 34 feeds then live were stale until Monday's open,
    most of them from Friday afternoon;
  - on 7 September, 34 of 35 were stale for the last 1–23 h of Monday.

  Without the span, all 35 go stale every weekend.
- **Daylight saving is unmeasured.** Every week observed is daylight time. If
  the schedule follows New York time, both edges move to 01:00Z on 1 November
  2026. The Saturday side would then put rounds inside the span, which the
  rule treats as a contradiction. The Monday side would add an hour of open
  time.
- **Crypto feeds need no span.** The widest gap between two rounds of ETH/USD
  or USDG/USD is 24h01m, inside heartbeat plus margin.

The inference is clean enough to build the rule on. Holidays still read as a
stale open session, as the decision said they would.
**Affects:** 1.3's `freshness()`, 1.4, 1.6, 1.8, 1.11; PLAN §13; `config/sessions.json`.

## 2026-09-18 — GeckoTerminal's 429 says `Retry-After: 0`, and its limit is a handful of requests
Measured on the batch tokens endpoint, 2026-09-19 01:01Z:
- **A burst hit the limit fast.** The sixth request inside 0.5 s drew a 429.
  The body names the error, and the header `Retry-After: 0` says nothing.
- **Recovery took seconds.** Polls a second apart stayed 429 for 4.3 s.
- **Paced requests still ran out.** At 2.1 s spacing, 5 requests passed, then
  10 were refused over about 21 s.

So the limit is roughly five requests before a refusal that lasts seconds to
tens of seconds, recorded as observed, not as a published number. The shared
client therefore reads Retry-After but treats 0 as no hint, and falls back to
its doubling backoff. The response also carries `Cache-Control: max-age=30,
s-maxage=60` and no timestamp for the price. So a corroborating price can be
up to a minute old at the edge, and its source time is unknown.
**Affects:** 1.4; `adapters/http.py`, `config/gecko.json`.

## 2026-09-18 — 1.4 compares the divergence tier in `core/valuation.py`: a second site outside `gates.py`, open and not decided
CODEBASE §3 and PLAN §2 invariant 4 make `core/gates.py` the only module that
defines a threshold comparison. They record one exception, feed staleness in
the chain adapter. PHASE-0-1 1.4 tells this unit to gate by the tiered rule,
and its done-condition says "the tier comes from config". But `gates.py` is
3.4's, and it was outside this pass's paths. So `valuation.cross_check()`
compares both numbers: 24h volume against the $1M line, and divergence
against 100 bps. Each reads its threshold from `config/thresholds.json` as an
argument, and each refusal names its rule.

That is the same shape as the staleness case: the plan put the rule in an early
unit, and the gate module does not exist yet. It is recorded **open, not
decided**, and CODEBASE §3 and PLAN invariant 4 now say so. Whether it becomes
a second named exception or moves into `gates.py` at 3.4 is the operator's call.
Either way, the "one gate definition" test must name it.
**Affects:** 3.4; CODEBASE §3 and rules table; PLAN §2 invariant 4.

## 2026-09-18 — 1.4 live: 20 of 35 above the line, and the veto fired on a liquid name inside the closed session
`python -m fund.adapters.gecko --prove`, block 66689567, Sat 2026-09-19
01:28Z, which is inside the inferred closed session:
- **The tier.** 20 of 35 markable stocks were above the $1M line (F0.4.5 had
  19 of 32). 15 fell below it, so at this block the universe would shrink to
  20.
- **The veto fired live.** MSTR diverged −122.87 bps on $4.76M of volume. The
  other 19 above the line agreed within 77 bps.
- **Measured at one block only, and read with that in mind.** The feeds are
  frozen through the closed session while the pools trade on. MSTR tracks
  bitcoin, which trades all weekend. So a veto here may measure weekend drift
  rather than a broken mark. It fails closed either way, and whether weekend
  divergence should be judged differently is not decided.
- **Cash is not a dollar.** USDG/USD marked $0.99995.

The recorded AMZN case (−499.47 bps on $2.19M) is vetoed by the same function.
**Affects:** 1.6, 1.11, 3.4; the weekend cycle.

## 2026-09-18 — DECISION: divergence during a closed session is a finding, not a veto
*Decided by the operator after 1.4.* In an inferred closed session the feed is
frozen while the pools keep trading. Divergence then measures market movement
since the close, not a broken mark. Vetoing on it is too blunt: 1.4's proof
vetoed MSTR at −122.87 bps on $4.76M of volume, on a Saturday, and MSTR tracks
bitcoin, which trades all weekend.
- **In a closed session:** mark at the last published price, do not veto on
  divergence, and record the divergence as a finding.
- **The finding reaches the decision record, not just a log.** A buyer of the
  record should see that the pool moved while the feed was frozen. That is the
  difference between "we ignored it" and "we saw it and judged it expected".
- **In an open session:** the divergence veto is unchanged and still fires.

**Not yet in code.** `core/valuation.py`'s `cross_check()` still vetoes in a
closed session. It was outside 1.5's paths. Three things are owed:
- `cross_check()` must take whether the mark's feed is inside its closed span;
- the snapshot entry must carry the finding (1.6);
- the decision record must carry it (3.7).

A holiday is not a closed session under the 1.4 decision. There the mark is
stale, so there is no mark to cross-check at all.
**Affects:** 1.4's `cross_check()`, 1.6, 3.4, 3.7, 3.8; PLAN §11.

## 2026-09-18 — DECISION: threshold comparisons stay where the plan put them, as named exceptions, and 3.4 sweeps them into `gates.py`
*Decided by the operator after 1.4.* CODEBASE §3 reserves threshold comparisons
to `core/gates.py`. That module is 3.4's, while 1.3, 1.4 and 1.5 each need
one. So each is recorded as a **named exception with its reason**, rather than
three unmarked contradictions, and **3.4 owns the sweep** into `gates.py` as one
deliberate move. The three:
1. **Feed staleness**, in `adapters/chain_4663.py` `freshness()` (1.3).
   Heartbeat plus margin in open-session time; margin from
   `config/thresholds.json`.
2. **The divergence tier**, in `core/valuation.py` `cross_check()` (1.4). The
   $1M line and the 100 bps veto, from `config/thresholds.json`.
3. **Quote age and signed impact**, in `adapters/bankr_quote.py` (1.5). 60 s
   and 50 bps, from `config/thresholds.json`.

Each reads its thresholds from config as arguments, and each refusal names its
rule. This settles two questions left open:
- which unit revisits the staleness exception (3.4, not the "1.8" the first
  decision named);
- whether the divergence tier is an exception (it is, until 3.4).

The "one gate definition" test must name all three until the sweep.
**Affects:** 3.4; CODEBASE §3 and rules table; PLAN §2 invariant 4; PHASE-0-1
1.3-1.5; ROADMAP 3.4.

## 2026-09-18 — 1.5 live: 31 of 35 tradeable at $25, and the four refused at impact all sit below the corroborator line
`python -m fund.adapters.bankr_quote --prove`, Sat 2026-09-19 01:52Z: all 35
markable stocks quoted at 25.001227 USDG. That is $25 at USDG's own Chainlink
mark, $0.99995.
- **31 are tradeable.** Their impact ran from −19 to +48 bps.
- **Four were refused at `impact` at the nominal size itself:** CLSK 991 bps,
  RGTI 684, IONQ 480, NBIS 77. All four were below the $1M corroborator line
  at 1.4: IONQ $0, CLSK $242, RGTI $507, NBIS $28k. The first three were the
  three thinnest pools.
- **The link is not one for one.** The other eleven names below the line
  passed on impact, EWY at $2.6k and CRWV at $4.9k among them. Thin pools and
  wide venue impact go together here, but not reliably. That is one
  observation each, not a rule.
- **Impact moves quote to quote.** Two runs two minutes apart gave TSLA −11
  then +1, and different sets of names with negative impact: 10, then 4. A
  quote is a moment, which is why its age is bounded.
- **Quotes price on a Saturday,** while the feeds are frozen in their closed
  session.

So PLAN §12's "how many are tradeable at $25" has a first measured answer: 31
of 35, at one moment. Whether any would fill is still unmeasurable (F0.5.1).
**Affects:** 1.6, 3.3; PLAN §12.

## 2026-09-18 — F0.3.4 re-run: the two impact fields never differ even at 7,084 bps, and a quote prices far past the venue's own cap
F0.3.4 left open whether `swapImpactBps` and `priceImpactBps` ever differ, and
said a size large enough to separate them was needed. 1.5 quoted 25,000 USDG,
read-only, on the three names with the widest impact at $25:
- CLSK 6,417 bps, RGTI 5,500 and IONQ 7,084;
- the two fields were identical every time;
- `maxPriceImpactBps` said 1,500 every time.

So the venue returns a 200 quote at more than four times its own documented
cap. The cap binds at execution, if anywhere, not at quoting. It is still only
documented that `swapImpactBps` is the field execution gates on, since the two
have now been measured equal up to 7,084 bps. The adapter gates on
`swapImpactBps` as documented, at 50 bps, far inside either number.
**Affects:** 1.5, 3.4, 5.6; closes F0.3.4's "needs a funded wallet" (it did not).

## 2026-09-18 — The venue declines with HTTP 500, and `http.py` retries it and keeps no body
A 0.000001 USDG quote drew HTTP 500 `{"message":"No quote available"}`, three
times. It is the venue's answer, not a transport failure. But `adapters/http.py`
treats every non-200 as transient: it retries, and keeps only the status. The
first cut of 1.5 then called the result unreachable. Two changes to
`http.py` are owed, both outside 1.5's paths:
1. **A status the caller names as an answer should come back without retries.**
   Until then, 1.5 records every reply at its transport and reads the venue's
   body from there. A declined quote costs three requests and 6 s of backoff.
2. **`urllib_transport` should take caller headers.** Until then, 1.5 supplies
   its own four-line transport to put the key in `X-API-Key`. The deadline,
   retries, pacing and redaction are still `http.py`'s.
**Affects:** `adapters/http.py`, 1.5, 4.x (`bankr_exec` will meet the same).

## 2026-09-18 — 1.5 sizes $25 at USDG's Chainlink mark, not at the venue's USDG price
PHASE-0-1 1.5 said "$25 nominal is about 24.94 USDG", which is $25 at the
venue's own USDG price of 1.0022 (F0.3.5). 1.5 converts at USDG's Chainlink
mark instead: $0.99995 gives 25.001227 USDG, rounded down.
- **Why.** Chainlink marks the book (PLAN §11). Sizing at the venue's price
  would let the venue decide what $25 is.
- **The difference.** It is about 0.2% on one trade.
- **Status.** A choice made inside the unit, recorded here for the operator to
  overrule.
**Affects:** 1.5, 3.3.
