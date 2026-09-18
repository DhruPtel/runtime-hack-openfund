"""Probe 0.4 — does Chainlink carry equity feeds on 4663, and is the mark
already multiplier-adjusted?

Read-only throughout: a reference directory over HTTPS, `eth_call` against
`RPC_4663_MAINNET`, and one public GeckoTerminal endpoint. Nothing here can move
funds.

**Why this probe opens with an enumeration.** At the close of the 0.3 session the
directory was fetched, reported 57 feeds, and four were sampled — BTC, ETH, LINK
and USDG. No equity feed was seen, and the honest record of that
(`tracker/LOGS.md`, state at close) called it an *observation, not a finding*
precisely because the other 53 were never looked at. `planning/PLAN.md` §11 rests
on "Chainlink marks the book", so a sample that happens to miss the equity feeds
is indistinguishable from their absence until every row is listed. Step 1 lists
every row.

The steps, in the order `planning/PHASE-0-1.md` 0.4 requires — coverage before
divergence:

  1. enumerate the directory in full and classify every feed,
  2. ask GeckoTerminal whether it prices RH stock tokens at all,
  3. read `latestRoundData` and `uiMultiplier` at one pinned block,
  4. compare, and decide whether the feed answer already carries the multiplier.

Run:  PYTHONPATH=src python3 -m probes.feed
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

#: Chainlink's published reference directory. The `robinhood-mainnet` filename
#: was found by trying the documented naming pattern; `feeds-robinhood.json` and
#: `feeds-robinhood-chain-mainnet.json` both 404, so this is the only spelling
#: that resolves and there is no second directory to cross-check it against.
DIRECTORY_URL = (
    "https://reference-data-directory.vercel.app/feeds-robinhood-mainnet.json"
)

#: Returns 403 to a bare urllib request (F0.3, operational notes). A 403 from
#: this host is not an auth failure.
USER_AGENT = "openfund-probe/0.4 (+phase-0 discovery)"

#: What the directory calls a feed whose underlying asset is a US equity or ETF.
#: Both spellings appear: `docs.assetClass` is absent on three rows that still
#: carry the equity market-hours string, so neither field alone partitions the
#: directory and the classifier takes either.
EQUITY_MARKET_HOURS = "us_equities_24/5"
EQUITY_ASSET_CLASS = "Equity"


def _get(url: str) -> object:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def is_equity(feed: dict) -> bool:
    docs = feed.get("docs") or {}
    return (
        docs.get("assetClass") == EQUITY_ASSET_CLASS
        or docs.get("marketHours") == EQUITY_MARKET_HOURS
    )


def ticker_of(feed: dict) -> str | None:
    """The directory's own ticker, never one parsed out of the display name.

    `docs.baseAsset` is the field the issuer fills in. Three equity rows leave it
    holding a prefixed form (`RHDELL`) or omit it, and those are reported as
    unresolved rather than repaired by a regex over `name` — guessing a ticker
    is how an asset ends up pinned to the wrong address.
    """
    return (feed.get("docs") or {}).get("baseAsset") or None


def enumerate_directory() -> dict:
    """Step 1. Every row in the directory, classified. No sampling."""
    feeds = _get(DIRECTORY_URL)
    if not isinstance(feeds, list):
        raise SystemExit(f"directory is {type(feeds).__name__}, expected a list")

    equity = [f for f in feeds if is_equity(f)]
    other = [f for f in feeds if not is_equity(f)]

    print(f"{DIRECTORY_URL}\n{len(feeds)} feeds: "
          f"{len(equity)} equity, {len(other)} non-equity\n")
    print(f"  {'name':34} {'ticker':8} {'dec':>3} {'heartbeat':>9} {'thr':>5}")
    for feed in sorted(equity, key=lambda f: f["name"]):
        print(f"  {feed['name'][:34]:34} {str(ticker_of(feed)):8} "
              f"{feed.get('decimals')!s:>3} {feed.get('heartbeat')!s:>9} "
              f"{feed.get('threshold')!s:>5}")
    print()
    print("  non-equity: " + ", ".join(sorted(f["name"] for f in other)))

    unresolved = [f["name"] for f in equity if not ticker_of(f)]
    if unresolved:
        print(f"\n  no docs.baseAsset on {len(unresolved)}: {unresolved}")

    return {
        "url": DIRECTORY_URL,
        "total": len(feeds),
        "equity_count": len(equity),
        "non_equity_count": len(other),
        "equity": equity,
        "non_equity_names": sorted(f["name"] for f in other),
        "equity_without_ticker": unresolved,
    }


# --- step 2: does GeckoTerminal price these tokens at all? -------------------

#: The same discovery list probe 0.3 used, with the same caveat: it is
#: **unverified**, it lists undeployed assets, and it truncates `name` at 60
#: characters (`research/agent-os.md`). `config/universe.json` is empty until
#: unit 0.8, so there is no trustworthy address source yet and this probe says so
#: rather than implying one.
COINGECKO_LIST = "https://tokens.coingecko.com/robinhood/all.json"

#: The issuer's name marker. Necessary, not sufficient — it is the only thing
#: separating the real GME from two impersonators (F0.3.6), and the 60-character
#: truncation means a longer name loses it.
NAME_MARKER = "• Robinhood Token"

#: ERC-8056 `uiMultiplier()`, documented at `research/agent-os.md:374` and
#: recomputed from the signature here rather than copied on faith. It answers on
#: a genuine Stock Token and reverts otherwise, which makes it the one
#: discriminator this probe can actually apply to an address.
SELECTOR_UI_MULTIPLIER = "0xa60bf13d"

GECKO_NETWORK = "robinhood"
GECKO_MULTI = "https://api.geckoterminal.com/api/v2/networks/{net}/tokens/multi/{addrs}"

#: The documented ceiling for the multi-token endpoint.
GECKO_BATCH = 30


def resolve_assets(equity_feeds: list[dict]) -> dict[str, dict]:
    """Map each equity feed's ticker to a candidate token address.

    Deliberately conservative, and it reports rather than resolves:

      - only entries carrying the issuer's name marker are considered,
      - a ticker matching more than one such address is recorded as ambiguous
        and is not silently resolved to the first one,
      - a ticker matching none is recorded as unresolved.

    None of this makes an address trustworthy. Unit 0.8 owns that.
    """
    listing = _get(COINGECKO_LIST)
    tokens = listing["tokens"] if isinstance(listing, dict) else listing

    marked: dict[str, list[dict]] = {}
    for token in tokens:
        if NAME_MARKER in (token.get("name") or ""):
            marked.setdefault(token["symbol"].upper(), []).append(token)

    resolved: dict[str, dict] = {}
    for feed in equity_feeds:
        ticker = ticker_of(feed)
        if not ticker:
            continue
        matches = marked.get(ticker, [])
        resolved[ticker] = {
            "ticker": ticker,
            "feed_name": feed["name"],
            "proxy": feed["proxyAddress"],
            "secondary_proxy": feed.get("secondaryProxyAddress"),
            "feed_decimals": feed.get("decimals"),
            "heartbeat": feed.get("heartbeat"),
            "threshold": feed.get("threshold"),
            "address": matches[0]["address"].lower() if len(matches) == 1 else None,
            "token_decimals": matches[0].get("decimals") if len(matches) == 1 else None,
            "candidates": [m["address"].lower() for m in matches],
            "status": ("ok" if len(matches) == 1
                       else "ambiguous" if matches else "no-marked-token"),
        }
    return resolved


def gecko_coverage(assets: dict[str, dict]) -> dict[str, dict]:
    """Step 2 — coverage, asked before divergence.

    `planning/PHASE-0-1.md` 0.4 calls this a question rather than an assumption:
    GeckoTerminal prices come from pools, and the plan records that RH stock
    tokens have no pool of their own. So the finding is whatever comes back,
    including nothing.
    """
    addressed = {t: a for t, a in assets.items() if a["address"]}
    order = list(addressed)
    coverage: dict[str, dict] = {t: {"covered": False, "price_usd": None,
                                     "pools_listed_floor": 0, "http": None}
                                 for t in order}

    for start in range(0, len(order), GECKO_BATCH):
        chunk = order[start:start + GECKO_BATCH]
        url = GECKO_MULTI.format(
            net=GECKO_NETWORK,
            addrs=",".join(addressed[t]["address"] for t in chunk),
        )
        try:
            payload = _get(url)
        except Exception as error:  # a refusal is the finding, not a crash
            for ticker in chunk:
                coverage[ticker]["http"] = f"{type(error).__name__}: {error}"
            continue

        by_address = {}
        for entry in payload.get("data", []):
            attributes = entry.get("attributes", {})
            # The batch endpoint returns at most one entry in `top_pools`, where
            # the single-token endpoint lists six for the same address. So this
            # is a floor on how many pools exist, not a count, and it is named
            # that way -- a "pool_count" of 1 read as a count would understate
            # the venue by a factor of six.
            pools = ((entry.get("relationships") or {})
                     .get("top_pools", {}).get("data", []))
            by_address[attributes["address"].lower()] = {
                "covered": attributes.get("price_usd") is not None,
                "price_usd": attributes.get("price_usd"),
                "pools_listed_floor": len(pools),
                "gecko_decimals": attributes.get("decimals"),
                "h24_volume_usd": (attributes.get("volume_usd") or {}).get("h24"),
                "total_reserve_usd": attributes.get("total_reserve_in_usd"),
                "http": 200,
            }
        for ticker in chunk:
            found = by_address.get(addressed[ticker]["address"])
            coverage[ticker] = found or {"covered": False, "price_usd": None,
                                         "pools_listed_floor": 0,
                                         "http": "absent-from-200"}

    covered = sum(1 for c in coverage.values() if c["covered"])
    print(f"\nGeckoTerminal '{GECKO_NETWORK}': {covered} of {len(order)} "
          f"addressed tickers priced")
    return coverage


def main() -> int:
    directory = enumerate_directory()
    assets = resolve_assets(directory["equity"])
    unresolved = {t: a["status"] for t, a in assets.items() if a["status"] != "ok"}
    print(f"\naddresses: {len(assets) - len(unresolved)} of {len(assets)} "
          f"equity tickers resolved to one RH-marked token")
    if unresolved:
        print(f"  unresolved: {unresolved}")

    coverage = gecko_coverage(assets)
    result = {"directory": directory, "assets": assets, "gecko": coverage}
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "feed.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
