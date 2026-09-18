# Openfund

An onchain fund that holds tokenized equities on Robinhood Chain (chain 4663) and
rebalances itself. Agents research a frozen market snapshot, a risk gate can
refuse the resulting plan, and a single treasurer executes it. Every decision is
signed and published, and the fund's own books — revenue, costs, and P&L — are
reconciled and open.

**Status: building, Phase 0.** The plan and research are complete; unit 0.1 (repo
skeleton, config loader, credential redaction) is done. Everything the pipeline
below describes is planned, not running. Nothing here is a claim about a result
we have.

Built for the Runtime hackathon.

---

## How a cycle works

1. **Snapshot.** Adapters read the chain at one pinned block and merge every
   observation into a single frozen, hashed market snapshot. Assets are
   identified by `(chain_id, address)`, never by ticker — 4663 is permissionless
   and has impersonator tokens.
2. **Analysts.** Read-only agents run in parallel. Each receives that exact
   snapshot — the same bytes, the same hash — and returns a structured report.
   `NO_CALL` is a valid answer; an analyst forced to always have a view will
   manufacture one.
3. **Aggregate.** Deterministic code, no model, turns validated reports into
   proposed weights or a recorded decision not to rebalance.
4. **Plan.** Weights are sized into ordered trades against real holdings and live
   quotes, with explicit units, fees and quote age.
5. **Risk.** A risk agent reads every full report *and* the sized plan, and can
   veto. Fixed gates decide; the model explains. Unknown blocks execution.
6. **Execute.** The treasurer — the only component in the system with spend
   authority — re-runs the same gates against fresh evidence, persists the order
   intent before submitting it, and executes.
7. **Books.** An accounting layer reconciles fills, fees, revenue and inference
   cost into an income statement and a portfolio report.
8. **Publish.** The signed decision record is sold to other agents over an x402
   endpoint and shown to humans on a public page — the same record, by the same
   immutable id.

## What makes it different

**Published reconciled books.** Not a P&L number on a dashboard. An income
statement and a portfolio report reconciled against independently observed wallet
balances and settlement evidence, with unresolved items surfaced as named
exceptions rather than smoothed away.

**Revenue from research.** The signed decision record is a product. Other agents
pay for it over x402, and that revenue is booked from settlement evidence — not
from the fact that a request handler returned 200.

**A risk gate that can refuse.** The veto is a code path the treasurer cannot
proceed past, not advice in a prompt. A cycle that decides not to trade, and says
why, is a successful cycle.

## What is paper and what is real

Stated up front rather than in a footnote. Robinhood gates tokenized-stock
execution behind location verification, and the operator is in the US, so **stock
fills are paper** — sized and priced from real live quotes, through the same
executor interface, but not submitted. **The chain activity is real:** the
treasurer executes small ungated swaps on 4663, which require no verification, so
the order state machine, receipts, reconciliation and the ledger are exercised
against a real chain and a real explorer rather than a mock.

Everything upstream of execution — the snapshot, the quotes, the sizing, the
gates, the veto, the books — is the same code in both paths. The full limitation
list is [`PLAN.md`](PLAN.md) §13.

## Architecture

A supervisor with read-only workers and a single writer: analysts and the
deterministic core cannot import a signing path at all, and the treasurer runs as
its own process with its own credentials as the sole spend authority.

The full target file tree, the one-way dependency rule, and the boundary rules
stated as tests are in [`CODEBASE.md`](CODEBASE.md).

## Running it

Working today, with no network and no credentials:

```bash
make test        # the test suite
make check-env   # which declared credentials are present, by name only
```

The rest arrives with the unit that builds it; `make help` names which. The
intended surface when finished:

```bash
make replay      # rebuild a snapshot from fixtures; hash matches   [unit 1.8]
make cycle-demo  # a full cycle from fixtures                       [unit 4.8]
make snapshot    # live, block-pinned, hashed                       [unit 1.6]
make selftest    # every configured address attested against chain  [unit 1.9]
make cycle       # live cycle, durable orders, reconciled journal    [unit 4.8]
```

## Where to look

| | |
|---|---|
| Build history, unit by unit | [`tracker/LOGS.md`](tracker/LOGS.md) |
| What went wrong and what changed | [`tracker/LESSONS.md`](tracker/LESSONS.md) |
| Stated limitations | [`PLAN.md`](PLAN.md) §13 |
| Units and the 27 checkpoints | [`ROADMAP.md`](ROADMAP.md) |
| Phase 0 and 1 in detail | [`PHASE-0-1.md`](PHASE-0-1.md) |
| Target file tree and boundary rules | [`CODEBASE.md`](CODEBASE.md) |
| External technical review of the v1 plan | [`PLAN-technical-review.md`](PLAN-technical-review.md) |
| Discovery reports behind the plan's factual claims | [`research/`](research/) |

Probe results are marked **measured**, **documented**, or **inferred**, and
**unresolved** is a valid outcome. Where this repository states something as fact,
`research/findings.md` will say how we know it.
