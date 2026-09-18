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
    Check, Fixed, Instant, Price, Source, content_id, from_canonical, to_canonical,
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
