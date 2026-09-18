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
