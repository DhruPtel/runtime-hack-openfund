"""Unit 1.6: the snapshot builder, offline, on the real pinned universe.

The live build is `python -m fund.run.snapshot`, not part of `make test`.
"""

from __future__ import annotations

import ast
import dataclasses
import json
from pathlib import Path

import pytest

from fund.core import snapshot, universe, valuation
from fund.core.types import (
    BPS, USD, Amount, AssetId, BlockRef, Check, FetchStatus, Fixed, Instant, Observation, Price,
    Quote, Series, Source,
)

U = universe.load()
CHAIN = 4663
SAT = 1_789_776_000                  # Sat 2026-09-19 00:00:00Z
DAY, HOUR = 86_400, 3_600
BLOCK = BlockRef(CHAIN, 66_700_000, Instant.from_seconds(SAT + 2 * HOUR), "0x" + "ab" * 32)
BUILT = Instant.from_seconds(SAT + 2 * HOUR + 30)
RULE = valuation.DivergenceRule(max_bps=Fixed(100, 0, BPS), min_volume_usd=Fixed(1_000_000, 0, USD))
EXECUTABLE = Check(None, "a quote is a price, not a fill (F0.3.3, F0.5.1)")
BEACON = Check(True, "resolves to the issuer beacon")


def listed(symbol: str) -> AssetId:
    """Test setup only: the product never resolves an asset by ticker."""
    return next(a for a, r in U.records.items() if r.symbol == symbol and a.chain_id == CHAIN)


def feed_point(asset, answer: int, updated: int, round_id: int, block=BLOCK) -> Observation:
    return Observation(value=Price(answer, 8, asset.id, USD),
                       source=Source("chainlink-feed", asset.feed.proxy.address),
                       source_time=Instant.from_seconds(updated), fetch_time=Instant.from_seconds(SAT),
                       block=block, status=FetchStatus.OK, source_ref=str(round_id))


def week(asset, answers, *, newest_at=SAT - 4 * HOUR, reach=True) -> Series:
    """Rounds oldest first, the newest at `newest_at`. Four days apart they reach
    back past the seven-day window, as coverage claims; a day apart they do not."""
    count, gap = len(answers), (4 * DAY if reach else DAY)
    start = newest_at - (count - 1) * gap
    points = tuple(feed_point(asset, a, start + i * gap, 1000 + i) for i, a in enumerate(answers))
    window = Instant.from_seconds(BLOCK.timestamp.epoch_ms // 1000 - 7 * DAY)
    coverage = (Check(True, f"{count} rounds reach back to the window start") if reach else
                Check(False, "history starts at phase 1 round 1, 3 days after the window start"))
    return Series(asset=asset.id, source=points[0].source, fetch_time=Instant.from_seconds(SAT),
                  status=FetchStatus.OK, points=points, window_start=window, coverage=coverage)


def offchain(value, system="geckoterminal", status=FetchStatus.OK, detail=None, at=SAT + 2 * HOUR + 5):
    return Observation(value=value, source=Source(system, "networks/robinhood/tokens/x"),
                       source_time=None, fetch_time=Instant.from_seconds(at), block=None,
                       status=status, detail=detail or ("ok" if status is FetchStatus.OK else "absent"))


def quote_for(asset, impact: int, at=SAT + 2 * HOUR + 10) -> Observation:
    q = Quote(sell=Amount(25_001_227, 6, U.cash_leg), buy=Amount(98_238_794_658_145_448, 18, asset.id),
              min_buy=Amount(93_326_854_925_238_176, 18, asset.id), price_impact=Fixed(impact, 0, BPS),
              swap_impact=Fixed(impact, 0, BPS), max_price_impact=Fixed(1500, 0, BPS),
              fee=Fixed(0, 0, BPS), fee_waived=False, slippage=Fixed(500, 0, BPS),
              sell_price=Price.parse("0.9978409512787565", U.cash_leg, USD),
              buy_price=Price.parse("253.0839", asset.id, USD), quote_id="q-" + asset.symbol)
    return Observation(value=q, source=Source("bankr-quote", "/wallet/swap-quote"), source_time=None,
                       fetch_time=Instant.from_seconds(at), block=None, status=FetchStatus.OK,
                       source_ref=q.quote_id)


def stock(symbol, *, answers=(25_000_000_000, 25_100_000_000, 25_260_000_000), corroborator="252.70",
          volume="2193251.17", impact=18, closed=True, fresh=Check(True, "fresh in open-session time"),
          corroboration=None, reach=True) -> snapshot.StockInputs:
    asset = U.stock(listed(symbol), BEACON)
    series = week(asset, answers, reach=reach)
    trade_ok = impact <= 50
    return snapshot.StockInputs(
        asset=asset, reading=series.newest, fresh=fresh, series=series, closed_session=closed,
        corroboration=corroboration or offchain(Price.parse(corroborator, asset.id, USD)),
        volume=offchain(Fixed.parse(volume, USD)), independent=True, quote=quote_for(asset, impact),
        tradeable=Check(True, "quoted at the size asked") if trade_ok else
        Check(False, f"[impact] swapImpactBps {impact} exceeds 50, compared signed"),
        tradeable_rule=None if trade_ok else "impact", executable=EXECUTABLE)


def marked(asset, answer) -> snapshot.MarkedInputs:
    reading = Observation(value=Price(answer, 8, asset.id, USD),
                          source=Source("chainlink-feed", asset.feed.proxy.address),
                          source_time=Instant.from_seconds(SAT - HOUR), fetch_time=Instant.from_seconds(SAT),
                          block=BLOCK, status=FetchStatus.OK, source_ref="1")
    return snapshot.MarkedInputs(asset=asset, reading=reading, fresh=Check(True, "fresh"))


def balance(asset_id: AssetId, raw: int, decimals: int) -> Observation:
    return Observation(value=Amount(raw, decimals, asset_id), source=Source("erc20-balance", asset_id.address),
                       source_time=None, fetch_time=Instant.from_seconds(SAT), block=BLOCK,
                       status=FetchStatus.OK)


def inputs(*stocks, extra_balances=None, held_outside=None, built=BUILT) -> snapshot.Inputs:
    balances = {U.cash_leg: balance(U.cash_leg, 78_742, 6),
                U.gas_asset: balance(U.gas_asset, 460_162_486_507_929, 18)}
    balances |= extra_balances or {}
    return snapshot.Inputs(
        block=BLOCK, built_at=built, stocks=tuple(stocks), cash=marked(U.cash(), 99_995_090),
        gas=marked(U.gas(), 261_662_681_386), wallet=universe.ChainAddress(CHAIN, "0x" + "93" * 20),
        balances=balances, held_outside=held_outside or {}, closed_sessions=("us_equities_24/5",),
        divergence_rule=RULE, rules={"freshness": "heartbeat + 3600 s of open session"},
        config={"thresholds.json": "0" * 64})


def entry(snap, symbol):
    return next(e for e in snap.document["assets"] if e["asset"]["symbol"] == symbol)


# --- an entry a person can read -------------------------------------------------------------------

def test_a_tradeable_entry_says_what_the_fund_knows_in_plain_fields():
    e = entry(snapshot.build(inputs(stock("NVDA")), U), "NVDA")
    assert e["status"] == {"value": "tradeable", "rule": None, "verdict": True,
                           "reason": "every rule passed: " + ", ".join(snapshot.ORDER)}
    assert e["mark"]["price_usd"] == "252.6" and e["mark"]["fresh"]["verdict"] is True
    assert e["mark"]["round_id"] == "1002" and e["mark"]["updated_at"] == "2026-09-18T20:00:00Z"
    assert e["identity"]["verdict"] is True and e["markability"]["verdict"] is True
    assert e["corroboration"]["price_usd"] == "252.7" and e["corroboration"]["session"] == "closed"
    assert e["quote"]["sell_amount"] == "25.001227" and e["quote"]["swap_impact_bps"] == "18"
    assert e["quote"]["executable"]["verdict"] is None
    assert e["timeline"]["columns"] == ["updated_at", "price_usd"]
    assert e["timeline"]["points"][-1] == ["2026-09-18T20:00:00Z", "252.6"]
    assert e["timeline"]["rounds"] == 3 and e["timeline"]["coverage"]["verdict"] is True


def test_the_bytes_are_canonical_json_with_no_floats_and_parse_back_exactly():
    snap = snapshot.build(inputs(stock("NVDA"), stock("AMZN")), U)
    parsed = json.loads(snap.body)
    assert snapshot.canonical(parsed) == snap.body and snap.body.endswith(b"\n")
    assert b'["2026-09-18T20:00:00Z", "252.6"]' in snap.body  # one point, one line
    def leaves(node):
        if isinstance(node, dict):
            for v in node.values():
                yield from leaves(v)
        elif isinstance(node, list):
            for v in node:
                yield from leaves(v)
        else:
            yield node
    assert not any(isinstance(v, float) for v in leaves(parsed))


def test_the_canonical_form_refuses_a_float_and_an_unsafe_integer():
    with pytest.raises(TypeError):
        snapshot.canonical({"price": 1.5})
    with pytest.raises(ValueError):
        snapshot.canonical({"round": 2**64})


# --- the hash is the version ------------------------------------------------------------------

def test_identical_inputs_in_any_order_give_one_hash():
    a = snapshot.build(inputs(stock("NVDA"), stock("AMZN")), U)
    b = snapshot.build(inputs(stock("AMZN"), stock("NVDA")), U)
    assert a.sha256 == b.sha256 and a.body == b.body


@pytest.mark.parametrize("change", [
    {"corroborator": "252.71"},                                   # one GeckoTerminal price
    {"answers": (25_000_000_000, 25_100_000_000, 25_260_000_001)},  # one feed answer, one unit
    {"impact": 17},                                               # one quote field
])
def test_any_reported_change_changes_the_hash(change):
    assert snapshot.build(inputs(stock("NVDA")), U).sha256 != \
        snapshot.build(inputs(stock("NVDA", **change)), U).sha256


def test_the_judging_instant_is_part_of_the_snapshot():
    later = Instant.from_seconds(SAT + 2 * HOUR + 31)
    assert snapshot.build(inputs(stock("NVDA")), U).sha256 != \
        snapshot.build(inputs(stock("NVDA"), built=later), U).sha256


def test_a_chain_reread_at_the_same_block_gives_the_same_hash():
    first = stock("NVDA")
    reread_points = tuple(dataclasses.replace(p, fetch_time=Instant.from_seconds(SAT + 999))
                          for p in first.series.points)
    again = dataclasses.replace(first, series=dataclasses.replace(first.series, points=reread_points),
                                reading=reread_points[-1])
    assert snapshot.build(inputs(first), U).sha256 == snapshot.build(inputs(again), U).sha256


# --- the pipeline: each status at its own rule --------------------------------------------------

def test_in_a_closed_session_divergence_is_a_finding_carried_in_the_entry():
    snap = snapshot.build(inputs(stock("AMZN", corroborator="265.87982073", closed=True)), U)
    e = entry(snap, "AMZN")
    assert e["status"]["value"] == "tradeable" and e["corroboration"]["session"] == "closed"
    [finding] = e["findings"]
    assert finding["kind"] == "closed-session divergence" and finding["beyond_open_session_limit"] is True
    assert finding["divergence_bps"] == e["corroboration"]["divergence_bps"] == "-499.47"
    assert snap.document["summary"]["findings"] == [["AMZN", "closed-session divergence", "-499.47"]]


def test_in_an_open_session_the_same_divergence_is_vetoed():
    e = entry(snapshot.build(inputs(stock("AMZN", corroborator="265.87982073", closed=False)), U), "AMZN")
    assert e["status"]["value"] == "divergence_veto" and e["status"]["rule"] == "divergence"
    assert e["findings"] == []


def test_absent_corroboration_stays_undetermined_and_never_becomes_zero():
    missing = offchain(None, status=FetchStatus.ABSENT, detail="GeckoTerminal did not list this address")
    e = entry(snapshot.build(inputs(stock("NVDA", corroboration=missing)), U), "NVDA")
    c = e["corroboration"]
    assert c["price_usd"] is None and c["divergence_bps"] is None and c["verdict"]["verdict"] is None
    assert c["read"] == "absent" and "did not list" in c["read_reason"]
    assert e["status"]["value"] == "uncorroborated" and e["status"]["verdict"] is None


def test_below_the_line_the_asset_is_excluded_and_its_quote_verdict_still_shows():
    e = entry(snapshot.build(inputs(stock("CLSK", volume="242.1", impact=991)), U), "CLSK")
    assert e["status"]["value"] == "below_corroborator_line"
    assert e["quote"]["tradeable"]["verdict"] is False and "[impact]" in e["quote"]["tradeable"]["reason"]


def test_a_quote_refused_at_impact_makes_a_liquid_name_not_tradeable():
    e = entry(snapshot.build(inputs(stock("NVDA", impact=60)), U), "NVDA")
    assert e["status"]["value"] == "not_tradeable" and e["status"]["rule"] == "impact"


def test_a_stale_mark_is_no_mark_at_freshness():
    stale = Check(False, "a gap this long in an open session is stale")
    e = entry(snapshot.build(inputs(stock("NVDA", fresh=stale)), U), "NVDA")
    assert e["status"]["value"] == "no_mark" and e["status"]["rule"] == "freshness"
    assert e["mark"]["price_usd"] is None


def test_a_short_series_says_it_is_short():
    e = entry(snapshot.build(inputs(stock("NVDA", reach=False)), U), "NVDA")
    assert e["timeline"]["coverage"]["verdict"] is False and "3 days after" in e["timeline"]["coverage"]["reason"]
    assert e["timeline"]["rounds"] == 3


# --- holdings: never silently zero ------------------------------------------------------------

def test_a_held_asset_with_no_feed_is_carried_without_a_value():
    crm = listed("CRM")
    held = U.held_asset(crm, 18, BEACON)
    snap = snapshot.build(inputs(stock("NVDA"), extra_balances={crm: balance(crm, 10**18, 18)},
                                 held_outside={crm: held}), U)
    [row] = [h for h in snap.document["holdings"] if h["asset"]["symbol"] == "CRM"]
    assert row["balance"] == "1" and row["value_usd"] is None
    assert "not zero" in row["value_reason"] and row["status"]["value"] == "unmarkable"
    assert ["CRM", crm.address] in snap.document["outside_universe"]["assets"]


def test_cash_is_valued_at_its_own_mark_and_an_empty_stock_is_not_a_holding():
    zero = {listed("NVDA"): balance(listed("NVDA"), 0, 18)}
    snap = snapshot.build(inputs(stock("NVDA"), extra_balances=zero), U)
    rows = {h["asset"]["symbol"]: h for h in snap.document["holdings"]}
    assert set(rows) == {"ETH", "USDG"}
    assert rows["USDG"]["value_usd"] == "0.0787381337678" and rows["USDG"]["mark"]["price_usd"] == "0.9999509"


def test_everything_registry_listed_without_a_feed_is_listed_as_outside_the_universe():
    snap = snapshot.build(inputs(stock("NVDA")), U)
    stocks_with_feeds = sum(1 for a in U.feeds if a in U.records)
    listed_here = sum(1 for a in U.records if a.chain_id == CHAIN)
    assert snap.document["outside_universe"]["count"] == listed_here - stocks_with_feeds


# --- refusals, each at its rule ------------------------------------------------------------------

def test_a_reading_from_another_block_is_refused_at_block_pin():
    first = stock("NVDA")
    elsewhere = dataclasses.replace(first.reading, block=BlockRef(CHAIN, BLOCK.number - 1,
                                                                  BLOCK.timestamp, "0x" + "cd" * 32))
    with pytest.raises(snapshot.SnapshotRefused) as refused:
        snapshot.build(inputs(dataclasses.replace(first, reading=elsewhere)), U)
    assert refused.value.rule == snapshot.RULE_BLOCK_PIN


def test_a_round_dated_after_the_pinned_block_is_refused_at_after_pin():
    first = stock("NVDA")
    future = dataclasses.replace(first.reading, source_time=Instant.from_seconds(SAT + 3 * HOUR))
    with pytest.raises(snapshot.SnapshotRefused) as refused:
        snapshot.build(inputs(dataclasses.replace(first, reading=future)), U)
    assert refused.value.rule == snapshot.RULE_AFTER_PIN


def test_a_series_that_does_not_end_at_the_mark_is_refused_at_series_head():
    first = stock("NVDA")
    other = dataclasses.replace(first.reading, source_ref="999")
    with pytest.raises(snapshot.SnapshotRefused) as refused:
        snapshot.build(inputs(dataclasses.replace(first, reading=other)), U)
    assert refused.value.rule == snapshot.RULE_SERIES_HEAD


def test_two_readings_for_one_asset_are_refused_at_duplicate():
    with pytest.raises(snapshot.SnapshotRefused) as refused:
        snapshot.build(inputs(stock("NVDA"), stock("NVDA")), U)
    assert refused.value.rule == snapshot.RULE_DUPLICATE


# --- 1.1's measured cases, now in the real snapshot ---------------------------------------------

def test_the_measured_cases_live_together_in_one_hashed_snapshot():
    """A week of history with a fresh newest point, a quote with negative impact,
    a corroborator that was unreachable rather than false, and a held asset with
    no feed. They were 1.1's cases for its snapshot type; they are this one's."""
    crm = listed("CRM")
    unreachable = offchain(None, status=FetchStatus.UNREACHABLE, detail="timeout after 20 s")
    snap = snapshot.build(inputs(stock("TSLA", impact=-15), stock("NVDA", corroboration=unreachable),
                                 extra_balances={crm: balance(crm, 10**17, 18)},
                                 held_outside={crm: U.held_asset(crm, 18, BEACON)}), U)
    tsla, nvda = entry(snap, "TSLA"), entry(snap, "NVDA")
    assert tsla["quote"]["swap_impact_bps"] == "-15" and tsla["status"]["value"] == "tradeable"
    assert nvda["corroboration"]["read"] == "unreachable" and nvda["status"]["verdict"] is None
    assert [h["value_usd"] for h in snap.document["holdings"] if h["asset"]["symbol"] == "CRM"] == [None]
    assert json.loads(snap.body) == json.loads(snapshot.canonical(snap.document))


def test_core_snapshot_imports_nothing_from_adapters_anywhere():
    tree = ast.parse(Path(snapshot.__file__).read_text())
    modules = {n.module or "" for n in ast.walk(tree) if isinstance(n, ast.ImportFrom)}
    modules |= {a.name for n in ast.walk(tree) if isinstance(n, ast.Import) for a in n.names}
    assert not any("adapters" in m for m in modules)
