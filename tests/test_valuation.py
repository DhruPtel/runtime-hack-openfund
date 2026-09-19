"""Unit 1.4: the one valuation function and the tiered cross-check, offline.

Assets come from the real pinned universe in `config/registry/`. The AMZN case is
probe 0.4's own reading (`probes/out/feed.json`, block 66354932): the feed at
252.60, GeckoTerminal at 265.87982073 on $2,193,251.17 of 24h volume, which
F0.4.5 recorded as a 499.5 bps divergence on a liquid name.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path

import pytest

from fund.core import universe, valuation
from fund.core.types import (
    USD, Amount, AssetId, BlockRef, Check, FetchStatus, Fixed, Instant, Observation, Price, Source,
    UniverseStatus,
)

U = universe.load()
CHAIN = 4663
BLOCK = BlockRef(CHAIN, 66354932, Instant.from_seconds(1789746000))
FETCHED = Instant.from_seconds(1789746005)
FRESH = Check(True, "age 50s of open session against heartbeat 86400s + margin 3600s")
BEACON = Check(True, "not what these tests are about")
RULE = valuation.DivergenceRule(max_bps=Fixed(100, 0, "bps"), min_volume_usd=Fixed(1_000_000, 0, USD))


def listed(symbol: str) -> AssetId:
    """Test setup only: the product never resolves an asset by ticker."""
    return next(a for a, r in U.records.items() if r.symbol == symbol and a.chain_id == CHAIN)


AMZN = U.stock(listed("AMZN"), BEACON)
GME = U.stock(listed("GME"), BEACON)
CRM = U.stock(listed("CRM"), BEACON)       # genuine, listed, and has no feed (F0.8.2)
USDG, ETH = U.cash(), U.gas()


def reading(asset, answer: int, *, proxy: str | None = None, base: AssetId | None = None,
            status=FetchStatus.OK) -> Observation:
    source = Source("chainlink-feed", proxy or asset.feed.proxy.address)
    if status is not FetchStatus.OK:
        return Observation(value=None, source=source, source_time=None, fetch_time=FETCHED,
                           block=BLOCK, status=status, detail="[transport] RPC_4663_MAINNET: refused")
    return Observation(value=Price(answer, 8, base or asset.id, USD), source=source,
                       source_time=Instant.from_seconds(1789745950), fetch_time=FETCHED, block=BLOCK,
                       status=FetchStatus.OK, source_ref="18446744073709552407")


def gecko(asset, price: str | None, volume: str | None = "2193251.17210313"):
    def observe(value, detail):
        status = FetchStatus.OK if value is not None else FetchStatus.ABSENT
        return Observation(value=value, source=Source("geckoterminal", f"networks/robinhood/tokens/"
                                                                         f"{asset.id.address}"),
                           source_time=None, fetch_time=FETCHED, block=None, status=status,
                           detail=detail)
    return (observe(Price.parse(price, asset.id, USD) if price else None, "price_usd"),
            observe(Fixed.parse(volume, USD) if volume else None, "volume_usd.h24"))


def balance(asset, raw: int) -> Observation:
    return Observation(value=Amount(raw, asset.decimals, asset.id),
                       source=Source("erc20-balance", asset.id.address), source_time=None,
                       fetch_time=FETCHED, block=BLOCK, status=FetchStatus.OK)


# --- value: the one function ------------------------------------------------------------

def test_value_is_raw_units_times_the_mark_exactly():
    one_and_a_half = Amount.from_units("1.5", 18, AMZN.id)
    worth = valuation.value(one_and_a_half, Price(25260000000, 8, AMZN.id, USD))
    assert worth.unit == USD and worth.decimals == 26
    assert worth.same_value(Fixed.parse("378.9", USD))


def test_value_refuses_another_assets_price():
    with pytest.raises(TypeError):
        valuation.value(Amount(1, 18, AMZN.id), Price(1, 8, GME.id, USD))


def test_value_does_not_apply_the_multiplier_again():
    # Every registry asset carries a multiplier; the value ignores it, because the
    # feed answer already incorporates it per the documentation (F0.4.4).
    assert AMZN.registry.current_multiplier is not None
    worth = valuation.value(Amount.from_units("1", 18, AMZN.id), Price(25260000000, 8, AMZN.id, USD))
    assert worth.same_value(Fixed.parse("252.6", USD))


# --- the mark -----------------------------------------------------------------------------

def test_the_pinned_feeds_fresh_answer_is_the_mark():
    m = valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH)
    assert m.check.passes and m.rule is None and m.price == Price(25260000000, 8, AMZN.id, USD)


def test_an_answer_from_another_feed_is_refused_at_feed_match():
    # GME's feed, labelled as AMZN: the ticker-style mistake 1.2's address map exists to stop.
    m = valuation.mark(AMZN, reading(AMZN, 2255175000, proxy=GME.feed.proxy.address), FRESH)
    assert m.rule == valuation.RULE_FEED_MATCH and m.check.value is False and m.price is None


def test_a_reading_priced_for_another_asset_is_refused_at_feed_match():
    m = valuation.mark(AMZN, reading(AMZN, 25260000000, base=GME.id), FRESH)
    assert m.rule == valuation.RULE_FEED_MATCH


@pytest.mark.parametrize("fresh, value", [
    (Check(False, "a gap this long in an open session is stale"), False),
    (Check(None, "a round inside the closed span contradicts the inference"), None),
])
def test_a_mark_that_is_not_fresh_is_refused_at_freshness(fresh, value):
    m = valuation.mark(AMZN, reading(AMZN, 25260000000), fresh)
    assert m.rule == valuation.RULE_FRESHNESS and m.check.value is value and m.price is None


def test_an_unread_feed_is_undetermined_at_reading():
    m = valuation.mark(AMZN, reading(AMZN, 0, status=FetchStatus.UNREACHABLE), FRESH)
    assert m.rule == valuation.RULE_READING and m.check.value is None


def test_an_asset_with_no_feed_has_no_mark_at_markability():
    m = valuation.mark(CRM, None, FRESH)
    assert m.rule == valuation.RULE_MARKABILITY and m.check.value is False


# --- holdings: never silently zero -------------------------------------------------------------

def test_an_unmarkable_holding_is_carried_with_no_value_not_zero():
    held = valuation.value_holding(CRM, balance(CRM, 10**18), valuation.mark(CRM, None, FRESH),
                                   universe_status=UniverseStatus.UNMARKABLE,
                                   universe_reason="[markability] no Chainlink feed")
    assert held.value is None and held.mark is None and held.balance.value.raw == 10**18
    assert "not zero" in held.value_reason and "[markability]" in held.value_reason


def test_a_stale_mark_leaves_the_holding_unvalued():
    stale = valuation.mark(AMZN, reading(AMZN, 25260000000), Check(False, "stale"))
    held = valuation.value_holding(AMZN, balance(AMZN, 10**18), stale,
                                   universe_status=UniverseStatus.TRADEABLE, universe_reason=None)
    assert held.value is None and "[freshness]" in held.value_reason


def test_an_unread_balance_is_not_a_zero_balance():
    unread = Observation(value=None, source=Source("erc20-balance", AMZN.id.address), source_time=None,
                         fetch_time=FETCHED, block=BLOCK, status=FetchStatus.UNREACHABLE,
                         detail="[transport] refused")
    held = valuation.value_holding(AMZN, unread, valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH),
                                   universe_status=UniverseStatus.TRADEABLE, universe_reason=None)
    assert held.value is None and held.value_reason.startswith("[balance]")


def test_cash_is_marked_by_its_own_feed_and_usdg_is_not_assumed_to_be_a_dollar():
    usdg_mark = valuation.mark(USDG, reading(USDG, 100_020_000), FRESH)  # $1.0002
    held = valuation.value_holding(USDG, balance(USDG, 78_742), usdg_mark,
                                   universe_status=UniverseStatus.NOT_A_STOCK, universe_reason="cash leg")
    assert held.value.same_value(Fixed.parse("0.0787577484", USD))
    assert not held.value.same_value(Fixed.parse("0.078742", USD))


def test_gas_is_marked_by_its_own_feed():
    eth_mark = valuation.mark(ETH, reading(ETH, 450_000_000_000), FRESH)  # $4,500
    held = valuation.value_holding(ETH, balance(ETH, 460_162_486_507_929), eth_mark,
                                   universe_status=UniverseStatus.NOT_A_STOCK, universe_reason="gas")
    assert held.value.same_value(Fixed.parse("2.0707311892856805", USD))


# --- divergence --------------------------------------------------------------------------------

def test_divergence_is_the_mark_against_the_corroborator_signed():
    below = valuation.divergence_bps(Price(100, 0, AMZN.id, USD), Price(101, 0, AMZN.id, USD))
    assert below == Fixed(-9901, 2, "bps")      # -99.0099... rounded away from zero
    above = valuation.divergence_bps(Price(101, 0, AMZN.id, USD), Price(100, 0, AMZN.id, USD))
    assert above == Fixed(10000, 2, "bps")      # exactly 100


def test_the_recorded_amzn_case_is_vetoed_on_a_liquid_name():
    price, volume = gecko(AMZN, "265.87982073")
    check = valuation.cross_check(valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH),
                                  price, volume, RULE, independent=True)
    assert check.rule == valuation.RULE_DIVERGENCE and check.verdict.value is False
    assert check.tier == "above-line" and check.divergence == Fixed(-49947, 2, "bps")  # -499.4669
    assert "veto" in check.verdict.reason and check.independent


def test_a_thin_corroborator_excludes_the_asset_rather_than_vetoing_it():
    price, volume = gecko(AMZN, "265.87982073", volume="3502.1")  # EWY's volume, F0.4.5
    check = valuation.cross_check(valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH),
                                  price, volume, RULE, independent=True)
    assert check.rule == valuation.RULE_CORROBORATOR_LINE and check.tier == "below-line"
    assert check.universe_status is UniverseStatus.BELOW_CORROBORATOR_LINE
    assert check.divergence is not None  # recorded all the same


@pytest.mark.parametrize("corroborator, passes", [
    ("252.60", True),            # agreement
    ("255.126", True),           # mark below by 99.01 bps
    ("250.09901", True),         # mark above by 99.99999996 bps, rounded to 100.00: within
    ("250.0990099", False),      # mark above by 100.0000000004 bps: past the limit, however slightly
    ("250.09", False),           # mark above by 100.36 bps
])
def test_the_veto_limit_is_on_the_magnitude(corroborator, passes):
    price, volume = gecko(AMZN, corroborator)
    check = valuation.cross_check(valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH),
                                  price, volume, RULE, independent=True)
    assert check.verdict.passes is passes and check.tier == "above-line"


def test_a_volume_exactly_on_the_line_is_above_it():
    price, volume = gecko(AMZN, "252.60", volume="1000000")
    check = valuation.cross_check(valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH),
                                  price, volume, RULE, independent=True)
    assert check.tier == "above-line" and check.verdict.passes


@pytest.mark.parametrize("status", [FetchStatus.ABSENT, FetchStatus.UNREACHABLE, FetchStatus.REFUSED])
def test_absent_corroboration_is_undetermined_not_agreement(status):
    source = Source("geckoterminal", f"networks/robinhood/tokens/{AMZN.id.address}")
    missing = Observation(value=None, source=source, source_time=None, fetch_time=FETCHED, block=None,
                          status=status, detail="GeckoTerminal answered and did not list this address")
    check = valuation.cross_check(valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH),
                                  missing, missing, RULE, independent=True)
    assert check.rule == valuation.RULE_CORROBORATION and check.verdict.value is None
    assert check.divergence is None and not check.verdict.passes


def test_a_missing_volume_leaves_the_tier_undetermined():
    price, volume = gecko(AMZN, "252.60", volume=None)
    check = valuation.cross_check(valuation.mark(AMZN, reading(AMZN, 25260000000), FRESH),
                                  price, volume, RULE, independent=True)
    assert check.rule == valuation.RULE_VOLUME and check.verdict.value is None and check.tier is None


def test_with_no_mark_the_cross_check_names_the_marks_rule():
    price, volume = gecko(CRM, "250.00")
    check = valuation.cross_check(valuation.mark(CRM, None, FRESH), price, volume, RULE,
                                  independent=True)
    assert check.rule == valuation.RULE_MARKABILITY and check.divergence is None


# --- the rule comes from config -----------------------------------------------------------------

def test_the_tier_comes_from_thresholds_json():
    thresholds = json.loads((Path(universe.DEFAULT_DIR).parent / "thresholds.json").read_text())
    rule = valuation.DivergenceRule.from_thresholds(thresholds)
    assert rule.max_bps.same_value(Fixed(100, 0, "bps"))
    assert rule.min_volume_usd.same_value(Fixed(1_000_000, 0, USD))


def test_a_null_threshold_blocks_and_a_float_is_refused():
    with pytest.raises(ValueError, match="null"):
        valuation.DivergenceRule.from_thresholds({"divergence_max_bps": None,
                                                  "corroborator_min_volume_usd_24h": 1})
    with pytest.raises(TypeError, match="float"):
        valuation.DivergenceRule.from_thresholds({"divergence_max_bps": 99.5,
                                                  "corroborator_min_volume_usd_24h": 1})


def test_valuation_imports_nothing_from_adapters():
    tree = ast.parse(Path(valuation.__file__).read_text())
    modules = {node.module or "" for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    modules |= {a.name for node in ast.walk(tree) if isinstance(node, ast.Import) for a in node.names}
    assert not any("adapters" in m for m in modules)
