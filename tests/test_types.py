"""Unit 1.1: the types module.

Two things are proven here. The first is the canonical encoding: sorted keys,
no floats, big integers as strings, and a byte-stable round trip. The second is
that each type can express the cases the probes actually measured, built from
recorded values wherever the record has them.
"""

from __future__ import annotations

import json

import pytest

from fund.core.types import (
    BPS, MULTIPLE, PERCENT, SECONDS, USD, Amount, AssetId, BlockRef, ChainAddress,
    Asset, AssetKind, Check, Deployment, FeedRef, FetchStatus, Fixed, Instant,
    Observation, Price, Quote, RegistryRecord, Series, Source, TradingCapability,
    content_id, from_canonical, to_canonical,
)

CHAIN = 4663
USDG = AssetId(CHAIN, "0x5fc5360d0400a0fd4f2af552add042d716f1d168")
AAPL = AssetId(CHAIN, "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9")
ETH = AssetId.native(CHAIN)
WALLET = ChainAddress(CHAIN, "0x93faecde3c88a713e1edddf417c02c326889a3da")


def roundtrip(obj):
    """Decode(encode(x)) == x, and re-encoding gives the identical bytes."""
    blob = to_canonical(obj)
    back = from_canonical(blob)
    assert back == obj
    assert to_canonical(back) == blob
    return blob


# --- canonical encoding --------------------------------------------------------

def test_canonical_bytes_are_sorted_compact_and_typed():
    blob = to_canonical(Fixed(-15, 0, BPS))
    assert blob == b'{"_type":"Fixed","decimals":0,"raw":"-15","unit":"bps"}'
    parsed = json.loads(blob)
    assert list(parsed) == sorted(parsed)


def test_no_float_is_ever_accepted_or_encoded():
    with pytest.raises(TypeError):
        Fixed(0.5, 1, PERCENT)
    with pytest.raises(TypeError):
        to_canonical([1.5])
    with pytest.raises(TypeError):
        from_canonical(b'{"_type":"Instant","epoch_ms":1.5}')


def test_bool_is_not_an_int():
    with pytest.raises(TypeError):
        Fixed(True, 0, USD)
    with pytest.raises(TypeError):
        Instant(False)


def test_big_integers_travel_as_strings():
    # One whole stock token in raw units exceeds 2**53, so it would lose
    # precision as a JSON number in a JavaScript reader.
    one_aapl = Amount(10**18, 18, AAPL)
    blob = roundtrip(one_aapl)
    assert b'"raw":"1000000000000000000"' in blob


def test_an_unsafe_int_in_a_numeric_field_is_refused_not_rounded():
    with pytest.raises(ValueError):
        to_canonical(BlockRef(CHAIN, 2**60))


def test_decode_rejects_unknown_types_extra_fields_and_sloppy_integers():
    with pytest.raises(ValueError):
        from_canonical(b'{"_type":"Nope"}')
    with pytest.raises(ValueError):
        from_canonical(b'{"_type":"Instant","epoch_ms":1,"extra":2}')
    with pytest.raises(ValueError):
        from_canonical(b'{"_type":"Fixed","decimals":0,"raw":"007","unit":"bps"}')


def test_content_id_is_the_sha256_of_the_canonical_bytes():
    import hashlib
    value = Amount(78742, 6, USDG)
    assert content_id(value) == hashlib.sha256(to_canonical(value)).hexdigest()


# --- identity ------------------------------------------------------------------

def test_asset_id_normalises_eip55_case():
    # The registry writes mixed case (F0.8.1); identity compares case-insensitively.
    mixed = AssetId(CHAIN, "0xd95B44124e475743a7589e68F3D74008A5536D44")
    assert mixed == AssetId(CHAIN, "0xd95b44124e475743a7589e68f3d74008a5536d44")
    roundtrip(mixed)


def test_a_ticker_is_never_an_asset_key():
    with pytest.raises(ValueError):
        AssetId(CHAIN, "AAPL")


def test_the_same_address_on_another_chain_is_another_asset():
    assert AssetId(1, AAPL.address) != AAPL


def test_native_eth_is_keyed_by_the_sentinel():
    assert ETH.is_native and not USDG.is_native
    roundtrip(ETH)


# --- quantities ----------------------------------------------------------------

def test_usdg_is_6_decimals_and_stock_tokens_are_18():
    # F0.3.1: two documented sources said 18 for USDG. Decimals are never
    # defaulted, so the conversion is explicit per asset.
    assert Amount.from_units("24.94", 6, USDG).raw == 24_940_000
    assert Amount.from_units("1", 18, AAPL).raw == 10**18
    with pytest.raises(ValueError):
        Amount.from_units("0.0000001", 6, USDG)


def test_decimals_have_no_default():
    with pytest.raises(TypeError):
        Amount(1, asset=USDG)  # type: ignore[call-arg]


def test_amounts_of_different_assets_do_not_compare():
    with pytest.raises(TypeError):
        Amount(1, 6, USDG) < Amount(1, 18, AAPL)
    with pytest.raises(TypeError):
        Amount(1, 6, USDG) < Amount(1, 18, USDG)


def test_fixed_parses_exactly_and_compares_across_decimals():
    multiplier = Fixed.parse("1.001148322800714293", MULTIPLE)  # registry, CRM
    assert (multiplier.raw, multiplier.decimals) == (1001148322800714293, 18)
    roundtrip(multiplier)
    assert Fixed.parse("0.5", PERCENT).same_value(Fixed(50, 2, PERCENT))
    assert Fixed(-155, 1, BPS) < Fixed(50, 0, BPS)


def test_unlike_units_refuse_to_compare():
    with pytest.raises(TypeError):
        Fixed(1, 0, BPS) < Fixed(1, 0, SECONDS)


def test_a_chainlink_answer_is_a_price_with_eight_decimals():
    # probes/out/feed.json: AAPL answer_raw 33538474720 at 8 decimals.
    mark = Price(33538474720, 8, AAPL, USD)
    roundtrip(mark)
    assert mark.same_value(Price(3353847472, 7, AAPL, USD))
    assert mark != Price(3353847472, 7, AAPL, USD)  # `==` is structural, by design
    with pytest.raises(TypeError):
        mark < Price(1, 8, USDG, USD)


# --- provenance and checks -----------------------------------------------------

def test_a_source_locator_can_never_hold_a_url():
    # The RPC URL is a declared credential; refusing any scheme is cheaper
    # than trusting redaction to catch it downstream.
    with pytest.raises(ValueError):
        Source("rpc-4663", "https://rpc.example/v2/secret")
    roundtrip(Source("chainlink-feed", "0x0e96b7708487f91baac09697593d3e8bf253f2d8"))


def test_check_is_three_valued_and_only_true_passes():
    assert Check(True).passes
    assert not Check(False).passes
    unknown = Check.undetermined("rpc unreachable: timeout after 20 s")
    assert unknown.value is None and not unknown.passes
    assert unknown != Check(False, "rpc unreachable: timeout after 20 s")
    with pytest.raises(ValueError):
        Check(None)
    with pytest.raises(TypeError):
        Check(1)  # type: ignore[arg-type]
    roundtrip(unknown)


def test_block_and_instant_roundtrip():
    pinned = BlockRef(CHAIN, 66_586_209, Instant.from_seconds(1_789_762_500),
                      "0x" + "ab" * 32)
    roundtrip(pinned)
    with pytest.raises(ValueError):
        BlockRef(CHAIN, 1, hash="0xABC")


# --- observations and series ---------------------------------------------------

FEED = Source("chainlink-feed", "0x0e96b7708487f91baac09697593d3e8bf253f2d8")
PINNED = BlockRef(CHAIN, 66_353_908, Instant.from_seconds(1_789_744_300))
T0 = 1_789_744_288  # AAPL feed updatedAt in probes/out/feed.json
DAY = 86_400


def feed_point(seconds: int, answer: int, round_id: int) -> Observation:
    return Observation(
        value=Price(answer, 8, AAPL, USD), source=FEED,
        source_time=Instant.from_seconds(seconds),
        fetch_time=Instant.from_seconds(T0 + 12), block=PINNED,
        status=FetchStatus.OK, source_ref=str(round_id))


def test_a_feed_reading_keeps_source_time_and_fetch_time_apart():
    reading = feed_point(T0, 33538474720, 18446744073709552261)
    assert reading.source_time != reading.fetch_time
    blob = roundtrip(reading)
    # The round id exceeds 2**53, so it is carried as text.
    assert b'"source_ref":"18446744073709552261"' in blob


def test_an_unreachable_source_is_not_false_and_not_zero():
    timed_out = Observation(
        value=None, source=FEED, source_time=None,
        fetch_time=Instant.from_seconds(T0), block=PINNED,
        status=FetchStatus.UNREACHABLE, detail="timeout after 20 s")
    assert not timed_out.ok and timed_out.value is None
    roundtrip(timed_out)
    with pytest.raises(ValueError):
        Observation(value=Price(0, 8, AAPL, USD), source=FEED, source_time=None,
                    fetch_time=Instant.from_seconds(T0), block=PINNED,
                    status=FetchStatus.UNREACHABLE, detail="timeout")
    with pytest.raises(ValueError):
        Observation(value=None, source=FEED, source_time=None,
                    fetch_time=Instant.from_seconds(T0), block=PINNED,
                    status=FetchStatus.UNREACHABLE)
    with pytest.raises(TypeError):
        Observation(value=None, source=FEED, source_time=None,
                    fetch_time=Instant.from_seconds(T0), block=PINNED,
                    status=FetchStatus.OK)


def test_an_absent_field_is_null_with_a_reason_never_zero():
    # F0.3.2: all 12 fields appeared, which is not a guarantee.
    missing = Observation(
        value=None, source=Source("bankr-quote", "/wallet/swap-quote"),
        source_time=None, fetch_time=Instant.from_seconds(T0), block=None,
        status=FetchStatus.ABSENT, detail="swapImpactBps not in response")
    roundtrip(missing)


def test_a_week_of_history_with_a_fresh_newest_point_is_one_series():
    points = tuple(feed_point(T0 - (7 - d) * DAY, 33_000_000_000 + d, 18446744073709552254 + d)
                   for d in range(8))
    history = Series(asset=AAPL, source=FEED, fetch_time=Instant.from_seconds(T0 + 12),
                     status=FetchStatus.OK, points=points)
    now = Instant.from_seconds(T0 + 12)
    assert now.epoch_ms - history.oldest.source_time.epoch_ms == (7 * DAY + 12) * 1000
    # Only the newest point is aged; a week-old oldest point is history, not staleness.
    assert history.age_of_newest_ms(now) == 12_000
    roundtrip(history)


def test_a_series_must_run_oldest_first_from_one_source_for_one_asset():
    a, b = feed_point(T0 - DAY, 1, 1), feed_point(T0, 2, 2)
    with pytest.raises(ValueError):
        Series(asset=AAPL, source=FEED, fetch_time=Instant.from_seconds(T0),
               status=FetchStatus.OK, points=(b, a))
    with pytest.raises(ValueError):
        Series(asset=USDG, source=FEED, fetch_time=Instant.from_seconds(T0),
               status=FetchStatus.OK, points=(a, b))
    with pytest.raises(ValueError):
        Series(asset=AAPL, source=Source("geckoterminal", "/ohlcv"),
               fetch_time=Instant.from_seconds(T0), status=FetchStatus.OK, points=(a, b))


def test_a_series_that_could_not_be_fetched_says_why_and_has_no_points():
    failed = Series(asset=AAPL, source=FEED, fetch_time=Instant.from_seconds(T0),
                    status=FetchStatus.UNREACHABLE, detail="rpc timeout")
    assert failed.newest is None and failed.age_of_newest_ms(Instant(0)) is None
    roundtrip(failed)
    with pytest.raises(ValueError):
        Series(asset=AAPL, source=FEED, fetch_time=Instant.from_seconds(T0),
               status=FetchStatus.OK)


# --- assets: identity and markability ------------------------------------------

CRM = AssetId(CHAIN, "0xd95B44124e475743a7589e68F3D74008A5536D44")
# The genuine GME and the "GameStop" counterfeit, as probe 0.8 recorded them.
GME = AssetId(CHAIN, "0x1b0e319c6a659f002271b69db8a7df2f911c153e")
FAKE_GME = AssetId(CHAIN, "0x7e86381a763f0ecca2bdf27c54eac403ddd48123")


def registry_record(asset: AssetId, symbol: str) -> RegistryRecord:
    # CRM's record from the registry snapshot 0.8 took (probes/out/registry_snapshot.json).
    return RegistryRecord(
        registry_id="0x00000000000000000000000000000000022015c295294037bfe416d3e45327b9",
        symbol=symbol, name="Salesforce • Robinhood Token", isin="US79466L3024",
        status="ASSET_STATUS_ACTIVE", decimals=18,
        deployments=(Deployment(contract=ChainAddress(asset.chain_id, asset.address),
                                network_name="Robinhood Chain"),),
        current_multiplier=Fixed.parse("1.001148322800714293", MULTIPLE),
        pending_multiplier=None,  # the registry writes "" for none
        trading_capabilities=(
            TradingCapability(session="market", lot="whole", status="TRADING_STATUS_TRADABLE"),
            TradingCapability(session="market", lot="fractional", status="TRADING_STATUS_UNTRADABLE"),
        ))


def equity_feed(proxy: str, name: str) -> FeedRef:
    return FeedRef(proxy=ChainAddress(CHAIN, proxy), decimals=8,
                   heartbeat=Fixed(86_400, 0, SECONDS),
                   deviation_threshold=Fixed.parse("0.5", PERCENT),
                   market_hours="us_equities_24/5", name=name)


def test_crm_is_genuine_listed_and_correctly_unmarkable():
    crm = Asset(id=CRM, kind=AssetKind.STOCK, symbol="CRM", decimals=18,
                identity=Check(True, "in registry snapshot"),
                markability=Check(False, "no Chainlink feed (F0.4.1)"),
                beacon=Check(True, "resolves to the issuer beacon"),
                registry=registry_record(CRM, "CRM"), feed=None)
    assert crm.identity.passes and not crm.markability.passes
    roundtrip(crm)


def test_a_feed_carries_no_identity_weight():
    # F0.8.3: feed presence admitted both GME counterfeits. The type can hold a
    # counterfeit that a ticker join has attached the real GME feed to. Its
    # identity is still false, so 1.2 can refuse it by name.
    fake = Asset(id=FAKE_GME, kind=AssetKind.STOCK, symbol="GME", decimals=18,
                 identity=Check(False, "not in registry"),
                 markability=Check(True, "a feed exists for the ticker"),
                 beacon=Check(False, "no beacon slot set"),
                 feed=equity_feed("0x0e96b7708487f91baac09697593d3e8bf253f2d8",
                                  "Robinhood GME / USD"))
    assert fake.markability.passes and not fake.identity.passes
    roundtrip(fake)


def test_a_stock_cannot_claim_identity_without_its_registry_record():
    with pytest.raises(ValueError):
        Asset(id=GME, kind=AssetKind.STOCK, symbol="GME", decimals=18,
              identity=Check(True), markability=Check(False, "no feed"),
              beacon=Check(True))
    with pytest.raises(ValueError):  # a record for another address
        Asset(id=GME, kind=AssetKind.STOCK, symbol="GME", decimals=18,
              identity=Check(True), markability=Check(False, "no feed"),
              beacon=Check(True), registry=registry_record(CRM, "CRM"))


def test_markable_means_a_feed_is_pinned_and_a_stock_needs_its_beacon_check():
    with pytest.raises(ValueError):
        Asset(id=CRM, kind=AssetKind.STOCK, symbol="CRM", decimals=18,
              identity=Check(True), markability=Check(True), beacon=Check(True),
              registry=registry_record(CRM, "CRM"))
    with pytest.raises(TypeError):
        Asset(id=CRM, kind=AssetKind.STOCK, symbol="CRM", decimals=18,
              identity=Check(True), markability=Check(False, "no feed"), beacon=None,
              registry=registry_record(CRM, "CRM"))


def test_registry_decimals_must_agree_with_the_asset():
    with pytest.raises(ValueError):
        Asset(id=CRM, kind=AssetKind.STOCK, symbol="CRM", decimals=6,
              identity=Check(True), markability=Check(False, "no feed"),
              beacon=Check(True), registry=registry_record(CRM, "CRM"))


def test_cash_and_gas_are_assets_outside_the_registry():
    usdg = Asset(id=USDG, kind=AssetKind.CASH, symbol="USDG", decimals=6,
                 identity=Check(True, "pinned cash leg, on-chain decimals 6 (F0.3.1)"),
                 markability=Check(True, "Chainlink USDG / USD feed"), beacon=None,
                 feed=FeedRef(proxy=ChainAddress(CHAIN, "0x" + "11" * 20), decimals=8,
                              heartbeat=Fixed(86_400, 0, SECONDS),
                              deviation_threshold=Fixed.parse("0.5", PERCENT),
                              market_hours=None, name="USDG / USD"))
    eth = Asset(id=ETH, kind=AssetKind.GAS, symbol="ETH", decimals=18,
                identity=Check(True, "native"), markability=Check(False, "feed not pinned yet"),
                beacon=None)
    roundtrip(usdg)
    roundtrip(eth)
    with pytest.raises(ValueError):
        Asset(id=USDG, kind=AssetKind.GAS, symbol="USDG", decimals=6,
              identity=Check(True), markability=Check(False, "x"), beacon=None)
    with pytest.raises(ValueError):
        Asset(id=USDG, kind=AssetKind.CASH, symbol="USDG", decimals=6,
              identity=Check(True), markability=Check(False, "x"), beacon=Check(True))


def test_the_directory_float_threshold_must_be_converted_not_passed():
    with pytest.raises(TypeError):
        FeedRef(proxy=ChainAddress(CHAIN, "0x" + "22" * 20), decimals=8,
                heartbeat=Fixed(86_400, 0, SECONDS), deviation_threshold=0.5,
                market_hours=None, name="x")


# --- quotes --------------------------------------------------------------------

TSLA = AssetId(CHAIN, "0x322f0929c4625ed5bad873c95208d54e1c003b2d")
QUOTES = Source("bankr-quote", "/wallet/swap-quote")


def tsla_quote(impact_bps: int | None) -> Quote:
    """Probe 0.3's TSLA quote at $25, as recorded in probes/out/quote.json.

    `from.amount` came back human ("25") and `to.amount` raw; `minBuyAmount` is
    human; the two USD prices are JSON floats. Each is converted exactly here,
    the way 1.5 will have to.
    """
    bps = None if impact_bps is None else Fixed(impact_bps, 0, BPS)
    return Quote(
        sell=Amount.from_units("25", 6, USDG),
        buy=Amount(67948238487403141, 18, TSLA),
        min_buy=Amount.from_units("0.064550826563032984", 18, TSLA),
        price_impact=bps, swap_impact=bps,
        max_price_impact=Fixed(1500, 0, BPS), fee=Fixed(0, 0, BPS), fee_waived=False,
        slippage=Fixed(500, 0, BPS),
        sell_price=Price.parse(repr(1.0022236982588135), USDG, USD),
        buy_price=Price.parse(repr(369.2925339180603), TSLA, USD),
        quote_id="c9f64995-fa7c-469b-a880-4796cfa739d9")


def test_a_negative_impact_is_price_improvement_and_passes_a_positive_limit():
    quote = tsla_quote(-15)
    limit = Fixed(50, 0, BPS)  # impact_max_bps, compared signed
    assert quote.swap_impact < Fixed(0, 0, BPS)
    # The gate itself lives in core/gates.py; here the comparison it will make
    # must come out right. A magnitude comparison would have refused this fill.
    assert not (quote.swap_impact > limit)
    assert Fixed(abs(quote.swap_impact.raw), 0, BPS) < limit  # and so would abs, here
    assert not (Fixed(-60, 0, BPS) > limit)  # but abs would refuse -60; signed does not
    roundtrip(quote)


def test_an_absent_impact_is_none_never_zero():
    quote = tsla_quote(None)
    assert quote.swap_impact is None and quote.price_impact is None
    roundtrip(quote)


def test_a_quote_is_an_observation_with_no_source_time():
    seen = Observation(value=tsla_quote(-15), source=QUOTES, source_time=None,
                       fetch_time=Instant.from_seconds(T0), block=None,
                       status=FetchStatus.OK, source_ref="c9f64995-fa7c-469b-a880-4796cfa739d9")
    roundtrip(seen)


def test_quote_fields_carry_their_units():
    with pytest.raises(ValueError):
        Quote(sell=Amount(1, 6, USDG), buy=Amount(1, 18, TSLA), min_buy=Amount(1, 6, USDG),
              price_impact=None, swap_impact=None, max_price_impact=None, fee=None,
              fee_waived=None, slippage=None, sell_price=None, buy_price=None, quote_id=None)
    with pytest.raises(ValueError):
        Quote(sell=Amount(1, 6, USDG), buy=Amount(1, 18, TSLA), min_buy=Amount(1, 18, TSLA),
              price_impact=Fixed(-15, 0, PERCENT), swap_impact=None, max_price_impact=None,
              fee=None, fee_waived=None, slippage=None, sell_price=None, buy_price=None,
              quote_id=None)
