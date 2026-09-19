"""The mandate: what the operator authorized the treasurer to do (unit 4.1).

`load` reads `config/mandate.json` and refuses it unless every field the treasurer
relies on is there: the chain, the wallet, the per-trade limit, the allowed assets,
the revoked flag, and the operator's approval. A null or placeholder approval refuses,
as the provisional mandate of 3.4 did. `in_force` refuses it at a moment it is not in
force: revoked or expired.

What the mandate allows is judged by `core/gates.py`, the one module that compares
anything with a limit:
- `mandate_approved` and `mandate_term`: approved, not revoked, not expired;
- `mandate_legs` (S10): every leg an order trades, not only its label;
- `mandate_in_force`: the order's chain;
- `order_size`: the per-trade limit, on what the order sells;
- `live_budget`: the cumulative live budget, null until Phase 5, which blocks a live
  order and never a paper one.
This module only loads and refuses. It never compares a limit itself.

Minimal (SIMPLIFICATION 4.1): approvals are not hashed and replayed, versions are not
diffed, and cumulative use is not tracked. Each decision's record carries the
mandate's sha256, and each recorded cycle a copy of it (3.9).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Mapping

from fund import config
from fund.core import gates
from fund.core.types import Instant

#: What the treasurer relies on. Null refuses: a missing number is never a default.
REQUIRED = ("chain_id", "execution_wallet", "max_trade_usd", "allowed_assets", "revoked",
            *gates.APPROVAL)


class MandateError(ValueError):
    """The mandate cannot authorize anything: the reason is named."""


def validated(mandate: Mapping[str, Any]) -> Mapping[str, Any]:
    """The mandate, if it is complete and approved. Otherwise refused by name."""
    for name in REQUIRED:
        if mandate.get(name) is None:
            raise MandateError(f"the mandate's {name} is null")
    if type(mandate["chain_id"]) is not int:
        raise MandateError("the mandate's chain_id is a whole number")
    if type(mandate["revoked"]) is not bool:
        raise MandateError("the mandate's revoked flag is true or false")
    assets = mandate["allowed_assets"]
    if not isinstance(assets, list) or not assets or not all(
            isinstance(a, dict) and isinstance(a.get("address"), str) for a in assets):
        raise MandateError("the mandate's allowed_assets is a list of assets by address")
    approved = gates.mandate_approved(mandate)
    if not approved.passes:
        raise MandateError(approved.reason)
    return mandate


def load(config_dir: Path | None = None) -> Mapping[str, Any]:
    """`mandate.json` from `config_dir` (`config/` without one), refused unless it is
    complete and approved."""
    return validated(config.load_json("mandate.json", config_dir))


def in_force(mandate: Mapping[str, Any], at: Instant) -> Mapping[str, Any]:
    """The mandate, if it is in force at `at`. Otherwise refused by name."""
    term = gates.mandate_term(validated(mandate), at)
    if not term.passes:
        raise MandateError(term.reason)
    return mandate
