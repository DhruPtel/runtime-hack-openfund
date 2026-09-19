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


# --- P4, P5, P8: holdings and cash, from every event -----------------------------------------------

OPEN_PAPER = ledger.Opening("paper", Amount(200_000_000, 6, USDG), usd_mark(USDG, USDG_MARK))
SIX = [filled(i) for i in APPROVED]
GME = QUOTES[1].buy.asset


def sold_half_of_gme(usdg_raw: int = 9_300_000, order_id: str = "test/sell-gme") -> ledger.Fill:
    """A sell constructed for the test: half the GME order 1 bought, for 9.30 USDG."""
    return ledger.Fill(order_id=order_id, mode=ExecutionMode.PAPER,
                       gave=Amount(QUOTES[1].buy.raw // 2, 18, GME),
                       got=Amount(usdg_raw, 6, USDG), gave_mark=usd_mark(GME, mark_of("GME")),
                       got_mark=usd_mark(USDG, USDG_MARK), cash_asset=USDG)


def test_holdings_are_every_events_effect_in_raw_units():
    held = ledger.holdings([OPEN_PAPER, *SIX], book="paper")
    assert held[USDG] == Amount(200_000_000 - sum(QUOTES[i].sell.raw for i in APPROVED), 6, USDG)
    assert {a: h for a, h in held.items() if a != USDG} == {QUOTES[i].buy.asset: QUOTES[i].buy
                                                          for i in APPROVED}
    everything = ledger.Fill(order_id="test/all", mode=ExecutionMode.PAPER, gave=QUOTES[1].buy,
                             got=Amount(1, 6, USDG), gave_mark=usd_mark(GME, mark_of("GME")),
                             got_mark=usd_mark(USDG, USDG_MARK), cash_asset=USDG)
    assert GME not in ledger.holdings([OPEN_PAPER, SIX[0], everything], book="paper")


def test_a_book_never_holds_less_than_nothing_and_an_order_fills_once():
    with pytest.raises(ledger.LedgerError, match="event 1 gives"):
        ledger.holdings([OPEN_PAPER, sold_half_of_gme()], book="paper")  # no GME held yet
    with pytest.raises(ledger.LedgerError, match="event 2 fills order .*/1 a second time"):
        ledger.holdings([OPEN_PAPER, SIX[0], SIX[0]], book="paper")
    tiny = ledger.Opening("paper", Amount(1_000_000, 6, USDG), usd_mark(USDG, USDG_MARK))
    with pytest.raises(ledger.LedgerError, match="holds 1000000"):
        ledger.holdings([tiny, SIX[0]], book="paper")  # 18.75 USDG from 1 USDG


def test_cash_is_the_usdg_held_at_its_own_mark_not_a_dollar():
    amount, usd = ledger.cash_held([OPEN_PAPER, *SIX], book="paper", snapshot=SNAPSHOT)
    left = Decimal(200) - sum(units(QUOTES[i].sell) for i in APPROVED)
    assert units(amount) == left == Decimal("73.430231")
    assert usd == left * USDG_MARK == Decimal("73.42456145186449")
    # The exit run planned from $200 of paper cash and left $73.44. Held as 200 USDG,
    # the same book is worth $199.98 and leaves $73.42 (decision 2).
    assert Decimal(RECORD["plan"]["book"]["cash_usd"]) == 200
    assert ledger.cash_held([OPEN_PAPER], book="paper", snapshot=SNAPSHOT)[1] == Decimal("199.984558")


def test_inference_touches_no_holding_and_no_book_but_the_real_ones_expenses():
    spent = [ledger.Inference("price-trend", Decimal("0.260564")),
             ledger.Inference("risk", Decimal("0.099454"))]
    assert ledger.holdings([OPEN_PAPER, *spent], book="paper") == {USDG: OPEN_PAPER.amount}
    assert ledger.holdings(spent, book="real") == {}
    assert ledger.expenses(spent, book="real") == Decimal("0.360018")
    assert ledger.expenses([OPEN_PAPER, *spent], book="paper") == 0


# --- P6: average cost; a fee is never basis ----------------------------------------------------

def test_a_buy_adds_what_it_paid_and_a_sale_removes_its_share_of_the_average():
    events = [OPEN_PAPER, SIX[0]]
    paid = Decimal("18.751447") * USDG_MARK
    assert ledger.basis(events, GME, book="paper") == paid
    assert ledger.basis(events, USDG, book="paper") == Decimal("181.248553") * USDG_MARK
    half = [*events, sold_half_of_gme()]
    assert QUOTES[1].buy.raw % 2 == 0  # so half the units carry exactly half the basis
    assert ledger.basis(half, GME, book="paper") == paid / 2
    rest = [*half, sold_half_of_gme(order_id="test/sell-gme-2")]
    assert ledger.basis(rest, GME, book="paper") == 0 and GME not in ledger.holdings(rest, book="paper")


def test_a_second_buy_at_another_price_averages_and_a_part_sale_rounds_only_at_1e_30():
    second = ledger.Opening("paper", Amount(QUOTES[1].buy.raw, 18, GME), usd_mark(GME, "30"))
    events = [OPEN_PAPER, SIX[0], second]
    total = Decimal("18.751447") * USDG_MARK + units(QUOTES[1].buy) * 30
    assert ledger.basis(events, GME, book="paper") == total
    third = QUOTES[1].buy.raw * 2 // 3  # two thirds of the units: a share that does not divide
    sale = dataclasses.replace(sold_half_of_gme(), gave=Amount(third, 18, GME))
    left = ledger.basis([*events, sale], GME, book="paper")
    from fractions import Fraction
    exact = Fraction(total) * (2 * QUOTES[1].buy.raw - third) / (2 * QUOTES[1].buy.raw)
    assert abs(Fraction(left) - exact) <= Fraction(1, 2 * 10 ** 30)
    assert left.as_tuple().exponent >= -30


def test_a_fee_is_its_own_cost_never_basis_and_paying_it_disposes_at_average_cost():
    fee = ledger.Fee("paper", Amount(250_000, 6, USDG), usd_mark(USDG, USDG_MARK), "venue fee",
                     order_id=SIX[0].order_id)
    events = [OPEN_PAPER, SIX[0], fee]
    assert ledger.basis(events, GME, book="paper") == Decimal("18.751447") * USDG_MARK
    assert ledger.costs(events, book="paper") == Decimal("0.25") * USDG_MARK
    assert ledger.basis(events, USDG, book="paper") == Decimal("180.998553") * USDG_MARK
    assert ledger.realised(events, book="paper") == 0  # USDG paid at the mark it came in at


# --- P7: realised and unrealised -------------------------------------------------------------------

def test_a_sale_realises_what_it_received_less_the_basis_it_gave_up():
    events = [OPEN_PAPER, SIX[0], sold_half_of_gme()]
    received = Decimal("9.30") * USDG_MARK
    assert ledger.realised(events, book="paper") == received - Decimal("18.751447") * USDG_MARK / 2


def test_unrealised_is_each_holding_at_the_snapshots_mark_less_its_basis():
    events = [OPEN_PAPER, *SIX]
    expected = sum((units(QUOTES[i].buy) * mark_of(QUOTES[i].buy.asset)
                    - units(QUOTES[i].sell) * USDG_MARK for i in APPROVED), Decimal(0))
    assert ledger.unrealised(events, book="paper", snapshot=SNAPSHOT) == expected
    unmarked = {**SNAPSHOT, "assets": [a for a in SNAPSHOT["assets"]
                                       if a["asset"]["address"] != GME.address]}
    with pytest.raises(cash.NoMark):
        ledger.unrealised(events, book="paper", snapshot=unmarked)


def test_a_book_is_worth_what_opened_it_plus_realised_plus_unrealised_less_costs():
    """The identity every figure above must keep, per book, exactly: here with a
    sale, a fee in each book, a live round trip and inference beside it."""
    eth_open = ledger.Opening("real", Amount(460_000_000_000_000, 18, ETH), usd_mark(ETH, "2600"))
    usdg_open = ledger.Opening("real", Amount(78_742, 6, USDG), usd_mark(USDG, "0.99995"))
    sold_eth = ledger.Fill(order_id="test/eth", mode=ExecutionMode.LIVE,
                           gave=Amount(200_000_000_000_000, 18, ETH), got=Amount(525_000, 6, USDG),
                           gave_mark=usd_mark(ETH, ETH_MARK), got_mark=usd_mark(USDG, USDG_MARK),
                           cash_asset=USDG)
    gas = ledger.Fee("real", Amount(3_000_000_000_000, 18, ETH), usd_mark(ETH, ETH_MARK), "gas")
    paper_fee = ledger.Fee("paper", Amount(10_000, 6, USDG), usd_mark(USDG, USDG_MARK), "fee")
    events = [OPEN_PAPER, eth_open, *SIX, usdg_open, sold_half_of_gme(), sold_eth, gas,
              paper_fee, ledger.Inference("risk", Decimal("0.099454"))]
    for book in ledger.BOOKS:
        nav = sum((units(a) * mark_of(asset) for asset, a in
                   ledger.holdings(events, book=book).items()), Decimal(0))
        assert nav == (ledger.opened(events, book=book) + ledger.realised(events, book=book)
                       + ledger.unrealised(events, book=book, snapshot=SNAPSHOT)
                       - ledger.costs(events, book=book)), book
    assert ledger.opened(events, book="real") == Decimal("0.00046") * 2600 + Decimal("0.078742") * Decimal("0.99995")
    assert ledger.costs(events, book="real") == Decimal("0.000003") * ETH_MARK
    assert ledger.expenses(events, book="real") == Decimal("0.099454")


# --- P9: the books are never added --------------------------------------------------------------

def test_each_book_reads_only_its_own_events():
    live = dataclasses.replace(SIX[0], mode=ExecutionMode.LIVE, order_id="test/live")
    real_open = ledger.Opening("real", Amount(50_000_000, 6, USDG), usd_mark(USDG, USDG_MARK))
    events = [OPEN_PAPER, real_open, *SIX, live]
    paper, real = (ledger.holdings(events, book=b) for b in ledger.BOOKS)
    assert paper == ledger.holdings([OPEN_PAPER, *SIX], book="paper")
    assert real == ledger.holdings([real_open, live], book="real")
    assert real[GME] == QUOTES[1].buy and paper[USDG].raw + real[USDG].raw != 200_000_000


def test_every_reader_names_its_book_and_none_has_a_default():
    import inspect
    readers = [f for name, f in vars(ledger).items() if inspect.isfunction(f)
               and not name.startswith("_") and "events" in inspect.signature(f).parameters]
    assert {f.__name__ for f in readers} >= {"holdings", "cash_held", "basis", "realised",
                                             "unrealised", "opened", "costs", "expenses"}
    for reader in readers:
        book = inspect.signature(reader).parameters.get("book")
        assert book is not None and book.kind is inspect.Parameter.KEYWORD_ONLY, reader.__name__
        assert book.default is inspect.Parameter.empty, reader.__name__
    with pytest.raises(ValueError, match="a book is paper or real"):
        ledger.holdings([OPEN_PAPER], book="both")
