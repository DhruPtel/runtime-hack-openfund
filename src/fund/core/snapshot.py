"""One frozen snapshot per cycle: what the fund knows, pinned to one block. Unit 1.6.

Every analyst reads these same bytes (PLAN §2 invariant 2). If two analysts
reasoned from different data, their conflicting implicit assumptions would reach
a trade. So the snapshot is one document, content-hashed, and the file on disk
is exactly the bytes that are hashed and loaded into each prompt.

**It is written to be read.** Field names and structure are part of the product.
A reader should be able to open an asset's entry and see what the fund knows:
- prices and amounts are exact decimal text, never floats;
- times are ISO-8601 UTC;
- `null` means unknown and never zero;
- every verdict is `{"verdict": true | false | null, "reason": "..."}`, and
  `null` means undetermined, which blocks.

The 1.1 types' canonical encoding tags every object and repeats full provenance
on every series point: 831 bytes a point, against 37 for a `[time, price]`
pair. The typed objects are therefore this module's input, and a readable
document is its output (LESSONS 2026-09-18).

**What an asset entry holds.** Keys are sorted in the bytes:
- `asset`: symbol, name, address, decimals, ISIN;
- `identity`, `standing`, `beacon`, `markability`: 1.2's four rules, kept
  separate;
- `mark`: the Chainlink price, its round, and whether it is fresh;
- `corroboration`: GeckoTerminal's price and volume, the divergence, the tier,
  and the session;
- `quote`: the venue's price at the nominal size, its age and impact,
  `tradeable`, and `executable`, which is always undetermined;
- `findings`: what was seen and judged rather than acted on. Today that is a
  closed-session divergence past the limit an open session would veto at.
  Smaller divergences are not findings: the `corroboration` block already
  carries every divergence and its session (DECISION, LESSONS 2026-09-18);
- `status`: the first rule that did not pass, or `tradeable`;
- `timeline`: the price series, oldest first, as `[updated_at, price_usd]`,
  with its coverage stated. A short series says so; nothing is truncated
  silently.

**Chain values carry their block and not their fetch time.** A value read at a
pinned block is fixed by the block. So a re-read of the chain at the same block
gives the same snapshot. Offchain values, GeckoTerminal and the quotes, carry
the time they were fetched, because that is the only time they have.

**What the builder refuses.** It raises; a snapshot is never partly right:
- a chain value read at another block (`block-pin`);
- a chain value dated after the pinned block (`after-pin`);
- a series whose newest round is not the round read as the mark
  (`series-head`);
- two readings for one asset (`duplicate`).

A beacon disagreement raises earlier, in `core/universe.py`.

`core/` imports nothing from `adapters/`. Every reading, and every verdict an
adapter makes (freshness, tradeability), arrives as an argument.
"""

from __future__ import annotations

import hashlib
import json
import time
from dataclasses import dataclass
from typing import Any, Mapping

from . import valuation
from .types import (
    MAX_SAFE_JSON_INT, Amount, Asset, AssetId, AssetKind, BlockRef, ChainAddress, Check,
    FetchStatus, Fixed, Instant, Observation, Price, Quote, Series, UniverseStatus,
)
from .universe import Universe

SCHEMA = "openfund.snapshot/1"

RULE_BLOCK_PIN = "block-pin"
RULE_AFTER_PIN = "after-pin"
RULE_SERIES_HEAD = "series-head"
RULE_DUPLICATE = "duplicate"

#: The order an asset's rules run in. Its status is the first that does not pass.
ORDER = ("identity", "standing", "beacon", "markability", "mark", "corroboration",
         "corroborator-line", "divergence", "tradeability")


class SnapshotRefused(Exception):
    def __init__(self, rule: str, message: str):
        super().__init__(f"[{rule}] {message}")
        self.rule = rule


# --- inputs: fetched data and the adapters' verdicts, as arguments ---------------------------

@dataclass(frozen=True)
class StockInputs:
    """Everything read for one stock with a pinned feed, and the verdicts the
    adapters made on it."""

    asset: Asset
    reading: Observation         # the feed's latest round, at the pinned block
    fresh: Check                 # 1.3's verdict on it, in open-session time
    series: Series               # the feed's own rounds, at the pinned block
    closed_session: bool         # the feed's schedule is in its inferred closed span at the block
    corroboration: Observation   # GeckoTerminal's price
    volume: Observation          # GeckoTerminal's 24h volume
    independent: bool            # the corroborator is independent of the execution venue
    quote: Observation           # the venue's quote at the nominal size
    tradeable: Check             # 1.5's verdict on the quote, judged at `built_at`
    tradeable_rule: str | None
    executable: Check            # 1.5's statement that a quote is not a fill


@dataclass(frozen=True)
class MarkedInputs:
    """Cash or gas: marked by its own feed, and never a buy candidate."""

    asset: Asset
    reading: Observation
    fresh: Check


@dataclass(frozen=True)
class Inputs:
    block: BlockRef
    built_at: Instant                       # when quote ages and tradeability were judged
    stocks: tuple[StockInputs, ...]
    cash: MarkedInputs
    gas: MarkedInputs
    wallet: ChainAddress
    balances: Mapping[AssetId, Observation]  # the wallet's, at the pinned block
    held_outside: Mapping[AssetId, Asset]    # held assets with no pinned feed, as 1.2 describes them
    closed_sessions: tuple[str, ...]         # schedule labels whose closed span contains the block
    divergence_rule: valuation.DivergenceRule
    rules: Mapping[str, str]                 # the rules applied, in words, from config
    config: Mapping[str, str]                # config file -> sha256 of its bytes


@dataclass(frozen=True)
class Snapshot:
    """The document, the exact bytes that are hashed and read, and their sha256."""

    document: Mapping[str, Any]
    body: bytes
    sha256: str


# --- canonical bytes ---------------------------------------------------------------------------

def _scalar(value: Any) -> str:
    if isinstance(value, float):
        raise TypeError("a float never enters the snapshot; use decimal text")
    if type(value) is int and abs(value) > MAX_SAFE_JSON_INT:
        raise ValueError(f"{value} exceeds 2**53; write it as text")
    if value is not None and not isinstance(value, (str, int, bool)):
        raise TypeError(f"not a JSON scalar: {type(value).__name__}")
    return json.dumps(value, ensure_ascii=False)


def _emit(node: Any, depth: int) -> str:
    pad, inner = " " * depth, " " * (depth + 1)
    if isinstance(node, dict):
        if not node:
            return "{}"
        if not all(isinstance(k, str) for k in node):
            raise TypeError("snapshot keys are text")
        items = [f"{inner}{json.dumps(k, ensure_ascii=False)}: {_emit(node[k], depth + 1)}"
                 for k in sorted(node)]
        return "{\n" + ",\n".join(items) + "\n" + pad + "}"
    if isinstance(node, (list, tuple)):
        if all(not isinstance(v, (dict, list, tuple)) for v in node):
            return "[" + ", ".join(_scalar(v) for v in node) + "]"
        return "[\n" + ",\n".join(inner + _emit(v, depth + 1) for v in node) + "\n" + pad + "]"
    return _scalar(node)


def canonical(document: Mapping[str, Any]) -> bytes:
    """The one byte form: sorted keys, one space of indent per level, arrays of
    scalars on one line, no floats, no integer past 2**53, a final newline.
    Deterministic, and valid JSON that parses back to the same document."""
    return (_emit(document, 0) + "\n").encode("utf-8")


def seal(document: Mapping[str, Any]) -> Snapshot:
    body = canonical(document)
    return Snapshot(document=document, body=body, sha256=hashlib.sha256(body).hexdigest())


# --- rendering: exact, readable ------------------------------------------------------------------

def _decimal(raw: int, decimals: int) -> str:
    sign, digits = ("-" if raw < 0 else ""), str(abs(raw))
    if decimals == 0:
        return sign + digits
    digits = digits.rjust(decimals + 1, "0")
    whole, fraction = digits[:-decimals], digits[-decimals:].rstrip("0")
    return sign + whole + ("." + fraction if fraction else "")


def _q(quantity: Fixed | Price | Amount | None) -> str | None:
    return None if quantity is None else _decimal(quantity.raw, quantity.decimals)


def _time(instant: Instant | None) -> str | None:
    if instant is None:
        return None
    seconds, ms = divmod(instant.epoch_ms, 1000)
    stamp = time.strftime("%Y-%m-%dT%H:%M:%S", time.gmtime(seconds))
    return f"{stamp}.{ms:03d}Z" if ms else f"{stamp}Z"


def _check(check: Check | None) -> dict | None:
    return None if check is None else {"verdict": check.value, "reason": check.reason}


def _read(observation: Observation) -> dict:
    """How a read went, for a reader: only what is not OK says why."""
    if observation.ok:
        return {"read": "ok"}
    return {"read": observation.status.value, "read_reason": observation.detail}


def _asset(asset: Asset) -> dict:
    out = {"symbol": asset.symbol, "kind": asset.kind.value, "address": asset.id.address,
           "chain_id": asset.id.chain_id, "decimals": asset.decimals}
    if asset.registry is not None:
        out |= {"name": asset.registry.name, "isin": asset.registry.isin,
                "registry_status": asset.registry.status}
    return out


def _mark(asset: Asset, reading: Observation, fresh: Check, the_mark: valuation.Mark) -> dict:
    # A passing mark's own reason repeats the fields beside it; a failing one says why.
    verdict = ({"verdict": True, "reason": "the fresh answer of the feed pinned to this address"}
               if the_mark.check.passes else _check(the_mark.check))
    out = {"price_usd": _q(the_mark.price), "fresh": _check(fresh), "verdict": verdict}
    if asset.feed is not None:
        out |= {"feed": asset.feed.name, "feed_proxy": asset.feed.proxy.address}
    if reading is not None:
        out |= _read(reading) | {"round_id": reading.source_ref,
                                 "updated_at": _time(reading.source_time)}
    return out


def _timeline(series: Series) -> dict:
    out = _read_series(series) | {
        "window_start": _time(series.window_start),
        "coverage": _check(series.coverage),
        "rounds": len(series.points),
        "columns": ["updated_at", "price_usd"],
        "points": [[_time(p.source_time), _q(p.value)] for p in series.points],
    }
    return out


def _read_series(series: Series) -> dict:
    if series.status is FetchStatus.OK:
        return {"read": "ok"}
    return {"read": series.status.value, "read_reason": series.detail}


def _corroboration(s: StockInputs, cross: valuation.CrossCheck) -> dict:
    return _read(s.corroboration) | {
        "fetched_at": _time(s.corroboration.fetch_time),
        "price_usd": _q(s.corroboration.value) if s.corroboration.ok else None,
        "volume_24h_usd": _q(s.volume.value) if s.volume.ok else None,
        "divergence_bps": _q(cross.divergence),
        "tier": cross.tier,
        "session": "closed" if s.closed_session else "open",
        "independent_of_venue": s.independent,
        "verdict": _check(cross.verdict),
    }


def _quote(s: StockInputs, built_at: Instant, cash_symbol: str) -> dict:
    out = _read(s.quote) | {"fetched_at": _time(s.quote.fetch_time),
                            "age_s": _decimal(built_at.epoch_ms - s.quote.fetch_time.epoch_ms, 3),
                            "tradeable": _check(s.tradeable),
                            "executable": _check(s.executable)}
    if s.quote.ok:
        q: Quote = s.quote.value
        out |= {"quote_id": q.quote_id,
                "sell_token": cash_symbol, "sell_amount": _q(q.sell),
                "buy_token": s.asset.symbol, "buy_amount": _q(q.buy),
                "min_buy_amount": _q(q.min_buy),
                "venue_price_usd": _q(q.buy_price), "venue_sell_token_price_usd": _q(q.sell_price),
                "swap_impact_bps": _q(q.swap_impact), "price_impact_bps": _q(q.price_impact),
                "max_price_impact_bps": _q(q.max_price_impact), "fee_bps": _q(q.fee),
                "fee_waived": q.fee_waived, "slippage_bps": _q(q.slippage)}
    return out


def _finding(finding: valuation.Finding) -> dict:
    return {"kind": finding.kind, "divergence_bps": _q(finding.divergence),
            "beyond_open_session_limit": finding.beyond_open_session_limit,
            "reason": finding.reason}


def _status(status: UniverseStatus, rule: str | None, check: Check) -> dict:
    return {"value": status.value, "rule": rule, "verdict": check.value, "reason": check.reason}


# --- the pipeline, per stock -----------------------------------------------------------------------

def _judge(s: StockInputs, universe: Universe, rule: valuation.DivergenceRule
           ) -> tuple[UniverseStatus, str | None, Check, valuation.Mark, valuation.CrossCheck]:
    """The status is the first rule in ORDER that does not pass."""
    the_mark = valuation.mark(s.asset, s.reading, s.fresh)
    cross = valuation.cross_check(the_mark, s.corroboration, s.volume, rule,
                                  independent=s.independent, closed_session=s.closed_session)
    admitted = universe.admission(s.asset)
    if not admitted.decision.passes:
        return admitted.universe_status, admitted.rule, admitted.decision, the_mark, cross
    if not the_mark.check.passes:
        return UniverseStatus.NO_MARK, the_mark.rule, the_mark.check, the_mark, cross
    if cross.rule in (valuation.RULE_CORROBORATION, valuation.RULE_VOLUME):
        return UniverseStatus.UNCORROBORATED, cross.rule, cross.verdict, the_mark, cross
    if cross.rule == valuation.RULE_CORROBORATOR_LINE:
        return UniverseStatus.BELOW_CORROBORATOR_LINE, cross.rule, cross.verdict, the_mark, cross
    if cross.rule == valuation.RULE_DIVERGENCE:
        return UniverseStatus.DIVERGENCE_VETO, cross.rule, cross.verdict, the_mark, cross
    if not s.tradeable.passes:
        reason = s.tradeable.reason or "the quote did not pass"
        return (UniverseStatus.NOT_TRADEABLE, s.tradeable_rule,
                Check(s.tradeable.value, reason), the_mark, cross)
    return (UniverseStatus.TRADEABLE, None,
            Check(True, "every rule passed: " + ", ".join(ORDER)), the_mark, cross)


def _pinned(observation: Observation, block: BlockRef, what: str) -> None:
    if observation.block != block:
        at = observation.block.number if observation.block else "no block"
        raise SnapshotRefused(RULE_BLOCK_PIN, f"{what} was read at {at}, not the pinned "
                                              f"block {block.number}")
    if observation.source_time is not None and observation.source_time > block.timestamp:
        raise SnapshotRefused(RULE_AFTER_PIN, f"{what} is dated {_time(observation.source_time)}, "
                                              f"after the pinned block's {_time(block.timestamp)}")


def _check_stock(s: StockInputs, block: BlockRef) -> None:
    symbol = s.asset.symbol
    _pinned(s.reading, block, f"{symbol}'s feed reading")
    if s.series.asset != s.asset.id:
        raise SnapshotRefused(RULE_DUPLICATE, f"{symbol}'s series is for another asset")
    for point in s.series.points:
        _pinned(point, block, f"{symbol}'s round {point.source_ref}")
    if s.series.newest is not None and s.reading.ok and \
            s.series.newest.source_ref != s.reading.source_ref:
        raise SnapshotRefused(RULE_SERIES_HEAD, f"{symbol}'s series ends at round "
                                                f"{s.series.newest.source_ref}, but the mark read "
                                                f"at the same block is round {s.reading.source_ref}")


# --- the snapshot ------------------------------------------------------------------------------

ABOUT = (
    "One frozen snapshot of what the fund knows, pinned to one block of Robinhood Chain "
    "(4663). Every chain value was read at `block`; GeckoTerminal prices and venue quotes "
    "are live offchain reads, stamped with when they were fetched. Prices and amounts are "
    "exact decimal text, times are UTC, and null means unknown, never zero. Each verdict is "
    "true, false or null, and null is undetermined, which blocks. `assets` holds one entry per "
    "stock with a pinned Chainlink feed; `summary` gives every asset's status in one line; "
    "`rules` says what each status means. A quote is a price, not a fill.")


def build(inputs: Inputs, universe: Universe) -> Snapshot:
    """The snapshot for `inputs`. Identical inputs, in any order, give identical
    bytes; any change to what it reports changes them."""
    block = inputs.block
    if block.timestamp is None or block.hash is None:
        raise SnapshotRefused(RULE_BLOCK_PIN, "a snapshot is pinned by block hash, with its time")
    seen: set[AssetId] = set()
    for s in inputs.stocks:
        if s.asset.id in seen:
            raise SnapshotRefused(RULE_DUPLICATE, f"two readings for {s.asset.id.address}")
        seen.add(s.asset.id)
        _check_stock(s, block)
    for marked in (inputs.cash, inputs.gas):
        _pinned(marked.reading, block, f"{marked.asset.symbol}'s feed reading")
    for asset, balance in inputs.balances.items():
        _pinned(balance, block, f"the balance of {asset.address}")

    rule = inputs.divergence_rule
    cash_symbol = inputs.cash.asset.symbol
    entries, verdicts, marks = [], {}, {}
    for s in sorted(inputs.stocks, key=lambda s: (s.asset.symbol, s.asset.id)):
        status, rule_name, check, the_mark, cross = _judge(s, universe, rule)
        verdicts[s.asset.id], marks[s.asset.id] = (status, rule_name, check), the_mark
        entries.append({
            "asset": _asset(s.asset),
            "identity": _check(s.asset.identity),
            "standing": _check(universe.standing(s.asset.id)),
            "beacon": _check(s.asset.beacon),
            "markability": _check(s.asset.markability),
            "mark": _mark(s.asset, s.reading, s.fresh, the_mark),
            "corroboration": _corroboration(s, cross),
            "quote": _quote(s, inputs.built_at, cash_symbol),
            "findings": ([_finding(cross.finding)]
                         if cross.finding and cross.finding.beyond_open_session_limit else []),
            "status": _status(status, rule_name, check),
            "timeline": _timeline(s.series),
        })

    holdings = _holdings(inputs, universe, verdicts, marks)
    outside = sorted(((r.symbol, a.address) for a, r in universe.records.items()
                      if a.chain_id == block.chain_id and a not in universe.feeds))
    counts: dict[str, int] = {}
    for e in entries:
        counts[e["status"]["value"]] = counts.get(e["status"]["value"], 0) + 1
    document = {
        "schema": SCHEMA,
        "about": ABOUT,
        "block": {"chain_id": block.chain_id, "number": block.number, "hash": block.hash,
                  "time": _time(block.timestamp),
                  "closed_sessions": sorted(inputs.closed_sessions)},
        "built_at": _time(inputs.built_at),
        "inputs": {"issuer_registry": _pin(universe.registry),
                   "feed_directory": _pin(universe.directory),
                   "config_sha256": dict(inputs.config)},
        "rules": dict(inputs.rules) | {"order": ", ".join(ORDER)},
        "assets": entries,
        "holdings": holdings,
        "wallet": inputs.wallet.address,
        "outside_universe": {
            "reason": ("registry-listed, so identity holds, but no Chainlink feed is pinned, so "
                       "there is no mark independent of the venue and the asset is not bought "
                       "(0.4 decision). Beacons are not read for these; any one held appears "
                       "under holdings, carried without a value."),
            "status": UniverseStatus.UNMARKABLE.value,
            "count": len(outside),
            "columns": ["symbol", "address"],
            "assets": [list(pair) for pair in outside],
        },
        "summary": {
            "counts": counts,
            "columns": ["symbol", "status", "rule"],
            "assets": [[e["asset"]["symbol"], e["status"]["value"], e["status"]["rule"]]
                       for e in entries],
            "findings": [[e["asset"]["symbol"], f["kind"], f["divergence_bps"]]
                         for e in entries for f in e["findings"]],
        },
    }
    return seal(document)


def _pin(pin) -> dict:
    return {"sha256": pin.sha256, "locator": pin.locator, "fetched_at": _time(pin.fetch_time)}


def _holdings(inputs: Inputs, universe: Universe, verdicts: Mapping, marks: Mapping) -> list[dict]:
    """Cash and gas always, and every stock the wallet holds or whose balance is
    unknown. A held stock with no mark is carried without a value, never at zero."""
    rows = []
    for marked in (inputs.cash, inputs.gas):
        the_mark = valuation.mark(marked.asset, marked.reading, marked.fresh)
        rows.append((marked.asset, marked.reading, marked.fresh, the_mark,
                     UniverseStatus.NOT_A_STOCK, None,
                     Check(True, "the cash leg" if marked.asset.kind is AssetKind.CASH
                           else "the gas asset")))
    by_id = {s.asset.id: s for s in inputs.stocks}
    for asset_id, balance in sorted(inputs.balances.items()):
        if asset_id in (inputs.cash.asset.id, inputs.gas.asset.id):
            continue
        if balance.ok and balance.value.raw == 0:
            continue
        if asset_id in by_id:
            s = by_id[asset_id]
            status, rule, check = verdicts[asset_id]
            rows.append((s.asset, s.reading, s.fresh, marks[asset_id], status, rule, check))
        else:
            asset = inputs.held_outside[asset_id]
            admitted = universe.admission(asset)
            no_feed = valuation.mark(asset, None, Check(None, "no feed to read"))
            rows.append((asset, None, None, no_feed, admitted.universe_status or
                         UniverseStatus.UNMARKABLE, admitted.rule, admitted.decision))
    out = []
    for asset, reading, fresh, the_mark, status, rule, check in rows:
        balance = inputs.balances[asset.id]
        held = valuation.value_holding(asset, balance, the_mark, universe_status=status,
                                       universe_reason=check.reason)
        out.append(_read(balance) | {
            "asset": _asset(asset),
            "balance": _q(balance.value) if balance.ok else None,
            "mark": _mark(asset, reading, fresh, the_mark) if reading is not None or fresh
            else {"price_usd": None, "verdict": _check(the_mark.check)},
            "value_usd": _q(held.value),
            "value_reason": held.value_reason,
            "status": _status(status, rule, check),
        })
    return sorted(out, key=lambda h: (h["asset"]["symbol"], h["asset"]["address"]))
