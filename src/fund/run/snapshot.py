"""The live read for one snapshot: every adapter at one pinned block, handed to
`core/snapshot.build()`. Unit 1.6.

**Where the seam falls** (decided in 1.6, LESSONS 2026-09-18). `core/` makes no
network calls (CODEBASE §1), so something above it must call the adapters. That
layer is `run/`: CODEBASE §5 draws `run/cycle.py` calling `chain_4663`, `gecko`
and `bankr_quote` before `core/snapshot.build()`. `cycle.py` is 4.8's, and this
module is the read it will call. It is now the one place the adapters meet;
the 1.4 and 1.5 proofs composed them inside their own `prove()` functions, and
those stay as those units' proofs.

**The order of reads.**
1. The chain, all at one pinned block: feeds, series, beacon slots and the
   wallet's balances.
2. GeckoTerminal.
3. The quotes, last, so they are as young as they can be when they are judged
   at `built_at`.

The adapters' verdicts are made here, with the adapters' own functions:
freshness in open-session time (1.3), and tradeability (1.5). `core/` receives
them as arguments.

    PYTHONPATH=src python3 -m fund.run.snapshot            build live, write it, print a summary
    PYTHONPATH=src python3 -m fund.run.snapshot --prove    also rebuild at the same block

The snapshot is written to `fixtures/live/snapshot-<sha256>.json`, which is
never committed (.gitignore). The file is exactly the hashed bytes.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from fund import config
from fund.adapters import bankr_quote, chain_4663, gecko
from fund.core import snapshot, universe, valuation
from fund.core.types import (
    USD, Amount, AssetId, BlockRef, ChainAddress, Check, FetchStatus, Instant, Observation,
    Series, Source,
)
from fund.credentials import Role

ROOT = Path(__file__).resolve().parents[3]
CONFIG = ROOT / "config"
OUT = ROOT / "fixtures" / "live"
CONFIG_FILES = ("thresholds.json", "sessions.json", "chain.json", "gecko.json", "quote.json",
                "mandate.json", "registry/pins.json", "registry/feed_map.json")


@dataclass(frozen=True)
class ChainRead:
    """Everything read from the chain, at one block."""

    block: BlockRef
    readings: dict[AssetId, Observation]   # every mapped feed's latest round
    series: dict[AssetId, Series]          # each stock's rounds over the window
    beacons: dict[AssetId, Check]          # each stock's beacon cross-check, held ones included
    balances: dict[AssetId, Observation]   # the wallet: cash, gas, every registry asset


@dataclass(frozen=True)
class Sources:
    """The three adapters' clients. `live_sources` makes the real ones; a test
    passes clients over recorded-shape transports, and nothing else changes."""

    rpc: chain_4663.RpcClient
    corroborator: gecko.Gecko
    venue: bankr_quote.QuoteAdapter


def live_sources(cfg: config.Config, settings: chain_4663.Settings) -> Sources:
    return Sources(rpc=settings.client(cfg.secret), corroborator=gecko.Settings.load().gecko(),
                   venue=bankr_quote.Settings.load().adapter(cfg.secret))


@dataclass(frozen=True)
class OffchainRead:
    """What GeckoTerminal and the venue said, and when the quotes were judged."""

    corroborations: dict[AssetId, gecko.Corroboration]
    quote_size: Amount | None
    quotes: dict[AssetId, Observation]
    built_at: Instant


def now() -> Instant:
    return Instant(time.time_ns() // 1_000_000)


def stocks_of(u: universe.Universe) -> list[AssetId]:
    """The buy universe's candidates: registry stocks with a pinned feed."""
    return sorted(a for a in u.feeds if a in u.records)


def read_chain(settings: chain_4663.Settings, rpc: chain_4663.RpcClient, u: universe.Universe,
               wallet: ChainAddress, block: BlockRef) -> ChainRead:
    read = settings.reader(rpc, block)
    stocks = stocks_of(u)
    readings = read.latest_rounds(dict(u.feeds))
    def series_of(a: AssetId) -> Series:
        feed = u.feeds[a]
        if settings.sampling == "daily_close":
            return read.daily_closes(a, feed, days=settings.window_s // 86400, cut_s=settings.cut_s,
                                     closure=settings.sessions.get(feed.market_hours),
                                     max_rounds=settings.max_rounds,
                                     scale_break_ratio=settings.scale_break_ratio)
        return read.price_series(a, feed, window_s=settings.window_s, max_rounds=settings.max_rounds,
                                 scale_break_ratio=settings.scale_break_ratio)

    series = {a: series_of(a) for a in stocks}
    tokens = {u.cash_leg: u.cash_decimals, u.gas_asset: u.gas_decimals}
    tokens |= {a: r.decimals for a, r in u.records.items() if a.chain_id == block.chain_id}
    # Assets the registry dropped while held are still read: a holding never
    # leaves the book because its asset left the registry (1.8).
    tokens |= {a: c.decimals for a, c in u.carried.items() if a.chain_id == block.chain_id}
    balances = read.balances(wallet, tokens)
    # Beacons are read for the universe, and for any stock held outside it: an
    # unread beacon would put a held unmarkable stock at identity_in_doubt.
    held_outside = [a for a, b in balances.items() if a in u.records and a not in u.feeds
                    and b.ok and b.value.raw > 0]
    beacons = u.cross_check_beacons(read.beacon_slots(stocks + held_outside))  # disagreement raises
    return ChainRead(block, readings, series, beacons, balances)


def cash_mark(chain: ChainRead, u: universe.Universe, settings: chain_4663.Settings) -> valuation.Mark:
    feed = u.feeds[u.cash_leg]
    reading = chain.readings[u.cash_leg]
    fresh = chain_4663.freshness(reading, feed, chain.block.timestamp,
                                 settings.staleness_margin_s, settings.sessions)
    return valuation.mark(u.cash(), reading, fresh)


def read_offchain(chain: ChainRead, u: universe.Universe, settings: chain_4663.Settings,
                  limits: bankr_quote.Limits, sources: Sources,
                  clock: Callable[[], Instant] = now) -> OffchainRead:
    stocks = stocks_of(u)
    corroborations = sources.corroborator.corroborate(stocks)
    cash = cash_mark(chain, u, settings)
    size = (bankr_quote.nominal_sell(limits.nominal, cash.price, u.cash_decimals)
            if cash.check.passes else None)
    quotes: dict[AssetId, Observation] = {}
    for a in stocks:
        if size is None:
            quotes[a] = Observation(value=None, source=bankr_quote.SOURCE, source_time=None,
                                    fetch_time=clock(), block=None, status=FetchStatus.REFUSED,
                                    detail=f"not asked: no size, because the cash leg has no "
                                           f"mark ({cash.check.reason})")
        else:
            quotes[a] = sources.venue.quote(bankr_quote.QuoteRequest(
                sell=size, buy=a, buy_decimals=u.records[a].decimals))
    return OffchainRead(corroborations, size, quotes, clock())


def _config_sha256() -> dict[str, str]:
    return {name: hashlib.sha256((CONFIG / name).read_bytes()).hexdigest() for name in CONFIG_FILES}


def _rules(settings: chain_4663.Settings, rule: valuation.DivergenceRule,
           limits: bankr_quote.Limits, size: Amount | None) -> dict[str, str]:
    q = snapshot._q  # the snapshot's own exact decimal text
    spans = "; ".join(f"{label}: {c.describe()}" for label, c in sorted(settings.sessions.items()))
    return {
        "mark": ("Chainlink's answer for the feed pinned to the asset's address, never matched by "
                 "ticker. uiMultiplier() is not applied again: the documentation says the answer "
                 "already incorporates it, which is documented, not measured (F0.4.4)."),
        "freshness": (f"A mark is fresh while its newest round is at most the feed's heartbeat + "
                      f"{settings.staleness_margin_s} s old, counting only open-session time. "
                      f"Closed sessions, inferred from the feeds' own rounds: {spans}. A market "
                      f"holiday is not modelled and reads as stale. A round dated inside a closed "
                      f"span leaves freshness undetermined."),
        "corroboration": (f"GeckoTerminal's token-level price and 24h volume, independent of the "
                          f"venue. Below ${q(rule.min_volume_usd)} of 24h volume the asset is "
                          f"excluded. Above it, a divergence past {q(rule.max_bps)} bps is vetoed "
                          f"in an open session and recorded as a finding in a closed one. A "
                          f"missing corroboration is undetermined, never agreement."),
        "tradeability": (f"A venue quote for {q(size) if size else 'the nominal size'} USDG "
                         f"(${q(limits.nominal)} at USDG's own mark) succeeded, is at most "
                         f"{q(limits.max_age)} s old at built_at, and its swapImpactBps is known and "
                         f"at most {q(limits.max_impact)}, compared signed. A quote is a price, "
                         f"not a fill."),
        "timeline": ((f"One close a day over {settings.window_s // 86400} days to the pinned block: "
                      f"the round in effect at {settings.cut_s // 3600:02d}:"
                      f"{settings.cut_s % 3600 // 60:02d}Z, then the latest round. A day whose cut "
                      f"falls in a closed session has no close, and neither has a day with no new "
                      f"round since the previous close, such as a holiday: nothing is carried "
                      f"forward or interpolated. ")
                     if settings.sampling == "daily_close" else
                     f"The feed's own rounds over {settings.window_s // 86400} days to the pinned "
                     f"block, oldest first. ") +
                    (f"At most {settings.max_rounds} rounds are read. A series that falls short "
                     f"says so in its coverage, and its asset is not tradeable that snapshot."),
        "value": "Raw units times the mark, exact. No mark, no value, and never zero.",
    }


def assemble(chain: ChainRead, offchain: OffchainRead, u: universe.Universe,
             settings: chain_4663.Settings, rule: valuation.DivergenceRule,
             limits: bankr_quote.Limits, wallet: ChainAddress) -> snapshot.Inputs:
    """The adapters' verdicts, made here, and everything handed to core as data."""
    block = chain.block
    at_s = block.timestamp.epoch_ms // 1000
    closed = tuple(sorted(label for label, c in settings.sessions.items() if c.contains(at_s)))
    margin, sessions = settings.staleness_margin_s, settings.sessions

    def fresh(asset: AssetId) -> Check:
        feed, series = u.feeds[asset], chain.series.get(asset)
        if series is not None and series.newest is not None:
            return chain_4663.series_freshness(series, feed, block.timestamp, margin, sessions)
        return chain_4663.freshness(chain.readings[asset], feed, block.timestamp, margin, sessions)

    stocks = []
    for a in stocks_of(u):
        feed = u.feeds[a]
        judged = (bankr_quote.tradeability(offchain.quotes[a], offchain.quote_size,
                                           offchain.built_at, limits)
                  if offchain.quote_size is not None else None)
        c = offchain.corroborations[a]
        stocks.append(snapshot.StockInputs(
            asset=u.stock(a, chain.beacons[a]), reading=chain.readings[a], fresh=fresh(a),
            series=chain.series[a], closed_session=feed.market_hours in closed,
            corroboration=c.price, volume=c.volume_24h, independent=gecko.INDEPENDENT_OF_VENUE,
            quote=offchain.quotes[a],
            tradeable=judged.verdict if judged else Check(None, "[quote] no quote was asked for"),
            tradeable_rule=judged.rule if judged else bankr_quote.RULE_QUOTE,
            executable=bankr_quote.NOT_EVIDENCE_OF_EXECUTION))

    def marked(asset) -> snapshot.MarkedInputs:
        return snapshot.MarkedInputs(asset=asset, reading=chain.readings[asset.id],
                                     fresh=chain_4663.freshness(chain.readings[asset.id],
                                                                u.feeds[asset.id], block.timestamp,
                                                                margin, sessions))

    def decimals(a: AssetId) -> int:
        return u.records[a].decimals if a in u.records else u.carried[a].decimals

    held_outside = {a: u.held_asset(a, decimals(a),
                                    chain.beacons.get(a, Check(None, "not read: the balance was "
                                                                     "not read either")))
                    for a, b in chain.balances.items()
                    if (a in u.records or a in u.carried) and a not in u.feeds
                    and (not b.ok or b.value.raw > 0)}
    return snapshot.Inputs(
        block=block, built_at=offchain.built_at, stocks=tuple(stocks), cash=marked(u.cash()),
        gas=marked(u.gas()), wallet=wallet, balances=chain.balances, held_outside=held_outside,
        closed_sessions=closed, divergence_rule=rule,
        rules=_rules(settings, rule, limits, offchain.quote_size), config=_config_sha256())


@dataclass(frozen=True)
class Built:
    snapshot: snapshot.Snapshot
    chain: ChainRead
    offchain: OffchainRead


def read_and_build(sources: Sources, *, settings: chain_4663.Settings, u: universe.Universe,
                   rule: valuation.DivergenceRule, limits: bankr_quote.Limits,
                   wallet: ChainAddress, clock: Callable[[], Instant] = now) -> Built:
    """Pin a block, read everything, judge, and build: the whole live path."""
    block = chain_4663.pin_block(sources.rpc, settings.chain_id, settings.block_tag)
    chain = read_chain(settings, sources.rpc, u, wallet, block)
    offchain = read_offchain(chain, u, settings, limits, sources, clock)
    return Built(snapshot.build(assemble(chain, offchain, u, settings, rule, limits, wallet), u),
                 chain, offchain)


def write(snap: snapshot.Snapshot) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"snapshot-{snap.sha256}.json"
    path.write_bytes(snap.body)
    return path


def main(prove: bool = False) -> int:
    cfg = config.load(Role.ANALYST, require=False)
    settings = chain_4663.Settings.load()
    thresholds = json.loads((CONFIG / "thresholds.json").read_text())
    rule = valuation.DivergenceRule.from_thresholds(thresholds)
    limits = bankr_quote.Limits.from_thresholds(thresholds)
    u = universe.load()
    wallet = ChainAddress(settings.chain_id,
                          json.loads((CONFIG / "mandate.json").read_text())["execution_wallet"])
    sources = live_sources(cfg, settings)
    started = time.monotonic()
    built = read_and_build(sources, settings=settings, u=u, rule=rule, limits=limits,
                           wallet=wallet)
    snap, chain, offchain, block = built.snapshot, built.chain, built.offchain, built.chain.block
    path = write(snap)

    doc = snap.document
    oldest = max((offchain.built_at.epoch_ms - o.fetch_time.epoch_ms)
                 for o in offchain.quotes.values()) / 1000
    points = sum(e["timeline"]["rounds"] for e in doc["assets"])
    print(f"== snapshot at block {block.number} ({doc['block']['time']}), built_at {doc['built_at']}")
    print(f"   {path.relative_to(ROOT)}")
    print(f"   sha256 {snap.sha256}; {len(snap.body):,} bytes; {len(doc['assets'])} assets, "
          f"{points:,} rounds of history; closed sessions at the block: "
          f"{doc['block']['closed_sessions'] or 'none'}")
    print(f"   read and built in {time.monotonic() - started:.1f}s; oldest quote {oldest:.1f}s "
          f"old at built_at")
    print(f"   counts: {doc['summary']['counts']}")
    print(f"   findings: {len(doc['summary']['findings'])}; holdings: "
          + ", ".join(f"{h['asset']['symbol']} {h['balance']} = ${h['value_usd']}"
                      for h in doc["holdings"]))
    print(f"   outside the universe: {doc['outside_universe']['count']} registry assets with no feed")
    for symbol, status, why in doc["summary"]["assets"]:
        print(f"     {symbol:6} {status:24} {why or ''}")
    if not prove:
        return 0

    print("\n== the same build at the same block: the chain re-read, fresh, at "
          f"{block.hash[:18]}…, with the same offchain answers")
    again = read_chain(settings, sources.rpc, u, wallet, block)
    def content(o: Observation) -> tuple:  # everything but when it was fetched
        return o.status, o.value, o.source_time, o.source_ref, o.block
    same_chain = (all(content(again.readings[a]) == content(chain.readings[a]) for a in chain.readings)
                  and all([content(p) for p in again.series[a].points]
                          == [content(p) for p in chain.series[a].points] for a in chain.series)
                  and all(content(again.balances[a]) == content(chain.balances[a])
                          for a in chain.balances))
    rebuilt = snapshot.build(assemble(again, offchain, u, settings, rule, limits, wallet), u)
    print(f"   every chain value identical on re-read, fetch times apart: {same_chain}")
    print(f"   first  {snap.sha256}\n   second {rebuilt.sha256}\n   identical: "
          f"{rebuilt.sha256 == snap.sha256 and rebuilt.body == snap.body}")
    target = stocks_of(u)[0]
    c = offchain.corroborations[target]
    if c.price.ok:
        nudged = replace(c.price, value=replace(c.price.value, raw=c.price.value.raw + 1))
        changed = replace(offchain, corroborations={**offchain.corroborations,
                                                    target: replace(c, price=nudged)})
        other = snapshot.build(assemble(chain, changed, u, settings, rule, limits, wallet), u)
        print(f"   one GeckoTerminal price moved by one unit in its last place: {other.sha256} "
              f"(different: {other.sha256 != snap.sha256})")
    return 0


if __name__ == "__main__":
    import sys

    args = sys.argv[1:]
    if args not in ([], ["--prove"]):
        print("usage: python -m fund.run.snapshot [--prove]")
        sys.exit(2)
    sys.exit(main(prove=args == ["--prove"]))
