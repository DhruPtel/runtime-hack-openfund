"""Robinhood Chain (4663): every external read for the chain lives here. Unit 1.3.

It reads Chainlink feeds and their round history, token metadata, balances,
and the EIP-1967 beacon slot that `core/universe.py`'s cross-check consumes.
Everything it returns is an `Observation` or a `Series` from `core/types.py`,
never a bare number. It can depend on `core/`; `core/` never depends on it.

What the record requires, and where each requirement is met:

- **One pinned block.** `pin_block` fixes a block; every later read addresses
  it by hash (EIP-1898), so a reorg fails with "header not found" instead of
  answering from another block. `require_one_block` refuses a mixed bundle by
  name (rule `block-pin`).
- **The transport is `adapters/http.py`**, shared with every adapter since 1.4:
  a User-Agent on every request (the RPC returns 403 without one, and that 403
  looks like an auth failure, probe 0.3), a whole-request deadline, failover
  that advances on a hang, pacing and a doubling backoff. The RPC's 429 carries
  no `Retry-After`, so the backoff has no server hint (measured 2026-09-18).
  There is one endpoint today, so the failover has nowhere to go
  (`config/chain.json`). What is JSON-RPC's own stays here: an error inside a
  200, and which of those are worth retrying.
- **Three-valued results.** An unreachable source yields an Observation marked
  UNREACHABLE, which a Check reads as undetermined, never as false.
- **Round ids exceed 2**53.** They are parsed from hex into Python ints and
  carried as text in `source_ref`; no float is ever made.
- **The multiplier.** A Chainlink answer is taken as published. Per the
  documentation it already incorporates `uiMultiplier()`, which 0.4 could not
  measure (22 bps of effect under a 142 bps noise floor, F0.4.4), so it is
  **not** applied here or anywhere else. The label on every reading says so.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Sequence

from fund.adapters import http
from fund.adapters.http import RULE_TRANSPORT, Endpoint, Transport, urllib_transport
from fund.core import universe
from fund.core.types import (
    USD, Amount, AssetId, BlockRef, ChainAddress, Check, FeedRef, FetchStatus, Fixed, Instant,
    Observation, Price, Series, Source,
)

RULE_BLOCK_PIN = "block-pin"


class ChainError(Exception):
    def __init__(self, rule: str, message: str):
        super().__init__(f"[{rule}] {message}")
        self.rule = rule


class RpcUnavailable(ChainError):
    """Every attempt on every endpoint failed. `failures` names each one by
    endpoint name, never by URL: the URL is a credential."""

    def __init__(self, failures: Sequence[tuple[str, str]]):
        self.failures = tuple(failures)
        super().__init__(RULE_TRANSPORT, "; ".join(f"{name}: {why}" for name, why in failures))


class RpcError(ChainError):
    """The node answered with a JSON-RPC error — `execution reverted`, `header
    not found`. That is an answer, not a transport failure, so it does not fail
    over."""

    def __init__(self, code: Any, message: str):
        super().__init__("rpc", f"{code}: {message}")
        self.code = code
        self.message = message


# --- JSON-RPC over the shared transport ---------------------------------------------

def _missing_state(error: dict) -> bool:
    message = str(error.get("message", ""))
    return error.get("code") == -32000 and "historical state" in message and "not available" in message


class RpcClient:
    """JSON-RPC over an ordered list of endpoints, on `adapters/http.py`.

    The transport handles hangs, dead connections, HTTP 429s and 5xx: each moves
    on to the next endpoint and is retried on the next pass, after a doubling
    backoff. Two answers inside a 200 are treated the same way here:
    - a JSON-RPC 429;
    - "historical state ... is not available" for the pinned block: seen once
      in ~100 reads at a block a minute old, never in 326 reads of one block
      over 9 minutes (2026-09-19), so a backend's gap, not an age limit. A read
      by block hash cannot answer from another block, so a retry is safe.
      "header not found" is not retried: it can mean a reorg.
    Every other JSON-RPC error is an answer, returned as `RpcError`.
    """

    def __init__(self, endpoints: Sequence[Endpoint], *, timeout_s: float, attempts: int,
                 backoff_s: float, min_interval_s: float, transport: Transport,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        self._http = http.HttpClient(endpoints, timeout_s=timeout_s, attempts=attempts,
                                     backoff_s=backoff_s, min_interval_s=min_interval_s,
                                     transport=transport, sleep=sleep, monotonic=monotonic)
        self.endpoints = self._http.endpoints
        self._next_id = 1

    @staticmethod
    def _accept(reply: http.Reply) -> Any:
        try:
            parsed = json.loads(reply.body)
        except ValueError:
            raise http.Retry("a 200 whose body is not JSON") from None
        error = (parsed.get("error") or {}) if isinstance(parsed, dict) else {}
        if error.get("code") == 429:
            raise http.Retry("rate limited: JSON-RPC 429")
        if _missing_state(error):
            raise http.Retry("pinned block's state not available: " + str(error.get("message")))
        return parsed

    def _post(self, payload: Any) -> Any:
        try:
            return self._http.send(json.dumps(payload).encode("utf-8"), accept=self._accept)
        except http.Unavailable as unavailable:
            raise RpcUnavailable(unavailable.failures) from None

    def call(self, method: str, params: list) -> Any:
        """One JSON-RPC call. Returns `result`, raises RpcError or RpcUnavailable."""
        request_id, self._next_id = self._next_id, self._next_id + 1
        response = self._post({"jsonrpc": "2.0", "id": request_id, "method": method,
                               "params": params})
        if not isinstance(response, dict) or ("error" not in response and "result" not in response):
            raise RpcError(None, "a reply with neither result nor error")
        if "error" in response:
            error = response["error"] or {}
            raise RpcError(error.get("code"), self._http.scrub(str(error.get("message"))))
        return response["result"]


# --- ABI: just enough, by hand, stdlib only --------------------------------------

SEL_LATEST_ROUND = "feaf968c"   # latestRoundData()
SEL_GET_ROUND = "9a6fc8f5"      # getRoundData(uint80)
SEL_DECIMALS = "313ce567"       # decimals()
SEL_BALANCE_OF = "70a08231"     # balanceOf(address)
SEL_AGGREGATE3 = "82ad56cb"     # aggregate3((address,bool,bytes)[])

_U64 = (1 << 64) - 1


def _w(value: int) -> str:
    return format(value, "064x")


def _uint(data: bytes, offset: int) -> int:
    return int.from_bytes(data[offset:offset + 32], "big")


def encode_aggregate3(calls: Sequence[tuple[str, bytes]]) -> str:
    """Multicall3 `aggregate3`, every call with allowFailure = true, so one
    reverting feed is one refused reading, not a failed batch."""
    tuples = []
    for target, data in calls:
        padded = data + b"\x00" * (-len(data) % 32)
        tuples.append(_w(int(target, 16)) + _w(1) + _w(0x60) + _w(len(data)) + padded.hex())
    offsets, position = [], 32 * len(calls)
    for encoded in tuples:
        offsets.append(position)
        position += len(encoded) // 2
    return ("0x" + SEL_AGGREGATE3 + _w(0x20) + _w(len(calls))
            + "".join(_w(o) for o in offsets) + "".join(tuples))


def decode_aggregate3(result_hex: str) -> list[tuple[bool, bytes]]:
    data = bytes.fromhex(result_hex[2:])
    array = _uint(data, 0)
    count = _uint(data, array)
    out = []
    for i in range(count):
        start = array + 32 + _uint(data, array + 32 + 32 * i)
        success = _uint(data, start) == 1
        payload = start + _uint(data, start + 32)
        length = _uint(data, payload)
        out.append((success, data[payload + 32:payload + 32 + length]))
    return out


@dataclass(frozen=True)
class Round:
    """One Chainlink round. `answer` is int256, so it is decoded signed."""

    round_id: int
    answer: int
    started_at: int
    updated_at: int
    answered_in_round: int

    @property
    def phase(self) -> int:
        return self.round_id >> 64

    @property
    def aggregator_round(self) -> int:
        return self.round_id & _U64


def decode_round(data: bytes) -> Round:
    if len(data) < 160:
        raise ValueError("a round is five words")
    return Round(round_id=_uint(data, 0),
                 answer=int.from_bytes(data[32:64], "big", signed=True),
                 started_at=_uint(data, 64), updated_at=_uint(data, 96),
                 answered_in_round=_uint(data, 128))


def round_problem(r: Round) -> str | None:
    """Chainlink's own sanity rules. Any failure is a refused reading, not a price."""
    if r.answer <= 0:
        return f"non-positive answer {r.answer}"
    if r.updated_at == 0:
        return "round not complete (updatedAt 0)"
    if r.answered_in_round < r.round_id:
        return "answered in an earlier round"
    return None


# --- the pinned block, and reads at it -------------------------------------------

MULTIPLIER_NOTE = ("price as published by the feed; uiMultiplier() is already incorporated "
                   "per documentation and is not applied again: documented, not measured (F0.4.4)")


class MixedBlocks(ChainError):
    def __init__(self, offenders: Sequence[tuple[str, int | None]], pinned: BlockRef):
        self.offenders = tuple(offenders)
        listed = ", ".join(f"{source} at {'no block' if n is None else n}" for source, n in offenders)
        super().__init__(RULE_BLOCK_PIN, f"pinned block {pinned.number}; read elsewhere: {listed}")


def require_one_block(observations: Sequence[Observation], pinned: BlockRef) -> None:
    """Every chain observation in a bundle comes from the pinned block, or the
    bundle is refused. Two blocks is an error, not a warning."""
    offenders = [(f"{o.source.system}:{o.source.locator}", o.block.number if o.block else None)
                 for o in observations if o.block != pinned]
    if offenders:
        raise MixedBlocks(offenders, pinned)


def pin_block(rpc: RpcClient, chain_id: int, tag: str = "latest") -> BlockRef:
    """Fix one block. The node's chain id is checked first: a testnet URL in the
    mainnet slot would otherwise answer, plausibly, about a different chain."""
    reported = int(rpc.call("eth_chainId", []), 16)
    if reported != chain_id:
        raise ChainError(RULE_BLOCK_PIN, f"endpoint reports chain {reported}, expected {chain_id}")
    block = rpc.call("eth_getBlockByNumber", [tag, False])
    return BlockRef(chain_id, int(block["number"], 16),
                    Instant.from_seconds(int(block["timestamp"], 16)), block["hash"].lower())


def freshness(reading: Observation, feed: FeedRef, as_of: Instant, margin_s: int) -> Check:
    """Is this newest reading fresh? Judged against its own feed's heartbeat
    plus the margin, at `as_of` — the pinned block's time, not the wall clock,
    so the same snapshot gives the same verdict every time.

    Only the newest point of a series is ever judged (decision 2026-09-18). A
    reading that was not taken is undetermined, never stale and never fresh.
    """
    if not reading.ok or reading.source_time is None:
        return Check(None, f"no reading to judge: {reading.status.value}: {reading.detail}")
    if feed.heartbeat.decimals != 0:
        raise ValueError("heartbeat is whole seconds")
    limit_ms = (feed.heartbeat.raw + margin_s) * 1000
    age_ms = as_of.epoch_ms - reading.source_time.epoch_ms
    detail = (f"age {age_ms // 1000}s against heartbeat {feed.heartbeat.raw}s + margin "
              f"{margin_s}s; market hours {feed.market_hours}")
    return Check(age_ms <= limit_ms, detail)


class ChainReader:
    """Reads at one pinned block. A failed read comes back as an UNREACHABLE or
    REFUSED observation carrying its reason; the reader never raises for one."""

    def __init__(self, rpc: RpcClient, block: BlockRef, *, multicall3: str, chunk: int,
                 clock: Callable[[], Instant]):
        if block.hash is None or block.timestamp is None:
            raise ValueError("pin a block by hash, with its time")
        self.rpc, self.block, self.multicall3, self.chunk = rpc, block, multicall3, chunk
        self.clock = clock

    def _at(self) -> dict:
        return {"blockHash": self.block.hash}

    def _observe(self, source: Source, *, value=None, source_time=None, status=FetchStatus.OK,
                 detail=None, ref=None) -> Observation:
        return Observation(value=value, source=source, source_time=source_time,
                           fetch_time=self.clock(), block=self.block, status=status,
                           detail=detail, source_ref=ref)

    def _failed(self, source: Source, error: Exception) -> Observation:
        status = FetchStatus.UNREACHABLE if isinstance(error, RpcUnavailable) else FetchStatus.REFUSED
        return self._observe(source, status=status, detail=str(error))

    def multicall(self, calls: Sequence[tuple[str, bytes]]) -> list[tuple[bool, bytes]]:
        out: list[tuple[bool, bytes]] = []
        for start in range(0, len(calls), self.chunk):
            chunk = calls[start:start + self.chunk]
            result = self.rpc.call("eth_call", [
                {"to": self.multicall3, "data": encode_aggregate3(chunk)}, self._at()])
            try:
                decoded = decode_aggregate3(result)
            except (ValueError, IndexError) as error:
                raise ChainError("multicall", f"undecodable aggregate3 result: {error}") from error
            if len(decoded) != len(chunk):
                raise ChainError("multicall", f"{len(decoded)} results for {len(chunk)} calls")
            out += decoded
        return out

    # feeds ---------------------------------------------------------------------

    def _round_observation(self, asset: AssetId, feed: FeedRef, success: bool,
                           data: bytes) -> Observation:
        source = Source("chainlink-feed", feed.proxy.address)
        if not success:
            return self._observe(source, status=FetchStatus.REFUSED, detail="the feed call reverted")
        try:
            r = decode_round(data)
        except ValueError as error:
            return self._observe(source, status=FetchStatus.REFUSED, detail=str(error))
        problem = round_problem(r)
        if problem:
            return self._observe(source, status=FetchStatus.REFUSED, detail=problem,
                                 ref=str(r.round_id))
        return self._observe(source, value=Price(r.answer, feed.decimals, asset, USD),
                             source_time=Instant.from_seconds(r.updated_at),
                             detail=MULTIPLIER_NOTE, ref=str(r.round_id))

    def latest_rounds(self, feeds: dict[AssetId, FeedRef]) -> dict[AssetId, Observation]:
        """`latestRoundData` for every feed, in one aggregated call per chunk."""
        assets = list(feeds)
        calls = [(feeds[a].proxy.address, bytes.fromhex(SEL_LATEST_ROUND)) for a in assets]
        try:
            results = self.multicall(calls)
        except ChainError as error:
            return {a: self._failed(Source("chainlink-feed", feeds[a].proxy.address), error)
                    for a in assets}
        return {a: self._round_observation(a, feeds[a], ok, data)
                for a, (ok, data) in zip(assets, results)}

    # tokens, balances, beacon ------------------------------------------------------

    def _decimals(self, targets: dict[AssetId, str], system: str) -> dict[AssetId, Observation]:
        calls = [(address, bytes.fromhex(SEL_DECIMALS)) for address in targets.values()]
        try:
            results = self.multicall(calls)
        except ChainError as error:
            return {k: self._failed(Source(system, v), error) for k, v in targets.items()}
        out = {}
        for (key, address), (ok, data) in zip(targets.items(), results):
            source = Source(system, address)
            out[key] = (self._observe(source, value=Fixed(_uint(data, 0), 0, "decimals"))
                        if ok and len(data) >= 32 else
                        self._observe(source, status=FetchStatus.REFUSED,
                                      detail="decimals() reverted or returned nothing"))
        return out

    def decimals(self, tokens: Sequence[AssetId]) -> dict[AssetId, Observation]:
        """A token's own `decimals()`: USDG 6, stock tokens 18 (F0.3.1)."""
        return self._decimals({t: t.address for t in tokens}, "erc20")

    def feed_decimals(self, feeds: dict[AssetId, FeedRef]) -> dict[AssetId, Observation]:
        """A feed proxy's own `decimals()`, to set beside the pinned directory's."""
        return self._decimals({a: f.proxy.address for a, f in feeds.items()}, "chainlink-feed")

    def balances(self, holder: ChainAddress, tokens: dict[AssetId, int]) -> dict[AssetId, Observation]:
        """Balances over RPC; `/wallet/portfolio` omits every token (F0.7b.8).
        `tokens` maps each asset to its decimals; the native asset is read with
        eth_getBalance, the rest with one aggregated balanceOf."""
        out: dict[AssetId, Observation] = {}
        erc20 = [t for t in tokens if not t.is_native]
        for native in (t for t in tokens if t.is_native):
            source = Source("native-balance", holder.address)
            try:
                raw = int(self.rpc.call("eth_getBalance", [holder.address, self._at()]), 16)
                out[native] = self._observe(source, value=Amount(raw, tokens[native], native))
            except ChainError as error:
                out[native] = self._failed(source, error)
        calls = [(t.address, bytes.fromhex(SEL_BALANCE_OF + _w(int(holder.address, 16))))
                 for t in erc20]
        try:
            results = self.multicall(calls) if calls else []
        except ChainError as error:
            out.update({t: self._failed(Source("erc20-balance", t.address), error) for t in erc20})
            return out
        for token, (ok, data) in zip(erc20, results):
            source = Source("erc20-balance", token.address)
            out[token] = (self._observe(source, value=Amount(_uint(data, 0), tokens[token], token))
                          if ok and len(data) >= 32 else
                          self._observe(source, status=FetchStatus.REFUSED,
                                        detail="balanceOf reverted or returned nothing"))
        return out

    def beacon_slots(self, tokens: Sequence[AssetId]) -> dict[AssetId, Observation]:
        """Each token's EIP-1967 beacon slot, for `Universe.cross_check_beacons`.
        Storage cannot be read through Multicall3, so these are single, paced reads."""
        out = {}
        for token in tokens:
            source = Source("eip1967-beacon-slot", token.address)
            try:
                word = self.rpc.call("eth_getStorageAt",
                                     [token.address, universe.BEACON_SLOT, self._at()])
                out[token] = self._observe(
                    source, value=universe.beacon_from_slot(token.chain_id, word))
            except ChainError as error:
                out[token] = self._failed(source, error)
            except ValueError as error:
                out[token] = self._observe(source, status=FetchStatus.REFUSED, detail=str(error))
        return out

    # the price series ----------------------------------------------------------------

    def _rounds(self, proxy: str, phase: int, numbers: Sequence[int]) -> list[tuple[bool, bytes]]:
        return self.multicall([(proxy, bytes.fromhex(SEL_GET_ROUND + _w((phase << 64) | n)))
                               for n in numbers])

    def price_series(self, asset: AssetId, feed: FeedRef, *, window_s: int, max_rounds: int,
                     scale_break_ratio: int) -> Series:
        """Chainlink rounds for `asset`, newest first back to the window start,
        returned oldest first, all read at the pinned block.

        The window is measured back from the pinned block's time. The walk keeps
        the first round at or before the window start, so the series holds the
        price in effect when the window opened, and `coverage` is True only then.

        It stops early, and says so in `coverage`, at the first of:
        - the start of the current phase: the feed is younger than the window;
        - `max_rounds`: a very active feed, or a cap too low;
        - a scale break: consecutive answers `scale_break_ratio` apart, which is
          a change of units, not a price move (32 of 37 feeds, measured);
        - a round that fails Chainlink's sanity rules, or a failed read: the
          points gathered so far are kept, and coverage is undetermined.
        """
        source = Source("chainlink-feed", feed.proxy.address)
        window_start = Instant(max(0, self.block.timestamp.epoch_ms - window_s * 1000))

        def failed(status: FetchStatus, detail: str) -> Series:
            return Series(asset=asset, source=source, fetch_time=self.clock(), status=status,
                          detail=detail, window_start=window_start,
                          coverage=Check(None, f"no series: {detail}"))

        latest = self.latest_rounds({asset: feed})[asset]
        if not latest.ok:
            return failed(latest.status, latest.detail)
        head = int(latest.source_ref)
        phase = head >> 64

        walked: list[Round] = [decode_round_from(latest, head)]
        coverage: Check | None = None
        while coverage is None:
            oldest = walked[-1]
            number = (oldest.round_id & _U64) - 1
            if oldest.updated_at * 1000 <= window_start.epoch_ms:
                coverage = Check(True, f"{len(walked)} rounds reach back to the window start")
            elif number < 1:
                coverage = Check(False, f"history starts at phase {phase} round 1, "
                                        f"{_age(oldest.updated_at, window_start)} after the "
                                        f"window start; earlier phases are not walked")
            elif len(walked) >= max_rounds:
                coverage = Check(False, f"round cap {max_rounds} reached "
                                        f"{_age(oldest.updated_at, window_start)} short of the "
                                        f"window start")
            else:
                coverage = self._walk_back(walked, feed.proxy.address, phase, number,
                                           min(self.chunk, max_rounds - len(walked)),
                                           window_start, scale_break_ratio)

        points = tuple(self._observe(source, value=Price(r.answer, feed.decimals, asset, USD),
                                     source_time=Instant.from_seconds(r.updated_at),
                                     detail=MULTIPLIER_NOTE, ref=str(r.round_id))
                       for r in reversed(walked))
        return Series(asset=asset, source=source, fetch_time=self.clock(), status=FetchStatus.OK,
                      points=points, window_start=window_start, coverage=coverage,
                      detail=f"{len(points)} rounds, phase {phase}")

    def _walk_back(self, walked: list[Round], proxy: str, phase: int, number: int, count: int,
                   window_start: Instant, scale_break_ratio: int) -> Check | None:
        """Read up to `count` rounds below `number`, appending each good one to
        `walked`. Returns a coverage verdict if the walk must stop here, and
        None if it may go on. Each call reads at least one round or returns a
        verdict, so the walk always ends."""
        if count < 1 or number < 1:
            raise ValueError("a walk step reads at least one round")
        batch = list(range(number, max(0, number - count), -1))
        try:
            results = self._rounds(proxy, phase, batch)
        except ChainError as error:
            return Check(None, f"read failed at round {(phase << 64) | number}: {error}")
        for n, (ok, data) in zip(batch, results):
            wanted = (phase << 64) | n
            r = decode_round(data) if ok and len(data) >= 160 else None
            problem = ("the call reverted" if r is None else
                       f"returned round {r.round_id}" if r.round_id != wanted else round_problem(r))
            if problem:
                return Check(None, f"round {wanted}: {problem}")
            newer = walked[-1]
            if r.updated_at > newer.updated_at:
                return Check(None, f"round {wanted} is dated after the round that follows it; "
                                   f"history order in doubt")
            if max(r.answer, newer.answer) >= scale_break_ratio * min(r.answer, newer.answer):
                return Check(False, f"scale break before round {newer.round_id}: answer "
                                    f"{r.answer} then {newer.answer}; older rounds are in other "
                                    f"units and are left out")
            walked.append(r)
            if r.updated_at * 1000 <= window_start.epoch_ms:
                return None  # the loop above records the coverage
        return None


def decode_round_from(reading: Observation, round_id: int) -> Round:
    """The Round behind an OK feed Observation, for the walk's comparisons."""
    return Round(round_id=round_id, answer=reading.value.raw, started_at=0,
                 updated_at=reading.source_time.epoch_ms // 1000, answered_in_round=round_id)


def _age(seconds: int, since: Instant) -> str:
    return f"{(seconds * 1000 - since.epoch_ms) // 1000}s"


def series_freshness(series: Series, feed: FeedRef, as_of: Instant, margin_s: int) -> Check:
    """Freshness of a series is the freshness of its newest point, and of nothing
    else: every older point is old by construction (decision 2026-09-18)."""
    if series.newest is None:
        return Check(None, f"no points to judge: {series.status.value}: {series.detail}")
    return freshness(series.newest, feed, as_of, margin_s)


# --- configuration ------------------------------------------------------------------

CHAIN_CONFIG = Path(__file__).resolve().parents[3] / "config" / "chain.json"
THRESHOLDS = Path(__file__).resolve().parents[3] / "config" / "thresholds.json"


@dataclass(frozen=True)
class Settings:
    chain_id: int
    endpoints: tuple[str, ...]   # credential names, in failover order
    block_tag: str
    timeout_s: float
    attempts: int
    backoff_s: float
    min_interval_s: float
    multicall3: str
    chunk: int
    window_s: int
    max_rounds: int
    scale_break_ratio: int
    user_agent: str
    staleness_margin_s: int

    @classmethod
    def load(cls, chain_path: Path = CHAIN_CONFIG, thresholds_path: Path = THRESHOLDS) -> Settings:
        c = json.loads(chain_path.read_text())
        t = json.loads(thresholds_path.read_text())
        if t["feed_staleness_rule"] != "per_feed_heartbeat_plus_margin":
            raise ValueError(f"unknown staleness rule {t['feed_staleness_rule']!r}")
        return cls(chain_id=c["chain_id"], endpoints=tuple(c["rpc_endpoints"]),
                   block_tag=c["block_tag"], timeout_s=c["request_timeout_seconds"],
                   attempts=c["attempts_per_endpoint"], backoff_s=c["backoff_seconds"],
                   min_interval_s=c["min_request_interval_ms"] / 1000,
                   multicall3=ChainAddress(c["chain_id"], c["multicall3"]).address,
                   chunk=c["multicall_chunk"], window_s=c["series_window_seconds"],
                   max_rounds=c["series_max_rounds"],
                   scale_break_ratio=c["series_scale_break_ratio"], user_agent=c["user_agent"],
                   staleness_margin_s=t["feed_staleness_margin_seconds"])

    def client(self, secret: Callable[[str], str], transport: Transport | None = None) -> RpcClient:
        """`secret` is `Config.secret`: the URLs come from the role's credentials."""
        return RpcClient([Endpoint(name, secret(name)) for name in self.endpoints],
                         timeout_s=self.timeout_s, attempts=self.attempts,
                         backoff_s=self.backoff_s, min_interval_s=self.min_interval_s,
                         transport=transport or urllib_transport(self.user_agent))

    def reader(self, rpc: RpcClient, block: BlockRef,
               clock: Callable[[], Instant] | None = None) -> ChainReader:
        return ChainReader(rpc, block, multicall3=self.multicall3, chunk=self.chunk,
                           clock=clock or wall_clock)


def wall_clock() -> Instant:
    return Instant(time.time_ns() // 1_000_000)


# --- the live proof: `python -m fund.adapters.chain_4663 --prove` ---------------------------

def _iso(instant: Instant | None) -> str:
    if instant is None:
        return "-"
    return time.strftime("%Y-%m-%d %H:%M:%SZ", time.gmtime(instant.epoch_ms // 1000))


def _dur(ms: int) -> str:
    s = ms // 1000
    return f"{s // 86400}d{s % 86400 // 3600:02d}h{s % 3600 // 60:02d}m" if s >= 86400 else \
        f"{s // 3600}h{s % 3600 // 60:02d}m{s % 60:02d}s"


def prove(series_asset: str = "AAPL") -> int:
    """One live read of every claim 1.3 makes, printed. Read-only; spends nothing."""
    import socket

    from fund import config
    from fund.credentials import Role

    cfg = config.load(Role.ANALYST, require=False)
    settings = Settings.load()
    missing = [name for name in settings.endpoints if not cfg.has(name)]
    if missing:
        print(f"missing credentials: {', '.join(missing)}")
        return 2
    u = universe.load()
    with open(CHAIN_CONFIG.parent / "mandate.json") as handle:
        wallet = ChainAddress(settings.chain_id, json.load(handle)["execution_wallet"])
    symbol = {a: (u.records[a].symbol if a in u.records else f.name.split(" / ")[0])
              for a, f in u.feeds.items()}  # display only
    by_symbol = {v: k for k, v in symbol.items()}
    feeds = dict(sorted(u.feeds.items(), key=lambda item: symbol[item[0]]))
    margin = settings.staleness_margin_s

    rpc = settings.client(cfg.secret)
    block = pin_block(rpc, settings.chain_id, settings.block_tag)
    read = settings.reader(rpc, block)
    print(f"== pinned block {block.number} at {_iso(block.timestamp)}, hash {block.hash}")
    print(f"   endpoints {', '.join(e.name for e in rpc.endpoints)}; every read below is at this hash\n")

    print(f"== 1. {len(feeds)} feeds at one block: latestRoundData, decimals, freshness "
          f"(heartbeat + {margin}s, judged at block time)")
    rounds = read.latest_rounds(feeds)
    chain_decimals = read.feed_decimals(feeds)
    print(f"   {'asset':6} {'proxy':12} {'dec dir/chain':13} {'round id (exact)':24} "
          f"{'phase/round':11} {'updatedAt':20} {'age':10} {'hb':6} fresh")
    counts: dict[Any, int] = {}
    for asset, f in feeds.items():
        o, d = rounds[asset], chain_decimals[asset]
        verdict = freshness(o, f, block.timestamp, margin)
        counts[verdict.value] = counts.get(verdict.value, 0) + 1
        on_chain = d.value.raw if d.ok else d.status.value
        if o.ok:
            rid = int(o.source_ref)
            print(f"   {symbol[asset]:6} {f.proxy.address[:12]} {f.decimals:>5} / {on_chain!s:<5} "
                  f"{o.source_ref:24} {rid >> 64:>3}/{rid & _U64:<7} {_iso(o.source_time):20} "
                  f"{_dur(block.timestamp.epoch_ms - o.source_time.epoch_ms):10} "
                  f"{f.heartbeat.raw:<6} {verdict.value}")
        else:
            print(f"   {symbol[asset]:6} {f.proxy.address[:12]} {o.status.value}: {o.detail}  "
                  f"fresh={verdict.value}")
    mismatched = [symbol[a] for a in feeds
                  if chain_decimals[a].ok and chain_decimals[a].value.raw != feeds[a].decimals]
    print(f"   verdicts: {counts}; directory decimals disagreeing with chain: {mismatched or 'none'}")
    sample = rounds[by_symbol["GME"]]
    print(f"   GME price {sample.value.raw} / 10**{sample.value.decimals} USD; label: {sample.detail}\n")

    print("== 2. token metadata, the fund wallet's balances, and the beacon slots")
    stock = by_symbol["GME"]
    for token, o in read.decimals([u.cash_leg, stock]).items():
        print(f"   decimals() {symbol.get(token, 'USDG'):5} {token.address}: {o.value.raw if o.ok else o.detail}")
    held = read.balances(wallet, {u.gas_asset: u.gas_decimals, u.cash_leg: u.cash_decimals,
                                  stock: 18})
    for token, o in held.items():
        name = "ETH" if token.is_native else symbol.get(token, "USDG")
        print(f"   {wallet.address} holds {name:5}: raw {o.value.raw} ({o.value.decimals} dp)"
              if o.ok else f"   {name}: {o.status.value}: {o.detail}")
    slots = read.beacon_slots([a for a in feeds if a in u.records])  # stock tokens only
    checks = u.cross_check_beacons(slots)
    agree = sum(1 for c in checks.values() if c.value is True)
    print(f"   beacon slots read: {sum(o.ok for o in slots.values())}/{len(slots)}; agree with the "
          f"issuer beacon {u.issuer_beacon.address}: {agree}/{len(checks)}")
    for asset, o in slots.items():
        if not o.ok:
            print(f"   unread, so undetermined ({checks[asset].value}): {symbol[asset]}: "
                  f"{o.status.value}: {o.detail}")
    print()

    target = by_symbol[series_asset]
    print(f"== 3. price series for {series_asset}: {settings.window_s}s window back from the block")
    s = read.price_series(target, feeds[target], window_s=settings.window_s,
                          max_rounds=settings.max_rounds, scale_break_ratio=settings.scale_break_ratio)
    print(f"   {s.detail}; window start {_iso(s.window_start)}; coverage {s.coverage.value}: "
          f"{s.coverage.reason}")
    for label, point in (("oldest", s.oldest), ("2nd", s.points[1] if len(s.points) > 1 else None),
                         ("newest", s.newest)):
        if point is None:
            continue
        alone = freshness(point, feeds[target], block.timestamp, margin)
        print(f"   {label:6} round {point.source_ref} at {_iso(point.source_time)}, "
              f"age {_dur(block.timestamp.epoch_ms - point.source_time.epoch_ms):10} "
              f"price {point.value.raw}; judged alone it would be fresh={alone.value}")
    verdict = series_freshness(s, feeds[target], block.timestamp, margin)
    print(f"   the series' verdict judges the newest point only: fresh={verdict.value} ({verdict.reason})")
    print("   every point at the pinned block:", all(p.block == block for p in s.points))
    same = lambda o: (o.status, o.value, o.source_time, o.source_ref, o.block)  # noqa: E731
    again = read.latest_rounds(feeds)
    s2 = read.price_series(target, feeds[target], window_s=settings.window_s,
                           max_rounds=settings.max_rounds,
                           scale_break_ratio=settings.scale_break_ratio)
    print(f"   read again at the same block: {sum(same(rounds[a]) == same(again[a]) for a in feeds)}"
          f"/{len(feeds)} feeds identical; {series_asset} series identical: "
          f"{[same(p) for p in s.points] == [same(p) for p in s2.points] and s.coverage == s2.coverage}"
          "\n")

    print(f"== 4. the same walk for every feed, to see which real series come back short")
    short = 0
    for asset, f in feeds.items():
        s = read.price_series(asset, f, window_s=settings.window_s, max_rounds=settings.max_rounds,
                              scale_break_ratio=settings.scale_break_ratio)
        if s.coverage.value is not True:
            short += 1
        print(f"   {symbol[asset]:6} {len(s.points):>4} points  coverage {s.coverage.value!s:5} "
              f"{'' if s.coverage.value is True else s.coverage.reason}")
    print(f"   {short} of {len(feeds)} short or undetermined\n")

    print("== 5. a constructed mixed-block read")
    earlier = pin_block(rpc, settings.chain_id, hex(block.number - 1))
    one = by_symbol["AAPL"]
    here = rounds[one]
    there = settings.reader(rpc, earlier).latest_rounds({one: feeds[one]})[one]
    print(f"   AAPL read at {block.number} and at {earlier.number} ({earlier.hash[:18]}…)")
    try:
        require_one_block([here, there], block)
        print("   NOT REFUSED — this is a failure of the proof")
        return 1
    except MixedBlocks as refused:
        print(f"   refused: {type(refused).__name__}: {refused}\n")

    print("== 6. unreachable, and a hang that the failover moves past")
    closed = socket.socket()
    closed.bind(("127.0.0.1", 0))
    port = closed.getsockname()[1]
    closed.close()  # nothing listens here now: a real connection refusal
    dead = RpcClient([Endpoint("DEAD_LOCAL", f"http://127.0.0.1:{port}")], timeout_s=3,
                     attempts=1, backoff_s=0, min_interval_s=0,
                     transport=urllib_transport(settings.user_agent))
    gone = ChainReader(dead, block, multicall3=settings.multicall3, chunk=settings.chunk,
                       clock=wall_clock).latest_rounds({one: feeds[one]})[one]
    verdict = freshness(gone, feeds[one], block.timestamp, margin)
    print(f"   AAPL via a refused endpoint: status {gone.status.value}; freshness {verdict.value} "
          f"(is False: {verdict.value is False}); {verdict.reason}")
    silent = socket.socket()
    silent.bind(("127.0.0.1", 0))
    silent.listen(8)  # accepts at the kernel, never answers
    try:
        hung = RpcClient([Endpoint("HANGS_LOCAL", f"http://127.0.0.1:{silent.getsockname()[1]}"),
                          *rpc.endpoints], timeout_s=3, attempts=1, backoff_s=0,
                         min_interval_s=settings.min_interval_s,
                         transport=urllib_transport(settings.user_agent))
        started = time.monotonic()
        reading = ChainReader(hung, block, multicall3=settings.multicall3, chunk=settings.chunk,
                              clock=wall_clock).latest_rounds({one: feeds[one]})[one]
        print(f"   AAPL via [HANGS_LOCAL, {rpc.endpoints[0].name}]: status {reading.status.value}, "
              f"round {reading.source_ref}, same as the direct read: "
              f"{reading.source_ref == here.source_ref}; took {time.monotonic() - started:.1f}s")
    finally:
        silent.close()
    return 0


if __name__ == "__main__":
    import sys

    if sys.argv[1:] != ["--prove"]:
        print("usage: python -m fund.adapters.chain_4663 --prove")
        sys.exit(2)
    sys.exit(prove())
