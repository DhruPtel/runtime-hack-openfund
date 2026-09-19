"""Unit 3.3: target weights to sized, quoted orders. H: this is where a view
becomes an amount of money.

Quotes come from the fake venue in phase3.py, labelled as such, and are judged
by `adapters/bankr_quote.tradeability`, the one definition of quote age and
impact.
"""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal

import pytest

from fund.core import plan
from fund.core.types import Instant, from_canonical
from phase3 import (
    ADDRESS, FOUR, LIMITS, SNAPSHOT, book, fake_quote, judged, propose, quoted, worth, written,
)


def sized(reports=FOUR, the_book=None):
    the_book = the_book or book()
    return plan.size(propose(reports, the_book), the_book, SNAPSHOT, LIMITS)


def test_the_four_approved_reports_become_four_buys_sized_from_their_weights():
    intents = sized()
    assert [(i.index, i.symbol, i.side, str(i.usd)) for i in intents] == [
        (1, "AMD", "buy", "12.50"), (2, "USO", "buy", "12.50"), (3, "META", "buy", "25"),
        (4, "INTC", "buy", "12.50")]
    usdg_mark = Decimal("0.9999509")  # the capture's USDG mark
    for intent in intents:
        spent = Decimal(intent.sell.raw).scaleb(-6)
        assert spent * usdg_mark <= intent.usd < (spent + Decimal("0.000001")) * usdg_mark
        assert intent.sell.asset.address == "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
        assert intent.buy.address == ADDRESS[intent.symbol] and intent.buy_decimals == 18


def test_no_order_is_larger_than_the_per_trade_limit_and_dust_is_dropped():
    """A move of about $37.50 is a $25 order and the rest. A remainder under the
    minimum order is dropped. TSLA is held worth a hair under $50, since a holding's
    units are rounded down, so the move is $37.49."""
    the_book = book({"TSLA": worth("TSLA", "50")}, cash="150")
    sell_high = {"symbol": "TSLA", "address": ADDRESS["TSLA"], "word": "sell",
                 "confidence": "high"}
    reports = [{"seat": "price-trend", "calls": [sell_high]},
               {"seat": "cross-asset-macro", "calls": []},
               {"seat": "execution-quality", "calls": []}]
    proposal = propose(reports, the_book)  # cut by 0.75 x 0.25
    intents = plan.size(proposal, the_book, SNAPSHOT, LIMITS)
    assert [(i.side, str(i.usd)) for i in intents] == [("sell", "25"), ("sell", "12.49")]
    assert all(i.usd <= LIMITS.max_trade_usd for i in intents)
    fussy = dataclasses.replace(LIMITS, min_order_usd=Decimal(13))
    assert [str(i.usd) for i in plan.size(proposal, the_book, SNAPSHOT, fussy)] == ["25"]


def test_hold_and_silence_trade_nothing_in_cycle_two():
    """NVDA held, and price-trend says hold. TSLA held, and no seat mentions it."""
    the_book = book({"NVDA": worth("NVDA", "20"), "TSLA": worth("TSLA", "10")}, cash="170")
    intents = sized(FOUR, the_book)
    assert {i.symbol for i in intents} == {"AMD", "USO", "META", "INTC"}


def test_a_sell_never_sells_more_than_is_held_and_a_cut_to_zero_sells_it_all():
    held = worth("AMZN", "10")  # AMZN sell low wants $12.50 cut; only $10 is held
    intents = sized(FOUR, book({"AMZN": held}, cash="190"))
    sells = [i for i in intents if i.side == "sell"]
    assert len(sells) == 1 and sells[0].symbol == "AMZN" and sells[0].index == 1
    assert sells[0].sell == held  # the whole position, not a unit more
    assert sells[0].buy.address == "0x5fc5360d0400a0fd4f2af552add042d716f1d168"


def test_a_partial_sell_sells_the_stock_worth_its_dollars_at_the_mark():
    held = worth("AMZN", "40")
    sell = [i for i in sized(FOUR, book({"AMZN": held}, cash="160")) if i.side == "sell"][0]
    mark = Decimal(next(a for a in SNAPSHOT["assets"]
                        if a["asset"]["symbol"] == "AMZN")["mark"]["price_usd"])
    assert str(sell.usd) == "12.49"  # 0.0625 of a NAV a hair under $200, cut to the cent
    assert Decimal(sell.sell.raw).scaleb(-18) * mark <= sell.usd
    assert sell.sell.raw < held.raw


def test_no_rebalance_plans_no_order():
    assert sized(FOUR[:2], book({"NVDA": worth("NVDA", "20")}, cash="180")) == ()


def test_a_holding_the_snapshot_cannot_mark_refuses_the_plan():
    from fund.core.types import Amount, AssetId
    unknown = Amount(10 ** 18, 18, AssetId(4663, "0x" + "ab" * 20))
    with pytest.raises(plan.PlanError, match="not in the snapshot"):
        plan.book({unknown.asset.address: unknown}, Decimal(100), SNAPSHOT)


def test_each_order_carries_its_fresh_quote_its_verdict_and_the_evidence_risk_reads():
    written_plan = written()
    assert written_plan["judged_at_ms"] and written_plan["turnover_usd"] == "62.5"
    assert written_plan["cash_after_usd"] == "137.5"
    amd = written_plan["orders"][0]
    assert amd["asset"]["symbol"] == "AMD"
    assert amd["weight"] == {"current": "0", "target": "0.0625", "after": "0.0625"}
    assert amd["quote"]["tradeable"] == {
        "value": True, "rule": None, "reason": amd["quote"]["tradeable"]["reason"]}
    assert "age 5.0s within 60s" in amd["quote"]["tradeable"]["reason"]
    assert amd["quote"]["venue_price_usd"] == "551.9120935475604"
    evidence = amd["evidence"]
    assert evidence["mark"]["price_usd"] == "559.42445"
    assert evidence["corroboration"]["divergence_bps"] == "105.98"
    assert evidence["findings"][0]["kind"] == "closed-session divergence"
    assert evidence["status"]["value"] == "tradeable"


def test_a_stale_or_costly_quote_is_recorded_with_the_rule_that_refused_it():
    stale = written(META={"fetched_ms": 1_790_000_000_000 - 120_000})
    meta = next(o for o in stale["orders"] if o["asset"]["symbol"] == "META")
    assert meta["quote"]["tradeable"]["value"] is False
    assert meta["quote"]["tradeable"]["rule"] == "quote-age"
    costly = written(INTC={"impact_bps": 60})
    intc = next(o for o in costly["orders"] if o["asset"]["symbol"] == "INTC")
    assert intc["quote"]["tradeable"]["rule"] == "impact"


def test_the_recorded_quote_is_the_observation_exactly_so_it_can_be_judged_again():
    intents = sized()
    seen = quoted(intents)
    written_plan = plan.write(intents, seen, proposal=propose(), the_book=book(),
                              snapshot=SNAPSHOT, snapshot_sha256="0" * 64,
                              judged_at=Instant(1_790_000_005_000))
    for order in written_plan["orders"]:
        back = from_canonical(json.dumps(order["quote"]["observation"]).encode())
        assert back == seen[order["index"]].observation
        again = judged(intents[order["index"] - 1], back)
        assert again.verdict == seen[order["index"]].verdict


def test_an_order_with_no_quote_carries_none():
    intents = sized()
    written_plan = plan.write(intents, {}, proposal=propose(), the_book=book(),
                              snapshot=SNAPSHOT, snapshot_sha256="0" * 64,
                              judged_at=Instant(1))
    assert all(o["quote"] is None for o in written_plan["orders"])


def test_a_proposal_made_on_a_bigger_book_never_sells_more_than_this_book_holds():
    """The guard behind every sell: a proposal from another book (here, one holding
    $40 of AMZN) asks for a $12.49 cut; this book holds $10, and sells only that."""
    bigger, smaller = book({"AMZN": worth("AMZN", "40")}, cash="160"), book(
        {"AMZN": worth("AMZN", "10")}, cash="190")
    proposal = propose(FOUR, bigger)
    assert next(r for r in proposal.rows if r.symbol == "AMZN").target > 0
    sells = [i for i in plan.size(proposal, smaller, SNAPSHOT, LIMITS) if i.side == "sell"]
    assert sum(i.sell.raw for i in sells) <= smaller.holdings[ADDRESS["AMZN"]].raw
