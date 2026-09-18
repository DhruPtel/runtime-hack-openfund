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
"""

from __future__ import annotations

import enum
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
    """

    asset: AssetId
    source: Source
    fetch_time: Instant
    status: FetchStatus
    points: tuple[Observation, ...] = ()
    detail: str | None = None

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
