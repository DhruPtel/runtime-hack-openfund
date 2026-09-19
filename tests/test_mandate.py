"""Unit 4.1: the mandate the treasurer refuses to act outside. H: spend authority.

The approved mandate is `config/mandate.json`. The provisional one it replaced is the
copy the exit run's cycle carries (`fixtures/cycles/20260919T202259Z/decision/config/`),
with placeholder approvals and 20 assets, and no USDG.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from fund import config
from fund.core import gates
from fund.core.types import Instant
from fund.treasurer import mandate

REPO = Path(__file__).resolve().parents[1]
APPROVED = config.load_json("mandate.json")
PROVISIONAL = json.loads((REPO / "fixtures" / "cycles" / "20260919T202259Z" / "decision"
                          / "config" / "mandate.json").read_text())
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
ETH = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
GME = "0x1b0e319c6a659f002271b69db8a7df2f911c153e"
OUTSIDE = "0x" + "ab" * 20  # constructed: no asset the mandate names


def at(iso: str) -> Instant:
    return Instant(int(datetime.fromisoformat(iso.replace("Z", "+00:00")).timestamp() * 1000))


def order(side: str, stock: str = GME, cash: str = USDG) -> dict:
    """The legs of a plan's order: a buy gives cash for the stock, a sell the reverse."""
    sell, buy = (cash, stock) if side == "buy" else (stock, cash)
    return {"side": side, "asset": {"chain_id": 4663, "address": stock, "symbol": "X"},
            "sell": {"address": sell}, "buy": {"address": buy}}


# --- what the operator approved -----------------------------------------------------------------

def test_the_approved_mandate_loads_with_the_35_stocks_eth_and_usdg_for_seven_days():
    loaded = mandate.load()
    assets = {a["address"] for a in loaded["allowed_assets"]}
    feeds = {e["asset"] for e in json.loads((REPO / "config" / "registry" / "feed_map.json")
                                            .read_text())["entries"]}
    assert assets == feeds and len(assets) == 37 and {USDG, ETH} <= assets
    approved, expires = (datetime.fromisoformat(loaded[k].replace("Z", "+00:00"))
                         for k in ("approved_at", "expires_at"))
    assert loaded["approved_by"] == "the operator" and expires - approved == timedelta(days=7)
    assert loaded["revoked"] is False and loaded["cumulative_budget_usd"] is None


def test_the_provisional_mandate_of_3_4_refuses_to_load():
    with pytest.raises(mandate.MandateError, match="approved_by is not an approval"):
        mandate.validated(PROVISIONAL)


@pytest.mark.parametrize("name", mandate.REQUIRED)
def test_a_null_required_field_refuses_by_name(name):
    with pytest.raises(mandate.MandateError, match=name):
        mandate.validated({**APPROVED, name: None})


def test_a_mandate_that_expires_before_its_approval_or_names_no_time_refuses():
    for broken in ({"expires_at": APPROVED["approved_at"]}, {"approved_at": "yesterday"},
                   {"expires_at": "2026-09-26T21:54:28+00:00"}):  # not written as UTC
        with pytest.raises(mandate.MandateError):
            mandate.validated({**APPROVED, **broken})


# --- in force: not expired, not revoked ------------------------------------------------------------

def test_an_expired_mandate_refuses_from_the_moment_it_expires():
    expires = at(APPROVED["expires_at"])
    assert mandate.in_force(APPROVED, Instant(expires.epoch_ms - 1)) is APPROVED
    for moment in (expires, Instant(expires.epoch_ms + 86_400_000)):
        with pytest.raises(mandate.MandateError, match="expired at 2026-09-26T21:54:28Z"):
            mandate.in_force(APPROVED, moment)


def test_a_revoked_mandate_refuses_and_an_unset_flag_blocks():
    now = at(APPROVED["approved_at"])
    assert gates.mandate_term({**APPROVED, "revoked": True}, now).value is False
    assert gates.mandate_term({**APPROVED, "revoked": "no"}, now).value is None
    with pytest.raises(mandate.MandateError):
        mandate.in_force({**APPROVED, "revoked": True}, now)


def test_the_clock_starts_at_approval_and_the_term_is_what_the_gate_says():
    """The treasurer's loader asks the one gate; it never compares a time itself."""
    now = at(APPROVED["approved_at"])
    assert gates.mandate_term(APPROVED, now).passes
    assert gates.mandate_term(PROVISIONAL, now).value is None


# --- S10: the legs traded, not the label -----------------------------------------------------------

def test_s10_a_buy_needs_both_its_legs_allowed():
    assert gates.mandate_legs(order("buy"), APPROVED).passes
    # the provisional mandate: GME is allowed, but USDG, the leg a buy gives, is not
    refused = gates.mandate_legs(order("buy"), PROVISIONAL)
    assert refused.value is False and USDG in refused.reason
    assert gates.mandate_legs(order("buy", stock=OUTSIDE), APPROVED).value is False


def test_s10_a_sell_needs_what_it_gets_allowed_and_may_give_a_held_stock_outside_it():
    outside = {**APPROVED, "allowed_assets": [a for a in APPROVED["allowed_assets"]
                                              if a["address"] != GME]}
    assert gates.mandate_legs(order("sell"), outside).passes  # S8: always sellable
    no_cash = {**APPROVED, "allowed_assets": [a for a in APPROVED["allowed_assets"]
                                              if a["address"] != USDG]}
    assert gates.mandate_legs(order("sell"), no_cash).value is False
    assert gates.mandate_legs(order("buy"), {**APPROVED, "allowed_assets": []}).value is None


# --- the live budget ------------------------------------------------------------------------------

def test_the_null_live_budget_blocks_a_live_order_and_a_set_one_bounds_it():
    assert gates.live_budget(APPROVED, Decimal(0), Decimal("0.5")).value is None
    five = {**APPROVED, "cumulative_budget_usd": "5"}
    assert gates.live_budget(five, Decimal("4.5"), Decimal("0.5")).passes
    assert gates.live_budget(five, Decimal("4.6"), Decimal("0.5")).value is False
