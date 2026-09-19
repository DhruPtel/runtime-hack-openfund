"""Unit 4.5: the paper executor, on the interface the live one will use. H.

The orders are the exit run's six, submitted, and their quotes fresh from the fake
venue. The executor sends and answers; it never books and never moves a state.
"""

from __future__ import annotations

import dataclasses
import inspect

import pytest

from fund.core import orders
from fund.core.types import Amount, ExecutionMode, Instant, OrderState
from fund.run.fake_venue import FakeVenue
from fund.treasurer import execute
from test_chokepoint import AT, SIX, SNAPSHOT, THRESHOLDS, USDG


def fresh(order):
    venue = FakeVenue(SNAPSHOT, lambda: Instant(AT.epoch_ms - 5_000))
    return execute.requote(order, venue, AT, THRESHOLDS).observation.value


def submitted(order):
    return orders.transition(order, OrderState.SUBMITTED)


def test_a_paper_order_fills_at_its_quotes_amounts_marked_paper():
    executor = execute.PaperExecutor(SNAPSHOT)
    for order in SIX:
        quote = fresh(order)
        outcome = executor.submit(submitted(order), quote)
        assert outcome.state is OrderState.CONFIRMED and outcome.execution is None
        fill = outcome.fill
        assert (fill.gave, fill.got) == (quote.sell, quote.buy)
        assert fill.mode is ExecutionMode.PAPER and fill.order_id == order.order_id


def test_a_repeat_under_the_same_key_is_the_first_outcome_not_a_second_fill():
    executor = execute.PaperExecutor(SNAPSHOT)
    order, quote = submitted(SIX[0]), fresh(SIX[0])
    first = executor.submit(order, quote)
    again = executor.submit(order, dataclasses.replace(quote, quote_id="another"))
    assert again is first


def test_a_quote_below_the_orders_minimum_fails_and_books_nothing():
    quote = fresh(SIX[0])
    short = dataclasses.replace(quote, buy=Amount(SIX[0].min_buy.raw - 1, 18, quote.buy.asset))
    outcome = execute.PaperExecutor(SNAPSHOT).submit(submitted(SIX[0]), short)
    assert outcome.state is OrderState.FAILED and outcome.fill is None
    assert "minimum" in outcome.reason


def test_the_paper_executor_never_takes_a_live_order():
    live = dataclasses.replace(submitted(SIX[0]), mode=ExecutionMode.LIVE)
    with pytest.raises(ValueError, match="paper orders only"):
        execute.PaperExecutor(SNAPSHOT).submit(live, fresh(SIX[0]))


def test_the_interface_is_the_one_the_live_executor_will_satisfy():
    """`submit(order, quote) -> Outcome`, and an Outcome carries what the live leg
    needs: confirmed with its fill and chain evidence, failed, or unknown."""
    assert list(inspect.signature(execute.PaperExecutor.submit).parameters) == [
        "self", "order", "quote"]
    assert list(inspect.signature(execute.Executor.submit).parameters) == ["self", "order", "quote"]
    assert {f.name for f in dataclasses.fields(execute.Outcome)} == {
        "state", "reason", "fill", "execution"}
    execute.Outcome(OrderState.UNKNOWN, "timeout: the live leg's case")
    with pytest.raises(ValueError):
        execute.Outcome(OrderState.CONFIRMED, "no fill")
    with pytest.raises(ValueError):
        execute.Outcome(OrderState.SUBMITTED, "not an ending")
