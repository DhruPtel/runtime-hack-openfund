# Openfund. Targets appear as the unit that implements them lands.
# See planning/CODEBASE.md section 7 for what "finished" looks like.

.PHONY: help test check-env snapshot selftest cycle replay cycle-demo

help:
	@echo "Available now:"
	@echo "  make test        run the test suite, no network, no credentials"
	@echo "  make check-env   report which declared credentials are present, by name only"
	@echo ""
	@echo "Not yet built (the unit that lands each is named):"
	@echo "  make snapshot    live block-pinned hashed snapshot        [unit 1.6]"
	@echo "  make replay      rebuild a snapshot from fixtures         [unit 1.8]"
	@echo "  make selftest    attest every address against chain       [unit 1.9]"
	@echo "  make cycle-demo  a full cycle from fixtures               [unit 4.8]"
	@echo "  make cycle       a live cycle, durable orders, journal     [unit 4.8]"

test:
	python3 -m pytest -q

# Prints names and presence only. Never a value.
check-env:
	@PYTHONPATH=src python3 -c "import json, fund.config as c; print(json.dumps(c.audit(), indent=2))"

snapshot selftest cycle replay cycle-demo:
	@echo "'$@' is not built yet. See 'make help' for the unit that lands it."
	@exit 1
