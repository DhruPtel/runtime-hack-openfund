# Simplification plan: Phases 2 to 8

**Status: a proposal, awaiting the operator.** Written 2026-09-19, after the
Phase 1 gate, with the deadline about 16 hours away. Nothing in it is built.
PLAN, ROADMAP, PHASE-0-1 and `config/` are unchanged. If it is approved, the
folds are listed in the last section.

Where this and `PHASE-1-GATE.md` §5 disagree, this wins. The gate cut units;
this keeps every unit and cuts its depth.

## In short

- **Every unit in Phases 2 to 8 is kept.** Each is built at reduced depth. Its
  full version is recorded here so it can be built later.
- **What stays whole:**
  - live pricing on 4663 (built);
  - four analyst processes, each on its own Bankr account, reading one frozen
    snapshot;
  - a deterministic aggregator;
  - a risk agent that reads every report and can veto;
  - the treasurer as the only writer and the only signer;
  - a real transaction on 4663;
  - a signed decision record sold over x402;
  - a page.
- **The security floor does not move.** No agent key can transact or sign.
  Orders are written before they are sent. The chokepoint refuses anything
  outside the signed record or the mandate. Secrets stay redacted. What goes is
  ceremony: mandate hash-and-replay, a separate deployed host, and
  exhaustive regression suites.
- **Q1:** repoint the fourth seat to **price integrity**: can this asset's mark
  be trusted today? The snapshot already holds three prices per asset, and no
  seat asks that question.
- **Q2:** in a closed session no market-data veto fires on the tradeable names.
  Build the risk moment on the five closed-session divergence findings. The
  venue's own price is the third witness: it sides with the market on two of
  them and with the frozen mark on three.
- **Q3:** five new Bankr accounts, one read-only gateway key each, each funded
  with its own LLM credits. The agents exist, are identified and pay for their
  own inference. They do not transact and do not sign.
- **Build order:** five stages. Each ends in something a judge could watch. At
  the record's pace the plan does not fit in 16 hours, so the order decides what
  exists when time runs out.

---

## How depth is cut

- **Scope.** The main path is handled. Each unit states what it does not cover.
- **Verification** follows `CLAUDE.md`. Units marked **H** touch money, identity,
  spend authority or the signed record. They keep the discipline: break the rule
  in a copy and show a test fail. Units marked **L** need a passing test only.
- **Output.** Reports are a summary and a few key values. Books are a NAV and
  four lines.
- **Edge cases.** Handled if likely. Recorded here if not.
- **Stops.** Five review stops, one at the end of each stage, replace the 21
  remaining ▶ checkpoints. The rest are shown, not stopped.
- **Records.** Each decision is written once. The other documents point at it.

---

## The three answers

### 1. The fourth seat: repoint it to price integrity

**Recommendation: repoint `fundamentals-calendar` to `price-integrity`.** Its
question: can this asset's mark be trusted today?

- **Dropping to three is out.** The brief keeps four analysts in parallel.
  Three would be a different demonstration.
- **A frozen source is out for now.** It needs a new adapter, a capture so
  replay (1.9) still holds, and a cost. The record names no source (gate §5).
  In 16 hours it would crowd out Phase 4.
- **Why price integrity.** For every asset the snapshot already carries three
  prices, and no seat asks whether they agree:
  - the Chainlink mark, with its round time, freshness and pause flag;
  - GeckoTerminal's price, 24h volume and divergence;
  - the venue's price inside the $25 quote (`quote.venue_price_usd`).

  `price-trend` asks direction. `execution-quality` asks cost.
  `cross-asset-macro` asks co-movement. None asks whether the mark is right. The
  question is disjoint from the others, and everything it cites is in the frozen
  snapshot, so invariant 2 holds.
- **It is the question a closed session raises** (Q2).
- **What is lost:** no seat reasons about the company, meaning earnings,
  filings or events. The fund cannot claim fundamental research. The full
  version is still a frozen events source, captured into the snapshot.
- **Cost:** the same as any seat, at most 1.8a's $0.264 a call.
- **Change after approval:** the seat's id and objective in
  `config/analysts.json`, whose status already says "revised at checkpoint 2.1".

### 2. What the risk gate can do in a closed session

Read from the committed weekend capture, `66852293-253315c0e691`, and the
record.

**Rules already built, at the snapshot:**

| Rule | Fires in a closed session? | Evidence |
|---|---|---|
| identity, standing, beacon | Only if the world changes | 0 of 35 |
| paused | Only on a real pause | 35 of 35 false at two weekend blocks (1.11) |
| freshness | No. Closed time does not count. A holiday would. | All 35 fresh |
| history | Only on a short series | SPCX once (1.7) |
| **corroborator line** | **Yes** | 15 of 35 excluded, in both weekend captures |
| divergence | No veto, by DECISION (LESSONS 2026-09-18). A finding past 100 bps. | **5 findings on tradeable names:** AMD, AMZN, GOOGL, MSTR, SGOV |
| quote, size, impact | Rarely at $25 | The 20 tradeable names: impact 21 bps at most, against 50. Every name over 50 sits below the line (four at 1.5, six in this capture), so none reaches a plan. |
| quote age (60 s) | **Yes, if nothing re-quotes** | Quotes are 0–20 s old at `built_at`. Analysts take 46–75 s (1.7, 1.8). Every snapshot quote is past the limit by the time a plan exists. |

**Rules still to build**, which ignore the session: position weight, turnover,
cash floor, quorum, the mandate (allowed assets, $25 per trade, budget,
expiry), and the context budget.

**The risk agent's own veto** can fire on anything it reads.

**Recommendation: build the risk moment around the five divergence findings.**
The venue's price is the third witness. Computed from two fields the capture
carries (not a recorded finding):

| Asset | GeckoTerminal vs mark | Venue vs mark | Reading |
|---|---|---|---|
| AMD | about 1.0% below | 1.3% below | The venue agrees with the market. The feed froze and the price moved. |
| MSTR | 1.9% above | 1.3% above | The same. MSTR tracks bitcoin, which trades all weekend (LESSONS 2026-09-18). |
| AMZN | 4.7% above | within 0.23% | The venue agrees with the mark. The corroborator is the outlier, as the AMZN entry in LESSONS already suspects. |
| GOOGL | 1.3% above | within 0.12% | The corroborator is the outlier. |
| SGOV | 1.2% below | within 0.22% | The corroborator is the outlier. SGOV is a T-bill fund. |

- **What a buy of AMD or MSTR would do.** It would be booked at a mark about 1.3%
  away from the price paid. A buy of AMZN would not.
- **The fixed rule stands down by decision.** Telling the two cases apart is the
  judgment the finding was carried to the record for ("we saw it and judged it
  expected"). The `price-integrity` seat names the case per asset. The plan
  carries the three prices beside each order. Risk approves or vetoes with the
  reason. That is substantive, not staged.

**Caveats, stated rather than rounded up:**
- A live cycle may not propose any of the five names, and a model veto is not
  reproducible. Identical calls differ (F1.7.1).
- So the demo shows the veto from a recorded cycle (replay from recorded
  outputs, invariant 7) and runs a live cycle with whatever verdict it gives.
  Both are labelled.
- The venue comparison is one capture's reading. The venue is not independent of
  execution; LESSONS 2026-09-17 calls quote-versus-feed the weaker check.
- It stays evidence in prose and does not become a fixed gate. A fixed
  closed-session veto on divergence would reverse the operator's DECISION of
  2026-09-18. That is the operator's call and is not proposed here.

**The fixed gates seen firing in every demo cycle:**
- the corroborator line, with 15 names that never reach the plan;
- the mandate and position gates on the sized plan;
- the route of every stock leg to paper. Each stock quote's `executable` is
  null (location-gated, F0.5.1), and null blocks (invariant 5). 0.5's recorded
  403 is the evidence (5.6).

### 3. A Bankr wallet per agent: what it takes

**One Bankr account is one wallet.** All three of the fund's keys resolve to one
address (F0.2.3). A wallet per agent therefore means an account per agent: the
four analysts and risk. That is **five new accounts**. The treasurer keeps the
fund's wallet, `0x93fa…a3da`. The aggregator and planner are code, not agents.

- **Account creation.** Not in the record. It is the operator's step, repeated
  five times. The record does not say whether one person may hold several
  accounts, or what each sign-up requires. Check that first.
- **Keys.** One per account, set at `bankr.bot/api`:
  - Read Only ON, LLM Gateway ON, Agent API OFF. That is today's
    `BANKR_LLM_KEY` scope.
  - The Agent API must stay off. It carries `/agent/sign` and `/agent/submit`
    (`research/bankr-claude.md`), a signing path.
  - Its toggle cannot be read back (F0.2.5), so "off" is asserted in code: no
    call to `/agent/*`, as `test_boundaries.py` already asserts for
    `/agent/prompt`.
  - Five new rows in `credentials.py`, each loadable only by its own role.
    Redaction covers them automatically, as 0.1 proved for a credential added
    later.
  - Proposed names: `BANKR_KEY_PRICE_TREND`, `BANKR_KEY_PRICE_INTEGRITY`,
    `BANKR_KEY_CROSS_ASSET`, `BANKR_KEY_EXECUTION_QUALITY`, `BANKR_KEY_RISK`.
- **Funding.** Each agent calls the gateway, and credits are wallet-scoped
  (F0.6.6). So each account needs its own credits:
  - Credits are bought from the wallet in USDC on Base. The one purchase on
    record paid $3.00 and credited $2.825608, a 5.81% difference (F0.7b.10).
  - This is an operator action in each account, not an agent action.
  - No ETH is needed, because inference is not on chain.
  - Estimate: about $5 per analyst and $2 for risk. That is about 18 analyst
    calls each at $0.264 (1.8a) after the overhead, and about 38 risk calls at
    $0.05 (1.7). That leaves room for a dozen cycles plus retries and
    development runs.
- **Transact or only exist? Only exist, be identified, and pay for their own
  inference.**
  - **Exist:** an address. Each agent reads its own from `/wallet/portfolio`
    with its read-only key (F0.2.2 shows such a key can read the Wallet API).
  - **Be identified:** each report carries its seat's address. The provider
    bills the call to that account. So per-agent cost is provider evidence,
    not our estimate. F0.6.4 found attribution per key only, and now there is
    one key per agent.
  - **Pay:** credits are debited per call. That is off chain.
  - **Never sign or transact.** Either would need a write-capable key or the
    Agent API inside an agent process. That breaks invariant 1 and this
    brief's security floor. Each report is bound to its agent by the fund's
    ed25519 signature over the report's hash and the seat's address. The
    agent does not sign it.
- **What it buys:**
  - §13's "one Bankr account" limitation shrinks. The agent keys no longer
    live in the account that holds spend authority, so a leaked agent key
    reaches only that agent's credits. The snapshot's `BANKR_KEY_READ` still
    shares the fund's account.
  - Per-agent cost becomes measured.
  - The page can show each agent's address and balance.
- **Proven once per key, live (H):**
  - it reaches the gateway;
  - it reads its own, distinct address;
  - it is refused a swap.

  The refusal is a write attempt and needs one authorization. It must be shown
  to be the read-only toggle and not an empty wallet: probe 0.5 checked the
  balance first to exclude that confound.
- **Full version:**
  - Agents paying each other: the treasurer buys each report over x402. The
    payer needs USDC but no gas (EIP-3009, `research/x402-cli-example.md` §6).
  - Agent-signed reports, with a key held in the agent's own process.

  Neither is needed to show the structure.

---

## Units

**Legend.** **H**: money, identity, spend authority or the signed record. Break
it in a copy and show a test fail. **L**: a passing test. **= equal**: the unit
cannot be reduced without becoming something else. **Full** points at PLAN §8,
which holds the complete description. The line here is what matters for building
it later.

### Phase 2: analyst contract and fan-out

| Unit | Minimal: what gets built | Full: recorded | Given up |
|---|---|---|---|
| **2.1 ▶** Format · L | The format below. Two seat kinds, a three-sentence summary, up to eight calls, and field paths whose values code fills in. Approving this document approves the format, so the 2.1 stop is spent here. | Sections, depth, evidence citation, conviction told from speculation. Hand-written and approved at its own stop before code. | Depth. A report is a view with its key numbers, not research. No horizon per call, and no "what would change my mind". |
| **2.2** Schema · L | One validator: required fields and types; the call from its seat kind's set; confidence 0–1; every asset address in the snapshot's tradeable set (tickers never resolve an asset); every field path present in the snapshot; the snapshot hash echoed back and equal. A failure is a named rejection. | Hard validation of every field; out-of-scope assertions refused per seat; address-scoped claims (§9 analyst contract). | Scope enforcement per seat. Numbers in the prose are the model's and are not checked. Only the key-values table is the snapshot's. |
| **2.3** Brief · L | One versioned file, `briefs/analyst.v1.md`: the seat's question from `analysts.json`, the rules 0.9's brief states, the schema, and the snapshot's bytes. Every seat sees the whole universe and differs in question. | Mandate, explicit scope boundaries, snapshot bytes, schema, effort scaling; assets partitioned in config. | Asset partitioning and effort scaling. Overlap is prevented by question only. |
| **2.4** Runner · L; isolation **H** | Four analyst processes started in parallel. Each environment holds only its own key. The snapshot is passed as a file. Worker deadline 630 s and transport 600 s (set). One retry on a malformed reply, then a failed worker. A partial-failure flag. Every step writes an event to the cycle's log, which the page reads. | Bounded width, per-worker deadline, transport timeout, retry budget, pre-allocated slots, per-worker fallback, partial-failure disclosure. | Fallback models, and retry budgets beyond one. A timed-out call is still billed (F0.9.3). It is recorded as spend with no report, and nothing tries to cancel it. |
| **2.5** Tokens · L | Each call records the response's `usage` block, the price at the published rate, and its own account's `/v1/credits` before and after. 0.9 found the rate, the usage block and the balance agreeing to the last digit. | Per-call counts reconciled to `/v1/usage` in settled windows, aggregate to aggregate (F0.6.4, F0.9.2). | `/v1/usage` reconciliation. A balance delta assumes nothing else spends from that account, which holds while only the agent uses it. |
| **2.6 ▶** First report · L | One analyst call on the committed snapshot, shown on the page with cost and latency. It can run before the agent accounts exist, on the fund's own key ($0.937 covers about three calls), labelled as such. | A stop to judge the gap from 2.1. | The stop. Whether a report is worth paying for moves to stage A's review. |
| **2.7** Store · L | Each report written once as canonical JSON named by its sha256. Writing an existing name must match or it fails. | Content-addressed store in SQLite (PLAN §5). | SQLite and queries. Files are enough for one runner. |
| **2.8 ▶** Drill · L | Three offline tests on a fake gateway: malformed, hung past the deadline, and `NO_CALL`. Each cycle completes with the failure named in its log, and the page shows a failed seat. | A live drill of all three. | A live drill. Quorum is set without watching one. |

### Phase 3: aggregation, planning, risk

| Unit | Minimal | Full | Given up |
|---|---|---|---|
| **3.1** Aggregator · L, invariant 6 tested | A total function, as in "The report format". Below quorum, or with every seat abstaining: no rebalance, holdings kept. Positive scores become weights, capped at the position limit; the remainder goes to cash, ties break by address, and the residual is shown. | Equation, confidence scale, horizon, quorum, cash weight, tie-break, rounding residual. | Horizon, and weighting seats unequally. Confidence is taken at face value. |
| **3.2 ▶** Table · L | A page panel: seats by assets, contributions, weights, cash, residual. Shown, not stopped. | The same, as a stop. | The stop. |
| **3.3** Planner · **H** | Weights times the paper capital, less paper holdings, into orders of at most $25; orders under $1 dropped. **Each order is re-quoted when the plan is written,** because the snapshot's quotes are past 60 s by then (Q2). Each order carries its quote, `minBuyAmount`, and the asset's mark, corroboration, venue price and findings, so risk sees them. It adds the live leg (below). | Weights, reconciled holdings and reservations into sized orders with live quotes, age, fees, minimum proceeds and projected holdings. | Reservations, dependent orders and projected holdings. Orders run one at a time, so there is nothing to reserve against. |
| **3.4** Gates · **H** | `core/gates.py`: named checks over the plan, each true, false or null, with null blocking. The checks: tradeable in the snapshot, allowed by the mandate, quote age, signed impact, order size, position weight, cash floor, quorum, context budget. Risk and treasurer call the same function. The three named exceptions are called from it, not moved into it. | A declarative, fail-closed array, the single definition of every limit, with the three exceptions swept in as one move (CODEBASE §3). | The sweep. Each of the three comparisons is still defined once, from config. The boundary test keeps naming them, and invariant 4's "until 3.4" becomes permanent until the full version. |
| **3.5** Risk · model L; override rule **H** | A fifth process on its own account. It reads every report in full and the plan with its evidence, and returns approve or veto per order with one sentence each, plus an overall verdict. In code, any failed or null gate is a veto whatever the model says. The model may veto what the gates pass, never the reverse. | Full reports and the sized plan in, a verdict out; model text cannot override a fixed gate. | Nothing structural. The verdict is short. |
| **3.6** Context budget · L | The bundle is measured before the call, conservatively from its bytes, because the gateway has no token-count endpoint (F1.7.2). Over budget is a veto, never a summary. | An exact budget over reports, plan and risk output (invariant 3). | An exact count. The estimate errs toward vetoing. |
| **3.7** Record · **H**, = equal | Canonical JSON with the sha256 of the snapshot, every report, the config, the proposal, the plan, the gate results and the risk output. Every closed-session finding is carried. It is signed ed25519 by the treasurer's key, and `signed=false` never authorizes. One pinned dependency, `cryptography`, is added. | The same. | Nothing. This is what is sold. A thinner record is a different claim. |
| **3.8 ▶** A veto · **H** (gate half) | Built as Q2 says: `price-integrity` names the case, the plan carries the three prices, risk decides, and the fixed gates that fire are shown too. Shown at stage A's review, from a recorded cycle if the live one does not veto. | A cycle where divergence, quote age or unknown impact trips a fixed gate. | A fixed divergence veto in a closed session, by DECISION. A live veto is not guaranteed; the recorded one is replay. |
| **3.9 ▶** Replay · **H** | One test. A recorded cycle's decision record is rebuilt byte for byte, with no network, from its capture (1.9), its recorded reports, plan quotes and risk output. | The same, as a stop. | The stop. The treasurer's side is not replayed. |

### Phase 4: treasurer (paper) and the journal

| Unit | Minimal | Full | Given up |
|---|---|---|---|
| **4.1** Mandate · **H** | `mandate.json` loaded, and refused if a required field is null. It checks the chain, wallet, allowed assets, per-trade limit, cumulative live budget, expiry and the revoked flag. Values are proposed below. | A mandate with version, approval, expiry, revocation and cumulative use tracked. | Hash-and-replay: approvals are not hashed and replayed, and versions are not diffed. The treasurer still refuses anything outside the mandate. |
| **4.2** Intent · **H**, = equal in substance | The approved orders, in order, from the signed record. Each has an idempotency key from the decision id and the order's index, sent as Bankr's `idempotencyKey`, which deduplicates (F0.10.1). | Ordered orders, fresh mandate validation, stable key. | Nothing that prevents a double spend. |
| **4.3** Order states · **H**, = equal in substance | SQLite, one table: prepared, submitted, unknown, confirmed, failed, each written before the act it describes. An unknown order never gets a new key. | PLAN §4 whole, with reservations and buys waiting for confirmed proceeds. | Reservations and dependencies. Orders run one at a time. |
| **4.4** Chokepoint · **H** | One function every submission passes: the order is in the signed record, the signature verifies, the mandate allows it, and the gates pass again on a fresh quote. Six regression vectors, each a known-bad order refused by name. | A chokepoint with a full regression suite. | Breadth of vectors. |
| **4.5** Paper executor · **H** | The live executor's interface. A stock leg fills at a fresh quote's amounts, and the journal event is marked paper. Stock legs route here because each stock quote's `executable` is null (F0.5.1). | The same. | Partial fills and a slippage model. A paper fill is the quote. |
| **4.6** Journal · **H** | Append-only events: opening balance, fill (paper or live), fee, gas, x402 settlement, inference cost. Chain events carry chain id, tx hash, log index, block, raw units and decimals. | Every event type: transfers, credit purchase and consumption, marks. | External transfers, credit purchases, and marks as events. Marks come from the snapshot. |
| **4.7** Positions · **H**, = equal | Derived from the journal, never written directly. Valued only by `core/valuation.value()`, which exists. | The same. | Nothing. |
| **4.8 ▶** Paper cycle · L | `make cycle-demo` runs the committed capture through reports, weights, plan, verdict, signed record, paper fills and positions, on the page. | The same, as a stop. | The stop. |
| **4.9** Startup, lock · **H** | Before a new cycle, every order left submitted or unknown is resolved: re-sent with its key, which Bankr deduplicates, or found on chain. One lock row; a second runner refuses. | Startup reconciliation and a single-owner lock. | The in-flight `409` path (F0.10.1) is treated as unknown and left to the next start. |
| **4.10 ▶** Crash · **H** | One offline test on the fake executor: killed after `submitted` is written, restarted, resolved once. | A live kill mid-submission. | A live kill. The claim is "tested against a simulated crash". |
| **4.11 ▶** Known answer · **H** | A fixture: opening capital, two paper buys, one live round trip with its fee, one x402 sale, one inference cost. Its NAV and four lines equal a hand-computed answer. Built in stage D. | A partial sale, external transfer, reverted-trade gas, settled and unsettled revenue, credits bought and consumed. | Those cases. The books are known to count only what the fixture holds. |
| **4.12** Treasurer process · **H**, = equal in substance | The treasurer is its own process holding `BANKR_KEY_EXEC` and `SIGNING_KEY`, and reads approved intents from SQLite. Tests: both keys are unreadable from every agent's environment, and each agent key is refused a swap (live, authorized once, Q3). The signer lands in stage A; execution in C. | The same on a deployed host behind an IP allowlist (PLAN §5). | The separate host. Isolation is by process environment on one machine. Whether the execution key has an allowlist today is not recorded, and this build neither adds nor removes one. |

### Phase 5: live chain activity

| Unit | Minimal | Full | Given up |
|---|---|---|---|
| **5.1** Live executor · **H** | `adapters/bankr_exec.py`, the only signing path, behind the paper interface: `/wallet/swap` with the idempotency key, ETH and USDG only, by the mandate. | The same. | Other assets. |
| **5.2** Round trip · **H**, = equal in substance | One ETH→USDG and one USDG→ETH, about $0.50 each, from what the wallet holds (about $1.21 of ETH), authorized once. USDG→ETH has never run, and its sponsorship is inferred. | A small real buy and sell with production-shaped permissions. | Size, and nothing about the path. |
| **5.3** Receipts · **H** | Confirmed from the `UserOperationEvent` naming the wallet with `success`; amounts from `Transfer` logs to and from the wallet. Never from `tx.from`, the outer status or the nonce (F0.10.3). `success:false` is failed. | Confirmation depth, reorgs, mined reverts, balance-based amounts, the 6 bps. | Reorgs past a fixed depth, and the 6 bps (F0.10.4). A gap shows as an exception in 6.2. |
| **5.4 ▶** Explorer · **H**, = equal | The page links the transaction on the 4663 explorer beside its order row and journal entry, booked once. A review stop: this is the claim. | The same. | Nothing. |
| **5.5** Access lost · **H** | A 401 or 403 from the execution key stops new submissions, keeps holdings and reconciliation, and shows "access lost". One test. | Pause, preserve, expose remediation. | Remediation, and detecting expiry ahead of time. |
| **5.6 ▶** The 403 · L | 0.5's recorded body through a decoder that names the location gate from its prose, and fails closed with the raw body on anything else. Shown as why stock legs are paper. | A live 403 decoded against the seven causes. | A fresh 403. 0.5 measured one, and another proves nothing new. |
| **5.7 ▶** Live cycle · L | One of 8.3's unattended cycles carries the live leg. | A scheduled live cycle as its own stop. | The separate stop. |

**The live leg, a decision the record leaves open.** Nothing on record says what
drives it. The proposal: the planner appends one live order to each cycle that
trades, at a fixed small size and alternating direction, so the wallet
round-trips over two cycles. It is labelled **the demonstration leg**. It proves
the money path, and no analyst decided it. It passes the same gates, risk,
signature and treasurer as every other order. The operator decides.

### Phase 6: books and attribution

| Unit | Minimal | Full | Given up |
|---|---|---|---|
| **6.1** Statement · **H** | **NAV and four lines.** NAV is two labelled figures, never added: real (the 4663 wallet at its marks) and paper (stocks at Chainlink marks plus paper cash). **Revenue:** x402 sales settled on Base. **Costs:** fees and gas on the live leg. **Expenses:** inference, per agent. **Net:** revenue less costs less expenses. | Income statement and portfolio report over sealed inputs, with a versioned policy. | The portfolio report, sealed inputs and versioned policy. |
| **6.2** Reconcile · **H** | At a pinned block, the journal's ETH and USDG against the wallet's RPC balances, and booked revenue against `PaymentSettled`. Each difference is listed as an exception, never absorbed. | Against independent balances and settlement evidence, unresolved items shown. | Credits against usage, which F0.6.6 says cannot be reconciled anyway. |
| **6.3** Cost · L | Per agent, its calls' cost from 2.5, totalled from its own account's balance. | Estimate flags and pricing basis, reconciled to `/v1/usage` in settled windows. | Settled-window reconciliation. |
| **6.4** Contribution · L | For each executed order, the seats whose calls supported it and their share, with a residual. Stock marks are frozen all weekend, so realized P&L is zero and shares are shown, not dollars. | Realized P&L allocated once by executed weight, with a residual. | Dollar attribution until marks move. |
| **6.5** Accuracy · L | Each call stored with the mark at decision time, and scored against a later snapshot, labelled hypothetical and never in profit. Over the demo window it reads "not yet scorable". | Hit rate against a horizon and benchmark. | Any score in the demo. |
| **6.6 ▶** Statement · L | The books panel after real cycles. A review stop, at stage D. | The same. | Nothing. |
| **6.7 ▶** Overlap · L | A test: two seats buying the same asset share its credit once, and the residual reconciles. | Shown as a stop. | The stop. |
| **6.8 ▶** Exception · L | 6.2's exceptions as a panel, with a test that a deliberate mismatch appears. If 0.10's 6 bps shows up live, it is a real one. | Shown as a stop. | The stop. |

### Phase 7: surfaces

| Unit | Minimal | Full | Given up |
|---|---|---|---|
| **7.1** Publisher · **H** | Record bytes written under their sha256, never overwritten. `latest.json` is advanced by rename after the bytes land. The signature is checked before publishing. | Immutable bytes, manifest, atomic pointer, a public path on the runner host. | The manifest and the runner host. Where the public copy lives is the operator's call (below). |
| **7.2** x402 handler · L | The TypeScript handler 0.7d proved, returning `Response.json(record)` for a decision id. $0.25 USDC on Base, no state, no inference. How it holds the full record without that record being free elsewhere: see "What the minimal versions must not claim", item 4. | Resolve `latest` to an id before purchase, then serve by id. | Resolving `latest` in the handler. The buyer asks by id, which the page shows. |
| **7.3** Binding · L | A purchase row from each `PaymentSettled` with the fund as owner: payer, amount, tx hash. | Request, decision id, payer, price, asset, network, delivery status, settlement reference. | Which record a payment bought, and whether it was delivered. `x-402-payer` is platform-asserted (F0.7d.7) and unused. |
| **7.4** Revenue · **H**, = equal | Revenue booked only from `PaymentSettled` on Base with the fund as owner, never from the handler (invariant 9, F0.7b.5). | The same. | Nothing. |
| **7.5 ▶** Purchase · **H**, = equal | A fresh local key with about $1 of USDC on Base and no Bankr account pays through `@x402/fetch` 2.26.0 and receives the record. The sale appears in the books. A review stop: it closes §13's inference (F0.7e.6). | The same. | Nothing. |
| **7.6** Page · L | One static page, HTML and plain JavaScript, no build step. It polls the cycle's event log and the published records, and shows: the basket; four seats deliberating, with their addresses and costs; the aggregation table; the plan; the gates; the verdict landing; the signed record and its buy link; fills with the explorer link; the books. Served locally for the demo, and statically wherever records are published. It grows panel by panel through the stages. | A public page over the same records. | Styling, history beyond recent cycles, and in-browser signature checks. |
| **7.7 ▶** The page · L | Judged at stage E's dry run. | A stop on the page itself. | The separate stop. |
| **7.8** Skill · L | A `SKILL.md` naming the endpoint, the price, and the buyer client: `@x402/fetch` 2.26.0, not the v1 client Bankr's docs name (F0.7e.1). | A manifest other Bankr agents can call. | Testing it with another agent. |
| **7.9 ▶** Recovery · L | Stated, not drilled: a dropped response is paid again to retrieve it, and refunds are manual (§13). A buyer can check the bytes against the id. | Retrieval by id without a second charge. | Free re-retrieval. |

### Phase 8: schedule, demo, submission

| Unit | Minimal | Full | Given up |
|---|---|---|---|
| **8.1** Scheduler · L | `make run`: a loop starting a cycle on an interval, holding 4.9's lock, and skipping if a cycle is running. | Cheap tick, agent turn only when inputs changed, overlap fencing, no permission bypass. | The "inputs changed" test. Every tick is a full cycle at about $1.11. |
| **8.2** Kill switch · **H**, = equal | A file the treasurer checks before each submission. If present, no new submissions; reconciliation continues. | The same. | Nothing. |
| **8.3 ▶** Unattended · L | Three cycles with no hands: one carries the live leg (5.7), and at least one decides not to trade. Stock marks are frozen all weekend, so a second cycle's calls should resemble the first's and a no-rebalance is expected, not staged. | Several cycles, including a no-rebalance. | Duration: hours, not days. |
| **8.4** Script · L | The committed capture for the reproducible part, a live cycle, the purchase, the explorer. | The same. | Nothing. |
| **8.5 ▶** Dry run · L | The demo once, timed. A review stop. | The same. | Nothing. |
| **8.6** Submission · L | Architecture, limitations (§13 updated) and the six judging criteria. | The same. | Nothing, but it is **blocked on the criteria**, which are not in the repository. |
| **8.7 ▶** Read-through · L | Folded into 8.5: page and README read in order after the dry run. | A separate cold read as a judge. | The separate stop. |

---

## What the minimal versions must not claim

Each of these would break an invariant or say something we could not stand
behind.

1. **A blended NAV.** Adding paper stock to the real wallet without labels
   presents paper as capital. NAV is always two figures.
2. **Agent-signed reports.** The agents do not sign. Making them sign through
   Bankr's `/agent/sign` puts a signing path in an agent process (invariant 1).
   The claim is "each report is bound to its agent by the fund's signature".
3. **Paper fills as fills.** A fill is evidenced by a receipt (invariant 9).
   Paper fills are labelled paper everywhere and never counted as trades on
   chain.
4. **"Sells its research" while the full record is free.** PLAN §5 publishes
   records on a public path, the handler fetches from it, and the page reads the
   same records. As written, anyone can read the full record without paying.
   - **Minimal fix:** the public copy is a preview: summary, verdict, hashes
     and signature. The full record is reachable only through the handler.
   - **How the handler holds it:** either bundled into the handler at each
     deploy, or kept at a private URL only the handler knows. Deploys are proven
     (0.7d), but their latency is not measured. Whether x402 Cloud keeps a
     secret is not in the record.
   - The operator's call.
5. **P&L or accuracy over the demo window.** Stock marks are frozen all weekend,
   so any figure would be zero or invented.
6. **"Gates exist once" read as "in one module".** After minimal 3.4, three
   comparisons still live outside `gates.py`. The true claim is "each limit is
   defined once".
7. **"Survives a crash."** It is tested against a simulated crash only.
8. **Numbers in report prose.** Only the key values are the snapshot's.

---

## The report format (2.1)

Proposed. Approving this document approves it.

**Two kinds of seat,** because the record shows one kind cannot speak in the
other's terms. In 1.8's caching test, the `execution-quality` seat was asked for
buy, hold or sell and returned `NO_CALL` on all 35 assets
(`probes/out/analyst_cost_cache.json`, gitignored, in this working copy only).
Its question has no direction. Under one vocabulary, half the seats could only
abstain.

- **Direction seats,** `price-trend` and `cross-asset-macro`: buy, hold or sell,
  with a confidence from 0 to 1.
- **Condition seats,** `execution-quality` and `price-integrity`: proceed or
  caution, with a confidence from 0 to 1.

**Every report has:**
- `seat` and `agent`, the seat's own wallet address;
- `snapshot`, the sha256 echoed back and checked;
- `summary`, at most three sentences: the model's prose;
- `calls`, at most eight. Each has the asset as chain id and address, the symbol
  for display, the call, the confidence, one sentence of reason, and up to four
  snapshot field paths;
- or `no_call` with one sentence why.

**Code resolves each field path to its value and shows that value.** The model
never writes the key numbers, so it cannot invent them ("nothing important
happens in an agent", CODEBASE §1). A path that does not resolve is dropped and
flagged.

**Aggregation (3.1):**
- **direction** = the mean, over direction seats that called the asset, of
  (+1, 0, −1) × confidence;
- **caution** = the largest confidence among condition seats that said caution;
- **score** = direction × (1 − caution).

A seat that abstains adds nothing. Every seat can move the result.

**Example,** hand-written against the committed capture:

```
seat: price-integrity    agent: 0x…(its own wallet)    snapshot: 253315c0…
summary: Five marks differ from GeckoTerminal by more than 100 bps in this closed
  session. For AMD and MSTR the venue's price sides with GeckoTerminal, so the market
  has moved since the feeds froze. For AMZN, GOOGL and SGOV the venue sides with the
  mark, so the corroborator is the outlier.
calls:
  MSTR  caution 0.8  The mark is Friday's last round; the pools and the venue are both above it.
        mark.price_usd 152.64 · corroboration.price_usd 155.50 · quote.venue_price_usd 154.66
  AMZN  proceed 0.6  GeckoTerminal is far above the mark, but the venue agrees with the mark.
        mark.price_usd 253.86 · corroboration.price_usd 265.83 · quote.venue_price_usd 253.28
```

---

## Config the minimal build needs

Proposals, not written. Each is provisional, and none is set until approved.

| Key | Proposed | Why |
|---|---|---|
| `cadence.cycle_deadline_seconds` | 1,800 | Snapshot about 150 s, analysts up to 630 s in parallel, risk up to 630 s, with room. |
| `cadence.retry_budget_per_worker` | 1 | §9: malformed output retries once. |
| `cadence.confirmation_depth` | set at 5.3 | The record has no reorg measurement for 4663. |
| `models.risk_model` | `claude-sonnet-5` | 1.7 measured a risk call on it: $0.048, 7.7 s. |
| `models.context_budget_tokens` | 60,000 | Four replies at the 12,000-token cap plus a plan. Over is a veto. |
| `thresholds.quorum_min_analysts` | 3 | One failed seat still decides. |
| `thresholds.max_position_weight` | 0.25 | Two $25 orders in one name at $200. |
| `thresholds.cash_floor_usd` | 20 | 10% of the paper capital. |
| `thresholds.turnover_max_bps` | 10,000 | A cycle may trade at most its paper NAV. Loose, and stated as loose. |
| `thresholds.min_order_usd` (new) | 1 | Drops rebalancing dust, so an unchanged view means no trade. |
| `mandate.cumulative_budget_usd` | 5 | Real money on the live leg only. |
| `mandate.live_leg_usd` (new) | 0.50 | Fits what the wallet holds. |
| `mandate.allowed_assets` | the 35 markable stocks (paper), ETH and USDG (live) | The snapshot decides which are tradeable each cycle. |
| `mandate.approved_by`, `approved_at`, `expires_at` | the operator, at approval, plus 7 days | 4.1 refuses nulls. |
| `analysts.json` fourth seat | `price-integrity` | Q1. |

---

## What the operator has to do

These run on the operator's clock, alongside stage A's code.

| Action | Blocks | Spend |
|---|---|---|
| Approve this plan, the 2.1 format and the config values | everything | none |
| Create five Bankr accounts, with one key each: Read Only ON, LLM Gateway ON, Agent API OFF | stage A live (A is built and tested offline first) | none |
| Buy LLM credits in each account from USDC on Base | stage A live | about $22, plus about 5.8% |
| Authorize one refused-swap attempt per agent key | 4.12 | nothing if refused |
| Decide the live leg's rule | 3.3, 5.2 | none |
| Authorize the live round trip | 5.2 | about $1 moved, gas sponsored so far (F0.10.3) |
| Choose how the handler holds full records, and where previews and the page live | 7.1, 7.2, 7.6 | none |
| Approve the x402 deploy of the real handler | 7.2 | none |
| Fund a fresh local key with about $1 of USDC on Base | 7.5 | about $1 |
| Supply the six judging criteria | 8.6 | none |

---

## Build order

Each stage ends in a state a judge could watch on the page. A later stage never
leaves an earlier one half done.

| Stage | Units | The stopping state | Review stop | Guess |
|---|---|---|---|---|
| **A1** The swarm deliberates | 2.1–2.8, 7.6 begun | Four analyst processes, each on its own account, report on one snapshot. The page shows them arrive with address, cost and latency; a failed seat is disclosed. | none | 2.5 h |
| **A2** The fund decides | 3.1–3.9, 4.12's signer | Weights, a re-quoted plan, the gates, the risk verdict landing, and a signed record, all on the page. The replay test passes. | **1** (3.2, 3.8) | 3 h |
| **B** The record is sold | 7.1–7.5, 7.8, 7.9 | The record is published, a stranger's key buys it, and revenue shows from chain evidence. | **2** (7.5) | 1.5 h |
| **C1** The treasurer acts on paper | 4.1–4.10, 4.12 | `make cycle-demo`: orders written before action, paper fills, positions, lock, isolation tests passing. | none | 2.5 h |
| **C2** The treasurer acts on chain | 5.1–5.7 | One real ETH↔USDG round trip through the treasurer, confirmed from receipts, on the explorer, booked once. | **3** (5.4) | 1.5 h |
| **D** The books | 4.11, 6.1–6.8 | NAV as two figures and four lines, exceptions, and per-agent cost. | **4** (6.6) | 1.5 h |
| **E** Unattended and submitted | 7.7, 8.1–8.7 | Three unattended cycles, a timed dry run, the submission. | **5** (8.5) | 2 h |

**The guesses are not measurements.**
- They total about 14.5 hours, roughly a third of the record's pace: 0.7 h a
  unit at full discipline, 42 h for these 60 units (gate §5).
- Nothing on record shows that pace is reachable. If the real rate is half the
  old one rather than a third, the deadline falls inside stage C.
- That is why each stage's end is a demo.

**Why B before C.** B is small and reuses a handler proven twice (0.7d, 0.7e).
C is the money path under full discipline and the largest stage. If time runs
out inside C, the fund still decides, signs, publishes and sells. If C came
first and ran over, nothing would be sold.

**If the six criteria weight on-chain activity above revenue, swap B and C.**
The fund reads Robinhood Chain live at every stage, but its one on-chain act is
C2.

**What each stopping point lacks, plainly:**
- **After A2:** no sale, no execution.
- **After B:** no execution.
- **After C1:** nothing on chain yet.
- **After C2:** no books.
- **After D:** no unattended run and no submission text.

---

## If approved

These folds wait for approval and are not made by this document:
- **PLAN:**
  - §2 invariant 4: the three named exceptions outlive 3.4;
  - §6: five agent keys, and the account per agent;
  - §8: each unit's minimal version, pointing here;
  - §13: the one-account limitation narrowed; the demonstration leg; the
    preview/full split;
  - §11: NAV as two figures.
- **ROADMAP:** the five review stops replace the ▶ marks.
- **config:**
  - `analysts.json`: the fourth seat and the two seat kinds;
  - the values above.
- **`credentials.py` and `.env.example`:** five rows. This is H, so it is
  done with the full discipline.
- **`CLAUDE.md`:** nothing. The pace rule already covers this.
