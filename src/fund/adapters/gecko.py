"""GeckoTerminal: the corroborating USD price, and the 24h volume that tiers it. Unit 1.4.

Chainlink marks the book (PLAN §11); this is the second opinion the divergence
check compares it with. It returns Observations, never bare numbers, and
imports no other adapter: its transport is `adapters/http.py`.

What the record requires, and where each requirement is met:

- **Independent of the venue.** GeckoTerminal prices all 32 addressable stock
  tokens off real AMM pools (findings F0.4.2-F0.4.3). The fund's execution is
  Bankr RFQ, so this is a cross-source check. The Bankr quote is never the
  corroborator: its price is the venue's own (F0.3.5), and the venue applies
  the multiplier itself, which would make the comparison circular (F0.4.4).
- **Matched by address, never by symbol.** Each entry's `attributes.address`
  is compared with the pinned `(chain_id, address)`. A counterfeit chooses its
  own ticker (F0.8.3), so a symbol never selects an entry.
- **The volume the tier was set on.** The $1M line was decided on F0.4.5's
  numbers: token-level `volume_usd.h24` from the batch tokens endpoint, as
  `probes/feed.py` read it. This reads the same field from the same endpoint.
  That endpoint lists only one of a token's pools in `top_pools`, so the pool
  count here is a floor.
- **Exact.** Prices and volumes arrive as decimal strings and are parsed with no
  float. A zero or negative price is refused, since it cannot be compared with.
- **Absent is not agreement.** A token missing from a 200 is ABSENT, a field
  that is null is ABSENT, a failed request is UNREACHABLE, and a body that
  cannot be read is REFUSED. None of them carries a value, so none can read as
  a divergence of zero.
- **No source time.** The response gives no time for its price, and it may come
  from an edge cache up to 60 s old (`Cache-Control: max-age=30, s-maxage=60`,
  measured). So `source_time` is None, and the response's Date and cache status
  go in the detail.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from fund.adapters import http
from fund.core.types import (
    USD, AssetId, FetchStatus, Fixed, Instant, Observation, Price, Source,
)

SYSTEM = "geckoterminal"
ENDPOINT_NAME = "GECKOTERMINAL"
INDEPENDENT_OF_VENUE = True  # pool prices, not the venue's RFQ (F0.4.2-F0.4.3)

GECKO_CONFIG = Path(__file__).resolve().parents[3] / "config" / "gecko.json"


@dataclass(frozen=True)
class Corroboration:
    """What GeckoTerminal said about one asset: a USD price and a 24h USD volume,
    each an Observation that may be ABSENT, REFUSED or UNREACHABLE."""

    asset: AssetId
    price: Observation
    volume_24h: Observation


@dataclass(frozen=True)
class Batch:
    """One request and what came of it: the reply, or the transport's refusal."""

    assets: tuple[AssetId, ...]
    fetch_time: Instant
    reply: http.Reply | None
    failure: str | None


def batch_path(network: str, assets: Sequence[AssetId]) -> str:
    return f"/networks/{network}/tokens/multi/" + ",".join(a.address for a in assets)


def _source(network: str, asset: AssetId) -> Source:
    return Source(SYSTEM, f"networks/{network}/tokens/{asset.address}")


def _provenance(reply: http.Reply) -> str:
    cache = reply.headers.get("cf-cache-status", "no cache status")
    age = reply.headers.get("age")
    return (f"response Date {reply.headers.get('date', 'absent')}, edge cache {cache}"
            + (f", age {age}s" if age else ""))


def parse(batch: Batch, network: str) -> dict[AssetId, Corroboration]:
    """Every requested asset gets a Corroboration, whatever came back."""
    def every(status: FetchStatus, detail: str) -> dict[AssetId, Corroboration]:
        def one(asset):
            return Observation(value=None, source=_source(network, asset), source_time=None,
                               fetch_time=batch.fetch_time, block=None, status=status, detail=detail)
        return {a: Corroboration(a, one(a), one(a)) for a in batch.assets}

    if batch.reply is None:
        return every(FetchStatus.UNREACHABLE, batch.failure or "no reply")
    try:
        data = json.loads(batch.reply.body)["data"]
        if not isinstance(data, list):
            raise ValueError("`data` is not a list")
    except (ValueError, KeyError, TypeError) as error:
        return every(FetchStatus.REFUSED, f"a 200 whose body is not the batch shape: {error}")

    provenance = _provenance(batch.reply)
    entries: dict[str, list[dict]] = {}
    for entry in data:
        attributes = (entry or {}).get("attributes") or {}
        address = str(attributes.get("address", "")).lower()
        if str(entry.get("id", "")).lower() == f"{network}_{address}":
            entries.setdefault(address, []).append(entry)

    out = {}
    for asset in batch.assets:
        source = _source(network, asset)

        def observe(value=None, status=FetchStatus.OK, detail=provenance):
            return Observation(value=value, source=source, source_time=None,
                               fetch_time=batch.fetch_time, block=None, status=status,
                               detail=detail)

        found = entries.get(asset.address, [])
        if len(found) != 1:
            why = ("GeckoTerminal answered and did not list this address" if not found else
                   f"{len(found)} entries for one address: which one prices it is unknowable")
            status = FetchStatus.ABSENT if not found else FetchStatus.REFUSED
            out[asset] = Corroboration(asset, observe(status=status, detail=f"{why}; {provenance}"),
                                       observe(status=status, detail=f"{why}; {provenance}"))
            continue
        attributes = found[0]["attributes"]
        pools = len(((found[0].get("relationships") or {}).get("top_pools") or {}).get("data") or [])
        where = (f"token-level, over the pools GeckoTerminal indexes; the batch lists {pools} of "
                 f"them, a floor; {provenance}")
        out[asset] = Corroboration(
            asset,
            _read(attributes.get("price_usd"), lambda t: Price.parse(t, asset, USD), "price_usd",
                  observe, where, positive=True),
            _read((attributes.get("volume_usd") or {}).get("h24"), lambda t: Fixed.parse(t, USD),
                  "volume_usd.h24", observe, where, positive=False))
    return out


def _read(text, convert: Callable[[str], object], field_name: str, observe: Callable,
          where: str, *, positive: bool) -> Observation:
    if text is None:
        return observe(status=FetchStatus.ABSENT, detail=f"{field_name} is null; {where}")
    try:
        value = convert(str(text))
    except (ValueError, TypeError) as error:
        return observe(status=FetchStatus.REFUSED, detail=f"{field_name} {text!r}: {error}")
    if value.raw < 0 or (positive and value.raw == 0):
        return observe(status=FetchStatus.REFUSED, detail=f"{field_name} {text!r} is not a usable "
                                                          f"{'price' if positive else 'volume'}")
    return observe(value=value, detail=f"{field_name}; {where}")


class Gecko:
    """Batch token reads for one network, over the shared client."""

    def __init__(self, client: http.HttpClient, *, network: str, batch_size: int,
                 clock: Callable[[], Instant]):
        self.client, self.network, self.batch_size, self.clock = client, network, batch_size, clock

    def fetch(self, assets: Sequence[AssetId]) -> list[Batch]:
        batches = []
        for start in range(0, len(assets), self.batch_size):
            chunk = tuple(assets[start:start + self.batch_size])
            try:
                reply = self.client.send(path=batch_path(self.network, chunk))
                batches.append(Batch(chunk, self.clock(), reply, None))
            except http.Unavailable as error:
                batches.append(Batch(chunk, self.clock(), None, str(error)))
        return batches

    def corroborate(self, assets: Sequence[AssetId]) -> dict[AssetId, Corroboration]:
        out: dict[AssetId, Corroboration] = {}
        for batch in self.fetch(assets):
            out.update(parse(batch, self.network))
        return out


@dataclass(frozen=True)
class Settings:
    base_url: str
    network: str
    batch_size: int
    timeout_s: float
    attempts: int
    backoff_s: float
    min_interval_s: float
    user_agent: str

    @classmethod
    def load(cls, path: Path = GECKO_CONFIG) -> Settings:
        c = json.loads(path.read_text())
        return cls(base_url=c["base_url"], network=c["network"], batch_size=c["batch_size"],
                   timeout_s=c["request_timeout_seconds"], attempts=c["attempts"],
                   backoff_s=c["backoff_seconds"], min_interval_s=c["min_request_interval_ms"] / 1000,
                   user_agent=c["user_agent"])

    def gecko(self, transport: http.Transport | None = None,
              clock: Callable[[], Instant] | None = None) -> Gecko:
        client = http.HttpClient([http.Endpoint(ENDPOINT_NAME, self.base_url)],
                                 timeout_s=self.timeout_s, attempts=self.attempts,
                                 backoff_s=self.backoff_s, min_interval_s=self.min_interval_s,
                                 transport=transport or http.urllib_transport(self.user_agent))
        return Gecko(client, network=self.network, batch_size=self.batch_size,
                     clock=clock or (lambda: Instant(time.time_ns() // 1_000_000)))


# --- the live proof: `python -m fund.adapters.gecko --prove` -----------------------------

#: F0.4.5's liquid-name case, as probe 0.4 recorded it (`probes/out/feed.json`,
#: block 66354932): AMZN's feed answer and GeckoTerminal's price and volume.
RECORDED_AMZN = {"block": 66354932, "feed_answer": 25260000000, "round": "18446744073709552407",
                 "updated_at": 1789745950, "gecko_price": "265.87982073",
                 "gecko_volume": "2193251.17210313"}


def prove() -> int:
    """1.4 live and read-only: every markable asset's mark, corroboration,
    divergence, volume and tier verdict at one pinned block. It composes the
    chain adapter, this adapter and `core/valuation` the way 1.6's snapshot
    builder will; the chain import is the proof's own, inside this function.
    Spends nothing."""
    from decimal import Decimal

    from fund import config
    from fund.adapters import chain_4663 as chain
    from fund.core import universe, valuation
    from fund.core.types import Amount, BlockRef, Check, UniverseStatus
    from fund.credentials import Role

    def usd(quantity, places=4) -> str:  # display only
        return f"{Decimal(quantity.raw).scaleb(-quantity.decimals):,.{places}f}"

    cfg = config.load(Role.ANALYST, require=False)
    cs, gs = chain.Settings.load(), Settings.load()
    rule = valuation.DivergenceRule.from_thresholds(json.loads(chain.THRESHOLDS.read_text()))
    margin, sessions = cs.staleness_margin_s, cs.sessions
    u = universe.load()
    wallet = chain.ChainAddress(cs.chain_id, json.loads(
        (chain.CHAIN_CONFIG.parent / "mandate.json").read_text())["execution_wallet"])
    symbol = {a: (u.records[a].symbol if a in u.records else f.name.split(" / ")[0])
              for a, f in u.feeds.items()}  # display only
    rpc = cs.client(cfg.secret)
    block = chain.pin_block(rpc, cs.chain_id, cs.block_tag)
    read = cs.reader(rpc, block)
    print(f"== pinned block {block.number} at {chain._iso(block.timestamp)}; every chain read is at it")
    print(f"   rule: veto past {usd(rule.max_bps, 0)} bps above ${usd(rule.min_volume_usd, 0)} of 24h "
          f"volume, excluded below it (config/thresholds.json)\n")

    rounds = read.latest_rounds(dict(u.feeds))
    fresh = {a: chain.freshness(rounds[a], f, block.timestamp, margin, sessions)
             for a, f in u.feeds.items()}

    print("== 1. the closed session, and what it does to freshness at this block")
    for label, closure in sessions.items():
        print(f"   {label}: closed {closure.describe()}, inferred from the feeds' own rounds "
              f"(config/sessions.json; evidence: chain_4663 --sessions)")
        inside = closure.contains(block.timestamp.epoch_ms // 1000)
        print(f"   the pinned block is {'inside' if inside else 'outside'} that span")
    equity = [a for a, f in u.feeds.items() if f.market_hours in sessions]
    wall = {a: chain.freshness(rounds[a], u.feeds[a], block.timestamp, margin) for a in equity}
    print(f"   {len(equity)} equity feeds at the block: fresh {sum(fresh[a].passes for a in equity)} "
          f"counting open session, fresh {sum(wall[a].passes for a in equity)} counting every second")
    closure = next(iter(sessions.values()))
    last_minute = ((block.timestamp.epoch_ms // 1000 - chain.MONDAY_OFFSET_S) // chain.WEEK_S
                   * chain.WEEK_S + chain.MONDAY_OFFSET_S + closure.end_s - 60)
    later = chain.Instant.from_seconds(last_minute)
    if later > block.timestamp:
        what_if = {a: (chain.freshness(rounds[a], u.feeds[a], later, margin, sessions),
                       chain.freshness(rounds[a], u.feeds[a], later, margin)) for a in equity}
        print(f"   the same real readings judged at {chain._iso(later)}, the span's last minute, had no "
              f"round come (a what-if): fresh {sum(v[0].passes for v in what_if.values())} counting open "
              f"session, fresh {sum(v[1].passes for v in what_if.values())} counting every second")
    sample = equity[0]
    print(f"   e.g. {symbol[sample]}: {fresh[sample].reason}\n")

    stocks = sorted((a for a in u.feeds if a in u.records), key=lambda a: symbol[a])
    beacon = Check(None, "not read by this proof; chain_4663 --prove reads all 35")
    assets = {a: u.stock(a, beacon) for a in stocks}
    marks = {a: valuation.mark(assets[a], rounds[a], fresh[a]) for a in stocks}
    g = gs.gecko()
    batches = g.fetch(stocks)
    corroborated = {}
    for b in batches:
        corroborated.update(parse(b, g.network))
    checks = {a: valuation.cross_check(marks[a], corroborated[a].price, corroborated[a].volume_24h,
                                       rule, independent=INDEPENDENT_OF_VENUE) for a in stocks}

    print(f"== 2. {len(stocks)} markable stocks: Chainlink mark, GeckoTerminal corroboration, "
          f"divergence, 24h volume, tier")
    print(f"   {'asset':6} {'mark (USD)':>12} {'gecko (USD)':>14} {'div bps':>9} {'24h vol (USD)':>17} "
          f"{'tier':10} verdict")
    for a in stocks:
        c, m = checks[a], marks[a]
        seen = corroborated[a]
        print(f"   {symbol[a]:6} {usd(m.price) if m.price else '-':>12} "
              f"{usd(seen.price.value) if seen.price.ok else seen.price.status.value:>14} "
              f"{usd(c.divergence, 2) if c.divergence else '-':>9} "
              f"{usd(seen.volume_24h.value, 0) if seen.volume_24h.ok else seen.volume_24h.status.value:>17} "
              f"{c.tier or '-':10} {'pass' if c.verdict.passes else c.verdict.value} "
              f"{'' if c.rule is None else '[' + c.rule + ']'}")
    tally: dict[str, int] = {}
    for c in checks.values():
        key = "pass" if c.verdict.passes else f"{c.rule} ({c.verdict.value})"
        tally[key] = tally.get(key, 0) + 1
    print(f"   verdicts: {tally}; independent of the venue: {INDEPENDENT_OF_VENUE} "
          f"(pool prices, not Bankr's RFQ); corroborating responses: "
          + "; ".join(f"{len(b.assets)} assets, {'HTTP ' + str(b.reply.status) if b.reply else b.failure}"
                      for b in batches) + "\n")

    print("== 3. the veto on a liquid name")
    live = [a for a in stocks if checks[a].rule == valuation.RULE_DIVERGENCE]
    for a in live:
        print(f"   live: {symbol[a]}: {checks[a].verdict.reason}")
    if not live:
        print("   live: no name above the line diverges past the limit at this block")
    amzn = next(a for a in stocks if symbol[a] == "AMZN")
    r = RECORDED_AMZN
    old_block = BlockRef(cs.chain_id, r["block"])
    old_reading = Observation(
        value=Price(r["feed_answer"], 8, amzn, USD),
        source=Source("chainlink-feed", u.feeds[amzn].proxy.address),
        source_time=Instant.from_seconds(r["updated_at"]), fetch_time=Instant.from_seconds(r["updated_at"]),
        block=old_block, status=FetchStatus.OK, source_ref=r["round"])
    old_source = _source(gs.network, amzn)
    old_price = Observation(value=Price.parse(r["gecko_price"], amzn, USD), source=old_source,
                            source_time=None, fetch_time=old_reading.fetch_time, block=None,
                            status=FetchStatus.OK, detail="probe 0.4's capture")
    old_volume = Observation(value=Fixed.parse(r["gecko_volume"], USD), source=old_source,
                             source_time=None, fetch_time=old_reading.fetch_time, block=None,
                             status=FetchStatus.OK, detail="probe 0.4's capture")
    recorded = valuation.cross_check(
        valuation.mark(assets[amzn], old_reading, Check(True, "fresh when probe 0.4 read it")),
        old_price, old_volume, rule, independent=True)
    print(f"   recorded (probe 0.4, block {r['block']}, F0.4.5): AMZN feed 252.60 against GeckoTerminal "
          f"{r['gecko_price']} on ${usd(old_volume.value, 0)}: tier {recorded.tier}; "
          f"{recorded.verdict.reason}\n")

    print("== 4. cash and gas, marked by their own feeds, and the fund wallet's balances")
    extra = next((a for a in u.records if a not in u.feeds and u.records[a].symbol == "CRM"), None)
    held = read.balances(wallet, {u.gas_asset: u.gas_decimals, u.cash_leg: u.cash_decimals,
                                  **({extra: 18} if extra else {})})
    for asset_, status, reason in ((u.cash(), UniverseStatus.NOT_A_STOCK, "cash leg"),
                                   (u.gas(), UniverseStatus.NOT_A_STOCK, "gas")):
        the_mark = valuation.mark(asset_, rounds[asset_.id], fresh[asset_.id])
        holding = valuation.value_holding(asset_, held[asset_.id], the_mark, universe_status=status,
                                          universe_reason=reason)
        print(f"   {asset_.symbol:4} mark ${usd(the_mark.price, 8) if the_mark.price else '-'} "
              f"({u.feeds[asset_.id].name}, {fresh[asset_.id].reason}); balance "
              f"{usd(held[asset_.id].value, asset_.decimals) if held[asset_.id].ok else '-'}; value "
              f"${usd(holding.value, 6) if holding.value is not None else '-'} "
              f"{holding.value_reason or ''}")
    print()

    print("== 5. an asset with no feed, carried as a holding")
    if extra is None:
        print("   no registry asset named CRM without a feed; nothing to show")
    else:
        slots = read.beacon_slots([extra])
        crm = u.stock(extra, u.cross_check_beacons(slots)[extra])
        admitted = u.admission(crm)
        no_mark = valuation.mark(crm, None, Check(None, "no feed to read"))
        real = valuation.value_holding(crm, held[extra], no_mark, universe_status=admitted.universe_status,
                                       universe_reason=admitted.decision.reason)
        constructed = Observation(value=Amount.from_units("1", crm.decimals, extra),
                                  source=Source("constructed", extra.address), source_time=None,
                                  fetch_time=held[extra].fetch_time, block=None, status=FetchStatus.OK,
                                  detail="constructed for this proof: the wallet holds no CRM")
        one = valuation.value_holding(crm, constructed, no_mark, universe_status=admitted.universe_status,
                                      universe_reason=admitted.decision.reason)
        print(f"   CRM {extra.address}: identity {crm.identity.value}, markability {crm.markability.value}, "
              f"beacon {crm.beacon.value}; universe status {admitted.universe_status.value}")
        print(f"   live balance {held[extra].value.raw if held[extra].ok else held[extra].status.value} "
              f"raw: value {real.value}; {real.value_reason}")
        print(f"   constructed balance of 1 CRM: value {one.value}; {one.value_reason}\n")

    print("== 6. absent corroboration: the first live response, with one token's entry removed")
    first = next((b for b in batches if b.reply is not None), None)
    target = next((a for a in stocks if symbol[a] == "AAPL"), stocks[0])
    if first is None or target not in first.assets:
        print("   no live response carrying AAPL to edit")
        return 0
    body = json.loads(first.reply.body)
    body["data"] = [e for e in body["data"]
                    if str((e.get("attributes") or {}).get("address", "")).lower() != target.address]
    edited = Batch(first.assets, first.fetch_time, http.Reply(200, json.dumps(body).encode(),
                                                              first.reply.headers), None)
    missing = parse(edited, g.network)[target]
    gone = valuation.cross_check(marks[target], missing.price, missing.volume_24h, rule,
                                 independent=INDEPENDENT_OF_VENUE)
    print(f"   {symbol[target]}: corroboration {missing.price.status.value}; divergence {gone.divergence}; "
          f"verdict {gone.verdict.value} (is False: {gone.verdict.value is False}); {gone.verdict.reason}")
    return 0


if __name__ == "__main__":
    import sys

    if sys.argv[1:] != ["--prove"]:
        print("usage: python -m fund.adapters.gecko --prove")
        sys.exit(2)
    sys.exit(prove())
