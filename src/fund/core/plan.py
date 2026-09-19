"""Target weights to sized orders, each carrying its fresh quote and evidence (unit 3.3).

An H unit: this is where a view becomes an amount of money. Three steps:

1. **`book`** values the paper holdings at the snapshot's Chainlink marks,
   through `core/valuation.value()`, the one place a quantity becomes USD. Cash
   is paper USD. A holding with no usable mark cannot be valued, and the planner
   refuses rather than guessing.
2. **`size`** turns each target into orders, with every dollar figure from
   `core/cash.py`, the one definition of what an order is worth and what cash
   orders leave (since the 3.8 sweep).
   - **Sells first,** since they free cash. A sell sells the units its cut is
     worth at the mark, never more than is held, and all of them when the
     target is zero.
   - **Then buys, funded only from cash above the floor plus what the sells
     are worth** (`gates.fund`), so a plan cannot break the floor it is judged
     on. A buy sells the USDG its dollars are worth at USDG's mark, rounded
     down.
   - **`gates.split`** makes each move the fewest even orders that keep each
     within the per-trade limit, judged on what the move is worth. A move worth
     less than the minimum order is dust and becomes none.
   - **Hold and silence trade nothing:** a position whose target is where it
     stands gets no order.
3. **`write`** attaches to each order the fresh quote taken for it when the plan
   was written. The snapshot's quotes are past the 60 s limit by then
   (`planning/SIMPLIFICATION.md`, Q2). Each quote arrives with the verdict
   `adapters/bankr_quote.tradeability` gave it at `judged_at`. Each order also
   carries the evidence risk reads: the mark, the corroboration, the venue's
   price and every finding.

**Quotes are fetched outside `core/`,** which does no I/O. `size` returns what
to quote, the caller quotes it and judges it, and `write` records what came
back. Each quote is kept exactly as fetched, as a canonical `Observation`, so a
replay can judge the same quote again (3.9). The only time in the plan is
`judged_at`, and the caller records it as an input.

**Not built** (minimal 3.3): reservations, dependent orders, and fills. Orders
run one at a time. The live ETH↔USDG leg is not planned here; it is Phase 5's
(operator, 2026-09-19).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import ROUND_DOWN, Decimal
from typing import Any, Mapping, Sequence

from . import cash, gates
from .aggregate import Proposal, decimal_text as _text
from .types import Amount, AssetId, Check, Instant, Observation, Price, Quote, to_canonical

CENT = Decimal("0.01")


class PlanError(Exception):
    """The book cannot be valued or sized, so no plan is written."""


def _decimal(quantity: Any) -> Decimal:
    """A Fixed, Amount or Price as an exact Decimal."""
    return Decimal(quantity.raw).scaleb(-quantity.decimals)


def _entries(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {a["asset"]["address"].lower(): a for a in snapshot["assets"]}


def _mark(snapshot: Mapping[str, Any], address: str) -> Price:
    try:
        return cash.mark_of(snapshot, address)
    except cash.NoMark as missing:
        raise PlanError(str(missing)) from None


def _cash_leg(snapshot: Mapping[str, Any]) -> tuple[AssetId, int, Price]:
    entry = next(h for h in snapshot["holdings"] if h["asset"]["kind"] == "cash")
    mark = _mark(snapshot, entry["asset"]["address"])
    return mark.base, entry["asset"]["decimals"], mark


# --- 1. the book ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class Book:
    """The paper book at the snapshot's marks. Never the wallet's real holdings."""

    nav_usd: Decimal
    cash_usd: Decimal
    holdings: Mapping[str, Amount]
    values_usd: Mapping[str, Decimal]

    @property
    def weights(self) -> dict[str, Decimal]:
        return {a: v / self.nav_usd for a, v in self.values_usd.items()}

    @property
    def cash_weight(self) -> Decimal:
        return self.cash_usd / self.nav_usd

    def as_dict(self) -> dict[str, Any]:
        return {"nav_usd": _text(self.nav_usd), "cash_usd": _text(self.cash_usd),
                "positions": {a: {"amount": _text(_decimal(self.holdings[a])),
                                  "value_usd": _text(self.values_usd[a])}
                              for a in sorted(self.holdings)},
                "label": "paper: stocks at their Chainlink marks plus paper cash"}


def book(holdings: Mapping[str, Amount], cash_usd: Decimal,
         snapshot: Mapping[str, Any]) -> Book:
    """Value the paper holdings at the snapshot's marks. Raises PlanError for a
    holding the snapshot cannot mark: no value is never a value of zero."""
    entries = _entries(snapshot)
    chain_id = snapshot["block"]["chain_id"]
    held = {address.lower(): amount for address, amount in holdings.items() if amount.raw}
    values = {}
    for address, amount in held.items():
        if address not in entries:
            raise PlanError(f"{address} is held but not in the snapshot, so it cannot be valued")
        values[address] = cash.worth(amount, _mark(snapshot, address))
    nav = cash_usd + sum(values.values(), Decimal(0))
    if nav <= 0:
        raise PlanError("the paper book is worth nothing, so no weight can be computed")
    return Book(nav, cash_usd, held, values)


# --- 2. sizing -----------------------------------------------------------------------------------

@dataclass(frozen=True)
class Intent:
    """One order before it is quoted: what to sell to the venue, and for what."""

    index: int
    address: str
    symbol: str
    side: str  # "buy" or "sell"
    usd: Decimal  # what the order sells, at the mark (cash.worth): the figure the gates judge
    sell: Amount  # USDG for a buy, the stock for a sell
    buy: AssetId
    buy_decimals: int


class Sized(tuple):
    """The orders a proposal needs, in order, and how their buys were funded.

    A tuple of `Intent`s, so it reads as the orders. It also carries:
    - `proceeds_usd`, what the sells are worth;
    - `wanted_usd`, what the proposal's raises would cost;
    - `funded`, the share of them that cash above the floor pays for. It is None
      when the floor is unresolved, and then no buy is planned."""

    proceeds_usd: Decimal
    wanted_usd: Decimal
    funded: Decimal | None

    def __new__(cls, intents=(), proceeds_usd=Decimal(0), wanted_usd=Decimal(0), funded=None):
        sized = super().__new__(cls, intents)
        sized.proceeds_usd, sized.wanted_usd, sized.funded = proceeds_usd, wanted_usd, funded
        return sized


def _even(total: int, parts: int) -> list[int]:
    """`total` in `parts` that differ by at most one, the larger first."""
    base, extra = divmod(total, parts)
    return [base + 1] * extra + [base] * (parts - extra)


def size(proposal: Proposal, the_book: Book, snapshot: Mapping[str, Any],
         limits: gates.Limits) -> Sized:
    """Every order the proposal needs: sells first, then the buys cash can fund.

    - **A sell** sells the units its cut is worth at the mark, never more than
      is held, and all of them when the target is zero. It is split evenly into
      the fewest orders that keep each within the per-trade limit, judged on
      what the whole sale is worth.
    - **The buys** are funded only from cash above the floor, plus what the
      sells are worth, both by `cash.worth`, the measure the floor is judged on
      (`gates.fund`). When that falls short, every raise is scaled by the same
      share and rounded down to the cent. So the plan cannot break its own
      floor.
    - **Each buy** is split evenly the same way. It sells the USDG its dollars
      are worth at USDG's mark, rounded down.

    Each order's `usd` is what it sells, at the mark: the figure the gates
    judge. A move worth less than the minimum order is dust and becomes none. No
    rebalance, no orders."""
    if not proposal.rebalance:
        return Sized()
    entries = _entries(snapshot)
    chain_id = snapshot["block"]["chain_id"]
    cash_id, cash_decimals, cash_mark = _cash_leg(snapshot)
    nav = the_book.nav_usd

    def parts(value: Decimal) -> int:
        count = gates.split(value, limits)
        if count is None:
            raise PlanError("max_trade_usd or min_order_usd is null: unresolved, and it blocks")
        return count

    sells: list[dict] = []
    for row in sorted(proposal.rows, key=lambda r: r.address):
        if row.target >= row.current:
            continue
        held = the_book.holdings.get(row.address)
        stock_mark = _mark(snapshot, row.address)
        decimals = entries[row.address]["asset"]["decimals"]
        whole = held.raw if held else 0
        sold = whole if row.target == 0 else min(
            cash.units((row.current - row.target) * nav, stock_mark, decimals), whole)
        stock = AssetId(chain_id, row.address)
        count = parts(cash.worth(Amount(sold, decimals, stock), stock_mark)) if sold else 0
        for chunk in _even(sold, count) if count else ():
            amount = Amount(chunk, decimals, stock)
            sells.append(dict(address=row.address, symbol=row.symbol, side="sell",
                              usd=cash.worth(amount, stock_mark), sell=amount, buy=cash_id,
                              buy_decimals=cash_decimals))
    proceeds = sum((o["usd"] for o in sells), Decimal(0))

    raises = [(row, (row.target - row.current) * nav)
              for row in sorted(proposal.rows, key=lambda r: r.address) if row.target > row.current]
    wanted = sum((move for _, move in raises), Decimal(0))
    share = gates.fund(the_book.cash_usd, proceeds, wanted, limits)
    buys: list[dict] = []
    for row, move in raises if share is not None else ():
        usd = (move * share).quantize(CENT, rounding=ROUND_DOWN)
        count = parts(usd)
        for cents in _even(int(usd * 100), count) if count else ():
            spend = Amount(cash.units(Decimal(cents) / 100, cash_mark, cash_decimals),
                           cash_decimals, cash_id)
            buys.append(dict(address=row.address, symbol=row.symbol, side="buy",
                             usd=cash.worth(spend, cash_mark), sell=spend,
                             buy=AssetId(chain_id, row.address),
                             buy_decimals=entries[row.address]["asset"]["decimals"]))
    intents = tuple(Intent(index=i, **o) for i, o in enumerate(sells + buys, start=1))
    return Sized(intents, proceeds, wanted, share)


# --- 3. the plan ---------------------------------------------------------------------------------

@dataclass(frozen=True)
class QuoteSeen:
    """A fresh quote for one order, exactly as fetched, with the verdict
    `adapters/bankr_quote.tradeability` gave it at the plan's `judged_at`."""

    observation: Observation
    verdict: Check
    rule: str | None
    age_ms: int | None


def _canonical(obj: Any) -> Any:
    """A core type as the plain JSON object `types.to_canonical` writes."""
    return json.loads(to_canonical(obj))


def _quote_record(seen: QuoteSeen | None, side: str) -> dict[str, Any] | None:
    if seen is None:
        return None
    record: dict[str, Any] = {
        "observation": _canonical(seen.observation),
        "tradeable": {"value": seen.verdict.value, "rule": seen.rule,
                      "reason": seen.verdict.reason},
        "age_ms": seen.age_ms}
    q = seen.observation.value
    if isinstance(q, Quote):  # the figures risk reads, taken from the observation above
        stock_price = q.buy_price if side == "buy" else q.sell_price
        record.update({
            "sell": _text(_decimal(q.sell)), "buy": _text(_decimal(q.buy)),
            "min_buy": _text(_decimal(q.min_buy)),
            "swap_impact_bps": _text(_decimal(q.swap_impact)) if q.swap_impact else None,
            "slippage_bps": _text(_decimal(q.slippage)) if q.slippage else None,
            "fee_bps": _text(_decimal(q.fee)) if q.fee else None,
            "venue_price_usd": _text(_decimal(stock_price)) if stock_price else None})
    return record


def _evidence(entry: Mapping[str, Any]) -> dict[str, Any]:
    """What the snapshot says about the asset, for risk to read beside the quote."""
    mark, corroboration = entry.get("mark") or {}, entry.get("corroboration") or {}
    return {
        "status": entry["status"],
        "mark": {k: mark.get(k) for k in ("price_usd", "updated_at", "feed", "fresh", "verdict")},
        "corroboration": {k: corroboration.get(k) for k in (
            "price_usd", "volume_24h_usd", "divergence_bps", "session", "tier", "verdict")},
        "snapshot_quote": {k: (entry.get("quote") or {}).get(k) for k in (
            "venue_price_usd", "swap_impact_bps", "fetched_at")},
        "findings": list(entry.get("findings") or ())}


def write(intents: Sequence[Intent], quotes: Mapping[int, QuoteSeen], *,
          proposal: Proposal, the_book: Book, snapshot: Mapping[str, Any],
          snapshot_sha256: str, judged_at: Instant) -> dict[str, Any]:
    """The plan as the record keeps it and risk reads it. An order with no quote
    carries None, and the quote gate blocks it. What the plan would leave in cash
    is `cash.cash_after` of every order, the function the floor is judged with."""
    entries = _entries(snapshot)
    weights = the_book.weights
    targets = {r.address: r.target for r in proposal.rows}
    moved: dict[str, Decimal] = {}
    orders = []
    for intent in intents:
        signed = intent.usd if intent.side == "buy" else -intent.usd
        moved[intent.address] = moved.get(intent.address, Decimal(0)) + signed
        orders.append({
            "index": intent.index, "side": intent.side, "usd": _text(intent.usd),
            "asset": {"chain_id": snapshot["block"]["chain_id"], "address": intent.address,
                      "symbol": intent.symbol},
            "sell": {"address": intent.sell.asset.address, "amount": _text(_decimal(intent.sell)),
                     "decimals": intent.sell.decimals},
            "buy": {"address": intent.buy.address, "decimals": intent.buy_decimals},
            "weight": {"current": _text(weights.get(intent.address, Decimal(0))),
                       "target": _text(targets.get(intent.address))},
            "quote": _quote_record(quotes.get(intent.index), intent.side),
            "evidence": _evidence(entries[intent.address])})
    after = {a: (the_book.values_usd.get(a, Decimal(0)) + m) / the_book.nav_usd
             for a, m in moved.items()}
    for order in orders:
        order["weight"]["after"] = _text(after[order["asset"]["address"]])
    funded = getattr(intents, "funded", None)
    return {"snapshot_sha256": snapshot_sha256, "judged_at_ms": judged_at.epoch_ms,
            "rebalance": proposal.rebalance, "book": the_book.as_dict(), "orders": orders,
            "funding": {"sells_worth_usd": _text(getattr(intents, "proceeds_usd", Decimal(0))),
                        "raises_wanted_usd": _text(getattr(intents, "wanted_usd", Decimal(0))),
                        "share_funded": _text(funded),
                        "rule": "buys are paid only from cash above the floor plus what the "
                                "sells are worth (gates.fund)"},
            "cash_after_usd": _text(cash.cash_after(the_book.cash_usd, orders, snapshot)),
            "turnover_usd": _text(sum((i.usd for i in intents), Decimal(0))),
            "not_planned": "the live ETH<->USDG leg, a demonstration of the money path that "
                           "no analyst chose, is Phase 5's (operator, 2026-09-19)"}
