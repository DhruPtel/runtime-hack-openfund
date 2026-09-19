"""Unit 3.5: the risk agent. Its model call is L; the override rule and its
process isolation are H.

The model is 2.4's fake gateway on 127.0.0.1, answering with scripted replies
that say they are scripted. Nothing leaves the machine and no real key is used.
"""

from __future__ import annotations

import dataclasses
from decimal import Decimal

import pytest

from fund import config
from fund.agents import risk, runner
from fund.core.types import document_id
from fund.store import reports
from phase3 import LIMITS, SEATS, SNAPSHOT, example_text, written
from test_runner import ALLOWED_NAMES, PRICE, FakeGateway

MANDATE = config.load_json("mandate.json")
SHARED = {"BANKR_LLM_KEY": "bk_fake_shared_gateway_key_0000000001"}
TREASURER = {"SIGNING_KEY": "f" * 64, "BANKR_KEY_EXEC": "bk_fake_treasurer_exec_key_000000001"}
REPORTS = [risk.ReportText(seat, example_text(seat)) for seat in SEATS]


@pytest.fixture
def gateway():
    made = []

    def make(script):
        made.append(FakeGateway(script))
        return made[-1]

    yield make
    for g in made:
        g.close()


def settings(url, **changes):
    base = dict(model="claude-sonnet-5", max_tokens=12000, transport_timeout_s=2.5,
                worker_deadline_s=3.5, bytes_per_token=Decimal("1.8"), pricing=PRICE,
                gateway_url=url)
    return risk.Settings(**{**base, **changes})


def scripted(plan, votes=None, overall="approve") -> str:
    lines = [f"RISK {document_id(plan)}"]
    for order in plan["orders"]:
        lines += [f"ORDER {order['index']} {order['asset']['symbol']} "
                  f"{(votes or {}).get(order['asset']['symbol'], 'approve')}",
                  "Scripted for the test, not a model's words."]
    return "\n".join(lines + [f"OVERALL {overall}", "Scripted."]) + "\n"


def review(plan, g=None, tmp_path=None, recorded=None, limits=LIMITS, environ=SHARED, **kw):
    return risk.review(plan, document_id(plan), reports=REPORTS, snapshot=SNAPSHOT,
                       mandate=MANDATE, limits=limits,
                       settings=settings(g.url if g else "http://127.0.0.1:9"),
                       work_dir=tmp_path, credential=runner.SharedGatewayKey(environ).for_seat(
                           "risk"), environ=environ, recorded_reply=recorded, **kw)


def approved(outcome) -> list[str]:
    return [o["symbol"] for o in outcome["decision"]["orders"] if o["approved"]]


def test_risk_approves_in_its_own_process_which_never_sees_a_treasurer_key(
        gateway, tmp_path, monkeypatch):
    for name, value in TREASURER.items():
        monkeypatch.setenv(name, value)  # the parent holds them; the child must not
    plan = written()
    g = gateway({"risk": [("report", scripted(plan))]})
    store = reports.ReportStore(tmp_path / "store")
    outcome = review(plan, g, tmp_path, store=store)
    assert approved(outcome) == ["AMD", "USO", "META", "INTC"]
    assert g.count("risk") == 1 and g.requests[0]["key"] == SHARED["BANKR_LLM_KEY"]
    names = set(outcome["reply"]["environment_names"])
    assert names <= ALLOWED_NAMES and "SIGNING_KEY" not in names and "BANKR_KEY_EXEC" not in names
    for path in tmp_path.rglob("*.json"):
        text = path.read_text()
        assert SHARED["BANKR_LLM_KEY"] not in text and TREASURER["SIGNING_KEY"] not in text
    stored = store.get(outcome["reply"]["report_id"])
    assert stored["seat"] == "risk" and stored["text"] == scripted(plan)
    assert outcome["budget"]["gate"]["value"] is True and outcome["budget"]["tokens"] < 70_000


def test_the_model_may_veto_what_the_gates_passed(gateway, tmp_path):
    plan = written()
    g = gateway({"risk": [("report", scripted(plan, {"AMD": "veto"}))]})
    outcome = review(plan, g, tmp_path)
    amd = outcome["decision"]["orders"][0]
    assert amd["symbol"] == "AMD" and not amd["approved"] and amd["vetoed_by"] == ["risk"]
    assert approved(outcome) == ["USO", "META", "INTC"]


def test_the_model_cannot_approve_what_a_gate_refused(gateway, tmp_path):
    """META's quote is two minutes old. The model approves every order; the gate
    decides."""
    plan = written(META={"fetched_ms": 1_790_000_000_000 - 120_000})
    g = gateway({"risk": [("report", scripted(plan))]})
    outcome = review(plan, g, tmp_path)
    meta = next(o for o in outcome["decision"]["orders"] if o["symbol"] == "META")
    assert not meta["approved"] and meta["vetoed_by"] == ["quote-age"]
    assert meta["model_vote"] == "approve" and "the gates decide: quote-age" in meta["note"]
    assert approved(outcome) == ["AMD", "USO", "INTC"]


def test_an_overall_veto_vetoes_every_order(gateway, tmp_path):
    plan = written()
    g = gateway({"risk": [("report", scripted(plan, overall="veto"))]})
    outcome = review(plan, g, tmp_path)
    assert approved(outcome) == []
    assert all(o["vetoed_by"] == ["risk-overall"] for o in outcome["decision"]["orders"])


@pytest.mark.parametrize("reply, rule", [
    ("I approve of all of these trades.", "risk-unreadable"),
    ("RISK " + "0" * 64 + "\nOVERALL approve\nok", "risk-unreadable"),
])
def test_a_reply_in_the_wrong_shape_vetoes_everything(gateway, tmp_path, reply, rule):
    plan = written()
    g = gateway({"risk": [("report", reply)]})
    outcome = review(plan, g, tmp_path)
    assert approved(outcome) == [] and outcome["decision"]["no_votes"]["rule"] == rule
    assert g.count("risk") == 1  # never retried


def test_a_missing_order_vote_vetoes_that_order_alone(tmp_path):
    """S6: an order the reply does not vote on is vetoed on its own; the rest stand."""
    plan = written()
    reply = scripted(plan).replace("ORDER 2 USO approve\n", "")
    votes, why = risk.parse(reply, plan, document_id(plan))
    assert why is None and 2 not in votes.orders and "no vote on order(s) [2]" in votes.notes[0]
    outcome = review(plan, None, tmp_path, recorded=reply)
    uso = next(o for o in outcome["decision"]["orders"] if o["symbol"] == "USO")
    assert uso["vetoed_by"] == ["risk-no-vote"] and approved(outcome) == ["AMD", "META", "INTC"]


# --- S6: the shapes a real model may write, each of which vetoed everything at the sweep -----------

def reply_lines(plan, order_line, overall_line="OVERALL approve", head=None):
    """A reply whose first order is written as `order_line` (with {sha} and the
    order's own symbol in it), every other order plainly approved."""
    sha = document_id(plan)
    lines = [head if head is not None else f"RISK {sha}"]
    for o in plan["orders"]:
        if o["index"] == 1:
            lines.append(order_line.format(symbol=o["asset"]["symbol"]))
        else:
            lines.append(f"ORDER {o['index']} {o['asset']['symbol']} approve")
        lines.append("A reason.")
    return "\n".join(lines + [overall_line, "A summary."]) + "\n"


@pytest.mark.parametrize("order_line, vote", [
    ("ORDER 1 {symbol} veto (quote-age)", "veto"),
    ("ORDER 1 {symbol} veto - stale mark", "veto"),
    ("ORDER 1: {symbol} — Veto", "veto"),
    ("**ORDER 1 {symbol} veto**", "veto"),
    ("  - ORDER 1 {symbol} approve", "approve"),
    ("Order #1 {symbol}: Approved.", "approve"),
    ("ORDER 1 vetoed: no symbol given", "veto"),
])
def test_each_shape_that_vetoed_everything_at_the_sweep_is_now_read(order_line, vote):
    plan = written()
    votes, why = risk.parse(reply_lines(plan, order_line), plan, document_id(plan))
    assert why is None, why
    assert votes.orders[1][0] == vote and set(votes.orders) == {1, 2, 3, 4}


@pytest.mark.parametrize("overall_line, vote", [
    ("OVERALL: approve", "approve"), ("OVERALL approve.", "approve"),
    ("**Overall verdict: VETO**", "veto")])
def test_the_overall_line_is_read_in_its_variants(overall_line, vote):
    plan = written()
    votes, why = risk.parse(reply_lines(plan, "ORDER 1 {symbol} approve", overall_line), plan,
                            document_id(plan))
    assert why is None and votes.overall[0] == vote


def test_a_reason_that_begins_overall_is_prose_not_a_verdict():
    plan = written()
    reply = reply_lines(plan, "ORDER 1 {symbol} approve", "Overall, the plan follows the reports.")
    votes, why = risk.parse(reply, plan, document_id(plan))
    assert votes.overall is None and "no OVERALL line" in votes.notes[-1]
    assert all(v == "approve" for v, _ in votes.orders.values())


def test_what_still_cannot_be_read_vetoes_everything():
    plan = written()
    other = "RISK " + "0" * 64
    assert risk.parse(reply_lines(plan, "ORDER 1 {symbol} approve", head=other), plan,
                      document_id(plan))[0] is None  # a vote on another plan
    assert risk.parse("I approve of all of these trades.", plan, document_id(plan))[0] is None


def test_a_vote_given_both_ways_or_under_the_wrong_symbol_vetoes_that_order():
    plan = written()
    both = reply_lines(plan, "ORDER 1 {symbol} approve").replace(
        "ORDER 2 USO approve", "ORDER 2 USO approve\nORDER 2 USO veto")
    votes, _ = risk.parse(both, plan, document_id(plan))
    assert 2 not in votes.orders and 1 in votes.orders
    wrong = reply_lines(plan, "ORDER 1 MSFT approve")
    votes, _ = risk.parse(wrong, plan, document_id(plan))
    assert 1 not in votes.orders and "voted under MSFT" in " ".join(votes.notes)


@pytest.mark.parametrize("step, reason", [(("status", 504), "refused"), (("hang", 10), None)])
def test_no_reply_vetoes_everything_and_is_never_retried(gateway, tmp_path, step, reason):
    plan = written()
    g = gateway({"risk": [step]})
    outcome = review(plan, g, tmp_path)
    assert approved(outcome) == [] and outcome["decision"]["no_votes"]["rule"] == "risk-unavailable"
    assert g.count("risk") == 1
    assert outcome["reply"]["reason"] in ([reason] if reason else ["timeout", "worker deadline"])


def test_over_the_context_budget_no_call_is_made_and_every_order_is_vetoed(gateway, tmp_path):
    plan = written()
    g = gateway({"risk": [("report", scripted(plan))]})
    outcome = review(plan, g, tmp_path,
                     limits=dataclasses.replace(LIMITS, context_budget_tokens=20_000))
    assert g.count("risk") == 0 and outcome["reply"] is None
    assert approved(outcome) == []
    assert all("context-budget" in o["vetoed_by"] for o in outcome["decision"]["orders"])
    assert outcome["gates"]["plan"][-1]["rule"] == "context-budget"


def test_a_treasurer_key_as_the_risk_key_stops_before_any_process(gateway, tmp_path):
    plan = written()
    g = gateway({"risk": [("report", scripted(plan))]})
    leaked = {"BANKR_LLM_KEY": TREASURER["BANKR_KEY_EXEC"], **TREASURER}
    with pytest.raises(runner.SpendAuthorityError):
        review(plan, g, tmp_path, environ=leaked)
    assert g.count("risk") == 0


def test_a_recorded_reply_replays_the_same_decision_without_a_call(gateway, tmp_path):
    plan = written()
    reply = scripted(plan, {"INTC": "veto"})
    g = gateway({"risk": [("report", reply)]})
    live = review(plan, g, tmp_path)
    again = review(plan, None, tmp_path / "replay", recorded=reply)
    assert again["decision"] == live["decision"] and again["gates"] == live["gates"]
    assert again["reply"]["recorded"] is True and g.count("risk") == 1
