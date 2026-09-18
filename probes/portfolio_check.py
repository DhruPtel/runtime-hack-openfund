"""Probe 0.7c — how wrong is `GET /wallet/portfolio`?

Read-only. RPC reads and one authenticated GET; costs nothing.

F0.7.1 measured the Bankr portfolio endpoint returning `tokenBalances: []` for
Base while USDC `balanceOf` returned $0.108346 — not a zero entry, **no entry at
all**. That matters beyond tidiness: F0.2.6 recorded *"the fund wallet is empty"*
from this same endpoint, and unit 1.5 is meant to size trades against reconciled
holdings.

This compares the endpoint against `balanceOf` for every ERC-20 known to have
touched the wallet, and tries to tell three explanations apart:

  - **a value threshold** — small holdings filtered out,
  - **specific tokens** — particular contracts skipped,
  - **staleness** — the endpoint lagging the chain.

The candidate list is not guessed. On Base it comes from the wallet's own ERC-20
transfer history; on 4663 the explorer sits behind Cloudflare, so a pinned set
from `probes/assets.py` is used instead and the narrower coverage is stated in
the finding rather than glossed.

Run:  PYTHONPATH=src python3 -m probes.portfolio_check
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"
PORTFOLIO_URL = "https://api.bankr.bot/wallet/portfolio"
USER_AGENT = "openfund-probe/0.7c"

SELECTOR_BALANCE_OF = "0x70a08231"

#: Every ERC-20 that has moved to or from this wallet on Base, from its transfer
#: history. `exchange_rate` is what the explorer prices it at, and it is carried
#: here because "has a price" is the axis the threshold hypothesis turns on.
BASE_TOKENS = (
    {"symbol": "USDC", "address": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
     "decimals": 6, "priced": True},
    {"symbol": "USER", "address": "0xbc7d2ce645565de0461e6f66aa7c0a6aa6380db6",
     "decimals": 18, "priced": False},
    {"symbol": "ETH-lookalike", "address": "0x58bdc4310db1b19854ca9066deed7e3df4f2ec9b",
     "decimals": 18, "priced": False},
)

#: 4663. A pinned candidate set, not an enumeration — see the module docstring.
RH_TOKENS = (
    {"symbol": "USDG", "address": "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
     "decimals": 6, "priced": True},
    {"symbol": "AAPL", "address": "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
     "decimals": 18, "priced": True},
    {"symbol": "NVDA", "address": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
     "decimals": 18, "priced": True},
    {"symbol": "TSLA", "address": "0x322f0929c4625ed5bad873c95208d54e1c003b2d",
     "decimals": 18, "priced": True},
)

BASE_RPC = "https://mainnet.base.org"


def _rpc(url: str, method: str, params: list) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    request = urllib.request.Request(
        url, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}


def balance_of(url: str, token: str) -> int | None:
    result = _rpc(url, "eth_call",
                  [{"to": token,
                    "data": SELECTOR_BALANCE_OF + "0" * 24 + WALLET[2:]}, "latest"])
    raw = result.get("result")
    return int(raw, 16) if raw and raw != "0x" else None


def native_balance(url: str) -> int | None:
    raw = _rpc(url, "eth_getBalance", [WALLET, "latest"]).get("result")
    return int(raw, 16) if raw else None


def main() -> int:
    config.load_environment()
    key = config.load(Role.ANALYST).secret("BANKR_KEY_READ")
    rh_rpc = config.load(Role.ANALYST).secret("RPC_4663_MAINNET")

    capture = _capture.call(label="portfolio", url=PORTFOLIO_URL,
                            header_name="X-API-Key", header_value=key,
                            max_body_chars=9000)
    portfolio = (_capture.as_json(capture) or {}).get("balances") or {}

    report: dict = {"portfolio_status": capture.status, "chains": {}}

    for chain, rpc_url, tokens in (("base", BASE_RPC, BASE_TOKENS),
                                   ("robinhood", rh_rpc, RH_TOKENS)):
        reported = portfolio.get(chain, {})
        reported_tokens = reported.get("tokenBalances") or []
        rows = []
        for token in tokens:
            raw = balance_of(rpc_url, token["address"])
            held = bool(raw)
            in_portfolio = any(
                (t.get("address") or t.get("token") or "").lower() == token["address"]
                for t in reported_tokens if isinstance(t, dict))
            rows.append({**token, "onchain_raw": raw,
                         "onchain_human": (raw / 10 ** token["decimals"]) if raw else 0,
                         "held": held, "in_portfolio": in_portfolio})
        native = native_balance(rpc_url)
        report["chains"][chain] = {
            "portfolio_native": reported.get("nativeBalance"),
            "portfolio_native_usd": reported.get("nativeUsd"),
            "portfolio_token_count": len(reported_tokens),
            "onchain_native_raw": native,
            "native_matches": (
                native is not None and reported.get("nativeBalance") is not None
                and abs(native / 1e18 - float(reported["nativeBalance"])) < 1e-12),
            "tokens": rows,
        }

        print(f"\n=== {chain} ===")
        print(f"  portfolio: native={reported.get('nativeBalance')} "
              f"(${reported.get('nativeUsd')}), tokenBalances entries="
              f"{len(reported_tokens)}")
        print(f"  on chain : native={native / 1e18 if native else None} "
              f"-> native agrees: {report['chains'][chain]['native_matches']}")
        print(f"  {'symbol':14} {'priced':7} {'on-chain':>22} {'held':5} {'in portfolio'}")
        for row in rows:
            print(f"  {row['symbol']:14} {str(row['priced']):7} "
                  f"{row['onchain_human']:>22.10f} {str(row['held']):5} "
                  f"{row['in_portfolio']}")

    missing = [r for c in report["chains"].values() for r in c["tokens"]
               if r["held"] and not r["in_portfolio"]]
    report["held_but_missing"] = [
        {"symbol": r["symbol"], "address": r["address"],
         "human": r["onchain_human"], "priced": r["priced"]} for r in missing]

    print("\n" + "=" * 68)
    print(f"held on chain but absent from the portfolio: {len(missing)}")
    for row in missing:
        print(f"   {row['symbol']:14} {row['onchain_human']:.10f} "
              f"priced={row['priced']}  {row['address']}")
    print(f"native balances agree on every chain: "
          f"{all(c['native_matches'] for c in report['chains'].values())}")
    print("=" * 68)

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "portfolio_check.json"
    path.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
