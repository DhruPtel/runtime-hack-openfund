"""A fake venue, for paper cycles run offline (units 3.3 to 4.8). **It is not a quote.**

Offline, nothing can quote an order at the size the planner asks for. So this answers
at that size from the capture's own venue prices for the asset and for USDG, and the
capture's own impact unless a caller sets one. Every observation it makes says so in
its `detail`, "FAKE VENUE", and in its quote id. Its answers are judged, like a real
quote's, by `adapters/bankr_quote.tradeability`.

It has the venue's interface: `quote(QuoteRequest) -> Observation`, as the live
adapter's (`adapters/bankr_quote`). So the decision and the chokepoint take either,
and nothing that calls them knows which it has.

Built for 3.3's tests; moved into the fund at 4.4 so the paper cycle (4.8) can run
from the command line, and into `adapters/` at 4.12, where the venue is, so the
treasurer's own process reaches it without importing the layer above it. The tests'
`phase3.fake_quote` calls `observe`, so there is one.
"""

from __future__ import annotations

from decimal import ROUND_DOWN, Decimal
from typing import Any, Callable, Mapping

from fund.adapters import bankr_quote
from fund.core import cash
from fund.core.types import (
    BPS, USD, Amount, AssetId, FetchStatus, Fixed, Instant, Observation, Price, Quote,
)

DETAIL = "FAKE VENUE: scaled from the capture's own venue prices; not a quote"


def _units(value: Decimal, decimals: int) -> int:
    return int(value.scaleb(decimals).to_integral_value(rounding=ROUND_DOWN))


def observe(snapshot: Mapping[str, Any], request: bankr_quote.QuoteRequest, fetched: Instant, *,
            impact_bps: int | None = None, quote_id: str = "fake") -> Observation:
    """What the venue might answer for `request`, scaled from the capture."""
    usdg_id, _ = cash.cash_leg(snapshot)
    buying = request.sell.asset == usdg_id
    stock = request.buy if buying else request.sell.asset
    entry = next(a for a in snapshot["assets"] if a["asset"]["address"] == stock.address)
    venue = Decimal(entry["quote"]["venue_price_usd"])
    usdg = Decimal(entry["quote"]["venue_sell_token_price_usd"])
    impact = int(entry["quote"]["swap_impact_bps"]) if impact_bps is None else impact_bps
    sold = Decimal(request.sell.raw).scaleb(-request.sell.decimals)
    if buying:
        got = sold * usdg / venue
        sell_price = Price.parse(format(usdg, "f"), request.sell.asset, USD)
        buy_price = Price.parse(format(venue, "f"), stock, USD)
    else:
        got = sold * venue / usdg
        sell_price = Price.parse(format(venue, "f"), stock, USD)
        buy_price = Price.parse(format(usdg, "f"), request.buy, USD)
    buy = Amount(_units(got, request.buy_decimals), request.buy_decimals, request.buy)
    quote = Quote(sell=request.sell, buy=buy,
                  min_buy=Amount(buy.raw * 95 // 100, buy.decimals, buy.asset),
                  price_impact=Fixed(impact, 0, BPS), swap_impact=Fixed(impact, 0, BPS),
                  max_price_impact=Fixed(1500, 0, BPS), fee=Fixed(0, 0, BPS), fee_waived=False,
                  slippage=Fixed(500, 0, BPS), sell_price=sell_price, buy_price=buy_price,
                  quote_id=quote_id)
    return Observation(value=quote, source=bankr_quote.SOURCE, source_time=None,
                       fetch_time=fetched, block=None, status=FetchStatus.OK, detail=DETAIL,
                       source_ref=quote.quote_id)


class FakeVenue:
    """The venue's interface over one capture. `clock` says when each answer is
    fetched: an input, never the wall clock, so a paper cycle rebuilds exactly."""

    def __init__(self, snapshot: Mapping[str, Any], clock: Callable[[], Instant],
                 impact_bps: Mapping[str, int] | None = None):
        self.snapshot, self.clock, self.impact_bps = snapshot, clock, dict(impact_bps or {})
        self.asked = 0

    def quote(self, request: bankr_quote.QuoteRequest) -> Observation:
        self.asked += 1
        impact = self.impact_bps.get(request.buy.address,
                                     self.impact_bps.get(request.sell.asset.address))
        return observe(self.snapshot, request, self.clock(), impact_bps=impact,
                       quote_id=f"fake-{self.asked}")
