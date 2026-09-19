"""Every limit, defined once (units 3.1 to 3.6).

This is the one module that compares a quantity with a limit read from config
(CODEBASE §3; PLAN §2 invariant 4). Two kinds of code use it:
  - **the code that shapes a decision:** the aggregator and the planner. They
    call this module to apply a limit, so a target never passes the position
    limit and a buy is never funded from below the cash floor;
  - **the code that checks one:** the risk agent now, and the treasurer at 4.4.
    Both call the same gate functions on the same plan.

Nothing else defines a limit. A limit's number lives in `config/`, is loaded
into `Limits`, and never appears as a literal.

**Three-valued, and null blocks.** Every gate returns a `Gate` whose value is
True, False or None, with the rule it tested named. A limit that is null in
config is unresolved, and every gate that reads it answers None, which blocks
(PLAN §2 invariant 5). A missing number is never a default.

**The three older comparisons are consumed, not moved** (minimal 3.4,
`planning/SIMPLIFICATION.md`). Feed staleness (`adapters/chain_4663.freshness`,
1.3), the divergence tier (`core/valuation.cross_check`, 1.4), and quote age
with signed impact (`adapters/bankr_quote.tradeability`, 1.5) each stay where
the plan put them. This module reads the verdicts they produce and never
repeats their arithmetic:
  - the first two decided the asset's status when the snapshot was built;
  - the third judges each fresh quote where it is fetched, and the planner
    records its verdict.
`core/` imports nothing from `adapters/`, so this is the only way for it to
use them. Each limit is still defined once. It is no longer true that every
limit sits in this one module; that is 3.4's full version, the sweep.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping

RULE_QUORUM = "quorum"


def _number(config: Mapping[str, Any], name: str) -> Decimal | None:
    """A limit from config: an int or decimal text, never a float. Null is None,
    which blocks every gate that reads it."""
    raw = config.get(name)
    if raw is None:
        return None
    if isinstance(raw, bool) or isinstance(raw, float):
        raise TypeError(f"{name} must be an integer or decimal text, never a float")
    if type(raw) is int or isinstance(raw, str):
        return Decimal(raw)
    raise TypeError(f"{name} is {type(raw).__name__}, not a number")


@dataclass(frozen=True)
class Limits:
    """Every Phase 3 limit, read once from `config/thresholds.json`. None is
    unresolved. Weights are fractions of the paper NAV; money is USD."""

    quorum_min_analysts: int | None
    max_position_weight: Decimal | None
    cash_floor_usd: Decimal | None

    @classmethod
    def from_config(cls, thresholds: Mapping[str, Any]) -> "Limits":
        quorum = _number(thresholds, "quorum_min_analysts")
        if quorum is not None and quorum != quorum.to_integral_value():
            raise ValueError("quorum_min_analysts is a whole number of seats")
        return cls(quorum_min_analysts=None if quorum is None else int(quorum),
                   max_position_weight=_number(thresholds, "max_position_weight"),
                   cash_floor_usd=_number(thresholds, "cash_floor_usd"))


@dataclass(frozen=True)
class Gate:
    """One gate's verdict: True passes, False refuses, None is undetermined and
    blocks. `rule` names what was tested."""

    rule: str
    value: bool | None
    reason: str

    @property
    def passes(self) -> bool:
        return self.value is True

    def as_dict(self) -> dict[str, Any]:
        return {"rule": self.rule, "value": self.value, "reason": self.reason}


def _unresolved(rule: str, name: str) -> Gate:
    return Gate(rule, None, f"{name} is null: unresolved, and it blocks")


# --- the limits the aggregator applies (3.1) -------------------------------------------------

def quorum(reported: int, limits: Limits) -> Gate:
    """Enough seats reported for the cycle to decide. A report that abstains
    with NO CALLS has reported; a seat that failed has not."""
    need = limits.quorum_min_analysts
    if need is None:
        return _unresolved(RULE_QUORUM, "quorum_min_analysts")
    if reported < need:
        return Gate(RULE_QUORUM, False, f"{reported} seat(s) reported, below the quorum of {need}")
    return Gate(RULE_QUORUM, True, f"{reported} seat(s) reported, at least the quorum of {need}")


def raise_by(current: Decimal, step: Decimal, limits: Limits) -> Decimal | None:
    """How far a buy may raise a position: its step, but never past the position
    limit. A position already at or past the limit is not raised. None when the
    limit is unresolved."""
    limit = limits.max_position_weight
    if limit is None:
        return None
    room = limit - current
    if room <= 0:
        return Decimal(0)
    return step if step <= room else room


def cut_by(current: Decimal, step: Decimal) -> Decimal:
    """How far a sell may cut a position: its step, but never below zero."""
    return step if step <= current else current


def funded_share(cash_weight: Decimal, released: Decimal, wanted: Decimal, nav_usd: Decimal,
                 limits: Limits) -> Decimal | None:
    """The share, from 0 to 1, of the wanted increases that cash can pay for
    without going below the cash floor. `released` is what the cycle's cuts free.
    None when the floor is unresolved."""
    floor_usd = limits.cash_floor_usd
    if floor_usd is None:
        return None
    if wanted <= 0:
        return Decimal(1)
    spare = cash_weight + released - floor_usd / nav_usd
    if spare <= 0:
        return Decimal(0)
    if wanted <= spare:
        return Decimal(1)
    return spare / wanted
