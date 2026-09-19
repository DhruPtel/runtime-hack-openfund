"""Unit 3.1: reports to target weights, a total function.

Built on the four reports approved at 2.1 (planning/REPORT-FORMAT.md), parsed
by 2.2's schema as the aggregator receives them, against the committed weekend
capture. Holding tests pass a non-empty book: the hold-and-silence rule does not
bite on cycle one, where paper holdings start empty.
"""

from __future__ import annotations

import json
import random
from decimal import Decimal
from pathlib import Path

from fund import config
from fund.agents import schema
from fund.core import aggregate, gates

REPO = Path(__file__).resolve().parents[1]
FORMAT = (REPO / "planning" / "REPORT-FORMAT.md").read_text()
SNAPSHOT = json.loads((REPO / "fixtures" / "snapshots" / "66852293-253315c0e691"
                       / "snapshot.json").read_text())
SEATS = ["price-trend", "cross-asset-macro", "execution-quality", "price-integrity"]
ANALYSTS = config.load_json("analysts.json")
KINDS = {a["id"]: a["vocabulary"] for a in ANALYSTS["analysts"]}
WEIGHTS = {w: Decimal(v) for w, v in ANALYSTS["confidence_weights"].items()}
SYMBOLS = {a["asset"]["address"]: a["asset"]["symbol"] for a in SNAPSHOT["assets"]}
ADDRESS = {symbol: address for address, symbol in SYMBOLS.items()}
LIMITS = gates.Limits.from_config(config.load_json("thresholds.json"))


def approved(seat: str) -> dict:
    """An approved example as the aggregator receives it: parsed, then as_dict()."""
    text = FORMAT.split(f". {seat}\n", 1)[1].split("```\n", 2)[1]
    report, refusals = schema.parse(text)
    assert refusals == ()
    return report.as_dict()


def abstaining(seat: str) -> dict:
    return {"seat": seat, "agent": "unassigned", "no_calls": True, "calls": []}


def call(symbol: str, word: str, confidence: str) -> dict:
    return {"symbol": symbol, "address": ADDRESS[symbol], "word": word, "confidence": confidence}


def run(reports, current=None, cash=None, limits=LIMITS, nav="200"):
    current = {ADDRESS[s]: Decimal(w) for s, w in (current or {}).items()}
    cash = Decimal(1) - sum(current.values(), Decimal(0)) if cash is None else Decimal(cash)
    return aggregate.aggregate(reports, kinds=KINDS, current=current, cash_weight=cash,
                               limits=limits, confidence_weights=WEIGHTS,
                               symbols=SYMBOLS)


def targets(proposal) -> dict[str, str]:
    return {r.symbol: aggregate.decimal_text(r.target) for r in proposal.rows if r.target}


FOUR = [approved(seat) for seat in SEATS]


def test_the_four_approved_reports_give_a_book_of_their_buy_calls():
    p = run(FOUR)
    assert p.rebalance and p.quorum.passes and p.reported == tuple(sorted(SEATS))
    # META buy medium: 0.5 x 0.25. AMD buy medium, cautioned medium by price-integrity:
    # 0.5 x (1 - 0.5) x 0.25. INTC and USO buy low: 0.25 x 0.25.
    assert targets(p) == {"META": "0.125", "AMD": "0.0625", "INTC": "0.0625", "USO": "0.0625"}
    assert p.cash_target == Decimal("0.6875") and p.residual == 0
    row = {r.symbol: r for r in p.rows}
    assert row["AMD"].direction == Decimal("0.5") and row["AMD"].caution == Decimal("0.5")
    assert row["MSTR"].score is None and row["MSTR"].caution == Decimal("0.75")  # caution only
    assert row["AMZN"].target == 0 and "not held" in row["AMZN"].why  # a sell makes no position
    assert row["NVDA"].target == 0 and row["NVDA"].why == "hold: kept"


def test_a_held_asset_on_hold_and_one_nobody_mentions_both_survive():
    """Cycle two: NVDA is held and price-trend says hold; TSLA is held and no seat
    mentions it. Both targets are exactly what is held."""
    p = run(FOUR, current={"NVDA": "0.1", "TSLA": "0.05"})
    row = {r.symbol: r for r in p.rows}
    assert row["NVDA"].target == Decimal("0.1") and row["NVDA"].why == "hold: kept"
    assert row["TSLA"].target == Decimal("0.05") and row["TSLA"].contributions == ()
    assert row["TSLA"].why == "no seat mentioned it: kept"
    assert p.rebalance and targets(p)["META"] == "0.125"


def test_a_sell_cuts_a_held_position_and_never_below_zero():
    assert targets(run(FOUR, current={"AMZN": "0.1"}))["AMZN"] == "0.0375"  # 0.1 - 0.25 x 0.25
    row = {r.symbol: r for r in run(FOUR, current={"AMZN": "0.03"}).rows}
    assert row["AMZN"].target == 0 and row["AMZN"].why == "sell: cut by 0.03"


def test_a_buy_stops_at_the_position_limit():
    row = {r.symbol: r for r in run(FOUR, current={"META": "0.2"}).rows}
    assert row["META"].target == Decimal("0.25") and "capped" in row["META"].why
    row = {r.symbol: r for r in run(FOUR, current={"META": "0.3"}).rows}
    assert row["META"].target == Decimal("0.3")  # past the limit already: kept, not cut


def test_caution_discounts_a_direction_call_and_seats_are_averaged():
    reports = [{"seat": "price-trend", "calls": [call("AMD", "buy", "medium")]},
               {"seat": "cross-asset-macro", "calls": [call("AMD", "sell", "low")]},
               {"seat": "price-integrity", "calls": [call("AMD", "caution", "high")]}]
    row = run(reports).rows[0]
    assert row.direction == Decimal("0.125")  # (0.5 - 0.25) / 2
    assert row.score == Decimal("0.03125")  # x (1 - 0.75)
    assert row.target == Decimal("0.007812")  # x 0.25, rounded toward zero
    assert run(reports).residual == Decimal("0.0000005")


def test_below_quorum_no_rebalance_and_every_holding_kept():
    p = run(FOUR[:2], current={"NVDA": "0.1", "AMZN": "0.1"})
    assert not p.rebalance and p.quorum.value is False and "below the quorum of 3" in p.reason
    assert {r.symbol: r.target for r in p.rows if r.current} == {"NVDA": Decimal("0.1"),
                                                                 "AMZN": Decimal("0.1")}
    assert all(r.target == r.current for r in p.rows)


def test_every_seat_abstaining_keeps_every_holding_and_liquidates_nothing():
    """PLAN §2 invariant 6: all-abstain is no rebalance, never a sale."""
    p = run([abstaining(s) for s in SEATS], current={"NVDA": "0.1", "TSLA": "0.2"}, cash="0.7")
    assert not p.rebalance and p.reason == "every seat that reported abstained"
    assert {r.symbol: r.target for r in p.rows} == {"NVDA": Decimal("0.1"), "TSLA": Decimal("0.2")}
    assert p.cash_target == Decimal("0.7")


def test_the_aggregator_counts_no_cash_its_targets_are_what_the_calls_want():
    """Since the 3.8 sweep, funding is the planner's, through core/cash.py (R2). With
    85% held and 15% in cash, the targets are still the calls' own, and the plan
    decides what cash can pay for (test_cash.py, test_plan.py)."""
    p = run(FOUR, current={"TSLA": "0.85"}, cash="0.15")
    assert targets(p)["META"] == "0.125" and targets(p)["TSLA"] == "0.85"
    assert p.cash_target == Decimal("0.15") - Decimal("0.3125")
    assert "cash floor" not in {r.symbol: r for r in p.rows}["META"].why


def test_an_unresolved_limit_blocks_the_rebalance():
    for name in ("quorum_min_analysts", "max_position_weight"):
        thresholds = {**config.load_json("thresholds.json"), name: None}
        p = run(FOUR, current={"NVDA": "0.1"}, limits=gates.Limits.from_config(thresholds))
        assert not p.rebalance and "unresolved" in p.reason, name
        assert all(r.target == r.current for r in p.rows)


def test_the_order_reports_arrive_in_changes_nothing():
    shuffled = FOUR[:]
    random.Random(7).shuffle(shuffled)
    assert run(shuffled).as_dict() == run(FOUR).as_dict()


# --- 3.2: the table ------------------------------------------------------------------------------

def test_the_table_shows_each_seat_the_weights_cash_and_residual():
    shown = aggregate.table(run(FOUR), SEATS, Decimal("200"))
    lines = shown.splitlines()
    assert lines[0] == "4 of 4 seats reported · 4 seat(s) reported, at least the quorum of 3"
    assert "confidence: low 0.25, medium 0.5, high 0.75" in shown
    amd = next(line for line in lines if line.startswith("AMD "))
    assert "buy med +0.5" in amd and "caution med 0.5" in amd and amd.endswith("+12.50")
    assert next(line for line in lines if line.startswith("cash")).split()[-3:] == [
        "1", "0.6875", "-62.50"]
    assert lines[-1].startswith("residual 0:") and "the plan funds raises" in lines[-1]
    held = aggregate.table(run(FOUR[:2], current={"NVDA": "0.1"}), SEATS)
    assert "NO REBALANCE" in held


def test_an_indented_call_reaches_the_aggregator():
    """R6: META's block indented as the brief's own template is. At the sweep its call
    was silently prose, and META got no weight."""
    from test_schema import _indented_meta, example as approved_text, verdict as checked
    text = _indented_meta(approved_text("price-trend"))
    parsed = checked(text).as_dict()
    others = [r for r in FOUR if r["seat"] != "price-trend"]
    assert targets(run(others + [parsed]))["META"] == "0.125"
