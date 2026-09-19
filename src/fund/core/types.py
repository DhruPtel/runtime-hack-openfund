"""The contracts every other module imports, defined once. Unit 1.1.

Each rule below is enforced at construction, not merely documented, because a
type that only *describes* a rule lets the violation through the first time
someone is in a hurry (planning/CODEBASE.md §1 and §4):

- **Every number carries its units.** A quantity is a raw integer, its decimals,
  and what it measures. No float is accepted anywhere, and none is ever
  encoded. There is no default for decimals: USDG is 6 and stock tokens are 18,
  and a documented source said USDG was 18 (findings F0.3.1).
- **Source time and fetch time are separate fields, always.**
- **Verification is three-valued.** `Check.value` is True, False or None, and
  None means undetermined, which is not False. Only True passes.
- **Assets are keyed by `(chain_id, address)`.** A ticker is display text and
  never resolves anything.
- **Canonical JSON is the only serialisation**: sorted keys, no whitespace, no
  floats. Integers that can exceed 2**53 — raw token amounts, Chainlink round
  ids — are encoded as decimal strings, because the records are read by
  JavaScript clients, and a JSON number above 2**53 loses precision there.

Threshold comparisons are **not** defined here. `core/gates.py` is the only
module that may define one (CODEBASE §3). This module supplies exact ordering on
like-for-like quantities, and nothing more.

`core/` imports nothing from `adapters/`: this module is stdlib only.

Deliberately absent: `AnalystReport`, `Proposal`, `Plan`, `Decision`,
`JournalEvent` and `Statement`. Nothing in the record fixes their shapes yet, and
2.1 requires the report format to be designed by hand before any code. Each
arrives with the unit that designs it (tracker/LESSONS.md 2026-09-18).
"""

from __future__ import annotations

import enum
import functools
import hashlib
import json
import re
import typing
from dataclasses import dataclass, field, fields, is_dataclass
from typing import Any

# --- canonical encoding --------------------------------------------------------

#: Field metadata marking an int that is encoded as a decimal string.
AS_STR = {"as_str": True}

#: The largest integer JSON can carry without loss in a JavaScript reader.
MAX_SAFE_JSON_INT = 2**53 - 1

_REGISTRY: dict[str, type] = {}


def canonical(cls):
    """Register a dataclass for canonical encoding under its class name."""
    if cls.__name__ in _REGISTRY:
        raise TypeError(f"duplicate canonical type {cls.__name__}")
    _REGISTRY[cls.__name__] = cls
    return cls


def _encode(obj: Any) -> Any:
    if obj is None or isinstance(obj, (bool, str)):
        return obj
    if isinstance(obj, float):
        raise TypeError("a float is never encoded; use Fixed, Amount or Price")
    if type(obj) is int:
        if abs(obj) > MAX_SAFE_JSON_INT:
            raise ValueError(f"{obj} exceeds 2**53; it must be an AS_STR field")
        return obj
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, (tuple, list)):
        return [_encode(item) for item in obj]
    if is_dataclass(obj) and _REGISTRY.get(type(obj).__name__) is type(obj):
        out: dict[str, Any] = {"_type": type(obj).__name__}
        for f in fields(obj):
            value = getattr(obj, f.name)
            if f.metadata.get("as_str") and value is not None:
                out[f.name] = str(value)
            else:
                out[f.name] = _encode(value)
        return out
    raise TypeError(f"cannot encode {type(obj).__name__}")


def to_canonical(obj: Any) -> bytes:
    """The one byte representation of a value. Same value, same bytes."""
    return json.dumps(_encode(obj), sort_keys=True, separators=(",", ":"),
                      ensure_ascii=False, allow_nan=False).encode("utf-8")


def content_id(obj: Any) -> str:
    """sha256 of the canonical bytes: the id every derived artifact cites."""
    return hashlib.sha256(to_canonical(obj)).hexdigest()


_INT_STR = re.compile(r"^-?(0|[1-9][0-9]*)$")


@functools.cache
def _enum_fields(cls: type) -> dict[str, type]:
    """Fields whose declared type is an Enum (optionally `| None`)."""
    found = {}
    for name, hint in typing.get_type_hints(cls).items():
        options = typing.get_args(hint) or (hint,)
        for option in options:
            if isinstance(option, type) and issubclass(option, enum.Enum):
                found[name] = option
    return found


def _decode(data: Any) -> Any:
    if isinstance(data, list):
        return tuple(_decode(item) for item in data)
    if isinstance(data, float):
        raise TypeError("a float is never decoded")
    if not isinstance(data, dict):
        return data
    name = data.get("_type")
    cls = _REGISTRY.get(name)
    if cls is None:
        raise ValueError(f"unknown canonical type {name!r}")
    declared = {f.name: f for f in fields(cls)}
    extra = set(data) - set(declared) - {"_type"}
    if extra:
        raise ValueError(f"{name}: unexpected fields {sorted(extra)}")
    enums = _enum_fields(cls)
    kwargs = {}
    for fname, f in declared.items():
        if fname not in data:
            raise ValueError(f"{name}: missing field {fname}")
        raw = data[fname]
        if f.metadata.get("as_str") and raw is not None:
            if not isinstance(raw, str) or not _INT_STR.match(raw):
                raise ValueError(f"{name}.{fname}: not a canonical integer string")
            kwargs[fname] = int(raw)
        elif fname in enums and raw is not None:
            kwargs[fname] = enums[fname](raw)
        else:
            kwargs[fname] = _decode(raw)
    return cls(**kwargs)


def from_canonical(blob: bytes) -> Any:
    """Inverse of `to_canonical`. Every constructor invariant runs again."""
    return _decode(json.loads(blob.decode("utf-8")))


# --- small validators ----------------------------------------------------------

_ADDRESS = re.compile(r"^0x[0-9a-fA-F]{40}$")
_HASH32 = re.compile(r"^0x[0-9a-f]{64}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


def _int(name: str, value: Any, *, minimum: int | None = None) -> None:
    # `type(...) is int` rejects bool and float, which isinstance would not.
    if type(value) is not int:
        raise TypeError(f"{name} must be an int, got {type(value).__name__}")
    if minimum is not None and value < minimum:
        raise ValueError(f"{name} must be >= {minimum}, got {value}")


def _text(name: str, value: Any, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} must be non-empty text")


def _is(name: str, value: Any, kinds: type | tuple, *, optional: bool = False) -> None:
    if value is None and optional:
        return
    if not isinstance(value, kinds):
        raise TypeError(f"{name} must be {kinds}, got {type(value).__name__}")


def _tuple_of(obj: Any, name: str, kinds: type | tuple) -> None:
    value = getattr(obj, name)
    if isinstance(value, list):
        value = tuple(value)
        object.__setattr__(obj, name, value)
    if not isinstance(value, tuple):
        raise TypeError(f"{name} must be a tuple")
    for item in value:
        _is(f"{name}[]", item, kinds)


# --- time ----------------------------------------------------------------------

@canonical
@dataclass(frozen=True, slots=True, order=True)
class Instant:
    """A UTC instant in integer milliseconds since the epoch. The unit is the name."""

    epoch_ms: int

    def __post_init__(self):
        _int("epoch_ms", self.epoch_ms, minimum=0)

    @classmethod
    def from_seconds(cls, seconds: int) -> Instant:
        _int("seconds", seconds, minimum=0)
        return cls(seconds * 1000)


# --- addresses and identity ----------------------------------------------------

def _address(obj: Any) -> None:
    _int("chain_id", obj.chain_id, minimum=1)
    if not isinstance(obj.address, str) or not _ADDRESS.match(obj.address):
        raise ValueError(f"not an EVM address: {obj.address!r}")
    # The registry and the chain write EIP-55 mixed case (F0.8.1); identity
    # compares case-insensitively, so the key is normalised once, here.
    object.__setattr__(obj, "address", obj.address.lower())


@canonical
@dataclass(frozen=True, slots=True, order=True)
class ChainAddress:
    """Any EVM account or contract on a named chain: a wallet, a feed, a bundler."""

    chain_id: int
    address: str

    def __post_init__(self):
        _address(self)


#: The native-gas sentinel Bankr's swap API uses for ETH (docs.bankr.bot
#: wallet-api/swap). Native ETH has no contract address; keying it by this
#: sentinel keeps every asset keyed by `(chain_id, address)`.
NATIVE_SENTINEL = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"


@canonical
@dataclass(frozen=True, slots=True, order=True)
class AssetId:
    """What an asset *is*: `(chain_id, address)`. Never a ticker."""

    chain_id: int
    address: str

    def __post_init__(self):
        _address(self)

    @classmethod
    def native(cls, chain_id: int) -> AssetId:
        return cls(chain_id, NATIVE_SENTINEL)

    @property
    def is_native(self) -> bool:
        return self.address == NATIVE_SENTINEL


# --- quantities ----------------------------------------------------------------

USD = "USD"
BPS = "bps"
SECONDS = "s"
PERCENT = "%"
MULTIPLE = "x"

_DECIMAL_TEXT = re.compile(r"^-?[0-9]+(\.[0-9]+)?$")
_MAX_DECIMALS = 36


def _parse_decimal(text: str) -> tuple[int, int]:
    """Exact: '1.0022' -> (10022, 4). No float is ever involved."""
    if not isinstance(text, str) or not _DECIMAL_TEXT.match(text):
        raise ValueError(f"not a plain decimal: {text!r}")
    whole, _, frac = text.partition(".")
    return int(whole + frac), len(frac)


def _aligned(a_raw: int, a_dec: int, b_raw: int, b_dec: int) -> tuple[int, int]:
    scale = max(a_dec, b_dec)
    return a_raw * 10 ** (scale - a_dec), b_raw * 10 ** (scale - b_dec)


class _Ordered:
    """Exact ordering between like quantities. Unlike ones refuse to compare."""

    __slots__ = ()

    def _pair(self, other) -> tuple[int, int]:
        raise NotImplementedError

    def __lt__(self, other):
        a, b = self._pair(other)
        return a < b

    def __le__(self, other):
        a, b = self._pair(other)
        return a <= b

    def __gt__(self, other):
        a, b = self._pair(other)
        return a > b

    def __ge__(self, other):
        a, b = self._pair(other)
        return a >= b

    def same_value(self, other) -> bool:
        """Numeric equality across representations (1 vs 1.0). `==` is structural."""
        a, b = self._pair(other)
        return a == b


@canonical
@dataclass(frozen=True, slots=True)
class Fixed(_Ordered):
    """A signed fixed-point quantity: `raw / 10**decimals`, measured in `unit`.

    Signed on purpose. Price impact comes back negative when it is price
    improvement — four of six quotes in probe 0.3 (F0.3.4) — and divergence has
    a direction. A type that assumed a positive value would reject the fund's
    best fills.
    """

    raw: int = field(metadata=AS_STR)
    decimals: int
    unit: str

    def __post_init__(self):
        _int("raw", self.raw)
        _int("decimals", self.decimals, minimum=0)
        if self.decimals > _MAX_DECIMALS:
            raise ValueError("decimals out of range")
        _text("unit", self.unit)

    @classmethod
    def parse(cls, text: str, unit: str) -> Fixed:
        raw, decimals = _parse_decimal(text)
        return cls(raw, decimals, unit)

    def _pair(self, other):
        if not isinstance(other, Fixed):
            raise TypeError(f"cannot compare Fixed with {type(other).__name__}")
        if other.unit != self.unit:
            raise TypeError(f"cannot compare {self.unit} with {other.unit}")
        return _aligned(self.raw, self.decimals, other.raw, other.decimals)


@canonical
@dataclass(frozen=True, slots=True)
class Amount(_Ordered):
    """A token quantity: `(raw, decimals, asset)`, the one amount shape (CODEBASE §4).

    Signed, so a balance delta can be expressed. `decimals` has no default: it is
    read on chain per asset — USDG 6, stock tokens 18 (F0.3.1).
    """

    raw: int = field(metadata=AS_STR)
    decimals: int
    asset: AssetId

    def __post_init__(self):
        _int("raw", self.raw)
        _int("decimals", self.decimals, minimum=0)
        if self.decimals > _MAX_DECIMALS:
            raise ValueError("decimals out of range")
        _is("asset", self.asset, AssetId)

    @classmethod
    def from_units(cls, text: str, decimals: int, asset: AssetId) -> Amount:
        """Exact conversion of a human amount ('0.00003') to raw units."""
        raw, places = _parse_decimal(text)
        _int("decimals", decimals, minimum=0)
        if places > decimals:
            raise ValueError(f"{text!r} has more than {decimals} decimal places")
        return cls(raw * 10 ** (decimals - places), decimals, asset)

    def _pair(self, other):
        if not isinstance(other, Amount):
            raise TypeError(f"cannot compare Amount with {type(other).__name__}")
        if other.asset != self.asset:
            raise TypeError("cannot compare amounts of different assets")
        if other.decimals != self.decimals:
            raise TypeError("one asset with two decimal counts is a bug upstream")
        return self.raw, other.raw


@canonical
@dataclass(frozen=True, slots=True)
class Price(_Ordered):
    """The price of one whole `base` token in `quote_unit`: `raw / 10**decimals`.

    A Chainlink answer is `Price(answer, 8, asset, "USD")` (F0.4.7).
    """

    raw: int = field(metadata=AS_STR)
    decimals: int
    base: AssetId
    quote_unit: str

    def __post_init__(self):
        _int("raw", self.raw)
        _int("decimals", self.decimals, minimum=0)
        if self.decimals > _MAX_DECIMALS:
            raise ValueError("decimals out of range")
        _is("base", self.base, AssetId)
        _text("quote_unit", self.quote_unit)

    @classmethod
    def parse(cls, text: str, base: AssetId, quote_unit: str) -> Price:
        """Exact, from decimal text. Bankr sends prices as JSON floats
        (`1.0022236982588135`); the adapter passes their shortest text here."""
        raw, decimals = _parse_decimal(text)
        return cls(raw, decimals, base, quote_unit)

    def _pair(self, other):
        if not isinstance(other, Price):
            raise TypeError(f"cannot compare Price with {type(other).__name__}")
        if (other.base, other.quote_unit) != (self.base, self.quote_unit):
            raise TypeError("cannot compare prices of different pairs")
        return _aligned(self.raw, self.decimals, other.raw, other.decimals)


# --- provenance ----------------------------------------------------------------

@canonical
@dataclass(frozen=True, slots=True)
class BlockRef:
    """A block on a named chain. `timestamp` is the block's own time, when read."""

    chain_id: int
    number: int
    timestamp: Instant | None = None
    hash: str | None = None

    def __post_init__(self):
        _int("chain_id", self.chain_id, minimum=1)
        _int("number", self.number, minimum=0)
        _is("timestamp", self.timestamp, Instant, optional=True)
        if self.hash is not None and not _HASH32.match(self.hash):
            raise ValueError("block hash must be 0x + 64 lowercase hex")


@canonical
@dataclass(frozen=True, slots=True)
class Source:
    """Where a datum came from: a system and a locator within it.

    A locator is an address or a path, never a URL: the RPC URL is a declared
    credential, so a scheme is refused outright rather than hoped to be redacted.
    """

    system: str
    locator: str

    def __post_init__(self):
        _text("system", self.system)
        _text("locator", self.locator)
        if "://" in self.locator:
            raise ValueError("a Source locator is a path or address, never a URL")


# --- three-valued verification -------------------------------------------------

@canonical
@dataclass(frozen=True, slots=True)
class Check:
    """A verification result: True, False, or None — and None is not False.

    None means undetermined — the source was unreachable, or the check could not
    run — and it must say why. Only True passes; a required check that is None
    blocks (PLAN §2 invariant 5).
    """

    value: bool | None
    reason: str | None = None

    def __post_init__(self):
        if self.value is not None and type(self.value) is not bool:
            raise TypeError("Check.value must be True, False or None")
        if self.value is None:
            _text("reason (an undetermined check must say why)", self.reason)
        else:
            _text("reason", self.reason, optional=True)

    @property
    def passes(self) -> bool:
        return self.value is True

    @classmethod
    def undetermined(cls, reason: str) -> Check:
        return cls(None, reason)


# --- observations and series ---------------------------------------------------

class FetchStatus(enum.Enum):
    """What happened when a source was asked. Distinct from what it said.

    An unreachable source is not a source that said "false" or "zero". Folding
    them together is how a dead RPC turns into a price of zero.
    """

    OK = "ok"
    ABSENT = "absent"            # the source answered; this field was not in it (F0.3.2)
    UNREACHABLE = "unreachable"  # no answer: timeout, DNS, connection reset
    REFUSED = "refused"          # an answer that is an error: 4xx or 5xx, with its body


#: What an Observation may carry. Extended below, once Quote is defined.
_VALUE_TYPES: tuple[type, ...] = (Fixed, Amount, Price, AssetId, ChainAddress)


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Observation:
    """One datum with its provenance: value, source, source time, fetch time, block.

    `source_time` is when the datum was true, as the source states it — a feed's
    `updatedAt`, a candle's open. `fetch_time` is when this code saw it, from
    this code's own clock. They are separate always. The replay rules compare
    them, and a quote carries no source time at all, so its age is ours to
    measure (1.5).

    `block` is the block the read was made at, for a chain read, and None for an
    offchain source. `source_ref` is the source's own id for the datum — a
    Chainlink round id, a `quoteId`, a registry id — kept as text because round
    ids exceed 2**53.
    """

    value: Any
    source: Source
    source_time: Instant | None
    fetch_time: Instant
    block: BlockRef | None
    status: FetchStatus
    detail: str | None = None
    source_ref: str | None = None

    def __post_init__(self):
        _is("source", self.source, Source)
        _is("source_time", self.source_time, Instant, optional=True)
        _is("fetch_time", self.fetch_time, Instant)
        _is("block", self.block, BlockRef, optional=True)
        _is("status", self.status, FetchStatus)
        _text("source_ref", self.source_ref, optional=True)
        if self.status is FetchStatus.OK:
            _is("value", self.value, _VALUE_TYPES)
            _text("detail", self.detail, optional=True)
        else:
            if self.value is not None:
                raise ValueError(f"a {self.status.value} observation carries no value")
            _text("detail (say why there is no value)", self.detail)

    @property
    def ok(self) -> bool:
        return self.status is FetchStatus.OK


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Series:
    """An asset's history from one source, oldest first, up to a pinned block.

    Freshness binds the **newest point only** (decision 2026-09-18). A series
    is mostly old data by definition, and each historical point carries its own
    timestamp. So this type accepts a week-old oldest point beside a fresh
    newest one, and exposes the newest point's age for the staleness rule in
    1.3 to judge. The rule itself lives in 1.3, not here.

    **A short series is visible as short.** When a window was asked for
    (`window_start`), `coverage` says whether the points reach back to it:
    - True: the oldest point is at or before `window_start`;
    - False: the history does not reach it, and the reason says why — the feed
      is younger, a round cap was hit, or a scale break was found;
    - None: a read failed partway, so it is undetermined.

    Construction refuses a coverage claim the points cannot back. Every point
    must also come from one block, or from none (offchain); a mixed-block series
    is an error, not a warning.
    """

    asset: AssetId
    source: Source
    fetch_time: Instant
    status: FetchStatus
    points: tuple[Observation, ...] = ()
    detail: str | None = None
    window_start: Instant | None = None
    coverage: Check | None = None

    def __post_init__(self):
        _is("asset", self.asset, AssetId)
        _is("source", self.source, Source)
        _is("fetch_time", self.fetch_time, Instant)
        _is("status", self.status, FetchStatus)
        _tuple_of(self, "points", Observation)
        if self.status is not FetchStatus.OK:
            if self.points:
                raise ValueError("a series that was not fetched has no points")
            _text("detail (say why there is no series)", self.detail)
            return
        if not self.points:
            raise ValueError("a fetched series has at least one point")
        kind = type(self.points[0].value)
        previous = None
        for point in self.points:
            if not point.ok:
                raise ValueError("every point in a series is an OK observation")
            if point.source != self.source:
                raise ValueError("every point comes from the series' source")
            if point.source_time is None:
                raise ValueError("history needs each point's own timestamp")
            if type(point.value) is not kind:
                raise TypeError("a series holds one kind of value")
            if isinstance(point.value, Price) and point.value.base != self.asset:
                raise ValueError("a price point must be for the series' asset")
            if previous is not None and point.source_time < previous:
                raise ValueError("points run oldest first")
            previous = point.source_time
        if len({point.block for point in self.points}) > 1:
            raise ValueError("block-pin: a series' points come from one block")
        _is("window_start", self.window_start, Instant, optional=True)
        _is("coverage", self.coverage, Check, optional=True)
        if self.window_start is not None and self.coverage is None:
            raise ValueError("a series asked for a window says whether it covers it")
        if self.coverage is not None and self.coverage.value is True:
            if self.window_start is None:
                raise ValueError("coverage is judged against a requested window")
            if self.points[0].source_time > self.window_start:
                raise ValueError("coverage claimed, but the oldest point is after the window start")

    @property
    def oldest(self) -> Observation | None:
        return self.points[0] if self.points else None

    @property
    def newest(self) -> Observation | None:
        return self.points[-1] if self.points else None

    def age_of_newest_ms(self, as_of: Instant) -> int | None:
        """How old the newest point is at `as_of`. The only age that is judged."""
        _is("as_of", as_of, Instant)
        if self.newest is None:
            return None
        return as_of.epoch_ms - self.newest.source_time.epoch_ms


# --- assets: identity and markability, kept apart ------------------------------

@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class FeedRef:
    """A Chainlink feed as the pinned directory describes it (F0.4.1).

    The directory writes `threshold` as a JSON float (0.5). The adapter converts
    it with `Fixed.parse(str(...))`; this type refuses the float itself.
    """

    proxy: ChainAddress
    decimals: int
    heartbeat: Fixed          # seconds; 86,400 for the equity feeds
    deviation_threshold: Fixed  # percent
    market_hours: str | None  # e.g. "us_equities_24/5"
    name: str

    def __post_init__(self):
        _is("proxy", self.proxy, ChainAddress)
        _int("decimals", self.decimals, minimum=0)
        _is("heartbeat", self.heartbeat, Fixed)
        _is("deviation_threshold", self.deviation_threshold, Fixed)
        if self.heartbeat.unit != SECONDS or self.deviation_threshold.unit != PERCENT:
            raise ValueError("heartbeat is in seconds and deviation in percent")
        _text("market_hours", self.market_hours, optional=True)
        _text("name", self.name)


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Deployment:
    """One entry of a registry record's `deployments`. Not assumed to be the only one."""

    contract: ChainAddress
    network_name: str

    def __post_init__(self):
        _is("contract", self.contract, ChainAddress)
        _text("network_name", self.network_name)


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class TradingCapability:
    """One cell of the registry's `tradingCapabilities`: session × lot → status."""

    session: str  # market, extended, overnight
    lot: str      # whole, fractional
    status: str   # as reported, e.g. TRADING_STATUS_UNTRADABLE

    def __post_init__(self):
        for name in ("session", "lot", "status"):
            _text(name, getattr(self, name))


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class RegistryRecord:
    """An issuer registry entry, as given (`api.robinhood.com/rhj/assets`, F0.8.1).

    `status` is kept as the source's text, not an enum of the one value ever
    seen (`ASSET_STATUS_ACTIVE`). `deployments` is kept as a tuple, not assumed
    to have length 1. The registry writes an empty `pendingMultiplier` for "none";
    that is None here, never zero.
    """

    registry_id: str
    symbol: str   # display only
    name: str
    isin: str
    status: str
    decimals: int
    deployments: tuple[Deployment, ...]
    current_multiplier: Fixed
    pending_multiplier: Fixed | None
    trading_capabilities: tuple[TradingCapability, ...] = ()

    def __post_init__(self):
        for name in ("registry_id", "symbol", "name", "isin", "status"):
            _text(name, getattr(self, name))
        _int("decimals", self.decimals, minimum=0)
        _tuple_of(self, "deployments", Deployment)
        if not self.deployments:
            raise ValueError("a registry record lists at least one deployment")
        _tuple_of(self, "trading_capabilities", TradingCapability)
        for name in ("current_multiplier", "pending_multiplier"):
            value = getattr(self, name)
            _is(name, value, Fixed, optional=name == "pending_multiplier")
            if value is not None and value.unit != MULTIPLE:
                raise ValueError(f"{name} is a multiple")

    def deploys(self, asset: AssetId) -> bool:
        return any(d.contract.chain_id == asset.chain_id
                   and d.contract.address == asset.address for d in self.deployments)


class AssetKind(enum.Enum):
    STOCK = "stock"  # identity from the issuer registry
    CASH = "cash"    # USDG: genuine, not in the registry, pinned by config (F0.8.2)
    GAS = "gas"      # native ETH


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Asset:
    """An asset and what we know about it, as three separate verdicts.

    - `identity`: is this the real one? For a stock, that means registry
      membership on `(chain_id, address)`.
    - `markability`: can it be marked independently of the venue? That means a
      pinned Chainlink feed exists.
    - `beacon`: the independent-root cross-check. It applies to stocks only, and
      is None — not applicable — for cash and gas.

    They are never folded into one status. Feed presence admitted both GME
    counterfeits (F0.8.3), and CRM is genuine, registry-listed and correctly
    unmarkable (F0.8.2). A single status would have to get one of those wrong.
    """

    id: AssetId
    kind: AssetKind
    symbol: str    # display only: never looked up, never a key
    decimals: int
    identity: Check
    markability: Check
    beacon: Check | None
    registry: RegistryRecord | None = None
    feed: FeedRef | None = None

    def __post_init__(self):
        _is("id", self.id, AssetId)
        _is("kind", self.kind, AssetKind)
        _text("symbol", self.symbol)
        _int("decimals", self.decimals, minimum=0)
        _is("identity", self.identity, Check)
        _is("markability", self.markability, Check)
        _is("registry", self.registry, RegistryRecord, optional=True)
        _is("feed", self.feed, FeedRef, optional=True)
        if self.markability.value is True and self.feed is None:
            raise ValueError("markable means a feed is pinned")
        if self.feed is not None and self.feed.proxy.chain_id != self.id.chain_id:
            raise ValueError("a feed marks an asset on its own chain")
        if self.kind is AssetKind.STOCK:
            _is("beacon", self.beacon, Check)
            if self.identity.value is True:
                if self.registry is None or not self.registry.deploys(self.id):
                    raise ValueError("a stock's identity is its registry record")
            if self.registry is not None and self.registry.decimals != self.decimals:
                raise ValueError("registry decimals disagree with the asset's")
        else:
            if self.beacon is not None:
                raise ValueError("the beacon cross-check applies to stocks only")
            if self.registry is not None:
                raise ValueError("cash and gas are not registry assets")
        if self.kind is AssetKind.GAS and not self.id.is_native:
            raise ValueError("the gas asset is the chain's native token")


# --- quotes --------------------------------------------------------------------

@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Quote:
    """A `/wallet/swap-quote` response: a price at size, and nothing more.

    A quote is not evidence of executability. It is not balance-checked
    (F0.3.3), and stock execution is gated (F0.5.1).

    Impact is **signed**. Negative is price improvement, and four of six quotes
    in probe 0.3 came back negative (F0.3.4). Every impact field is optional,
    because all 12 documented fields appearing in six responses is not a
    guarantee (F0.3.2); an absent impact is None, and None blocks. The field that
    gates is `swap_impact` (documented).

    `sell_price` and `buy_price` are the venue's own USD prices (F0.3.5). They
    are recorded, and never used as a mark (F0.4.4).

    A quote carries no timestamp. Its age comes from the fetch time of the
    Observation that wraps it.
    """

    sell: Amount
    buy: Amount
    min_buy: Amount
    price_impact: Fixed | None
    swap_impact: Fixed | None
    max_price_impact: Fixed | None
    fee: Fixed | None
    fee_waived: bool | None
    slippage: Fixed | None
    sell_price: Price | None
    buy_price: Price | None
    quote_id: str | None

    def __post_init__(self):
        for name in ("sell", "buy", "min_buy"):
            _is(name, getattr(self, name), Amount)
        if self.min_buy.asset != self.buy.asset:
            raise ValueError("min_buy is an amount of the bought asset")
        if self.sell.asset == self.buy.asset:
            raise ValueError("a quote sells one asset for another")
        for name in ("price_impact", "swap_impact", "max_price_impact", "fee", "slippage"):
            value = getattr(self, name)
            _is(name, value, Fixed, optional=True)
            if value is not None and value.unit != BPS:
                raise ValueError(f"{name} is in basis points")
        if self.fee_waived is not None and type(self.fee_waived) is not bool:
            raise TypeError("fee_waived is True, False or None")
        for name, asset in (("sell_price", self.sell.asset), ("buy_price", self.buy.asset)):
            value = getattr(self, name)
            _is(name, value, Price, optional=True)
            if value is not None and value.base != asset:
                raise ValueError(f"{name} prices the wrong asset")
        _text("quote_id", self.quote_id, optional=True)


_VALUE_TYPES = _VALUE_TYPES + (Quote,)


# --- holdings ------------------------------------------------------------------

class UniverseStatus(enum.Enum):
    """Can we buy it? The ways out of the buy universe are kept distinct (1.8),
    because each means something different for valuation."""

    TRADEABLE = "tradeable"
    NOT_TRADEABLE = "not_tradeable"                      # this snapshot: quote, size, age or impact
    DIVERGENCE_VETO = "divergence_veto"                  # this snapshot: mark and corroborator disagree, open session
    UNCORROBORATED = "uncorroborated"                    # this snapshot: no corroborating price or volume, so undetermined
    NO_MARK = "no_mark"                                  # this snapshot: a feed is pinned, its reading is stale or unread
    BELOW_CORROBORATOR_LINE = "below_corroborator_line"  # still marked by Chainlink
    UNMARKABLE = "unmarkable"                            # no feed: no independent mark
    LISTED_NOT_ACTIVE = "listed_not_active"              # identity passes; the registry's status is not ACTIVE
    IDENTITY_IN_DOUBT = "identity_in_doubt"              # no longer listed, or the beacon disagrees
    NOT_A_STOCK = "not_a_stock"                          # cash leg, gas


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Holding:
    """Something the wallet holds, kept in the book whatever its universe status.

    The balance is read over RPC (F0.7b.8), so it is an Observation and can be
    unreachable. The value is either derived from a mark or absent with a
    reason. It is never silently zero, and never the venue's own quote: a
    holding with no feed has no independent mark (0.4 decision, F0.4.4).
    """

    asset: AssetId
    balance: Observation
    universe_status: UniverseStatus
    universe_reason: str | None
    mark: Observation | None
    value: Fixed | None
    value_reason: str | None

    def __post_init__(self):
        _is("asset", self.asset, AssetId)
        _is("balance", self.balance, Observation)
        _is("universe_status", self.universe_status, UniverseStatus)
        _is("mark", self.mark, Observation, optional=True)
        _is("value", self.value, Fixed, optional=True)
        if self.balance.ok and (not isinstance(self.balance.value, Amount)
                                or self.balance.value.asset != self.asset):
            raise ValueError("a balance is an amount of the held asset")
        if self.universe_status is not UniverseStatus.TRADEABLE:
            _text("universe_reason (say why it is out)", self.universe_reason)
        if self.mark is not None and self.mark.ok and (
                not isinstance(self.mark.value, Price) or self.mark.value.base != self.asset):
            raise ValueError("a mark is a price of the held asset")
        if self.value is None:
            _text("value_reason (an unvalued holding says why)", self.value_reason)
            return
        if self.value.unit != USD:
            raise ValueError("value is in USD")
        if self.mark is None or not self.mark.ok:
            raise ValueError("a value needs a mark that was read")
        if not self.balance.ok:
            raise ValueError("a value needs a balance that was read")


# --- the snapshot --------------------------------------------------------------

@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class PinnedInput:
    """A third-party input pinned by content hash: the registry, the feed directory.

    Neither source carries a version, so the sha256 of the raw bytes is the
    version (0.8 decision, F0.8.1).
    """

    name: str
    locator: str
    sha256: str
    byte_count: int
    fetch_time: Instant

    def __post_init__(self):
        _text("name", self.name)
        _text("locator", self.locator)
        if "://" in self.locator:
            raise ValueError("a locator is a host and path, never a URL")
        if not isinstance(self.sha256, str) or not _SHA256.match(self.sha256):
            raise ValueError("sha256 is 64 lowercase hex characters")
        _int("byte_count", self.byte_count, minimum=0)
        _is("fetch_time", self.fetch_time, Instant)


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class SnapshotEntry:
    """One asset as the snapshot sees it: what was read, and what it adds up to."""

    asset: Asset
    feed_reading: Observation | None
    series: tuple[Series, ...]
    corroboration: Observation | None
    corroborator_volume: Observation | None
    divergence: Fixed | None
    quote: Observation | None
    universe_status: UniverseStatus
    universe_reason: str | None

    def __post_init__(self):
        _is("asset", self.asset, Asset)
        asset = self.asset.id
        for name in ("feed_reading", "corroboration", "corroborator_volume", "quote"):
            _is(name, getattr(self, name), Observation, optional=True)
        _tuple_of(self, "series", Series)
        for history in self.series:
            if history.asset != asset:
                raise ValueError("a series belongs to its entry's asset")
        for name in ("feed_reading", "corroboration"):
            seen = getattr(self, name)
            if seen is not None and seen.ok and (
                    not isinstance(seen.value, Price) or seen.value.base != asset):
                raise ValueError(f"{name} is a price of the entry's asset")
        if self.quote is not None and self.quote.ok and (
                not isinstance(self.quote.value, Quote) or self.quote.value.buy.asset != asset):
            raise ValueError("the quote buys the entry's asset")
        volume = self.corroborator_volume
        if volume is not None and volume.ok and (
                not isinstance(volume.value, Fixed) or volume.value.unit != USD):
            raise ValueError("corroborator volume is USD: the $1M tier reads it (1.4)")
        _is("divergence", self.divergence, Fixed, optional=True)
        if self.divergence is not None and self.divergence.unit != BPS:
            raise ValueError("divergence is in basis points")
        _is("universe_status", self.universe_status, UniverseStatus)
        if self.universe_status is not UniverseStatus.TRADEABLE:
            _text("universe_reason (say why it is out)", self.universe_reason)


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Snapshot:
    """One frozen snapshot per cycle, containing history up to a pinned block.

    Entries, holdings and inputs are put in canonical order on construction, so
    identical inputs hash identically whatever order the builder produced them
    in. `snapshot_id` is the sha256 of the canonical bytes. The *policy* checks —
    mixed blocks, a stale newest point, anything after the pinned block — are
    1.6's and 1.11's. This type holds what they judge.
    """

    pinned_block: BlockRef
    inputs: tuple[PinnedInput, ...]
    config_version: str
    entries: tuple[SnapshotEntry, ...]
    holdings: tuple[Holding, ...]

    def __post_init__(self):
        _is("pinned_block", self.pinned_block, BlockRef)
        if self.pinned_block.timestamp is None:
            raise ValueError("the pinned block's own time is what 'after' is judged against")
        _text("config_version", self.config_version)
        _tuple_of(self, "inputs", PinnedInput)
        _tuple_of(self, "entries", SnapshotEntry)
        _tuple_of(self, "holdings", Holding)
        object.__setattr__(self, "inputs", tuple(sorted(self.inputs, key=lambda i: i.name)))
        object.__setattr__(self, "entries", tuple(sorted(self.entries, key=lambda e: e.asset.id)))
        object.__setattr__(self, "holdings", tuple(sorted(self.holdings, key=lambda h: h.asset)))
        for label, keys in (("input", [i.name for i in self.inputs]),
                            ("entry", [e.asset.id for e in self.entries]),
                            ("holding", [h.asset for h in self.holdings])):
            if len(keys) != len(set(keys)):
                raise ValueError(f"duplicate {label}")

    @property
    def snapshot_id(self) -> str:
        return content_id(self)


# --- orders and the evidence that one executed ---------------------------------

class OrderState(enum.Enum):
    """The durable states of PLAN §4, each written before the action it describes."""

    PREPARED = "prepared"
    SUBMITTED = "submitted"
    UNKNOWN = "unknown"      # timeout, dropped connection, or 409 in flight
    CONFIRMED = "confirmed"
    FAILED = "failed"


class ExecutionMode(enum.Enum):
    PAPER = "paper"  # stock legs: priced from live quotes, never submitted (PLAN §13)
    LIVE = "live"    # the ungated leg: ETH→USDG on 4663 (0.11 decision)


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class TokenTransfer:
    """An ERC-20 `Transfer` log. With the UserOperation event, this is what
    reconciliation reads (F0.10.3)."""

    token: AssetId
    sender: ChainAddress
    recipient: ChainAddress
    amount: Amount
    log_index: int

    def __post_init__(self):
        _is("token", self.token, AssetId)
        _is("sender", self.sender, ChainAddress)
        _is("recipient", self.recipient, ChainAddress)
        _is("amount", self.amount, Amount)
        _int("log_index", self.log_index, minimum=0)
        if self.amount.asset != self.token:
            raise ValueError("a transfer moves its own token")
        if self.amount.raw < 0:
            raise ValueError("a transfer amount is non-negative")
        if not (self.sender.chain_id == self.recipient.chain_id == self.token.chain_id):
            raise ValueError("a transfer happens on one chain")


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class TransactionRef:
    """The outer transaction a swap arrived in.

    On 4663 it is an EIP-7702 transaction (type 4) that a **bundler** sends to
    the ERC-4337 EntryPoint (F0.10.3). `submitted_by` is that bundler. It is
    recorded, and never used to decide whose swap this was. `outer_status` says
    the bundle mined, not that our swap succeeded. There is deliberately no
    nonce field: the wallet's nonce also moves for 7702 authorizations, and does
    not count swaps.
    """

    tx_hash: str
    block: BlockRef
    tx_type: int
    submitted_by: ChainAddress
    outer_status: int | None

    def __post_init__(self):
        if not isinstance(self.tx_hash, str) or not _HASH32.match(self.tx_hash):
            raise ValueError("tx_hash is 0x + 64 lowercase hex")
        _is("block", self.block, BlockRef)
        _int("tx_type", self.tx_type, minimum=0)
        _is("submitted_by", self.submitted_by, ChainAddress)
        if self.submitted_by.chain_id != self.block.chain_id:
            raise ValueError("the submitter is on the transaction's chain")
        if self.outer_status not in (0, 1, None) or type(self.outer_status) is bool:
            raise ValueError("outer_status is 0, 1 or None")


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class UserOperationRef:
    """The ERC-4337 `UserOperationEvent` for a swap: whose it was, and whether it worked.

    `sender` is the attribution field. `success` is the swap's own outcome;
    a reverted swap can sit inside a transaction whose outer status is 1.
    `actual_gas_cost` was 0 on the one swap measured, because the bundler
    sponsored it (F0.10.3). The nonce here is the EntryPoint's per-key sequence,
    not the wallet's.
    """

    entry_point: ChainAddress
    user_op_hash: str
    sender: ChainAddress
    paymaster: ChainAddress | None
    nonce_key: str
    nonce_seq: int = field(metadata=AS_STR)
    success: Check
    actual_gas_cost: Amount

    def __post_init__(self):
        _is("entry_point", self.entry_point, ChainAddress)
        if not isinstance(self.user_op_hash, str) or not _HASH32.match(self.user_op_hash):
            raise ValueError("user_op_hash is 0x + 64 lowercase hex")
        _is("sender", self.sender, ChainAddress)
        _is("paymaster", self.paymaster, ChainAddress, optional=True)
        if not isinstance(self.nonce_key, str) or not re.match(r"^0x[0-9a-f]+$", self.nonce_key):
            raise ValueError("nonce_key is lowercase hex")
        _int("nonce_seq", self.nonce_seq, minimum=0)
        _is("success", self.success, Check)
        _is("actual_gas_cost", self.actual_gas_cost, Amount)
        if not self.actual_gas_cost.asset.is_native:
            raise ValueError("gas is paid in the native token")


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Execution:
    """Chain evidence that an order executed. Reconciliation reads the
    UserOperation and the transfers, never `submitted_by` or a nonce."""

    transaction: TransactionRef
    user_operation: UserOperationRef | None
    transfers: tuple[TokenTransfer, ...]

    def __post_init__(self):
        _is("transaction", self.transaction, TransactionRef)
        _is("user_operation", self.user_operation, UserOperationRef, optional=True)
        _tuple_of(self, "transfers", TokenTransfer)
        chain = self.transaction.block.chain_id
        if self.user_operation is not None and self.user_operation.sender.chain_id != chain:
            raise ValueError("the operation is on the transaction's chain")
        if any(t.token.chain_id != chain for t in self.transfers):
            raise ValueError("every transfer is on the transaction's chain")


@canonical
@dataclass(frozen=True, slots=True, kw_only=True)
class Order:
    """One order through PLAN §4's state machine.

    It does not assume a swap is a transaction sent from our wallet. A
    confirmed live order is attributed by the UserOperation's `sender` and the
    bought asset's `Transfer` into `wallet` — the evidence F0.10.3 showed is
    actually there. The HTTP response is never the evidence (PLAN §2
    invariant 9).
    """

    order_id: str
    idempotency_key: str
    mode: ExecutionMode
    wallet: ChainAddress
    sell: Amount
    buy_asset: AssetId
    min_buy: Amount
    state: OrderState
    state_reason: str | None = None
    execution: Execution | None = None

    def __post_init__(self):
        _text("order_id", self.order_id)
        _text("idempotency_key", self.idempotency_key)
        _is("mode", self.mode, ExecutionMode)
        _is("wallet", self.wallet, ChainAddress)
        _is("sell", self.sell, Amount)
        _is("buy_asset", self.buy_asset, AssetId)
        _is("min_buy", self.min_buy, Amount)
        _is("state", self.state, OrderState)
        _is("execution", self.execution, Execution, optional=True)
        if self.sell.raw <= 0:
            raise ValueError("an order sells a positive amount")
        if self.sell.asset == self.buy_asset or self.min_buy.asset != self.buy_asset:
            raise ValueError("an order sells one asset for another, min_buy in the bought one")
        if self.wallet.chain_id != self.sell.asset.chain_id:
            raise ValueError("the wallet is on the order's chain")
        if self.state in (OrderState.UNKNOWN, OrderState.FAILED):
            _text("state_reason", self.state_reason)
        if self.execution is not None and self.state in (OrderState.PREPARED,
                                                         OrderState.SUBMITTED):
            raise ValueError("no execution evidence exists before an outcome")
        if self.mode is ExecutionMode.PAPER:
            if self.execution is not None:
                raise ValueError("a paper order has no chain evidence")
            return
        if self.state is OrderState.CONFIRMED:
            if self.execution is None:
                raise ValueError("a confirmed live order carries its chain evidence")
            op = self.execution.user_operation
            if op is not None:
                if op.sender != self.wallet:
                    raise ValueError("the operation was not sent for this wallet")
                if not op.success.passes:
                    raise ValueError("a confirmed order's operation succeeded")
            if not any(t.token == self.buy_asset and t.recipient == self.wallet
                       for t in self.execution.transfers):
                raise ValueError("confirmed means the bought asset reached the wallet")
