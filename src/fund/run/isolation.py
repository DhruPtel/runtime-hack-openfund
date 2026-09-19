"""What an analyst's key can do, measured by trying it (unit 4.12).

PLAN §2 invariant 1 says no key an analyst process holds may transact. Probe 0.2
measured the toggles, and `probes/keymap.py` reads them back, but a toggle is a claim
about a surface. This sends the thing itself: one swap request per analyst-role key,
and records what came back. A refusal costs nothing. A key that is *not* refused is
the finding, and the reason this is worth running.

    PYTHONPATH=src python3 -m fund.run.isolation --live

**The treasurer's key is never sent.** `BANKR_KEY_EXEC` can transact (F0.10.2), so an
attempt with it would spend. This module refuses any credential the analyst role may
not hold, by name, before anything reaches the wire.

**One request each, no retry** (as probe 0.5 did): a refusal is the result, and
trying again with different parameters would measure nothing about the gate. The
amount is the smallest the venue quotes, three orders of magnitude below the platform
caps, so neither size nor impact can be the reason for a refusal.
"""

from __future__ import annotations

import argparse
import json
import sys
import uuid
from typing import Any, Mapping, Sequence

from fund import config, credentials
from fund.adapters import bankr_quote
from fund.core.types import NATIVE_SENTINEL

SWAP_URL = "https://api.bankr.bot/wallet/swap"
CHAIN = "robinhood"
#: Apple, the best-evidenced address in the registry (F0.4.1, F0.4.3, F0.4.6), so a
#: refusal cannot be about the asset.
STOCK = "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9"
#: 0.0001 ETH, about $0.26: the smallest size that quotes cleanly (probe 0.5).
AMOUNT_ETH = "0.0001"
USER_AGENT = "openfund/4.12 isolation-check"
READ_ONLY = "read-only"


def attempt(name: str, secret: str, *, transport=None, timeout_s: float = 30.0) -> dict[str, Any]:
    """One swap request with the key called `name`. It must be a key the analyst role
    may hold; anything else is refused here, before the wire."""
    permitted = credentials.by_name(name)
    if credentials.Role.TREASURER in permitted.used_by:
        raise config.CredentialNotPermittedError(
            f"{name} may transact: it is the treasurer's, and this check never sends it")
    body = json.dumps({"fromChain": CHAIN, "fromToken": NATIVE_SENTINEL, "toChain": CHAIN,
                       "toToken": STOCK, "amount": AMOUNT_ETH,
                       "idempotencyKey": str(uuid.uuid4())}).encode()
    send = transport or bankr_quote.keyed_transport(USER_AGENT, "X-API-Key", secret)
    status, answer, _ = send(SWAP_URL, body, timeout_s)
    text = answer.decode("utf-8", "replace")[:400]
    return {"key": name, "status": status, "refused": status != 200, "body": text}


def check(environ: Mapping[str, str], *, transport=None) -> list[dict[str, Any]]:
    """Every analyst-role key present, tried once."""
    out = []
    for credential in credentials.CREDENTIALS:
        if credentials.Role.TREASURER in credential.used_by or not environ.get(credential.name):
            continue
        if credential.name.startswith("RPC"):  # not a Bankr key
            continue
        out.append(attempt(credential.name, environ[credential.name], transport=transport))
    return out


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="fund.run.isolation")
    parser.add_argument("--live", action="store_true",
                        help="send the requests; without it nothing is sent")
    args = parser.parse_args(argv)
    environ = config.parse_env_file(config.ENV_FILE)
    if not args.live:
        names = [c.name for c in credentials.CREDENTIALS
                 if credentials.Role.TREASURER not in c.used_by and environ.get(c.name)
                 and not c.name.startswith("RPC")]
        print(f"would send one swap request with: {', '.join(names)}. Nothing was sent.")
        return 0
    tried = check(environ)
    for result in tried:
        print(f"{result['key']:<16} HTTP {result['status']}  "
              f"{'refused' if result['refused'] else 'NOT REFUSED — the finding'}\n"
              f"                 {result['body'][:300]}")
    return 0 if all(r["refused"] for r in tried) else 1


if __name__ == "__main__":
    sys.exit(main())
