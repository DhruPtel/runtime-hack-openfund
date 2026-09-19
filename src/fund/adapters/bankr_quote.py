"""POST /wallet/swap-quote. READ ONLY. Never imports a signing path. Unit 1.5.

What a trade would cost at the $25 intended size, from the venue that would
execute it. This is the execution-side price. It is not the accounting mark,
which is Chainlink's (1.4), and it is not a fill.

What the record requires, and where each requirement is met:

- **Read-only, by construction.** It loads `BANKR_KEY_READ` (Read Only ON)
  under the analyst role, which cannot load `BANKR_KEY_EXEC` or `SIGNING_KEY`
  (`src/fund/credentials.py`). `Settings.load` refuses any credential that can
  transact. Nothing here imports a signing path, and a test asserts the module
  cannot reach `bankr_exec` or the signing key.
- **The shared transport.** The deadline, failover, pacing, backoff,
  Retry-After and redaction are `adapters/http.py`'s. This module supplies only
  the transport function, because the key travels in a header and
  `http.urllib_transport` sets no caller headers.
- **The documented request, validated here.** The endpoint answers every
  malformed body with the same `{"message":"Invalid request body"}` and leaks no
  schema (probe 0.3), so the request is checked before it is sent. Its shape is
  from `docs.bankr.bot/wallet-api/swap`, read 2026-09-17; `amount` is
  human-readable, in the sold token.
- **Decimals come from the pins, and are checked against the response.** USDG
  is 6 and stock tokens 18, and two documented sources said 18 for USDG
  (F0.3.1). A single "18 decimals" assumption is a 10^12 error that fixtures
  carrying the same wrong number would pass, so a response whose `decimals`
  disagree with the pinned ones is refused.
- **Four number formats in one payload, converted exactly** (probe 0.3's
  responses, LESSONS 2026-09-18):
  - `from.amount` echoes the human request;
  - `to.amount` is raw;
  - `to.formattedAmount` is lossy, a digit short, and is never read;
  - `minBuyAmount` is human text;
  - the two USD prices are JSON floats, taken from their text as sent, so no
    float is ever made.
- **Absent stays null.** All 12 documented fields appeared in six responses
  (F0.3.2). That is six responses at one moment, not a contract.
- **Impact is signed, and `swapImpactBps` gates.** It is documented as the
  number server-side execution gates on; `priceImpactBps` is "for display" (the
  note under F0.5). Negative impact is price improvement, and four of six
  quotes in probe 0.3 had it (F0.3.4). So the rule is `impact > limit`, never
  `abs(impact) > limit`.
- **Age from our own clock.** A quote carries no timestamp, and a stale
  `quoteId` "falls back silently" (documented). So age is the judging instant
  minus our fetch time.
- **A quote is a price, not a fill.** Quotes are not balance-checked (F0.3.3)
  and not location-gated: F0.5.1 measured a stock quote succeeding while its
  execution was refused with a 403. So `Tradeability` keeps two claims apart:
  - `verdict` is operational tradeability (PLAN §9);
  - `executable` is always undetermined, and says why.
- **Two comparisons, a named exception.** Quote age and impact are compared
  here until 3.4 sweeps them into `core/gates.py` (DECISION, LESSONS
  2026-09-18). Both limits come from `config/thresholds.json` as arguments.
"""

from __future__ import annotations

import json
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Mapping

from fund.adapters import http
from fund.core.types import (
    BPS, USD, Amount, AssetId, Check, FetchStatus, Fixed, Instant, Observation, Price, Quote,
    Source,
)
from fund.credentials import Role, by_name

SOURCE = Source("bankr-quote", "/wallet/swap-quote")
ENDPOINT_NAME = "BANKR_API"

QUOTE_CONFIG = Path(__file__).resolve().parents[3] / "config" / "quote.json"
THRESHOLDS = Path(__file__).resolve().parents[3] / "config" / "thresholds.json"

RULE_QUOTE = "quote"          # the venue returned no usable quote
RULE_SIZE = "size"            # the quote is not for the amount asked
RULE_QUOTE_AGE = "quote-age"  # older than quote_max_age_seconds
RULE_IMPACT = "impact"        # swapImpactBps absent, or above impact_max_bps compared signed

#: Carried on every verdict, whatever it says, so that "tradeable" can never be
#: read as "would execute".
NOT_EVIDENCE_OF_EXECUTION = Check(None, (
    "a quote is a price, not a fill: quotes are not balance-checked (F0.3.3) and not "
    "location-gated, and a stock quote succeeded while its execution was refused 403 (F0.5.1)"))


# --- sizing and the request ------------------------------------------------------------

def nominal_sell(nominal: Fixed, cash_price: Price, cash_decimals: int) -> Amount:
    """The cash-leg amount worth `nominal` USD at the cash leg's own mark,
    rounded down to its decimals so the order never exceeds the size it names.
    USDG is not assumed to be a dollar: 1.4 marked it at $0.99995."""
    if nominal.unit != USD or cash_price.quote_unit != USD:
        raise ValueError("a nominal size and a cash mark are both USD")
    if nominal.raw <= 0 or cash_price.raw <= 0:
        raise ValueError("a size and a mark are positive")
    numerator = nominal.raw * 10 ** (cash_decimals + cash_price.decimals)
    return Amount(numerator // (cash_price.raw * 10 ** nominal.decimals), cash_decimals,
                  cash_price.base)


def _decimal(raw: int, decimals: int) -> str:
    sign, digits = ("-" if raw < 0 else ""), str(abs(raw))
    if decimals == 0:
        return sign + digits
    digits = digits.rjust(decimals + 1, "0")
    whole, fraction = digits[:-decimals], digits[-decimals:].rstrip("0")
    return sign + whole + ("." + fraction if fraction else "")


def human(amount: Amount) -> str:
    """An amount as the exact decimal text the request's `amount` expects."""
    if amount.raw < 0:
        raise ValueError("a quoted amount is not negative")
    return _decimal(amount.raw, amount.decimals)


@dataclass(frozen=True)
class QuoteRequest:
    """Sell `sell` for `buy`. `buy_decimals` is the pinned decimals of the bought
    token: from the registry for a stock, from the pins for cash."""

    sell: Amount
    buy: AssetId
    buy_decimals: int

    def __post_init__(self):
        if self.sell.raw <= 0:
            raise ValueError("a quote sells a positive amount")
        if self.sell.asset == self.buy:
            raise ValueError("a quote sells one asset for another")
        if self.sell.asset.chain_id != self.buy.chain_id:
            raise ValueError("both sides are on one chain")
        if type(self.buy_decimals) is not int or self.buy_decimals < 0:
            raise ValueError("buy_decimals is a non-negative int, from the pins")

    def body(self, chain: str) -> dict[str, str]:
        """The documented request: five fields, `amount` human-readable."""
        return {"fromChain": chain, "fromToken": self.sell.asset.address, "toChain": chain,
                "toToken": self.buy.address, "amount": human(self.sell)}


# --- the response, converted exactly ------------------------------------------------------

_DIGITS = re.compile(r"^[0-9]+$")


def _text(value: Any, name: str) -> str:
    if value is None:
        raise ValueError(f"{name} is absent")
    if isinstance(value, str):
        return value
    if type(value) is int:
        return str(value)
    raise TypeError(f"{name} is {type(value).__name__}, not a number's text")


def parse(body: bytes, request: QuoteRequest, chain: str, fetch_time: Instant) -> Observation:
    """A 200's body as an Observation of a `Quote`, or REFUSED with the reason."""
    def refused(why: str) -> Observation:
        return Observation(value=None, source=SOURCE, source_time=None, fetch_time=fetch_time,
                           block=None, status=FetchStatus.REFUSED, detail=why)

    try:
        data = json.loads(body, parse_float=str)  # a JSON float stays the text that was sent
    except ValueError:
        return refused("a 200 whose body is not JSON")
    if not isinstance(data, dict) or not isinstance(data.get("from"), dict) \
            or not isinstance(data.get("to"), dict):
        return refused("a 200 without its `from` and `to` sides is not a quote")
    sides = (("from", data["from"], request.sell.asset, request.sell.decimals),
             ("to", data["to"], request.buy, request.buy_decimals))
    for label, side, asset, decimals in sides:
        token = str(side.get("token", "")).lower()
        if token != asset.address:
            return refused(f"{label}.token {token or 'absent'} is not the {asset.address} asked for")
        if side.get("chain") not in (None, chain):
            return refused(f"{label}.chain {side.get('chain')!r} is not {chain!r}")
        said = side.get("decimals")
        if said is not None and said != decimals:
            return refused(f"{label}.decimals {said!r} disagrees with the pinned {decimals}: "
                           "one of them is wrong, and trusting either blindly is the 10^12 "
                           "error F0.3.1 measured")

    try:
        sell = Amount.from_units(_text(data["from"].get("amount"), "from.amount"),
                                 request.sell.decimals, request.sell.asset)
        raw = _text(data["to"].get("amount"), "to.amount")
        if not _DIGITS.match(raw):
            raise ValueError(f"to.amount {raw!r} is not a raw integer")
        buy = Amount(int(raw), request.buy_decimals, request.buy)
        min_buy = Amount.from_units(_text(data.get("minBuyAmount"), "minBuyAmount"),
                                    request.buy_decimals, request.buy)
    except (ValueError, TypeError) as error:
        return refused(f"an amount the quote cannot be read without: {error}")

    absent: list[str] = []

    def bps(name: str) -> Fixed | None:
        value = data.get(name)
        try:
            if type(value) is int:
                return Fixed(value, 0, BPS)
            if isinstance(value, str):
                return Fixed.parse(value, BPS)
        except ValueError:
            pass
        absent.append(name if value is None else f"{name} ({value!r}, unreadable)")
        return None

    def price(name: str, asset: AssetId) -> Price | None:
        value = data.get(name)
        try:
            return Price.parse(_text(value, name), asset, USD)
        except (ValueError, TypeError):
            absent.append(name if value is None else f"{name} ({value!r}, unreadable)")
            return None

    waived = data.get("feeWaivedForEcosystemToken")
    if waived is not None and type(waived) is not bool:
        absent.append(f"feeWaivedForEcosystemToken ({waived!r}, unreadable)")
        waived = None
    elif waived is None:
        absent.append("feeWaivedForEcosystemToken")
    quote_id = data.get("quoteId") if isinstance(data.get("quoteId"), str) and data["quoteId"] else None
    if quote_id is None:
        absent.append("quoteId")
    try:
        quote = Quote(sell=sell, buy=buy, min_buy=min_buy,
                      price_impact=bps("priceImpactBps"), swap_impact=bps("swapImpactBps"),
                      max_price_impact=bps("maxPriceImpactBps"), fee=bps("feeBps"),
                      fee_waived=waived, slippage=bps("slippageBps"),
                      sell_price=price("sellTokenPriceUsd", request.sell.asset),
                      buy_price=price("buyTokenPriceUsd", request.buy), quote_id=quote_id)
    except (ValueError, TypeError) as error:
        return refused(f"not a quote: {error}")
    detail = "a price at size, not a fill (F0.3.3, F0.5.1); to.formattedAmount is lossy and not read"
    if absent:
        detail += "; absent, so null: " + ", ".join(absent)
    return Observation(value=quote, source=SOURCE, source_time=None, fetch_time=fetch_time,
                       block=None, status=FetchStatus.OK, detail=detail, source_ref=quote_id)


# --- the adapter --------------------------------------------------------------------------

def keyed_transport(user_agent: str, header: str, key: str) -> http.Transport:
    """urllib with the key in a header. Deadline, retries and redaction are the
    shared client's; this only puts the request on the wire."""
    def send(url: str, body: bytes | None, timeout_s: float) -> tuple[int, bytes, dict[str, str]]:
        headers = {"Accept": "application/json", "User-Agent": user_agent, header: key}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return response.status, response.read(), dict(response.headers.items())
        except urllib.error.HTTPError as error:
            return error.code, error.read(), dict(error.headers.items())
    return send


def _recording(transport: http.Transport, replies: list) -> http.Transport:
    """Keep every reply. The shared client treats any non-200 as a failure to
    retry and keeps only its status, but an HTTP error from the venue is still
    an answer, and its body says why it would not quote (LESSONS 2026-09-18)."""
    def send(url: str, body: bytes | None, timeout_s: float) -> tuple:
        result = transport(url, body, timeout_s)
        replies.append(result)
        return result
    return send


class QuoteAdapter:
    """Quotes over the shared client. Every request becomes an Observation, with
    the statuses `core/types.py` defines: OK with a `Quote`; REFUSED when the
    venue answered with an error, 4xx or 5xx, whose body is kept; UNREACHABLE
    when no answer came at all."""

    def __init__(self, client: http.HttpClient, *, chain: str, path: str,
                 clock: Callable[[], Instant], replies: list):
        self.client, self.chain, self.path, self.clock = client, chain, path, clock
        self._replies = replies

    def quote(self, request: QuoteRequest) -> Observation:
        self._replies.clear()
        body = json.dumps(request.body(self.chain)).encode("utf-8")
        try:
            reply = self.client.send(body, path=self.path)
        except http.Unavailable as unavailable:
            return self._failed(unavailable)
        return parse(reply.body, request, self.chain, self.clock())

    def _failed(self, unavailable: http.Unavailable) -> Observation:
        answered = [r for r in self._replies if r[0] != 200]
        if answered:
            status, body = answered[-1][0], answered[-1][1]
            said = self.client.scrub(body.decode("utf-8", "replace")[:400])
            return Observation(value=None, source=SOURCE, source_time=None,
                               fetch_time=self.clock(), block=None, status=FetchStatus.REFUSED,
                               detail=f"the venue answered HTTP {status}: {said}")
        return Observation(value=None, source=SOURCE, source_time=None, fetch_time=self.clock(),
                           block=None, status=FetchStatus.UNREACHABLE, detail=str(unavailable))


@dataclass(frozen=True)
class Settings:
    base_url: str
    path: str
    chain: str
    credential: str
    auth_header: str
    timeout_s: float
    attempts: int
    backoff_s: float
    min_interval_s: float
    user_agent: str

    @classmethod
    def load(cls, path: Path = QUOTE_CONFIG) -> Settings:
        c = json.loads(path.read_text())
        credential = by_name(c["credential"])
        if credential.can_transact:
            raise ValueError(f"{credential.name} can transact; the quote adapter is read-only "
                             "and refuses it")
        if Role.ANALYST not in credential.used_by:
            raise ValueError(f"{credential.name} is not the analyst role's, and quotes are read "
                             "under that role")
        return cls(base_url=c["base_url"], path=c["path"], chain=c["chain"],
                   credential=credential.name, auth_header=c["auth_header"],
                   timeout_s=c["request_timeout_seconds"], attempts=c["attempts"],
                   backoff_s=c["backoff_seconds"], min_interval_s=c["min_request_interval_ms"] / 1000,
                   user_agent=c["user_agent"])

    def adapter(self, secret: Callable[[str], str], transport: http.Transport | None = None,
                clock: Callable[[], Instant] | None = None) -> QuoteAdapter:
        """`secret` is `Config.secret` for the analyst role."""
        replies: list = []
        wire = transport or keyed_transport(self.user_agent, self.auth_header,
                                            secret(self.credential))
        client = http.HttpClient([http.Endpoint(ENDPOINT_NAME, self.base_url)],
                                 timeout_s=self.timeout_s, attempts=self.attempts,
                                 backoff_s=self.backoff_s, min_interval_s=self.min_interval_s,
                                 transport=_recording(wire, replies))
        return QuoteAdapter(client, chain=self.chain, path=self.path,
                            clock=clock or (lambda: Instant(time.time_ns() // 1_000_000)),
                            replies=replies)


# --- tradeability: a named exception until 3.4 --------------------------------------------

def _limit(thresholds: Mapping[str, Any], name: str, unit: str) -> Fixed:
    raw = thresholds.get(name)
    if raw is None:
        raise ValueError(f"{name} is null: unresolved, and it blocks the check that reads it")
    if type(raw) is int:
        return Fixed(raw, 0, unit)
    if isinstance(raw, str):
        return Fixed.parse(raw, unit)
    raise TypeError(f"{name} must be an integer or a decimal string, never a float")


@dataclass(frozen=True)
class Limits:
    """`quote_max_age_seconds`, `impact_max_bps` and the nominal size, from
    `config/thresholds.json`, all provisional (0.11 checkpoint decision)."""

    max_age: Fixed      # seconds
    max_impact: Fixed   # bps, compared signed
    nominal: Fixed      # USD, the intended size of one trade

    @classmethod
    def from_thresholds(cls, thresholds: Mapping[str, Any]) -> Limits:
        return cls(max_age=_limit(thresholds, "quote_max_age_seconds", "s"),
                   max_impact=_limit(thresholds, "impact_max_bps", BPS),
                   nominal=_limit(thresholds, "intended_trade_size_usd", USD))


@dataclass(frozen=True)
class Tradeability:
    """Operational tradeability of one quote, judged at one instant. `verdict`
    is True, False or None, with `rule` naming the rule that decided it when it
    did not pass. `executable` is separate, and always undetermined."""

    asked: Amount
    quote: Observation
    age_ms: int | None
    verdict: Check
    rule: str | None
    executable: Check = NOT_EVIDENCE_OF_EXECUTION


def _shown(quantity: Fixed) -> str:
    return _decimal(quantity.raw, quantity.decimals)


def tradeability(quote: Observation, asked: Amount, as_of: Instant, limits: Limits) -> Tradeability:
    """The three conditions of PLAN §9, in order, the first that does not pass
    named: the quote succeeded at the size asked (`quote`, `size`), its age is
    within the limit (`quote-age`), and its impact is known and at most the
    limit, compared signed (`impact`). Null blocks."""
    def verdict(value: bool | None, rule: str | None, reason: str, age: int | None = None):
        return Tradeability(asked, quote, age, Check(value, f"[{rule}] {reason}" if rule else reason),
                            rule)

    if not quote.ok:
        return verdict(None if quote.status is FetchStatus.UNREACHABLE else False, RULE_QUOTE,
                       f"no quote: {quote.status.value}: {quote.detail}")
    q = quote.value
    if not isinstance(q, Quote):
        raise TypeError("a quote observation carries a Quote")
    if q.sell.asset != asked.asset or q.sell.decimals != asked.decimals or q.sell.raw != asked.raw:
        return verdict(False, RULE_SIZE, f"quoted {human(q.sell)} of {q.sell.asset.address}, "
                                         f"asked {human(asked)} of {asked.asset.address}")
    age = as_of.epoch_ms - quote.fetch_time.epoch_ms
    if age < 0:
        return verdict(None, RULE_QUOTE_AGE, "fetched after the instant it is judged at, so its "
                                             "age is undetermined", age)
    if age * 10 ** limits.max_age.decimals > limits.max_age.raw * 1000:  # exact, in ms
        return verdict(False, RULE_QUOTE_AGE, f"age {age / 1000:.1f}s exceeds "
                                              f"{_shown(limits.max_age)}s; a stale quoteId falls "
                                              "back silently, so an old quote is never reused", age)
    impact = q.swap_impact
    if impact is None:
        return verdict(None, RULE_IMPACT, "swapImpactBps absent: unknown impact blocks (PLAN §2 "
                                          "invariant 5)", age)
    if impact > limits.max_impact:
        return verdict(False, RULE_IMPACT, f"swapImpactBps {_shown(impact)} exceeds "
                                           f"{_shown(limits.max_impact)}, compared signed", age)
    improvement = " (negative: price improvement, admitted)" if impact.raw < 0 else ""
    return verdict(True, None, f"quoted at the size asked; age {age / 1000:.1f}s within "
                               f"{_shown(limits.max_age)}s; swapImpactBps {_shown(impact)}{improvement} "
                               f"within {_shown(limits.max_impact)}, compared signed", age)


# --- the live proof: `python -m fund.adapters.bankr_quote --prove` ------------------------

def prove() -> int:
    """1.5 live and read-only: every markable stock quoted at the nominal size,
    judged at one instant, and one failure per rule. It sizes the order at the
    cash leg's Chainlink mark, which it reads through the chain adapter inside
    this function, the way 1.6's builder will compose them. Nothing is signed,
    submitted or spent."""
    import socket
    from decimal import Decimal

    from fund import config
    from fund.adapters import chain_4663 as chain
    from fund.core import universe, valuation

    def dec(raw: int, decimals: int, places: int) -> str:  # display only
        return f"{Decimal(raw).scaleb(-decimals):,.{places}f}"

    def now() -> Instant:
        return Instant(time.time_ns() // 1_000_000)

    cfg = config.load(Role.ANALYST, require=False)
    settings = Settings.load()
    limits = Limits.from_thresholds(json.loads(THRESHOLDS.read_text()))
    u = universe.load()
    symbol = {a: u.records[a].symbol for a in u.feeds if a in u.records}  # display only
    stocks = sorted(symbol, key=lambda a: symbol[a])

    cs = chain.Settings.load()
    rpc = cs.client(cfg.secret)
    block = chain.pin_block(rpc, cs.chain_id, cs.block_tag)
    cash_feed = u.feeds[u.cash_leg]
    reading = cs.reader(rpc, block).latest_rounds({u.cash_leg: cash_feed})[u.cash_leg]
    cash_mark = valuation.mark(u.cash(), reading, chain.freshness(
        reading, cash_feed, block.timestamp, cs.staleness_margin_s, cs.sessions))
    if not cash_mark.check.passes:
        print(f"no cash mark, so no size to quote at: {cash_mark.check.reason}")
        return 1
    sell = nominal_sell(limits.nominal, cash_mark.price, u.cash_decimals)
    print(f"== nominal size ${_shown(limits.nominal)} at USDG's own mark "
          f"${dec(cash_mark.price.raw, cash_mark.price.decimals, 8)} (block {block.number}, "
          f"{cash_feed.name}) = {human(sell)} USDG, rounded down")
    print(f"   limits from config/thresholds.json: quote age {_shown(limits.max_age)}s, "
          f"swapImpactBps {_shown(limits.max_impact)} compared signed\n")

    quotes = settings.adapter(cfg.secret)
    seen = {a: quotes.quote(QuoteRequest(sell=sell, buy=a, buy_decimals=u.records[a].decimals))
            for a in stocks}
    as_of = now()
    verdicts = {a: tradeability(seen[a], sell, as_of, limits) for a in stocks}

    print(f"== 1. {len(stocks)} markable stocks quoted at {human(sell)} USDG, judged together at "
          f"{time.strftime('%H:%M:%SZ', time.gmtime(as_of.epoch_ms // 1000))}")
    print(f"   {'asset':6} {'bought':>22} {'USDG/token':>12} {'venue $/tok':>12} {'age s':>6} "
          f"{'swap bps':>8} {'price bps':>9} verdict")
    for a in stocks:
        o, t = seen[a], verdicts[a]
        if not o.ok:
            print(f"   {symbol[a]:6} {o.status.value}: {o.detail[:90]}  -> {t.verdict.value} [{t.rule}]")
            continue
        q = o.value
        per = Decimal(q.sell.raw).scaleb(-q.sell.decimals) / Decimal(q.buy.raw).scaleb(-q.buy.decimals)
        print(f"   {symbol[a]:6} {human(q.buy):>22} {per:>12,.4f} "
              f"{dec(q.buy_price.raw, q.buy_price.decimals, 4) if q.buy_price else 'null':>12} "
              f"{t.age_ms / 1000:>6.1f} {_shown(q.swap_impact) if q.swap_impact else 'null':>8} "
              f"{_shown(q.price_impact) if q.price_impact else 'null':>9} "
              f"{'tradeable' if t.verdict.passes else t.verdict.value} "
              f"{'' if t.rule is None else '[' + t.rule + ']'}")
    tally: dict[str, int] = {}
    for t in verdicts.values():
        key = "tradeable" if t.verdict.passes else f"{t.rule} ({t.verdict.value})"
        tally[key] = tally.get(key, 0) + 1
    differ = [symbol[a] for a in stocks if seen[a].ok
              and seen[a].value.swap_impact != seen[a].value.price_impact]
    print(f"   verdicts: {tally}; swapImpactBps and priceImpactBps differ on: {differ or 'none'}")
    sample = next((t for t in verdicts.values() if t.verdict.passes), None)
    if sample:
        print(f"   every verdict also carries executable={sample.executable.value}: "
              f"{sample.executable.reason}\n")

    print("== 2. negative impact, admitted")
    improved = [a for a in stocks if seen[a].ok and seen[a].value.swap_impact is not None
                and seen[a].value.swap_impact.raw < 0]
    for a in improved:
        print(f"   {symbol[a]}: {verdicts[a].verdict.reason}")
    if not improved:
        print("   no quote came back with negative impact at this moment")
    print()

    print("== 3. failures, each refused at the rule it tests, the other conditions passing")
    for a in (a for a in stocks if verdicts[a].rule == RULE_IMPACT):
        print(f"   impact, at the nominal size: {symbol[a]}: {verdicts[a].verdict.value} "
              f"{verdicts[a].verdict.reason}")
    first = stocks[0]
    wait = (limits.max_age.raw / 10 ** limits.max_age.decimals + 1
            - (now().epoch_ms - seen[first].fetch_time.epoch_ms) / 1000)
    if wait > 0:
        time.sleep(wait)
    late = tradeability(seen[first], sell, now(), limits)
    print(f"   quote-age: {symbol[first]}'s own quote, tradeable above, judged again after "
          f"waiting: {late.verdict.value} {late.verdict.reason}")
    tiny = Amount(1, u.cash_decimals, u.cash_leg)
    t = tradeability(quotes.quote(QuoteRequest(sell=tiny, buy=first, buy_decimals=18)), tiny, now(),
                     limits)
    print(f"   quote, the venue declining: {symbol[first]} at {human(tiny)} USDG: {t.verdict.value} "
          f"{t.verdict.reason}")
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # nothing listens here now
    dead = Settings(**{**settings.__dict__, "base_url": f"http://127.0.0.1:{port}", "attempts": 1})
    t = tradeability(dead.adapter(cfg.secret).quote(QuoteRequest(sell=sell, buy=first, buy_decimals=18)),
                     sell, now(), limits)
    print(f"   quote, no answer at all: {symbol[first]} via a refused local port: {t.verdict.value} "
          f"(is False: {t.verdict.value is False}) {t.verdict.reason[:170]}\n")

    print("== 4. F0.3.4 re-run: do swapImpactBps and priceImpactBps ever differ? The three widest")
    print("   impacts above, at 25000 USDG, read-only; the venue's own cap is maxPriceImpactBps")
    big = Amount.from_units("25000", u.cash_decimals, u.cash_leg)
    widest = sorted((a for a in stocks if seen[a].ok and seen[a].value.swap_impact is not None),
                    key=lambda a: -seen[a].value.swap_impact.raw)[:3]
    for a in widest:
        o = quotes.quote(QuoteRequest(sell=big, buy=a, buy_decimals=u.records[a].decimals))
        if not o.ok:
            print(f"   {symbol[a]}: {o.status.value}: {o.detail[:120]}")
            continue
        q = o.value
        print(f"   {symbol[a]}: swapImpactBps {_shown(q.swap_impact) if q.swap_impact else 'null'}, "
              f"priceImpactBps {_shown(q.price_impact) if q.price_impact else 'null'}, "
              f"maxPriceImpactBps {_shown(q.max_price_impact) if q.max_price_impact else 'null'}; "
              f"verdict {tradeability(o, big, now(), limits).verdict.value}")
    return 0


if __name__ == "__main__":
    import sys

    if sys.argv[1:] != ["--prove"]:
        print("usage: python -m fund.adapters.bankr_quote --prove")
        sys.exit(2)
    sys.exit(prove())
