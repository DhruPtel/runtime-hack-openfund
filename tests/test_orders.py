"""Unit 4.0: an order's moves (P1), its identity (P2), and a refusal (P12).

An H unit: the state machine is what stops a double spend. Each rule here was broken
in a copy and a test failed (LOGS, 4.0).
"""

from __future__ import annotations

import itertools
import uuid

import pytest

from fund.core import orders
from fund.core.types import Amount, AssetId, ChainAddress, ExecutionMode, Order, OrderState
from test_types import swap_execution, swap_order

CHAIN = 4663
USDG = AssetId(CHAIN, "0x5fc5360d0400a0fd4f2af552add042d716f1d168")
GME = AssetId(CHAIN, "0x1b0e319c6a659f002271b69db8a7df2f911c153e")
WALLET = ChainAddress(CHAIN, "0x93faecde3c88a713e1edddf417c02c326889a3da")
DECISION = "732161ded89aee8367509069809b34e4fec901035a83011ebbf839d1bbe126fc"  # the exit run

P, S, U, C, F, R = (OrderState.PREPARED, OrderState.SUBMITTED, OrderState.UNKNOWN,
                    OrderState.CONFIRMED, OrderState.FAILED, OrderState.REFUSED)


def prepared(index: int = 1) -> Order:
    return Order(order_id=orders.order_id(DECISION, index),
                 idempotency_key=orders.idempotency_key(DECISION, index),
                 mode=ExecutionMode.PAPER, wallet=WALLET, sell=Amount(18_751_447, 6, USDG),
                 buy_asset=GME, min_buy=Amount(790_872_857_148_259_432, 18, GME), state=P)


def moved(order: Order, to: OrderState) -> Order:
    """A legal move with what `Order` requires of the state it reaches."""
    return orders.transition(order, to, reason=None if to in (S, C) else f"constructed: {to.value}")


# --- P1: the moves --------------------------------------------------------------------------

def test_the_table_is_plan_4s_with_the_refusal():
    assert {state: set(to) for state, to in orders.MOVES.items()} == {
        P: {S, R}, S: {C, F, U}, U: {C, F, S}, C: set(), F: set(), R: set()}
    assert set(orders.MOVES) == set(OrderState)


def test_every_move_outside_the_table_is_refused_by_name():
    reached = {P: prepared()}
    for state in (S, U):
        reached[state] = moved(reached[P] if state is S else reached[S], state)
    reached[C], reached[F], reached[R] = moved(reached[S], C), moved(reached[S], F), moved(reached[P], R)
    for start, to in itertools.product(OrderState, OrderState):
        if to in orders.MOVES[start]:
            assert moved(reached[start], to).state is to
        else:
            with pytest.raises(orders.IllegalMove, match=f"{start.value} → {to.value}"):
                orders.transition(reached[start], to, reason="constructed")


def test_an_unknown_order_is_sent_again_under_the_same_key():
    """PLAN §4: never a new key to escape uncertainty. Every path through the table
    keeps the order's id and key."""
    order = prepared()
    for to in (S, U, S, U, S, C):
        order = moved(order, to)
        assert (order.order_id, order.idempotency_key) == (
            orders.order_id(DECISION, 1), orders.idempotency_key(DECISION, 1))
    assert order.state is C


def test_what_a_state_requires_is_still_required_after_a_move():
    with pytest.raises(ValueError):
        orders.transition(moved(prepared(), S), U)  # unknown must say why
    live = swap_order(state=S)
    with pytest.raises(ValueError):
        orders.transition(live, C)  # a confirmed live order carries its evidence
    assert orders.transition(live, C, execution=swap_execution()).state is C


# --- P12: a refusal -------------------------------------------------------------------------

def test_the_chokepoint_refuses_a_prepared_order_with_its_reasons_and_that_is_final():
    refused = orders.transition(prepared(), R, reason="snapshot-age: 11 hours old")
    assert refused.state is R and refused.state_reason.startswith("snapshot-age")
    with pytest.raises(ValueError):
        orders.transition(prepared(), R)  # a refusal names why
    for to in OrderState:
        with pytest.raises(orders.IllegalMove):
            orders.transition(refused, to, reason="constructed")


def test_only_a_prepared_order_can_be_refused_since_anything_later_may_have_been_sent():
    sent = moved(prepared(), S)
    for start in (sent, moved(sent, U)):
        with pytest.raises(orders.IllegalMove):
            orders.transition(start, R, reason="constructed")


def test_a_refused_order_carries_no_chain_evidence():
    with pytest.raises(ValueError):
        Order(**{**{f: getattr(swap_order(state=U, reason="x"), f)
                    for f in ("order_id", "idempotency_key", "mode", "wallet", "sell",
                              "buy_asset", "min_buy")},
                 "state": R, "state_reason": "constructed", "execution": swap_execution()})


# --- P2: identity ---------------------------------------------------------------------------

def test_an_orders_id_and_key_derive_from_the_decision_and_index_alone():
    assert orders.order_id(DECISION, 3) == f"{DECISION}/3"
    assert orders.idempotency_key(DECISION, 3) == orders.idempotency_key(DECISION, 3)
    keys = {orders.idempotency_key(d, i) for d in (DECISION, "0" * 64) for i in (1, 2, 3)}
    assert len(keys) == 6
    assert orders.idempotency_key(DECISION, 1) == "09511981-1d83-5a03-8e8b-f630f4651d3f"


def test_the_key_is_uuid_shaped_as_the_one_bankr_deduplicated():
    key = orders.idempotency_key(DECISION, 1)
    assert str(uuid.UUID(key)) == key and len(key) == 36  # F0.10.1 sent a uuid4


@pytest.mark.parametrize("decision,index", [
    (DECISION.upper(), 1), (DECISION[:-1], 1), ("", 1), (None, 1),
    (DECISION, 0), (DECISION, -1), (DECISION, True), (DECISION, 1.0), (DECISION, "1")])
def test_an_id_from_anything_but_a_decision_id_and_a_plan_index_is_refused(decision, index):
    with pytest.raises(ValueError):
        orders.order_id(decision, index)
    with pytest.raises(ValueError):
        orders.idempotency_key(decision, index)

