"""Unit 4.0: the ledger's values, one definition each (P3 to P10).

Built on the exit run that ended Phase 3 (`fixtures/cycles/20260919T202259Z/`): its
snapshot, its six approved orders, and the quotes recorded for them. Each order is
filled on paper at its recorded quote here, as 4.5 will fill one at a fresh quote.
Every expected figure is worked from the order's amounts and the snapshot's marks in
the test, never read from the code under test.

An H unit: this is the money. Each rule was broken in a copy and a test failed.
"""

from __future__ import annotations

import dataclasses
import json
from decimal import Decimal
from pathlib import Path

import pytest

from fund.core import cash, ledger, orders
from fund.core.types import (
    USD, Amount, AssetId, ChainAddress, ExecutionMode, Order, OrderState, Price,
    from_canonical,
)

REPO = Path(__file__).resolve().parents[1]
CYCLE = REPO / "fixtures" / "cycles" / "20260919T202259Z" / "decision"
SNAPSHOT = json.loads((REPO / "fixtures" / "snapshots" / "67364057-c06abd9e89f0"
                       / "snapshot.json").read_text())
RECORD = json.loads((CYCLE / "record.json").read_text())
DECISION = json.loads((CYCLE / "envelope.json").read_text())["decision_id"]
QUOTES = {q["index"]: from_canonical(json.dumps(q["observation"]).encode()).value
          for q in json.loads((CYCLE / "quotes.json").read_text())["quotes"]}
PLANNED = {o["index"]: o for o in RECORD["plan"]["orders"]}
APPROVED = [o["index"] for o in RECORD["decision"]["approved"]]  # 1, 3, 4, 5, 6, 8
CHAIN = SNAPSHOT["block"]["chain_id"]
WALLET = ChainAddress(CHAIN, "0x93faecde3c88a713e1edddf417c02c326889a3da")
HELD = {h["asset"]["symbol"]: h for h in SNAPSHOT["holdings"]}
USDG = AssetId(CHAIN, HELD["USDG"]["asset"]["address"])
ETH = AssetId(CHAIN, HELD["ETH"]["asset"]["address"])
USDG_MARK = Decimal(HELD["USDG"]["mark"]["price_usd"])  # 0.99992279: not a dollar
ETH_MARK = Decimal(HELD["ETH"]["mark"]["price_usd"])


def usd_mark(asset: AssetId, price: str | Decimal) -> Price:
    return Price.parse(str(price), asset, USD)


def mark_of(symbol_or_asset) -> Decimal:
    address = symbol_or_asset.address if isinstance(symbol_or_asset, AssetId) else next(
        a["asset"]["address"] for a in SNAPSHOT["assets"] if a["asset"]["symbol"] == symbol_or_asset)
    entry = next(e for e in [*SNAPSHOT["assets"], *SNAPSHOT["holdings"]]
                 if e["asset"]["address"] == address)
    return Decimal(entry["mark"]["price_usd"])


def order(index: int, state=OrderState.SUBMITTED, mode=ExecutionMode.PAPER) -> Order:
    """The exit run's order `index`, as 4.2 will list it: id and key from the decision."""
    quote = QUOTES[index]
    return Order(order_id=orders.order_id(DECISION, index),
                 idempotency_key=orders.idempotency_key(DECISION, index), mode=mode,
                 wallet=WALLET, sell=quote.sell, buy_asset=quote.buy.asset,
                 min_buy=quote.min_buy, state=state)


def filled(index: int) -> ledger.Fill:
    return ledger.paper_fill(order(index), QUOTES[index], SNAPSHOT)


def units(amount: Amount) -> Decimal:
    return Decimal(amount.raw).scaleb(-amount.decimals)


# --- P3: a fill ---------------------------------------------------------------------------------

def test_a_paper_fill_is_the_quote_at_the_snapshots_marks():
    fill = filled(1)  # GME, part 1 of 2
    quote = QUOTES[1]
    assert (fill.gave, fill.got) == (quote.sell, quote.buy)
    assert fill.gave == Amount(18_751_447, 6, USDG) and fill.mode is ExecutionMode.PAPER
    assert fill.order_id == f"{DECISION}/1" and fill.cash_asset == USDG
    assert Decimal(fill.gave_mark.raw).scaleb(-fill.gave_mark.decimals) == USDG_MARK
    assert Decimal(fill.got_mark.raw).scaleb(-fill.got_mark.decimals) == mark_of("GME")
    # its value is what it paid: USDG at USDG's own mark, the plan's own figure
    assert fill.value_usd == Decimal("18.751447") * USDG_MARK == Decimal(PLANNED[1]["usd"])


def test_a_fill_is_valued_once_at_the_marks_it_recorded():
    fill = filled(1)
    moved = {**SNAPSHOT, "holdings": [{**h, "mark": {**h["mark"], "price_usd": "1.5"}}
                                      if h["asset"]["symbol"] == "USDG" else h
                                      for h in SNAPSHOT["holdings"]]}
    assert cash.mark_of(moved, USDG.address) != fill.gave_mark
    assert fill.value_usd == Decimal("18.751447") * USDG_MARK  # not re-marked


def test_a_paper_fill_is_refused_for_a_live_order_an_unsent_one_and_another_orders_quote():
    with pytest.raises(ledger.LedgerError, match="live"):
        ledger.paper_fill(order(1, mode=ExecutionMode.LIVE), QUOTES[1], SNAPSHOT)
    for state in (OrderState.PREPARED, OrderState.UNKNOWN, OrderState.CONFIRMED):
        with pytest.raises(ledger.LedgerError, match="only a submitted order fills"):
            ledger.paper_fill(dataclasses.replace(order(1), state=state, state_reason="x"),
                              QUOTES[1], SNAPSHOT)
    with pytest.raises(ledger.LedgerError, match="another order"):
        ledger.paper_fill(order(1), QUOTES[3], SNAPSHOT)
    short = dataclasses.replace(QUOTES[1], buy=Amount(QUOTES[1].min_buy.raw - 1, 18,
                                                      QUOTES[1].buy.asset))
    with pytest.raises(ledger.LedgerError, match="minimum"):
        ledger.paper_fill(order(1), short, SNAPSHOT)


def test_a_fill_has_a_cash_leg_and_each_mark_values_its_own_leg():
    fill = filled(1)
    with pytest.raises(ledger.LedgerError, match="cash leg"):
        dataclasses.replace(fill, cash_asset=ETH)
    with pytest.raises(ledger.LedgerError, match="USD mark"):
        dataclasses.replace(fill, gave_mark=fill.got_mark)
    with pytest.raises(ledger.LedgerError, match="positive"):
        dataclasses.replace(fill, got=Amount(0, 18, fill.got.asset))


# --- P9: which book --------------------------------------------------------------------------

def test_each_event_belongs_to_one_book():
    fill = filled(1)
    live = dataclasses.replace(fill, mode=ExecutionMode.LIVE)
    opening = ledger.Opening("paper", Amount(200_000_000, 6, USDG), usd_mark(USDG, USDG_MARK))
    fee = ledger.Fee("real", Amount(1_000, 6, USDG), usd_mark(USDG, USDG_MARK), "venue fee")
    assert [ledger.book_of(e) for e in (fill, live, opening, fee,
                                         ledger.Inference("risk", Decimal("0.1")))] == [
        "paper", "real", "paper", "real", "real"]
    with pytest.raises(ValueError, match="a book is paper or real"):
        ledger.Opening("blended", opening.amount, opening.mark)
    with pytest.raises(ledger.LedgerError):
        ledger.book_of("a string")
