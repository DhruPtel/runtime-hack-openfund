# Roadmap

Every unit in the build, one line each, plus the playtime checkpoints expanded.

This is the ideal shape, not a commitment. Phases 0 and 1 are detailed in
`PHASE-0-1.md`; the rest get detailed at their re-evaluation gate, because what
we learn will change them.

**Reading the checkpoints.** Each ▶ gives you three things: *what you see*, *what
to judge it on*, and *what it could change*. That last one matters most. A
checkpoint isn't a demo, it's a decision point where the plan can bend.

---

## Phase 0 — probes · no product code

Find out what's actually true before building on assumptions.

Run order: **0.8 before 0.3** — we must know an address is real before quoting
against it.

| Unit | Goal |
|---|---|
| 0.1 | Repo skeleton, config loader, secret redaction derived from the credential table |
| 0.2 | Which auth header each Bankr surface accepts; gateway on, Agent API off on both Bankr keys |
| 0.8 | Issuer allowlist source; beacon check against a good token and the fake GME |
| 0.3 | A real quote response for a stock on 4663 at the $25 intended size, field by field |
| 0.4 ▶ | Chainlink feed at a pinned block; GeckoTerminal coverage first, divergence second |
| 0.5 | Execution eligibility: the exact 403, recorded. Expected verdict: fail |
| 0.6 | Credits and usage endpoints: can we reconcile cost, not just estimate it |
| 0.7 ▶ | A trivial x402 handler deployed, paid, and timed |
| 0.9 | *Relocated to unit 1.7* — the cost probe needs a real snapshot. Run early as a labelled floor; 1.7 still owns the number |
| 0.10 | Idempotency behaviour and rate-limit response shape |
| 0.11 ▶ | `findings.md`: every probe marked measured / documented / inferred |

**▶ 0.4 — the price question**
*You see:* first, whether GeckoTerminal covers RH stock tokens at all — measured,
per asset. Then, if it does, a table of five stocks with the Chainlink price, the
GeckoTerminal price, the divergence, the feed's decimals and its last-update
time. If it does not, the same table against a Bankr quote at size, labelled *not
independent of the execution venue*.
*Judge:* do the two sources agree within a few basis points? If not, is the gap
explained by `uiMultiplier` being applied twice? And if the corroborator is a
quote, is a quote-versus-feed check worth anything?
*Could change:* which source marks the book, what the divergence veto threshold
is, whether the veto is cross-source or quote-versus-feed, and whether we need a
third source.

**▶ 0.7 — the x402 question**
*You see:* an unpaid call returning 402, a paid call returning data, both timed,
and the payer header printed.
*Judge:* is the round trip fast enough to feel like a product? Does USDC-on-Base
work from a standard client?
*Could change:* pricing, whether the endpoint serves cached records only, and how
the purchase binds to a decision id.

**▶ 0.11 — the go/no-go**
*You see:* one page, every probe with a recorded verdict — including fail and
unresolved — and its confidence level.
*Judge:* which assumptions in the plan just died.
*Could change:* the whole cost model, the asset universe, or which leg carries
the live chain activity in Phase 5.

---

## Phase 1 — adapters and snapshot

Turn a permissionless chain into one trustworthy, frozen object.

| Unit | Goal |
|---|---|
| 1.1 | Types module: the contracts everything else imports |
| 1.2 | Versioned issuer allowlist keyed by (chain, address) with provenance |
| 1.3 | Chain adapter: block-pinned reads, staleness and pause rules, source vs fetch time, timeouts and fail loudly |
| 1.4 | Price cross-check: Chainlink marks, corroboration from whatever 0.4 established |
| 1.5 | Quote adapter: quotes at the $25 intended size, with age, fees and three-valued impact |
| 1.6 ▶ | Snapshot builder: merge, filter, hash |
| 1.7 | Analyst cost and latency against the real snapshot (relocated from 0.9) |
| 1.8 | Held-but-untradeable assets stay in the book with a status |
| 1.9 ▶ | Fixtures and offline replay |
| 1.10 | Selftest attesting every address against chain |
| 1.11 ▶ | Skew rejection |

**▶ 1.6 — the data**
*You see:* a real snapshot JSON: every asset with price, source, quote at size,
quote age, impact (or null), status (tradeable / excluded), and every timestamp.
*Judge:* is this enough for an analyst to say something intelligent? What's
missing that a real analyst would want?
*Could change:* the whole adapter list. If the answer is "an analyst can't say
anything useful from this," we add fundamentals, history or news before writing
a single analyst.

**▶ 1.9 — reproducibility**
*You see:* the same command run twice, once live and once offline from a fixture,
producing identical hashes.
*Judge:* can the demo run with the network unplugged?
*Could change:* how much of the demo is live versus replayed.

**▶ 1.11 — the refusal**
*You see:* a deliberately corrupted snapshot (two blocks mixed) being rejected by
name.
*Judge:* does it fail loudly rather than quietly averaging?
*Could change:* how strict the freshness rules are before they become annoying.

---

## Phase 2 — analyst contract and fan-out

The reports are the product. Design them before writing the code that makes them.

| Unit | Goal |
|---|---|
| 2.1 ▶ | Report format designed by hand, before any code |
| 2.2 | Output schema, hard validation, `NO_CALL`, address-scoped claims |
| 2.3 | Brief format: mandate, scope boundaries, snapshot bytes, effort scaling. Scopes are disjoint in QUESTION, not necessarily in asset set — two analysts may both look at every asset provided they ask different things of it; the failure mode is two analysts asking the same question of overlapping assets |
| 2.4 | Runner: bounded width, deadlines, retries, fallback, partial-failure flag |
| 2.5 | Per-call token accounting, reconciled to provider usage |
| 2.6 ▶ | First real report from a real snapshot |
| 2.7 | Immutable content-addressed report store |
| 2.8 ▶ | Failure drill |

**▶ 2.1 — the format**
*You see:* a hand-written example report, written as if by a good analyst, with
no code behind it.
*Judge:* would you pay for this? Is it deep enough to be worth reading and short
enough to actually read? Can you tell evidence from opinion?
*Could change:* everything downstream. The schema, the brief, the model choice,
the price, and how many analysts we need.

**▶ 2.6 — the real thing**
*You see:* an actual model-generated report on real snapshot data, with cost and
latency.
*Judge:* how far is it from 2.1? Is it citing real numbers or inventing texture?
*Could change:* the brief, the model, whether analysts get more input data.

**▶ 2.8 — when workers break**
*You see:* one analyst returning garbage, one hanging, one abstaining, and the
cycle completing anyway with the failures disclosed.
*Judge:* is the partial result still trustworthy, or should a failure kill the
cycle?
*Could change:* quorum rules in Phase 3.

---

## Phase 3 — aggregation, planning, risk

Where opinions become a decision, and where the decision can be refused.

| Unit | Goal |
|---|---|
| 3.1 | Aggregator as a total function: equation, quorum, cash, tie-break, residual |
| 3.2 ▶ | Aggregation made visible |
| 3.3 | Planner: weights + holdings + quotes → sized orders |
| 3.4 | Gate module, shared by risk and treasurer |
| 3.5 | Risk agent: full reports + sized plan → verdict |
| 3.6 | Context budget: veto rather than summarize |
| 3.7 | Signed decision record with content hashes |
| 3.8 ▶ | A veto actually happening |
| 3.9 ▶ | Byte-stable replay |

**▶ 3.2 — the maths**
*You see:* a table of reports in, weights out, each analyst's contribution, the
cash weight, and the rounding residual.
*Judge:* does the result match your intuition given those reports? Would you have
allocated differently?
*Could change:* the aggregation equation, the confidence scale, the quorum.

**▶ 3.8 — the refusal**
*You see:* a cycle where a gate trips, the named reason, and execution blocked.
*Judge:* is the veto substantive or theatrical? Did it catch something real?
*Could change:* the gate thresholds and what risk is allowed to see.

**▶ 3.9 — provenance**
*You see:* a decision record regenerated from recorded model outputs, hashes
matching.
*Judge:* is this the artifact we want to sell?
*Could change:* the record's structure and what's included in the signature.

---

## Phase 4 — treasurer (paper) and the journal

Make the money path correct before it touches money.

| Unit | Goal |
|---|---|
| 4.1 | Mandate: bounds, wallet, assets, budget, expiry, revocation |
| 4.2 | Execution intent with stable idempotency key |
| 4.3 | Durable order state machine, written before action |
| 4.4 | Validating chokepoint with regression vectors |
| 4.5 | Paper executor on the live interface |
| 4.6 | Accounting journal covering every event type |
| 4.7 | Positions derived from journal; one valuation function |
| 4.8 ▶ | A full paper cycle end to end |
| 4.9 | Startup reconciliation and single-owner lock |
| 4.10 ▶ | Crash drill |
| 4.11 ▶ | Known-answer accounting fixture |
| 4.12 | Treasurer as its own process with its own credentials; deployed-isolation test |

**▶ 4.8 — the whole machine**
*You see:* one command producing snapshot → reports → weights → plan → verdict →
fills → positions.
*Judge:* does the story hold together? Is this the demo?
*Could change:* the demo script, cadence, and how much is shown live.

**▶ 4.10 — the failure that matters**
*You see:* the runner killed mid-submission, restarted, and resolving the
order once without double-spending.
*Judge:* do you believe it survives a bad moment on demo day?
*Could change:* confirmation depth, reservation rules.

**▶ 4.11 — the books can count**
*You see:* a fixture with funding, a partial sale, an external transfer, gas on a
reverted trade, settled and unsettled revenue, credits bought and consumed, all
reconciling to a known answer.
*Judge:* do the statements tell the economic truth, not just an arithmetically
consistent one?
*Could change:* the journal schema and cost-basis policy.

---

## Phase 5 — live chain activity · opens once 4.12 passes

Stock execution is location-gated and unavailable, so stock legs stay paper. The
money path is proven against a real chain using an **ungated leg** — memecoin and
USDG swaps on 4663 need no location verification — through the same treasurer,
the same order state machine and the same journal.

| Unit | Goal |
|---|---|
| 5.1 | Live executor behind the same interface the paper executor satisfies |
| 5.2 | Small real buy and sell round trip on the ungated leg |
| 5.3 | Receipt reconciliation, confirmation depth, mined-revert handling |
| 5.4 ▶ | A real transaction on the explorer |
| 5.5 | Access expiry and gate behaviour: pause, preserve, expose remediation |
| 5.6 ▶ | A real 403 from the gated stock path, decoded |
| 5.7 ▶ | A live scheduled cycle |

**Exit:** a real transaction on 4663 executed through the treasurer, reconciled
from its receipt, and booked exactly once.

**▶ 5.4 / 5.7 — proof it's real**
*You see:* a transaction hash on the Robinhood Chain explorer, the same order in
the ledger with its receipt, and later a full scheduled cycle doing it unattended
with the paper stock legs visible alongside.
*Judge:* is this the moment that makes the submission credible, given the traded
asset is not a stock?
*Could change:* trade size, cadence, which asset carries the live leg, and how
much of the demo leans on it.

**▶ 5.6 — the error**
*You see:* the exact 403 body and which of the documented causes it maps to. This
is the expected result for the stock path, not a failure.
*Judge:* would you be able to debug this at 2am on demo day? Does the page
explain the paper/live split honestly to someone who did not read the plan?
*Could change:* error surfacing across the whole system, and how the split is
presented.

---

## Phase 6 — books and attribution

| Unit | Goal |
|---|---|
| 6.1 | Statement builder over sealed inputs |
| 6.2 | Reconciliation against balances and settlements; exceptions shown |
| 6.3 | Cost with estimate flags, reconciled to provider usage |
| 6.4 | Funded contribution: realized P&L allocated once, with residual |
| 6.5 | Call accuracy: hypothetical, labelled, never mixed into profit |
| 6.6 ▶ | The first real statement |
| 6.7 ▶ | Attribution with overlapping calls |
| 6.8 ▶ | A reconciliation exception surfacing |

**▶ 6.6 — the differentiator**
*You see:* a real income statement and portfolio report from real cycles.
*Judge:* is this the thing no other project in the ecosystem has? Does it read
like a company's accounts?
*Could change:* the pitch itself, and what the page leads with.

**▶ 6.7 — honest credit**
*You see:* two analysts recommending the same asset, credited once between them,
residual reconciling.
*Judge:* is the attribution defensible if someone interrogates it?
*Could change:* the allocation rule, or whether we publish attribution at all.

**▶ 6.8 — showing the seams**
*You see:* a deliberate mismatch appearing as a named exception.
*Judge:* does showing our own unresolved items build trust or undermine it?
*Could change:* how exceptions are presented publicly.

---

## Phase 7 — surfaces

| Unit | Goal |
|---|---|
| 7.1 | Publisher: immutable bytes, manifest, atomic latest pointer |
| 7.2 | x402 handler serving by immutable id |
| 7.3 | Purchase binding: request, decision, payer, settlement |
| 7.4 | Revenue booked from settlement evidence |
| 7.5 ▶ | A real purchase, end to end |
| 7.6 | Public page over the same records |
| 7.7 ▶ | The page |
| 7.8 | Skill manifest for other Bankr agents |
| 7.9 ▶ | Recovery drill |

**▶ 7.5 — the business model working**
*You see:* a client paying, receiving the record, and the payment landing in the
books. The client is `@x402/fetch` with a fresh, locally held key and no Bankr
account — the first payment from anyone but ourselves.
*Judge:* is the x402 revenue line real, and does it reconcile from settlement
evidence rather than from a handler log?
*Could change:* price, tiering, what the free preview includes.

**▶ 7.7 — what a judge sees**
*You see:* the public page: basket, weights, latest decision and reasoning, veto
history, statements.
*Judge:* does a stranger understand what this is in thirty seconds?
*Could change:* the framing, the hierarchy, what gets cut.

**▶ 7.9 — paid but not delivered**
*You see:* a response dropped after settlement, then retrieved by decision id
without a second charge.
*Judge:* would you trust this with someone else's money?
*Could change:* refund policy and how it's disclosed.

---

## Phase 8 — schedule, demo, submission

| Unit | Goal |
|---|---|
| 8.1 | Scheduler: cheap ticks, overlap fencing, no permission bypass |
| 8.2 | Kill switch that stops submissions, not reconciliation |
| 8.3 ▶ | Unattended multi-cycle run |
| 8.4 | Demo script, fixtures plus a live section |
| 8.5 ▶ | Timed dry run |
| 8.6 | Submission text: architecture, limitations, six criteria |
| 8.7 ▶ | Final read-through as a judge |

**▶ 8.3 — autonomy**
*You see:* several cycles running with nobody touching anything, including one
that correctly decides not to trade.
*Judge:* is it alive, or does it need babysitting?

**▶ 8.5 — the pitch**
*You see:* the demo, timed, start to finish.
*Judge:* does it land in the time available? What gets cut?

**▶ 8.7 — cold eyes**
*You see:* everything a judge would see, read in order.
*Judge:* is the story complete and the limitations honest?

---

## Checkpoint summary

Twenty-seven playtime checkpoints. The five that can most change the plan:

1. **0.11** — do the probes kill an assumption?
2. **1.6** — is the data enough for an analyst to be intelligent?
3. **2.1** — is the report worth paying for?
4. **4.11** — can the books tell the economic truth?
5. **6.6** — is the statement the thing nobody else has?
