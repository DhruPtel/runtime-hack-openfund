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
    ADDRESS, FETCHED_MS, FOUR, JUDGED_MS, LIMITS, SNAPSHOT, book, fake_quote, judged, propose,
    quoted, worth, written,
)


def sized(reports=FOUR, the_book=None):
    the_book = the_book or book()
    return plan.size(propose(reports, the_book), the_book, SNAPSHOT, LIMITS)


def test_the_four_approved_reports_become_four_buys_sized_from_their_weights():
    intents = sized()
    assert [(i.index, i.symbol, i.side, f"{i.usd:.2f}") for i in intents] == [
        (1, "AMD", "buy", "12.50"), (2, "USO", "buy", "12.50"), (3, "META", "buy", "25.00"),
        (4, "INTC", "buy", "12.50")]
    usdg_mark = Decimal("0.9999509")  # the capture's USDG mark
    for intent, dollars in zip(intents, ("12.50", "12.50", "25", "12.50")):
        spent = Decimal(intent.sell.raw).scaleb(-6)
        assert intent.usd == spent * usdg_mark  # what it sells, at the mark: nothing else
        assert intent.usd <= Decimal(dollars) < (spent + Decimal("0.000001")) * usdg_mark
        assert intent.sell.asset.address == "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
        assert intent.buy.address == ADDRESS[intent.symbol] and intent.buy_decimals == 18


def test_no_order_is_larger_than_the_per_trade_limit_and_dust_is_dropped():
    """A sale worth about $37.50 is two even orders, each within the $25 limit.
    Since the 3.8 sweep a move is split evenly, so no remainder is left over to
    drop; only a whole move under the minimum order is dust."""
    the_book = book({"TSLA": worth("TSLA", "50")}, cash="150")
    sell_high = {"symbol": "TSLA", "address": ADDRESS["TSLA"], "word": "sell",
                 "confidence": "high"}
    reports = [{"seat": "price-trend", "calls": [sell_high]},
               {"seat": "cross-asset-macro", "calls": []},
               {"seat": "execution-quality", "calls": []}]
    proposal = propose(reports, the_book)  # cut by 0.75 x 0.25
    intents = plan.size(proposal, the_book, SNAPSHOT, LIMITS)
    assert [(i.side, f"{i.usd:.2f}") for i in intents] == [("sell", "18.75"), ("sell", "18.75")]
    assert all(i.usd <= LIMITS.max_trade_usd for i in intents)
    fussy = dataclasses.replace(LIMITS, min_order_usd=Decimal(40))  # the whole move is dust
    assert plan.size(proposal, the_book, SNAPSHOT, fussy) == ()


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
    assert f"{sell.usd:.2f}" == "12.50"  # 0.0625 of a NAV a hair under $200
    assert Decimal(sell.sell.raw).scaleb(-18) * mark == sell.usd <= Decimal("12.5")
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
    turnover = Decimal(written_plan["turnover_usd"])
    assert written_plan["judged_at_ms"] and turnover <= Decimal("62.5") < turnover + Decimal("0.00001")
    assert Decimal(written_plan["cash_after_usd"]) == Decimal(200) - turnover
    amd = written_plan["orders"][0]
    assert amd["asset"]["symbol"] == "AMD"
    assert amd["weight"]["before"] == "0" and amd["weight"]["target"] == "0.0625"
    assert Decimal("0.062499") < Decimal(amd["weight"]["after"]) <= Decimal("0.0625")
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
    stale = written(META={"fetched_ms": FETCHED_MS - 120_000})
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
                              judged_at=Instant(JUDGED_MS))
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



# --- a split move shows each order as its part (after F3.8.12) ----------------------------------

GME_UP = [{"seat": "price-trend", "calls": [{"symbol": "GME", "address": ADDRESS["GME"],
                                             "word": "buy", "confidence": "high"}]},
          {"seat": "cross-asset-macro", "calls": []}, {"seat": "execution-quality", "calls": []}]


def test_each_part_of_a_split_move_shows_its_part_and_the_weight_after_it():
    """GME buy high: 0.75 x 0.25 = 0.1875 of $200, a $37.50 move split by the $25
    limit into two orders. At 3.8 each half showed the whole move, from 0 to 0.1875,
    and a real risk agent read them as two positions of 0.1875 each."""
    orders = [o for o in written(GME_UP)["orders"] if o["asset"]["symbol"] == "GME"]
    assert [(o["move"]["part"], o["move"]["of"]) for o in orders] == [(1, 2), (2, 2)]
    first, second = (o["weight"] for o in orders)
    assert first["before"] == "0" and first["after"] == second["before"]
    assert Decimal("0.09374") < Decimal(first["after"]) < Decimal("0.09376")
    assert Decimal("0.18749") < Decimal(second["after"]) <= Decimal("0.1875")
    assert first["target"] == second["target"] == "0.1875"
    assert Decimal(orders[0]["move"]["move_usd"]).quantize(Decimal("0.01")) == Decimal("37.50")
    says = orders[1]["move"]["says"]
    assert says.startswith("part 2 of 2 of one buy of $37.50 in GME, taking it from 0.000000 to "
                           "0.187500")
    assert "this order alone takes it from 0.093750 to 0.187500" in says


def test_a_whole_move_in_one_order_says_so():
    order = next(o for o in written()["orders"] if o["asset"]["symbol"] == "AMD")
    assert (order["move"]["part"], order["move"]["of"]) == (1, 1)
    assert order["move"]["says"].startswith("one buy of $12.50 in AMD, taking it from 0.000000")


def test_layout_1_is_the_3_8_exit_runs_and_is_kept_for_replay():
    """Every order showed its asset's whole move. Only a replay of a /1 record writes it."""
    the_book = book()
    proposal = propose(GME_UP, the_book)
    intents = plan.size(proposal, the_book, SNAPSHOT, LIMITS)
    old = plan.write(intents, quoted(intents), proposal=proposal, the_book=the_book,
                     snapshot=SNAPSHOT, snapshot_sha256="0" * 64, judged_at=Instant(1), layout=1)
    gme = [o for o in old["orders"] if o["asset"]["symbol"] == "GME"]
    assert all("move" not in o and o["weight"]["current"] == "0" for o in gme)
    assert gme[0]["weight"]["after"] == gme[1]["weight"]["after"]
    with pytest.raises(ValueError):
        plan.write(intents, {}, proposal=proposal, the_book=the_book, snapshot=SNAPSHOT,
                   snapshot_sha256="0" * 64, judged_at=Instant(1), layout=3)
