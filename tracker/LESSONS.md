# Lessons

What went wrong, what surprised us, and what changed in the plan as a result.

This is the honest counterpart to [LOGS.md](LOGS.md). LOGS records what was
built; this records where the plan met reality and lost. A build with an empty
lessons file either got very lucky or is not telling you something.

This file is also the authoritative record of plan deltas. Where an entry here
contradicts [PLAN.md](../PLAN.md), [ROADMAP.md](../ROADMAP.md) or
[PHASE-0-1.md](../PHASE-0-1.md), the entry wins and is dated.

## When an entry gets written

- A probe contradicts a claim we had documented as fact.
- A phase or unit changes shape.
- An approach is abandoned.
- A checkpoint sends us back.

Not for ordinary bugs fixed in the normal course of work. Those belong in the
commit history, not here.

## Entry format

```
## YYYY-MM-DD — <short title>
**Context:** what we were doing.
**What happened:** the problem, surprise, or wrong assumption.
**Evidence:** the error, output, or finding.
**Change:** what we changed in the plan, code, or approach.
**Affects:** which phases or units this alters.
```

---

## 2026-09-17 — Operator is in the US; tokenized-stock execution is unavailable
**Context:** Resolving PLAN.md §12's first open question — "Is an eligible
execution operator available?" — which PLAN.md §8 makes the gate on whether
Phase 5 exists.

**What happened:** The operator is US-based. Bankr gates tokenized-stock trades
behind location verification and the US is excluded, so live stock fills are not
reachable for this build. We are not relocating a server to manufacture
eligibility. This was the plan's largest binary unknown and it resolved against
us before a line of code was written.

**Evidence:** `research/bankr-skills.md:300` region, citing Bankr's
`bankr/references/tokenized-stocks.md:73-79`: tokenized-stock trades require
location verification with a 30-day expiry and are unavailable in the US and UK;
a gated swap without a passed check returns `403` over the Wallet API.
`PLAN-technical-review.md` finding 12 anticipated exactly this and required Phase
0 to distinguish pass / fail / unresolved rather than treating a documented `403`
as a completed probe.

**Change:** Three consequences, adopted together.
1. **Stock legs are paper**, sized and priced from real live quotes through the
   same executor interface. Nothing is simulated upstream of execution: the
   snapshot, the quotes, the sizing and the gates are all real.
2. **Real on-chain activity comes from an ungated leg.** Memecoin/USDG swaps on
   4663 require no location verification. The treasurer executes small real
   transactions there, so the order state machine, receipt reconciliation,
   journal and explorer evidence are genuine rather than mocked.
3. **Probe 0.5 still runs**, to capture the exact `403` body and confirm the gate
   empirically. Its expected outcome is now **fail**, not unresolved. A fail is a
   recorded measurement; we do not skip the probe because we predict its answer.

**Affects:** Phase 5 (renamed and rescoped — see the Phase 5 entry below). Probe
0.5's expected verdict. Phase 4's paper executor becomes the permanent path for
stock legs rather than a stepping stone. PLAN.md §13 gains the limitation. The
demo story changes: the credible claim is "real transactions, real reconciliation,
paper stock fills, stated plainly," not "a live stock fund."

---

## 2026-09-17 — Capital and trade size fixed at ~$200 and $25
**Context:** PHASE-0-1.md unit 1.5 requires quotes "at the intended size, not a
token size," and warns that a small quote passing tells you nothing about a real
position. The intended size was undefined, which blocked 1.5, the 0.9 cost model
and every gate threshold denominated in dollars.

**What happened:** No number existed anywhere in the plan. Sizing, the cash
floor, turnover limits and the per-trade caps all depend on it.

**Evidence:** PLAN.md §6 specifies "low platform caps" on `BANKR_KEY_EXEC`
without values. Bankr's documented platform defaults are $500/24h and $500/tx.

**Change:** Capital under management is ~$200. Nominal per-trade size for quoting
is $25. Both sit well inside the platform caps, so the caps are a backstop rather
than a binding constraint, and a single bad cycle cannot exhaust the fund.

**Affects:** 1.5 (quote sizing), 0.9 and later 6.3 (cost per cycle is now a
meaningful fraction of capital and must be shown as such), 3.3 (planner sizing),
3.4 (dollar-denominated gate thresholds), 4.1 (mandate bounds).

---

## 2026-09-17 — Cadence set to daily, plus a manual trigger
**Context:** PLAN.md §12 left cadence open: "frequent enough to look alive, cheap
enough to sustain."

**What happened:** Undefined cadence blocks `config/cadence.json`, the Phase 8
scheduler, and the cost-per-day figure that 0.9 is supposed to produce.

**Evidence:** `research/agent-os.md` §13 on the scheduler:
`senior-unilp-manager/SKILL.md:666-669` — prefer `job_kind="script"` over
`job_kind="agent_turn"`, because an agent turn on a job that is almost always a
no-op costs a model call every tick. At $25 trades on ~$200 of capital, a
high-frequency cadence burns inference budget against trades too small to justify
it.

**Change:** Daily scheduled cycle, plus a manual "run cycle now" trigger for
demos. The manual trigger goes through the identical code path as the scheduled
one — it is a trigger, not a demo mode.

**Affects:** `config/cadence.json`, 8.1 (scheduler), 8.3 (unattended run
checkpoint now means several daily cycles, so the drill compresses time rather
than waiting days), 0.9 (cost-per-day multiplies out from one cycle per day).

---

## 2026-09-17 — x402 price set at $0.05 per decision record
**Context:** ROADMAP.md checkpoint 0.7 asks what a fair price is; PLAN.md §8 unit
0.9 multiplies analyst cost out into "a per-request price for the endpoint."

**What happened:** No price existed, so revenue could not be modelled and the
0.7 checkpoint had no proposal to judge against.

**Evidence:** PLAN.md §11 fixes the settlement rail: USDC on Base, because the
standard client's network enum excludes 4663
(`research/x402-cli-example.md` §7, "USDG on chain 4663 — a definitive no").

**Change:** $0.05 per decision record, priced in USDC on Base. Subject to
revision at checkpoint 0.7 once the real round-trip timing and the real
per-cycle inference cost from 0.9 are known — this is a starting number, not a
finding.

**Affects:** 0.7 (the checkpoint now judges a concrete price), 7.2–7.4, 6.1
(revenue line).

---

## 2026-09-17 — Roster fixed at four analysts, with scopes partitioned in config
**Context:** The single largest under-specification in the plan: nothing stated
how many analysts there are, what they do, or how they differ. Phase 2 units 2.3
and 2.4 reference "scope boundaries" and "bounded width" without a roster.

**What happened:** The reports are the product, and the product had no defined
shape. Left undefined until Phase 2, it would have been decided under time
pressure at the 2.1 checkpoint.

**Evidence:** PLAN.md §8 Phase 2 exit says "N analysts produce N valid reports"
with N unbound. `research/agent-os.md` §13 flags the fragile pattern to avoid:
`max_children_per_session` defaults to `None`, so fan-out width is unbounded
unless configured — "for our N analysts that must be an explicit number."
`research/miroshark.md` §9 makes the complementary point: its personas divide
work by *instruction*, and divergence between them is unbounded by design.

**Change:** **Four analysts, one risk agent, one treasurer.** Risk and treasurer
are separate roles, not analysts: risk reads all four full reports plus the sized
plan and applies `core/gates.py`; the treasurer is the sole writer.

Scopes are **disjoint by construction, not by instruction**. Our universe is
known in advance, so the partition is declared deterministically in config rather
than decomposed by a lead model at runtime. Each brief carries an objective, its
exact asset scope, the output schema, source boundaries, and effort guidance,
following the delegation discipline in the Anthropic multi-agent write-up.

Proposed scopes, **to be confirmed at the 2.1 checkpoint**:

| Analyst | Scope |
|---|---|
| price/trend | recent price action and trend, for its assigned assets |
| fundamentals/calendar | the underlying equity's situation and known events |
| cross-asset/macro | correlations and regime, across the whole universe |
| execution quality | quote age, impact, spread, tradeability, per asset |

Two of the four (cross-asset/macro, execution quality) are universe-wide by
nature rather than asset-partitioned, so "disjoint" means disjoint in *question*,
not always in asset set. That tension is real and 2.1 is where it gets settled.

**Affects:** 2.1 (the checkpoint now has a concrete roster to approve or reject),
2.3 (brief format must carry an explicit scope field), 2.4 (fan-out width is 4),
0.9 and 6.3 (cycle cost is 4 analyst calls plus 1 risk call plus retries), 3.1
(quorum is defined against 4), 6.4 and 6.7 (attribution across a fixed roster).

---

## 2026-09-17 — Repo layout moved to root-level docs and `src/fund/`
**Context:** Unit 0.1 builds the directory skeleton, and CODEBASE.md exists
specifically so that nothing has to be moved later.

**What happened:** The repository's actual layout (`Plan/`, `Research/`,
`Plan/Phase_1/`) contradicted the target tree in CODEBASE.md §2, which places
`PLAN.md` and `ROADMAP.md` at the root and `research/` lowercase. ROADMAP.md:6
also refers to `PHASE-0-1.md` as a bare sibling filename. Building the skeleton
against the wrong layout would have guaranteed a move later.

**Evidence:** CODEBASE.md §2 tree; ROADMAP.md:6; PLAN.md §7, which lists
`research/` at root level.

**Change:** Docs moved to the repository root — `PLAN.md`, `ROADMAP.md`,
`REVIEW-RESPONSE.md`, `CODEBASE.md`, `PLAN-technical-review.md`,
`PHASE-0-1.md` — and `Research/` renamed to `research/`. The Python package is
`src/fund/`, per CODEBASE.md §2. Note this differs from PLAN.md §7, which shows a
bare `src/`; CODEBASE.md wins on layout.

**Affects:** 0.1. Every relative link in the docs. No behavioural change.

---

## 2026-09-17 — "Depth" removed as a concept
**Context:** Designing the tradeability filter for unit 1.6.

**What happened:** The plan filtered assets on "depth" in several places while
also asserting that tokenized stocks have no AMM pool of their own. If there is
no pool, there is no depth to read, and the filter was gating on a number that
cannot exist. `PLAN-technical-review.md` finding 3 predicted the exact failure
mode: an AMM-liquidity filter that excludes every RFQ-tradeable stock.

**Evidence:** `research/bankr-skills.md`, quoting Bankr's
`bankr/references/tokenized-stocks.md:42`: "tokenized stocks have no AMM pool of
their own, so Bankr sends them to a venue that quotes them directly." Also
`research/bankr-skills.md` on 4663 pool reads: "**not present** — no code in this
repo reads any 4663 pool," and its inference that the V3 pools that do exist on
4663 are for memecoins and hood.markets launches, not Robinhood's stock tokens.
`PLAN-technical-review.md:49` narrows the blanket claim usefully: Robinhood
documents RFQ, AMM and propAMM venues, which establishes supported venue types,
not measured liquidity for any asset.

**Change:** "Depth" is deleted from the vocabulary. **Tradeable** now means all
three of:
- a quote at intended size ($25) succeeded,
- quote age is within bound,
- impact is either known and within limit, **or null — and null blocks.**

This keeps the liquidity requirement but defines it operationally against the
venue we actually trade on, rather than inventing reserves. It is also the
correct reading of invariant 5: unknown blocks execution.

**Affects:** 1.5, 1.6 (the filter), 3.4 (the gate array loses a depth gate and
gains a quote-success/quote-age/impact triple), 3.8 (the veto checkpoint, whose
ROADMAP text names depth as a trip condition), PLAN.md §9's test list.

---

## 2026-09-17 — Probe 0.4 tests GeckoTerminal coverage before divergence
**Context:** Designing the highest-value probe in Phase 0 — the one that settles
how the accounting mark is computed and what the divergence veto threshold is.

**What happened:** 0.4 was specified as a Chainlink-versus-GeckoTerminal
divergence table. But GeckoTerminal prices come from pools, and Robinhood's
tokenized stocks have no pool of their own. The probe assumed coverage that no
research report demonstrates, and the checkpoint it feeds would have had no table
to show.

**Evidence:** Every GeckoTerminal use in the research is pool-derived:
`research/aero-stock-lp.md:199` reads Base *pool* TVL and volume;
`research/agent-os.md` §8 uses the `robinhood` slug inside `unilp`, which is a
Uniswap-v4 pool skill for launches and memecoins. No report shows GeckoTerminal
returning a price for a Robinhood stock token. Combined with
`bankr/references/tokenized-stocks.md:42` (no AMM pool of their own), there is a
structural reason to expect absent coverage, not merely an absence of evidence.

**Change:** 0.4 now runs in two steps.
1. **Coverage first.** Does GeckoTerminal return a price for RH stock tokens at
   all? Recorded as measured, for each of the five assets.
2. **Divergence second**, only if coverage exists.

If coverage is absent, the corroborating source becomes **a Bankr quote at size**,
recorded explicitly as **not independent of the execution venue**, and the
divergence veto changes shape from cross-source to **quote-versus-feed**. That is
a weaker check and the finding must say so rather than presenting it as
equivalent.

**Affects:** 0.4 and its checkpoint, 1.4 (the corroboration source may not be
`adapters/gecko.py`), 3.4 (what the divergence gate compares), PLAN.md §11's
first decision, which assumes two independent sources exist.

---

## 2026-09-17 — Probe order changed: 0.8 before 0.3, and 0.9 moves into Phase 1
**Context:** Sequencing Phase 0.

**What happened:** Two ordering defects. Probe 0.3 quotes "USDG → one stock
contract address," but the canonical address list is what probe 0.8 produces — so
0.3 as written would quote against an address we had not yet established as real,
on a permissionless chain with a known impersonator token. Separately, probe 0.9
measures analyst token cost using "one realistic analyst prompt with a real
snapshot embedded," but snapshots do not exist until unit 1.6, and snapshot bytes
dominate the token count being measured.

**Evidence:** PHASE-0-1.md 0.3 and 0.8 as written. `research/agent-os.md` §8
records the concrete hazard: two `GME`/"GameStop" entries on 4663, one real and
one fake, carried in-repo as an example. PHASE-0-1.md 0.9 already flags its own
prompt as a rough draft, but not its snapshot.

**Change:** **0.8 runs before 0.3.** **0.9 moves out of Phase 0 into Phase 1,
after 1.6**, where a real hashed snapshot exists to embed. Phase 0's exit no
longer waits on 0.9.

**Affects:** Phase 0 order and exit condition. Phase 1 gains a unit after 1.6.
The endpoint pricing input for 0.7's checkpoint now arrives later than 0.7 does,
so the $0.05 price stays provisional until the relocated 0.9 reports.

---

## 2026-09-17 — Agent API stays off on both Bankr keys
**Context:** Reconciling PHASE-0-1.md unit 0.2's done-condition with the
credential table.

**What happened:** 0.2's done-condition required confirming "the Agent API and
LLM Gateway toggles are confirmed **on** for the right keys," while the credential
table specifies Agent API **off**. Nothing in the system calls `/agent/prompt`.
The plan carried a leftover requirement from an earlier design in which fan-out
was bounded by the Agent API's message quota.

**Evidence:** PLAN.md §6 — `BANKR_KEY_READ` is "read-only, Agent API off."
PLAN.md §10 — "Analysts and risk run on the LLM gateway, which is credit-metered,
so the Agent API's 100/day figure does not bound fan-out."
`PLAN-technical-review.md` finding 13 — the daily quota applies to
`/agent/prompt`, and the plan was throttling against the wrong surface.
`research/bankr-claude.md` §10 sources the 100/day figure to
`bankr-safety/SKILL.md:57-65`, which is Agent API documentation.

**Change:** Agent API is **off on both keys**, read and exec. Unit 0.2's
done-condition becomes: confirm the LLM Gateway toggle is on for `BANKR_LLM_KEY`,
confirm Agent API is off for both Bankr keys, and record which auth header each
surface accepts. Reducing attack surface is the point — an unused write-capable
surface left enabled is exactly what `PLAN-technical-review.md` finding 2 warns
about.

**Affects:** 0.2, PLAN.md §6, PLAN.md §10.

---

## 2026-09-17 — RPC requirement reduced to timeout plus fail loudly
**Context:** Specifying `adapters/chain_4663.py` for unit 1.3, which required
"RPC failover that advances on hang as well as rejection."

**What happened:** Failover needs somewhere to fail over to. Exactly one public
4663 RPC endpoint is documented, and it has no archive data — so the plan
specified a resilience mechanism it had no second endpoint to implement, and
block-pinned historical reads would fail on the only endpoint available.

**Evidence:** `research/agent-os.md` §8 — public RPC
`https://rpc.mainnet.chain.robinhood.com`, "rate-limited, **no archive**"
(`robinhood-chain-stocks/SKILL.md:174,188`), with AgentOS recommending a
dedicated provider for any historical read or log sweep.
`PLAN-technical-review.md` finding 6 — "Public RPC failover does not prove
archival access." REVIEW-RESPONSE.md already accepted this: "Archive RPC and a
sequencer-uptime feed are not assumed."

**Change:** The requirement reduces to **explicit request timeouts plus fail
loudly**. No failover is claimed. **No archive reads are assumed anywhere** in the
system: block-pinning applies to a recent block within the public node's
retention, and historical reproducibility comes from the fixture capture in 1.8,
which stores raw source responses rather than re-reading the chain.

This is a reduction, and it is stated in PLAN.md §13.

**Affects:** 1.3, 1.8 (fixtures become the sole mechanism for historical
reproducibility, not a convenience), 1.9 (the selftest attests against current
chain state only).

---

## 2026-09-17 — Every "first in the ecosystem" claim removed
**Context:** Writing judge-facing text and auditing the plan's claims against the
research.

**What happened:** The plan claimed primacy that the research contradicts. A
judge who greps will find the counterexample in our own evidence folder.

**Evidence:** `research/bankr-skills.md:300` documents `urizen`, describing itself
as "an AI equity-research desk + **the first autonomous fund on Robinhood Chain
(4663)**," already serving `/api/fund/book` (positions and NAV), `/trades`,
`/mirror`, `/signals` and `/stats`. It ships zero lines of code and its API is
closed and unverifiable — which is precisely where our actual differentiator
sits — but the "first" framing was published before ours.

**Change:** Removed from ROADMAP.md checkpoint 7.5, which asked whether the x402
revenue line is "the first non-zero one in the ecosystem"; it now asks whether the
revenue reconciles from settlement evidence rather than from a handler log. The
README was written without any such claim. The differentiator is stated as what it
is: reconciled books with visible exceptions, revenue evidenced by settlement, and
a veto that is a code path rather than advice — none of which depends on being
first.

**Affects:** ROADMAP.md 7.5, README.md, and the 8.6 submission text when written.

---

## 2026-09-17 — Invariant 6 reworded: replay comes from recorded outputs, not seeds
**Context:** Auditing PLAN.md's invariants against what Phase 3 actually
delivers.

**What happened:** The v1 invariant "everything stochastic is seeded" implied that
seeding produces comparable model runs. It does not. Unit 3.9 already specified
the correct mechanism — byte-stable replay from recorded model outputs — so the
invariant was overclaiming relative to the build.

**Evidence:** `PLAN-technical-review.md` finding 9 — "A seed does not itself
demonstrate deterministic behavior across selected models or gateway routing,"
and the Phase 3 replay claim "omits freezing the stochastic risk result."
`research/miroshark.md` §10 item 7 makes the narrower, correct point about our own
code: with no `random.seed` anywhere, "two runs of the same config are not
comparable."

**Change:** The invariant now reads: **deterministic replay comes from recorded
model outputs, including the risk output. Seeds apply to our own code only and
prove nothing about model determinism.** Fresh inference against a recorded
snapshot is a separate experiment and is labelled as one, never presented as a
replay.

**Affects:** PLAN.md §2, 3.9 (the checkpoint's claim is now precisely what it
demonstrates), 2.5 and 3.7 (recorded outputs must be persisted with pinned model
ids and effective model/provider where exposed, because they are the replay
substrate).

---

## 2026-09-17 — New unit 4.12: treasurer as its own process
**Context:** Auditing the roadmap against PLAN.md invariant 1.

**What happened:** Invariant 1 requires the treasurer to run as its own process
with its own credentials, "proven by an environment test from the deployed
analyst process, not by an import graph alone." CODEBASE.md §3 calls the
deployed-isolation test "the one that matters most." No unit in any phase built
it. The strongest safety claim in the plan had no unit behind it.

**Evidence:** PLAN.md §2 invariant 1; CODEBASE.md §1 rule 2 and §3;
`PLAN-technical-review.md` finding 2 — "The claimed single-writer boundary is an
import rule, not an enforced authority boundary… An import-graph test alone is not
a pass." REVIEW-RESPONSE.md dispositions it **Adopt (core)**, with the treasurer
as a separate process reading approved intents from the database.

**Change:** **Unit 4.12 added** — run the treasurer as its own process with its
own credentials, reading approved intents from SQLite, plus the deployed-isolation
test: from the analyst process environment, execution and signing credentials are
unreadable and a raw HTTP swap fails. Placed at the end of Phase 4 so it lands
before any real submission in Phase 5. Phase 4's exit gains it.

**Affects:** Phase 4 exit condition, `tests/test_boundaries.py`, 5.x (no real
submission happens before 4.12 passes), PLAN.md §5 deployment.

---

## 2026-09-17 — Phase 5 renamed "live chain activity" and rescoped
**Context:** Following the US-operator decision through to the phase it gates.

**What happened:** Phase 5 was "live execution," gated on probe 0.5 passing, with
an exit of a live stock buy-and-sell round trip. With stock execution
unavailable, that phase as written cannot open at all — which would have left the
build with no real on-chain activity and no genuine receipt, reconciliation or
explorer evidence.

**Evidence:** The US-operator entry above. REVIEW-RESPONSE.md finding 12:
"Unresolved eligibility means Phase 5 does not open and the demo ships paper,
stated plainly." The narrower reading is that *stock* eligibility fails while
*chain* access does not — memecoin/USDG swaps on 4663 are ungated.

**Change:** Phase 5 becomes **"live chain activity."** New exit condition: **a
real transaction on 4663, executed through the treasurer, reconciled from its
receipt, and booked exactly once.** Live stock fills are out of scope and are
stated in PLAN.md §13.

This keeps everything the phase was actually for — the order state machine under
real conditions, receipt reconciliation, confirmation depth, mined reverts, the
crash drill against a real chain, and a transaction a judge can open in the
explorer — while being honest that the traded asset is not a stock. Unit 5.6 (a
real 403, decoded) still runs and is now the *expected* result for the stock path
rather than an error case.

**Affects:** Phase 5 name, units 5.1–5.7 and the phase exit. ROADMAP.md's
"only if probe 0.5 passed" gate, which no longer decides whether the phase exists.
PLAN.md §13. The demo script in 8.4 and the submission text in 8.6, both of which
must state the paper/live split without burying it.
