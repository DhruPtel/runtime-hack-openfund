"""Orders: which states they move through, and who they are. One definition each
(unit 4.0: P1, P2 and P12, `planning/PHASE-4.md`).

**P1, the moves.** An order moves only as `MOVES` allows, through `transition`, and
any other move is refused by name:

    prepared  → submitted, or refused
    submitted → confirmed, failed or unknown
    unknown   → confirmed or failed, or submitted again with the same key
    confirmed, failed and refused are final.

`store/orders.py` (4.3) persists what `transition` returns, and never decides a state
itself. That a state is written before the act it names is the store's and the
executor's rule to keep; this module says which moves exist.

**P12, a refusal.** The chokepoint (4.4) admits an order after it is written
`prepared`. One it refuses moves to `refused`, with its reasons. Nothing was sent, so
no key was spent and no fill can come. `failed` stays what PLAN §4 says: an evidenced
failure after sending.

**P2, identity.** An order's id and its idempotency key derive from the decision id
and the order's index in the signed plan, and from nothing else. So a restart
derives the same key, and an `unknown` order is sent again under it: no move changes
either, and there is no way to mint a new key to escape uncertainty (PLAN §4). The
key is UUID-shaped, like the one Bankr deduplicated at 0.10 (F0.10.1). That another
UUID is deduplicated the same way is inferred, not measured.

Pure and stdlib-only, like the rest of `core/`.
"""

from __future__ import annotations

import dataclasses
import re
import uuid
from types import MappingProxyType
from typing import Mapping

from .types import Execution, Order, OrderState

P, S, U, C, F, R = (OrderState.PREPARED, OrderState.SUBMITTED, OrderState.UNKNOWN,
                    OrderState.CONFIRMED, OrderState.FAILED, OrderState.REFUSED)

#: Every move an order may make (P1, P12). Anything else is refused.
MOVES: Mapping[OrderState, frozenset[OrderState]] = MappingProxyType({
    P: frozenset({S, R}),
    S: frozenset({C, F, U}),
    U: frozenset({C, F, S}),
    C: frozenset(), F: frozenset(), R: frozenset(),
})

#: The namespace every idempotency key is derived in. Fixed: changing it changes
#: every key, and a restart would send an unknown order under a new one.
KEYS = uuid.uuid5(uuid.NAMESPACE_URL, "openfund:orders:idempotency")

_DECISION = re.compile(r"^[0-9a-f]{64}$")


class IllegalMove(ValueError):
    """A move `MOVES` does not allow, named by its two states."""


def transition(order: Order, to: OrderState, *, reason: str | None = None,
               execution: Execution | None = None) -> Order:
    """The order in state `to`, if `MOVES` allows the move, and otherwise refused by
    name. Only the state, its reason and the chain evidence change: the order's id
    and key never do. `Order` itself requires a reason for unknown, failed and
    refused, and evidence for a confirmed live order."""
    allowed = MOVES[order.state]
    if to not in allowed:
        raise IllegalMove(
            f"order {order.order_id}: {order.state.value} → {to.value} is not a move; from "
            f"{order.state.value} an order may move to "
            f"{', '.join(sorted(s.value for s in allowed)) or 'nothing: it is final'}")
    return dataclasses.replace(order, state=to, state_reason=reason, execution=execution)


def order_id(decision_id: str, index: int) -> str:
    """The order at `index` in the signed plan of decision `decision_id`."""
    if not isinstance(decision_id, str) or not _DECISION.match(decision_id):
        raise ValueError("a decision id is 64 lowercase hex characters, its record's sha256")
    if type(index) is not int or index <= 0:
        raise ValueError(f"an order's index is its plan index, a whole number from one: {index!r}")
    return f"{decision_id}/{index}"


def idempotency_key(decision_id: str, index: int) -> str:
    """The key Bankr deduplicates the order's submission by, sent as `idempotencyKey`.
    The same order always has the same key."""
    return str(uuid.uuid5(KEYS, order_id(decision_id, index)))

