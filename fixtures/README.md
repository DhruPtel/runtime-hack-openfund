# Fixtures

`snapshots/` captures committed for replay (unit 1.9). Each directory is one
live build's raw answers at the transport, its clock readings and config, and
the snapshot built from them, which cites the answers by hash; `manifest.json`
says where and when. A directory is named `<block>-<sha12>` for the snapshot its
live build produced. When a schema change rebuilds the snapshot from the same
answers, the name stays, and the manifest's `snapshot.rebuilt` says why.
`make replay` rebuilds each with the network refused and fails unless it is
byte-identical. Two are committed, both taken on Saturday 19 September 2026
inside the closed session:
- `66852293-253315c0e691` (06:01Z), the first to hold the oracle pause flags;
- `67364057-c06abd9e89f0` (20:20Z), the snapshot of Phase 3's exit run.
`retired/` holds captures the current code cannot replay, because it asks the
chain something they never recorded. A replay stops at the first such request
rather than guess an answer. `66812461-8afe38a38b03` is 1.9's checkpoint
capture, from before `oraclePaused()` was read. It replays byte for byte at
commit `ee9077c`, the last before the build read the flag (`8c7a702`).
`cycles/` recorded cycles, committed for replay (3.8, 3.9). Each holds:
- `cycle/`: the runner's cycle as it wrote it;
- `reports/`: every stored reply, by its id;
- `decision/`: the decision's files. These are the quotes as recorded, the
  plan, the risk review, and the record's exact bytes with its envelope;
- `decision/config/`: the four config files the decision read, byte for byte.
  The record names each file's sha256, and a replay reads this copy, never the
  working tree's `config/` (`run/decide.replay`), so config tuned later does not
  change an earlier record's rebuild.

Each is scanned for every declared credential before commit.
`20260919T202259Z` is the exit run that ended Phase 3, on
`67364057-c06abd9e89f0`:
- four reports accepted;
- live quotes;
- one live risk call, which vetoed two orders;
- the record signed with the fund's key, and rebuilt byte for byte offline
  from this directory. It is 3.9's cycle.

`20260919T171351Z` is 3.8's exit run on the committed capture:
- four live replies, all refused;
- so no quorum and no rebalance;
- the record signed with the fund's key.

It is **history, and nothing rebuilds it.** It predates the 3.8 sweep, which
changed what a record holds, though its schema also says `openfund.decision/1`.
`accounting/` the known-answer accounting fixture (unit 4.11): thirteen
constructed events, the answer worked out by hand in `answer.md` without running
the ledger, and the same figures as data in `expected.json`.

`liveleg/` the live leg (units 5.1 and 5.2), one directory a swap. Each holds
what authorized it and what became of it:
- `instruction.json`: one order, in the plan's own layout, with the quote it was
  written on and the window it was authorized for;
- `envelope.json`: the ed25519 signature over those exact bytes. The order's id
  and idempotency key derive from their sha256;
- `outcome.json`: the order as the store holds it, the chain evidence
  `treasurer/reconcile.py` read from the receipt — the transaction, the
  EntryPoint's operation and the wallet's own transfers — and the real book that
  fill left, as text and as data.

The books themselves are SQLite and are not committed; this is the repository's
evidence of the live leg. Both swaps are on chain 4663, 2026-09-20.

`live/` never committed: every live build's snapshot and its capture under
`live/captures/`, the paper cycle's output under `live/cycle-demo/`, and the
fund's own database. See .gitignore.
