# Fixtures

`snapshots/` captures committed for replay (unit 1.9). Each directory is one
live build's raw answers at the transport, its clock readings and config, and
the snapshot built from them, which cites the answers by hash; `manifest.json`
says where and when. A directory is named `<block>-<sha12>` for the snapshot its
live build produced. When a schema change rebuilds the snapshot from the same
answers, the name stays, and the manifest's `snapshot.rebuilt` says why.
`make replay` rebuilds each with the network refused and fails unless it is
byte-identical. The one committed now is `66852293-253315c0e691`, taken on a
Saturday inside the closed session, the first to hold the oracle pause flags.
`retired/` holds captures the current code cannot replay, because it asks the
chain something they never recorded. A replay stops at the first such request
rather than guess an answer. `66812461-8afe38a38b03` is 1.9's checkpoint
capture, from before `oraclePaused()` was read. It replays byte for byte at
commit `ee9077c`, the last before the build read the flag (`8c7a702`).
`accounting/` the known-answer accounting fixture (unit 4.11).
`live/` never committed: every live build's snapshot, and its capture under
`live/captures/`. See .gitignore.
