"""Candidate addresses for probe 0.3, with provenance and an on-chain check.

**This is not the universe allowlist.** Unit 0.8 owns that: an issuer-derived,
versioned list keyed by `(chain_id, address)` with recorded provenance, which
`config/universe.json` will hold and `core/universe.py` will enforce. Probe 0.3
needs one tradeable address to ask the quote endpoint about, and this is the
smallest honest way to get one. Every address below is **unverified** until 0.8
runs.

Provenance: `https://tokens.coingecko.com/robinhood/all.json`, the discovery list
documented in `research/agent-os.md`, which also warns it is
*"explicitly treated as untrustworthy: it lists undeployed assets and truncates
`name` at 60 chars"*. Two things we do with it, and one we do not:

  - we do read `decimals()` on chain for every address we are about to use,
    because a wrong decimals is a silent factor-of-10^n error in sizing,
  - we do keep the `• Robinhood Token` name marker, because the list contains
    three tokens with the symbol `GME` and only one of them is the issuer's,
  - we do **not** treat presence in this list as evidence the token is genuine.
    That is exactly what probe 0.8's beacon check and the issuer's own
    deployment list are for.

Run:  PYTHONPATH=src python3 -m probes.assets
"""

from __future__ import annotations

import json
import os
import sys
import urllib.request

from fund import config, redaction

#: Discovery list. Read-only, unauthenticated, needs a User-Agent (see findings).
COINGECKO_LIST = "https://tokens.coingecko.com/robinhood/all.json"

USER_AGENT = "openfund-probe/0.3 (+phase-0 discovery)"

#: ERC-20 `decimals()`.
SELECTOR_DECIMALS = "0x313ce567"

CHAIN_ID = 4663

#: Sourced from COINGECKO_LIST on 2026-09-17. Pinned here so the quote probe is
#: re-runnable without re-fetching, and so a later diff shows if a value moved.
#: `decimals` is what the chain said, not what the list said -- they disagree
#: for USDG, and the chain wins.
CANDIDATES: dict[str, dict] = {
    "USDG": {
        "address": "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
        "decimals": 6,
        "name": "Global Dollar",
        "role": "cash leg",
    },
    "AAPL": {
        "address": "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
        "decimals": 18,
        "name": "Apple • Robinhood Token",
        "role": "stock candidate",
    },
    "NVDA": {
        "address": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
        "decimals": 18,
        "name": "NVIDIA • Robinhood Token",
        "role": "stock candidate",
    },
    "TSLA": {
        "address": "0x322f0929c4625ed5bad873c95208d54e1c003b2d",
        "decimals": 18,
        "name": "Tesla • Robinhood Token",
        "role": "stock candidate",
    },
    # Kept deliberately. The discovery list carries three GME tokens: this one
    # with the issuer's name marker, plus "GameStop" (0x7e86...) and "Greatest
    # Meme Ever" (0xef67...). All three are 18 decimals and all three answer
    # decimals() on chain, so neither the list nor a decimals read distinguishes
    # them. That is the concrete case probe 0.8 has to solve.
    "GME": {
        "address": "0x1b0e319c6a659f002271b69db8a7df2f911c153e",
        "decimals": 18,
        "name": "GameStop • Robinhood Token",
        "role": "stock candidate (impersonator siblings exist)",
    },
}

#: Same symbol, not the issuer's token. Never quote against these.
KNOWN_SIBLINGS = {
    "GME": [
        {"address": "0x7e86381a763f0ecca2bdf27c54eac403ddd48123", "name": "GameStop"},
        {"address": "0xef67e3064bef1a27e81925ec7132f23e533bd5f6",
         "name": "Greatest Meme Ever"},
    ],
}


def _rpc(method: str, params: list) -> dict:
    url = os.environ["RPC_4663_MAINNET"]
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {"error": redaction.Redactor().redact(f"{type(error).__name__}: {error}")}


def onchain_decimals(address: str) -> int | None:
    result = _rpc("eth_call", [{"to": address, "data": SELECTOR_DECIMALS}, "latest"])
    raw = result.get("result")
    return int(raw, 16) if raw and raw != "0x" else None


def verify() -> int:
    """Confirm the chain, and that each pinned decimals matches what the token says."""
    config.load_environment()

    chain = _rpc("eth_chainId", []).get("result")
    block = _rpc("eth_blockNumber", []).get("result")
    if not chain or int(chain, 16) != CHAIN_ID:
        print(f"REFUSING: chain id is {chain}, expected {CHAIN_ID}")
        return 1
    print(f"chain {int(chain, 16)} at block {int(block, 16)}\n")

    failures = 0
    for symbol, meta in CANDIDATES.items():
        actual = onchain_decimals(meta["address"])
        ok = actual == meta["decimals"]
        failures += not ok
        print(f"{symbol:6} {meta['address']} pinned={meta['decimals']:>2} "
              f"chain={actual!s:>4} {'ok' if ok else 'MISMATCH'}")
    print()
    for symbol, siblings in KNOWN_SIBLINGS.items():
        for sibling in siblings:
            actual = onchain_decimals(sibling["address"])
            print(f"{symbol:6} sibling {sibling['address']} decimals={actual} "
                  f"name={sibling['name']!r} -- answers like the real one")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(verify())
