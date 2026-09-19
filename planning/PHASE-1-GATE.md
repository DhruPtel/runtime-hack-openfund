# Phase 1 gate

The re-evaluation gate `PHASE-0-1.md` sets before Phase 2 is detailed. Written
2026-09-18, at the end of Phase 1. Phase 2 has not started.

**Superseded in part on 2026-09-19.** The cut-or-fold list in §5 is replaced by
the scope pivot. Every unit is kept and built at minimal depth instead (PLAN §8,
`SIMPLIFICATION.md`, LESSONS 2026-09-19). The "Fewer stops" advice survives as
five stops: 3.8, 5.4, 6.6, 7.5 and 8.5. The rest of this report stands.

**The state it describes:**
- 362 tests pass offline.
- `make replay` rebuilds the committed capture, `66852293-253315c0e691`,
  byte for byte, with every connection refused.
- `make selftest` attests 235 of 235 addresses live.
- The snapshot schema is `openfund.snapshot/4`.

## In short

- **Phase 1's exit is met.**
  - A hashed snapshot from live data, with 30 days of history to its block.
  - Byte-identical replay from a committed fixture.
  - Bad inputs refused by name, and old history accepted.
  - Every address attested, the beacon included.
- **The snapshot fully feeds only one of the four analyst seats.** Two others
  get part of what they need. The fourth, fundamentals and calendar, gets
  nothing but names. 2.1 has to settle that seat.
- **Phase 1's measurements changed the marking and veto rules,** as Phase 0's
  did: staleness, the weekend, the pause, history, and held assets.
- **Phase 5 should stay in, cut to its first four units:** one real round trip
  on the ungated leg, reconciled and booked. Without it the fund never acts on
  chain.
- **The pace.** Phases 0 and 1 are 22 units in about 15 working hours, over 26
  hours elapsed. 60 units remain, about 42 working hours at the same rate. The
  record holds no deadline, so whether that fits is the operator's to say. If
  the pace holds, cut or fold 15 units (below) and most of the stop-and-wait
  checkpoints.

---

## 1. What Phase 1 delivered

| Unit | Delivered |
|---|---|
| 1.1 Types | `core/types.py`, stdlib only. Canonical JSON that refuses floats and carries integers past 2**53 as text. Fixed-point quantities with no default decimals, three-valued checks, and `(chain_id, address)` identity. Built from recorded data, including the real GME counterfeit and a Chainlink round id past 2**53. |
| 1.2 Universe | The issuer registry and Chainlink's directory pinned by sha256 in `config/registry/`. Identity, standing and markability are separate rules, and a beacon disagreement raises. The feed map is keyed by address. Both counterfeits are refused at identity. |
| 1.3 Chain adapter | `adapters/chain_4663.py`. Every read is addressed to one block by hash. It has a JSON-RPC client with a deadline, failover, pacing and backoff, Multicall3 reads, and freshness on the newest point. It found every equity feed silent 48–59 h each weekend, against a 25 h rule. |
| 1.4 Cross-check | `adapters/http.py`, `adapters/gecko.py` and `core/valuation.py`. Chainlink marks, and GeckoTerminal corroborates. Divergence is tiered at a $1M line. The closed session, Sat 00:05Z to Sun 23:55Z, was inferred from 86,606 rounds over twelve weeks. |
| 1.5 Quotes | `adapters/bankr_quote.py`, read-only under the analyst role. Four number formats converted exactly. Impact compared signed. Tradeability is named by rule, and a quote is never evidence of a fill. |
| 1.6 ▶ Snapshot | `core/snapshot.py` and `run/snapshot.py`: one readable document, hashed as its bytes on disk. A re-read at the same block rebuilds the same hash. |
| 1.7 Analyst cost | $0.454 a call against the real snapshot, with the timeline two thirds of the input. That led to daily closes, $0.264 a call, and $1.11 a cycle at four analysts plus risk. |
| 1.8 Held assets | Every holding carries a universe status and a holding status. An asset the registry drops while held is carried, never dropped. |
| Test audit | 354 cases cut to 313, each cut shown redundant by breaking what it tested. `test_boundaries.py` covers ten recorded rules that had no test. |
| 1.9 ▶ Fixtures | Capture at the transport, and offline replay. A replay stops at any request its capture does not hold. The snapshot names its capture's answers by hash, so every captured byte moves it. |
| 1.10 Selftest | `make selftest`: 235 addresses at one block, each check able to fail on a plausible wrong value, about 100 s. GME's address pointed at the counterfeit fails at the beacon, named. |
| 1.11 ▶ Skew | Mixed blocks, a future value, a stale newest point and a holiday are each refused at their rule. The builder's block check was tested at one of its four places, and is now tested at all four. After the checkpoint, a paused feed is refused at its own rule, read from the token's `oraclePaused()`. |

## 2. What it cannot do

From `PHASE-0-1.md` ("What Phase 1 still cannot do") and the LOGS open items:

- **Trade a stock.** Stock execution is location-gated, so stock legs are paper
  (F0.5.1). A quote is a price, not a fill.
- **Size against real capital.** The wallet holds about $1.29: 0.078742 USDG
  and 0.000460 ETH, against a ~$200 target.
- **Measure the multiplier.** Whether the feed already includes it is
  documented, not measured (F0.4.4).
- **Value an equity on a market holiday.** It reads as stale and fails closed.
- **Know the closed session after 1 November.** Daylight saving is unmeasured,
  and the span is re-derived on 9 November.
- **Read an old block, or fail over.** There is one public endpoint with no
  archive.
- **Catch a counterfeit inside the registry, or a proxy clone with its own
  beacon** (F0.8.5).
- **Detect a stale offchain body.** No body carries a source time, and
  GeckoTerminal's `Date` is deliberately unchecked (PLAN §13).
- **Assess exit.** No sell quote is read, so neither a sale nor a spread is
  known.
- **Know a rate limit.** Bankr's and the RPC's are unknown. The new capture
  holds one RPC 429, retried.
- **Account for the 6 bps of the 0.10 sale** (F0.10.4).

Also open:
- about 37–50% of billed analyst output never appears in the reply;
- AMZN's GeckoTerminal price alternates between two levels;
- $25 is sized at USDG's own mark;
- the oldest quote runs 20–25 s old at `built_at`;
- nine feeds describe themselves `RH<ticker> / USD`, against F0.4.1.

## 3. What is owed

| Owed | When | Blocked on |
|---|---|---|
| **Weekday capture,** committed beside the weekend one. Every committed capture is from a closed session, so the veto cannot fire from fixtures. | From Mon 2026-09-21 00:00Z, ideally 13:30–20:00Z | The calendar (`CLAUDE.md`) |
| **Re-derive the closed session** | Mon 2026-11-09 | The calendar (`CLAUDE.md`, `config/sessions.json`) |
| **LLM credits.** $0.937 is left, less than one $1.11 cycle, so 2.6's first real report cannot run twice. | Before 2.6 | The operator: it is a spend |
| **Wallet funding** for the live round trip | Before 5.2 | The operator: it is a spend |
| **Fixtures or live in the demo?** Asked at 1.9, not answered | Before 8.4 | The operator |
| **Two `adapters/http.py` changes** (1.5's workarounds) | When next touched | — |
| **README status line.** It still says "Phase 0". | Outside this pass's paths | — |
| **F0.4.1 in `research/findings.md`** still says every equity feed is named `Robinhood <TICKER> / USD` | Outside this pass's paths | — |
| **The six judging criteria.** PLAN 8.6 names them, and they are not in the repository. The cuts below would be better aimed with them. | Now | The operator |

## 4. Config still null

`null` means unresolved, and it blocks whatever reads it.

| File | Key | Blocks |
|---|---|---|
| `cadence.json` | `cycle_deadline_seconds`, `retry_budget_per_worker` | 2.4 |
| `cadence.json` | `confirmation_depth` | 5.3 |
| `models.json` | `risk_model` | 2.4 |
| `models.json` | `context_budget_tokens` | 2.4, 3.6 |
| `thresholds.json` | `quorum_min_analysts` | 3.1 |
| `thresholds.json` | `max_position_weight`, `turnover_max_bps`, `cash_floor_usd` | 3.4 |
| `mandate.json` | `cumulative_budget_usd`, `approved_by`, `approved_at`, `expires_at`; `allowed_assets` is empty | 4.1 |

## 5. The four questions

### Is the snapshot rich enough for an analyst to be worth paying for?

**For one of the four seats, fully. For two, partly. For the fourth, no.** Each
of the 35 assets carries:
- its registry identity;
- the Chainlink mark, with freshness and the pause flag;
- GeckoTerminal's price, 24h volume and divergence;
- a $25 buy quote with impact and fees;
- its findings and status;
- 30 daily closes plus the latest round.

Measured against the roster in `config/analysts.json`:

| Seat | What the snapshot gives it |
|---|---|
| `price-trend` | Enough: 30 daily closes per asset. 1.8's reports used the history as much as with every round. That is a proxy, not a grade. |
| `execution-quality` | Most of it: quote age, impact, fees and tradeability, buy side at one size. No spread, because no sell quote is read. |
| `cross-asset-macro` | Part of it: 35 aligned price series, so correlations. No rates, volatility or macro calendar beyond what SPY, QQQ, SGOV, SLV and USO tokens imply. |
| `fundamentals-calendar` | Nothing but a name and an ISIN: no earnings dates, filings, news or corporate-action calendar. This seat would reason from the model's memory, which no snapshot freezes and no decision record can cite (invariant 2). |

Whether a report is worth paying for is 2.1's question, and 2.6 is the first
real one. What this gate can say:
- 2.1 has to decide the fourth seat. It can be dropped, or it needs a frozen
  source of events, which is a new adapter, capture and cost.
- Dropping it saves about $0.26 a cycle.
- At $0.25 a record, a four-analyst cycle needs about 4.4 sales to break even,
  and a three-analyst cycle about 3.4.

### Did anything Phase 1 measured change the marking, veto or universe decisions?

**Yes, as 0.4 and 0.8 did.**
- **Marking.**
  - Staleness counts open-session time only. One weekend measured every equity
    feed silent 48–59 h against a 25 h rule, so every weekend would have
    refused every stock.
  - A paused oracle has no mark (1.11).
  - A series that falls short of its window blocks trading (1.7's SPCX).
- **Veto.**
  - In a closed session divergence is a finding, not a veto. 1.4 vetoed MSTR
    on a Saturday.
  - Findings are kept only past the open-session limit.
  - GeckoTerminal's age is not checked, and the one fail-open direction is in
    PLAN §13.
- **Universe.**
  - An asset the registry drops while held stays in the book (1.8).
  - The $1M corroborator line excluded 15 of 35 in both weekend captures.
    Weekday behaviour is not measured, which is one reason the weekday capture
    matters.
- **Unchanged:** identity (registry by hash, beacon cross-check), the
  unapplied multiplier, the $25 size.

### Is Phase 5 in or out, and does that change the demo?

**Recommendation: in, cut to 5.1–5.4.** That is a live executor behind the paper
interface, one real ETH→USDG→ETH round trip on 4663 through the treasurer, and
receipt reconciliation, shown on the explorer.
- **Why keep it.**
  - Stock legs are paper either way, because of location.
  - Without Phase 5 the fund never acts on chain. The books reconcile paper
    against paper. The technical review's warning stands: a paper demo does not
    prove the Robinhood Chain requirement.
  - 0.10 proved one $0.08 sell. The return leg has never run.
- **What it needs.** A funded wallet. A few dollars would do; that is a spend,
  and the operator's call.
- **What it changes in the demo.** The one real on-chain act is the ungated
  round trip, booked exactly once, beside paper stock legs. The demo has to
  say that plainly.
- **Cut:**
  - 5.5, the access-expiry drill, becomes a stated limitation;
  - 5.6 reuses probe 0.5's recorded 403 rather than decoding it again;
  - 5.7 folds into 8.3.

### What did Phases 0 and 1 cost in time, and what does that imply?

**Measured from the commit history:**
- **Elapsed:** 349 commits over 26.0 h, Thu 2026-09-17 21:06 to Fri 23:10
  PDT.
- **Phase 0:** about 8.3 h of work, 21:06 to 15:42 the next day, less a 10.3 h
  overnight gap.
- **Phase 1:** about 7.3 h, 15:54 to 23:10, the replan and the test audit
  included.
- **Active time:** summing only the gaps under 45 minutes gives 9.9 h. So the
  real figure is between about 10 h and 15.5 h, depending on what the longer
  gaps held.
- **Where it went.** 146 of 349 commits are documentation. `planning/` and
  `tracker/` hold 6,367 lines, against 7,110 in `src/` and 4,860 in `tests/`.
- **Against the plan:** the record holds no time budget and no deadline. The
  only sizing on record is the replan's, written before the units were built.
  It marked 7 of Phase 1's 11 units bigger than drafted.

**Implication.** 22 units took about 15 working hours, roughly 0.7 h a unit.
60 remain: 8 in Phase 2, 9 in 3, 12 in 4, 7 in 5, 8 in 6, 9 in 7 and 7 in 8.
- **At the same rate:** about 42 working hours, nearly three times what has
  been spent.
- **Why that is a floor:** the later units are heavier. They spend money,
  deploy, take a real purchase and run crash drills.
- **The checkpoints:** 21 of the remaining units are ▶ checkpoints, each a
  stop and a wait for the operator.
- **The deadline:** unknown to the record. If it is less than about two more
  working days, the plan as written does not fit.

**If the pace holds, cut or fold these: 15 units, with two more reduced, about
10 working hours:**

| Phase | Keep | Cut or fold |
|---|---|---|
| 2 | 2.1–2.7 | 2.8's failure drill becomes 2.4's tests. Drop `fundamentals-calendar` unless 2.1 finds a frozen source. |
| 3 | 3.1, 3.3–3.5, 3.7, 3.8 | 3.2 folds into 3.1's output. 3.6 stays small. 3.9 reuses 1.9's replay. |
| 4 | 4.1–4.9, 4.11, 4.12 | 4.10's crash drill becomes 4.9's tests. This is the money path, so it stays whole otherwise. |
| 5 | 5.1–5.4 | 5.5 becomes a limitation. 5.6 reuses 0.5's 403. 5.7 folds into 8.3. |
| 6 | 6.1–6.3, 6.6 | 6.4, 6.5 and 6.7 (attribution and call accuracy) are deferred. 6.8 folds into 6.2. |
| 7 | 7.1, 7.2, 7.5, a plain 7.6 | 7.3 and 7.4 fold into 7.5. 7.8 becomes a stub. 7.9 is cut. |
| 8 | 8.1–8.6 | 8.7 folds into 8.6. |

**Two changes of practice would save more than any single cut:**
- **Fewer stops.** Keep ▶ for the checkpoints that can change the plan: 2.1,
  3.8, 4.11, 5.4, 6.6, 7.5 and 8.5. The rest become shown, not stopped.
- **Record once.** Each decision goes in one place and the others point at it,
  rather than folded into three documents per unit.

The pace rule in `CLAUDE.md`, verification scaled to risk, is the third lever,
and is already in force.
