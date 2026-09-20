# Judging criteria

Supplied by the operator on 2026-09-19 (LESSONS 2026-09-19). PLAN 8.6 names six
criteria the submission must address; until now they were not in the
repository. No definitions came with them, and none is invented here.

1. Product
2. Founder-market fit
3. Execution
4. Originality
5. Onchain potential
6. Token design

**Bonus consideration** for projects built around onchain equities.

## Where the record stands against each

As of 2026-09-20, with Phases 0 to 4 built and Phase 5 built through 5.3: the
live leg has run. This is for unit 8.6 to write against. It is not a claim of
how the project scores.

| Criterion | What the record has now | Where more comes from |
|---|---|---|
| Product | The whole pipeline runs: snapshot, four analyst reports, weights, a sized plan, the gates, a risk vote, a signed record, fills, and books that reconcile exactly. `make cycle-demo` shows it end to end in about a second, on a fresh clone. | 6.1's statement and 7.6's page: the work is done and not yet *shown* to anyone who is not reading files |
| Founder-market fit | Nothing in the build. The operator writes it. | 8.6 |
| Execution | 793 offline tests; two committed captures that replay byte-identically with every connection refused; 235 addresses attested live; a ledger held to an answer computed by hand; two real transactions reconciled from their receipts; and a commit history that names what each unit broke to prove its tests. | Every later unit |
| Originality | A veto that is a code path, not a prompt; two books that cannot be added; nothing booked from an HTTP status; unknown as a first-class outcome that stops the fund rather than a guess. Every "first" claim removed (LESSONS 2026-09-17). | 6.2's exceptions, 6.6's statement |
| Onchain potential | Reads Robinhood Chain live, and **spends** on it: a round trip of two real swaps (5.2), each authorized by a signed instruction, sent once, and booked from the EntryPoint event and the wallet's own logs rather than the venue's reply. x402 sales settled on Base (0.7d, 0.7e). | 7.5's purchase, and 5.7's live cycle |
| Token design | **Nothing.** PLAN §12 leaves "do we launch a token" open, and no unit covers it. | Not decided |
| Bonus: onchain equities | The universe is Robinhood Chain's tokenized stocks, pinned by the issuer's registry and marked by Chainlink. Stock legs are paper, because execution is location-gated for this operator (F0.5.1) — sized, quoted and gated for real, filled on paper. | — |

**What is still not demonstrable** (2026-09-20): revenue. The endpoint that sells
research is live but serves a Phase 0 probe response, the journal has no
settled-revenue event, and the identity has no line for it. 7.1 to 7.4 own it.
