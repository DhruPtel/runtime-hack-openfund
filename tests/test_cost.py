"""Unit 2.5: what each call cost, labelled an estimate, and the one check the
provider allows: aggregate against a settled window.

The usage window below is the one recorded at 1.7 (probes/out/analyst_cost.json,
`usage_settled_window`): 6 requests and $1.105746 over one day. The six calls in it
are recorded too: 0.9's two billed calls (1,793 input tokens with 864 and with 982
output: $0.012226 and $0.013406) and 1.7's four ($0.461206, $0.447586, $0.122966 and
$0.048356). They sum to the window's total exactly. The times below are placed
inside the window for the test; the costs are the recorded ones.
"""

import json
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

import pytest

from fund import config
from fund.adapters import bankr_llm, bankr_usage
from fund.agents import analyst

REPO = Path(__file__).resolve().parents[1]
PRICE = config.load_json("models.json")["pricing_per_million"]["claude-sonnet-5"]
SETTLE = config.load_json("models.json")["usage_settle_seconds"]

SETTLED_WINDOW = {
    "object": "usage_summary", "days": 1,
    "startDate": "2026-09-18T02:42:03.194Z", "endDate": "2026-09-19T02:42:03.194Z",
    "totals": {"totalRequests": 6, "totalInputTokens": 456288, "totalOutputTokens": 19317,
               "totalCost": 1.105746, "totalCacheCost": 0, "totalImageCost": 0},
    "byModel": [{"model": "claude-sonnet-5", "provider": "surplus", "requests": 6,
                 "inputTokens": 456288, "outputTokens": 19317, "totalCost": 1.105746}],
}
RECORDED_CALLS = ["0.012226", "0.013406", "0.461206", "0.447586", "0.122966", "0.048356"]


def calls_at(start, costs, step_minutes=30):
    return [bankr_usage.Call(at=start + timedelta(minutes=step_minutes * i),
                             usd=None if c is None else Decimal(c)) for i, c in enumerate(costs)]


# --- per call ---------------------------------------------------------------------------------------

def test_a_call_costs_its_own_usage_block_at_the_listed_price_and_says_it_is_an_estimate():
    cost = bankr_llm.cost({"prompt_tokens": 94716, "completion_tokens": 7484}, PRICE)
    assert cost["usd"] == "0.264272"  # 1.8a's recorded daily-close call, to the last digit
    assert cost["is_estimate"] is True and "F0.6.4" in cost["attribution"]
    assert cost["input_tokens"] == 94716 and cost["output_tokens"] == 7484
    assert bankr_llm.cost({"prompt_tokens": 1793, "completion_tokens": 864}, PRICE)["usd"] == \
        "0.012226"  # 0.9's cut-off call, billed anyway


def test_a_call_with_no_usage_block_or_no_price_has_an_unknown_cost_and_says_why():
    timed_out = bankr_llm.cost({}, PRICE)
    assert timed_out["usd"] is None and timed_out["is_estimate"] is True
    assert "F0.9.3" in timed_out["basis"]
    unpriced = bankr_llm.cost({"prompt_tokens": 1, "completion_tokens": 1}, {})
    assert unpriced["usd"] is None and "no listed price" in unpriced["basis"]


def test_each_call_and_each_analyst_carry_a_labelled_estimate(tmp_path):
    report = (REPO / "planning" / "REPORT-FORMAT.md").read_text().split(". price-trend\n", 1)[1] \
        .split("```\n", 2)[1]
    replies = iter([b"CALL nothing\n", report.encode()])

    def send(url, body, headers, timeout_s):
        text = next(replies).decode()
        return 200, json.dumps({"id": "chatcmpl-x", "model": "claude-sonnet-5",
                                "choices": [{"finish_reason": "stop",
                                             "message": {"content": text}}],
                                "usage": {"prompt_tokens": 94716,
                                          "completion_tokens": 7484}}).encode()

    import hashlib
    snapshot = REPO / "fixtures" / "snapshots" / "66852293-253315c0e691" / "snapshot.json"
    job = {"seat": "price-trend", "agent": "0x…", "snapshot_path": str(snapshot),
           "snapshot_sha256": hashlib.sha256(snapshot.read_bytes()).hexdigest(),
           "model": "claude-sonnet-5", "max_tokens": 12000, "transport_timeout_s": 600,
           "worker_deadline_s": 630, "retry_budget": 1, "gateway_url": "http://unused",
           "pricing": PRICE, "result_path": str(tmp_path / "r.json")}
    result = analyst.run(job, "bk_fake", send=send)
    assert result["status"] == "ok" and len(result["attempts"]) == 2
    for attempt in result["attempts"]:
        assert attempt["cost"]["usd"] == "0.264272" and attempt["cost"]["is_estimate"] is True
        assert attempt["request_id"] == "chatcmpl-x"
        datetime.fromisoformat(attempt["at"].replace("Z", "+00:00"))
    seat = result["cost"]
    assert seat["usd"] == "0.528544" and seat["calls"] == 2 and seat["calls_of_unknown_cost"] == 0
    assert seat["is_estimate"] is True, "a per-analyst figure is an estimate and says so"


# --- the window, read back, and the one comparison it allows ------------------------------------------

def test_the_window_is_the_one_the_provider_states_not_the_one_asked_for():
    window = bankr_usage.parse({**SETTLED_WINDOW, "days": 90}, requested_days=91)
    assert window.days == 90 and window.coerced  # F0.6.5: 91 comes back as 90
    assert bankr_usage.parse(SETTLED_WINDOW, requested_days=1).coerced is False


def test_a_settled_window_is_compared_aggregate_to_aggregate():
    window = bankr_usage.parse(SETTLED_WINDOW, requested_days=1)
    calls = calls_at(datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc), RECORDED_CALLS)
    result = bankr_usage.reconcile(calls, window, settle_seconds=SETTLE)
    assert result["status"] == "compared"
    assert result["ours_usd"] == result["provider_usd"] == "1.105746"
    assert result["difference_usd"] == "0" and result["our_calls"] == 6
    assert "aggregate to aggregate" in result["label"]


def test_a_window_that_has_not_settled_is_not_compared():
    window = bankr_usage.parse(SETTLED_WINDOW)
    late = window.end - timedelta(seconds=SETTLE / 6)
    calls = calls_at(datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc), RECORDED_CALLS[:-1])
    result = bankr_usage.reconcile(calls + [bankr_usage.Call(late, Decimal("0.048356"))], window,
                                   settle_seconds=SETTLE)
    assert result["status"] == "unsettled" and "difference_usd" not in result


def test_a_difference_is_reported_not_absorbed_and_unknown_costs_are_counted():
    window = bankr_usage.parse(SETTLED_WINDOW)
    calls = calls_at(datetime(2026, 9, 18, 10, 0, tzinfo=timezone.utc),
                     RECORDED_CALLS[2:] + [None])  # 0.9's two missing, one timed out
    outside = bankr_usage.Call(window.start - timedelta(hours=1), Decimal("1"))
    result = bankr_usage.reconcile(calls + [outside], window, settle_seconds=SETTLE)
    assert result["status"] == "compared" and result["difference_usd"] == "0.025632"
    assert result["our_calls_of_unknown_cost"] == 1 and result["calls_outside_window"] == 1


def test_a_read_is_one_request_and_a_refusal_is_named():
    sent = []

    def refused(url, headers, timeout_s):
        sent.append(url)
        return 403, b'{"error":{"message":"This API key does not have LLM Gateway access enabled."}}'

    unread = bankr_usage.fetch("bk_fake", days=1, get=refused)
    assert isinstance(unread, bankr_usage.Unread) and unread.status == 403 and len(sent) == 1
    assert sent[0].endswith("/v1/usage?days=1")
    read = bankr_usage.fetch("bk_fake", days=1,
                             get=lambda *a: (200, json.dumps(SETTLED_WINDOW).encode()))
    assert isinstance(read, bankr_usage.Window) and read.total_requests == 6


def test_the_cycle_reads_its_own_calls_for_the_comparison():
    cycle = {"seats": {"a": {"attempts": [
        {"at": "2026-09-18T10:00:00.000Z", "cost": {"usd": "0.264272"}},
        {"at": "2026-09-18T10:01:00.000Z", "cost": {"usd": None}}]}}}
    calls = bankr_usage.calls_from_cycle(cycle)
    assert [c.usd for c in calls] == [Decimal("0.264272"), None]
