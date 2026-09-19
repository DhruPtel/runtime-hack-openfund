"""Unit 1.1, the types: a canonical encoding with no floats and big integers as text,
and types that hold what the probes measured (CRM's shape, a series judged on its
newest point, a swap run through a bundler) and refuse what they did not."""

from __future__ import annotations

import dataclasses
import json

import pytest

from fund.core.types import (
    BPS, MULTIPLE, PERCENT, SECONDS, USD, Amount, AssetId, BlockRef, ChainAddress,
    Asset, AssetKind, Check, Deployment, Execution, ExecutionMode, FeedRef, FetchStatus,
    Fixed, Holding, Instant, Order, OrderState, TokenTransfer, TransactionRef,
    UserOperationRef,
    Observation, PinnedInput, Price, Quote, RegistryRecord, Series,
    Source, TradingCapability,
    UniverseStatus, content_id, from_canonical, to_canonical,
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


# --- quantities ----------------------------------------------------------------

def test_a_human_amount_converts_at_the_decimals_given_and_never_rounds():
    # F0.3.1: two documented sources said 18 for USDG, which is 6, so decimals are
    # never defaulted. An amount finer than its decimals allow is refused, not
    # rounded. That the USDG pin says 6 is tested in test_universe.py.
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
    def absent(value, detail):
        return Observation(
            value=value, source=Source("bankr-quote", "/wallet/swap-quote"),
            source_time=None, fetch_time=Instant.from_seconds(T0), block=None,
            status=FetchStatus.ABSENT, detail=detail)

    roundtrip(absent(None, "swapImpactBps not in response"))
    with pytest.raises(ValueError):
        absent(Fixed(0, 0, BPS), "swapImpactBps not in response")  # zero is a value
    with pytest.raises(ValueError):
        absent(None, None)  # and absence says why


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


# --- holdings ------------------------------------------------------------------

RPC = Source("rpc-4663", "public")


def balance_of(asset: AssetId, raw: int, decimals: int) -> Observation:
    return Observation(value=Amount(raw, decimals, asset), source=RPC, source_time=None,
                       fetch_time=Instant.from_seconds(T0), block=PINNED,
                       status=FetchStatus.OK)


def test_an_unvalued_holding_must_say_why_and_a_value_needs_a_read_mark():
    with pytest.raises(ValueError):
        Holding(asset=CRM, balance=balance_of(CRM, 1, 18),
                universe_status=UniverseStatus.UNMARKABLE, universe_reason="no feed",
                mark=None, value=None, value_reason=None)
    with pytest.raises(ValueError):  # a value with no mark is a number from nowhere
        Holding(asset=CRM, balance=balance_of(CRM, 1, 18),
                universe_status=UniverseStatus.UNMARKABLE, universe_reason="no feed",
                mark=None, value=Fixed(0, 0, USD), value_reason=None)


def test_an_unreadable_balance_is_kept_not_dropped():
    lost = Observation(value=None, source=RPC, source_time=None,
                       fetch_time=Instant.from_seconds(T0), block=PINNED,
                       status=FetchStatus.UNREACHABLE, detail="rpc timeout")
    held = Holding(asset=AAPL, balance=lost, universe_status=UniverseStatus.TRADEABLE,
                   universe_reason=None, mark=None, value=None,
                   value_reason="balance unreadable this snapshot")
    roundtrip(held)


# --- pinned inputs ------------------------------------------------------------

# 0.8's recorded registry hash, used as a stand-in value: its bytes were not kept,
# so 1.2 will pin a fresh one (LESSONS 2026-09-18).
REGISTRY_INPUT = PinnedInput(name="rhj-registry", locator="api.robinhood.com/rhj/assets",
                             sha256="442718b5843e448e46a3deceab9f2d92f8719c0a4b1a77942d5d6da8098c8b4b",
                             byte_count=154_149, fetch_time=Instant.from_seconds(T0))


def test_a_pinned_input_roundtrips():
    roundtrip(REGISTRY_INPUT)


# --- orders: the swap probe 0.10 made, as the chain recorded it ------------------

SWAP_BLOCK = BlockRef(CHAIN, 66_586_209, None,
                      "0xdf97c54f3353ee139a9f355cb6859f3456a16e3300b1be3577b4fc9e5b126a8c")
BUNDLER = ChainAddress(CHAIN, "0x8e3435ad7c1183bc0e34f9ec34ea3423182e1c67")
ENTRY_POINT = ChainAddress(CHAIN, "0x0000000071727de22e5e9d8baf0edac6f37da032")
ROUTER_LEG = ChainAddress(CHAIN, "0xb92fe925dc43a0ecde6c8b1a2709c170ec4fff4f")


def swap_execution(success: bool = True, sender: ChainAddress = WALLET) -> Execution:
    return Execution(
        transaction=TransactionRef(
            tx_hash="0xb9e412815dc9bce933100bf23ece1e2b24fedcbcb91a4fa90c49ad36e64ae2a5",
            block=SWAP_BLOCK, tx_type=4, submitted_by=BUNDLER, outer_status=1),
        user_operation=UserOperationRef(
            entry_point=ENTRY_POINT,
            user_op_hash="0x3de3e3cd1a2ac72335d39e190526ffe39f912df1a94fe679da994d4cdd42a710",
            sender=sender, paymaster=None,
            nonce_key="0xb5a5e1cf69828cc450420d8c325eae3cd5ea8504d799", nonce_seq=0,
            success=Check(success), actual_gas_cost=Amount(0, 18, ETH)),
        transfers=(TokenTransfer(token=USDG, sender=ROUTER_LEG, recipient=WALLET,
                                 amount=Amount(78_742, 6, USDG), log_index=21),))


def swap_order(state=OrderState.CONFIRMED, execution=None, reason=None) -> Order:
    return Order(order_id="0.10-swap", idempotency_key="da8dd080-1e78-4357-bca6-2502d8ad9724",
                 mode=ExecutionMode.LIVE, wallet=WALLET,
                 sell=Amount.from_units("0.00003", 18, ETH), buy_asset=USDG,
                 min_buy=Amount.from_units("0.074804", 6, USDG), state=state,
                 state_reason=reason, execution=execution)


def test_an_order_that_executed_via_a_bundler_is_confirmed_by_the_operation():
    order = swap_order(execution=swap_execution())
    # The outer transaction was not sent by our wallet, and that is fine.
    assert order.execution.transaction.submitted_by != WALLET
    assert order.execution.user_operation.sender == WALLET
    roundtrip(order)


def test_there_is_no_field_for_the_sender_shortcut_or_the_wallet_nonce():
    from dataclasses import fields as fields_of
    names = {f.name for cls in (Order, Execution, TransactionRef) for f in fields_of(cls)}
    assert not {"from", "from_address", "nonce", "sender_is_wallet"} & names


def test_a_reverted_operation_inside_a_mined_bundle_is_not_confirmed():
    # Outer status 1 says the bundle mined; the operation's own success decides.
    with pytest.raises(ValueError):
        swap_order(execution=swap_execution(success=False))
    failed = swap_order(state=OrderState.FAILED, execution=swap_execution(success=False),
                        reason="UserOperationEvent.success false")
    roundtrip(failed)


def test_an_operation_for_another_wallet_does_not_confirm_ours():
    stranger = ChainAddress(CHAIN, "0x" + "44" * 20)
    with pytest.raises(ValueError):
        swap_order(execution=swap_execution(sender=stranger))


def test_confirmed_needs_the_bought_asset_to_reach_the_wallet():
    no_transfer = Execution(transaction=swap_execution().transaction,
                            user_operation=swap_execution().user_operation, transfers=())
    with pytest.raises(ValueError):
        swap_order(execution=no_transfer)


def test_paper_and_pending_orders_carry_no_chain_evidence():
    paper = Order(order_id="paper-1", idempotency_key="k-1", mode=ExecutionMode.PAPER,
                  wallet=WALLET, sell=Amount.from_units("25", 6, USDG), buy_asset=TSLA,
                  min_buy=Amount.from_units("0.064550826563032984", 18, TSLA),
                  state=OrderState.CONFIRMED)
    roundtrip(paper)
    with pytest.raises(ValueError):
        swap_order(state=OrderState.SUBMITTED, execution=swap_execution())
    with pytest.raises(ValueError):
        swap_order(state=OrderState.UNKNOWN)  # unknown must say why
    roundtrip(swap_order(state=OrderState.UNKNOWN, reason="409: original still in flight"))


# --- a short series is visible as short (unit 1.3) --------------------------------

def week_series(window_days: int, coverage):
    points = tuple(feed_point(T0 - (7 - d) * DAY, 33_000_000_000 + d, 18446744073709552254 + d)
                   for d in range(8))
    return Series(asset=AAPL, source=FEED, fetch_time=Instant.from_seconds(T0 + 12),
                  status=FetchStatus.OK, points=points,
                  window_start=Instant.from_seconds(T0 - window_days * DAY), coverage=coverage)


def test_a_series_cannot_claim_a_window_its_points_do_not_reach():
    # Asked for 30 days, holding 7: it must not read as success.
    with pytest.raises(ValueError):
        week_series(30, Check(True))
    short = week_series(30, Check(False, "round cap reached 23 days short"))
    assert not short.coverage.passes
    roundtrip(short)


def test_a_series_asked_for_a_window_must_state_coverage():
    with pytest.raises(ValueError):
        week_series(7, None)


def test_a_series_from_two_blocks_is_refused():
    other_block = BlockRef(CHAIN, PINNED.number + 1, Instant.from_seconds(1_789_744_301))
    a = feed_point(T0 - DAY, 1, 1)
    b = Observation(value=Price(2, 8, AAPL, USD), source=FEED, source_time=Instant.from_seconds(T0),
                    fetch_time=Instant.from_seconds(T0 + 12), block=other_block,
                    status=FetchStatus.OK)
    with pytest.raises(ValueError, match="block-pin"):
        Series(asset=AAPL, source=FEED, fetch_time=Instant.from_seconds(T0),
               status=FetchStatus.OK, points=(a, b))


# --- a sampled series: daily closes (DECISION 2026-09-18) --------------------------------

def test_a_sampled_series_carries_one_sample_per_point_at_or_after_each_point():
    points = tuple(feed_point(T0 - (3 - d) * DAY, 33_000_000_000 + d, 18446744073709552254 + d)
                   for d in range(4))
    cuts = tuple(Instant.from_seconds(T0 - (3 - d) * DAY + 3600) for d in range(4))
    closes = Series(asset=AAPL, source=FEED, fetch_time=Instant.from_seconds(T0 + 12),
                    status=FetchStatus.OK, points=points, samples=cuts)
    roundtrip(closes)
    with pytest.raises(ValueError, match="one sample per point"):
        dataclasses.replace(closes, samples=cuts[:3])
    with pytest.raises(ValueError, match="at or before"):
        dataclasses.replace(closes, samples=tuple(Instant(c.epoch_ms - 7_200_000) for c in cuts))
    with pytest.raises(ValueError, match="oldest first"):
        dataclasses.replace(closes, samples=(cuts[1], cuts[0], cuts[2], cuts[3]))
