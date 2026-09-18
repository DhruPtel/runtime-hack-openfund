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


# --- the proof, on the pinned universe in config/registry/ -------------------------

import shutil

from fund.core.types import (
    USD, Amount, ChainAddress, Check, FetchStatus, Fixed, Holding, Observation, Price,
    Source, UniverseStatus,
)

# As probe 0.8 recorded them (probes/out/identity.json).
GME = AssetId(CHAIN, "0x1b0e319c6a659f002271b69db8a7df2f911c153e")
FAKE_GAMESTOP = AssetId(CHAIN, "0x7e86381a763f0ecca2bdf27c54eac403ddd48123")
FAKE_GREATEST_MEME_EVER = AssetId(CHAIN, "0xef67e3064bef1a27e81925ec7132f23e533bd5f6")
CRM = AssetId(CHAIN, "0xd95b44124e475743a7589e68f3d74008a5536d44")
USDG = AssetId(CHAIN, "0x5fc5360d0400a0fd4f2af552add042d716f1d168")
ISSUER_BEACON = ChainAddress(CHAIN, "0xe10b6f6b275de231345c20d14ab812db62151b00")
RPC = Source("rpc-4663", "public")


@pytest.fixture(scope="module")
def pinned():
    return u.load()


def slot_read(value=None, status=FetchStatus.OK, detail=None) -> Observation:
    return Observation(value=value, source=RPC, source_time=None, fetch_time=Instant(1),
                       block=None, status=status, detail=detail)


def test_the_pinned_universe_loads_and_is_the_version_0_8_recorded(pinned):
    assert pinned.registry.sha256 == "442718b5843e448e46a3deceab9f2d92f8719c0a4b1a77942d5d6da8098c8b4b"
    assert len(pinned.records) == 194
    assert len(pinned.feeds) == 37  # 35 equity feeds + USDG / USD + ETH / USD


# identity ------------------------------------------------------------------------

def test_the_real_gme_is_admitted(pinned):
    gme = pinned.stock(GME, beacon=Check(True))
    assert gme.identity.passes and gme.markability.passes
    admission = pinned.admission(gme)
    assert admission.decision.passes and admission.rule is None


@pytest.mark.parametrize("fake", [FAKE_GAMESTOP, FAKE_GREATEST_MEME_EVER],
                         ids=["GameStop", "Greatest Meme Ever"])
def test_each_gme_counterfeit_is_refused_at_identity(pinned, fake):
    with pytest.raises(u.Refused) as refusal:
        pinned.stock(fake, beacon=Check(True))
    assert refusal.value.rule == u.RULE_IDENTITY
    assert refusal.value.asset == fake
    assert "not in rhj_assets 442718b5843e" in str(refusal.value)


# markability, apart from identity -----------------------------------------------

def test_crm_is_genuine_and_correctly_unmarkable(pinned):
    crm = pinned.stock(CRM, beacon=Check(True))
    assert crm.identity.passes and pinned.standing(CRM).passes
    assert not crm.markability.passes and crm.feed is None
    admission = pinned.admission(crm)
    assert admission.rule == u.RULE_MARKABILITY and admission.decision.value is False


def test_markability_admits_every_mapped_feed_and_only_by_address(pinned):
    assert pinned.markability(GME).passes
    # A counterfeit whose ticker has a feed is still unmarkable: the map is keyed
    # by address, and it can only hold registry-listed assets.
    assert not pinned.markability(FAKE_GAMESTOP).passes


def test_cash_and_gas_are_admitted_on_their_own_pins(pinned):
    for asset in (pinned.cash(), pinned.gas()):
        assert pinned.admission(asset).decision.passes, asset.symbol
    assert pinned.cash().decimals == 6 and pinned.identity(USDG).value is False  # not a stock


# the beacon ------------------------------------------------------------------------

def test_a_matching_beacon_passes(pinned):
    checks = pinned.cross_check_beacons({GME: slot_read(ISSUER_BEACON)})
    assert checks[GME].passes


def test_a_constructed_beacon_disagreement_stops_the_cycle(pinned):
    elsewhere = ChainAddress(CHAIN, "0x" + "de" * 20)
    with pytest.raises(u.BeaconDisagreement) as refusal:
        pinned.cross_check_beacons({GME: slot_read(ISSUER_BEACON), CRM: slot_read(elsewhere)})
    assert refusal.value.rule == u.RULE_BEACON
    assert refusal.value.disagreements == ((CRM, elsewhere),)


def test_an_unset_slot_on_a_listed_asset_is_a_disagreement(pinned):
    zero = u.beacon_from_slot(CHAIN, "0x" + "0" * 64)
    with pytest.raises(u.BeaconDisagreement):
        pinned.cross_check_beacons({GME: slot_read(zero)})


def test_an_unread_slot_is_undetermined_not_a_disagreement(pinned):
    checks = pinned.cross_check_beacons(
        {GME: slot_read(status=FetchStatus.UNREACHABLE, detail="rpc timeout")})
    assert checks[GME].value is None
    admission = pinned.admission(pinned.stock(GME, beacon=checks[GME]))
    assert admission.rule == u.RULE_BEACON and admission.decision.value is None  # blocks


def test_a_counterfeit_is_never_beacon_compared_it_is_refused_at_identity(pinned):
    with pytest.raises(u.Refused) as refusal:
        pinned.cross_check_beacons({FAKE_GAMESTOP: slot_read(ISSUER_BEACON)})
    assert refusal.value.rule == u.RULE_IDENTITY


def test_the_slot_word_decodes_to_the_issuer_beacon():
    word = "0x000000000000000000000000e10b6f6b275de231345c20d14ab812db62151b00"
    assert u.beacon_from_slot(CHAIN, word) == ISSUER_BEACON


# the pin, on the real bytes ----------------------------------------------------------

@pytest.fixture
def registry_copy(tmp_path):
    target = tmp_path / "registry"
    shutil.copytree(u.DEFAULT_DIR, target)
    return target


def test_a_pinned_file_whose_bytes_no_longer_hash_to_the_pin_is_refused(registry_copy):
    pin, raw = u.read_pinned(u.REGISTRY, registry_copy)
    assert b"Salesforce" in raw
    (registry_copy / u.filename_for(u.REGISTRY, pin.sha256)).write_bytes(
        raw.replace(b"Salesforce", b"Salesforcf", 1))  # still valid JSON
    with pytest.raises(u.PinMismatch) as refusal:
        u.load(registry_copy)
    assert refusal.value.rule == u.RULE_PIN


def test_a_feed_map_reviewed_against_other_versions_is_refused(registry_copy):
    doc = json.loads((registry_copy / u.FEED_MAP_FILE).read_text())
    doc["reviewed_against"][u.REGISTRY] = "0" * 64
    (registry_copy / u.FEED_MAP_FILE).write_text(json.dumps(doc))
    with pytest.raises(u.FeedMapStale) as refusal:
        u.load(registry_copy)
    assert refusal.value.rule == u.RULE_FEED_MAP


def test_the_feed_map_cannot_give_a_counterfeit_a_feed(registry_copy):
    doc = json.loads((registry_copy / u.FEED_MAP_FILE).read_text())
    gme_entry = next(e for e in doc["entries"] if e["asset"] == GME.address)
    doc["entries"].remove(gme_entry)
    doc["entries"].append({**gme_entry, "asset": FAKE_GAMESTOP.address})
    (registry_copy / u.FEED_MAP_FILE).write_text(json.dumps(doc))
    with pytest.raises(u.UniverseError) as refusal:
        u.load(registry_copy)
    assert refusal.value.rule == u.RULE_FEED_MAP
    # Three map failures share this rule; this one must be the identity guard,
    # not staleness or a double mapping.
    assert not isinstance(refusal.value, u.FeedMapStale)
    assert "names neither a registry asset" in str(refusal.value)
    assert FAKE_GAMESTOP.address in str(refusal.value)


# a status that is not ACTIVE: refused for buying, never dropped -----------------------

def repin_with(registry_dir, raw: bytes):
    """Pin new registry bytes through the real refresh path, then re-review the map."""
    _, current = u.read_pinned(u.REGISTRY, registry_dir)
    plan = u.plan_refresh(u.REGISTRY, "api.robinhood.com/rhj/assets", raw, Instant(2), current)
    u.store(plan, registry_dir)
    u.accept(plan, registry_dir)
    doc = json.loads((registry_dir / u.FEED_MAP_FILE).read_text())
    doc["reviewed_against"][u.REGISTRY] = plan.pin.sha256
    (registry_dir / u.FEED_MAP_FILE).write_text(json.dumps(doc))
    return plan


def test_a_delisted_status_refuses_buying_at_standing_and_keeps_the_holding(registry_copy):
    _, raw = u.read_pinned(u.REGISTRY, registry_copy)
    payload = json.loads(raw)
    for item in payload["assets"]:
        if item["tokenSymbol"] == "GME":
            item["status"] = "ASSET_STATUS_DELISTED"  # constructed: never observed (F0.8.1)
    plan = repin_with(registry_copy, json.dumps(payload).encode())
    assert any(k == GME and field == "status" for k, field, *_ in plan.changed)

    universe = u.load(registry_copy)
    gme = universe.stock(GME, beacon=Check(True))
    assert gme.identity.passes and gme.markability.passes  # still the genuine asset
    admission = universe.admission(gme)
    assert admission.rule == u.RULE_STANDING and admission.decision.value is False

    # The holding does not vanish: it keeps its full description and its mark.
    held = universe.held_asset(GME, decimals=18)
    assert held.registry is not None and held.feed is not None
    mark = Observation(value=Price(2_500_000_000, 8, GME, USD), source=RPC,
                       source_time=Instant(1), fetch_time=Instant(1), block=None,
                       status=FetchStatus.OK)
    balance = Observation(value=Amount(10**18, 18, GME), source=RPC, source_time=None,
                          fetch_time=Instant(1), block=None, status=FetchStatus.OK)
    Holding(asset=GME, balance=balance, universe_status=UniverseStatus.IDENTITY_IN_DOUBT,
            universe_reason="registry status ASSET_STATUS_DELISTED, not ACTIVE",
            mark=mark, value=Fixed(25, 0, USD), value_reason=None)


def test_an_asset_dropped_from_the_registry_stays_describable_while_held(registry_copy):
    _, raw = u.read_pinned(u.REGISTRY, registry_copy)
    payload = json.loads(raw)
    payload["assets"] = [a for a in payload["assets"] if a["tokenSymbol"] != "CRM"]
    _, current = u.read_pinned(u.REGISTRY, registry_copy)
    plan = u.plan_refresh(u.REGISTRY, "api.robinhood.com/rhj/assets",
                          json.dumps(payload).encode(), Instant(2), current)
    u.store(plan, registry_copy)
    with pytest.raises(u.HeldAssetRemoved):
        u.accept(plan, registry_copy, held=[CRM])
    u.accept(plan, registry_copy, held=[CRM], acknowledge_removed_held=True)
    doc = json.loads((registry_copy / u.FEED_MAP_FILE).read_text())
    doc["reviewed_against"][u.REGISTRY] = plan.pin.sha256
    (registry_copy / u.FEED_MAP_FILE).write_text(json.dumps(doc))

    universe = u.load(registry_copy)
    with pytest.raises(u.Refused):
        universe.stock(CRM, beacon=Check(True))  # no longer admissible to buy
    held = universe.held_asset(CRM, decimals=18)  # and still in the book
    assert held.identity.value is False and "not in rhj_assets" in held.identity.reason


# the boundary ------------------------------------------------------------------------

def test_core_universe_imports_nothing_from_adapters():
    import ast
    import pathlib
    import sys
    tree = ast.parse(pathlib.Path(u.__file__).read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.level:  # relative: only .types, within core
                assert node.module == "types", node.module
            else:
                assert node.module.split(".")[0] in sys.stdlib_module_names, node.module
        elif isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] in sys.stdlib_module_names, alias.name
