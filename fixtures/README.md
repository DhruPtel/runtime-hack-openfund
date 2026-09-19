# Fixtures

`snapshots/` captures committed for replay (unit 1.9). Each directory is one
live build's raw answers at the transport, its clock readings and config, and
the snapshot built from them, which cites the answers by hash; `manifest.json`
says where and when. A directory is named `<block>-<sha12>` for the snapshot its
live build produced. When a schema change rebuilds the snapshot from the same
answers, the name stays, and the manifest's `snapshot.rebuilt` says why:
`66812461-8afe38a38b03` now holds `daafd945…`. `make replay` rebuilds each
with the network refused and fails unless it is byte-identical.
`accounting/` the known-answer accounting fixture (unit 4.11).
`live/` never committed: every live build's snapshot, and its capture under
`live/captures/`. See .gitignore.
