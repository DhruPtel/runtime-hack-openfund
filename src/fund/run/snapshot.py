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

    PYTHONPATH=src python3 -m fund.run.snapshot                  build live, capture, replay the capture
    PYTHONPATH=src python3 -m fund.run.snapshot --prove          also re-read the chain at the same block
    PYTHONPATH=src python3 -m fund.run.snapshot --capture DIR    put the capture under DIR instead
    PYTHONPATH=src python3 -m fund.run.snapshot --replay DIR     rebuild from a capture, network refused

The snapshot is written to `fixtures/live/snapshot-<sha256>.json`, and the file
is exactly the hashed bytes. Every live build also records its capture (unit
1.9), as `<block>-<sha256[:12]>/` under `fixtures/live/captures/` by default.
Nothing under `fixtures/live/` is committed (.gitignore). A capture chosen for
the repository is taken with `--capture fixtures/snapshots`, where `make
replay` and the tests rebuild it.
"""

from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Callable

from fund import config
from fund.adapters import bankr_quote, cache, chain_4663, gecko, http
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
    """The three adapters' clients, and the chain reader's clock.
    `capturing_sources` makes the real ones, each recording what it hears; a
    replay and the offline test pass clients over recorded transports, and
    nothing else changes."""

    rpc: chain_4663.RpcClient
    corroborator: gecko.Gecko
    venue: bankr_quote.QuoteAdapter
    chain_clock: Callable[[], Instant] = chain_4663.wall_clock


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
               wallet: ChainAddress, block: BlockRef,
               clock: Callable[[], Instant] | None = None) -> ChainRead:
    read = settings.reader(rpc, block, clock)
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


def _config_sha256(config_dir: Path = CONFIG) -> dict[str, str]:
    return {name: hashlib.sha256((config_dir / name).read_bytes()).hexdigest()
            for name in CONFIG_FILES}


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
             limits: bankr_quote.Limits, wallet: ChainAddress,
             config_dir: Path = CONFIG) -> snapshot.Inputs:
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
        rules=_rules(settings, rule, limits, offchain.quote_size), config=_config_sha256(config_dir))


@dataclass(frozen=True)
class Built:
    snapshot: snapshot.Snapshot
    chain: ChainRead
    offchain: OffchainRead


def read_and_build(sources: Sources, *, settings: chain_4663.Settings, u: universe.Universe,
                   rule: valuation.DivergenceRule, limits: bankr_quote.Limits,
                   wallet: ChainAddress, clock: Callable[[], Instant] = now,
                   config_dir: Path = CONFIG) -> Built:
    """Pin a block, read everything, judge, and build: the whole live path.
    `config_dir` is whose files the snapshot names by hash: config/, or a
    capture's own copies on replay."""
    block = chain_4663.pin_block(sources.rpc, settings.chain_id, settings.block_tag)
    chain = read_chain(settings, sources.rpc, u, wallet, block, sources.chain_clock)
    offchain = read_offchain(chain, u, settings, limits, sources, clock)
    inputs = assemble(chain, offchain, u, settings, rule, limits, wallet, config_dir)
    return Built(snapshot.build(inputs, u), chain, offchain)


def write(snap: snapshot.Snapshot) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / f"snapshot-{snap.sha256}.json"
    path.write_bytes(snap.body)
    return path


# --- capture and replay (unit 1.9) -----------------------------------------------------------
#
# A live build records every answer at the transport and every clock read, with
# `adapters/cache.py`. A replay feeds them back through the same adapters, with
# the capture's own config, and refuses every connection. The live build's
# snapshot and the replay's must be the same bytes.

SNAPSHOTS = ROOT / "fixtures" / "snapshots"
REPLAY_URL = "replay://{}"   # a replayed RPC client's endpoint: nowhere; its transport is the capture


def capturing_sources(cfg: config.Config, settings: chain_4663.Settings, g: gecko.Settings,
                      q: bankr_quote.Settings
                      ) -> tuple[Sources, dict[str, cache.Recorder], Callable[[], Instant]]:
    """The live clients, each over a recording transport and clock, and the run's
    own recorded clock, which stamps `built_at`."""
    recorders = {"chain": cache.Recorder("chain", {n: cfg.secret(n) for n in settings.endpoints}),
                 "gecko": cache.Recorder("gecko", {gecko.ENDPOINT_NAME: g.base_url}),
                 "venue": cache.Recorder("venue", {bankr_quote.ENDPOINT_NAME: q.base_url}),
                 "run": cache.Recorder("run", {})}
    wire = bankr_quote.keyed_transport(q.user_agent, q.auth_header, cfg.secret(q.credential))
    sources = Sources(
        rpc=settings.client(cfg.secret, recorders["chain"].transport(
            http.urllib_transport(settings.user_agent))),
        corroborator=g.gecko(recorders["gecko"].transport(http.urllib_transport(g.user_agent)),
                             recorders["gecko"].clock(now)),
        venue=q.adapter(cfg.secret, recorders["venue"].transport(wire), recorders["venue"].clock(now)),
        chain_clock=recorders["chain"].clock(now))
    return sources, recorders, recorders["run"].clock(now)


def _iso(ms: int) -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ms // 1000))


def _code() -> dict[str, object]:
    """The commit that captured, and whether src/ or config/ differed from it."""
    try:
        head = subprocess.run(["git", "-C", str(ROOT), "rev-parse", "HEAD"], capture_output=True,
                              text=True, check=True).stdout.strip()
        dirty = subprocess.run(["git", "-C", str(ROOT), "status", "--porcelain", "--", "src", "config"],
                               capture_output=True, text=True, check=True).stdout.strip()
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None}
    return {"commit": head, "uncommitted_changes_in_src_or_config": bool(dirty)}


def write_capture(directory: Path, built: Built, recorders: dict[str, cache.Recorder],
                  u: universe.Universe, settings: chain_4663.Settings, g: gecko.Settings,
                  q: bankr_quote.Settings, started_ms: int) -> dict:
    """Write what the build heard, with the config it read, beside its snapshot.
    The config is read back and must hash to what the snapshot names."""
    config_files = {name: (CONFIG / name).read_bytes() for name in CONFIG_FILES}
    named = built.snapshot.document["inputs"]["config_sha256"]
    changed = [n for n, data in config_files.items() if hashlib.sha256(data).hexdigest() != named[n]]
    if changed:
        raise ValueError(f"config changed during the build, so no capture: {', '.join(changed)}")
    block = built.chain.block
    manifest = {
        "about": ("Every answer one live build heard, at the transport, and every reading of each "
                  "source's clock. `--replay` rebuilds the snapshot from these alone, with every "
                  "connection refused, and it must be byte-identical to snapshot.json."),
        "block": {"chain_id": block.chain_id, "number": block.number, "hash": block.hash,
                  "time": _iso(block.timestamp.epoch_ms)},
        "captured": {"started_at": _iso(started_ms), "finished_at": _iso(now().epoch_ms)} | _code(),
        "endpoints": ({n: "a declared credential: kept by name only" for n in settings.endpoints}
                      | {gecko.ENDPOINT_NAME: g.base_url, bankr_quote.ENDPOINT_NAME: q.base_url}),
        "pinned": {"issuer_registry": u.registry.sha256, "feed_directory": u.directory.sha256,
                   "held_in": "config/registry/, under their sha256, and not copied here"},
        "snapshot": {"sha256": built.snapshot.sha256, "bytes": len(built.snapshot.body)},
        "replay": f"PYTHONPATH=src python3 -m fund.run.snapshot --replay {directory.relative_to(ROOT)}",
    }
    return cache.write(directory, recorders=recorders, manifest=manifest, config_files=config_files,
                       snapshot_body=built.snapshot.body)


@dataclass(frozen=True)
class Replayed:
    snapshot: snapshot.Snapshot
    capture: cache.Capture
    unused: dict[str, tuple[int, int]]   # per source: (exchanges, clock readings) never asked for

    @property
    def expected(self) -> str:
        return self.capture.manifest["snapshot"]["sha256"]

    @property
    def same_snapshot(self) -> bool:
        return self.snapshot.sha256 == self.expected and self.snapshot.body == self.capture.snapshot_body

    @property
    def all_used(self) -> bool:
        return all(u == (0, 0) for u in self.unused.values())

    @property
    def identical(self) -> bool:
        """The captured snapshot, from an intact capture, every answer and reading used."""
        return self.same_snapshot and not self.capture.altered and self.all_used


def replay(directory: Path) -> Replayed:
    """Rebuild the snapshot a capture recorded, from its own answers, clocks and
    config, with every connection refused."""
    capture = cache.Capture(directory)
    with tempfile.TemporaryDirectory() as tmp:
        config_dir = Path(tmp)
        for name, data in capture.config_files().items():
            (config_dir / name).parent.mkdir(parents=True, exist_ok=True)
            (config_dir / name).write_bytes(data)
        registry_dir = config_dir / "registry"
        for pinned in json.loads((registry_dir / "pins.json").read_text())["inputs"].values():
            held = CONFIG / "registry" / pinned["file"]
            if not held.exists():
                raise FileNotFoundError(f"the capture references {pinned['file']}, which "
                                        f"config/registry/ no longer holds")
            shutil.copyfile(held, registry_dir / pinned["file"])
        # Pacing and backoff only set how long to wait between answers already on
        # disk. Nothing they decide reaches the snapshot, so a replay waits for none.
        settings = replace(chain_4663.Settings.load(config_dir / "chain.json",
                                                    config_dir / "thresholds.json",
                                                    config_dir / "sessions.json"),
                           min_interval_s=0, backoff_s=0)
        g = replace(gecko.Settings.load(config_dir / "gecko.json"), min_interval_s=0, backoff_s=0)
        q = replace(bankr_quote.Settings.load(config_dir / "quote.json"), min_interval_s=0, backoff_s=0)
        thresholds = json.loads((config_dir / "thresholds.json").read_text())
        u = universe.load(registry_dir)
        wallet = ChainAddress(settings.chain_id, json.loads(
            (config_dir / "mandate.json").read_text())["execution_wallet"])
        replayers = {"chain": capture.replayer("chain", {n: REPLAY_URL.format(n) for n in settings.endpoints}),
                     "gecko": capture.replayer("gecko", {gecko.ENDPOINT_NAME: g.base_url}),
                     "venue": capture.replayer("venue", {bankr_quote.ENDPOINT_NAME: q.base_url}),
                     "run": capture.replayer("run", {})}
        sources = Sources(
            rpc=settings.client(REPLAY_URL.format, replayers["chain"].transport()),
            corroborator=g.gecko(replayers["gecko"].transport(), replayers["gecko"].clock()),
            venue=q.adapter(REPLAY_URL.format, replayers["venue"].transport(),
                            replayers["venue"].clock()),
            chain_clock=replayers["chain"].clock())
        with cache.no_network():
            built = read_and_build(sources, settings=settings, u=u,
                                   rule=valuation.DivergenceRule.from_thresholds(thresholds),
                                   limits=bankr_quote.Limits.from_thresholds(thresholds),
                                   wallet=wallet, clock=replayers["run"].clock(),
                                   config_dir=config_dir)
    return Replayed(built.snapshot, capture, {s: r.unused() for s, r in replayers.items()})


def replay_main(directory: Path) -> int:
    """Rebuild from a capture, report it, and fail unless it is byte-identical."""
    try:
        r = replay(directory)
    except (cache.ReplayMiss, cache.NetworkDisabled) as stopped:
        print(f"== replay of {directory} stopped: {type(stopped).__name__}: {stopped}")
        return 1
    m = r.capture.manifest
    print(f"== replay of {directory.relative_to(ROOT) if directory.is_relative_to(ROOT) else directory}")
    print(f"   block {m['block']['number']} at {m['block']['time']}, captured "
          f"{m['captured']['started_at']} by commit {str(m['captured'].get('commit'))[:12]}")
    print("   every answer served from the capture, every clock read from its tape, every "
          "connection refused")
    served = ", ".join(f"{s} {m['exchanges'][s] - r.unused[s][0]}/{m['exchanges'][s]}"
                       for s in m["exchanges"])
    clocks = ", ".join(f"{s} {m['clock_readings'][s] - r.unused[s][1]}/{m['clock_readings'][s]}"
                       for s in m["clock_readings"])
    print(f"   exchanges answered: {served}")
    print(f"   clock readings used: {clocks}")
    path = write(r.snapshot)
    print(f"   rebuilt  {r.snapshot.sha256}  {path.relative_to(ROOT)}")
    print(f"   captured {r.expected}")
    print(f"   the captured snapshot, byte for byte: {'yes' if r.same_snapshot else 'NO'}")
    print("   capture files against the manifest: "
          + ("all match" if not r.capture.altered else "ALTERED: " + ", ".join(r.capture.altered)))
    print(f"   every answer and clock reading used: {'yes' if r.all_used else 'NO'}")
    print(f"   replay: {'PASS' if r.identical else 'FAIL'}")
    return 0 if r.identical else 1


def main(prove: bool = False, capture_to: Path = OUT / "captures") -> int:
    cfg = config.load(Role.ANALYST, require=False)
    settings = chain_4663.Settings.load()
    g, q = gecko.Settings.load(), bankr_quote.Settings.load()
    thresholds = json.loads((CONFIG / "thresholds.json").read_text())
    rule = valuation.DivergenceRule.from_thresholds(thresholds)
    limits = bankr_quote.Limits.from_thresholds(thresholds)
    u = universe.load()
    wallet = ChainAddress(settings.chain_id,
                          json.loads((CONFIG / "mandate.json").read_text())["execution_wallet"])
    sources, recorders, clock = capturing_sources(cfg, settings, g, q)
    started, started_ms = time.monotonic(), now().epoch_ms
    built = read_and_build(sources, settings=settings, u=u, rule=rule, limits=limits,
                           wallet=wallet, clock=clock)
    snap, chain, offchain, block = built.snapshot, built.chain, built.offchain, built.chain.block
    path = write(snap)
    directory = capture_to / f"{block.number}-{snap.sha256[:12]}"
    manifest = write_capture(directory, built, recorders, u, settings, g, q, started_ms)

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
    on_disk = sum(f.stat().st_size for f in directory.rglob("*") if f.is_file())
    print(f"\n== captured: {directory.relative_to(ROOT)}, {on_disk:,} bytes on disk")
    print(f"   exchanges {manifest['exchanges']}; clock readings {manifest['clock_readings']}; "
          f"strings masked by the credential redactor: {manifest['redaction']['strings_masked']}")
    replayed = replay(directory)
    print(f"   replayed from it, every connection refused: {replayed.snapshot.sha256} "
          f"(identical: {replayed.identical})")
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
    if len(args) == 2 and args[0] == "--replay":
        sys.exit(replay_main(Path(args[1]).resolve()))
    prove = "--prove" in args
    rest = [a for a in args if a != "--prove"]
    if rest and not (len(rest) == 2 and rest[0] == "--capture"):
        print("usage: python -m fund.run.snapshot [--prove] [--capture DIR]\n"
              "       python -m fund.run.snapshot --replay DIR")
        sys.exit(2)
    sys.exit(main(prove=prove, **({"capture_to": Path(rest[1]).resolve()} if rest else {})))
