# Openfund. Targets appear as the unit that implements them lands.
# See planning/CODEBASE.md section 7 for what "finished" looks like.

.PHONY: help test check-env snapshot selftest cycle replay cycle-demo

help:
	@echo "Available now:"
	@echo "  make test        run the test suite, no network, no credentials"
	@echo "  make check-env   report which declared credentials are present, by name only"
	@echo "  make snapshot    live block-pinned hashed snapshot, captured and replayed [1.6, 1.9]"
	@echo "  make replay      rebuild every committed capture offline; fails unless identical [1.9]"
	@echo ""
	@echo "Not yet built (the unit that lands each is named):"
	@echo "  make selftest    attest every address against chain       [unit 1.10]"
	@echo "  make cycle-demo  a full cycle from fixtures               [unit 4.8]"
	@echo "  make cycle       a live cycle, durable orders, journal     [unit 4.8]"

test:
	python3 -m pytest -q

# Prints names and presence only. Never a value.
check-env:
	@PYTHONPATH=src python3 -c "import json, fund.config as c; print(json.dumps(c.audit(), indent=2))"

# Reads the chain, GeckoTerminal and the venue with the analyst role's keys. Spends nothing.
snapshot:
	PYTHONPATH=src python3 -m fund.run.snapshot

# Every committed capture, rebuilt with every connection refused. Needs no credential.
replay:
	@for capture in fixtures/snapshots/*/; do \
		PYTHONPATH=src python3 -m fund.run.snapshot --replay "$$capture" || exit 1; \
	done

selftest cycle cycle-demo:
	@echo "'$@' is not built yet. See 'make help' for the unit that lands it."
	@exit 1
