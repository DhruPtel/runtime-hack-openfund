"""Probe 0.8 — how does the fund know a token is the real one?

Read-only. One HTTPS fetch of the issuer's registry plus `eth_call` /
`eth_getStorageAt` against `RPC_4663_MAINNET`. Costs nothing.

4663 is permissionless, so anyone can deploy a token called AAPL, and the fund
must never be able to buy a counterfeit. Unit 1.2 builds the allowlist from
whatever this concludes, so the job here is to decide **what evidence makes an
asset admissible** — and, just as much, which candidate checks are carrying no
weight.

Four checks are on trial. Three have already been partly characterised and two of
those have failed in the field:

  - **the name marker** — `• Robinhood Token`. F0.3.6 made it the discriminator
    for the three GME tokens; the testnet probe then found 140 tokens carrying it
    and not one genuine (F0.T.4). Forgeable, and on testnet an anti-signal. It is
    included below only so the table shows it failing rather than omitting it.
  - **`uiMultiplier()`** — answers on all 32 real mainnet stock tokens and
    reverts on both GME fakes (F0.4.6), but five testnet tokens running the same
    contract answer it too. Necessary, not sufficient.
  - **the EIP-1967 beacon** — the check that survived testnet. Measured there,
    so it is re-measured here on **mainnet**, which has a different beacon and a
    different implementation version.
  - **the issuer registry** — `GET api.robinhood.com/rhj/assets`, found during
    the testnet probe. If this is authoritative the other three become
    corroboration rather than the test.

**The failure this unit exists to prevent** is a check that looks decisive because
it was only ever pointed at things it obviously catches. So every check runs
against every candidate, including the ones it is supposed to admit.

Run:  PYTHONPATH=src python3 -m probes.identity
"""

from __future__ import annotations

import datetime
import hashlib
import json
import os
import pathlib
import sys
import time
import urllib.error
import urllib.request

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

#: The issuer's own registry, documented at
#: `https://docs.robinhood.com/chain/stock-tokens/` as the way to "query the
#: assets API". Issuer-derived, which is what planning/PLAN.md §2 invariant 8
#: asks for.
REGISTRY_URL = "https://api.robinhood.com/rhj/assets"

USER_AGENT = "openfund-probe/0.8"
CHAIN_ID = 4663

#: EIP-1967 beacon slot, and BeaconUpgradeable's `implementation()`.
SLOT_BEACON = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"
SELECTOR_IMPLEMENTATION = "0x5c60da1b"
SELECTOR_UI_MULTIPLIER = "0xa60bf13d"
SELECTOR_NAME = "0x06fdde03"

#: The issuer's mainnet beacon, established from a known-genuine token and
#: re-confirmed by this probe rather than carried over from the testnet run —
#: the two chains have different beacons and different contract versions.
EXPECTED_BEACON = "0xe10b6f6b275de231345c20d14ab812db62151b00"

NAME_MARKER = "• Robinhood Token"

#: The candidate set. Every check runs against every row, including rows it is
#: meant to admit — a check only ever pointed at things it obviously catches
#: proves nothing. `expect` is what the *fund* should conclude, not what any
#: single check returns.
CANDIDATES = (
    # The material from F0.3.6: one real, two counterfeit, all answering to GME.
    {"label": "GME (issuer)", "address": "0x1b0e319c6a659f002271b69db8a7df2f911c153e",
     "expect": "admit", "note": "the real one"},
    {"label": "GME fake 'GameStop'", "address": "0x7e86381a763f0ecca2bdf27c54eac403ddd48123",
     "expect": "reject", "note": "counterfeit, F0.3.6"},
    {"label": "GME fake 'Greatest Meme Ever'",
     "address": "0xef67e3064bef1a27e81925ec7132f23e533bd5f6",
     "expect": "reject", "note": "counterfeit, F0.3.6"},
    # Known-genuine stock tokens. These must be ADMITTED; a check that rejects
    # them is worse than useless.
    {"label": "AAPL (issuer)", "address": "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
     "expect": "admit", "note": "genuine, has feed"},
    {"label": "NVDA (issuer)", "address": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
     "expect": "admit", "note": "genuine, has feed"},
    {"label": "TSLA (issuer)", "address": "0x322f0929c4625ed5bad873c95208d54e1c003b2d",
     "expect": "admit", "note": "genuine, has feed"},
    {"label": "ORCL (issuer)", "address": "0xb0992820e760d836549ba69bc7598b4af75dee03",
     "expect": "admit", "note": "genuine, largest multiplier"},
    # Genuine, in the registry, but NO Chainlink feed. Separates the identity
    # question from the markability question the 0.4 checkpoint decided.
    {"label": "CRM (issuer, no feed)", "address": "0xd95b44124e475743a7589e68f3d74008a5536d44",
     "expect": "admit-but-unmarkable", "note": "genuine, no equity feed"},
    # Real, important, and not a stock. The stock-specific checks must reject it
    # without that meaning it is a counterfeit.
    {"label": "USDG (cash leg)", "address": "0x5fc5360d0400a0fd4f2af552add042d716f1d168",
     "expect": "reject-as-stock", "note": "genuine token, not a stock"},
)


def _get(url: str) -> tuple[bytes, dict, int]:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return response.read(), dict(response.headers), response.status


def _rpc(url: str, method: str, params: list, tries: int = 5) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    for attempt in range(tries):
        try:
            request = urllib.request.Request(
                url, data=payload,
                headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
            with urllib.request.urlopen(request, timeout=25) as response:
                return json.loads(response.read().decode("utf-8"))
        except urllib.error.HTTPError as error:
            if error.code == 429:
                time.sleep(2 * (attempt + 1))
                continue
            return {"error": f"HTTP {error.code}"}
        except Exception:
            time.sleep(1.5)
    return {"error": "rate_limited_or_unreachable"}


# --- the registry ------------------------------------------------------------

def snapshot_registry() -> dict:
    """Fetch it once and record enough to cite it later.

    The endpoint carries **no version, no ETag and no Last-Modified**, so there
    is nothing to pin to. `planning/PLAN.md` §2 invariant 8 wants a *versioned*
    allowlist with recorded provenance; since the source supplies no version, the
    snapshot has to carry its own — a content hash and a fetch timestamp — and
    unit 1.2 must treat a hash change as the version change.
    """
    body, headers, status = _get(REGISTRY_URL)
    fetched_at = datetime.datetime.now(datetime.timezone.utc).isoformat()
    digest = hashlib.sha256(body).hexdigest()
    payload = json.loads(body)
    assets = payload.get("assets", [])

    kept = {k: v for k, v in headers.items()
            if k.lower() in ("content-type", "date", "etag", "last-modified",
                             "cache-control", "x-ratelimit-limit",
                             "x-ratelimit-remaining", "retry-after")}
    provenance = {
        "url": REGISTRY_URL,
        "fetched_at": fetched_at,
        "http_status": status,
        "bytes": len(body),
        "sha256": digest,
        "asset_count": len(assets),
        "response_headers": kept,
        "carries_version_field": any(
            k in json.dumps(payload).lower()
            for k in ('"version"', '"updated', '"revision"')),
        "auth_required": False,  # fetched with no credential at all
    }
    print(f"registry: {len(assets)} assets, {len(body)} bytes, "
          f"sha256 {digest[:16]}…")
    print(f"  fetched {fetched_at}")
    print(f"  headers kept: {kept}")
    print(f"  version field in body: {provenance['carries_version_field']}")
    return {"provenance": provenance, "assets": assets}


def registry_behaviour() -> dict:
    """Does it need auth, does it reject one, and does it rate-limit?"""
    result: dict = {}

    # Authenticated calls, to see whether a credential changes anything. Both
    # keys are read-scoped; neither is expected to matter.
    key = config.load(Role.ANALYST).secret("BANKR_KEY_READ")
    for label, header, value in (("no-auth", "User-Agent", USER_AGENT),
                                 ("x-api-key", "X-API-Key", key),
                                 ("bad-key", "X-API-Key", "bk_" + "0" * 32)):
        capture = _capture.call(label=label, url=REGISTRY_URL,
                                header_name=header, header_value=value,
                                max_body_chars=200)
        result[label] = {"status": capture.status, "elapsed_ms": capture.elapsed_ms}

    # A modest burst. Not a load test: enough to see whether limit headers or a
    # 429 appear at all, and no more.
    statuses = []
    for _ in range(10):
        try:
            _, headers, status = _get(REGISTRY_URL)
            statuses.append(status)
            if any(h.lower().startswith("x-ratelimit") for h in headers):
                result["ratelimit_headers"] = {
                    k: v for k, v in headers.items()
                    if k.lower().startswith("x-ratelimit")}
        except urllib.error.HTTPError as error:
            statuses.append(error.code)
    result["burst_10_statuses"] = statuses
    result["rate_limited_in_burst"] = any(s == 429 for s in statuses)
    print(f"\nauth: {[(k, v['status']) for k, v in result.items() if isinstance(v, dict) and 'status' in v]}")
    print(f"burst of 10: {statuses}, rate limited: {result['rate_limited_in_burst']}")
    return result


# --- the four checks ---------------------------------------------------------

def check_registry(address: str, by_address: dict) -> tuple[bool, str]:
    record = by_address.get(address.lower())
    if not record:
        return False, "absent"
    chains = {d["chainId"] for d in record["deployments"]}
    if CHAIN_ID not in chains:
        return False, f"present but not on {CHAIN_ID}"
    return True, f"{record['tokenSymbol']} · isin {record['isin']} · {record['status']}"


def check_beacon(rpc_url: str, address: str) -> tuple[bool, str]:
    raw = _rpc(rpc_url, "eth_getStorageAt", [address, SLOT_BEACON, "latest"]).get("result")
    if not raw or int(raw, 16) == 0:
        return False, "no EIP-1967 beacon slot"
    beacon = "0x" + raw[-40:]
    if beacon.lower() != EXPECTED_BEACON.lower():
        return False, f"different beacon {beacon}"
    impl = _rpc(rpc_url, "eth_call",
                [{"to": beacon, "data": SELECTOR_IMPLEMENTATION}, "latest"]).get("result")
    return True, f"beacon {beacon[:10]}… impl 0x{impl[-40:][:8]}…" if impl else (True, "beacon matches")


def check_feed(symbol: str, feed_tickers: set) -> tuple[bool, str]:
    return (symbol.upper() in feed_tickers,
            "equity feed present" if symbol.upper() in feed_tickers else "no equity feed")


def check_ui_multiplier(rpc_url: str, address: str) -> tuple[bool, str]:
    result = _rpc(rpc_url, "eth_call",
                  [{"to": address, "data": SELECTOR_UI_MULTIPLIER}, "latest"])
    raw = result.get("result")
    if raw and raw != "0x":
        return True, f"{int(raw, 16) / 1e18:.10f}"
    return False, "reverts"


def check_name_marker(rpc_url: str, address: str) -> tuple[bool, str]:
    raw = _rpc(rpc_url, "eth_call",
               [{"to": address, "data": SELECTOR_NAME}, "latest"]).get("result")
    if not raw or raw == "0x":
        return False, "no name()"
    try:
        body = bytes.fromhex(raw[2:])
        length = int.from_bytes(body[32:64], "big")
        name = body[64:64 + length].decode("utf-8", errors="replace")
    except Exception:
        return False, "undecodable"
    return NAME_MARKER in name, f"{name!r}"


def main() -> int:
    config.load_environment()
    rpc_url = os.environ["RPC_4663_MAINNET"]

    registry = snapshot_registry()
    behaviour = registry_behaviour()
    assets = registry["assets"]
    by_address = {d["contractAddress"].lower(): a
                  for a in assets for d in a["deployments"]}

    feeds = json.loads((OUT_DIR / "feed.json").read_text())
    feed_tickers = {t.upper() for t in
                    ((f.get("docs") or {}).get("baseAsset")
                     for f in feeds["directory"]["equity"]) if t}
    # The directory writes one row's ticker as RHDELL and omits two others;
    # resolve those against the registry rather than dropping them.
    feed_tickers |= {"DELL", "SGOV", "USAR"}

    rows = []
    print(f"\n{'candidate':30} {'registry':9} {'beacon':7} {'feed':6} {'uiMult':7} {'marker':7} verdict")
    for candidate in CANDIDATES:
        address = candidate["address"]
        record = by_address.get(address.lower())
        symbol = record["tokenSymbol"] if record else candidate["label"].split()[0]

        in_registry, registry_why = check_registry(address, by_address)
        beacon_ok, beacon_why = check_beacon(rpc_url, address)
        feed_ok, feed_why = check_feed(symbol, feed_tickers)
        mult_ok, mult_why = check_ui_multiplier(rpc_url, address)
        marker_ok, marker_why = check_name_marker(rpc_url, address)

        rows.append({**candidate, "symbol": symbol,
                     "registry": in_registry, "registry_why": registry_why,
                     "beacon": beacon_ok, "beacon_why": beacon_why,
                     "feed": feed_ok, "feed_why": feed_why,
                     "ui_multiplier": mult_ok, "ui_multiplier_why": mult_why,
                     "name_marker": marker_ok, "name_marker_why": marker_why})
        print(f"{candidate['label'][:30]:30} {str(in_registry):9} {str(beacon_ok):7} "
              f"{str(feed_ok):6} {str(mult_ok):7} {str(marker_ok):7} "
              f"{candidate['expect']}")
        time.sleep(0.3)

    result = {"provenance": registry["provenance"], "behaviour": behaviour,
              "candidates": rows, "expected_beacon": EXPECTED_BEACON,
              "feed_ticker_count": len(feed_tickers)}
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "identity.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    # The snapshot itself, separate, so 1.2 can consume it with its hash.
    snap = OUT_DIR / "registry_snapshot.json"
    snap.write_text(json.dumps({"provenance": registry["provenance"],
                                "assets": assets}, indent=2, sort_keys=True),
                    encoding="utf-8")
    print(f"\nwritten to {path} and {snap}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
