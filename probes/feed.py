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
import os
import pathlib
import sys
import urllib.request

from fund import config, redaction

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


# --- step 3: the chain, at one pinned block ---------------------------------

CHAIN_ID = 4663

#: AggregatorV3Interface. Selectors are recomputed from their signatures rather
#: than copied: `uiMultiplier()` matches the `0xa60bf13d` recorded at
#: `research/agent-os.md:374`, which is corroboration and not a coincidence.
SELECTOR_LATEST_ROUND = "0xfeaf968c"
SELECTOR_DECIMALS = "0x313ce567"


def _rpc(method: str, params: list) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    request = urllib.request.Request(
        os.environ["RPC_4663_MAINNET"], data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {"error": redaction.Redactor().redact(f"{type(error).__name__}: {error}")}


def _call(to: str, selector: str, block: str) -> str | None:
    return _rpc("eth_call", [{"to": to, "data": selector}, block]).get("result")


def _word(raw: str, index: int) -> int:
    """One 32-byte word of an ABI return, as an unsigned integer."""
    body = raw[2:]
    return int(body[index * 64:(index + 1) * 64], 16)


def _signed(value: int) -> int:
    """int256 two's complement. A feed answer is typed int256, so a negative is
    representable even where it would be nonsense for a price. Decoding it as
    unsigned would turn one into ~1.2e77 and a staleness check would pass it."""
    return value - (1 << 256) if value >= (1 << 255) else value


def block_pin_is_honoured(block: str) -> dict:
    """Does this RPC actually honour the block parameter, or serve latest anyway?

    `planning/PHASE-0-1.md` 0.4 asks for readings "at one pinned block", and
    `research/agent-os.md` §8 records that the one public 4663 endpoint carries
    no archive data. Those two facts sit badly together: if the node ignores the
    parameter and serves current state, every reading is still consistent with
    itself and nothing in the output would reveal it.

    So this asks the falsifying question directly — read a feed at block 1, long
    before it was deployed. An honoured pin returns empty or errors. Current data
    means the parameter is decorative and "pinned block" is not a claim we can
    make.
    """
    feed = "0x6B22A786bAa607d76728168703a39Ea9C99f2cD0"  # Robinhood AAPL / USD
    ancient = _call(feed, SELECTOR_LATEST_ROUND, "0x1")
    now = _call(feed, SELECTOR_LATEST_ROUND, block)
    honoured = ancient != now
    print(f"\nblock pin at {int(block, 16)}: "
          f"{'honoured' if honoured else 'NOT HONOURED — node served latest'} "
          f"(block 1 -> {str(ancient)[:18]})")
    return {"block_1_result": ancient, "pinned_result": now, "honoured": honoured}


def read_chain(assets: dict[str, dict]) -> tuple[str, dict, dict]:
    """Step 3 — every reading in one pass at one block."""
    chain = _rpc("eth_chainId", []).get("result")
    if not chain or int(chain, 16) != CHAIN_ID:
        raise SystemExit(f"REFUSING: chain id is {chain}, expected {CHAIN_ID}")
    block = _rpc("eth_blockNumber", []).get("result")
    print(f"\nchain {int(chain, 16)} pinned at block {int(block, 16)} ({block})")

    pin = block_pin_is_honoured(block)
    readings: dict[str, dict] = {}

    for ticker, asset in sorted(assets.items()):
        row: dict = {"ticker": ticker}
        raw = _call(asset["proxy"], SELECTOR_LATEST_ROUND, block)
        if raw and raw != "0x":
            row.update(
                round_id=_word(raw, 0),
                answer_raw=_signed(_word(raw, 1)),
                started_at=_word(raw, 2),
                updated_at=_word(raw, 3),
                answered_in_round=_word(raw, 4),
            )
            # The phase-encoded round id: high 64 bits are the proxy's phase,
            # low 64 the aggregator's own round. Worth splitting because the
            # two proxies answer with different phases for the same round.
            row["phase_id"] = row["round_id"] >> 64
            row["aggregator_round"] = row["round_id"] & ((1 << 64) - 1)
        else:
            row["error"] = "latestRoundData returned nothing"

        onchain_decimals = _call(asset["proxy"], SELECTOR_DECIMALS, block)
        row["feed_decimals_onchain"] = (
            int(onchain_decimals, 16) if onchain_decimals and onchain_decimals != "0x"
            else None
        )
        row["feed_decimals_directory"] = asset["feed_decimals"]
        row["decimals_agree"] = (
            row["feed_decimals_onchain"] == asset["feed_decimals"]
        )

        if asset["address"]:
            multiplier = _call(asset["address"], SELECTOR_UI_MULTIPLIER, block)
            # A revert here is a finding, not an error: it is what separates a
            # genuine Stock Token from an impersonator (research/agent-os.md:230).
            row["ui_multiplier_raw"] = (
                int(multiplier, 16) if multiplier and multiplier != "0x" else None
            )
            row["ui_multiplier_answers"] = row["ui_multiplier_raw"] is not None
            row["ui_multiplier"] = (
                row["ui_multiplier_raw"] / 1e18
                if row["ui_multiplier_raw"] is not None else None
            )

        if "answer_raw" in row and row["feed_decimals_onchain"] is not None:
            row["feed_price"] = row["answer_raw"] / (10 ** row["feed_decimals_onchain"])
        readings[ticker] = row

    answered = sum(1 for r in readings.values() if "feed_price" in r)
    multiplied = sum(1 for r in readings.values() if r.get("ui_multiplier") not in (None, 1.0))
    print(f"{answered} of {len(readings)} feeds answered; "
          f"{multiplied} tokens carry a multiplier other than exactly 1.0")
    return block, pin, readings


def main() -> int:
    config.load_environment()
    directory = enumerate_directory()
    assets = resolve_assets(directory["equity"])
    unresolved = {t: a["status"] for t, a in assets.items() if a["status"] != "ok"}
    print(f"\naddresses: {len(assets) - len(unresolved)} of {len(assets)} "
          f"equity tickers resolved to one RH-marked token")
    if unresolved:
        print(f"  unresolved: {unresolved}")

    coverage = gecko_coverage(assets)
    block, pin, readings = read_chain(assets)
    result = {"directory": directory, "assets": assets, "gecko": coverage,
              "block": block, "block_pin": pin, "readings": readings}
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "feed.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
