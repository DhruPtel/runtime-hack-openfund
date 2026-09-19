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
from phase3 import FETCHED_MS, LIMITS, SNAPSHOT, SYMBOLS, book, worth, written
MANDATE = config.load_json("mandate.json")


def evaluate(plan, *, snapshot=SNAPSHOT, mandate=MANDATE, limits=LIMITS, reported=4, extra=()):
    return gates.evaluate(plan, snapshot=snapshot, mandate=mandate, limits=limits,
                          reported=reported, extra=extra)


def gate(order_result, rule: str) -> dict:
    """An order's verdict under one rule, found by name, never by position."""
    return next(g for g in order_result["gates"] if g["rule"] == rule)


def blocked(result) -> dict[str, list[str]]:
    return {o["symbol"]: o["blocked_by"] for o in result["orders"] if not o["cleared"]}


def test_the_approved_reports_plan_clears_every_gate():
    result = evaluate(written())
    assert result["plan_clear"] and blocked(result) == {}
    assert [g["rule"] for g in result["plan"]] == [  # the floor: settle
        "quorum", "turnover", "snapshot-age", "mandate-term"]
    assert [g["rule"] for g in result["orders"][0]["gates"]] == [
        "tradeable", "mandate", "mandate-legs", "order-size", "quote", "position-weight"]
    assert Decimal(result["turnover_usd"]).quantize(Decimal("0.01")) == Decimal("62.50")


def test_a_stale_quote_and_a_costly_one_are_refused_by_the_rule_that_judged_them():
    result = evaluate(written(META={"fetched_ms": FETCHED_MS - 120_000},
                              INTC={"impact_bps": 60}))
    assert blocked(result) == {"META": ["quote-age"], "INTC": ["impact"]}
    assert {o["symbol"] for o in result["orders"] if o["cleared"]} == {"AMD", "USO"}


def test_a_quote_for_another_order_is_refused():
    plan = written()
    plan["orders"][0]["quote"], plan["orders"][1]["quote"] = (plan["orders"][1]["quote"],
                                                             plan["orders"][0]["quote"])
    result = evaluate(plan)
    assert blocked(result) == {"AMD": ["quote"], "USO": ["quote"]}
    assert "for another order" in gate(result["orders"][0], "quote")["reason"]


def test_no_quote_blocks_as_undetermined():
    plan = written()
    plan["orders"][2]["quote"] = None
    assert gate(evaluate(plan)["orders"][2], "quote")["value"] is None
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
    assert blocked(evaluate(written(), mandate=narrow)) == {"USO": ["mandate", "mandate-legs"]}
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
    size = gate(next(o for o in evaluate(plan)["orders"] if o["symbol"] == "META"), "order-size")
    assert size["value"] is None


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
    assert amzn["cleared"]
    assert [g["rule"] for g in amzn["gates"]] == [
        "priced", "mandate", "mandate-legs", "order-size", "quote"]


def test_extra_plan_gates_are_counted():
    over = gates.Gate("context-budget", False, "constructed")
    assert set(blocked(evaluate(written(), extra=[over]))) == {"AMD", "USO", "META", "INTC"}


def test_a_gate_set_this_code_does_not_define_refuses_rather_than_judging_by_another():
    """A record names the gate set it was judged by (3.9). A set the code does not
    define refuses, in `evaluate` and in `settle`, rather than judging by other gates."""
    assert gates.GATE_SET in gates.GATE_SETS and LIMITS.gate_set == gates.GATE_SET
    later = dataclasses.replace(LIMITS, gate_set=max(gates.GATE_SETS) + 1)
    for judge in (lambda: evaluate(written(), limits=later),
                  lambda: gates.settle(written(), [1], snapshot=SNAPSHOT, limits=later)):
        try:
            judge()
        except ValueError as refused:
            assert "gate set" in str(refused)
        else:
            raise AssertionError("an unknown gate set was judged")


# --- gate set 2 (4.4): S11, the mandate's term, S10; and what a book holds ------------------------

def test_s11_the_exit_run_was_judged_4_minutes_after_its_snapshot_and_the_1713_no_op_11_hours():
    from pathlib import Path
    import json
    cycles = Path(__file__).resolve().parents[1] / "fixtures" / "cycles"
    ages = {}
    for name in ("20260919T202259Z", "20260919T171351Z"):
        record = json.loads((cycles / name / "decision" / "record.json").read_text())
        ages[name] = gates.snapshot_age(record["snapshot"]["block"]["time"],
                                        record["decided_at_ms"], LIMITS)
    assert ages["20260919T202259Z"].passes
    assert ages["20260919T171351Z"].value is False and "past 900s" in ages["20260919T171351Z"].reason


def test_s11_fifteen_minutes_to_the_millisecond_and_never_before_the_block():
    block = "2026-09-19T06:01:49Z"
    at_block = 1_789_797_709_000
    assert gates.snapshot_age(block, at_block + 900_000, LIMITS).passes
    assert gates.snapshot_age(block, at_block + 900_001, LIMITS).value is False
    assert gates.snapshot_age(block, at_block - 1, LIMITS).value is False
    unset = dataclasses.replace(LIMITS, snapshot_max_age_s=None)
    assert gates.snapshot_age(block, at_block, unset).value is None


def test_a_plan_judged_too_long_after_its_snapshot_or_outside_the_mandates_term_refuses_all():
    stale = written()
    stale["judged_at_ms"] = 1_789_797_709_000 + 16 * 60_000
    result = evaluate(stale)
    assert not result["plan_clear"]
    assert all(o["blocked_by"] == ["snapshot-age"] for o in result["orders"])
    lapsed = {**MANDATE, "expires_at": "2026-09-19T06:00:00Z", "approved_at": "2026-09-12T06:00:00Z"}
    assert all(o["blocked_by"] == ["mandate-term"] for o in evaluate(written(), mandate=lapsed)["orders"])


def test_gate_set_1_still_judges_as_phase_3_did():
    one = evaluate(written(), limits=dataclasses.replace(LIMITS, gate_set=1))
    assert [g["rule"] for g in one["plan"]] == ["quorum", "turnover"]
    assert [g["rule"] for g in one["orders"][0]["gates"]] == [
        "tradeable", "mandate", "order-size", "quote", "position-weight"]


def test_an_order_gives_no_more_than_the_book_holds():
    gives = {"address": "0x" + "ab" * 20, "raw": "1000"}
    assert gates.held(gives, 1000).passes
    assert gates.held(gives, 999).value is False and gates.held(gives, None).value is False
