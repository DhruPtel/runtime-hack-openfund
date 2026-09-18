"""Unit 1.2: the universe.

Every rule is tested against something it should admit and something it should
reject. Every refusal is checked for *which rule* refused: a rejection firing
for the wrong reason looks exactly like a passing test.
"""

from __future__ import annotations

import json

import pytest

from fund.core import universe as u
from fund.core.types import AssetId, Instant, PinnedInput

CHAIN = 4663


def registry_bytes(*assets: dict) -> bytes:
    return json.dumps({"assets": list(assets)}, separators=(",", ":")).encode()


def registry_asset(symbol: str, address: str, status: str = u.ACTIVE, pending: str = "") -> dict:
    return {"id": "0x" + "0" * 63 + "1", "tokenSymbol": symbol, "tokenName": f"{symbol} • Robinhood Token",
            "isin": "US0000000001", "status": status, "tokenDecimals": 18,
            "deployments": [{"chainId": CHAIN, "contractAddress": address,
                             "networkName": "Robinhood Chain"}],
            "currentMultiplier": "1.000000000000000000", "pendingMultiplier": pending,
            "tradingCapabilities": {"market": {"whole": "TRADING_STATUS_TRADABLE",
                                               "fractional": "TRADING_STATUS_UNTRADABLE"}}}


def pin_for(name: str, raw: bytes) -> PinnedInput:
    return PinnedInput(name=name, locator="example.invalid/path", sha256=u.sha256_hex(raw),
                       byte_count=len(raw), fetch_time=Instant(0))


# --- the pin rule ----------------------------------------------------------------

def test_the_pin_admits_the_exact_bytes():
    raw = registry_bytes(registry_asset("AAA", "0x" + "aa" * 20))
    u.verify(raw, pin_for(u.REGISTRY, raw))


def test_the_pin_refuses_one_changed_byte_at_the_pin_rule():
    raw = registry_bytes(registry_asset("AAA", "0x" + "aa" * 20))
    tampered = raw.replace(b"AAA", b"AAB")  # still valid JSON: only the hash can catch it
    with pytest.raises(u.PinMismatch) as refusal:
        u.verify(tampered, pin_for(u.REGISTRY, raw))
    assert refusal.value.rule == u.RULE_PIN


def test_stored_files_are_named_by_their_hash():
    sha = "ab" * 32
    assert u.filename_for(u.REGISTRY, sha) == f"rhj_assets.{sha}.json"
    with pytest.raises(ValueError):
        u.filename_for("something_else", sha)


# --- parsing ---------------------------------------------------------------------

def test_registry_parse_is_exact_and_keeps_status_as_given():
    raw = registry_bytes(registry_asset("AAA", "0x" + "Aa" * 20, status="ASSET_STATUS_HALTED"))
    records = u.parse_registry(raw)
    record = records[AssetId(CHAIN, "0x" + "aa" * 20)]  # EIP-55 case normalised
    assert record.status == "ASSET_STATUS_HALTED"
    assert record.pending_multiplier is None  # "" means none, never zero
    assert (record.current_multiplier.raw, record.current_multiplier.decimals) == (10**18, 18)


def test_registry_parse_refuses_one_address_claimed_twice():
    raw = registry_bytes(registry_asset("AAA", "0x" + "aa" * 20),
                         registry_asset("BBB", "0x" + "aa" * 20))
    with pytest.raises(ValueError):
        u.parse_registry(raw)


def test_directory_parse_converts_the_float_threshold_exactly():
    raw = json.dumps([{"proxyAddress": "0x" + "cc" * 20, "decimals": 8, "heartbeat": 86400,
                       "threshold": 0.5, "name": "Robinhood AAA / USD",
                       "docs": {"marketHours": "us_equities_24/5", "baseAsset": "AAA"}}]).encode()
    feed = next(iter(u.parse_directory(raw, CHAIN).values()))
    assert (feed.deviation_threshold.raw, feed.deviation_threshold.decimals) == (5, 1)
    assert feed.heartbeat.raw == 86_400 and feed.market_hours == "us_equities_24/5"
