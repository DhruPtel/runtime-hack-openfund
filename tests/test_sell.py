"""Selling what the fund holds (the operator's decision on the sweep's S8). H: money.

Buying into an asset and exiting one are different risks. A sell needs a price
to value what it sells, and a fresh quote at its size, with the mandate in force
and the order size. A buy keeps every check. DELL is the case: held, below the
corroborator line so outside the buy universe, and its $25 quote costs 64 bps,
past the 50 bps a buy may pay. It is not among the mandate's allowed assets here:
the mandate approved at 4.1 names all 35 markable stocks, DELL included, so these
tests narrow it by DELL to keep the case an asset the mandate does not name.
"""

from __future__ import annotations

import copy
import dataclasses
from decimal import Decimal

from fund import config
from fund.agents import risk
from fund.core import gates
from fund.core.types import document_id
from phase3 import ADDRESS, ENTRIES, LIMITS, SNAPSHOT, book, worth, written
from test_cash import REPORTS, SETTINGS, approve_all, calls
from test_schema import example, verdict

DELL = ADDRESS["DELL"]
APPROVED = config.load_json("mandate.json")
MANDATE = {**APPROVED, "allowed_assets": [a for a in APPROVED["allowed_assets"]
                                          if a["address"] != DELL]}


def evaluate(plan, snapshot=SNAPSHOT, mandate=MANDATE):
    return gates.evaluate(plan, snapshot=snapshot, mandate=mandate, limits=LIMITS, reported=3)


def held_dell(**changes):
    return written(calls(DELL=("sell", "high")),
                   the_book=book({"DELL": worth("DELL", "60")}, cash="140"), **changes)


def test_dell_is_outside_the_buy_universe_and_the_mandate():
    assert ENTRIES[DELL]["status"]["value"] == "below_corroborator_line"
    assert ENTRIES[DELL]["quote"]["swap_impact_bps"] == "64"
    assert DELL not in {a["address"] for a in MANDATE["allowed_assets"]}


def test_a_held_asset_outside_the_buy_universe_is_sold(tmp_path):
    plan = held_dell()
    sells = [o for o in plan["orders"] if o["asset"]["symbol"] == "DELL"]
    assert sells and all(o["side"] == "sell" for o in sells)
    result = evaluate(plan)
    assert all(o["cleared"] for o in result["orders"] if o["symbol"] == "DELL"), result
    quote_gate = next(g for g in result["orders"][0]["gates"] if g["rule"] == "quote")
    assert "impact is not a condition of selling" in quote_gate["reason"]
    outcome = risk.review(plan, document_id(plan), reports=REPORTS, snapshot=SNAPSHOT,
                          mandate=MANDATE, limits=LIMITS, settings=SETTINGS, work_dir=tmp_path,
                          recorded_reply=approve_all(plan))
    assert set(outcome["decision"]["approved"]) == {o["index"] for o in sells}


def test_a_buy_into_the_same_asset_is_still_refused():
    plan = written(calls(DELL=("buy", "high")), the_book=book())
    result = evaluate(plan)
    buys = [o for o in result["orders"] if o["symbol"] == "DELL"]
    assert buys and all(not o["cleared"] for o in buys)
    assert all({"tradeable", "mandate", "impact"} <= set(o["blocked_by"]) for o in buys), buys


def test_a_sell_still_needs_a_fresh_quote():
    stale = held_dell(DELL={"fetched_ms": 1_790_000_000_000 - 120_000})
    assert all(o["blocked_by"] == ["quote-age"] for o in evaluate(stale)["orders"])
    plan = held_dell()
    plan["orders"][0]["quote"] = None
    assert evaluate(plan)["orders"][0]["blocked_by"] == ["quote"]


def test_a_sell_still_needs_a_price():
    """Judged against a snapshot with no usable mark for DELL, as a later regate
    might be, the sale is undetermined, and it blocks."""
    snapshot = copy.deepcopy(SNAPSHOT)
    entry = next(a for a in snapshot["assets"] if a["asset"]["symbol"] == "DELL")
    entry["mark"]["verdict"] = {"verdict": False, "reason": "constructed: stale"}
    order = evaluate(held_dell(), snapshot=snapshot)["orders"][0]
    assert order["blocked_by"] == ["priced", "order-size"] and not order["cleared"]
    assert order["gates"][0]["value"] is None


def test_a_sell_still_needs_the_mandate_in_force():
    revoked = evaluate(held_dell(), mandate={**MANDATE, "revoked": True})
    assert all("mandate" in o["blocked_by"] for o in revoked["orders"])


def test_an_analysts_sell_call_on_it_does_not_refuse_the_report():
    """At the sweep, a sell call on an asset the snapshot does not call tradeable
    refused the whole report, which could cost the quorum. Any other word on it
    still refuses."""
    line = "CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 sell low"
    text = example("price-trend")
    assert line in text
    as_sell = text.replace(line, f"CALL DELL {DELL} sell low", 1)
    v = verdict(as_sell)
    assert "asset" not in {r.rule for r in v.refusals}
    assert ("DELL", "sell") in {(c["symbol"], c["word"]) for c in v.as_dict()["calls"]}
    as_buy = text.replace(line, f"CALL DELL {DELL} buy low", 1)
    assert any(r.rule == "asset" and "not tradeable" in r.detail
               for r in verdict(as_buy).refusals)
