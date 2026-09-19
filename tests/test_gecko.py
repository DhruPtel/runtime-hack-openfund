"""Unit 1.4, the GeckoTerminal corroborator: price and 24h volume read exactly and
matched by address, and a missing, zero, duplicated or unreadable entry never read
as a price. Replies follow the batch endpoint's, captured 2026-09-19 UTC."""

from __future__ import annotations

import ast
import json
from pathlib import Path

from fund.adapters import gecko, http
from fund.core.types import AssetId, FetchStatus, Fixed, Instant, Price

CHAIN = 4663
AMZN = AssetId(CHAIN, "0x12f190a9f9d7d37a250758b26824b97ce941bf54")
SPY = AssetId(CHAIN, "0x117cc2133c37b721f49de2a7a74833232b3b4c0c")
FETCHED = Instant(1_789_779_709_000)
HEADERS = {"date": "Sat, 19 Sep 2026 01:01:49 GMT", "cf-cache-status": "MISS"}


def entry(asset: AssetId, *, price="254.1327539942", volume="2253536.02715481", symbol="AMZN",
          network="robinhood") -> dict:
    return {"id": f"{network}_{asset.address}", "type": "token",
            "attributes": {"address": asset.address, "symbol": symbol, "decimals": 18,
                           "price_usd": price, "volume_usd": {"h24": volume}},
            "relationships": {"top_pools": {"data": [{"id": "robinhood_0xpool", "type": "pool"}]}}}


def batch(*entries, assets=(AMZN,), status=200, body=None) -> gecko.Batch:
    raw = body if body is not None else json.dumps({"data": list(entries)}).encode()
    return gecko.Batch(tuple(assets), FETCHED, http.Reply.of((status, raw, HEADERS)), None)


def test_price_and_volume_are_exact_with_their_provenance():
    c = gecko.parse(batch(entry(AMZN)), "robinhood")[AMZN]
    assert c.price.value == Price(2541327539942, 10, AMZN, "USD")
    assert c.volume_24h.value == Fixed(225353602715481, 8, "USD")
    assert c.price.source.locator == f"networks/robinhood/tokens/{AMZN.address}"
    assert c.price.source_time is None and c.price.fetch_time == FETCHED and c.price.block is None
    assert "lists 1 of them, a floor" in c.price.detail and "edge cache MISS" in c.price.detail


def test_an_entry_is_matched_by_address_never_by_symbol():
    impostor = AssetId(CHAIN, "0x" + "ab" * 20)
    c = gecko.parse(batch(entry(impostor, symbol="AMZN")), "robinhood")[AMZN]
    assert c.price.status is FetchStatus.ABSENT and c.price.value is None


def test_an_entry_from_another_network_is_not_ours():
    c = gecko.parse(batch(entry(AMZN, network="eth")), "robinhood")[AMZN]
    assert c.price.status is FetchStatus.ABSENT


def test_a_token_missing_from_a_200_is_absent_not_zero():
    got = gecko.parse(batch(entry(SPY, symbol="SPY"), assets=(AMZN, SPY)), "robinhood")
    assert got[AMZN].price.status is FetchStatus.ABSENT and got[AMZN].price.value is None
    assert got[AMZN].volume_24h.status is FetchStatus.ABSENT
    assert "did not list this address" in got[AMZN].price.detail
    assert got[SPY].price.ok


def test_a_null_price_is_absent_and_leaves_the_volume_alone():
    c = gecko.parse(batch(entry(AMZN, price=None)), "robinhood")[AMZN]
    assert c.price.status is FetchStatus.ABSENT and "price_usd is null" in c.price.detail
    assert c.volume_24h.ok


def test_a_zero_or_unreadable_price_is_refused():
    for bad in ("0", "0.0", "-1.5", "1e-05", "n/a"):
        c = gecko.parse(batch(entry(AMZN, price=bad)), "robinhood")[AMZN]
        assert c.price.status is FetchStatus.REFUSED, bad


def test_a_zero_volume_is_a_reading_not_a_refusal():
    c = gecko.parse(batch(entry(AMZN, volume="0.0")), "robinhood")[AMZN]
    assert c.volume_24h.ok and c.volume_24h.value.raw == 0


def test_two_entries_for_one_address_are_refused():
    c = gecko.parse(batch(entry(AMZN), entry(AMZN, price="300")), "robinhood")[AMZN]
    assert c.price.status is FetchStatus.REFUSED and "2 entries" in c.price.detail


def test_a_body_that_is_not_the_batch_shape_refuses_every_asset():
    got = gecko.parse(batch(body=b"<html>busy</html>", assets=(AMZN, SPY)), "robinhood")
    assert all(c.price.status is FetchStatus.REFUSED for c in got.values())


def test_an_unreachable_source_is_unreachable_for_every_asset_in_the_batch():
    settings = gecko.Settings.load()

    def refuse(url, body, timeout):
        raise ConnectionRefusedError("[Errno 111] Connection refused")

    g = settings.gecko(transport=refuse, clock=lambda: FETCHED)
    g.client._sleep = lambda s: None
    got = g.corroborate([AMZN, SPY])
    assert all(c.price.status is FetchStatus.UNREACHABLE and c.price.value is None
               for c in got.values())
    assert "GECKOTERMINAL" in got[AMZN].price.detail


def test_assets_are_asked_in_batches_of_the_documented_ceiling():
    assets = [AssetId(CHAIN, "0x" + format(i, "040x")) for i in range(1, 36)]
    paths = []

    def transport(url, body, timeout):
        paths.append(url)
        asked = url.rsplit("/", 1)[1].split(",")
        return 200, json.dumps({"data": [entry(AssetId(CHAIN, a)) for a in asked]}).encode(), {}

    g = gecko.Settings.load().gecko(transport=transport, clock=lambda: FETCHED)
    g.client.min_interval_s = 0
    got = g.corroborate(assets)
    assert [len(p.rsplit("/", 1)[1].split(",")) for p in paths] == [30, 5]
    assert len(got) == 35 and all(c.price.ok for c in got.values())
    assert paths[0].startswith("https://api.geckoterminal.com/api/v2/networks/robinhood/tokens/multi/")


def test_a_429_with_retry_after_zero_backs_off_and_then_reads():
    replies = iter([(429, b'{"status":{"error_code":429}}', {"Retry-After": "0"}),
                    (200, json.dumps({"data": [entry(AMZN)]}).encode(), HEADERS)])
    sleeps: list[float] = []
    g = gecko.Settings.load().gecko(transport=lambda *a: next(replies), clock=lambda: FETCHED)
    g.client._sleep, g.client.min_interval_s = sleeps.append, 0
    assert g.corroborate([AMZN])[AMZN].price.ok
    assert sleeps == [5.0]  # the configured backoff, not Retry-After's 0


def test_the_request_is_a_get():
    seen = []

    def transport(url, body, timeout):
        seen.append(body)
        return 200, json.dumps({"data": []}).encode(), {}

    gecko.Settings.load().gecko(transport=transport, clock=lambda: FETCHED).corroborate([AMZN])
    assert seen == [None]


def test_the_adapter_imports_no_other_adapter():
    tree = ast.parse(Path(gecko.__file__).read_text())
    imported = {node.module for node in tree.body if isinstance(node, ast.ImportFrom)}
    imported |= {f"{node.module}.{a.name}" for node in tree.body if isinstance(node, ast.ImportFrom)
                 for a in node.names}
    assert not any("chain_4663" in name for name in imported)
