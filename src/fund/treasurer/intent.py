"""A signed decision, turned into the orders it approved (unit 4.2).

`intents` takes a decision record's exact bytes and its envelope, and returns the
orders the record approved, in the plan's order, each an `Order` in state `prepared`
with its id and idempotency key from `core/orders.py` (4.0, P2). It refuses the whole
record, by name, unless:
- **it is signed by the published key** (S13): `keys.json`'s, never the key the
  envelope names (`treasurer/sign.py`);
- **the mandate is in force** when the orders are listed: approved, not revoked, not
  expired (4.1). Whether each order's legs are allowed is the chokepoint's, as every
  other check on an order is (4.4).

Nothing is sent and nothing is written here. The store writes these orders
`prepared` before anything is attempted (4.3), and the chokepoint admits or refuses
each (4.4).

Every order is a stock leg, which is paper (PLAN §13): its quote's `executable` is
null, because stock execution is location-gated. The live ETH↔USDG leg is Phase 5's.
"""

from __future__ import annotations

import json
from typing import Any, Mapping

from fund.core import orders
from fund.core.types import (
    Amount, AssetId, ChainAddress, ExecutionMode, Instant, Order, OrderState, from_canonical,
)
from fund.treasurer import mandate as mandates
from fund.treasurer import keys, sign


class IntentError(ValueError):
    """The record cannot become orders: the reason is named."""


def intents(record_bytes: bytes, envelope: Mapping[str, Any], *, public_key: str | None,
            mandate: Mapping[str, Any], at: Instant) -> list[Order]:
    """The approved orders of a signed decision, `prepared`, in the plan's order."""
    if public_key is None:
        raise IntentError("no decision-signing key is published in keys.json, so no record "
                          "authorizes")
    signed = sign.authorizes(envelope, record_bytes, public_key)
    if not signed.passes:
        raise IntentError(f"the record does not authorize: {signed.reason}")
    try:
        mandates.in_force(mandate, at)
    except mandates.MandateError as refused:
        raise IntentError(f"the mandate is not in force: {refused}") from None
    record = json.loads(record_bytes)
    chain = record["snapshot"]["block"]["chain_id"]
    if chain != mandate["chain_id"]:
        raise IntentError(f"the record is on chain {chain}, the mandate on {mandate['chain_id']}")
    wallet = ChainAddress(chain, mandate["execution_wallet"].lower())
    planned = {o["index"]: o for o in record["plan"]["orders"]}
    listed = []
    for approved in record["decision"]["approved"]:
        order = planned[approved["index"]]
        if order["quote"] is None:
            raise IntentError(f"order {order['index']} was approved with no quote")
        quote = from_canonical(json.dumps(order["quote"]["observation"]).encode()).value
        sell = order["sell"]
        listed.append(Order(
            order_id=orders.order_id(envelope["decision_id"], order["index"]),
            idempotency_key=orders.idempotency_key(envelope["decision_id"], order["index"]),
            mode=ExecutionMode.PAPER, wallet=wallet,
            sell=Amount.from_units(sell["amount"], sell["decimals"],
                                   AssetId(chain, sell["address"].lower())),
            buy_asset=AssetId(chain, order["buy"]["address"].lower()),
            min_buy=quote.min_buy, state=OrderState.PREPARED))
    return listed
