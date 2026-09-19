"""Target weights to sized orders, each carrying its fresh quote and evidence (unit 3.3).

An H unit: this is where a view becomes an amount of money. Three steps:

1. **`book`** values the paper holdings at the snapshot's Chainlink marks,
   through `core/valuation.value()`, the one place a quantity becomes USD. Cash
   is paper USD. A holding with no usable mark cannot be valued, and the planner
   refuses rather than guessing.
2. **`size`** turns each target into orders. The move is `(target − current) ×
   NAV`, cut toward zero to the cent. `gates.pieces` splits it into orders of at
   most the mandate's per-trade limit and drops dust under the minimum order.
   Sells go first, since they free cash, then buys, each by address. A buy sells
   USDG worth the order at USDG's own mark, rounded down, so it never spends
   more than it names. A sell sells the stock worth the order at its mark,
   rounded down, never more than is held, and all of it when the target is zero.
   A position whose target is where it stands gets no order: hold and silence
   trade nothing.
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

from . import gates, valuation
from .aggregate import Proposal, decimal_text as _text
from .types import USD, Amount, AssetId, Check, Instant, Observation, Price, Quote, to_canonical

CENT = Decimal("0.01")


class PlanError(Exception):
    """The book cannot be valued or sized, so no plan is written."""


def _decimal(quantity: Any) -> Decimal:
    """A Fixed, Amount or Price as an exact Decimal."""
    return Decimal(quantity.raw).scaleb(-quantity.decimals)


def _entries(snapshot: Mapping[str, Any]) -> dict[str, Mapping[str, Any]]:
    return {a["asset"]["address"].lower(): a for a in snapshot["assets"]}


def _mark(entry: Mapping[str, Any], chain_id: int) -> Price:
    mark = entry.get("mark") or {}
    if (mark.get("verdict") or {}).get("verdict") is not True or not mark.get("price_usd"):
        raise PlanError(f"{entry['asset']['symbol']} has no usable mark in the snapshot: "
                        f"{(mark.get('verdict') or {}).get('reason')}")
    return Price.parse(mark["price_usd"], AssetId(chain_id, entry["asset"]["address"].lower()), USD)


def _cash_leg(snapshot: Mapping[str, Any]) -> tuple[AssetId, int, Price]:
    chain_id = snapshot["block"]["chain_id"]
    entry = next(h for h in snapshot["holdings"] if h["asset"]["kind"] == "cash")
    return (AssetId(chain_id, entry["asset"]["address"].lower()), entry["asset"]["decimals"],
            _mark(entry, chain_id))


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
        values[address] = _decimal(valuation.value(amount, _mark(entries[address], chain_id)))
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
    usd: Decimal  # the order's size in the paper book's dollars, to the cent
    sell: Amount  # USDG for a buy, the stock for a sell
    buy: AssetId
    buy_decimals: int


def _units(usd: Decimal, price: Price, decimals: int) -> int:
    """Raw units worth `usd` at `price`, rounded down: an order never names more
    than its dollars buy."""
    return int((usd / _decimal(price)).scaleb(decimals).to_integral_value(rounding=ROUND_DOWN))


def size(proposal: Proposal, the_book: Book, snapshot: Mapping[str, Any],
         limits: gates.Limits) -> tuple[Intent, ...]:
    """Every order the proposal needs, sells first. No rebalance, no orders."""
    if not proposal.rebalance:
        return ()
    entries = _entries(snapshot)
    chain_id = snapshot["block"]["chain_id"]
    cash_id, cash_decimals, cash_mark = _cash_leg(snapshot)
    sells: list[dict] = []
    buys: list[dict] = []
    for row in proposal.rows:
        change = row.target - row.current
        if not change:
            continue  # hold, silence, caution alone: no order
        total = (abs(change) * the_book.nav_usd).quantize(CENT, rounding=ROUND_DOWN)
        pieces = gates.pieces(total, limits)
        if pieces is None:
            raise PlanError("max_trade_usd or min_order_usd is null: unresolved, and it blocks")
        entry = entries[row.address]
        stock = AssetId(chain_id, row.address)
        decimals = entry["asset"]["decimals"]
        if change > 0:
            for usd in pieces:
                sell = Amount(_units(usd, cash_mark, cash_decimals), cash_decimals, cash_id)
                buys.append(dict(address=row.address, symbol=row.symbol, side="buy", usd=usd,
                                 sell=sell, buy=stock, buy_decimals=decimals))
            continue
        held = the_book.holdings.get(row.address)
        left = held.raw if held else 0
        mark = _mark(entry, chain_id)
        for n, usd in enumerate(pieces):
            units = min(_units(usd, mark, decimals), left)
            if row.target == 0 and n == len(pieces) - 1:
                units = left  # a position cut to zero is sold whole, dust included
            left -= units
            if units:
                sells.append(dict(address=row.address, symbol=row.symbol, side="sell", usd=usd,
                                  sell=Amount(units, decimals, stock), buy=cash_id,
                                  buy_decimals=cash_decimals))
    ordered = sorted(sells, key=lambda o: o["address"]) + sorted(buys, key=lambda o: o["address"])
    return tuple(Intent(index=i, **o) for i, o in enumerate(ordered, start=1))


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
    carries None, and the quote gate blocks it."""
    entries = _entries(snapshot)
    weights = the_book.weights
    targets = {r.address: r.target for r in proposal.rows}
    moved: dict[str, Decimal] = {}
    cash = the_book.cash_usd
    orders = []
    for intent in intents:
        signed = intent.usd if intent.side == "buy" else -intent.usd
        moved[intent.address] = moved.get(intent.address, Decimal(0)) + signed
        cash -= signed
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
    return {"snapshot_sha256": snapshot_sha256, "judged_at_ms": judged_at.epoch_ms,
            "rebalance": proposal.rebalance, "book": the_book.as_dict(), "orders": orders,
            "cash_after_usd": _text(cash), "turnover_usd": _text(
                sum((i.usd for i in intents), Decimal(0))),
            "not_planned": "the live ETH<->USDG leg, a demonstration of the money path that "
                           "no analyst chose, is Phase 5's (operator, 2026-09-19)"}
