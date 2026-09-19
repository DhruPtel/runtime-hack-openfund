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
    MULTIPLE, PERCENT, SECONDS, Asset, AssetId, AssetKind, ChainAddress, Check, Deployment,
    FeedRef, Fixed, Instant, Observation, PinnedInput, RegistryRecord, TradingCapability,
    UniverseStatus,
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
    acknowledged. Even acknowledged, the holding stays in the book: the asset
    is written to `pins.json`'s `carried` list with its last registry record's
    symbol, name and decimals (1.8). So its balance is still read, and
    `Universe.held_asset` still describes it. A carried asset that a later
    registry lists again leaves the list. After a new registry or directory is
    accepted, the reviewed feed map no longer matches, and loading refuses until
    the map is re-reviewed.
    """
    stored = registry_dir / plan.filename
    if not stored.exists() or stored.read_bytes() != plan.raw:
        raise PinMismatch(f"{plan.filename} is not stored; call store() first")
    pins = read_pins(registry_dir)
    carried = pins.setdefault("carried", {})
    if plan.pin.name == REGISTRY:
        removed = set(plan.removed)
        dropped = [asset for asset in held if asset in removed]
        if dropped and not acknowledge_removed_held:
            raise HeldAssetRemoved(dropped)
        old = parse_registry(read_pinned(REGISTRY, registry_dir)[1]) if dropped else {}
        for asset in dropped:
            record = old[asset]
            carried[_carried_key(asset)] = {
                "chain_id": asset.chain_id, "address": asset.address, "symbol": record.symbol,
                "name": record.name, "decimals": record.decimals,
                "removed_in": plan.pin.sha256,
                "reason": "held when the issuer registry stopped listing it; carried so the "
                          "holding stays in the book (1.8)"}
        now_listed = parse_registry(plan.raw)
        for key in [k for k, v in carried.items()
                    if AssetId(v["chain_id"], v["address"]) in now_listed]:
            del carried[key]
    pins["inputs"][plan.pin.name] = _pin_to_json(plan.pin)
    (registry_dir / PINS_FILE).write_text(json.dumps(pins, indent=2, sort_keys=True) + "\n")


def _carried_key(asset: AssetId) -> str:
    return f"{asset.chain_id}:{asset.address}"


@dataclass(frozen=True)
class CarriedAsset:
    """An asset the issuer registry no longer lists, kept because it was held
    when the registry dropped it. Its balance is still read, and it stays in the
    book with identity in doubt and no mark."""

    asset: AssetId
    symbol: str      # display only, from its last registry record
    name: str
    decimals: int
    removed_in: str  # sha256 of the registry version that dropped it


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


# --- the beacon: an independent root that must fail loudly ---------------------

#: EIP-1967's beacon slot: keccak256("eip1967.proxy.beacon") - 1.
BEACON_SLOT = "0xa3f0ad74e5423aebfd80d3ef4346578335a9a72aeaee59ff6cb3582b35133d50"


def beacon_from_slot(chain_id: int, word: str) -> ChainAddress:
    """The address a 32-byte slot word holds. An unset slot is the zero address."""
    if not isinstance(word, str) or not re.fullmatch(r"0x[0-9a-fA-F]{64}", word):
        raise ValueError("a storage slot word is 0x + 64 hex")
    return ChainAddress(chain_id, "0x" + word[-40:])


class BeaconDisagreement(UniverseError):
    """Registry and beacon disagree: one of them is compromised. The cycle stops.

    This is raised, never returned as a False check, so that no caller can log
    it and carry on. A cross-check that degrades to a warning is not a
    cross-check (0.8 decision).
    """

    def __init__(self, disagreements: Iterable[tuple[AssetId, ChainAddress]], expected: ChainAddress):
        self.disagreements = tuple(disagreements)
        self.expected = expected
        listed = "; ".join(f"{a.address} resolves to {b.address}" for a, b in self.disagreements)
        super().__init__(RULE_BEACON, f"registry-listed assets whose beacon is not the "
                         f"issuer's {expected.address}: {listed}")


# --- the universe ---------------------------------------------------------------

@dataclass(frozen=True)
class Admission:
    """Whether the fund may buy an asset. `rule` names the rule that refused or
    left it undetermined, and is None when every rule passed."""

    decision: Check
    rule: str | None

    @property
    def universe_status(self) -> UniverseStatus | None:
        """The status a refusal books as. None when every rule passed, because
        whether an admitted asset is tradeable this snapshot is 1.6's call."""
        return {
            None: None,
            RULE_IDENTITY: UniverseStatus.IDENTITY_IN_DOUBT,     # no longer listed
            RULE_STANDING: UniverseStatus.LISTED_NOT_ACTIVE,     # listed, identity passes
            RULE_BEACON: UniverseStatus.IDENTITY_IN_DOUBT,       # unread or disagreeing
            RULE_MARKABILITY: UniverseStatus.UNMARKABLE,
        }[self.rule]


@dataclass(frozen=True)
class Universe:
    """The pinned universe. Each rule is a separate method returning a three-valued Check."""

    registry: PinnedInput
    directory: PinnedInput
    records: Mapping[AssetId, RegistryRecord]
    feeds: Mapping[AssetId, FeedRef]
    issuer_beacon: ChainAddress
    cash_leg: AssetId
    cash_decimals: int
    gas_asset: AssetId
    gas_decimals: int
    carried: Mapping[AssetId, CarriedAsset] = MappingProxyType({})

    @property
    def _tag(self) -> str:
        return f"{REGISTRY} {self.registry.sha256[:12]}…"

    # the rules, each on its own --------------------------------------------

    def identity(self, asset: AssetId) -> Check:
        if asset in self.records:
            return Check(True, f"listed in {self._tag}")
        return Check(False, f"not in {self._tag}")

    def standing(self, asset: AssetId) -> Check:
        record = self.records.get(asset)
        if record is None:
            return Check(False, f"not in {self._tag}")
        if record.status == ACTIVE:
            return Check(True, ACTIVE)
        return Check(False, f"registry status {record.status}, not {ACTIVE} — a status "
                            "never observed before (F0.8.1)")

    def markability(self, asset: AssetId) -> Check:
        feed = self.feeds.get(asset)
        if feed is None:
            return Check(False, "no Chainlink feed pinned for this address")
        return Check(True, f"{feed.name} at {feed.proxy.address}")

    def cross_check_beacons(self, reads: Mapping[AssetId, Observation]) -> dict[AssetId, Check]:
        """Compare each listed asset's beacon slot with the issuer's beacon.

        - An address the registry does not list is refused at identity, and never
          compared: the beacon opines, it does not admit.
        - A read that failed is undetermined, and says why. It blocks, but it is
          not a disagreement: an RPC timeout is not evidence of compromise.
        - A slot that was read and differs, zero included, is a disagreement.
          Every disagreement is collected, then raised together.
        """
        checks: dict[AssetId, Check] = {}
        disagreements = []
        for asset, seen in reads.items():
            self.require_listed(asset)
            if not seen.ok:
                checks[asset] = Check.undetermined(
                    f"beacon slot not read: {seen.status.value}: {seen.detail}")
            elif not isinstance(seen.value, ChainAddress):
                raise TypeError("a beacon read is a ChainAddress")
            elif seen.value == self.issuer_beacon:
                checks[asset] = Check(True, f"resolves to the issuer beacon {self.issuer_beacon.address}")
            else:
                disagreements.append((asset, seen.value))
        if disagreements:
            raise BeaconDisagreement(disagreements, self.issuer_beacon)
        return checks

    # assets ---------------------------------------------------------------------

    def require_listed(self, asset: AssetId) -> RegistryRecord:
        record = self.records.get(asset)
        if record is None:
            raise Refused(RULE_IDENTITY, asset, f"not in {self._tag}")
        return record

    def stock(self, asset: AssetId, beacon: Check) -> Asset:
        """A registry-listed stock, with its three verdicts. Unlisted addresses are refused."""
        record = self.require_listed(asset)
        return Asset(id=asset, kind=AssetKind.STOCK, symbol=record.symbol,
                     decimals=record.decimals, identity=self.identity(asset),
                     markability=self.markability(asset), beacon=beacon,
                     registry=record, feed=self.feeds.get(asset))

    def cash(self) -> Asset:
        return Asset(id=self.cash_leg, kind=AssetKind.CASH, symbol="USDG",
                     decimals=self.cash_decimals,
                     identity=Check(True, "pinned cash leg (config/registry/pins.json)"),
                     markability=self.markability(self.cash_leg), beacon=None,
                     feed=self.feeds.get(self.cash_leg))

    def gas(self) -> Asset:
        return Asset(id=self.gas_asset, kind=AssetKind.GAS, symbol="ETH",
                     decimals=self.gas_decimals, identity=Check(True, "the chain's native token"),
                     markability=self.markability(self.gas_asset), beacon=None,
                     feed=self.feeds.get(self.gas_asset))

    def held_asset(self, asset: AssetId, decimals: int,
                   beacon: Check = Check(None, "beacon not read for this description")) -> Asset:
        """Describe something the wallet holds. This never refuses: a holding
        must not vanish.

        - A listed asset keeps its full description, whatever its status: a
          non-ACTIVE asset is refused for buying (`standing`), but it keeps its
          identity, its registry record and its mark.
        - An address the registry no longer lists — or never listed — is
          described with identity False and no feed, so it stays in the book,
          flagged. `decimals` is the chain's, since the registry no longer
          supplies it.
        - A carried asset, dropped by the registry while held, is described
          the same way, under its last record's symbol and decimals, with the
          registry version that dropped it (1.8).
        """
        if asset == self.cash_leg:
            return self.cash()
        if asset == self.gas_asset:
            return self.gas()
        if asset in self.records:
            return self.stock(asset, beacon)
        carried = self.carried.get(asset)
        if carried is not None:
            return Asset(id=asset, kind=AssetKind.STOCK, symbol=carried.symbol,
                         decimals=carried.decimals,
                         identity=Check(False, f"not in {self._tag}: dropped by registry "
                                               f"{carried.removed_in[:12]}… while held, and carried"),
                         markability=Check(False, "no longer listed: no feed may mark it"),
                         beacon=Check(None, "not cross-checked: identity is false"))
        return Asset(id=asset, kind=AssetKind.STOCK, symbol="unlisted", decimals=decimals,
                     identity=self.identity(asset),
                     markability=Check(False, "unlisted: no feed may mark it"),
                     beacon=Check(None, "not cross-checked: identity is false"))

    def admission(self, asset: Asset) -> Admission:
        """May the fund buy it? The rules run in a fixed order; the first failure is named.

        The order: identity, standing, beacon, markability. Cash and gas have no
        registry standing and no beacon. A None anywhere yields an undetermined
        admission rather than a refusal, because null blocks and is not false.
        """
        rules = [(RULE_IDENTITY, asset.identity)]
        if asset.kind is AssetKind.STOCK:
            rules += [(RULE_STANDING, self.standing(asset.id)), (RULE_BEACON, asset.beacon)]
        rules.append((RULE_MARKABILITY, asset.markability))
        for rule, check in rules:
            if not check.passes:
                return Admission(Check(check.value, f"[{rule}] {check.reason}"), rule)
        return Admission(Check(True, "identity, standing, beacon and markability all pass"
                               if asset.kind is AssetKind.STOCK
                               else "pinned identity and markability pass"), None)


# --- loading the pinned universe ------------------------------------------------

def _load_feed_map(registry_dir: Path, registry: PinnedInput, directory: PinnedInput,
                   records: Mapping[AssetId, RegistryRecord],
                   feeds: Mapping[ChainAddress, FeedRef],
                   non_registry: set[AssetId]) -> dict[AssetId, FeedRef]:
    doc = json.loads((registry_dir / FEED_MAP_FILE).read_bytes())
    expected = {REGISTRY: registry.sha256, DIRECTORY: directory.sha256}
    if doc.get("reviewed_against") != expected:
        raise FeedMapStale(f"feed map was reviewed against {doc.get('reviewed_against')}, "
                           f"but the pins are {expected}: re-review it before loading")
    mapped: dict[AssetId, FeedRef] = {}
    used: set[ChainAddress] = set()
    for entry in doc["entries"]:
        asset = AssetId(entry["chain_id"], entry["asset"])
        proxy = ChainAddress(entry["chain_id"], entry["feed_proxy"])
        if asset not in records and asset not in non_registry:
            # A feed may only attach to an asset whose identity is already
            # settled. This is where a counterfeit would try to get in.
            raise UniverseError(RULE_FEED_MAP, f"entry for {asset.address} names neither a "
                                "registry asset nor the pinned cash leg or gas")
        feed = feeds.get(proxy)
        if feed is None:
            raise UniverseError(RULE_FEED_MAP, f"feed {proxy.address} is not in the pinned directory")
        if feed.name != entry["feed_name"]:
            raise UniverseError(RULE_FEED_MAP, f"{proxy.address} is {feed.name!r} in the "
                                f"directory, {entry['feed_name']!r} in the map")
        if asset in mapped or proxy in used:
            raise UniverseError(RULE_FEED_MAP, f"{asset.address} or {proxy.address} mapped twice")
        mapped[asset] = feed
        used.add(proxy)
    return mapped


def load(registry_dir: Path = DEFAULT_DIR) -> Universe:
    """The pinned universe, read from disk. Every input is verified against its
    pin before it is parsed. Nothing is fetched."""
    pins = read_pins(registry_dir)
    registry, registry_raw = read_pinned(REGISTRY, registry_dir)
    directory, directory_raw = read_pinned(DIRECTORY, registry_dir)
    beacon = pins["issuer_beacon"]
    chain_id = beacon["chain_id"]
    records = parse_registry(registry_raw)
    cash = pins["cash_leg"]
    cash_leg = AssetId(cash["chain_id"], cash["address"])
    gas_asset = AssetId.native(pins["gas"]["chain_id"])
    feeds = _load_feed_map(registry_dir, registry, directory, records,
                           parse_directory(directory_raw, chain_id), {cash_leg, gas_asset})
    carried = {}
    for entry in (pins.get("carried") or {}).values():
        asset = AssetId(entry["chain_id"], entry["address"])
        carried[asset] = CarriedAsset(asset=asset, symbol=entry["symbol"], name=entry["name"],
                                      decimals=entry["decimals"], removed_in=entry["removed_in"])
    return Universe(registry=registry, directory=directory,
                    records=MappingProxyType(records), feeds=MappingProxyType(feeds),
                    issuer_beacon=ChainAddress(chain_id, beacon["address"]),
                    cash_leg=cash_leg, cash_decimals=cash["decimals"],
                    gas_asset=gas_asset, gas_decimals=pins["gas"]["decimals"],
                    carried=MappingProxyType(carried))
