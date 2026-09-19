# Phase 4: the treasurer and the ledger

**Status, 2026-09-19:** the six decisions are made (below), and **4.0 is built**:
twelve values, one definition each (LOGS, 4.0). Next is Batch B, from 4.1. Phase 3 closed with 3.9: the exit run's
signed decision rebuilds byte for byte (`tests/test_replay_cycle.py`). Before 4.0,
the replay was made to read the config its cycle carries and to judge by the gate
set its record names (LOGS, "3.9 hardened"), because 4.1 and 4.4 change both.

**Read first:**
- `CLAUDE.md`;
- the design lesson in `tracker/LESSONS.md` (2026-09-19, "a value that more
  than one component computes is one function, defined before any of them");
- the Phase 4 rows in `SIMPLIFICATION.md`;
- PLAN §4, the execution state machine.

Phase 3 ends with a signed decision: which orders were approved, and why. Phase
4 turns that into orders written before they are acted on, paper fills at fresh
quotes, a ledger, and positions derived from it. It also moves the treasurer
into a process of its own. Nothing here touches the chain: stock legs are paper
(PLAN §13), and the live leg is Phase 5's.

## In short

- **The primitives come first, as unit 4.0.** Phase 4 has the shape the 3.8
  sweep found in Phase 3. Order state, what a fill gives and takes, position
  quantity, cost basis, realised and unrealised value, and cash would each be
  computed in three or four places. Each is specified below as one function,
  built and tested before any unit that uses it.
- **Twelve values, not seven.** The orientation after Phase 3 found five more
  that several units would each compute: what a ledger event that is not a fill
  does, which book an event belongs to, a book's NAV and which holding is cash,
  cash partway through a decision, and the state of an order the chokepoint
  refuses. They are P8 to P12.
- **The six decisions are made** (the operator, 2026-09-19; LESSONS). Two are
  encoded by 4.0: average cost (P6), and paper cash as USDG at its own mark
  (P5). The other four wait for the units that use them: the mandate (4.1), the
  published key (4.2), the snapshot's age limit (4.4), and the refused swaps
  (4.12).
- **A stop at 4.11,** the known-answer accounting fixture (the operator,
  2026-09-19). `CLAUDE.md`'s stop list does not name 4.11 yet, and that file is
  outside this pass's paths: owed.
- **Batches:**
  - A: 4.0;
  - B: 4.1 to 4.8;
  - C: 4.9 and 4.10;
  - then the stop at 4.11;
  - D: 4.12.

  Each batch is sequential, and each unit consumes the one before. None builds
  a value another unit also builds, because 4.0 builds them all first.
- **The spend:** none until 4.12. There, one refused-swap attempt per agent key
  needs authorizing; nothing is spent if refused (SIMPLIFICATION).

---

## What the record already settles

Not re-decided here.

- **Stock legs are paper.** Each stock quote's `executable` is null, because
  execution is location-gated (F0.5.1), and null blocks. A paper fill is the
  fresh quote's amounts, labelled paper everywhere, never counted as a trade on
  chain (SIMPLIFICATION, "What the minimal versions must not claim").
- **Nothing is booked from an HTTP status** (PLAN §2 invariant 9). A live fill
  is evidenced by a receipt; that is Phase 5's.
- **Orders are written before they are sent** (PLAN §4). An `unknown` order
  never gets a new key.
- **The idempotency key is derived from the decision id and the order's
  index.** Bankr's `idempotencyKey` deduplicates (F0.10.1).
- **Already one definition each:**
  - valuation is `core/valuation.value`;
  - what an order is worth and the cash orders leave is `core/cash.py`;
  - every limit is `core/gates.py`;
  - the floor on approved orders is `gates.settle`;
  - the signer is `treasurer/sign.py`.
- **Already typed at 1.1:** `Order`, `OrderState` (prepared, submitted,
  unknown, confirmed, failed), `ExecutionMode` (paper, live), `Execution`,
  `TokenTransfer` and `TransactionRef` (`core/types.py`).

---

## The shared primitives: one definition each, built first (4.0)

For each: what it is, which units would otherwise compute it, the one function,
and its rule. All are **H**. Each rule is broken in a copy and a test must fail.

### P1. Order state and its transitions

- **Who computes it:**
  - 4.3 writes states;
  - 4.4 reads them (only `prepared` may be sent);
  - 4.5 moves an order through them;
  - 4.9 resolves `submitted` and `unknown`;
  - 4.10 drills a crash between two of them.
- **One definition:** `core/orders.py`, `transition(order, to, reason=…) -> Order`.
  It is a pure table of the allowed moves, and any other move is refused by
  name:

  | From | To |
  |---|---|
  | `prepared` | `submitted`, or `refused` (P12) |
  | `submitted` | `confirmed`, `failed` or `unknown` |
  | `unknown` | `confirmed` or `failed`, or `submitted` again with the same key |
  | `confirmed`, `failed`, `refused` | nothing: each is final |

  `store/orders.py` persists what `transition` returns. It never decides a
  state.
- **Rule:** a state is written before the act it names. An `unknown` order
  keeps its key.

### P2. Order identity and the idempotency key

- **Who computes it:** 4.2 (intent), 4.4 (the chokepoint checks it), 4.5 and
  5.1 (sent with the order), 4.9 (a re-send).
- **One definition:** `core/orders.py`, `order_id(decision_id, index)` and
  `idempotency_key(decision_id, index)`. Both are deterministic, so a restart
  derives the same key. The key is UUID-shaped, as the key F0.10.1 measured
  being deduplicated was; that another UUID is accepted the same way is inferred.

### P3. What a fill gives and takes

- **Who computes it:** 4.5 (the paper executor), 4.6 (the ledger records it),
  4.7 (positions), 4.11 (the fixture). Later, 5.3 builds a live fill from
  `Transfer` logs.
- **One definition:** `core/ledger.py`, `Fill`: the asset given and its raw
  amount, the asset got and its raw amount, the mode, the marks at fill time,
  and which leg is cash. `paper_fill(order, quote, snapshot)` takes the fresh
  quote's `sell` and `buy` amounts exactly: "a paper fill is the quote". It
  refuses a live order, a quote for another order, and one below `min_buy`.
- **Rules:**
  - a fill records the marks it was valued at, so its worth is never
    recomputed later at another price;
  - a fill's value is its cash leg at that leg's recorded mark: what a buy
    paid, and what a sell received. Every trade has a USDG leg.

### P4. Position quantity

- **Who computes it:**
  - 4.7 (positions);
  - 4.4 (a sell may not exceed what is held);
  - 4.9 (reconciliation);
  - the next cycle's planner (its `holdings` input);
  - 4.11.
- **One definition:** `core/ledger.py`, `holdings(events, *, book) -> {asset:
  Amount}`: every event's effect per asset (P8), in raw units, for one book (P9).
  It is the only way a quantity held is known. A book that would hold less than
  nothing refuses at the event that did it, and so does an order filled twice.
  Nothing writes a position directly (PLAN §8 4.7).

### P5. Cash

- **Who computes it:**
  - 4.5 (a buy spends it);
  - 4.7;
  - the planner's `cash_usd` input;
  - `gates.settle`, on the approved orders;
  - 4.11.
- **One definition:** cash is the cash leg the ledger holds, from P4: USDG.
  Its dollar value is `cash.worth` at USDG's own mark. `core/ledger.py`,
  `cash_held(events, *, book, snapshot)`. It sits in the ledger, not `core/cash.py`
  as first planned, because `cash.py` cannot import the ledger that imports it,
  and it is not named `cash`, which would hide that module inside the ledger.
  `cash.cash_after` stays the projection for plans (P11).
- **Decided (the operator):** paper cash is USDG units, valued at USDG's own
  mark, never assumed to be a dollar. The exit run's snapshot marks USDG at
  0.99992279.

### P6. Cost basis

- **Who computes it:** 4.7 (unrealised value), 6.1 (the statement), 6.4
  (contribution), 4.11.
- **One definition:** `core/ledger.py`, `basis(events, asset, *, book)`.
- **Decided (the operator): average cost.**
  - A buy adds what it gave, at the marks recorded in its fill (P3).
  - A sell removes basis in proportion to the units it sells.
  - Every asset is held this way, USDG and ETH included. So a move in USDG's
    own mark is value, realised or not, rather than a gap nothing explains.
  - The basis a disposal removes is rounded half-even to 10⁻³⁰ USD. Every other
    ledger figure is exact, and an inexact step raises.
- **Decided (the operator): a fee is not basis** (P8).

### P7. Realised and unrealised value

- **Who computes it:** 4.7, 6.1, 6.4 and 4.11.
- **One definition:** `core/ledger.py`.
  - `realised(events)`: each sale's proceeds, at the marks recorded in its
    fill, less the basis it removes.
  - `unrealised(events, snapshot)`: each holding at the snapshot's mark, through
    `valuation.value`, less its basis.
- **Rules:**
  - paper and real are never added together (SIMPLIFICATION 6.1, "a blended
    NAV");
  - over a closed weekend marks are frozen, so both are near zero, and nothing
    is claimed as P&L (SIMPLIFICATION, item 5);
  - per book, NAV = what opened it + realised + unrealised − costs, exactly.
    Inference is an expense beside it, never in a NAV (P8).

### P8. Ledger events that are not fills

- **Who computes it:** 4.6 (the ledger records them), 4.7, 4.11 (the fixture
  holds all three), 6.1 (costs and expenses), 6.3.
- **One definition:** the one fold in `core/ledger.py` that every reader of P4
  to P7 derives from. It applies each event in the order the ledger holds them:

  | Event | Book | Holdings and cash | Basis | Value |
  |---|---|---|---|---|
  | Opening balance | named | + the amount | + its worth at the recorded mark | none: what opened the book |
  | Fill (P3) | by its mode (P9) | − given, + got | given: − its average cost; got: + the fill's value | realised += value − the basis given up |
  | Fee | named | − the amount paid | − the average cost of what paid it | cost += its worth at the recorded mark; realised += that worth − that basis |
  | Inference | real | none | none | expense += its USD |

- **Rules:**
  - **a fee never counts toward basis** (the operator): it is its own cost
    line, as 6.1 shows it, so no dollar is counted twice. Paying it disposes of
    what paid it, at average cost;
  - inference is paid from LLM credits, which neither book holds, so it touches
    no holding and no NAV. It is an expense, real.

### P9. Paper and real: which book an event belongs to

- **Who computes it:** 4.7 and 6.1 (never added), 6.2 (real holdings only), the
  planner (paper only), 4.11.
- **One definition:** `ledger.book_of(event)`: a fill by its mode, `paper` or
  `live` to the `paper` or `real` book, and an opening or a fee by the book it
  names. Every reader of events takes `book=` with no default, and no function
  returns a figure summed across books.
- **Why it matters now:** P5's decision makes paper cash and live cash the same
  asset, USDG. Without the book in the signature, every consumer would filter
  its own way.

### P10. A book's NAV, and which holding is cash

- **Who computes it:** 4.7, 4.8 (the next cycle plans from the ledger), 4.11,
  6.1.
- **One definition:**
  - `cash.cash_leg(snapshot)`: the one test of which asset is cash, USDG. Every
    other holding is a position, ETH included;
  - `cash.nav(cash_usd, values)`: a book's NAV, its cash plus each position's
    worth, exact. `plan.book` and `ledger.value` both call it;
  - `ledger.value(events, *, book, snapshot)`: the book's cash and positions at
    the snapshot's marks, each with its basis, and its NAV;
  - `ledger.planner_book(events, snapshot)`: the paper book as `plan.book`
    takes it, stocks and a USD cash figure. `plan.book` raises on an address
    outside the snapshot's assets, so ETH never reaches the planner.
- **Rule:** a holding with no usable mark refuses, as `plan.book` does. No value
  is never a value of zero. What the cycle then signs is S12's, at 4.8.

### P11. Cash partway through a decision

- **Who computes it:** 4.4 (the floor, each time it admits an order), 4.5, 4.11.
- **The two definitions it reconciles.** `cash.cash_after` credits a sell at
  its Chainlink mark: a projection, made before anything fills. A paper fill
  credits the USDG its quote returns: what was booked. Once one order has filled,
  a floor check that used either alone would be wrong: the projection ignores
  what the fill really got, and booked cash ignores what is still to come.
- **One definition:** `gates.settle(plan, approved, …, booked_usd, filled)`.
  The orders already filled count at what they booked, which is in
  `booked_usd` (P5, `ledger.cash_held`). The approved orders not yet filled count at `cash_after`'s
  projection. A filled order is never projected again and never dropped.
  Orders run in the plan's order, sells first, so every buy is judged against
  the sells' booked proceeds, not their marks.
- At decision time nothing has filled. `settle` is called as before, from the
  plan's own cash, and a recorded decision is unchanged.

### P12. An order the chokepoint refuses

- **Who computes it:** 4.3 (the state), 4.4 (the refusal), 4.9 (startup).
- **One definition:** `prepared → refused` in P1's table, with the chokepoint's
  reasons as its `state_reason`. `refused` is final. Nothing was sent, so no key
  was spent and no fill can arrive. `failed` stays what PLAN §4 says it is: an
  evidenced failure after sending.
- **Left to 4.9:** a `prepared` order found at startup was never sent. It is
  admitted again, or refused.

**What 4.0 delivers:**
- `core/orders.py` and `core/ledger.py`, pure and stdlib-only like the rest of
  `core/`;
- `OrderState.REFUSED`, `cash.cash_leg`, `cash.nav`, and `gates.settle` taking
  what has filled;
- `tests/test_orders.py` and `tests/test_ledger.py`, with every rule above
  broken in a copy.

No unit consumes the order and ledger primitives yet. The boundary test gains
the lines that keep each of the five new values in one place:
- no module outside `core/ledger.py` reads a fill's legs or decides an event's
  book;
- no module outside `core/cash.py` tests which asset is cash;
- no module outside `core/orders.py` moves an order's state.

---

## The units, at the approved minimal scope

Each with: goal · what gets built · the artifact · done when · risk · the full
version in one line. Rows are `SIMPLIFICATION.md`'s, adjusted where the record
has moved since.

### 4.1 Mandate · H
- **Goal:** the treasurer refuses anything outside a mandate the operator
  approved.
- **Build:** `treasurer/mandate.py` loads `config/mandate.json` and refuses to
  load it with a null or **placeholder** required field. Today's
  `approved_by`, `approved_at` and `expires_at` say "PROVISIONAL", and
  `allowed_assets` is the 06:01Z capture's 20. It checks:
  - the chain and the wallet;
  - allowed assets;
  - the per-trade limit;
  - expiry;
  - the revoked flag;
  - the cumulative live budget, which stays null until Phase 5 and blocks only
    the live leg.
- **Artifact:** the loader and `tests/test_mandate.py`.
- **Done when:** a placeholder refuses, an expired mandate refuses, and the
  approved one loads.
- **Operator:** the approval values, and whether `allowed_assets` becomes the
  35 markable stocks with ETH and USDG (SIMPLIFICATION's proposal).
- **Full:** a versioned mandate, with approvals hashed and replayed and
  cumulative use tracked.

### 4.2 Intent · H, equal in substance
- **Goal:** exactly the approved orders, in order, each with its stable key.
- **Build:** `treasurer/intent.py` reads a signed decision and lists its
  approved orders with `order_id` and `idempotency_key` (P2).
  - It refuses a record whose envelope does not verify **against the fund's
    configured public key**, not the key the envelope names (S13).
  - `config/keys.json` (new) holds the published public key.
- **Artifact:** the intent builder and its tests, on the 3.8 fixture's
  record.
- **Done when:** the fixture's six approved orders come out in order with
  stable keys, and an unsigned, altered, or foreign-signed record refuses.
- **Full:** ordered orders, fresh mandate validation, a stable key.

### 4.3 Order states · H, equal in substance
- **Goal:** every order's state is durable before the act it describes.
- **Build:** `store/orders.py` and `store/schema.sql`: one SQLite table,
  written only through P1's `transition`.
- **Artifact:** the store and `tests/test_orders.py` (the store half).
- **Done when:** each transition is persisted before its act, an illegal one is
  refused, and an `unknown` order keeps its key across a reopen.
- **Full:** PLAN §4 whole, with reservations and buys waiting for confirmed
  proceeds.

### 4.4 Chokepoint · H
- **Goal:** one function every submission passes.
- **Build:** `treasurer/execute.py`, `admit(order, record, …)`:
  - the order is in the signed record, and the signature verifies against the
    configured key (S13);
  - the mandate allows it: **both legs traded**, not only the labelled asset
    (S10);
  - the gates pass again, on a fresh quote, by the order's side (the buy and
    sell paths of 3.4 and S8);
  - **the snapshot is not too old** at decision and at submission (S11):
    - a new gate, `snapshot-age`, in `gates.py`;
    - the limit is new config;
    - a Saturday snapshot is refused after Monday's open, when divergence
      becomes a veto again;
  - the floor holds on what is still approved (`gates.settle`);
  - a sell does not exceed what is held (P4).
- **Artifact:** the chokepoint, and six regression vectors, each a known-bad
  order refused by name.
- **Done when:** all six refuse by name, and the 3.8 fixture's approved orders
  pass on fresh fake quotes.
- **Full:** a chokepoint with a full regression suite.

### 4.5 Paper executor · H
- **Goal:** a stock leg fills on paper, through the interface the live
  executor will use.
- **Build:** `treasurer/execute.py`'s paper executor: `paper_fill` (P3) at a
  fresh quote, the state moved by P1, and one ledger event per fill, marked
  paper.
- **Artifact:** the executor and its tests.
- **Done when:** an admitted order fills at the quote's amounts, is booked
  once, and a second call with the same key books nothing.
- **Full:** the same, with partial fills and a slippage model.

### 4.6 Ledger · H
- **Goal:** everything that moves value is an event, appended and never edited.
- **Build:** `store/journal.py`, an append-only SQLite table: opening balance,
  fill (paper, or live from Phase 5), fee and inference cost. Chain events will
  carry chain id, tx hash, log index, block, raw units and decimals (Phase 5).
- **Artifact:** the ledger and its tests.
- **Done when:** events append, an edit or delete is refused, and P4 to P7 read
  it back.
- **Full:** every event type: transfers, credit purchase and consumption,
  marks.

### 4.7 Positions · H, equal
- **Goal:** positions and their value, derived and never written.
- **Build:** `store/positions.py`, over P4 to P7, valued only by
  `valuation.value`.
- **Artifact:** positions and their tests.
- **Done when:** a position rebuilt from the ledger equals the hand sum, with
  paper and real kept apart.
- **Full:** the same.

### 4.8 ▶ Paper cycle · L · shown, not stopped
- **Goal:** one command from a capture to positions.
- **Build:** `run/cycle.py` and `make cycle-demo`:
  - the 3.8 fixture's recorded reports and quotes;
  - the decision;
  - intent, admit, paper fills, the ledger, positions.
- **S12, carried:** when a holding cannot be priced, the cycle still signs a
  no-rebalance record that says why, instead of stopping with none (owned with
  3.7).
- **Artifact:** `make cycle-demo`.
- **Done when:** it runs offline to positions, and a second run from the new
  holdings plans from them.
- **Full:** the same, as a stop.

### 4.9 Startup and the lock · H
- **Goal:** no new cycle while an order's fate is unknown, and never two
  runners.
- **Build:** `run/startup.py`:
  - every `submitted` or `unknown` order is resolved before a cycle: re-sent
    with its key (P1, P2), or found;
  - one lock row, and a second runner refuses.
- **Artifact:** startup and its tests.
- **Done when:** an unresolved order blocks a new cycle until resolved, and a
  second lock refuses.
- **Full:** startup reconciliation and a single-owner lock, with the in-flight
  `409` path.

### 4.10 ▶ Crash · H · shown, not stopped
- **Goal:** a crash between writing `submitted` and hearing back leaves no
  double fill.
- **Build:** one offline test on the fake executor: killed after `submitted`,
  restarted, resolved once.
- **Artifact:** the test.
- **Done when:** the order is booked once, under one key.
- **Full:** a live kill mid-submission.

### 4.11 ▶ Known answer · H · **a stop**
- **Goal:** the ledger tells the economic truth on a case worked by hand.
- **Build:** `fixtures/accounting/`:
  - opening capital;
  - two paper buys;
  - one live round trip with its fee, constructed as Phase 5 will record it;
  - one inference cost.

  The x402 sale is Phase 7's, and joins at 6.1 as SIMPLIFICATION planned.
  Positions, cash, basis and value (P4 to P7) are checked against a hand
  computation.
- **Artifact:** the fixture, the hand computation and the test.
- **Done when:** every figure matches to the unit. **Shown at a stop,** and
  waits for the operator.
- **Full:** a partial sale, an external transfer, reverted-trade gas, settled
  and unsettled revenue, credits bought and consumed.

### 4.12 Treasurer process · H, equal in substance
- **Goal:** spend authority lives in one process, and nothing else can reach
  it.
- **Build:**
  - the treasurer runs as its own process, holding `BANKR_KEY_EXEC` and
    `SIGNING_KEY`, and reads approved intents from SQLite. `treasurer/sign.py`
    already runs as a process; this moves execution with it;
  - **`.env` split per role,** so the analyst side cannot read the treasurer's
    file. This is open item 3: `config.load()` merges the whole `.env`;
  - tests: both keys are unreadable from every agent's environment, and each
    agent key is refused a swap, live and authorized once. No agent keys exist
    while 2.0's choice is open, so today that is `BANKR_LLM_KEY` and
    `BANKR_KEY_READ`.
- **Artifact:** the process, the split, and the isolation tests.
- **Done when:** each is shown, the refused swaps included.
- **Full:** the same on a deployed host behind an IP allowlist.

---

## Batches, and where the stop falls

| Batch | Units | Why together | Ends |
|---|---|---|---|
| **A** | 4.0 | The definitions every later unit calls. Built alone, so nothing else is computing the same values while they are. | Shown |
| **B** | 4.1 → 4.2 → 4.3 → 4.4 → 4.5 → 4.6 → 4.7 → 4.8 | Each consumes the one before: mandate, intent, state, admission, fill, ledger, positions, the cycle. Every shared value is 4.0's, so no two units define one. | 4.8, shown |
| **C** | 4.9 → 4.10 | Recovery over the states 4.3 writes and the fills 4.5 books. | 4.10, shown |
| **stop** | **4.11** | The known answer: every primitive, checked by hand. | **Waits for the operator** |
| **D** | 4.12 | It moves keys and splits `.env`: spend authority, with a live refused-swap test that needs authorizing. It goes after the stop, so the ledger is known-good first. | Shown |

**Not batched across a stop.** Batch B could be split at 4.4, since admission
is the most consequential unit, if the operator wants to see it before fills are
booked.

---

## Decisions, made by the operator on 2026-09-19

| # | Decision | Applied at |
|---|---|---|
| 1 | **Cost basis:** average cost. A fee is not basis (asked and answered at 4.0). | 4.0 (P6, P8) |
| 2 | **Paper cash:** USDG units, valued at USDG's own mark, not assumed to be a dollar. | 4.0 (P5) |
| 3 | **The mandate:** approved by the operator, expiring 7 days after approval; `allowed_assets` the 35 markable stocks plus ETH and USDG. | 4.1 writes `mandate.json` |
| 4 | **The published key:** `config/keys.json`, the public half only: `1c232435…`, as both 3.8 envelopes show. | 4.2 (S13) |
| 5 | **S11's limit:** a snapshot at most 15 minutes old, at decision and at submission. The 17:13Z decision came 11 hours after its snapshot; the exit run's, about 2 minutes. | 4.4, as gate set 2 |
| 6 | **4.12's refused swaps:** authorized. | 4.12 |

---

## Open items the record already holds for Phase 4

| Item | Where | Unit |
|---|---|---|
| The mandate's approval and expiry are placeholders; `allowed_assets` is provisional | `config/mandate.json`, LESSONS 2026-09-19 | 4.1 |
| **S10:** the mandate gate checks the labelled asset, not the legs traded | LESSONS, the sweep | 4.4 |
| **S11:** the snapshot's verdicts have no age limit | LESSONS, the sweep | 4.4 |
| **S12:** one unmarkable holding stops the cycle with no signed record | LESSONS, the sweep | 4.8, with 3.7 |
| **S13:** "authorizes" checks the envelope against the key it names | LESSONS, the sweep | 4.2, 4.4; publishing is 7.1 |
| `config.load()` merges all of `.env` into the caller | LOGS open item 3 | 4.12 |
| `cumulative_budget_usd` and `confirmation_depth` are null | `config/` | Phase 5 (5.2, 5.3) |
| 4.11 is a stop, but `CLAUDE.md`'s list does not say so | the operator, 2026-09-19 | `CLAUDE.md`, owed |
| S10 against today's mandate refuses every buy: USDG, the leg a buy sells, is not in it | the orientation, 2026-09-19 | 4.1's mandate, before 4.4 |
| A quote matches an order in two shapes: `gates.fresh_quote` on the record's plan, `orders.quote_is_for` on an `Order` | 4.0 | 4.4 calls `quote_is_for` |

## What Phase 4 ends with

`make cycle-demo` takes the committed capture and the 3.8 cycle's recorded
reports to:
- a signed decision;
- orders written before they are acted on, admitted by one chokepoint;
- paper fills at fresh quotes;
- a ledger, and positions derived from it.

Every value computed in more than one place is computed once, in `core/`. The
known answer at 4.11 holds, and the treasurer runs alone with the only keys that
can spend.

**Still not there:**
- a trade on chain (Phase 5);
- books with revenue (Phase 6);
- a sale (Phase 7);
- a page (7.6).
