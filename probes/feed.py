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


def main() -> int:
    result = {"directory": enumerate_directory()}
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "feed.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
