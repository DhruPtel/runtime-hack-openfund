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

---

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

Probe results are marked **measured**, **documented** or **inferred**, and
**unresolved** is a valid outcome. Where this repository states something as fact,
`research/findings.md` says how we know it.
