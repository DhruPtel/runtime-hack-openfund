"""Every limit, defined once (units 3.1 to 3.6).

This is the one module that compares a quantity with a limit read from config
(CODEBASE §3; PLAN §2 invariant 4). Two kinds of code use it:
  - **the code that shapes a decision:** the aggregator and the planner. They
    call this module to apply a limit, so a target never passes the position
    limit and a buy is never funded from below the cash floor;
  - **the code that checks one:** the risk agent now, and the treasurer at 4.4.
    Both call the same gate functions on the same plan.

**Money is `core/cash.py`'s** (since the 3.8 sweep). What an order is worth and
what cash orders leave are defined there, and this module calls it. The planner
funds and sizes with the same two functions, so a plan cannot break the floor
it is judged on.

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
from typing import Any, Iterable, Mapping, Sequence

from . import cash

RULE_QUORUM = "quorum"
RULE_TRADEABLE = "tradeable"        # the snapshot's status: staleness, divergence tier, quote at build
RULE_PRICED = "priced"              # a sell: the snapshot holds a usable mark to value what is sold
RULE_MANDATE = "mandate"            # the asset is one the mandate allows, on its chain, not revoked
RULE_ORDER_SIZE = "order-size"      # at most the mandate's per-trade limit
RULE_QUOTE = "quote"                # a fresh quote for this order, judged by bankr_quote.tradeability
RULE_POSITION = "position-weight"   # a buy leaves the position at most the position limit
RULE_CASH_FLOOR = "cash-floor"      # the plan leaves at least the cash floor
RULE_TURNOVER = "turnover"          # the plan trades at most turnover_max_bps of the NAV
RULE_CONTEXT_BUDGET = "context-budget"  # risk's whole bundle fits the budget (invariant 3)


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


def _whole(config: Mapping[str, Any], name: str) -> int | None:
    value = _number(config, name)
    if value is not None and value != value.to_integral_value():
        raise ValueError(f"{name} is a whole number")
    return None if value is None else int(value)


@dataclass(frozen=True)
class Limits:
    """Every Phase 3 limit, read once from `config/thresholds.json` and, for the
    per-trade limit, `config/mandate.json`. None is unresolved. Weights are
    fractions of the paper NAV; money is USD."""

    quorum_min_analysts: int | None
    max_position_weight: Decimal | None
    cash_floor_usd: Decimal | None
    min_order_usd: Decimal | None
    max_trade_usd: Decimal | None
    turnover_max_bps: Decimal | None
    context_budget_tokens: int | None

    @classmethod
    def from_config(cls, thresholds: Mapping[str, Any],
                    mandate: Mapping[str, Any] | None = None,
                    models: Mapping[str, Any] | None = None) -> "Limits":
        """Without a mandate or the models file, their limits are unresolved and block."""
        return cls(quorum_min_analysts=_whole(thresholds, "quorum_min_analysts"),
                   max_position_weight=_number(thresholds, "max_position_weight"),
                   cash_floor_usd=_number(thresholds, "cash_floor_usd"),
                   min_order_usd=_number(thresholds, "min_order_usd"),
                   max_trade_usd=_number(mandate or {}, "max_trade_usd"),
                   turnover_max_bps=_number(thresholds, "turnover_max_bps"),
                   context_budget_tokens=_whole(models or {}, "context_budget_tokens"))


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


# --- the limits the planner applies (3.3, one definition of cash since the 3.8 sweep) ---------

def fund(cash_usd: Decimal, proceeds_usd: Decimal, wanted_usd: Decimal,
         limits: Limits) -> Decimal | None:
    """The share, from 0 to 1, of the wanted buys that cash can pay for without
    going below the floor. `proceeds_usd` is what the plan's sells are worth, by
    `cash.worth`, the same measure the floor is judged on. None when the floor is
    unresolved, and then no buy is funded."""
    floor_usd = limits.cash_floor_usd
    if floor_usd is None:
        return None
    if wanted_usd <= 0:
        return Decimal(1)
    spare = cash_usd + proceeds_usd - floor_usd
    if spare <= 0:
        return Decimal(0)
    if wanted_usd <= spare:
        return Decimal(1)
    return spare / wanted_usd


def split(worth_usd: Decimal, limits: Limits) -> int | None:
    """How many orders a move worth this much becomes: the fewest that keep each
    within the per-trade limit, split evenly. A move under the minimum order is
    dust and becomes none. None when either limit is unresolved."""
    size, least = limits.max_trade_usd, limits.min_order_usd
    if size is None or least is None:
        return None
    if worth_usd < least:
        return 0
    whole, rest = divmod(worth_usd, size)
    return int(whole) + (1 if rest else 0)


# --- the gate array (3.4) -----------------------------------------------------------------------
#
# Each gate reads the plan as written, and recomputes from it what it checks:
# the book's values, each order's dollars, and the quote's own amounts. It never
# trusts a figure the planner derived.

BPS_PER_WHOLE = Decimal(10_000)


def tradeable(entry: Mapping[str, Any] | None) -> Gate:
    """The snapshot's own verdict on the asset. It is where feed staleness (1.3),
    the divergence tier (1.4) and the build-time quote (1.5) were judged, each by
    its own named function; this gate reads what they decided."""
    if entry is None:
        return Gate(RULE_TRADEABLE, None, "the asset is not in the snapshot")
    status = entry.get("status") or {}
    if status.get("value") == "tradeable":
        return Gate(RULE_TRADEABLE, True, "tradeable in the snapshot: every rule passed")
    return Gate(RULE_TRADEABLE, False, f"the snapshot says {status.get('value')}: "
                                       f"{status.get('reason')}")


def mandate_in_force(order: Mapping[str, Any], mandate: Mapping[str, Any]) -> Gate:
    """The mandate is not revoked, and the order is on its chain. Spend authority,
    not a market check, so it holds for a sell as for a buy."""
    if mandate.get("revoked") is not False:
        return Gate(RULE_MANDATE, False if mandate.get("revoked") else None,
                    f"the mandate's revoked flag is {mandate.get('revoked')!r}")
    asset = order["asset"]
    if asset["chain_id"] != mandate.get("chain_id"):
        return Gate(RULE_MANDATE, False, f"chain {asset['chain_id']} is not the mandate's "
                                         f"{mandate.get('chain_id')}")
    return Gate(RULE_MANDATE, True, "the mandate is in force on this chain")


def mandate_allows(order: Mapping[str, Any], mandate: Mapping[str, Any]) -> Gate:
    """A buy: the asset is one the mandate names, on the mandate's chain, and the
    mandate is not revoked."""
    allowed = mandate.get("allowed_assets")
    if not allowed:
        return Gate(RULE_MANDATE, None, "the mandate names no allowed assets: unresolved, "
                                        "and it blocks")
    in_force = mandate_in_force(order, mandate)
    if not in_force.passes:
        return in_force
    asset = order["asset"]
    if asset["address"].lower() not in {a["address"].lower() for a in allowed}:
        return Gate(RULE_MANDATE, False, f"{asset['symbol']} {asset['address']} is not an asset "
                                         "the mandate allows")
    return Gate(RULE_MANDATE, True, f"{asset['symbol']} is allowed by the mandate")


def order_size(usd: Decimal, limits: Limits) -> Gate:
    size = limits.max_trade_usd
    if size is None:
        return _unresolved(RULE_ORDER_SIZE, "max_trade_usd")
    if usd > size:
        return Gate(RULE_ORDER_SIZE, False, f"${usd} exceeds the per-trade limit of ${size}")
    return Gate(RULE_ORDER_SIZE, True, f"${usd} within the per-trade limit of ${size}")


def _amount(canonical: Mapping[str, Any]) -> tuple[str, int]:
    return canonical["asset"]["address"].lower(), int(canonical["raw"])


def fresh_quote(order: Mapping[str, Any]) -> Gate:
    """The fresh quote taken for this order, as `adapters/bankr_quote.tradeability`
    judged it when the plan was written: size, age and signed impact, each named
    there. This gate first checks that the quote is for this order."""
    quote = order.get("quote")
    if quote is None:
        return Gate(RULE_QUOTE, None, "no fresh quote was taken for this order")
    observation = quote.get("observation") or {}
    value = observation.get("value")
    if value is None or observation.get("status") != "ok":
        verdict = quote.get("tradeable") or {}
        return Gate(verdict.get("rule") or RULE_QUOTE,
                    False if verdict.get("value") is False else None,
                    f"no quote: {observation.get('status')}: {observation.get('detail')}")
    sold, bought = _amount(value["sell"]), value["buy"]["asset"]["address"].lower()
    asked = (order["sell"]["address"].lower(),
             int(Decimal(order["sell"]["amount"]).scaleb(order["sell"]["decimals"])))
    if sold != asked or bought != order["buy"]["address"].lower():
        return Gate(RULE_QUOTE, False, "the quote is for another order: it sells "
                                       f"{sold[1]} of {sold[0]} for {bought}")
    verdict = quote.get("tradeable") or {}
    if verdict.get("value") is True:
        return Gate(RULE_QUOTE, True, verdict.get("reason") or "tradeable")
    return Gate(verdict.get("rule") or RULE_QUOTE, verdict.get("value"),
                verdict.get("reason") or "the quote's verdict was not recorded")


def priced(order: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Gate:
    """A sell: the snapshot holds a usable mark for what is sold, so the sale can be
    valued. With none, the sale is undetermined, and it blocks."""
    try:
        mark = cash.mark_of(snapshot, order["sell"]["address"])
    except cash.NoMark as missing:
        return Gate(RULE_PRICED, None, f"no price to value the sale: {missing}")
    return Gate(RULE_PRICED, True, f"valued at its mark, "
                                   f"{Decimal(mark.raw).scaleb(-mark.decimals)} USD")


def sell_quote(order: Mapping[str, Any]) -> Gate:
    """A sell: a fresh quote for this order at the size it sells. The quote's own
    verdict from `bankr_quote.tradeability` is read, as for a buy, except that its
    impact is not a condition of selling. That verdict checks impact last, so an
    `impact` refusal means the quote, its size and its age all passed."""
    verdict = fresh_quote(order)
    if verdict.passes or verdict.rule != "impact":
        return verdict
    return Gate(RULE_QUOTE, True, "quoted at the size asked, within the age limit; impact "
                                  f"is not a condition of selling ({verdict.reason})")


def position_weight(after: Decimal, side: str, limits: Limits) -> Gate:
    """A buy may not leave a position past the limit. A sell only lowers one."""
    if side == "sell":
        return Gate(RULE_POSITION, True, "a sell lowers the position")
    limit = limits.max_position_weight
    if limit is None:
        return _unresolved(RULE_POSITION, "max_position_weight")
    if after > limit:
        return Gate(RULE_POSITION, False, f"the position would be {after:.6f} of the NAV, past "
                                          f"the limit of {limit}")
    return Gate(RULE_POSITION, True, f"the position would be {after:.6f} of the NAV, within "
                                     f"{limit}")


def cash_floor(cash_after_usd: Decimal, limits: Limits) -> Gate:
    floor_usd = limits.cash_floor_usd
    if floor_usd is None:
        return _unresolved(RULE_CASH_FLOOR, "cash_floor_usd")
    if cash_after_usd < floor_usd:
        return Gate(RULE_CASH_FLOOR, False, f"the plan leaves ${cash_after_usd:.2f} of paper cash, "
                                            f"below the floor of ${floor_usd}")
    return Gate(RULE_CASH_FLOOR, True, f"the plan leaves ${cash_after_usd:.2f} of paper cash, at "
                                       f"least the floor of ${floor_usd}")


def turnover(traded_usd: Decimal, nav_usd: Decimal, limits: Limits) -> Gate:
    most = limits.turnover_max_bps
    if most is None:
        return _unresolved(RULE_TURNOVER, "turnover_max_bps")
    allowed = nav_usd * most / BPS_PER_WHOLE
    if traded_usd > allowed:
        return Gate(RULE_TURNOVER, False, f"${traded_usd} traded, past {most} bps of the NAV "
                                          f"(${allowed:.2f})")
    return Gate(RULE_TURNOVER, True, f"${traded_usd} traded, within {most} bps of the NAV "
                                     f"(${allowed:.2f})")


def context_budget(tokens: int, limits: Limits) -> Gate:
    """Risk's whole bundle, as `core/context.measure` counts it, fits the budget.
    Over it the cycle vetoes; nothing is summarized to make it fit (PLAN §2
    invariant 3)."""
    budget = limits.context_budget_tokens
    if budget is None:
        return _unresolved(RULE_CONTEXT_BUDGET, "context_budget_tokens")
    if tokens > budget:
        return Gate(RULE_CONTEXT_BUDGET, False, f"about {tokens} tokens, over the budget of "
                                                f"{budget}: veto, never a summary")
    return Gate(RULE_CONTEXT_BUDGET, True, f"about {tokens} tokens, within the budget of {budget}")


def _worth(order: Mapping[str, Any], snapshot: Mapping[str, Any]) -> Decimal | None:
    """What the order sells, or None when that cannot be known: no mark, or an
    amount the asset's decimals cannot hold. None blocks; it never raises."""
    try:
        return cash.order_worth(order, snapshot)
    except (cash.NoMark, ValueError, KeyError, TypeError):
        return None


def evaluate(plan: Mapping[str, Any], *, snapshot: Mapping[str, Any],
             mandate: Mapping[str, Any], limits: Limits, reported: int,
             extra: Sequence[Gate] = ()) -> dict[str, Any]:
    """Every gate over a written plan. The risk agent calls this (3.5), and the
    treasurer will call it again before it submits (4.4).

    **Buying into an asset and exiting one are different risks** (the operator's
    decision on the sweep's S8). A buy passes every check: tradeable in the
    snapshot, which holds identity, markability, the corroborator line and
    divergence; allowed by the mandate; the order size; the fresh quote's full
    verdict of size, age and impact; and the position limit. A sell needs a price
    to value what it sells, and a fresh quote at its size, with the mandate in
    force and the order size, which are spend authority. It does not need the
    asset to be tradeable, allowed for buying, or cheap to exit, so a position the
    snapshot no longer calls tradeable can still be sold.

    Every money figure is what an order sells, at the snapshot's mark
    (`cash.order_worth`), never the planner's label. An order is cleared only when
    every one of its gates and every plan-level gate passes. False refuses and
    None blocks, alike. `extra` carries plan-level gates measured outside the
    plan, such as the context budget (3.6).

    **The cash floor is not judged here.** It is judged by `settle`, on the orders
    actually approved, once these gates and the risk vote have spoken (R1)."""
    entries = {a["asset"]["address"].lower(): a for a in snapshot["assets"]}
    book = plan["book"]
    nav = Decimal(book["nav_usd"])
    values = {a.lower(): Decimal(p["value_usd"]) for a, p in book["positions"].items()}
    worths = {order["index"]: _worth(order, snapshot) for order in plan["orders"]}
    traded = Decimal(0)
    for order in plan["orders"]:
        value = worths[order["index"]] or Decimal(0)
        address = order["asset"]["address"].lower()
        values[address] = values.get(address, Decimal(0)) + (
            value if order["side"] == "buy" else -value)
        traded += value

    plan_gates = [quorum(reported, limits), turnover(traded, nav, limits), *extra]
    plan_clear = all(g.passes for g in plan_gates)
    orders = []
    for order in plan["orders"]:
        address = order["asset"]["address"].lower()
        value = worths[order["index"]]
        size = (order_size(value, limits) if value is not None else
                Gate(RULE_ORDER_SIZE, None, "what the order sells cannot be valued: no mark, "
                                            "or an amount its asset cannot hold"))
        if order["side"] == "sell":  # an exit: a price and a fresh quote at its size
            own = [priced(order, snapshot), mandate_in_force(order, mandate), size,
                   sell_quote(order)]
        else:  # a buy keeps every check
            own = [tradeable(entries.get(address)), mandate_allows(order, mandate), size,
                   fresh_quote(order),
                   position_weight(values[address] / nav, order["side"], limits)]
        cleared = plan_clear and all(g.passes for g in own)
        blocking = [g.rule for g in [*own, *plan_gates] if not g.passes]
        orders.append({"index": order["index"], "symbol": order["asset"]["symbol"],
                       "cleared": cleared, "blocked_by": blocking,
                       "gates": [g.as_dict() for g in own]})
    return {"plan": [g.as_dict() for g in plan_gates], "plan_clear": plan_clear,
            "orders": orders, "turnover_usd": format(traded, "f")}


def settle(plan: Mapping[str, Any], approved: Iterable[int], *,
           snapshot: Mapping[str, Any], limits: Limits) -> tuple[list[int], list[int], Gate]:
    """The cash floor, on the orders actually approved (R1): after the gates and the
    risk vote. While the approved orders would leave less than the floor, the last
    approved buy is dropped. A sell is never dropped: it raises cash. Returns the
    orders still approved, the buys dropped, and the floor's verdict on what is left.

    With the floor unresolved, every buy is dropped: null blocks."""
    orders = {o["index"]: o for o in plan["orders"]}
    kept = sorted(i for i in approved if i in orders)
    dropped: list[int] = []
    start = Decimal(plan["book"]["cash_usd"])
    while True:
        left = cash.cash_after(start, [orders[i] for i in kept], snapshot)
        verdict = cash_floor(left, limits)
        buys = [i for i in kept if orders[i]["side"] == "buy"]
        if verdict.passes or not buys:
            return kept, dropped, verdict
        kept.remove(buys[-1])
        dropped.append(buys[-1])
