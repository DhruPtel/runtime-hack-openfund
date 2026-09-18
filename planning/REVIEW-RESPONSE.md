# Response to the technical review

The review is written to a production standard. We are building a demo in a
week that must also be genuinely operable, so each finding gets one of three
dispositions: **adopt** (it is cheap and it is right), **reduce** (adopt the
core, cut the expensive tail, record the limit), or **dispute** (we think the
finding misreads the goal).

Nothing is silently dropped. Everything reduced appears in `PLAN.md` §13 as a
stated limitation, because a fund that publishes its own books cannot hide its
own caveats.

| # | Finding | Disposition | Note |
|---|---|---|---|
| 1 | Successful swap can vanish; recovery can double-spend | **Adopt** | Durable order intent before submission, five states, restart reconciliation, single execution owner. This is the highest-value fix in the review and it is cheap. |
| 2 | Single-writer is an import rule, not an authority boundary | **Adopt (core)** | Separate process, separate credentials, analysts never receive execution or signing secrets. Execution wallet named explicitly in every snapshot and order; its balances read via RPC, not via another account's portfolio. Reduced: no service mesh or authenticated internal RPC; the treasurer is a separate process reading approved intents from the database. |
| 3 | Risk approves weights before sized orders exist | **Adopt** | Reordered: aggregate, then build a sized candidate plan from live quotes, then risk sees reports plus the plan. Treasurer reruns the same gate module against fresh evidence before submit. Shared gate code, one interpretation of the limits. |
| 4 | No deployment design connecting runner, state, handler, page | **Adopt (core)** | Named: one runner host, SQLite as authoritative state, immutable published records over HTTPS, handler fetches by ID. Reduced: no HA, no backup strategy beyond a copied file. |
| 5 | Trade ledger cannot produce the promised statements | **Adopt** | Accounting-event journal replaces trades-only. Opening balances, transfers, fills, fees, gas, x402 settlements, LLM credit purchases and consumption, valuation marks. Reduced: reporting entity is one wallet plus one Base receiving address; no consolidation beyond that. |
| 6 | A frozen snapshot can freeze an inconsistent state | **Adopt** | Chain reads pinned to one block. Source time and fetch time recorded separately. Per-feed staleness and pause rules. Held-but-untradeable assets stay in the book with a status. |
| 7 | Beacon-slot match is not issuer authentication | **Adopt** | A pinned issuer-derived allowlist keyed by `(chain_id, address)` with recorded provenance is the authority. Beacon check demoted to a secondary consistency check. |
| 8 | Aggregation has no defined result for abstention cases | **Adopt** | The aggregator becomes a total function with a specified equation, quorum, cash weight, tie-break and rounding residual. All-abstain yields an explicit no-rebalance, which preserves holdings and never means liquidate. |
| 9 | "All reports reach risk" and seeding are not executable contracts | **Adopt** | Pinned model IDs, per-worker deadlines, output token caps, an explicit context budget. If the full bundle does not fit, veto rather than summarize. Replay runs from recorded model outputs, including the risk output. |
| 10 | Mandate, decision signing and execution signing conflated | **Adopt (core)** | Two objects: a human-authorized mandate (bounds, wallet, chain, assets, budget, expiry) and a per-cycle execution intent revalidated against it. Ed25519 rather than HMAC so the public key can be published. `signed=false` is a diagnostic and can never authorize or be sold. Reduced: no key-rotation trust chain; one key, published, rotated manually if needed. |
| 11 | Paid request has no purchase-to-delivery-to-settlement mapping | **Adopt (core)** | `latest` resolves to an immutable decision ID before purchase; purchase binds to that ID; revenue is booked from settlement evidence, never from a handler invocation. Reduced: no refund automation. A paid-but-undelivered record is retrievable by decision ID; refunds are manual and recorded. |
| 12 | Live access has no satisfactory phase exit | **Adopt** | Phase 0 probes resolve to pass / fail / unresolved. Phase 5 requires an eligible execution account and a demonstrated small buy **and** sell round trip. Unresolved eligibility means Phase 5 does not open and the demo ships paper, stated plainly. |
| 13 | Credit balance IS readable; quota model targets the wrong surface | **Adopt, and this corrects us** | `GET /v1/credits` and `GET /v1/usage` exist, so cost estimates get reconciled against provider totals instead of standing alone. Analysts run on the LLM gateway (credit-metered), not `/agent/prompt`, so the 100/day figure was the wrong constraint to design around. Budgets become per-service. |
| 14 | Per-analyst attribution has no economic meaning | **Reduce** | We publish two clearly separated numbers: *funded contribution* (realized strategy P&L allocated once by executed weight, with a residual line for cash, fees and unassigned effects) and *call accuracy* (hit rate against a stated horizon and benchmark, explicitly hypothetical, never mixed into fund profit). Full counterfactual replay is out of scope. |

## Where we disagree, or narrow the framing

**"Audited books" was the wrong word.** The review is right that an internal
reconciliation cannot quietly satisfy an unstated assurance promise. We say
**published and reconciled** books: reconciled against independent wallet
balances and provider settlement evidence at the reporting cutoff, signed for
provenance, with unresolved items shown rather than absorbed. Nobody external
audits anything, and we will not imply otherwise.

**Reorg and finality handling is reduced, not solved.** We record a confirmation
depth and treat anything below it as unconfirmed. Compensating events for a
receipt becoming noncanonical are out of scope for the week; the limitation is
stated, and the reconciler surfaces a mismatch rather than silently correcting
it.

**Archive RPC and a sequencer-uptime feed are not assumed.** We require
demonstrated chain progress and halt on uncertainty. We do not claim an
equivalent sequencer attestation exists.

**The public page is intentional.** The review anticipates a bad fix here and it
is right to. We are selling structured, verifiable, machine-readable delivery
and provenance, not exclusive information. The page stays.

**One point of scope, stated once.** Several corrections in the review are the
right answer for a fund running unattended with real outside capital. Within a
week, with the operator's own small stake, the honest version is: build the
correctness properties that prevent silent economic error (1, 3, 5, 6, 8, 10),
and record the operational hardening we did not do. A demo that overstates its
own robustness would fail the same standard the product itself is built to
enforce.
