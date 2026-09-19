"""Unit 1.8: held-but-untradeable. A holding never leaves the book, whatever
takes its asset out of the buy universe.

Every case holds 2 NVDA and moves NVDA out of the buy universe one way. Then it
reads the snapshot's holdings:
- **the five ways PHASE-0-1 1.8 names:** not tradeable this snapshot, below
  the corroborator line, no longer markable, listed but not ACTIVE, and
  identity in doubt (dropped by the registry and carried, or an unread beacon);
- **the per-snapshot statuses 1.6 and 1.8 added:** no mark, short history,
  uncorroborated, and divergence veto.

Each time the holding is still there, with its universe status, and is either
valued at its own mark or explicitly unvalued with the reason. It is never
valued at zero, and never at the venue's quote. A final test asserts that
every way-out status is exercised here, so a status added later cannot slip
past this file.
"""

from __future__ import annotations

import dataclasses
from types import MappingProxyType

import pytest

from fund.core import snapshot, universe
from fund.core.types import Check, FetchStatus, UniverseStatus
from test_snapshot import BEACON, U, balance, entry, inputs, listed, offchain, stock  # the 1.6 builders

NVDA = listed("NVDA")
TWO = 2 * 10**18
HELD = {NVDA: balance(NVDA, TWO, 18)}
MARKED_VALUE = "505.2"  # 2 NVDA at the builders' mark of 252.60


def without_nvda(mapping):
    return MappingProxyType({a: v for a, v in mapping.items() if a != NVDA})


def tradeable():
    return [stock("NVDA")], U, {}


def not_tradeable_this_snapshot():
    return [stock("NVDA", impact=60)], U, {}


def below_the_corroborator_line():
    return [stock("NVDA", volume="242.1")], U, {}


def no_longer_markable():
    # The feed map no longer maps NVDA: it leaves the stocks with feeds, and is
    # held outside the universe, described by 1.2.
    u = dataclasses.replace(U, feeds=without_nvda(U.feeds))
    return [], u, {NVDA: u.held_asset(NVDA, 18, BEACON)}


def listed_but_not_active():
    record = dataclasses.replace(U.records[NVDA], status="ASSET_STATUS_INACTIVE")
    u = dataclasses.replace(U, records=MappingProxyType({**U.records, NVDA: record}))
    return [dataclasses.replace(stock("NVDA"), asset=u.stock(NVDA, BEACON))], u, {}


def dropped_by_the_registry_and_carried():
    carried = universe.CarriedAsset(asset=NVDA, symbol="NVDA", name="NVIDIA", decimals=18,
                                    removed_in="e" * 64)
    u = dataclasses.replace(U, records=without_nvda(U.records), feeds=without_nvda(U.feeds),
                            carried=MappingProxyType({NVDA: carried}))
    return [], u, {NVDA: u.held_asset(NVDA, 18)}


def beacon_unread():
    s = stock("NVDA")
    unread = U.stock(NVDA, Check(None, "beacon slot not read: unreachable: timeout"))
    return [dataclasses.replace(s, asset=unread)], U, {}


def no_mark():
    return [stock("NVDA", fresh=Check(False, "a gap this long in an open session is stale"))], U, {}


def short_history():
    return [stock("NVDA", reach=False)], U, {}


def uncorroborated():
    missing = offchain(None, status=FetchStatus.ABSENT, detail="GeckoTerminal did not list this address")
    return [stock("NVDA", corroboration=missing)], U, {}


def divergence_veto():
    return [stock("NVDA", corroborator="265.87982073", closed=False)], U, {}


#: (way out, its universe status, the holding's `valued` verdict, its value)
ROUTES = [
    (not_tradeable_this_snapshot, "not_tradeable", True, MARKED_VALUE),
    (below_the_corroborator_line, "below_corroborator_line", True, MARKED_VALUE),
    (no_longer_markable, "unmarkable", False, None),
    (listed_but_not_active, "listed_not_active", True, MARKED_VALUE),
    (dropped_by_the_registry_and_carried, "identity_in_doubt", False, None),
    (beacon_unread, "identity_in_doubt", True, MARKED_VALUE),
    (no_mark, "no_mark", False, None),
    (short_history, "short_history", True, MARKED_VALUE),
    (uncorroborated, "uncorroborated", True, MARKED_VALUE),
    (divergence_veto, "divergence_veto", True, MARKED_VALUE),
]


def build(route) -> snapshot.Snapshot:
    stocks, u, held_outside = route()
    return snapshot.build(inputs(*stocks, extra_balances=HELD, held_outside=held_outside), u)


def holding(snap) -> dict:
    rows = [h for h in snap.document["holdings"] if h["asset"]["address"] == NVDA.address]
    assert len(rows) == 1, "the holding left the book"
    return rows[0]


@pytest.mark.parametrize("route, status, valued, value", ROUTES, ids=[r[0].__name__ for r in ROUTES])
def test_a_holding_survives_each_way_out_of_the_buy_universe(route, status, valued, value):
    row = holding(build(route))
    assert row["balance"] == "2" and row["holding_status"]["owned"]["verdict"] is True
    assert row["universe_status"]["value"] == status
    assert row["holding_status"]["valued"]["verdict"] is valued
    assert row["value_usd"] == value
    if value is None:
        assert "not zero" in row["value_reason"]  # carried without a value, and it says so
    assert row["holding_status"]["exit"]["verdict"] is None  # a stock exit is not assessed in Phase 1


@pytest.mark.parametrize("route", [r[0] for r in ROUTES], ids=[r[0].__name__ for r in ROUTES])
def test_a_status_change_never_drops_a_holding(route):
    before, after = build(tradeable), build(route)
    assert holding(before)["universe_status"]["value"] == "tradeable"
    held = lambda snap: {(h["asset"]["address"], h["balance"]) for h in snap.document["holdings"]}  # noqa: E731
    assert held(before) == held(after)


def test_cash_and_gas_stay_holdings_valued_at_their_own_feeds_whatever_the_stocks_do():
    for route, *_ in ROUTES:
        rows = {h["asset"]["symbol"]: h for h in build(route).document["holdings"]}
        assert rows["USDG"]["value_usd"] == "0.0787381337678" and rows["ETH"]["value_usd"] is not None
        assert rows["USDG"]["universe_status"]["value"] == "not_a_stock"
        assert rows["USDG"]["holding_status"]["exit"]["verdict"] is True


def test_no_holding_is_valued_at_the_venue_quote():
    # Unmarkable: the quote's own price is in the snapshot's quotes, never in the book.
    row = holding(build(no_longer_markable))
    assert row["value_usd"] is None and row["mark"]["price_usd"] is None


def test_every_way_out_of_the_buy_universe_is_exercised_here():
    exercised = {status for _, status, _, _ in ROUTES}
    ways_out = {s.value for s in UniverseStatus} - {"tradeable", "not_a_stock"}
    assert exercised == ways_out, f"a status without a holding test: {sorted(ways_out - exercised)}"


def test_the_summary_lists_every_holding_with_its_value_or_its_absence():
    summary = build(dropped_by_the_registry_and_carried).document["summary"]
    assert summary["holding_columns"] == ["symbol", "universe_status", "valued", "value_usd"]
    assert ["NVDA", "identity_in_doubt", False, None] in summary["holdings"]
