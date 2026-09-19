# Codebase — target structure

What the repository should look like when the build is finished. This is the
destination, not the starting point. Files appear as their phase produces them,
but their place is decided now so nothing has to be moved later.

Judges will read this code. Legibility is a requirement, not a nicety.

---

## 1. Organizing principles

**1. Dependency flows one way.**

```
adapters ──► core ──► agents ──► treasurer ──► surfaces
                └──► store ◄────────┘
```

`core/` imports nothing from `adapters/`. It receives already-fetched data and
returns computed data. That makes every rule in the system testable with no
network and no keys.

**2. Spend authority is a directory.** Only `treasurer/` may import
`adapters/bankr_exec` or the signing key. `agents/` and `core/` cannot reach
either. This is enforced by a test, and separately by running the treasurer as
its own process with its own credentials.

**3. One rule, one location.** A limit is defined once in `core/gates.py` and
called by both risk and treasurer. Two interpretations of the same limit is how
a fund trades outside its own policy. **Three named exceptions, until 3.4**
(DECISION, LESSONS 2026-09-18). This module is 3.4's, and three earlier units
each needed a threshold comparison, so each stays where the plan put it:
1. feed staleness, in `adapters/chain_4663.py` `freshness()` (1.3);
2. the divergence tier's volume line and veto limit, in `core/valuation.py`
   `cross_check()` (1.4);
3. quote age and signed impact, in `adapters/bankr_quote.py` (1.5).

Each is defined once, reads its thresholds from `config/thresholds.json` as
arguments, and names its rule when it refuses. **3.4 owns the sweep:** it moves
all three into this module as one deliberate move.

**4. Nothing important happens in an agent.** Models produce opinions and prose.
Arithmetic, ranking, thresholding, sizing and accounting are deterministic code.

**5. Every number carries its units.** Raw integer amount, decimals, and asset
identity travel together. No bare floats cross a module boundary.

**6. Every observation carries its provenance.** Value, source, source time,
fetch time, block. A number with no provenance cannot enter a snapshot.

**7. Writes are durable before they are attempted.** Order intent is persisted
before the HTTP call, not after the response.

---

## 2. The tree

```
fund/
├── README.md                   what this is, how to run it, the limitations
├── pyproject.toml              pinned deps, lockfile committed
├── Makefile                    snapshot, cycle, replay, test, selftest, demo
├── .env.example                every credential named, no values
│
├── planning/                   every planning document. README.md stays at root.
│   ├── PLAN.md                 the build plan. Authoritative.
│   ├── ROADMAP.md              units and checkpoints
│   ├── PHASE-0-1.md            unit-level detail for the first two phases
│   ├── CODEBASE.md             this file
│   ├── REVIEW-RESPONSE.md      disposition of every technical-review finding
│   ├── PLAN-technical-review.md  the external review the response answers
│   └── PLAN-v1.md              superseded. Kept for comparison; v2 wins.
│
├── tracker/
│   ├── LOGS.md                 what was built, one entry per unit
│   └── LESSONS.md              what changed and why. History, not authority.
│
├── config/
│   ├── registry/               the allowlist: pinned raw registry and feed directory (named by sha256),
│   │                           pins.json (versions, issuer beacon, cash leg, gas), feed_map.json
│   ├── mandate.json            bounds, wallet, chain, allowed assets, budget, expiry
│   ├── thresholds.json         staleness, divergence, quote age, impact, turnover, cash floor, quorum
│   ├── models.json             pinned model ids, token caps, deadlines, context budget
│   ├── cadence.json            schedule, confirmation depth, retry budgets
│   ├── analysts.json           the roster and its scope partition
│   ├── chain.json              the 4663 RPC: endpoints, deadlines, pacing, series window (1.3)
│   ├── sessions.json           closed sessions inferred from feed rounds, with evidence (1.4)
│   └── gecko.json              GeckoTerminal: network slug, batch size, pacing (1.4)
│
├── src/fund/
│   │
│   ├── adapters/               ALL external I/O. Nothing else touches the network.
│   │   ├── chain_4663.py       block-pinned RPC reads: feeds, balances, decimals, beacon slot
│   │   ├── gecko.py            corroborating USD prices via the "robinhood" slug
│   │   ├── bankr_quote.py      /wallet/swap-quote — READ ONLY, no signing import
│   │   ├── bankr_exec.py       /wallet/swap — the ONLY signing path in the repo
│   │   ├── bankr_llm.py        gateway client: backoff, deadlines, token accounting
│   │   ├── bankr_usage.py      /v1/credits, /v1/usage — cost reconciliation evidence
│   │   ├── http.py             one HTTP client: timeouts, retries, Retry-After, redaction
│   │   │                       (1.3's, moved here at 1.4; every adapter uses it)
│   │   └── cache.py            raw source responses to disk, timestamped by code
│   │
│   ├── core/                   PURE. No network, no keys, no clock reads outside inputs.
│   │   ├── types.py            Observation, Series, Asset, Quote, Holding, Snapshot,
│   │   │                       Order (1.1); report/plan/decision/journal types later
│   │   ├── universe.py         allowlist loading, address verification, status assignment
│   │   ├── snapshot.py         merge → filter → canonicalize → hash
│   │   ├── aggregate.py        reports → weights or no-rebalance. A total function.
│   │   ├── plan.py             weights + holdings + quotes → sized orders
│   │   ├── gates.py            the declarative gate array. THE single definition of every limit.
│   │   │                       (three named exceptions until 3.4 sweeps them in; §3)
│   │   ├── valuation.py        the ONE valuation function
│   │   ├── books.py            journal → income statement + portfolio report
│   │   └── attribution.py      funded contribution (allocated once) and call accuracy (hypothetical)
│   │
│   ├── agents/                 Model calls. Opinions only, never authority.
│   │   ├── runner.py           bounded fan-out, deadlines, fallbacks, partial-failure disclosure
│   │   ├── analyst.py          brief → call → parse → validate
│   │   ├── risk.py             full reports + sized plan → verdict (gates decide, model explains)
│   │   ├── schema.py           strict output schemas incl. NO_CALL
│   │   └── briefs/
│   │       ├── analyst.v1.md   versioned. mandate, scope boundaries, output contract, effort scaling
│   │       └── risk.v1.md
│   │
│   ├── store/                  Durable state. SQLite, single writer.
│   │   ├── schema.sql          orders, reports, journal, positions, publications, locks
│   │   ├── orders.py           the order state machine (§4 of PLAN)
│   │   ├── reports.py          immutable content-addressed report store
│   │   ├── journal.py          append-only accounting events
│   │   ├── positions.py        derived from journal, never mutated directly
│   │   └── publish.py          immutable record bytes, manifest, atomic latest pointer
│   │
│   ├── treasurer/              THE ONLY SPEND AUTHORITY. Own process, own credentials.
│   │   ├── mandate.py          load, validate, check expiry and revocation, track cumulative use
│   │   ├── intent.py           plan → ordered orders + stable idempotency keys
│   │   ├── execute.py          regate on fresh evidence → validating chokepoint → submit
│   │   ├── reconcile.py        receipts, confirmation depth, mined reverts, startup recovery
│   │   └── sign.py             ed25519. The only signer in the system.
│   │
│   ├── surfaces/
│   │   ├── x402/               TypeScript handler: fetch published record by id. No state, no inference.
│   │   ├── page/               static page over the same published records
│   │   └── skill/SKILL.md      so other Bankr agents can call it
│   │
│   └── run/
│       ├── cycle.py            the pipeline: snapshot → analysts → aggregate → plan → risk → decide
│       ├── schedule.py         cheap tick, overlap fencing, kill switch
│       └── startup.py          reconcile unresolved intents before accepting a cycle
│
├── probes/                     Phase 0 throwaways. Nothing in src/ imports these.
├── fixtures/
│   ├── snapshots/              raw captured source responses + rebuilt snapshots
│   └── accounting/             the known-answer fixture
├── research/                   the seven discovery reports + findings.md
└── tests/
    ├── test_snapshot.py
    ├── test_universe.py
    ├── test_aggregate.py
    ├── test_gates.py
    ├── test_orders.py          incl. crash and ambiguity drills
    ├── test_books.py           incl. the known-answer fixture
    ├── test_attribution.py
    ├── test_boundaries.py      import graph + deployed-process capability
    └── test_redaction.py
```

---

## 3. Boundary rules, stated as tests

These live in `tests/test_boundaries.py` and are the ones a judge can read in
thirty seconds to understand the safety model.

| Rule | Test |
|---|---|
| `core/` is pure | no module under `core/` imports `adapters/`, `agents/`, `store/` |
| Analysts cannot spend | no module under `agents/` or `core/` imports `bankr_exec` or `sign` |
| One signer | `sign.py` is imported only by `treasurer/` |
| One gate definition | `gates.py` is the only module defining a threshold comparison, except the three named exceptions in §3 (staleness in `chain_4663.py`, the divergence tier in `valuation.py`, quote age and impact in `bankr_quote.py`), which the test must name until 3.4 sweeps them in |
| Deployed isolation | from the analyst process environment, execution credentials are unreadable and a raw HTTP swap fails (unit 4.12) |
| No credential in logs | every declared credential value is masked in captured log output |

The deployed-isolation test is the one that matters most. An import graph proves
a code property; only the environment test proves an authority property.

---

## 4. Data conventions

**Amounts.** Always `(raw_int, decimals, asset_id)`. Formatting to a human
decimal happens at the edge, never in `core/`.

**Time.** Two fields, always: `source_time` (when the data was true) and
`fetch_time` (when we saw it). Code generates `fetch_time`. Nothing agent-
reported is ever trusted as a clock.

**Verification.** Three-valued: `true` / `false` / `null`. Null means
undetermined. A required check must be explicitly `true`; null blocks execution.

**Identity.** `(chain_id, address)` everywhere. Tickers are display-only and
never resolve an asset.

**Hashing.** Canonical JSON: sorted keys, stable numeric encoding, saved times,
no floats. Same input, same bytes, same hash, always.

**Ids.** `snapshot_id`, `report_id`, `decision_id`, `order_id`, `cycle_id`. Every
artifact references the ids of its inputs, so any published number can be traced
back to the block it came from.

---

## 5. How data moves, file by file

```
run/cycle.py
  ├─ adapters/chain_4663 ─┐
  ├─ adapters/gecko ──────┼─► core/snapshot.build() ──► snapshot_id
  ├─ adapters/bankr_quote ┘        │
  │                                ├─► agents/runner ──► agents/analyst ──► store/reports
  │                                │        (parallel, read-only, deadline-bounded)
  │                                │
  │                                └─► core/aggregate ──► Proposal
  │                                         │
  │                          store/positions ┴─► core/plan ──► Plan (sized orders)
  │                                                    │
  │                        store/reports (full) ───────┴─► agents/risk + core/gates ──► Decision
  │                                                                  │
  │                                              treasurer/sign ─────┴─► decision_id (immutable)
  │                                                                  │
  │        treasurer/intent ──► store/orders (prepared) ─────────────┘
  │                    │
  │        treasurer/execute ──► core/gates (regate) ──► adapters/bankr_exec
  │                    │
  │        treasurer/reconcile ──► store/journal ──► store/positions
  │                                       │
  │                            core/books ┴─► Statement ──► store/publish
  │                                                              │
  └──────────────────────────────────────────► surfaces/x402 + surfaces/page
```

Read that top to bottom and the whole system is visible in one screen. That's the
point of the layout.

---

## 6. Naming and style

- Modules are nouns, functions are verbs: `snapshot.build()`, `gates.evaluate()`,
  `orders.prepare()`.
- No abbreviations in public names. `divergence_bps`, not `div`.
- Every threshold reads from config, never a literal in a function body.
- Errors are typed and named after the rule they broke: `StaleFeedError`,
  `UnverifiedAssetError`, `MandateExceededError`, `QuorumNotMetError`.
- Prompts are files, versioned in their filename, never inline strings.
- A module doing both I/O and logic is a bug to be split, not a style preference.

---

## 7. What "finished" looks like

Someone clones the repo and, without credentials:

```bash
make test        # everything passes, no network
make replay      # rebuilds a snapshot from fixtures, hash matches
make cycle-demo  # a full cycle from fixtures: reports, weights, verdict, fills, books
```

With credentials:

```bash
make snapshot    # live, block-pinned, hashed
make selftest    # every address attested against chain
make cycle       # live cycle, durable orders, reconciled journal
```

And the public page shows the same records the paid endpoint serves, each
traceable to a snapshot hash and a block.

---

## 8. Things that would mean we got it wrong

- A threshold appearing as a literal anywhere outside `config/`.
- An LLM call inside `core/`.
- A network call inside `core/`.
- A second place that computes value.
- An order submitted before its intent row exists.
- A ticker used to resolve an asset.
- A float in a hashed structure.
- Any credential reachable from the analyst process.
