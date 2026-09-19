# Fixtures

`snapshots/` captures committed for replay (unit 1.9). Each directory is one
live build's raw answers at the transport, its clock readings and config, and
the snapshot it produced; `manifest.json` says where and when. `make replay`
rebuilds each with the network refused and fails unless it is byte-identical.
`accounting/` the known-answer accounting fixture (unit 4.11).
`live/` never committed: every live build's snapshot, and its capture under
`live/captures/`. See .gitignore.
