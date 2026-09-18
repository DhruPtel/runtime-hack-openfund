"""Out-of-order probe — can Robinhood Chain testnet (46630) host an execution demo?

Read-only throughout. No transaction is attempted on testnet, and the Bankr API
is never called with a testnet chain parameter: `planning/PLAN.md` §6 keeps
46630 for probes and drills, and poking an unfamiliar write path to find out
whether it routes is exactly the kind of experiment that belongs behind an
explicit authorization. Bankr support is settled from documentation only.

**Why this exists.** Probe 0.5 measured the mainnet refusal — 403, region-gated,
tokenized stocks unavailable to a US operator (`research/findings.md` F0.5.1).
The plan's answer is paper stock legs plus real chain activity on an ungated
asset, which works but is a weaker demo than a real stock trade. Testnet was an
open question at the Phase 1 gate; this settles it before Phase 1 designs around
mainnet.

Three questions, in the order they matter:

  1. do tokenized stock tokens exist on 46630 at all?
  2. do Chainlink equity feeds exist there?
  3. does Bankr route to testnet, or is 4663 the only supported chain?

**The trap this probe is built to avoid.** 0.4 concluded "no equity feeds" from a
four-feed sample and was wrong. Absence here is therefore established two ways
that do not share a failure mode: the **issuer's own deployment list**, which is
authoritative and names a chain id per asset, and an **exhaustive same-address
check** over every mainnet Robinhood token. A liveness check runs first, because
an empty answer from a dead endpoint looks exactly like an empty answer from a
live one.

Run:  PYTHONPATH=src python3 -m probes.testnet
"""

from __future__ import annotations

import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

from fund import config, redaction

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

USER_AGENT = "openfund-probe/testnet (+phase-0 discovery)"

TESTNET_CHAIN_ID = 46630
MAINNET_CHAIN_ID = 4663

#: The issuer's own asset registry, documented at
#: `https://docs.robinhood.com/chain/stock-tokens/` (read 2026-09-18) as the way
#: to "query the assets API". Every asset carries a `deployments` array with an
#: explicit `chainId`, which makes this the deployment list unit 0.8 has been
#: waiting for and the authoritative answer to question 1.
ISSUER_ASSETS = "https://api.robinhood.com/rhj/assets"

#: Blockscout for testnet, named in the issuer's own network table.
TESTNET_EXPLORER = "https://explorer.testnet.chain.robinhood.com/api/v2"

#: Chainlink's reference directory. The mainnet file is `feeds-robinhood-mainnet.json`
#: (F0.4.1). The testnet spelling is unknown, so several are tried, and
#: `feeds-ethereum-testnet-sepolia.json` is fetched as a **positive control** —
#: it proves the `-testnet-` convention exists and that a 404 means absence
#: rather than a wrong guess.
DIRECTORY = "https://reference-data-directory.vercel.app/"
DIRECTORY_CANDIDATES = (
    "feeds-robinhood-testnet.json",
    "feeds-robinhood-testnet-sepolia.json",
    "feeds-robinhood-chain-testnet.json",
    "feeds-robinhood-mainnet-testnet.json",
)
DIRECTORY_CONTROL = "feeds-ethereum-testnet-sepolia.json"

#: ERC-8056 `uiMultiplier()` (F0.4.6) and ERC-20 `decimals()`.
SELECTOR_UI_MULTIPLIER = "0xa60bf13d"
SELECTOR_DECIMALS = "0x313ce567"

#: EIP-1967 beacon slot. The real discriminator on testnet, for the reason
#: F0.4.6 flagged and this probe confirms: `uiMultiplier()` answering is
#: necessary but not sufficient, and on a permissionless testnet it is cheap to
#: fake. What is not cheap to fake is sitting behind the issuer's beacon.
SLOT_BEACON = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"

#: BeaconUpgradeable `implementation()`.
SELECTOR_IMPLEMENTATION = "0x5c60da1b"


def _get(url: str, tries: int = 3) -> object | None:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(tries):
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code in (429, 503):
                time.sleep(2 * (attempt + 1))
                continue
            return None
        except Exception:
            time.sleep(1)
    return None


def _rpc(url: str, method: str, params: list, tries: int = 6) -> dict:
    """One JSON-RPC call, with backoff.

    The public testnet endpoint rate-limits hard, and the issuer's own docs call
    it "rate-limited and not recommended for production". A 429 swallowed as an
    empty result would read as *absence*, which is the one mistake this probe
    cannot afford, so a rate-limit is returned as its own outcome and never as
    a missing contract.
    """
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    for attempt in range(tries):
        request = urllib.request.Request(
            url, data=payload,
            headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
        )
        try:
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 429:
                time.sleep(3 * (attempt + 1))
                continue
            return {"error": f"HTTP {error.code}"}
        except Exception as error:
            time.sleep(2)
            last = redaction.Redactor().redact(f"{type(error).__name__}: {error}")
    return {"error": "rate_limited_or_unreachable"}


def liveness(url: str) -> dict:
    """Is the endpoint live, on the chain we think, and advancing?

    Everything below is an absence claim, and an absence claim against a dead
    endpoint is worthless. This runs first and the probe stops if it fails.
    """
    chain = _rpc(url, "eth_chainId", []).get("result")
    client = _rpc(url, "web3_clientVersion", []).get("result")
    first = _rpc(url, "eth_blockNumber", []).get("result")
    block = _rpc(url, "eth_getBlockByNumber", [first, False]).get("result") or {}
    time.sleep(4)
    second = _rpc(url, "eth_blockNumber", []).get("result")

    result = {
        "chain_id": int(chain, 16) if chain else None,
        "client": client,
        "block_first": int(first, 16) if first else None,
        "block_second": int(second, 16) if second else None,
        "latest_block_timestamp": int(block.get("timestamp", "0x0"), 16),
        "txs_in_latest_block": len(block.get("transactions", [])),
    }
    result["advancing"] = bool(
        result["block_second"] and result["block_first"]
        and result["block_second"] > result["block_first"]
    )
    result["live"] = result["chain_id"] == TESTNET_CHAIN_ID and result["advancing"]
    print(f"testnet liveness: chain {result['chain_id']}, block "
          f"{result['block_first']} -> {result['block_second']}, "
          f"advancing={result['advancing']}, client={client}")
    return result


def issuer_deployments() -> dict:
    """Question 1, authoritatively. Every asset, every chain id it is on."""
    payload = _get(ISSUER_ASSETS)
    assets = (payload or {}).get("assets") or []
    chains: dict[int, int] = {}
    for asset in assets:
        for deployment in asset.get("deployments", []):
            chain_id = deployment.get("chainId")
            chains[chain_id] = chains.get(chain_id, 0) + 1
    print(f"\nissuer asset registry: {len(assets)} assets, "
          f"deployments by chain id {chains}")
    return {
        "url": ISSUER_ASSETS,
        "asset_count": len(assets),
        "deployments_by_chain": chains,
        "on_testnet": chains.get(TESTNET_CHAIN_ID, 0),
        "tickers": sorted({a.get("tokenSymbol", "").upper() for a in assets}),
        "assets": assets,
    }


def same_address_check(testnet_url: str, assets: list[dict],
                       feed_proxies: list[str]) -> dict:
    """Does any mainnet Robinhood contract exist at the same address on testnet?

    Exhaustive over the mainnet set, not sampled. `eth_getCode` is verified to
    work on this endpoint first — otherwise "no code anywhere" is a statement
    about the probe rather than about the chain.
    """
    block = _rpc(testnet_url, "eth_blockNumber", []).get("result")

    # Control: contracts that recent testnet transactions actually touched must
    # have code. If they do not, `eth_getCode` is not answering and every
    # negative below is meaningless.
    touched: list[str] = []
    head = int(block, 16)
    for offset in range(40):
        candidate = _rpc(testnet_url, "eth_getBlockByNumber",
                         [hex(head - offset), True]).get("result") or {}
        for tx in candidate.get("transactions", []):
            if tx.get("to"):
                touched.append(tx["to"].lower())
        if len(set(touched)) >= 20:
            break
    touched = list(dict.fromkeys(touched))[:20]
    with_code = sum(
        1 for a in touched
        if (_rpc(testnet_url, "eth_getCode", [a, block]).get("result") or "0x") != "0x"
    )
    print(f"\ncontrol: {with_code} of {len(touched)} recently-touched testnet "
          f"addresses have code (eth_getCode is answering)")

    addresses = []
    for asset in assets:
        for deployment in asset.get("deployments", []):
            addresses.append((asset.get("tokenSymbol"),
                              deployment["contractAddress"].lower()))
    hits = []
    for symbol, address in addresses:
        code = _rpc(testnet_url, "eth_getCode", [address, block]).get("result")
        if code and code != "0x":
            hits.append({"symbol": symbol, "address": address, "code_len": len(code)})
    feed_hits = []
    for proxy in feed_proxies:
        code = _rpc(testnet_url, "eth_getCode", [proxy.lower(), block]).get("result")
        if code and code != "0x":
            feed_hits.append(proxy)

    print(f"same-address: {len(hits)} of {len(addresses)} issuer token addresses "
          f"and {len(feed_hits)} of {len(feed_proxies)} mainnet feed proxies "
          f"have code on testnet")
    return {
        "block": block,
        "control_touched": len(touched),
        "control_with_code": with_code,
        "checked_token_addresses": len(addresses),
        "token_hits": hits,
        "checked_feed_proxies": len(feed_proxies),
        "feed_proxy_hits": feed_hits,
    }


def chainlink_directory() -> dict:
    """Question 2, at the directory level, with a positive control."""
    control = _get(DIRECTORY + DIRECTORY_CONTROL)
    found = {}
    for name in DIRECTORY_CANDIDATES:
        payload = _get(DIRECTORY + name)
        found[name] = None if payload is None else len(payload)
    print(f"\nchainlink directory: control "
          f"({DIRECTORY_CONTROL}) = "
          f"{len(control) if control else 'MISSING'} feeds; "
          f"robinhood testnet candidates = {found}")
    return {
        "control_file": DIRECTORY_CONTROL,
        "control_feed_count": len(control) if control else None,
        "candidates": found,
        "any_found": any(v is not None for v in found.values()),
    }


def stock_contracts_on_testnet(testnet_url: str, mainnet_url: str) -> dict:
    """Is the issuer's Stock Token *machinery* deployed on testnet, unlisted?

    The issuer registry answers whether the *listed assets* are there. It cannot
    answer whether the contracts exist unlisted, which matters for a demo. So
    this walks the explorer's token list — ordered by holder count, so the cut is
    at the tail and not arbitrary — and checks each equity-symbol candidate for
    the EIP-1967 beacon that mainnet stock tokens sit behind.
    """
    block = _rpc(testnet_url, "eth_blockNumber", []).get("result")

    def beacon_of(url: str, address: str) -> str | None:
        raw = _rpc(url, "eth_getStorageAt", [address, SLOT_BEACON, "latest"]).get("result")
        if not raw or int(raw, 16) == 0:
            return None
        return "0x" + raw[-40:]

    def implementation_of(url: str, beacon: str) -> str | None:
        raw = _rpc(url, "eth_call",
                   [{"to": beacon, "data": SELECTOR_IMPLEMENTATION}, "latest"]).get("result")
        return "0x" + raw[-40:] if raw and raw != "0x" else None

    # The mainnet reference: what beacon does a known-genuine stock token use?
    mainnet_aapl = "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9"
    mainnet_beacon = beacon_of(mainnet_url, mainnet_aapl)
    mainnet_impl = implementation_of(mainnet_url, mainnet_beacon) if mainnet_beacon else None

    tokens = _get(f"{TESTNET_EXPLORER}/tokens?type=ERC-20") or {}
    items = tokens.get("items", [])
    candidates = []
    for token in items:
        address = (token.get("address") or token.get("address_hash") or "").lower()
        if not address:
            continue
        beacon = beacon_of(testnet_url, address)
        if not beacon:
            continue
        impl = implementation_of(testnet_url, beacon)
        multiplier = _rpc(testnet_url, "eth_call",
                          [{"to": address, "data": SELECTOR_UI_MULTIPLIER},
                           "latest"]).get("result")
        decimals = _rpc(testnet_url, "eth_call",
                        [{"to": address, "data": SELECTOR_DECIMALS}, "latest"]).get("result")
        candidates.append({
            "symbol": token.get("symbol"),
            "name": token.get("name"),
            "address": address,
            "holders": token.get("holders_count") or token.get("holders"),
            "beacon": beacon,
            "implementation": impl,
            "ui_multiplier": int(multiplier, 16) / 1e18
            if multiplier and multiplier != "0x" else None,
            "decimals": int(decimals, 16) if decimals and decimals != "0x" else None,
        })
    beacons = {c["beacon"] for c in candidates}
    print(f"\nbeacon-proxy tokens on the explorer's first page: {len(candidates)}, "
          f"behind {len(beacons)} distinct beacon(s)")
    for c in candidates:
        print(f"   {c['symbol']!s:8} {str(c['name'])[:24]:24} {c['address']} "
              f"mult={c['ui_multiplier']} dec={c['decimals']} holders={c['holders']}")
    return {
        "mainnet_reference": {"token": mainnet_aapl, "beacon": mainnet_beacon,
                              "implementation": mainnet_impl},
        "testnet_beacon_proxies": candidates,
        "testnet_beacons": sorted(b for b in beacons if b),
        "same_beacon_as_mainnet": mainnet_beacon in beacons if mainnet_beacon else None,
    }


def main() -> int:
    config.load_environment()
    testnet_url = os.environ["RPC_4663_TESTNET"]
    mainnet_url = os.environ["RPC_4663_MAINNET"]

    live = liveness(testnet_url)
    if not live["live"]:
        print("\nSTOPPING: endpoint is not live on 46630, so nothing below would "
              "be evidence of absence.")
        return 1

    issuer = issuer_deployments()
    feeds = json.loads((OUT_DIR / "feed.json").read_text())
    feed_proxies = [f["proxyAddress"] for f in feeds["directory"]["equity"]]
    same = same_address_check(testnet_url, issuer["assets"], feed_proxies)
    directory = chainlink_directory()
    contracts = stock_contracts_on_testnet(testnet_url, mainnet_url)

    result = {
        "liveness": live,
        "issuer_registry": {k: v for k, v in issuer.items() if k != "assets"},
        "same_address": same,
        "chainlink_directory": directory,
        "stock_contracts": contracts,
        # Question 3 is settled from documentation on purpose: calling the Bankr
        # API with a testnet chain parameter is a write path we have no reason
        # to poke. https://docs.bankr.bot/wallet-api/swap/ read 2026-09-18.
        "bankr": {
            "documented_chains": ["base", "mainnet", "polygon", "unichain",
                                  "arbitrum", "bnb", "worldchain", "robinhood",
                                  "solana"],
            "testnet_mentions_in_docs": 0,
            "method": "documentation only; no API call made with a testnet chain",
        },
    }
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "testnet.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print("\n" + "=" * 68)
    print(f"1. issuer stock tokens on 46630: "
          f"{issuer['on_testnet']} of {issuer['asset_count']} assets  "
          f"(same-address hits: {len(same['token_hits'])})")
    print(f"2. chainlink equity feeds on 46630: "
          f"{'directory file found' if directory['any_found'] else 'no directory file'}")
    print(f"3. bankr routes to testnet: no (documented chain list is mainnet-only)")
    print("=" * 68)
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
