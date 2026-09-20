# Openfund

An autonomous fund on **Robinhood Chain (4663)** that shows its work. Four analyst
agents read one frozen, hashed market snapshot of 35 tokenized equities and return
structured reports. Deterministic code — no model — turns those into weights, sizes
them into orders against real quotes, and puts them through fixed gates. A risk agent
may veto; it may never approve what a gate refused. A single treasurer process, the
only thing in the repository that can spend, re-checks every gate against fresh
evidence and executes. Every decision is signed ed25519 over its exact bytes, and the
books are derived from an append-only journal and reconcile to the cent.

Built for the Runtime hackathon. **Everything below is either a command you can run or
a file you can open.**

## Contents

- [The pipeline](#the-pipeline) — what each stage produces, and where the two books part
- [How a cycle works](#how-a-cycle-works) — the same thing in eight lines
- [Clone and run](#clone-and-run) — a fresh machine to a working dashboard
- [The dashboard](#the-dashboard) — serving it, the empty state, the offline fallback
- [What you can run right now](#what-you-can-run-right-now) — every command, timed
- [The two real transactions](#the-two-real-transactions)
- [What it does not do](#what-it-does-not-do) — paper fills, no revenue, no record sales
- [Where to look](#where-to-look) — and a README in every directory

**A few words this repository uses, once each:** a **snapshot** is one frozen, hashed
document of everything the fund knows, pinned to a single block. A **mandate** is the
operator's signed permission — which chain, which wallet, which assets, how much.
**Quorum** is the least number of analysts that must report before the fund will
rebalance. The **chokepoint** is the one function every order passes immediately before
it is sent, which re-checks every rule against fresh evidence. A **paper** fill is
simulated; the **real** book is money that moved.

---

## The pipeline

```
   ADAPTERS ─────────────────────────────────────────────────────────────────
   chain 4663 · Chainlink feeds · GeckoTerminal · Bankr quotes
        │
        ▼
 ┌─ 1. SNAPSHOT ───────────────────────────────────────────────────────────┐
 │ every read taken at ONE pinned block, merged, frozen, hashed            │
 │ produces: snapshot.json — 35 stocks, their marks, the wallet's balances │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │  the same bytes, to every seat
 ┌─ 2. ANALYSTS ───────────────────────────────────────────────────────────┐
 │ four agents, four processes, read-only keys, no memory of each other    │
 │ produces: four reports — refused unless every figure cites the snapshot │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │
 ┌─ 3. AGGREGATE ──────────────────────────────────────────────────────────┐
 │ deterministic code, no model: calls → weights, or a recorded refusal    │
 │ produces: a proposal — or "no rebalance", which is a valid outcome      │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │
 ┌─ 4. PLAN + GATES ───────────────────────────────────────────────────────┐
 │ weights sized into orders on fresh quotes; every fixed limit applied    │
 │ produces: a plan, and a verdict per order. False refuses; unknown too   │
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │
 ┌─ 5. RISK ───────────────────────────────────────────────────────────────┐
 │ a model reads every report in full and the sized plan, and votes        │
 │ it may VETO what the gates passed. It may never approve what they refused│
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │
 ┌─ 6. RECORD ─────────────────────────────────────────────────────────────┐
 │ signed ed25519 over its exact bytes, and rebuildable from its own inputs│
 └──────────────────────────────┬──────────────────────────────────────────┘
                                │
 ┌─ 7. TREASURER ──────────────────────────────────────────────────────────┐
 │ its own process, its own keys, the only thing here that can spend.      │
 │ Re-runs every gate on a fresh quote, writes the order down, sends ONCE  │
 └───────────────┬──────────────────────────────────┬──────────────────────┘
                 │                                  │
   ══ THE BOOKS PART HERE ══════════   ══════════════════════════════════════
                 │                                  │
 ┌─ PAPER ───────▼──────────────────┐ ┌─ REAL ──────▼──────────────────────┐
 │ a stock order fills at its quote │ │ an ETH↔USDG swap is SENT to 4663   │
 │ because tokenized-stock          │ │ and read back from its receipt:    │
 │ execution answers 403 in this    │ │ the EntryPoint event, the wallet's │
 │ region — the order is sized,     │ │ own Transfer logs, its balance     │
 │ quoted and gated for real        │ │ across the block. Never an HTTP 200│
 └───────────────┬──────────────────┘ └─────────────┬──────────────────────┘
                 │                                  │
                 └────────────► ONE JOURNAL ◄───────┘
                    append-only; every figure is derived from it, never
                    written directly. Two books, side by side, NEVER added:
                    paper NAV and real NAV are two answers, and there is no third
```

## How a cycle works

1. **Snapshot** — every adapter reads chain 4663 at one pinned block; the merged
   document is frozen and hashed. Assets are `(chain_id, address)`, never a ticker:
   4663 is permissionless and carries impersonator tokens.
2. **Analysts** — four read-only agents, in parallel, each on those exact bytes.
   `NO_CALL` is a valid answer.
3. **Aggregate** — deterministic weights, or a signed record saying it will not trade.
4. **Plan** — weights sized into ordered trades on fresh quotes, with units, impact
   and quote age carried.
5. **Gates** — one module makes every comparison: tradeability, the mandate, order
   size, quote age, position weight, the cash floor, quorum. False refuses; unknown
   blocks too.
6. **Risk** — a model reads every full report and the sized plan and votes. A veto is
   a code path, not advice.
7. **Execute** — the treasurer, in its own process with its own credentials, re-runs
   the gates on a fresh quote, writes the order `prepared` then `submitted` before it
   acts, sends once, and books what the **chain** says — never what the reply claimed.
8. **Books** — holdings, basis, realised and unrealised from the journal alone, paper
   and real kept apart and never added.

## Clone and run

Tested on a fresh clone of this repository with no credentials at all.

**What to install.** Python **3.11 or newer** (built on 3.13), and two packages:

```bash
git clone https://github.com/DhruPtel/runtime-hack-openfund.git
cd runtime-hack-openfund
pip install cryptography==46.0.3 pytest==9.1.1     # the only two, both pinned
```

`cryptography` signs and verifies the decision record; `pytest` runs the suite. Nothing
else is needed, and nothing is vendored. `make` is convenient but optional — every
target is one `python3` command, shown in the Makefile.

**What runs with no credentials, no network, and no account anywhere:**

```bash
make test         # 795 tests, about 42 s
make replay       # both committed captures rebuilt byte-identically, about 1 s
make cycle-demo   # two whole paper cycles from a committed capture, about 1 s
```

**What needs credentials.** Copy the manifest and fill it in:

```bash
cp .env.example .env      # its header explains every name, and the optional second file
make check-env            # prints which are present, by name only, never a value
```

You need a [Bankr](https://bankr.bot) account for three keys — a read-only key for
quotes, an LLM-gateway key for the analysts, and, only if you want to spend, a
transacting key — plus an RPC endpoint for chain 4663. `.env.example` says what each
one is for and which process is allowed to hold it.

**You do not need any of that to see the fund work.** The dashboard below reads
committed artifacts and renders with no credentials and no server at all.

## The dashboard

```bash
PYTHONPATH=src python3 -m fund.run.serve        # → http://127.0.0.1:8000
```

One command. It serves the page, a manifest naming the cycle it is reading, the
fund's own data rebuilt from its artifacts, and two endpoints that spend — each
refusing any request that does not explicitly confirm.

| | |
|---|---|
| `http://127.0.0.1:8000/` | the last cycle, both books, the four real swaps |
| `http://127.0.0.1:8000/?empty` | **the demo state:** nothing decided, the flow idle, the four seats waiting, the run button ready |
| `front-end/Openfund.html` opened directly | **no server at all.** Every section still renders from the committed export; the buttons that spend are disabled and the page says why |

On a fresh clone `/api/data` answers 503 until a cycle has been run locally — there is
no live data in a clone, because `fixtures/live/` is deliberately not committed. The
page falls back to the export that *is* committed, so it renders either way.

The page is a single HTML file with no build step and no framework.
[`front-end/README.md`](front-end/README.md) explains what each section shows.

## What you can run right now

**No network, no credentials** — these work on a fresh clone:

| Command | ~Time | What it proves |
|---|---|---|
| `make test` | 41 s | 794 tests, offline |
| `make replay` | 1 s | both committed captures rebuilt **byte-identical** with every connection refused |
| `make cycle-demo` | 1 s | two whole paper cycles from a committed capture and four real analyst reports: reports → weights → plan → gates → risk vote → signed record → fills → a book that reconciles exactly (NAV **$200.17**) |
| `PYTHONPATH=src python3 -m pytest tests/test_accounting.py -q` | <1 s | the ledger against an answer worked out **by hand** in `fixtures/accounting/answer.md`: paper NAV $183.64629364, real NAV $4.26567681261301, to the last digit |

**Live, with credentials.** Copy `.env.example` to `.env` and fill it in; its header
explains the optional second file that keeps the signing and spending keys out of the
one an analyst process reads. The `make` targets set `PYTHONPATH` themselves; the bare
`python3 -m` commands need `PYTHONPATH=src`.

| Command | ~Time | What it does |
|---|---|---|
| `make check-env` | instant | which declared credentials are present, **by name only** |
| `make selftest` | 100 s | attests all 235 configured addresses against the chain at one block — feeds, tokens, the beacon, the wallet's delegation |
| `make snapshot` | 150 s | a live block-pinned hashed snapshot, captured, then replayed from its own capture in the same run |
| `python3 -m fund.run.isolation --live` | seconds | tries a swap with each analyst key and records the refusal |
| `python3 -m fund.run.liveleg --snapshot PATH --sell ETH --amount 0.00003 --db PATH --out DIR` | 3 s | quotes the swap, signs the instruction, prints asset, size, wallet and chain — **and stops.** Adding `--confirm` sends it, once |

`python3 -m fund.agents.runner --confirm` (four analyst calls, about $1) and
`python3 -m fund.run.decide --confirm` (one risk call, about $0.10) spend LLM credits.
Everything else above is read-only.

## The two real transactions

Both on 4663, 2026-09-20, each authorized by its own signed instruction, sent once,
reconciled from the receipt and booked:

- **ETH → USDG** — [`0x9c8ea67d…cfbbfa`](https://robinhoodchain.blockscout.com/tx/0x9c8ea67dd8c17c9a7315f38ad427f8e0b3852d55b68af463d5f17027d3cfbbfa)
  — block 67,501,588. Gave 0.00003 ETH, got 0.078714 USDG.
- **USDG → ETH** — [`0x737e32b4…02a27`](https://robinhoodchain.blockscout.com/tx/0x737e32b4ea091110fa0dc42daf8992c705a5d89edc24c5bdd4fae3553a802a27)
  — block 67,501,988. Gave 0.10 USDG, got 0.000038026356590733 ETH.

The instruction that authorized each, its signature, and the chain evidence booked
from it are in [`fixtures/liveleg/`](fixtures/liveleg/). A swap here is a
gas-sponsored ERC-4337 UserOperation inside a bundler's transaction, so the fund reads
the EntryPoint event, the wallet's own `Transfer` logs and its balance across the
block — never `tx.from`, and never the HTTP reply.

**That explorer link is for a human, not evidence:** the page returns HTTP 200 for any
hash, including one that is not a transaction. The evidence is the RPC receipt.

## What it does not do

- **Stock fills are paper.** Robinhood gates tokenized-stock execution behind location
  verification and the operator is in the US, so every equity order is sized, quoted
  and gated for real but filled on paper. The chain activity is real and ungated:
  ETH↔USDG on 4663.
- **Revenue is not booked.** The journal has no settled-revenue event and the
  accounting identity has no line for it. Revenue is therefore zero everywhere, by
  construction, rather than estimated.
- **The x402 endpoint sells a probe, not the record.** `x402.bankr.bot/…/roundtrip` is
  live and answers a 402 challenge, but what it serves is a Phase 0 static response
  measuring platform overhead. Publishing records by immutable id is unbuilt.
- **There is no page yet,** and no scheduler: cycles are run by hand with the commands
  above.
- **One runner, one SQLite file, one signing key.** No HA, no key rotation, no
  independent audit.

The full list, with how each was measured, is [`planning/PLAN.md`](planning/PLAN.md)
§13.

## Where to look

| | |
|---|---|
| Build history, unit by unit, and the state at close | [`tracker/LOGS.md`](tracker/LOGS.md) |
| What went wrong and what changed because of it | [`tracker/LESSONS.md`](tracker/LESSONS.md) |
| Stated limitations | [`planning/PLAN.md`](planning/PLAN.md) §13 |
| Every measured claim, marked measured / documented / inferred | [`research/findings.md`](research/findings.md) |
| Units, checkpoints, and what each was cut down to | [`planning/ROADMAP.md`](planning/ROADMAP.md), [`planning/SIMPLIFICATION.md`](planning/SIMPLIFICATION.md) |
| The one-way dependency rule, stated as tests | [`planning/CODEBASE.md`](planning/CODEBASE.md) |
| A signed decision, its reports, plan, gates and vote | [`fixtures/cycles/20260919T202259Z/`](fixtures/cycles/20260919T202259Z/) |

**Every directory has a README of its own**, one page each, saying what lives there and
what it is for:

| | |
|---|---|
| [`src/fund/`](src/fund/README.md) | the fund, and the one-way rule its layers obey |
| [`src/fund/adapters/`](src/fund/adapters/README.md) · [`core/`](src/fund/core/README.md) · [`agents/`](src/fund/agents/README.md) · [`treasurer/`](src/fund/treasurer/README.md) · [`store/`](src/fund/store/README.md) · [`run/`](src/fund/run/README.md) | one per layer: what it owns, and what it must never do |
| [`front-end/`](front-end/README.md) | the dashboard, section by section |
| [`fixtures/`](fixtures/README.md) | recorded cycles, and why a decision rebuilds byte for byte |
| [`tests/`](tests/README.md) | what the suite proves, and which tests guard money |
| [`research/`](research/README.md) | seven discovery reports, and every measured finding |
| [`probes/`](probes/README.md) | throwaway scripts that measured what the docs got wrong |
| [`planning/`](planning/README.md) | the plan, and how it changed |
| [`tracker/`](tracker/README.md) | what was built, and what went wrong |
| [`config/`](config/README.md) | every tunable, with a note saying who set it and why |

Probe results are marked **measured**, **documented** or **inferred**, and
**unresolved** is a valid outcome. Where this repository states something as fact,
`research/findings.md` says how we know it.
