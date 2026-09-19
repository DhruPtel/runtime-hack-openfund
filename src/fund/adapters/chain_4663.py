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
- **A User-Agent on every request.** The RPC returns 403 without one, and that
  403 looks like an auth failure (probe 0.3).
- **Explicit timeouts, and failover that advances on a hang.** Every request
  has a whole-request deadline. A hang or a dead connection moves on to the
  next endpoint; a 429 or 5xx backs off and tries again. The RPC's 429 carries
  no `Retry-After`, so the backoff has no server hint (measured 2026-09-18).
  There is one endpoint today, so the failover has nowhere to go
  (`config/chain.json`).
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
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Sequence

from fund import redaction
from fund.core import universe
from fund.core.types import (
    USD, Amount, AssetId, BlockRef, ChainAddress, Check, FeedRef, FetchStatus, Fixed, Instant,
    Observation, Price, Series, Source,
)

RULE_TRANSPORT = "transport"
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


# --- transport -----------------------------------------------------------------

#: `(url, body, timeout_s) -> (http_status, body)`. Injected so tests can hang,
#: refuse or rate-limit on purpose, with no network.
Transport = Callable[[str, bytes, float], tuple[int, bytes]]


def urllib_transport(user_agent: str) -> Transport:
    def send(url: str, body: bytes, timeout_s: float) -> tuple[int, bytes]:
        request = urllib.request.Request(url, data=body, headers={
            "Content-Type": "application/json", "Accept": "application/json",
            "User-Agent": user_agent})
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return response.status, response.read()
        except urllib.error.HTTPError as error:
            return error.code, error.read()
    return send


@dataclass(frozen=True)
class Endpoint:
    name: str                          # the credential's name: what errors show
    url: str = field(repr=False)       # the secret itself: never shown


class _Hang(Exception):
    pass


def _with_deadline(fn: Callable[[], Any], deadline_s: float) -> Any:
    """Run `fn`, or give up after `deadline_s` of wall-clock time.

    A socket timeout only bounds each blocking operation. A server that trickles
    bytes, or accepts and then says nothing, can outlast it, and that is the
    hang the failover must advance on.
    """
    box: dict[str, Any] = {}

    def run():
        try:
            box["value"] = fn()
        except BaseException as error:  # handed back to the caller below
            box["error"] = error

    worker = threading.Thread(target=run, daemon=True)
    worker.start()
    worker.join(deadline_s)
    if worker.is_alive():
        raise _Hang()
    if "error" in box:
        raise box["error"]
    return box["value"]


class RpcClient:
    """JSON-RPC over an ordered list of endpoints.

    Each pass tries every endpoint once, in order:
    - a hang, a dead connection or an unparseable body moves straight on to the
      next endpoint;
    - a 429 or 5xx, or a JSON-RPC 429, also moves on, and is retried on the
      next pass.

    Passes are separated by a doubling backoff, up to `attempts` passes. Every
    request waits out `min_interval_s` since the previous one.
    """

    def __init__(self, endpoints: Sequence[Endpoint], *, timeout_s: float, attempts: int,
                 backoff_s: float, min_interval_s: float, transport: Transport,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic):
        if not endpoints:
            raise ValueError("at least one endpoint")
        self.endpoints = tuple(endpoints)
        self.timeout_s, self.attempts = timeout_s, attempts
        self.backoff_s, self.min_interval_s = backoff_s, min_interval_s
        self._transport, self._sleep, self._monotonic = transport, sleep, monotonic
        self._last_request: float | None = None
        self._redactor = redaction.Redactor()
        self._next_id = 1

    def _scrub(self, text: str) -> str:
        """Mask declared credentials, and every endpoint URL by its name. An
        exception from the transport can quote the URL, and the URL is the
        secret; the redactor alone masks it only if it is loaded as a
        credential."""
        for endpoint in self.endpoints:
            text = text.replace(endpoint.url, f"<{endpoint.name}>")
        return self._redactor.redact(text)

    def _pace(self) -> None:
        if self._last_request is not None:
            wait = self.min_interval_s - (self._monotonic() - self._last_request)
            if wait > 0:
                self._sleep(wait)
        self._last_request = self._monotonic()

    def _post(self, payload: Any) -> Any:
        body = json.dumps(payload).encode("utf-8")
        failures: list[tuple[str, str]] = []
        for attempt in range(self.attempts):
            if attempt:
                self._sleep(self.backoff_s * 2 ** (attempt - 1))
            for endpoint in self.endpoints:
                self._pace()
                try:
                    status, raw = _with_deadline(
                        lambda: self._transport(endpoint.url, body, self.timeout_s), self.timeout_s)
                except _Hang:
                    failures.append((endpoint.name, f"hang: no complete response in {self.timeout_s}s"))
                    continue
                except Exception as error:  # DNS, TLS, reset, socket timeout
                    failures.append((endpoint.name, "unreachable: " + self._scrub(
                        f"{type(error).__name__}: {error}")))
                    continue
                if status == 429:
                    failures.append((endpoint.name, "rate limited: HTTP 429, no Retry-After"))
                    continue
                if status == 403:
                    failures.append((endpoint.name, "HTTP 403: a missing User-Agent reads "
                                                    "exactly like this (probe 0.3)"))
                    continue
                if status != 200:
                    failures.append((endpoint.name, f"HTTP {status}"))
                    continue
                try:
                    parsed = json.loads(raw)
                except ValueError:
                    failures.append((endpoint.name, "a 200 whose body is not JSON"))
                    continue
                if isinstance(parsed, dict) and (parsed.get("error") or {}).get("code") == 429:
                    failures.append((endpoint.name, "rate limited: JSON-RPC 429"))
                    continue
                return parsed
        raise RpcUnavailable(failures)

    def call(self, method: str, params: list) -> Any:
        """One JSON-RPC call. Returns `result`, raises RpcError or RpcUnavailable."""
        request_id, self._next_id = self._next_id, self._next_id + 1
        response = self._post({"jsonrpc": "2.0", "id": request_id, "method": method,
                               "params": params})
        if not isinstance(response, dict) or ("error" not in response and "result" not in response):
            raise RpcError(None, "a reply with neither result nor error")
        if "error" in response:
            error = response["error"] or {}
            raise RpcError(error.get("code"), self._scrub(str(error.get("message"))))
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

    def decimals(self, tokens: Sequence[AssetId]) -> dict[AssetId, Observation]:
        calls = [(t.address, bytes.fromhex(SEL_DECIMALS)) for t in tokens]
        try:
            results = self.multicall(calls)
        except ChainError as error:
            return {t: self._failed(Source("erc20", t.address), error) for t in tokens}
        out = {}
        for token, (ok, data) in zip(tokens, results):
            source = Source("erc20", token.address)
            out[token] = (self._observe(source, value=Fixed(_uint(data, 0), 0, "decimals"))
                          if ok and len(data) >= 32 else
                          self._observe(source, status=FetchStatus.REFUSED,
                                        detail="decimals() reverted or returned nothing"))
        return out

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
