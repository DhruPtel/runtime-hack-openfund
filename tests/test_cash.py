"""One definition of cash and order size (after the 3.8 sweep's R1 to R3). H: money.

The aggregator, the planner and the gates each counted cash their own way
(LESSONS 2026-09-19, the design lesson). These tests hold the three bugs that
came of it closed. Each computes what an order is worth itself, from the order's
amounts and the snapshot's marks, and never from a figure the code under test
derived.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

from fund import config
from fund.agents import risk
from fund.core import gates
from fund.core.types import document_id
from phase3 import (
    ADDRESS, ENTRIES, LIMITS, SEATS, SNAPSHOT, book, example_text, worth, written,
)

MANDATE = config.load_json("mandate.json")
REPORTS = [risk.ReportText(seat, example_text(seat)) for seat in SEATS]  # a quorum of four
USDG = next(h for h in SNAPSHOT["holdings"] if h["asset"]["kind"] == "cash")
FLOOR = LIMITS.cash_floor_usd
SETTINGS = risk.Settings(model="claude-sonnet-5", max_tokens=12000, transport_timeout_s=1,
                         worker_deadline_s=2, bytes_per_token=Decimal("1.8"))


def mark(address: str) -> Decimal:
    if address.lower() == USDG["asset"]["address"]:
        return Decimal(USDG["mark"]["price_usd"])
    return Decimal(ENTRIES[address.lower()]["mark"]["price_usd"])


def traded(order) -> Decimal:
    """What an order sells, at the mark: computed here, not read from the plan."""
    return Decimal(order["sell"]["amount"]) * mark(order["sell"]["address"])


def cash_left(plan, indices) -> Decimal:
    cash = Decimal(plan["book"]["cash_usd"])
    for order in plan["orders"]:
        if order["index"] in indices:
            cash += traded(order) if order["side"] == "sell" else -traded(order)
    return cash


def calls(**words):
    """price-trend's calls, two empty seats for a quorum of three."""
    trend = [{"symbol": s, "address": ADDRESS[s], "word": w, "confidence": c}
             for s, (w, c) in words.items()]
    return [{"seat": "price-trend", "calls": trend}, {"seat": "cross-asset-macro", "calls": []},
            {"seat": "execution-quality", "calls": []}]


def approve_all(plan) -> str:
    lines = [f"RISK {document_id(plan)}"]
    for o in plan["orders"]:
        lines += [f"ORDER {o['index']} {o['asset']['symbol']} approve", "Scripted, not a model's."]
    return "\n".join(lines + ["OVERALL approve", "Scripted."]) + "\n"


def decided(plan, tmp_path, reply=None):
    return risk.review(plan, document_id(plan), reports=REPORTS, snapshot=SNAPSHOT,
                       mandate=MANDATE, limits=LIMITS, settings=SETTINGS, work_dir=tmp_path,
                       recorded_reply=reply if reply is not None else approve_all(plan))


# --- R1: the cash floor is judged on the orders approved -----------------------------------------

def test_r1_a_blocked_sell_does_not_leave_the_buys_it_funded_approved(tmp_path):
    """$20 of cash and $180 of META. Sell META, buy MSFT. META's quotes are two
    minutes old, so both META sells are blocked. The MSFT buys they would have paid
    for must not be approved: at the sweep, approved cash was −$17.49. (At the
    sweep the sells were blocked by impact, which since S8 no longer binds a sell.)"""
    plan = written(calls(META=("sell", "high"), MSFT=("buy", "high")),
                   the_book=book({"META": worth("META", "180")}, cash="20"),
                   META={"fetched_ms": 1_790_000_000_000 - 120_000})
    outcome = decided(plan, tmp_path)
    approved = set(outcome["decision"]["approved"])
    sides = {o["index"]: (o["side"], o["asset"]["symbol"]) for o in plan["orders"]}
    assert not any(sides[i] == ("sell", "META") for i in approved)
    assert cash_left(plan, approved) >= FLOOR
    dropped = [o for o in outcome["decision"]["orders"] if "cash-floor" in o["vetoed_by"]]
    assert dropped and all(sides[o["index"]] == ("buy", "MSFT") for o in dropped)


def test_r1_a_risk_veto_on_a_sell_drops_the_buys_it_funded(tmp_path):
    plan = written(calls(META=("sell", "high"), MSFT=("buy", "high")),
                   the_book=book({"META": worth("META", "180")}, cash="20"))
    veto_sells = approve_all(plan).replace("META approve", "META veto")
    outcome = decided(plan, tmp_path, veto_sells)
    assert cash_left(plan, set(outcome["decision"]["approved"])) >= FLOOR


# --- R2: the planner never writes a plan its own floor refuses ------------------------------------

def test_r2_a_plan_that_sells_and_buys_in_one_cycle_keeps_the_floor_and_clears(tmp_path):
    """NAV $205 with $20.50 of cash. Sell META, buy AAPL and MSFT. At the sweep the
    planner counted the sell's exact dollars as freed, sold less, and its own floor
    gate blocked every order, the sell included."""
    the_book = book({"META": worth("META", "60"), "AMD": worth("AMD", "60"),
                     "INTC": worth("INTC", "64.5")}, cash="20.50")
    plan = written(calls(META=("sell", "medium"), AAPL=("buy", "high"), MSFT=("buy", "high")),
                   the_book=the_book)
    every = {o["index"] for o in plan["orders"]}
    assert {o["side"] for o in plan["orders"]} == {"sell", "buy"}
    assert cash_left(plan, every) >= FLOOR
    outcome = decided(plan, tmp_path)
    assert set(outcome["decision"]["approved"]) == every


# --- R3: no order trades more than the per-trade limit ---------------------------------------------

def test_r3_a_full_exit_never_sells_more_than_the_limit_in_one_order():
    """META worth $25.90 sold whole. At the sweep it went as one order labelled $25
    that sold $25.90."""
    held = worth("META", "25.90")
    plan = written(calls(META=("sell", "high")), the_book=book({"META": held}, cash="174.10"))
    sells = [o for o in plan["orders"] if o["side"] == "sell"]
    assert sum(Decimal(o["sell"]["amount"]) for o in sells) == Decimal(held.raw).scaleb(-18)
    assert all(traded(o) <= LIMITS.max_trade_usd for o in sells)


def test_r3_the_order_size_gate_reads_what_an_order_sells_not_its_label():
    plan = written(calls(META=("sell", "high")),
                   the_book=book({"META": worth("META", "60")}, cash="140"))
    order = plan["orders"][0]
    order["sell"]["amount"] = format(Decimal(order["sell"]["amount"]) * 2, "f")  # sells double
    result = gates.evaluate(plan, snapshot=SNAPSHOT, mandate=MANDATE, limits=LIMITS, reported=3)
    assert "order-size" in result["orders"][0]["blocked_by"]


# --- the floor's other edges, and the planner's funding ------------------------------------------

def test_the_floor_never_drops_a_sell_so_a_book_below_it_can_sell_its_way_back(tmp_path):
    """$5 of cash, below the $20 floor, and $195 of META and AMD. Sell META: the
    one sale raises cash, and the floor on the approved set does not block it."""
    plan = written(calls(META=("sell", "low")),
                   the_book=book({"META": worth("META", "97.50"), "AMD": worth("AMD", "97.50")},
                                 cash="5"))
    outcome = decided(plan, tmp_path)
    assert outcome["decision"]["approved"] == [o["index"] for o in plan["orders"]]
    assert all(o["side"] == "sell" for o in plan["orders"])


def test_an_unresolved_floor_plans_no_buy_and_settles_none():
    thresholds = config.load_json("thresholds.json")
    unset = gates.Limits.from_config({**thresholds, "cash_floor_usd": None}, MANDATE,
                                     config.load_json("models.json"))
    plan = written(calls(META=("sell", "high"), MSFT=("buy", "high")),
                   the_book=book({"META": worth("META", "60")}, cash="140"), limits=unset)
    assert {o["side"] for o in plan["orders"]} == {"sell"}
    assert plan["funding"]["share_funded"] is None
    buy_plan = written(the_book=book(), limits=LIMITS)
    kept, dropped, floor = gates.settle(buy_plan, [o["index"] for o in buy_plan["orders"]],
                                        snapshot=SNAPSHOT, limits=unset)
    assert kept == [] and len(dropped) == 4 and floor.value is None


def test_the_planner_funds_buys_only_from_cash_above_the_floor():
    """85% held in TSLA, 15% in cash, and the four approved reports want 31.25% of new
    buys. The floor is $20 of $200: $10 is spare, and the buys are scaled to it."""
    plan = written(the_book=book({"TSLA": worth("TSLA", "170")}, cash="30"))
    assert Decimal(plan["funding"]["share_funded"]).quantize(Decimal("0.0001")) == Decimal("0.16")
    every = {o["index"] for o in plan["orders"]}
    assert FLOOR <= cash_left(plan, every) < FLOOR + Decimal("0.05")


def test_a_rule_is_named_once_among_an_orders_vetoes(tmp_path):
    """R7: over the context budget, `context-budget` blocked each order and was also
    the reason no vote came; it is named once."""
    plan = written()
    outcome = risk.review(plan, document_id(plan), reports=REPORTS, snapshot=SNAPSHOT,
                          mandate=MANDATE, settings=SETTINGS, work_dir=tmp_path,
                          limits=dataclasses.replace(LIMITS, context_budget_tokens=20_000),
                          recorded_reply=approve_all(plan))
    assert all(o["vetoed_by"] == ["context-budget"] for o in outcome["decision"]["orders"])


# --- 4.0 P10: which holding is cash, and a book's NAV, each defined once -------------------------

def test_worth_is_exact_past_28_significant_digits():
    """$131 of GME at an 8-decimal mark is a 29-digit product. `worth` said exact, and
    rounded it at 28 digits until 4.0. No position of the $200 book reaches $100, so
    nothing it decided was rounded; but the planner's NAV and the ledger's must agree
    to the last digit, so it is exact now."""
    from fractions import Fraction
    from fund.core import cash
    from fund.core.types import USD, Amount, AssetId, Price
    gme = AssetId(4663, ADDRESS["GME"])
    amount, mark = Amount(5_832_497_744_366_588_876, 18, gme), Price(2_253_123_457, 8, gme, USD)
    value = cash.worth(amount, mark)
    assert len(value.as_tuple().digits) == 29
    assert Fraction(value) == Fraction(5_832_497_744_366_588_876 * 2_253_123_457, 10 ** 26)


def test_the_one_cash_leg_is_usdg_and_every_other_holding_is_a_position():
    from fund.core import cash
    asset, decimals = cash.cash_leg(SNAPSHOT)
    assert (asset.address, decimals) == (USDG["asset"]["address"], 6)
    gas = next(h for h in SNAPSHOT["holdings"] if h["asset"]["kind"] == "gas")
    assert gas["asset"]["symbol"] == "ETH" and asset.address != gas["asset"]["address"]
    for holdings in ([], [USDG, USDG]):  # none, or two: which would be cash is not known
        try:
            cash.cash_leg({**SNAPSHOT, "holdings": holdings})
        except ValueError as refused:
            assert "exactly one cash asset" in str(refused)
        else:
            raise AssertionError("a snapshot without exactly one cash asset named one")


def test_a_books_nav_is_one_function_and_it_is_exact(monkeypatch):
    """The planner's NAV comes from `cash.nav`: replace it, and `plan.book` follows.
    `ledger.value` is held to the same in test_ledger.py."""
    from fund.core import cash, plan
    assert cash.nav(Decimal("0.1"), [Decimal("1E-40"), Decimal("2")]) == Decimal(
        "2.1000000000000000000000000000000000000001")
    from fund.core.types import Amount, AssetId
    meta = Amount.from_units("0.1", 18, AssetId(4663, ADDRESS["META"]))
    held = book({"META": meta}, cash="150").holdings
    assert book({"META": meta}, cash="150").nav_usd == Decimal(150) + Decimal("0.1") * Decimal(
        ENTRIES[ADDRESS["META"]]["mark"]["price_usd"])
    monkeypatch.setattr(cash, "nav", lambda cash_usd, values: Decimal("12345"))
    assert plan.book(held, Decimal("150"), SNAPSHOT).nav_usd == Decimal("12345")
