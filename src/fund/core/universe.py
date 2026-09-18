"""The universe: which assets the fund may ever touch. Unit 1.2.

Robinhood Chain is permissionless, and 0.8 measured two live GME counterfeits
beside the genuine token. This module decides what is real, and does so on the
four decisions taken at the close of 0.8 (tracker/LESSONS.md, 2026-09-18):

- **Identity is registry membership on `(chain_id, address)`**, and nothing
  else. It is necessary and sufficient against every counterfeit tested
  (findings F0.8.5).
- **The registry is pinned by the sha256 of its raw bytes.** It carries no
  version, `ETag` or `Last-Modified` (F0.8.1). The bytes live in
  `config/registry/`, named by their hash. The loader refuses bytes that do not
  hash to the pin, and nothing looks the registry up live.
- **The beacon is a cross-check that fails loudly, not a filter.** When
  registry and beacon disagree, one of them is compromised, so the cycle stops
  (`BeaconDisagreement`).
- **Feed presence is markability, not identity.** It is a separate rule,
  evaluated separately, with zero identity weight (F0.8.3). CRM is genuine and
  unmarkable (F0.8.2).
- `uiMultiplier()` and the name marker are not read here at all.

**Where the I/O seam falls.** `core/` makes no network calls (CODEBASE §1). Two
reads this unit depends on are network I/O, and belong to adapters:
- fetching the registry and the feed directory for a refresh;
- reading each token's EIP-1967 beacon slot, which is 1.3's chain adapter.

Everything after the bytes or the reads arrive is here, as functions that take
them as arguments: hashing, parsing, diffing, the rules, and the cross-check.
This module's only I/O is reading and writing files under `config/registry/`,
which CODEBASE §2 assigns to `core/universe.py` as "allowlist loading".

Every refusal names the rule that refused (`RULE_*`), so a test can prove a
rejection fired at the rule it meant to exercise and not somewhere else.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from types import MappingProxyType
from typing import Any, Iterable, Mapping

from .types import (
    MULTIPLE, PERCENT, SECONDS, AssetId, ChainAddress, Deployment, FeedRef, Fixed,
    Instant, PinnedInput, RegistryRecord, TradingCapability,
)

# --- rules and refusals --------------------------------------------------------

RULE_PIN = "pin"                  # the bytes hash to the pinned version
RULE_IDENTITY = "identity"        # registry membership on (chain_id, address)
RULE_STANDING = "standing"        # the registry's status for it is ACTIVE
RULE_MARKABILITY = "markability"  # a pinned Chainlink feed, matched by address
RULE_BEACON = "beacon"            # the beacon slot resolves to the issuer's beacon
RULE_FEED_MAP = "feed-map"        # the reviewed feed map matches the pinned inputs

ACTIVE = "ASSET_STATUS_ACTIVE"

REGISTRY = "rhj_assets"
DIRECTORY = "chainlink_directory"
INPUT_NAMES = (REGISTRY, DIRECTORY)


class UniverseError(Exception):
    """A refusal. `rule` says which rule refused; the message says why."""

    def __init__(self, rule: str, message: str):
        super().__init__(f"[{rule}] {message}")
        self.rule = rule


class PinMismatch(UniverseError):
    def __init__(self, message: str):
        super().__init__(RULE_PIN, message)


class Refused(UniverseError):
    """An asset refused by a named rule."""

    def __init__(self, rule: str, asset: AssetId, reason: str):
        super().__init__(rule, f"{asset.chain_id}:{asset.address} — {reason}")
        self.asset = asset
        self.reason = reason


class FeedMapStale(UniverseError):
    def __init__(self, message: str):
        super().__init__(RULE_FEED_MAP, message)


# --- pins ----------------------------------------------------------------------

_SHA = re.compile(r"^[0-9a-f]{64}$")


def sha256_hex(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def filename_for(name: str, sha256: str) -> str:
    """Raw bytes are stored under their own hash: `<name>.<sha256>.json`."""
    if name not in INPUT_NAMES:
        raise ValueError(f"unknown pinned input {name!r}")
    if not _SHA.match(sha256):
        raise ValueError("sha256 is 64 lowercase hex")
    return f"{name}.{sha256}.json"


def verify(raw: bytes, pin: PinnedInput) -> None:
    """Refuse bytes that are not exactly the pinned version. Nothing else runs first."""
    actual = sha256_hex(raw)
    if actual != pin.sha256:
        raise PinMismatch(f"{pin.name}: bytes hash to {actual}, pinned {pin.sha256}")
    if len(raw) != pin.byte_count:
        raise PinMismatch(f"{pin.name}: {len(raw)} bytes, pinned {pin.byte_count}")


def _pin_from_json(name: str, entry: Mapping[str, Any]) -> PinnedInput:
    return PinnedInput(name=name, locator=entry["locator"], sha256=entry["sha256"],
                       byte_count=entry["byte_count"],
                       fetch_time=Instant(entry["fetch_time_ms"]))


def _pin_to_json(pin: PinnedInput) -> dict[str, Any]:
    return {"locator": pin.locator, "sha256": pin.sha256, "byte_count": pin.byte_count,
            "fetch_time_ms": pin.fetch_time.epoch_ms,
            "file": filename_for(pin.name, pin.sha256)}


# --- parsing the registry, exactly ---------------------------------------------

def parse_registry(raw: bytes) -> dict[AssetId, RegistryRecord]:
    """The issuer registry as `RegistryRecord`s, keyed by every deployment.

    Conversions are exact:
    - multipliers are 18-decimal strings, parsed with no float;
    - an empty `pendingMultiplier` is None, never zero;
    - `status` and `deployments` are kept as given, without assuming `ACTIVE` or
      a single deployment (F0.8.1).

    An address claimed by two records is a registry integrity failure, and the
    parse refuses it.
    """
    payload = json.loads(raw)
    records: dict[AssetId, RegistryRecord] = {}
    for item in payload["assets"]:
        pending = item.get("pendingMultiplier") or None
        record = RegistryRecord(
            registry_id=item["id"], symbol=item["tokenSymbol"], name=item["tokenName"],
            isin=item["isin"], status=item["status"], decimals=item["tokenDecimals"],
            deployments=tuple(
                Deployment(contract=ChainAddress(d["chainId"], d["contractAddress"]),
                           network_name=d["networkName"])
                for d in item["deployments"]),
            current_multiplier=Fixed.parse(item["currentMultiplier"], MULTIPLE),
            pending_multiplier=None if pending is None else Fixed.parse(pending, MULTIPLE),
            trading_capabilities=tuple(sorted(
                (TradingCapability(session=session, lot=lot, status=status)
                 for session, lots in (item.get("tradingCapabilities") or {}).items()
                 for lot, status in lots.items()),
                key=lambda c: (c.session, c.lot))))
        for deployment in record.deployments:
            key = AssetId(deployment.contract.chain_id, deployment.contract.address)
            if key in records:
                raise ValueError(f"registry lists {key.address} twice")
            records[key] = record
    return records


def parse_directory(raw: bytes, chain_id: int) -> dict[ChainAddress, FeedRef]:
    """Chainlink's feed directory as `FeedRef`s, keyed by proxy address.

    The directory writes `threshold` as a JSON float (0.5). It is converted from
    its shortest text, so the float never reaches a type. The directory carries
    **no token address** — a feed names its asset only by ticker — which is why
    markability runs through the reviewed feed map rather than here.
    """
    feeds: dict[ChainAddress, FeedRef] = {}
    for item in json.loads(raw):
        proxy = ChainAddress(chain_id, item["proxyAddress"])
        feeds[proxy] = FeedRef(
            proxy=proxy, decimals=item["decimals"],
            heartbeat=Fixed(item["heartbeat"], 0, SECONDS),
            deviation_threshold=Fixed.parse(repr(item["threshold"]), PERCENT),
            market_hours=(item.get("docs") or {}).get("marketHours") or None,
            name=item["name"])
    return feeds


# --- the pin file, and refresh as a deliberate act -----------------------------

PINS_FILE = "pins.json"

#: `config/registry/`, found from this file rather than the working directory.
DEFAULT_DIR = Path(__file__).resolve().parents[3] / "config" / "registry"

RULE_REFRESH = "refresh"


class HeldAssetRemoved(UniverseError):
    def __init__(self, assets: Iterable[AssetId]):
        listed = ", ".join(f"{a.chain_id}:{a.address}" for a in assets)
        super().__init__(RULE_REFRESH, "accepting this refresh would drop held assets "
                         f"from the registry: {listed}. The holdings stay in the book "
                         "either way; accept only with acknowledge_removed_held=True.")
        self.assets = tuple(assets)


def read_pins(registry_dir: Path = DEFAULT_DIR) -> dict[str, Any]:
    return json.loads((registry_dir / PINS_FILE).read_bytes())


def read_pinned(name: str, registry_dir: Path = DEFAULT_DIR) -> tuple[PinnedInput, bytes]:
    """The pinned bytes for one input, verified against the pin before they are returned."""
    entry = read_pins(registry_dir)["inputs"][name]
    pin = _pin_from_json(name, entry)
    if entry["file"] != filename_for(name, pin.sha256):
        raise PinMismatch(f"{name}: pin names file {entry['file']}, "
                          f"expected {filename_for(name, pin.sha256)}")
    raw = (registry_dir / entry["file"]).read_bytes()
    verify(raw, pin)
    return pin, raw


def _diff(old: Mapping, new: Mapping) -> tuple[tuple, tuple, tuple]:
    added = tuple(sorted(k for k in new if k not in old))
    removed = tuple(sorted(k for k in old if k not in new))
    changed = []
    for key in sorted(k for k in new if k in old):
        before, after = old[key], new[key]
        for field_name in type(before).__dataclass_fields__:
            a, b = getattr(before, field_name), getattr(after, field_name)
            if a != b:
                changed.append((key, field_name, repr(a), repr(b)))
    return added, removed, tuple(changed)


@dataclass(frozen=True)
class RefreshPlan:
    """A candidate new version of one pinned input, with its diff against the current pin.

    Producing a plan changes nothing. `store` writes the bytes, and `accept` bumps
    the pin; both are explicit calls, and the loader never makes either.
    """

    pin: PinnedInput
    raw: bytes
    added: tuple
    removed: tuple
    changed: tuple

    @property
    def filename(self) -> str:
        return filename_for(self.pin.name, self.pin.sha256)

    @property
    def unchanged(self) -> bool:
        return not (self.added or self.removed or self.changed)


def plan_refresh(name: str, locator: str, raw: bytes, fetch_time: Instant,
                 current: bytes | None, chain_id: int = 4663) -> RefreshPlan:
    """Hash, parse and diff freshly fetched bytes. The fetch itself is an adapter's."""
    if name not in INPUT_NAMES:
        raise ValueError(f"unknown pinned input {name!r}")
    parse = (parse_registry if name == REGISTRY
             else lambda b: parse_directory(b, chain_id))
    fresh = parse(raw)  # a malformed fetch is refused here, before anything is stored
    old = parse(current) if current is not None else {}
    added, removed, changed = _diff(old, fresh) if current is not None else ((), (), ())
    pin = PinnedInput(name=name, locator=locator, sha256=sha256_hex(raw),
                      byte_count=len(raw), fetch_time=fetch_time)
    return RefreshPlan(pin=pin, raw=raw, added=added, removed=removed, changed=changed)


def store(plan: RefreshPlan, registry_dir: Path = DEFAULT_DIR) -> Path:
    """Write the raw bytes under their own hash. It is idempotent, and it never touches the pin."""
    path = registry_dir / plan.filename
    if path.exists():
        if path.read_bytes() != plan.raw:
            raise PinMismatch(f"{path.name} exists with different bytes")
        return path
    path.write_bytes(plan.raw)
    return path


def accept(plan: RefreshPlan, registry_dir: Path = DEFAULT_DIR, *,
           held: Iterable[AssetId] = (), acknowledge_removed_held: bool = False) -> None:
    """Bump the pin to `plan`: the explicit config change a new version requires.

    It refuses to drop a held asset from the registry unless that is
    acknowledged. Even acknowledged, the holding stays in the book, where
    `Universe.held_asset` still describes it. After a new registry or directory
    is accepted, the reviewed feed map no longer matches, and loading refuses
    until the map is re-reviewed.
    """
    stored = registry_dir / plan.filename
    if not stored.exists() or stored.read_bytes() != plan.raw:
        raise PinMismatch(f"{plan.filename} is not stored; call store() first")
    if plan.pin.name == REGISTRY:
        removed = set(plan.removed)
        dropped = [asset for asset in held if asset in removed]
        if dropped and not acknowledge_removed_held:
            raise HeldAssetRemoved(dropped)
    pins = read_pins(registry_dir)
    pins["inputs"][plan.pin.name] = _pin_to_json(plan.pin)
    (registry_dir / PINS_FILE).write_text(json.dumps(pins, indent=2, sort_keys=True) + "\n")


# --- the feed map: the one place a name ever meets an address ------------------

FEED_MAP_FILE = "feed_map.json"


@dataclass(frozen=True)
class FeedProposal:
    asset: AssetId
    feed_proxy: ChainAddress
    feed_name: str
    evidence: str


def propose_feed_map(records: Mapping[AssetId, RegistryRecord], directory_raw: bytes,
                     chain_id: int = 4663) -> tuple[list[FeedProposal], list[dict]]:
    """A *proposal* for a human to review, never called at cycle time.

    Chainlink's directory carries no token address; a feed names its asset only
    by ticker. So the address-keyed feed map has to originate from a name match,
    and this is where that happens, once, under review. It is safe from F0.8.3's
    failure for one reason: it iterates the **registry's** records. The symbol it
    matches is the issuer's, for an address the issuer lists, never a symbol a
    token claims for itself. A counterfeit can never be proposed a feed.

    Only exact `docs.baseAsset` matches are proposed. Every other equity feed —
    `RHDELL`, and SGOV and USAR, which have no base asset (F0.8.1) — is returned
    unresolved rather than guessed at.
    """
    feeds = json.loads(directory_raw)
    # SGOV's and USAR's entries carry no assetClass at all, only us_equities
    # market hours. Filtering on assetClass alone drops them silently, so either
    # signal counts, which gives the 35 F0.4.1 counted.
    equity = [f for f in feeds
              if (f.get("docs") or {}).get("assetClass") == "Equity"
              or str((f.get("docs") or {}).get("marketHours", "")).startswith("us_equities")]
    by_symbol = {r.symbol: key for key, r in records.items() if key.chain_id == chain_id}
    proposals, unresolved = [], []
    for feed in equity:
        base = (feed.get("docs") or {}).get("baseAsset")
        if base in by_symbol:
            proposals.append(FeedProposal(
                asset=by_symbol[base], feed_proxy=ChainAddress(chain_id, feed["proxyAddress"]),
                feed_name=feed["name"], evidence="docs.baseAsset equals the registry's tokenSymbol"))
        else:
            unresolved.append({"feed_name": feed["name"], "proxy": feed["proxyAddress"].lower(),
                               "baseAsset": base,
                               "baseAssetEntityId": (feed.get("docs") or {}).get("baseAssetEntityId")})
    return sorted(proposals, key=lambda p: p.asset), unresolved
