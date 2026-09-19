# Lessons

A history of what went wrong, what surprised us, and what changed as a result.

**This file is history, not authority.** [planning/PLAN.md](../planning/PLAN.md),
[planning/ROADMAP.md](../planning/ROADMAP.md) and [planning/PHASE-0-1.md](../planning/PHASE-0-1.md) are the
authoritative plan; every change recorded here has been folded into them —
checked entry by entry on 2026-09-18, after this claim had been false since
before 09:10 that day. Where a fold exposes a contradiction, the plan doc marks
it open rather than reconciling it.

**Pending folds into the plan docs: the 7.6 page slice into ROADMAP, if the
operator approves it.**

**Folded on 2026-09-19, before 2.0 ran:** into `CLAUDE.md`, PLAN §8, ROADMAP,
SIMPLIFICATION.md and the gate report's marker:
- 2.1 as a stop;
- unit 2.0;
- the 70,000 context budget.

**Folded before that, after the scope pivot:** The 2026-09-19 decisions are folded into PLAN §8, where the phase list
begins, with markers in §1, §2, §5, §6, §11, §12 and §13. They also sit in the
ROADMAP unit tables, PHASE-0-1, `planning/SIMPLIFICATION.md`,
`planning/JUDGING-CRITERIA.md` and `CLAUDE.md`.

**Owed outside the plan docs, because they sit outside that pass's paths:**
- `config/analysts.json`: the fourth seat and the two vocabularies, with 2.1;
- `credentials.py` and `.env.example`: five agent keys, once SIWE is verified;
- the README status line.

F0.4.1 in `research/findings.md` still says every equity feed is named
`Robinhood <TICKER> / USD`. That file is research, not plan, and was outside
1.10's pass.

**Owed in code, outside the paths of the passes that found them:**
1. **`adapters/http.py`, two changes** (found by 1.5): return a caller-named
   status as an answer without retries, and take caller headers on
   `urllib_transport`. 1.5 works around both in its own module.

Done in 1.8: the chain client's second missing-state wording, and
`valuation.py`'s docstring on findings. Done in 1.9: `make snapshot`, now the
live build, which captures.

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

## 2026-09-18 — DECISION: the live read lives in `run/snapshot.py`
*Decided in 1.6, as delegated.* `core/` makes no network calls, so something
above it must call the adapters and hand `core/snapshot.build()` their results.
That is `run/`: CODEBASE §5 draws `run/cycle.py` calling `chain_4663`, `gecko`
and `bankr_quote` before the build. `cycle.py` is 4.8's, so 1.6 builds
`run/snapshot.py`, the read that `cycle.py` will call.
- **It is the one place the adapters meet.** The 1.4 and 1.5 proofs composed
  them inside their own `prove()` functions, and stay as those units' proofs.
- **It makes the adapters' verdicts** with their own functions: freshness in
  open-session time, and tradeability. `core/` receives them as data.
- **It reads the quotes last,** so they are as young as they can be when
  judged.
- **`make snapshot` still prints "not built yet".** The Makefile was outside
  1.6's paths, so the command is `python -m fund.run.snapshot`.
**Affects:** 4.8; CODEBASE §2 and §5; the Makefile.

## 2026-09-18 — 1.6 retires 1.1's `Snapshot` type: the snapshot is a document written to be read
1.1 defined `Snapshot` and `SnapshotEntry` as types whose canonical encoding
was the snapshot. That encoding tags every object and repeats full provenance on
every series point: 831 bytes a point, against 37 for a `[time, price]` pair.
That is about 3.9 MB for a real snapshot's 4,753 rounds, and no analyst can read
it. So `core/snapshot.py` builds a document from the typed objects:
- exact decimal text, UTC times, and null for unknown;
- each asset's four admission rules as separate fields;
- a named status, the first rule that did not pass;
- the series as pairs, with coverage stated.

The bytes on disk are the hashed bytes. They use a canonical form of their own:
sorted keys, one space of indent, and arrays of scalars on one line. Chain
values carry their block and not their fetch time, so a re-read at the same
block hashes the same. Offchain values carry their fetch time.

Three statuses were added for one snapshot: `no_mark`, `uncorroborated` and
`divergence_veto`. 1.1's measured cases now coexist in `tests/test_snapshot.py`.
**Affects:** 1.1, 1.7 (the byte count it prices), 1.9, 2.x, 3.7; CODEBASE §2 and §4.

## 2026-09-18 — 1.6 live: 348 KB, 20 tradeable, and three liquid names past 100 bps inside the closed session
`python -m fund.run.snapshot --prove`, block 66716733, Sat 2026-09-19 02:13Z:
- **Size.** 347,648 bytes, 4,753 rounds of history, all 35 series covering
  their window. The timeline dominates. Tokens are not measured; that is 1.7's.
- **Statuses.** 20 tradeable, 15 below the corroborator line, and nothing
  undetermined.
- **Findings.** 20 closed-session findings, one per name above the line.
  Three are past 100 bps and would have been vetoed in an open session: AMZN
  −423.69, PLTR +190.73 and MSTR −168.55. AMZN was −4.01 at 1.4's run 45
  minutes earlier. On a weekend, a pool's divergence swings far and fast.
- **Holdings.** USDG and ETH, valued at their own marks. Nothing registry-listed
  is held outside the universe.
- **Rebuilt at the same block.** A fresh re-read of the chain gave identical
  values and an identical hash. One GeckoTerminal price moved by one unit gave
  a different hash.
- **Timing.** The chain read took 58 s, mostly 35 paced beacon slots and the
  series walks. The oldest quote was 29.1 s old at `built_at`, half the 60 s
  budget, because 35 quotes are read one after another.

A fully live second build would differ, because GeckoTerminal and the quotes
are not pinned to a block. Recording them is 1.9's.
**Affects:** 1.7, 1.9, 3.7, 3.8; the quote-age budget as the universe grows.

## 2026-09-18 — AMZN's corroborating price alternates between two levels, so its "divergence" may be GeckoTerminal changing pools
Three readings of GeckoTerminal's token-level AMZN price, against a feed that
stayed between 252.60 and 253.86:

| Reading | When | GeckoTerminal | Divergence |
|---|---|---|---|
| Probe 0.4 (F0.4.5) | Fri 15:40Z, open session | 265.88 | −499.5 bps |
| 1.4's proof | Sat 01:28Z, closed | 253.96 | −4.01 bps |
| 1.6's snapshot | Sat 02:14Z, closed | 265.09 | −423.69 bps |

The two high readings sit about $1 apart. The low one agrees with the feed and
the venue.
- **The explanation is not measured.** One reading is that the token-level
  price follows whichever pool GeckoTerminal ranks first, and that the ranking
  changes; the batch endpoint lists only one pool (F0.4 limitations).
- **What it means for the findings.** If that is right, AMZN's "divergence" is
  the corroborator switching sources, not the market moving while the feed was
  frozen. The closed-session finding's wording says the pools traded on, which
  would then be wrong for AMZN.
- **The veto was right to catch it** at 0.4, whatever its cause.
- **Unresolved.** Finding out needs the pool list for AMZN, which the batch
  endpoint does not give.
**Affects:** 1.4's corroborator, the finding's wording, 3.7, 3.8; F0.4.5's AMZN case.

## 2026-09-18 — DECISION: a closed-session finding only when the divergence is past the open-session limit
*Decided by the operator after 1.6.* 1.6 recorded one closed-session finding
for every asset above the $1M line: 20 in one weekend snapshot, 17 of them
within the 100 bps an open session would veto at. Only the ones past the limit
are interesting. The rest are noise in a document that analysts read and buyers
pay for.
- **Now:** the snapshot emits a finding only when
  `beyond_open_session_limit` is true.
- **Unchanged:** the `corroboration` block, which carries every divergence and
  its session.
- **The finding stays in the snapshot.** `core/valuation.py` still returns a
  `Finding` for every closed-session cross-check above the line, and the
  snapshot filters them. Its docstring says the snapshot entry carries the
  finding, which is now true only past the limit. That wording is owed; it
  was outside 1.7's paths.
**Affects:** 1.6's `core/snapshot.py`, 3.7; PLAN §11; PHASE-0-1 1.6.

## 2026-09-18 — 1.7: an analyst call is $0.454 and a cycle $1.87 against the real snapshot, and the timeline is two thirds of the input
0.9 measured a floor on six hand-assembled assets and said the real number would
be higher. 1.7 measured it against snapshot `7eba6212…` (335,294 bytes, 4,628
rounds) at `claude-sonnet-5`, with four calls.
- **Two identical analyst calls:** 185,168 tokens in, 9,087 and 7,725 out,
  $0.461 and $0.448, 75.0 and 62.4 s.
- **A risk call over four stand-in reports:** $0.048.
- **A cycle:** $1.87, which is $56 a month. That is 28 times the floor.
  Covering one cycle at $0.05 a record takes 37 sales.
- **The timeline:** 123,765 of the input tokens, 66.8%, and 53% of a cycle.
- **The snapshot fits,** at 18.5% of a 1M-token window. Three smaller models
  would not hold it.
- **Reconciliation:** the balance and a settled `/v1/usage` window both agree
  with the listed price to the last digit.

What it leaves for others to decide:
- whether to thin the history, where halving it saves about $0.50 a cycle;
- whether to cache the shared snapshot, which is priced to take a cycle to
  about $0.96, is untested, and does not happen automatically;
- the model, a 180× price span, which is 2.4's;
- the $0.05 price, which is the operator's.

About 37–50% of billed analyst output does not appear in the reply. That is
inferred, most likely hidden reasoning (`research/findings.md` §1.7).
**Affects:** 1.6's history window, 2.4, 6.3, 7.2, the 0.7 price; PLAN §10, §11.

## 2026-09-18 — 1.7: the configured timeouts cover today's calls, but not the evidence
The analyst calls took 62 and 75 s, inside the 120 s worker deadline. But:
- **Output is uncapped:** `max_output_tokens` is null, and the replies ran to
  9,087 tokens.
- **Throughput varied sevenfold:** about 17 output tokens/s at 0.9, and about
  121 at 1.7. A 9,087-token reply at 0.9's rate takes about 535 s.
- **A cut-off call still bills,** with no report (F0.9.3).
- **The two values are inverted:** 120 s against 180 s, so the transport
  timeout never acts inside the runner.

**Recommended, not set,** because the values are 2.4's and the operator's:
- `max_output_tokens` about 12,000;
- `transport_timeout_seconds` at least 600;
- `worker_deadline_seconds` at least the transport timeout plus a margin, such
  as 630.

`config/models.json` notes the measurement and leaves the values alone.
**Affects:** 2.4; `config/models.json`.

## 2026-09-18 — The chain client misses a second wording of missing state
1.7's snapshot lost SPCX's history after its newest round:
`-32000: … layer stale missing trie node … layer stale`. 1.3's `RpcClient`
retries missing state only when the message reads "historical state … not
available". A read by block hash is safe to retry in either wording.
- **The snapshot told the truth.** SPCX's coverage is `null` with the error,
  and it has one point.
- **The analyst saw it,** and abstained on SPCX for that reason.
- **The status did not change:** SPCX stayed `tradeable`, because status does
  not look at coverage, and whether it should is open.
- **The fix is owed** in `adapters/chain_4663.py`, outside 1.7's paths.
**Affects:** 1.3's `RpcClient`, 1.6, 1.11.

## 2026-09-18 — DECISION: the x402 price rises to $0.25 a record
*Decided by the operator after 1.7.* At 1.7's measured $1.87 a cycle, $0.05
needs 37 record sales a cycle to cover inference. $0.25 needs 8, which is still
cheap for an agent buying a research record. **Provisional**: it can move again
once the cycle cost settles, which the history and caching decisions below may
do. This answers 1.7's "done when".
**Affects:** 1.7, 7.2, 7.4, 8.6; PLAN §11.

## 2026-09-18 — DECISION: thin the history to daily closes over 30 days, if measurement supports it
*Decided by the operator after 1.7, on a condition.* At 1.7 the series was
every round over 7 days: about 132 points an asset, 66.8% of the input and 53%
of a cycle, for a fund that rebalances daily. It is to become one close a day
over 30 days, a longer view in fewer points.
- **Measure first.** Build a snapshot with the new series, re-run 1.7's analyst
  call against it, and report tokens, cost, and whether the reports still cite
  history. If daily closes make the analysts worse, the denser series stays.
- **No close is invented.** A daily close inside a closed session does not
  exist, and the series must say what it does across a weekend rather than
  interpolate.
**Affects:** 1.3's series, 1.6, 1.7's numbers, 1.9; `config/chain.json`.

## 2026-09-18 — DECISION: output cap 12,000; transport timeout 600 s; worker deadline 630 s
*Decided by the operator after 1.7,* as recommended in F1.7.4, and set now
rather than at 2.4.
- **The inversion was the real bug.** A 120 s worker deadline fired before a
  180 s transport timeout could.
- **The slow case is real.** The gateway ran at about 17 and about 121 output
  tokens a second at 0.9 and 1.7.
- **A call cut off on our side is still billed** (F0.9.3).

The worker deadline now exceeds the transport timeout, so the transport ends a
call and the worker is left time to record it.
**Affects:** 2.4; `config/models.json`.

## 2026-09-18 — DECISION: test explicit prompt caching, in two calls
*Decided by the operator after 1.7.* If four analysts can share one cached
snapshot, a cycle drops from about $1.87 to about $0.96 (F1.7.6), halving the
largest cost line in the project. Two calls:
- one that writes the cached snapshot;
- one that reads it.

They measure whether the gateway honours cache control, and what it saves.
**Affects:** 2.4, 6.3; PLAN §10.

## 2026-09-18 — Daily closes measured and adopted: the input halves, a call costs 42% less, and the reports use history as much as before
The decision to thin the history was conditional, so it was measured first
(`research/findings.md` §1.8a). A snapshot with one close a day over 30 days:
- **Size:** 189,357 bytes and 763 points, against 335,294 and 4,628.
- **One analyst call:** 94,716 tokens in and $0.264, against 185,168 and
  $0.454.
- **How the reports used history:** 35 of 35 cited the timeline, 18 quoted
  dated points, and none said `NO_CALL`. 1.7's two *identical* calls spanned
  20–35, 10–31 and 1–16 on the same counts, so the daily call sits inside that
  range. It is not worse on any count. That is one call and a proxy, not a
  grade.
- **The cycle:** $1.11 instead of $1.87. At $0.25 a record it is covered by
  4.4 sales.

The series says what it does across a gap, rather than interpolating:
- a day whose 20:00Z cut falls in the closed session has no close;
- a day with no new round since the previous close has none, as on Labor Day;
- the latest round is always last, so freshness still judges the newest round.

Adopted in `config/chain.json`. Two cautions:
- 20:00Z is 16:00 in New York only in daylight time;
- the proxy that caught the reports' dates first missed them, because they are
  written `08-20`, and it was corrected before this entry.
**Affects:** 1.3's series, 1.6, 1.7's cost, 1.9, 2.x; PLAN §8, §10;
`config/chain.json`.

## 2026-09-18 — The gateway does not honour prompt caching
Two `/v1/messages` calls were made:
- both marked the system prompt and the snapshot `cache_control: ephemeral`;
- the second read the same prefix under a different analyst's scope, 62 s
  after the first.

Both billed the full ~94,720 input tokens at $2/M. Neither `usage` block
carries a cache field, and the gateway's own settled `/v1/usage` records zero
cache reads and writes, although its price list offers both. So the halving
F1.7.6 priced is not available through this path. Other request shapes are
untested, since the decision allowed two calls. The cycle stays at $1.11,
uncached.
**Affects:** 2.4, 6.3; PLAN §10.

## 2026-09-18 — A short series left an asset tradeable, a defect separate from the missing retry
1.7's SPCX series stopped after one point on `missing trie node … layer
stale`, which the chain client did not retry. That is now retried. But
retrying only makes the error rarer. The status pipeline never read the
series' coverage, so any series that fell short left its asset `tradeable`,
whether from a read failing partway, a round cap, or a young feed.
- **The fix.** A `history` rule now runs after the mark: coverage false is
  `short_history`, refused, and coverage undetermined is `short_history`,
  undetermined.
- **The reasoning.** An analyst reasons from the series, and a buy on one
  point is a buy on no history.
**Affects:** 1.6's status order, 1.11; `core/snapshot.py`.

## 2026-09-18 — 1.8: the registry dropping a held asset was the quiet way out of the book
Holdings come from the chain: a balance is read for cash, gas, and every asset
the pinned registry lists. 1.2's `accept()` already refused a registry refresh
that removed a held asset unless acknowledged. But once acknowledged, the
asset was in no list anything read, so its balance stopped being read and the
holding left the book. The books would still balance, and they would be wrong.
- **What 1.8 changed.** An acknowledged removal now writes the asset to
  `pins.json`'s `carried` list, with its last record's symbol, name and
  decimals, and the registry version that dropped it. The live read keeps
  reading its balance, and it stays a holding: `identity_in_doubt`, no mark,
  and `value_usd` null with the reason. A registry that lists it again takes it
  off the list.
- **Every other way out already kept the row,** because a held asset in or out
  of the universe was always read. 1.8 now proves it:
  - `tests/test_holdings.py` takes a held NVDA out ten ways, and the set of
    holdings is identical before and after each;
  - a test fails if a way-out status has no case there.
- **The count of ways out.** PHASE-0-1 1.8 lists five. The task named four.
  1.6 and 1.8 have added four per-snapshot statuses: no mark, short history,
  uncorroborated, and divergence veto. All are tested, nine statuses in all.
**Affects:** 1.2's refresh, 1.6, 1.9, 4.x's positions; `config/registry/pins.json`.

## 2026-09-18 — 1.8: each holding carries a holding status apart from its universe status
- **The universe status** says whether the asset can be bought.
- **The holding status** says three things:
  - `owned`: the balance, or why it was not read;
  - `valued`: true at its own mark, false with the reason when there is none
    (never zero, never the venue's quote), and undetermined when the mark or
    balance is unread;
  - `exit`: true for cash, which is what a sale settles into; for ETH and the
    stocks it is *not assessed*, because Phase 1 reads no sell quote, and a
    stock sale is paper for this operator (F0.5.1).

The snapshot schema is now `openfund.snapshot/2`, with sampled timelines and
these rows. Live, at block 66750551, USDG and ETH carry both statuses, and a
re-read at the same block rebuilt to the identical hash.
**Affects:** 1.9, 3.3 (sizing reads holdings), 4.x, 6.x.

## 2026-09-18 — DECISION: captures are recorded at the transport, and the repository keeps them in `fixtures/snapshots/`
*Decided in 1.9, as delegated.* `fixtures/live/` is gitignored, so every
snapshot so far has existed on one machine. A fixture that cannot be committed
cannot run in CI or on a judge's machine.
- **Where.** Every live build writes its capture to `fixtures/live/captures/`,
  never committed. A capture chosen for the repository is taken with
  `--capture fixtures/snapshots` and checked for every declared credential
  value before it is committed. The first is 1 MB, at block 66812461.
- **At the transport.** The capture is the raw answers, not the adapters'
  parsed results, so a replay runs the same parsing code the live build did.
- **The config, copied.** The eight config files the snapshot names by hash
  are copied, because they change. The registry and feed directory are
  referenced by sha256, as PHASE-0-1 1.9 asked.
- **Not kept: `Set-Cookie`.** The venue's answers carried an AWS load-balancer
  cookie. It is not a declared credential and no adapter reads it, but it does
  not belong in a repository.
**Affects:** 1.9, 4.8 (`make cycle-demo`), CI; `fixtures/snapshots/`, `.gitignore`
(unchanged).

## 2026-09-18 — 1.9: a changed byte the snapshot does not carry cannot change its hash
The unit asked that a changed byte in any captured response change the rebuilt
hash.
- **For bytes the snapshot is built from, it does.** A test changes one byte in
  the chain's answers, GeckoTerminal's, the venue's, and the clock tape, and
  each rebuilt hash differs.
- **For bytes it never reads, nothing can.** A GeckoTerminal cache-status
  header changed from MISS to MIST rebuilt the identical snapshot. The same
  goes for a JSON-RPC id, or any header an adapter ignores. Only the snapshot
  naming its capture by hash would make those move it, and that is a
  `core/snapshot.py` change, outside 1.9's paths.
- **What 1.9 does instead.** The manifest holds each file's sha256, and a
  replay with any altered file fails and names it.
- **Open:** whether the snapshot should carry its capture's hash, so that a
  decision record can cite its raw inputs directly. That is the operator's
  call.
**Affects:** 1.9, `core/snapshot.py`, 3.7 (decision records citing their inputs).
*Resolved at the 1.9 checkpoint: the next entry.*

## 2026-09-18 — DECISION: the snapshot names its capture's answers by hash
*The operator's, at the 1.9 checkpoint.* A decision record should cite the raw
answers it came from, not only the snapshot built from them.
- **What it holds.** `inputs.capture` holds the sha256 of the capture's
  answers (the per-source `*.jsonl.gz` files and `clock.json.gz`) and each
  file's sha256. A buyer can hash the files themselves and find both.
  Schema `openfund.snapshot/3`.
- **With nothing recorded,** the field is `sha256: null` with a reason, never
  an empty string. That covers tests built from typed inputs.
- **Sealed before the build.** The answers are complete before the snapshot is
  built, so the capture is sealed first and written after.
- **What broke was what was predicted:** the core type, the cache writer, the
  committed fixture's `snapshot.json`, and the snapshot, cache, replay and run
  tests. Nothing else reads the schema or the hash.
- **The fixture.** Its raw answers are unchanged, and its snapshot was rebuilt
  from them, as `daafd945…`. The manifest keeps the live build's `8afe38a3…`
  and says why it was rebuilt. The two differ only in the schema and the new
  field.
- **The header byte now moves the hash.** It is a test case.
**Affects:** 1.9, `core/snapshot.py`, `adapters/cache.py`, `fixtures/snapshots/`,
3.7.

## 2026-09-18 — 1.10: nine feeds describe themselves `RH<ticker> / USD`, not as the directory names them
F0.4.1 recorded the equity feeds as named `Robinhood <TICKER> / USD`, read from
Chainlink's directory. The selftest's first live run read each proxy's own
`description()`. Nine answer `RH<TICKER> / USD`: AMD, INTC, MSFT, MU, NVDA,
SNDK, SPY, TSLA and USO. The directory's names and the chain's disagree on
correct values.
- **What 1.10 did.** A description names its asset by the registry symbol or
  by `RH` and the symbol. The check against the directory's name was dropped,
  because it failed on correct values. It was redundant anyway: the asset check
  already catches a swapped proxy.
- **Nothing else reads a description.** The feed map is keyed by address and
  checks names against the directory only.
- **Not folded:** `research/findings.md` F0.4.1 is outside this pass's paths.
**Affects:** 1.10, F0.4.1, anything that would match a feed by its name.

## 2026-09-18 — 1.11: mixed blocks are refused by the builder, not by 1.3, and three of its four checks were untested
The brief credited 1.3 with refusing mixed blocks. `require_one_block` in
`adapters/chain_4663.py` does, but its only caller is `--prove`. What refuses a
mixed block in a build is `core/snapshot.py`'s block-pin, which checks four
places: the mark, each series point, the cash and gas readings, and each
balance. Only the mark was tested. With the check deleted at any of the other
three, all 347 tests passed.
- **What 1.11 did.** The block-pin test is parametrized over the four places,
  and each case asserts the message naming its own place. Each deletion now
  fails exactly its own case.
- **Not changed:** `require_one_block` stays as the proof's own check.
**Affects:** 1.3, 1.6, 1.11.

## 2026-09-18 — 1.11: no offchain body carries a source time, so a replayed body cannot be built from a real source
PHASE-0-1 1.11 asked that an offchain response whose newest point's source time
is old relative to its fetch time be refused. That assumed an offchain series
with dated points. Since the price-history decision, history comes from chain
rounds.
- **The bodies.** In the committed capture, GeckoTerminal's token entries and
  the venue's 35 quotes carry no time field. The venue documents that a quote
  has no timestamp.
- **The only source-stated time is the HTTP `Date` header,** at 1 s
  resolution. Four GeckoTerminal answers measured were all edge-cache `MISS`,
  within 2.5 s of our clock. No rule reads the header. GeckoTerminal allows a
  cache up to 60 s old (`s-maxage=60`).
- **What is refused:**
  - a quote older than 60 s by our own clock;
  - a quote judged before it was fetched;
  - in a replay, any clock read past the capture's tape.

  A body replayed by the network, or a stale GeckoTerminal answer, is taken as
  current. GeckoTerminal only corroborates, so a stale answer can hide a
  divergence or invent one; it never sets the mark.
- **Open:** whether to refuse a GeckoTerminal answer whose `Date`, less any
  `Age`, is too old against its fetch time. Its limit belongs in
  `config/thresholds.json`, which was outside 1.11's paths. The operator's call.
**Affects:** 1.4, 1.5, 1.11; PLAN §9; `adapters/gecko.py`.
*Decided at 1.11's checkpoint: not checked. See the DECISION below.*

## 2026-09-18 — 1.11: a paused feed and a closed market look alike to the fund, but not to the chain
**What we believed.** 1.3 recorded that a paused feed shows up only as a stale
newest point, and that whether these proxies expose a pause flag was not
probed.

**What the record and the chain say.**
- Chainlink's Robinhood feed page says the token contract exposes
  `oraclePaused()`, and that the feed freezes at its last value while the flag
  is true. The workflow is to pause the oracle, stage the multiplier, then
  unpause.
- The mainnet implementation `0xb354…5ae2` dispatches `oraclePaused()`,
  `pauseOracle()` and `unpauseOracle()`. The feed proxies revert on both
  `paused()` and `oraclePaused()`.
- At block 66841212, Sat 05:43Z inside the closed session, all 35 feed-bearing
  tokens answered `oraclePaused()` false. A selector no contract has reverted,
  so that answer is real: the weekend silence is the closed market.

**What the fund does.** It reads only `latestRoundData`.
- A feed paused in an open session is judged fresh for 25 h of open-session
  time.
- One paused from Friday afternoon stays fresh until Monday about 20:00Z.
- A pause shorter than that is never seen. A pause is when the multiplier is
  being changed, so that is the window in which the mark is most in doubt.

**Open:** reading `oraclePaused()` at the pinned block and refusing the mark
while it is true. That touches the reader, the snapshot's inputs, its rule
order and schema, and `run/snapshot.py`, which was outside 1.11's paths. No
paused answer has been observed, so none could be recorded as a case. The
operator's call.
**Affects:** 1.3, 1.6, 1.8 (a held asset's value), 1.11; PLAN §9; F0.4.4.
*Built at 1.11's checkpoint: see the last entry below.*

## 2026-09-18 — DECISION: GeckoTerminal's `Date` header is not checked
*The operator's, at 1.11's checkpoint.* No offchain body carries a source time,
and GeckoTerminal's HTTP `Date` is the only time it states. It stays unread.
- **Why.** GeckoTerminal only corroborates. It never sets a mark, a size or a
  price paid.
- **The exposure, both ways.** A stale answer that invents a divergence vetoes a
  trade in an open session, which fails closed, or records a false finding in a
  closed one. A stale answer that hides a divergence, in an open session and
  while the Chainlink mark is wrong at the same moment, lets through a trade the
  veto would have stopped. That is the one direction that fails open. The
  operator's reasoning, a finding rather than a trade, holds for the closed
  session and for an invented divergence. PLAN §13 states both.
- **Measured:** four answers, all edge-cache misses within 2.5 s of our clock.
  GeckoTerminal allows a 60 s cache.
**Affects:** 1.4, 3.4 (the veto), PLAN §13.

## 2026-09-18 — DECISION: the closed session is re-derived on Monday 9 November 2026
*The operator's, at 1.11's checkpoint:* re-derive after the first weekend on US
standard time. The date given was "Monday 3 November". 3 November 2026 is a
Tuesday, and the recorded date is Monday 9 November, for the decision's own
reason:
- US clocks go back on Sunday 1 November.
- If the feeds follow New York time, Friday's 20:00 close lands at Sat 01:00Z
  first on Saturday 7 November, inside the span, which starts at Sat 00:05Z.
- A re-derivation on Monday 2 November would see no such round and propose the
  same span.

Until 9 November, if the prediction holds, every equity price is undetermined
from Sat 7 Nov 00:05Z to Monday's first round. That weekend fails closed. The
prediction is not a measurement. The date is where it will be seen: in
`CLAUDE.md`, in `config/sessions.json` (`_rederive_on`) and in PLAN §13.
**Affects:** `config/sessions.json`, PLAN §13, every weekend cycle from 7 November.

## 2026-09-18 — 1.11's checkpoint: a paused feed is refused at its own rule, and the committed capture could not be rebuilt
*The operator's change.* Every stock token's `oraclePaused()` is read at the
pinned block, and a true flag makes the asset `no_mark` at rule `paused`.
- **Ordering.** The pause is judged before freshness, because a paused feed is
  often stale too, and the pause says why it is silent.
- **Unknown blocks.** A flag that reverts, is not a bool, cannot be reached, or
  was never read for a stock is undetermined, and blocks.
- **The document.** The snapshot's `mark` carries `unpaused`, and the schema is
  `/4`.
- **Checked.** Eight breaks, each caught by a test.

**What we believed.** The brief said the committed fixture would need
rebuilding, as the capture-hash change did. It could not be rebuilt. That
change moved only how the snapshot was built from the same answers. This one
asks the chain a new question, and the capture never recorded an answer to it,
so its replay stops with `ReplayMiss` at the pause read. It must not guess.

**What we did.**
- **A new capture,** `66852293-253315c0e691`, taken at Sat 06:01Z inside the
  closed session by the committed code. It was checked for every declared
  credential value, and it replays byte for byte.
- **1.9's capture is retired** to `fixtures/retired/`, not deleted. It replays
  at `ee9077c`. The operator had called it the only weekend evidence; the new
  capture is a weekend capture too.
- **A retried 429 is kept.** The new capture holds one RPC 429 that was retried
  to a 200. The replay test had assumed every exchange was a 200, which was
  true of the old capture only.

**Affects:** 1.3, 1.6, 1.9 (fixtures), the demo's fixture; `fixtures/README.md`.

## 2026-09-19 — DECISION: from Phase 2, every unit is built at its minimal version
*The operator's, after the Phase 1 gate, with the deadline about 16 hours away.*
The plan was written for a fund that runs unattended with real capital, and
Phases 0 and 1 were built that way. From 2.1 on, each unit is built at the
minimal version `planning/SIMPLIFICATION.md` gives it. Its full version is
recorded there so it can be built later.
- **Nothing is deleted.** The components, flow and boundaries stay, and so does
  the phase and unit order. What shrinks is depth:
  - scope narrows to the main path;
  - verification covers the main path only;
  - output is the few lines that carry the claim;
  - unlikely edge cases are recorded, not handled.
- **The exception.** Keys, signing and spend authority keep their guard. What
  goes is the ceremony around a guarantee, such as the mandate's hash and
  replay, never the guarantee itself.
- **Ten units are equal,** because a reduced version would be a different
  thing: 3.7, 4.2, 4.3, 4.7, 4.12, 5.2, 5.4, 7.4, 7.5 and 8.2.
- **Not adopted:** SIMPLIFICATION's five-stage build order. It was a second map
  of the same units. The work follows the unit order, and that section is marked
  superseded.
- **Stops, as the approved unit rows set them:** 3.8, 5.4, 6.6, 7.5 and 8.5.
  2.1's stop, approving the report format, was spent on this approval, and 2.1's
  work is still to do. Every other ▶ is shown, not stopped.

**What it contradicts, marked in place rather than reconciled:**
- **The 2026-09-18 DECISION that 3.4 sweeps the three named exceptions into
  `gates.py`.** Minimal 3.4 calls them from there instead, so they outlive 3.4
  (PLAN §2 invariant 4, CODEBASE §3). The sweep is 3.4's full version.
- **Work the approved rows put in a stage that no longer exists.** In unit
  order:
  - 3.7 builds the signer, and 4.12 moves it into the treasurer's process;
  - 4.11 checks positions and value against its fixture, and 6.1 adds the four
    lines;
  - **the page arrives at 7.6, after four of the five stops.** So 3.8, 5.4, 6.6
    and 7.5 are shown as files and terminal output. Building 7.6 earlier would
    move one unit, and that is the operator's call.

**Affects:** every unit from 2.1; PLAN §2 and §8; ROADMAP; PHASE-0-1; CLAUDE.md.

## 2026-09-19 — DECISION: reports speak in two vocabularies, direction and condition
The one recorded execution-quality report, the second call of 1.8's caching
test, was asked for buy, hold or sell. It answered `NO_CALL` on all 35 assets,
because that vocabulary has no answer for "what does trading cost"
(`probes/out/analyst_cost_cache.json`, gitignored, local only). Under one
vocabulary, half the seats could only abstain.
- **Direction seats,** `price-trend` and `cross-asset-macro`: buy, hold or sell,
  with a confidence.
- **Condition seats,** `execution-quality` and `price-integrity`: proceed or
  caution, with a confidence.
- **The aggregator** combines them as direction × (1 − caution), as
  "The report format" in SIMPLIFICATION.md sets out.

The key values are snapshot field paths that code resolves, so the model never
writes the key numbers.
**Affects:** 2.1, 2.2, 2.3, 3.1; `config/analysts.json`.

## 2026-09-19 — DECISION: the fourth seat becomes price integrity
The snapshot gives `fundamentals-calendar` nothing but names and ISINs, so it
would reason from model memory, which no decision record can cite (gate §5). It
becomes `price-integrity`: does this asset's price hold up today? It compares
three sources that the snapshot already carries and no other seat compares:
- the Chainlink mark;
- GeckoTerminal's price;
- the venue's price inside the $25 quote.

**Given up:** nobody reasons about the companies themselves, so the fund claims
no fundamental research (PLAN §13).

**Not yet in config.** `config/analysts.json` still names
`fundamentals-calendar`. It is outside this pass's paths and changes with 2.1.
**Affects:** 2.1, 2.3, 3.8; `config/analysts.json`; PLAN §11 and §13.

## 2026-09-19 — DECISION: five agent wallets, from `bankr login siwe`, unverified
Each analyst and the risk agent gets its own Bankr account and wallet, created
with `bankr login siwe --private-key` from a locally generated key. Five local
keys replace five email sign-ups; the docs describe this path as built for
headless agents.
- **Each key's permissions:** read-only, LLM gateway on, Agent API off.
- **What the agents do:** exist, carry an address, and pay for their own
  inference. They never transact or sign.
- **The treasurer** keeps the fund's wallet.

**Unverified.** The path must be shown to work before Phase 2 depends on it. If
it does not work, that is a finding. **Falling back to one shared wallet is
ruled out,** because it collapses what is being demonstrated.

**What the installed CLI says** (0.3.37, `bankr login siwe --help`; documented,
not measured):
- read-only is the default, and `--read-write` turns it off;
- **the Agent API and the Token Launch API are on by default,** so
  `--no-agent-api` and `--no-token-launch` must be passed;
- **no LLM gateway option is listed,** so how an agent key gets gateway access
  is unknown;
- `--allowed-ips` and `--allowed-recipients` exist.

**Also unknown:**
- whether the account's wallet is the SIWE key's own address or a new custodial
  one;
- whether credits can be bought in it;
- whether a login replaces the CLI's current session, which is the fund's. This
  is inferred, not observed. Check it before the first run.

**The private key is setup material, not an agent credential.** It signs the
SIWE message. It never enters an agent process or the repository, and the agent
process holds only its read-only API key. If the wallet turns out to be that
key's own address, the key controls whatever the wallet holds.
**Affects:** 2.4, 2.5, 3.5, 4.12, 6.3; PLAN §6 and §13; `credentials.py` and
`.env.example`, once verified.

## 2026-09-19 — DECISION: the live ETH↔USDG trade is a demonstration of the money path
Nothing on record said what drives the live leg. It is labelled as what it is: a
demonstration of the money path that no analyst chose. No decision is
manufactured to justify it. It passes the same gates, risk agent, signature and
treasurer as any other order. SIMPLIFICATION.md proposes mechanics for it: one
small order in each cycle that trades, alternating direction. Those mechanics
are proposed, not decided.
**Affects:** 3.3, 5.2, 5.7; PLAN §13; the demo story.

## 2026-09-19 — DECISION: the endpoint sells the full record, and a preview is public
PLAN §5 put the published record on a public path that the page reads too. As
written, anyone could read in full what x402 sells.
- **Public preview:** the basket, the weights, the verdict, and that a veto
  fired.
- **Paid:** the full record, with every analyst report and its reasoning.

**Open:** how the handler holds the full record without it being public
elsewhere. The two options are bundling it into each deploy or a private URL
only the handler knows. Neither is measured: 0.7d proved that deploys work, not
how long they take.

**Open, as a consequence of the decision:** the preview as decided names
neither the decision id nor the hashes and signature.
- 7.2 serves by id, so a buyer has to learn the id somewhere.
- Without the hashes, a buyer cannot check that what they bought matches what
  they saw.

Neither is added here. Both are the operator's call.

**Contradicts,** marked in place: PLAN §1 ("shown on a public page"), §5, and
7.7's "latest decision and reasoning".
**Affects:** 7.1, 7.2, 7.6, 7.7; PLAN §1, §5, §8 and §11.

## 2026-09-19 — DECISION: execution before the sale, in the existing unit order
SIMPLIFICATION.md recommended building the sale before execution. That is not
adopted, for two reasons:
- the judging criteria weight onchain potential;
- probe 0.7e has already proven a sale through a standard client.

The unit order already puts Phases 4 and 5 before Phase 7, so nothing moves.
**Affects:** the order of work; SIMPLIFICATION.md's build order, superseded.

## 2026-09-19 — The six judging criteria, supplied
PLAN 8.6 names six judging criteria that were never in the repository. The
operator supplied them:
- product;
- founder-market fit;
- execution;
- originality;
- onchain potential;
- token design;
- and bonus consideration for projects built around onchain equities.

They are in `planning/JUDGING-CRITERIA.md`.

**A gap they expose: token design.** PLAN §12 leaves "do we launch a token"
open, and no unit covers it. Recorded, not resolved.
**Affects:** 8.6; PLAN §12.

## 2026-09-19 — DECISION: 2.1 is a stop, contradicting what the pivot recorded
*The operator's, in the Phase 2 planning brief.* 2.1 is a hand-written example
report that the operator reads and approves before any code. It is a stop.

**What it contradicts.** The pivot pass recorded 2.1's stop as spent on the
analysis approval, in four places: `CLAUDE.md` ("Stop only at 3.8, 5.4, 6.6,
7.5 and 8.5"), PLAN §8, ROADMAP, and SIMPLIFICATION's 2.1 row. That reading
came from SIMPLIFICATION's own row, which said "approving this document
approves the format". The operator's approval covered the vocabularies, not a
format.

**The stops from Phase 2 are 2.1, 3.8, 5.4, 6.6, 7.5 and 8.5.**

**Owed.** The four files are outside the Phase 2 planning pass's paths. Until
they are fixed, a session following `CLAUDE.md` would not stop at 2.1.
`planning/PHASE-2.md` and the LOGS state note say so.
**Affects:** 2.1; `CLAUDE.md`; PLAN §8; ROADMAP; SIMPLIFICATION.md.

## 2026-09-19 — SIWE login, read from the CLI's source: no gateway field, a new wallet, and it overwrites the fund's session
Read-only, from the installed `@bankr/cli` 0.3.37 (`dist/commands/login.js`,
`dist/lib/config.js`). Documented by code, not measured.
- **What the SIWE request sends:**
  - `readOnly`, true unless `--read-write`;
  - `walletApiEnabled`, true;
  - `tokenLaunchApiEnabled`, true;
  - `agentApiEnabled`, only with `--no-agent-api`;
  - IP and recipient allowlists.
- **It never sends `llmGatewayEnabled`.** The email flow sends it with `--llm`.
  A SIWE key's gateway access is the server's default, which is unknown.
- **The server "creates a wallet"** and returns `walletAddress` apart from the
  signer's address. The agent wallet is inferred to be a new Bankr wallet.
- **The key is written to `~/.bankr/config.json`** unless `--config` or
  `BANKR_CONFIG` says otherwise. An agent login would replace the fund's CLI
  session.
- **`--private-key` on the command line** lands in shell history and the
  process list.
- **No command changes a key's permissions later.** `bankr llm credits add`
  buys credits "from your wallet", which is a write a read-only key may be
  refused.
- **The SIWE private key can mint a read-write key for its account,** so it is
  spend authority over that agent's wallet, and is kept like `SIGNING_KEY`.

What this changes: 2.0 is planned to settle the gateway question before any unit
assumes five wallets (`planning/PHASE-2.md`).
**Affects:** 2.0, 2.4, 2.5; the SIWE DECISION above.

## 2026-09-19 — `config.load()` puts the whole `.env` in the caller's environment
**What `credentials.py` says:** "the analyst role cannot load execution or
signing secrets even on a single-host development machine". That is true of the
`Config` object `load()` returns.

**What the code does:** `load()` first calls `load_environment()`, which merges
every `.env` value into `os.environ`. So a process of any role holds
`BANKR_KEY_EXEC` and `SIGNING_KEY` in its environment. Two things already
acknowledge this:
- `_refuse_leaked_spend_authority`'s docstring names this single-host case;
- 4.12's deployed split is meant to end it.

**What it changes.** For Phase 2's analyst processes it is a design constraint.
The runner builds each child's environment from nothing, and children never read
`.env` (`planning/PHASE-2.md` 2.4). The file itself stays readable on one
machine until 4.12 splits it.
**Affects:** 2.4, 4.12; PLAN §2 invariant 1.

## 2026-09-19 — 2.0: SIWE made an agent account with its own address, a read-only key and the Agent API off, but no gateway access
**What we believed.** The five-wallet decision rested on `bankr login siwe`
producing accounts that are read-only, have the Agent API off, and have the LLM
gateway on. The CLI's help and source already doubted the gateway: the SIWE
request never asks for it.

**What one account measured** (`research/findings.md` §2.0; nothing spent; the
fund's CLI session untouched):
- **Its own address.** `0x42a9…3d27` is a new Bankr wallet, not the signer's
  address.
- **It cannot transact.** A signature and a swap were each refused 403 "Read-only
  API key", with the permission named. A signature needs no balance, so the
  empty wallet is not the reason.
- **The Agent API is off.** `/agent/prompt` was refused 403, with the toggle
  named.
- **The gateway is off.** Every gateway call drew 403, "does not have LLM
  Gateway access enabled". That is `BANKR_KEY_READ`'s body exactly.
- **It cannot buy credits either.** The top-up was refused at the gateway toggle
  first. So read-only's own effect on buying credits is unresolved.
- **An aside:** `POST /agent/sign`, which `research/bankr-claude.md` lists, is a
  404.

**What it changes.** The five-wallet plan cannot proceed as designed through
SIWE alone. The options are recorded, not chosen:
- (a) email sign-ups with `--llm`, untested;
- (b) enabling the gateway in the dashboard, which is unknown for a SIWE
  account;
- (c) own wallets with inference on the fund's key. It is available now, and
  gives up "each agent pays for its own inference".

One shared wallet stays ruled out. 2.4's credential rows and every live Phase 2
run wait on the operator.
**Affects:** 2.0, 2.4, 2.5, 2.6, 3.5, 6.3; PLAN §6, §8 and §13; the SIWE DECISION
above.

## 2026-09-19 — The fund's keys, measured: `BANKR_LLM_KEY` is not read-only, and the Agent API is on for all three
**Why this was run.** The operator asked which `.env` key is which, to match the
dashboard. `probes/keymap.py` is read-only and signs nothing:
- the wallet, from `/wallet/me`;
- the gateway, from `/v1/credits`;
- the Agent API, from `/agent/profile`, a read. It is calibrated against the
  2.0 key, whose Agent API was measured off, and which draws 403 "Agent API
  access not enabled" here too;
- read-only, from `/wallet/sign` with **no message**. A read-only key is
  refused by name before the body is read. A key that may sign fails
  validation instead.

A never-issued key drew 401 everywhere.

| Key | Wallet | Read-only | LLM gateway | Agent API |
|---|---|---|---|---|
| `BANKR_KEY_READ` | `0x93fa…a3da` | yes (403 "Read-only API key") | off | **on** |
| `BANKR_KEY_EXEC` | `0x93fa…a3da` | no (400 validation) | **on** | **on** |
| `BANKR_LLM_KEY` | `0x93fa…a3da` | **no** (400 validation) | on | **on** |

Token launch is not measured: no read is gated by it, and a deploy request was
not sent.

**What we believed** (PLAN §6, `credentials.py`, LESSONS 2026-09-17):
- `BANKR_LLM_KEY` is "Read Only ON … Cannot transact", held by the analyst
  role;
- the Agent API is off on both Bankr keys.

**What the record actually held.** Neither was ever measured. F0.2.2 said
outright that a write with `BANKR_LLM_KEY` was not tested. F0.2.5 said the
Agent API could not be read, and the decision was asserted in code instead: no
call to `/agent/*`.

**What it means:**
- **Invariant 1 ("no key the analyst role can load may transact") is false
  as measured today.** The role can load `BANKR_LLM_KEY`, which passes the
  read-only gate on the Wallet API and has the Agent API on.
- **No current code misuses it.** `src/` never calls a write with it, and the
  boundary tests hold. The exposure is the key's own capability.
- **2.0's option (c) is unsafe as the keys stand.** It would hand
  `BANKR_LLM_KEY` to every analyst process.
- **The spend authority itself is still one account**, as §13 already states.
- **The gateway balance reads $15.791107.** Credits were bought since the
  $0.937148 on record.

**Not reconciled here.** Key settings are the operator's, and this pass
changed none. Marked in PLAN §6. `credentials.py`'s scope text and
`can_transact=False` are owed, outside this pass's paths.

**Confidence:**
- read-only is measured by contrast. The identical request was refused by name
  for two read-only keys and passed that gate for these two; a signature was
  never attempted;
- the Agent API is measured through a read, calibrated against a key known to
  be off.
**Affects:** invariant 1; PLAN §6 and §13; `credentials.py`; 2.0's option (c);
2.4; 4.12.

## 2026-09-19 — DECISION: a brief file per seat, and costs checked against a settled window rather than balance deltas
*The operator's, in the batch brief for 2.2 to 2.5.* Two changes to the approved
minimal versions:
- **2.3: one versioned brief file per seat,** `briefs/<seat>.v1.md`, plus a
  shared output contract. The earlier minimal version had one file for all
  seats. Each seat's question comes from `config/analysts.json` and is written
  in at render time, so the file and the config cannot drift apart.
- **2.5: never a before-and-after delta.** Each call's cost comes from its own
  usage block, and every figure is labelled an estimate. The aggregate is
  checked against a settled `/v1/usage` window.
  - The earlier minimal version read each agent's `/v1/credits` before and
    after its call. The operator ruled deltas out because `/v1/usage` was seen
    going backwards around single calls (F0.9.2).
  - **What it gives up:** the per-agent balance as evidence that each agent
    paid. That now rests on each call being made with its agent's key.
  - **It moves 6.3 too,** whose minimal version totalled each agent from its
    own balance.
**Affects:** 2.3, 2.5, 6.3; ROADMAP and SIMPLIFICATION rows; `planning/PHASE-2.md`.

## 2026-09-19 — 2.2–2.5: what building against the record found
- **The approved examples caught a wrong rule, in the validator, not the
  report.** AMZN's 28 August close is exactly 266.085, and the approved report
  writes 266.08. Strict round-half-up says 266.09 and refused it. USO's 161.405,
  written 161.41, rounds the other way.
  - **Now:** a figure is the field when the field lies within half a unit of
    the figure's last digit, the midpoint included.
  - **The check still has teeth.** 266.07 is refused, and so is 569.42 against
    559.42.
- **A gateway reply carries its own request id** (`chatcmpl-…`, recorded at
  1.7), though `/v1/usage` has none (F0.6.4). Each call's record keeps it. If the
  provider ever gives per-request rows, the calls can be matched.
- **The reply also carries cost fields nothing explains:**
  `usage.buyer_cost_micro` (115,302 for a call that cost $0.461206) and
  `cost.diem` (0.691809, beside `cost.usd: 0`). They are kept raw and not used.
  The listed price reproduces the balance to the last digit (1.8a); these do
  not.
- **`BANKR_LLM_KEY` was still not read-only, with the Agent API on,** when this
  batch began (`probes/keymap.py`). The whole batch was built and proven offline
  against a fake gateway. Nothing ran live, and the runner has no live entry
  point yet.
**Affects:** 2.2's figure rule; 2.5; 2.6 and every live run.

## 2026-09-19 — The keys after the operator's fix, measured: the analysts' key cannot reach a signing surface
**What we believed.** At 2.1, `BANKR_LLM_KEY` measured not read-only with the
Agent API on, and the analysts would hold it. The operator then set it to
gateway on, read-only on, Agent API off and Wallet API off. `BANKR_KEY_READ`
became read-only with everything else off. `BANKR_KEY_EXEC` became Wallet API
on, read-only off, everything else off.

**What `probes/keymap.py` measured before 2.6 ran:**
- `BANKR_LLM_KEY`:
  - `/wallet/sign` refused 403 "Wallet API access not enabled";
  - `/agent/profile` refused 403 "Agent API access not enabled";
  - the gateway answers 200.
- `BANKR_KEY_READ`: read-only, gateway off, Agent API off.
- `BANKR_KEY_EXEC`: not read-only as labelled, gateway off, Agent API off.

Every setting matches the dashboard's word this time.

**What it means.** Invariant 1 holds for the analysts' key as far as it can be
measured: it is refused by name on both surfaces that can sign or transact.
**Still not measurable:**
- the read-only toggle on `BANKR_LLM_KEY`, because the Wallet API refuses
  first;
- token launch on every key, because no read is gated by it.
**Affects:** invariant 1; PLAN §6; 2.4 and 2.6; 2.0's option (c), now safe as the
keys stand.

## 2026-09-19 — 2.6: the first real report, refused on its first line and on a validator rule that was wrong
**What we believed.** A real model given the approved brief would either pass
2.2 or be caught fabricating.

**What one call measured** (`research/findings.md` §2.6; $0.273156; 78.6 s):
- **It did not copy the first line.** Where the brief gave the unassigned agent
  `0x…`, it wrote the fund's wallet, the only address in the snapshot. A
  placeholder shaped like an elided address was read as one to fill in.
- **2.2's bps rule refused five correct figures.** They were divergences the
  model computed and cited, such as `136bps`. The approved rule says computed
  figures are not checked, but the code checked any "bps" number against a
  `_bps` field. With the rule corrected in a scratch copy, the only refusal
  left is the header.
- **No figure was fabricated.** One computed clause was imprecise, and two
  prose claims were unsupported ("venue AMM", SGOV "likely thin"). The
  validator does not read prose, by design.
- **The reply states its own cost per request.** `usage.cost` is 0.273156,
  equal to our estimate. It also counts reasoning tokens: 5,858 of 7,628, or
  77%.

**The judgement.** A real view, reached mechanically. It follows the brief's own
method to the same five calls the hand-written example made, and it is thinner
than that example.

**Not changed, by instruction.** The brief and the validator stay as they were
at the call.

**Owed:**
- the bps rule, with its test;
- a placeholder that cannot be read as an address, or real agent addresses;
- tests for the runner's `main()`;
- the settled usage cross-check.
**Affects:** 2.2, 2.3, 2.5, 2.0's choice, the runner's `UNASSIGNED_AGENT`.

## 2026-09-19 — After 2.6: the bps rule loosened, the placeholder made a word, and no rule added
*The operator's instruction: fewer refusals, not more, while the shape is still
being found.* Two of the 2.6 reply's six refusals were ours to fix.
- **The bps rule.** A bps figure is now treated like a percentage: computed and
  cited, not checked. The exception is a line that cites a field itself stored
  in bps (`quote.swap_impact_bps`, `corroboration.divergence_bps`); then the
  figure names that field and is checked against it.
  - The recorded reply's five computed divergences now pass. Its cited
    `-450.32bps` is still checked, and altered to −440.32 it is refused.
- **The placeholder.** A seat with no wallet is now written `unassigned`, which
  nothing can read as an elided address. The approved examples' `0x…` is
  untouched, because the format is approved; only the value the runner assigns
  changed.
- **The result, on the same recorded reply with no new call.** Its one remaining
  refusal is the header, where it filled the old placeholder with the fund's
  wallet. Put back only that token and it is accepted.

**One strictness kept, and stated.** A plain decimal on a line that cites single
fields is still read as naming one of them. A computed difference written in
dollars on such a line, such as a gap of 7.51 between a mark and a venue, would
still be refused. Loosening that too would also let a fabricated field value
through. None has been seen, and it is the operator's call if one is.

**Also:**
- `python -m fund.agents.show` prints a stored report exactly as written;
- every attempt now keeps its reply whole;
- the runner's live entry point has its tests.
**Affects:** 2.2, 2.3 (the value its first line carries), 2.4, 2.6.

## 2026-09-19 — 2.6 finished: three more seats, one call each, and 2.7's store
*The operator's instruction: one call per seat, the same snapshot, no brief
iterated. A poor report is a finding.* Sent at 15:58:33Z with `BANKR_LLM_KEY`
measured first, as before (`research/findings.md` §2.6, continued).
- **Price-trend was refused for errors that are the model's.** It gave META a
  39-digit address invented after the first 8. It gave GME the address of its
  Chainlink feed (`mark.feed_proxy`), not the token. It dated GME's 18th close
  the 17th. The validator caught all three. Its other figures, including
  computed ones, check out.
  - **The lesson.** An entry holding two addresses invites the wrong one.
    Identity by address (PLAN §2 invariant 8) held because the validator
    checks it, not because the model gets it right.
- **Its NVDA call is the brief's own example.** `analyst.v1.md` carries the
  approved NVDA call from *this* capture, labelled "From an earlier snapshot".
  The model repeated its range, its reasoning and its "Wrong if". On this
  capture that call cannot be judged, and the label is false. The brief is
  2.3's, and it is not changed here.
- **Cross-asset-macro got no reply.** The gateway answered HTTP 504 after
  113.3 s, which suggests an upstream limit well under our 600 s. Not retried:
  a gateway refusal never is, and the rule was one call. Whether it was billed
  waits on the settled window.
- **Execution-quality was accepted,** the first reply to pass unchanged: no
  fee, small impact, and caution on MSTR.
- **Both condition seats caution MSTR on the same 132 bps gap,** one as a stale
  mark and one as a buyer's cost. The aggregator's largest-caution rule keeps
  it from counting twice. Otherwise the three reports answer different
  questions. The seat likeliest to repeat price-trend is the one that timed
  out.
- **2.7 built at its minimal version.** A write-once store: one file per
  report, named by the sha256 of its bytes. It is verified on every read and
  never rewritten. Refused replies are kept with their refusals, so the record
  holds every reply that arrived. The runner stores each one and puts its id
  on the seat's result.
  - **Not built:** a query layer, SQLite and any index.
  - **A mistake caught on the way:** an entry-point test wrote a fake record
    into the real live store. It was removed, and the test now writes to a
    temporary directory.

**Spent:** $0.522736 by the replies' own figures, plus the 504's unknown.
**Owed:**
- the settled `/v1/usage` cross-check, for the 15:39Z and 15:58Z calls both;
- one cross-asset-macro call, if the operator authorises it;
- a true label on, or a different, brief example.
**Affects:** 2.3 (the example), 2.4 (the gateway limit against the 600 s
timeout), 2.7, 3.x (the aggregator meets MSTR twice).

## 2026-09-19 — DECISIONS for Phase 3, in the operator's batch brief
*The operator's, before 3.1 to 3.7 were built as one offline pass.*
- **A target starts at the weight held.** A buy raises it, a sell cuts it, and
  hold and silence leave it where it is; a new position comes only from a buy.
  - **What it contradicts:** SIMPLIFICATION's 3.1 row, where positive scores
    became weights and everything else went to cash. That would have given a
    held asset on hold a weight of 0, and the planner would have sold it.
  - It does not bite on cycle one, because paper holdings start empty. It
    bites from cycle two, including 8.3's unattended cycles.
- **Config set, all provisional,** as SIMPLIFICATION proposed:
  - quorum 3;
  - maximum weight 0.25;
  - cash floor $20;
  - minimum order $1;
  - turnover 10,000 bps.

  The confidence mapping was left to the build: low 0.25, medium 0.5, high
  0.75. It is shown at 3.2, to be tuned after a real cycle.
- **The mandate, populated provisionally.** It holds the capture's 20
  tradeable assets, with placeholders in the approval fields. Otherwise every
  order would fail the mandate gate and bury 3.8's divergence story. 4.1
  replaces all of it.
- **The live leg leaves 3.3.** It is Phase 5's, not the planner's. This
  contradicts SIMPLIFICATION's 3.3 row.
- **3.6 before 3.5.** The risk call needs the budget checked before it is sent.
  This departs from the unit order.
- **Three files outside the batch's paths, approved when asked:**
  - `run/decide.py`, the one command;
  - `briefs/risk.v1.md`, because prompts are files (CODEBASE §6);
  - the `cryptography` pin in `pyproject.toml`.

Folded into SIMPLIFICATION's rows and config table, ROADMAP's Phase 3 table and
PLAN §8.
**Affects:** 3.1, 3.3, 3.5, 3.6, 4.1, 5.x, 8.3; `config/thresholds.json`,
`config/analysts.json`, `config/mandate.json`.

## 2026-09-19 — Phase 3 built offline: what building it found
- **`core/` cannot call the three older comparisons.** It cannot import
  `adapters/` (CODEBASE §3), and staleness and quote age live there. So
  `gates.py` reads the verdicts they produced:
  - the snapshot's status holds staleness and the divergence tier;
  - each fresh quote is judged by `bankr_quote.tradeability` where it is
    fetched, and the plan records that verdict.

  Each limit is still defined once. "In one module" still does not hold, as
  PLAN §2 invariant 4 already says.
- **The one-signer rule shaped the command.** Nothing outside `treasurer/`
  may import `sign.py`. So `run/decide.py` runs the signer as its own process,
  from an empty environment, and that process reads `SIGNING_KEY` itself. The
  command never holds the key. This is a first step toward 4.12's separate
  treasurer, not the whole of it.
- **Limits the aggregator and the planner apply are defined in `gates.py`.**
  These are the position cap, the cash floor, quorum, and the order split.
  The boundary test now counts every `gates.Limits` field as a threshold, and
  a comparison planted in `plan.py` was refused.
  - `min_order_usd` is decimal text, not the integer 1. As an integer, the test
    would read every `x < 1` in the code as that threshold.
- **Two defects, found by tests before any use:**
  - rounding every change toward zero left a millionth of a position that had
    been cut to zero, so it was never fully sold. Fixed: a cut to zero is
    exact;
  - the planner's guard against selling more than is held was never reached
    through the aggregator, and breaking it failed no test. A test that gives
    the planner a proposal made on a different book now catches it.
- **The weights, judged at 3.2.** The four approved reports give:
  - META 12.5%;
  - AMD, INTC and USO 6.25% each;
  - 68.75% cash.

  That is a small, cautious trend tilt a person could hold over a closed
  weekend. But three of the four positions are price-trend's calls with
  haircuts, and much of the cash comes from the confidence mapping, not from a
  view. Nothing weighs co-movement: AMD and INTC are two positions, though
  cross-asset-macro's report puts their correlation at 0.78. AMD,
  price-trend's strongest call, ends level with INTC, its weakest, because
  price-integrity's caution halves it.
- **No real model has seen `risk.v1.md`.** The reply format, the veto
  judgement and the budget's margin are proven on scripted replies only. The
  offline bundle for four orders is about 32,400 tokens, including the 12,000
  reserved for the reply.
- **The record carries no call timings,** so the same recorded inputs rebuild
  the same bytes. Two offline runs gave the same decision id. 3.9 will make
  that its test.

**Affects:** 3.4, 3.8, 3.9, 4.4, 4.12; PLAN §2 invariant 4; the confidence
mapping.

## 2026-09-19 — 3.8: the exit run refused all four seats, so the first real cycle decided nothing
**What we believed.** A real cycle would produce at least three accepted
reports, and the question would be whether risk vetoes. The fixed gates were
expected to pass, and the veto would be risk's judgement on a stale mark.

**What one run measured** (`research/findings.md` §3.8;
`fixtures/cycles/20260919T171351Z/`):
- **Four live calls, one per seat, all replied,** for $1.087706.
  Cross-asset-macro answered in 89 s, with no 504 this time.
- **All four were refused.** No figure was invented. Every refused figure is a
  real value of the capture, but cited under the wrong path:
  - another asset's figure without its symbol, six times in cross-asset-macro;
  - `swap_impact_bps` without `quote.`, five times in execution-quality;
  - a mark dated as a close.
- **Two of the defects are ours:** thousands separators, and brackets read as
  citations. Fixed, they rescue price-integrity alone: one of four.
- **So no quorum,** and the fund's real decision, signed, is no rebalance.
  - No order, so no risk call. No real model has read `risk.v1.md`.
  - No veto.
- **The signed record omits the refused replies.** It says why nothing
  happened, but not which reports were refused or why.

**What it changes.** Nothing was changed, by instruction: no brief was iterated
and no seat re-run. The validator stays as it was at the call. The shared
example was relabelled before the run, as the operator asked, and price-trend
made no NVDA call.

**Owed, each the operator's call:**
- the two validator defects;
- whether a figure cited under the wrong path should be refused, or checked by
  value;
- a citation line in the brief for other assets and full paths. That would be
  a brief change;
- the refused replies in the record;
- another exit run once those are settled.
**Affects:** 2.2, 2.3, 3.7, 3.8, 3.9; the quorum; the exit run.
