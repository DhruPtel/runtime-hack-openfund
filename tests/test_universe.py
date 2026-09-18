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


# --- refresh: fetch-agnostic, and deliberate ---------------------------------------

A = "0x" + "aa" * 20
B = "0x" + "bb" * 20
C = "0x" + "cc" * 20


def seed_dir(tmp_path, raw: bytes):
    """A registry dir pinned to `raw`, as a real one would be."""
    plan = u.plan_refresh(u.REGISTRY, "example.invalid/assets", raw, Instant(1), current=None)
    (tmp_path / u.PINS_FILE).write_text(json.dumps({"version": 1, "inputs": {}}))
    u.store(plan, tmp_path)
    u.accept(plan, tmp_path)
    return plan


def test_a_refresh_diffs_additions_removals_and_status_changes(tmp_path):
    old = registry_bytes(registry_asset("AAA", A), registry_asset("BBB", B))
    new = registry_bytes(registry_asset("AAA", A, status="ASSET_STATUS_HALTED"),
                         registry_asset("CCC", C))
    plan = u.plan_refresh(u.REGISTRY, "example.invalid/assets", new, Instant(2), current=old)
    assert plan.added == (AssetId(CHAIN, C),)
    assert plan.removed == (AssetId(CHAIN, B),)
    assert (AssetId(CHAIN, A), "status", repr(u.ACTIVE), repr("ASSET_STATUS_HALTED")) in plan.changed


def test_the_same_bytes_refresh_to_no_change(tmp_path):
    raw = registry_bytes(registry_asset("AAA", A))
    plan = u.plan_refresh(u.REGISTRY, "example.invalid/assets", raw, Instant(2), current=raw)
    assert plan.unchanged


def test_store_writes_under_the_hash_and_accept_bumps_the_pin(tmp_path):
    raw = registry_bytes(registry_asset("AAA", A))
    plan = seed_dir(tmp_path, raw)
    assert (tmp_path / plan.filename).read_bytes() == raw
    pin, stored = u.read_pinned(u.REGISTRY, tmp_path)
    assert pin.sha256 == u.sha256_hex(raw) and stored == raw


def test_planning_and_storing_never_move_the_pin(tmp_path):
    first = registry_bytes(registry_asset("AAA", A))
    seed_dir(tmp_path, first)
    second = registry_bytes(registry_asset("AAA", A), registry_asset("BBB", B))
    plan = u.plan_refresh(u.REGISTRY, "example.invalid/assets", second, Instant(3), current=first)
    u.store(plan, tmp_path)
    pin, _ = u.read_pinned(u.REGISTRY, tmp_path)
    assert pin.sha256 == u.sha256_hex(first)  # only accept() moves it


def test_accept_refuses_to_drop_a_held_asset_unless_acknowledged(tmp_path):
    first = registry_bytes(registry_asset("AAA", A), registry_asset("BBB", B))
    seed_dir(tmp_path, first)
    second = registry_bytes(registry_asset("AAA", A))
    plan = u.plan_refresh(u.REGISTRY, "example.invalid/assets", second, Instant(3), current=first)
    u.store(plan, tmp_path)
    with pytest.raises(u.HeldAssetRemoved) as refusal:
        u.accept(plan, tmp_path, held=[AssetId(CHAIN, B)])
    assert refusal.value.rule == u.RULE_REFRESH
    u.accept(plan, tmp_path, held=[AssetId(CHAIN, A)])  # a held asset that stays: fine


def test_a_malformed_fetch_is_refused_before_anything_is_stored(tmp_path):
    with pytest.raises(Exception):
        u.plan_refresh(u.REGISTRY, "example.invalid/assets", b"<html>busy</html>", Instant(1), None)
    assert list(tmp_path.iterdir()) == []


def test_a_pin_pointing_at_tampered_bytes_is_refused_on_read(tmp_path):
    raw = registry_bytes(registry_asset("AAA", A))
    plan = seed_dir(tmp_path, raw)
    (tmp_path / plan.filename).write_bytes(raw.replace(b"AAA", b"AAB"))
    with pytest.raises(u.PinMismatch) as refusal:
        u.read_pinned(u.REGISTRY, tmp_path)
    assert refusal.value.rule == u.RULE_PIN


# --- the feed-map proposal ---------------------------------------------------------

def directory_bytes(*feeds: dict) -> bytes:
    return json.dumps(list(feeds)).encode()


def equity_feed(base, name, proxy, asset_class="Equity"):
    docs = {"marketHours": "us_equities_24/5", "baseAssetEntityId": f"crypto-{base or 'X'}"}
    if base is not None:
        docs["baseAsset"] = base
    if asset_class:
        docs["assetClass"] = asset_class
    return {"proxyAddress": proxy, "decimals": 8, "heartbeat": 86400, "threshold": 0.5,
            "name": name, "docs": docs}


def test_a_proposal_matches_a_registry_asset_to_its_feed():
    records = u.parse_registry(registry_bytes(registry_asset("AAA", A)))
    props, unresolved = u.propose_feed_map(
        records, directory_bytes(equity_feed("AAA", "Robinhood AAA / USD", "0x" + "11" * 20)))
    assert [p.asset for p in props] == [AssetId(CHAIN, A)] and unresolved == []


def test_a_counterfeit_can_never_be_proposed_a_feed():
    # F0.8.3: feed presence admitted both GME counterfeits, because a forger
    # picks its own ticker. The proposal iterates registry records only, so a
    # token that is not listed gets nothing, even with the exact ticker.
    records = u.parse_registry(registry_bytes(registry_asset("GME", A)))
    props, _ = u.propose_feed_map(
        records, directory_bytes(equity_feed("GME", "Robinhood GME / USD", "0x" + "11" * 20)))
    assert {p.asset for p in props} == {AssetId(CHAIN, A)}
    assert AssetId(CHAIN, B) not in {p.asset for p in props}  # the counterfeit's address


def test_an_unmatched_equity_feed_is_reported_not_dropped_or_guessed():
    records = u.parse_registry(registry_bytes(registry_asset("DELL", A), registry_asset("SGOV", B)))
    props, unresolved = u.propose_feed_map(records, directory_bytes(
        equity_feed("RHDELL", "Robinhood DELL-USD", "0x" + "11" * 20),
        # SGOV's entry has neither baseAsset nor assetClass: only market hours.
        equity_feed(None, "Robinhood SGOV-USD", "0x" + "22" * 20, asset_class=None)))
    assert props == []
    assert {x["feed_name"] for x in unresolved} == {"Robinhood DELL-USD", "Robinhood SGOV-USD"}
