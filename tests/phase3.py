"""Shared by the Phase 3 tests: the approved reports, the committed capture, and a
fake venue.

**The fake venue is not a quote.** Offline, nothing can quote an order at the
size the planner asks for. So it answers at that size from the capture's own
venue prices for the asset and for USDG, with the capture's own impact unless a
test sets one. Every observation it makes says so in its `detail`. Its verdict
is still `adapters/bankr_quote.tradeability`'s, the one definition of quote age
and impact.
"""

from __future__ import annotations

import hashlib
import json
from decimal import ROUND_DOWN, Decimal
from pathlib import Path

from fund import config
from fund.adapters import bankr_quote
from fund.agents import schema
from fund.core import aggregate, gates, plan
from fund.core.types import (
    BPS, USD, Amount, AssetId, FetchStatus, Fixed, Instant, Observation, Price, Quote,
)

REPO = Path(__file__).resolve().parents[1]
FORMAT = (REPO / "planning" / "REPORT-FORMAT.md").read_text()
CAPTURE = REPO / "fixtures" / "snapshots" / "66852293-253315c0e691"
SNAPSHOT_BYTES = (CAPTURE / "snapshot.json").read_bytes()
SNAPSHOT = json.loads(SNAPSHOT_BYTES)
SNAPSHOT_SHA256 = hashlib.sha256(SNAPSHOT_BYTES).hexdigest()
SEATS = ["price-trend", "cross-asset-macro", "execution-quality", "price-integrity"]
INTEGRITY_AGENT = "0x42a9bd235aedd68e9f2881710577105cb46e3d27"

ANALYSTS = config.load_json("analysts.json")
KINDS = {a["id"]: a["vocabulary"] for a in ANALYSTS["analysts"]}
WEIGHTS = {w: Decimal(v) for w, v in ANALYSTS["confidence_weights"].items()}
ENTRIES = {a["asset"]["address"]: a for a in SNAPSHOT["assets"]}
SYMBOLS = {a: e["asset"]["symbol"] for a, e in ENTRIES.items()}
ADDRESS = {symbol: address for address, symbol in SYMBOLS.items()}
CHAIN = SNAPSHOT["block"]["chain_id"]
LIMITS = gates.Limits.from_config(config.load_json("thresholds.json"),
                                  config.load_json("mandate.json"), config.load_json("models.json"))
QUOTE_LIMITS = bankr_quote.Limits.from_thresholds(config.load_json("thresholds.json"))
NAV = Decimal(200)

#: When the fake venue answered, and when the plan judged it: both inputs, never a clock.
FETCHED_MS = 1_790_000_000_000
JUDGED_MS = FETCHED_MS + 5_000


def example_text(seat: str) -> str:
    """An approved report exactly as REPORT-FORMAT.md writes it."""
    return FORMAT.split(f". {seat}\n", 1)[1].split("```\n", 2)[1]


def approved(seat: str) -> dict:
    report, refusals = schema.parse(example_text(seat))
    assert refusals == ()
    return report.as_dict()


FOUR = [approved(seat) for seat in SEATS]


def amount(symbol: str, units: str) -> Amount:
    return Amount.from_units(units, ENTRIES[ADDRESS[symbol]]["asset"]["decimals"],
                             AssetId(CHAIN, ADDRESS[symbol]))


def worth(symbol: str, usd: str) -> Amount:
    """The holding worth `usd` at the snapshot's mark, rounded down."""
    mark = Decimal(ENTRIES[ADDRESS[symbol]]["mark"]["price_usd"])
    units = (Decimal(usd) / mark).quantize(Decimal(10) ** -18, rounding=ROUND_DOWN)
    return amount(symbol, format(units, "f"))


def book(holdings: dict[str, Amount] | None = None, cash: str = "200") -> plan.Book:
    return plan.book({a.asset.address: a for a in (holdings or {}).values()}, Decimal(cash),
                     SNAPSHOT)


def propose(reports=FOUR, the_book: plan.Book | None = None, limits=LIMITS) -> aggregate.Proposal:
    the_book = the_book or book()
    return aggregate.aggregate(reports, kinds=KINDS, current=the_book.weights,
                               cash_weight=the_book.cash_weight, nav_usd=the_book.nav_usd,
                               limits=limits, confidence_weights=WEIGHTS, symbols=SYMBOLS)


def _units(value: Decimal, decimals: int) -> int:
    return int(value.scaleb(decimals).to_integral_value(rounding=ROUND_DOWN))


def fake_quote(intent: plan.Intent, *, fetched_ms: int = FETCHED_MS,
               impact_bps: int | None = None) -> Observation:
    """What the venue might answer for this order, scaled from the capture."""
    entry = ENTRIES[intent.address]
    venue = Decimal(entry["quote"]["venue_price_usd"])
    usdg = Decimal(entry["quote"]["venue_sell_token_price_usd"])
    impact = int(entry["quote"]["swap_impact_bps"]) if impact_bps is None else impact_bps
    sold = Decimal(intent.sell.raw).scaleb(-intent.sell.decimals)
    stock = AssetId(CHAIN, intent.address)
    if intent.side == "buy":
        got = sold * usdg / venue
        sell_price = Price.parse(format(usdg, "f"), intent.sell.asset, USD)
        buy_price = Price.parse(format(venue, "f"), stock, USD)
    else:
        got = sold * venue / usdg
        sell_price = Price.parse(format(venue, "f"), stock, USD)
        buy_price = Price.parse(format(usdg, "f"), intent.buy, USD)
    buy = Amount(_units(got, intent.buy_decimals), intent.buy_decimals, intent.buy)
    quote = Quote(sell=intent.sell, buy=buy,
                  min_buy=Amount(buy.raw * 95 // 100, buy.decimals, buy.asset),
                  price_impact=Fixed(impact, 0, BPS), swap_impact=Fixed(impact, 0, BPS),
                  max_price_impact=Fixed(1500, 0, BPS), fee=Fixed(0, 0, BPS), fee_waived=False,
                  slippage=Fixed(500, 0, BPS), sell_price=sell_price, buy_price=buy_price,
                  quote_id=f"fake-{intent.index}")
    return Observation(value=quote, source=bankr_quote.SOURCE, source_time=None,
                       fetch_time=Instant(fetched_ms), block=None, status=FetchStatus.OK,
                       detail="FAKE VENUE: scaled from the capture's own venue prices; not a "
                              "quote", source_ref=quote.quote_id)


def judged(intent: plan.Intent, observation: Observation,
           judged_ms: int = JUDGED_MS) -> plan.QuoteSeen:
    """The verdict the one definition of quote age and impact gives."""
    verdict = bankr_quote.tradeability(observation, intent.sell, Instant(judged_ms), QUOTE_LIMITS)
    return plan.QuoteSeen(observation, verdict.verdict, verdict.rule, verdict.age_ms)


def quoted(intents, **changes) -> dict[int, plan.QuoteSeen]:
    """Every intent quoted by the fake venue and judged. `changes` maps a symbol to
    fake_quote keyword arguments for that asset's orders."""
    out = {}
    for intent in intents:
        options = changes.get(intent.symbol, {})
        out[intent.index] = judged(intent, fake_quote(intent, **options))
    return out


def written(reports=FOUR, the_book=None, limits=LIMITS, **changes) -> dict:
    """A whole plan, from reports to quoted orders."""
    the_book = the_book or book()
    proposal = propose(reports, the_book, limits)
    intents = plan.size(proposal, the_book, SNAPSHOT, limits)
    return plan.write(intents, quoted(intents, **changes), proposal=proposal, the_book=the_book,
                      snapshot=SNAPSHOT, snapshot_sha256=SNAPSHOT_SHA256,
                      judged_at=Instant(JUDGED_MS))
