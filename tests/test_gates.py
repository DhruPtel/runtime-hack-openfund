"""Unit 3.4: the gate array over a written plan. H: this is what may refuse a
trade, and what the treasurer will ask again before it submits.

Plans are built from the four approved reports and the committed capture, with
quotes from the labelled fake venue in phase3.py. Null blocks exactly as False
refuses (PLAN §2 invariant 5).
"""

from __future__ import annotations

import copy
import dataclasses
from decimal import Decimal

from fund import config
from fund.core import gates
from phase3 import LIMITS, SNAPSHOT, SYMBOLS, book, worth, written

MANDATE = config.load_json("mandate.json")


def evaluate(plan, *, snapshot=SNAPSHOT, mandate=MANDATE, limits=LIMITS, reported=4, extra=()):
    return gates.evaluate(plan, snapshot=snapshot, mandate=mandate, limits=limits,
                          reported=reported, extra=extra)


def blocked(result) -> dict[str, list[str]]:
    return {o["symbol"]: o["blocked_by"] for o in result["orders"] if not o["cleared"]}


def test_the_approved_reports_plan_clears_every_gate():
    result = evaluate(written())
    assert result["plan_clear"] and blocked(result) == {}
    assert [g["rule"] for g in result["plan"]] == ["quorum", "turnover"]  # the floor: settle
    assert [g["rule"] for g in result["orders"][0]["gates"]] == [
        "tradeable", "mandate", "order-size", "quote", "position-weight"]
    assert Decimal(result["turnover_usd"]).quantize(Decimal("0.01")) == Decimal("62.50")


def test_a_stale_quote_and_a_costly_one_are_refused_by_the_rule_that_judged_them():
    result = evaluate(written(META={"fetched_ms": 1_790_000_000_000 - 120_000},
                              INTC={"impact_bps": 60}))
    assert blocked(result) == {"META": ["quote-age"], "INTC": ["impact"]}
    assert {o["symbol"] for o in result["orders"] if o["cleared"]} == {"AMD", "USO"}


def test_a_quote_for_another_order_is_refused():
    plan = written()
    plan["orders"][0]["quote"], plan["orders"][1]["quote"] = (plan["orders"][1]["quote"],
                                                             plan["orders"][0]["quote"])
    result = evaluate(plan)
    assert blocked(result) == {"AMD": ["quote"], "USO": ["quote"]}
    assert "for another order" in result["orders"][0]["gates"][3]["reason"]


def test_no_quote_blocks_as_undetermined():
    plan = written()
    plan["orders"][2]["quote"] = None
    gate = evaluate(plan)["orders"][2]["gates"][3]
    assert gate["value"] is None and gate["rule"] == "quote"
    assert blocked(evaluate(plan)) == {"META": ["quote"]}


def test_an_asset_the_snapshot_does_not_call_tradeable_is_refused():
    snapshot = copy.deepcopy(SNAPSHOT)
    amd = next(a for a in snapshot["assets"] if a["asset"]["symbol"] == "AMD")
    amd["status"] = {"value": "below_corroborator_line", "rule": "corroborator-line",
                     "reason": "constructed", "verdict": False}
    assert blocked(evaluate(written(), snapshot=snapshot)) == {"AMD": ["tradeable"]}


def test_the_mandate_refuses_an_asset_it_does_not_name_a_revoked_mandate_and_an_empty_one():
    narrow = {**MANDATE, "allowed_assets": [a for a in MANDATE["allowed_assets"]
                                            if a["symbol"] != "USO"]}
    assert blocked(evaluate(written(), mandate=narrow)) == {"USO": ["mandate"]}
    revoked = evaluate(written(), mandate={**MANDATE, "revoked": True})
    assert set(blocked(revoked)) == {"AMD", "USO", "META", "INTC"}
    empty = evaluate(written(), mandate={**MANDATE, "allowed_assets": []})
    assert empty["orders"][0]["gates"][1]["value"] is None


def test_an_order_past_the_per_trade_limit_is_refused_on_what_it_sells_not_its_label():
    plan = written()
    plan["orders"][2]["usd"] = "99"  # a label: never read
    assert blocked(evaluate(plan)) == {}
    sold = plan["orders"][2]["sell"]
    sold["amount"] = format((Decimal(sold["amount"]) * Decimal("1.01")).quantize(
        Decimal("0.000001")), "f")  # $25.25 of USDG
    assert "order-size" in blocked(evaluate(plan))["META"]
    sold["amount"] = "25.1234567"  # more places than USDG has: unknown, and it blocks
    gate = next(o for o in evaluate(plan)["orders"] if o["symbol"] == "META")["gates"][2]
    assert gate["rule"] == "order-size" and gate["value"] is None


def test_a_buy_past_the_position_limit_is_refused_whatever_the_plan_says_it_leaves():
    """The gate recomputes the position from the book and the orders. The plan's
    own `after` figure is ignored, so editing it changes nothing."""
    tight = dataclasses.replace(LIMITS, max_position_weight=Decimal("0.1"))
    plan = written()
    for order in plan["orders"]:
        order["weight"]["after"] = "0"
    assert blocked(evaluate(plan, limits=tight)) == {"META": ["position-weight"]}


def test_a_plan_level_failure_blocks_every_order():
    everyone = {"AMD", "USO", "META", "INTC"}
    churn = evaluate(written(), limits=dataclasses.replace(LIMITS, turnover_max_bps=Decimal(100)))
    assert blocked(churn)["META"] == ["turnover"]
    short = evaluate(written(), reported=2)
    assert blocked(short)["INTC"] == ["quorum"]


def test_every_unresolved_limit_blocks_and_none_passes_as_a_default():
    for name in ("quorum_min_analysts", "max_position_weight", "max_trade_usd",
                 "turnover_max_bps"):  # the floor is settle's, on the approved set
        result = evaluate(written(), limits=dataclasses.replace(LIMITS, **{name: None}))
        assert not any(o["cleared"] for o in result["orders"]), name
        values = [g["value"] for g in result["plan"]] + [
            g["value"] for o in result["orders"] for g in o["gates"]]
        assert None in values and False not in values, name


def test_a_sell_passes_the_position_gate_and_frees_cash_for_the_floor():
    """Cycle two: AMZN held and cut. The sell's cash counts toward the floor."""
    plan = written(the_book=book({"AMZN": worth("AMZN", "40")}, cash="160"))
    result = evaluate(plan)
    amzn = next(o for o in result["orders"] if o["symbol"] == "AMZN")
    assert amzn["cleared"] and amzn["gates"][4]["reason"] == "a sell lowers the position"


def test_extra_plan_gates_are_counted():
    over = gates.Gate("context-budget", False, "constructed")
    assert set(blocked(evaluate(written(), extra=[over]))) == {"AMD", "USO", "META", "INTC"}
