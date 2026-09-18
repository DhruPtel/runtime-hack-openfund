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
