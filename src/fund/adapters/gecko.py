"""GeckoTerminal: the corroborating USD price, and the 24h volume that tiers it. Unit 1.4.

Chainlink marks the book (PLAN §11); this is the second opinion the divergence
check compares it with. It returns Observations, never bare numbers, and
imports no other adapter: its transport is `adapters/http.py`.

What the record requires, and where each requirement is met:

- **Independent of the venue.** GeckoTerminal prices all 32 addressable stock
  tokens off real AMM pools (findings F0.4.2-F0.4.3). The fund's execution is
  Bankr RFQ, so this is a cross-source check. The Bankr quote is never the
  corroborator: its price is the venue's own (F0.3.5), and the venue applies
  the multiplier itself, which would make the comparison circular (F0.4.4).
- **Matched by address, never by symbol.** Each entry's `attributes.address`
  is compared with the pinned `(chain_id, address)`. A counterfeit chooses its
  own ticker (F0.8.3), so a symbol never selects an entry.
- **The volume the tier was set on.** The $1M line was decided on F0.4.5's
  numbers: token-level `volume_usd.h24` from the batch tokens endpoint, as
  `probes/feed.py` read it. This reads the same field from the same endpoint.
  That endpoint lists only one of a token's pools in `top_pools`, so the pool
  count here is a floor.
- **Exact.** Prices and volumes arrive as decimal strings and are parsed with no
  float. A zero or negative price is refused, since it cannot be compared with.
- **Absent is not agreement.** A token missing from a 200 is ABSENT, a field
  that is null is ABSENT, a failed request is UNREACHABLE, and a body that
  cannot be read is REFUSED. None of them carries a value, so none can read as
  a divergence of zero.
- **No source time.** The response gives no time for its price, and it may come
  from an edge cache up to 60 s old (`Cache-Control: max-age=30, s-maxage=60`,
  measured). So `source_time` is None, and the response's Date and cache status
  go in the detail.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Sequence

from fund.adapters import http
from fund.core.types import (
    USD, AssetId, FetchStatus, Fixed, Instant, Observation, Price, Source,
)

SYSTEM = "geckoterminal"
ENDPOINT_NAME = "GECKOTERMINAL"
INDEPENDENT_OF_VENUE = True  # pool prices, not the venue's RFQ (F0.4.2-F0.4.3)

GECKO_CONFIG = Path(__file__).resolve().parents[3] / "config" / "gecko.json"


@dataclass(frozen=True)
class Corroboration:
    """What GeckoTerminal said about one asset: a USD price and a 24h USD volume,
    each an Observation that may be ABSENT, REFUSED or UNREACHABLE."""

    asset: AssetId
    price: Observation
    volume_24h: Observation


@dataclass(frozen=True)
class Batch:
    """One request and what came of it: the reply, or the transport's refusal."""

    assets: tuple[AssetId, ...]
    fetch_time: Instant
    reply: http.Reply | None
    failure: str | None


def batch_path(network: str, assets: Sequence[AssetId]) -> str:
    return f"/networks/{network}/tokens/multi/" + ",".join(a.address for a in assets)


def _source(network: str, asset: AssetId) -> Source:
    return Source(SYSTEM, f"networks/{network}/tokens/{asset.address}")


def _provenance(reply: http.Reply) -> str:
    cache = reply.headers.get("cf-cache-status", "no cache status")
    age = reply.headers.get("age")
    return (f"response Date {reply.headers.get('date', 'absent')}, edge cache {cache}"
            + (f", age {age}s" if age else ""))


def parse(batch: Batch, network: str) -> dict[AssetId, Corroboration]:
    """Every requested asset gets a Corroboration, whatever came back."""
    def every(status: FetchStatus, detail: str) -> dict[AssetId, Corroboration]:
        def one(asset):
            return Observation(value=None, source=_source(network, asset), source_time=None,
                               fetch_time=batch.fetch_time, block=None, status=status, detail=detail)
        return {a: Corroboration(a, one(a), one(a)) for a in batch.assets}

    if batch.reply is None:
        return every(FetchStatus.UNREACHABLE, batch.failure or "no reply")
    try:
        data = json.loads(batch.reply.body)["data"]
        if not isinstance(data, list):
            raise ValueError("`data` is not a list")
    except (ValueError, KeyError, TypeError) as error:
        return every(FetchStatus.REFUSED, f"a 200 whose body is not the batch shape: {error}")

    provenance = _provenance(batch.reply)
    entries: dict[str, list[dict]] = {}
    for entry in data:
        attributes = (entry or {}).get("attributes") or {}
        address = str(attributes.get("address", "")).lower()
        if str(entry.get("id", "")).lower() == f"{network}_{address}":
            entries.setdefault(address, []).append(entry)

    out = {}
    for asset in batch.assets:
        source = _source(network, asset)

        def observe(value=None, status=FetchStatus.OK, detail=provenance):
            return Observation(value=value, source=source, source_time=None,
                               fetch_time=batch.fetch_time, block=None, status=status,
                               detail=detail)

        found = entries.get(asset.address, [])
        if len(found) != 1:
            why = ("GeckoTerminal answered and did not list this address" if not found else
                   f"{len(found)} entries for one address: which one prices it is unknowable")
            status = FetchStatus.ABSENT if not found else FetchStatus.REFUSED
            out[asset] = Corroboration(asset, observe(status=status, detail=f"{why}; {provenance}"),
                                       observe(status=status, detail=f"{why}; {provenance}"))
            continue
        attributes = found[0]["attributes"]
        pools = len(((found[0].get("relationships") or {}).get("top_pools") or {}).get("data") or [])
        where = (f"token-level, over the pools GeckoTerminal indexes; the batch lists {pools} of "
                 f"them, a floor; {provenance}")
        out[asset] = Corroboration(
            asset,
            _read(attributes.get("price_usd"), lambda t: Price.parse(t, asset, USD), "price_usd",
                  observe, where, positive=True),
            _read((attributes.get("volume_usd") or {}).get("h24"), lambda t: Fixed.parse(t, USD),
                  "volume_usd.h24", observe, where, positive=False))
    return out


def _read(text, convert: Callable[[str], object], field_name: str, observe: Callable,
          where: str, *, positive: bool) -> Observation:
    if text is None:
        return observe(status=FetchStatus.ABSENT, detail=f"{field_name} is null; {where}")
    try:
        value = convert(str(text))
    except (ValueError, TypeError) as error:
        return observe(status=FetchStatus.REFUSED, detail=f"{field_name} {text!r}: {error}")
    if value.raw < 0 or (positive and value.raw == 0):
        return observe(status=FetchStatus.REFUSED, detail=f"{field_name} {text!r} is not a usable "
                                                          f"{'price' if positive else 'volume'}")
    return observe(value=value, detail=f"{field_name}; {where}")


class Gecko:
    """Batch token reads for one network, over the shared client."""

    def __init__(self, client: http.HttpClient, *, network: str, batch_size: int,
                 clock: Callable[[], Instant]):
        self.client, self.network, self.batch_size, self.clock = client, network, batch_size, clock

    def fetch(self, assets: Sequence[AssetId]) -> list[Batch]:
        batches = []
        for start in range(0, len(assets), self.batch_size):
            chunk = tuple(assets[start:start + self.batch_size])
            try:
                reply = self.client.send(path=batch_path(self.network, chunk))
                batches.append(Batch(chunk, self.clock(), reply, None))
            except http.Unavailable as error:
                batches.append(Batch(chunk, self.clock(), None, str(error)))
        return batches

    def corroborate(self, assets: Sequence[AssetId]) -> dict[AssetId, Corroboration]:
        out: dict[AssetId, Corroboration] = {}
        for batch in self.fetch(assets):
            out.update(parse(batch, self.network))
        return out


@dataclass(frozen=True)
class Settings:
    base_url: str
    network: str
    batch_size: int
    timeout_s: float
    attempts: int
    backoff_s: float
    min_interval_s: float
    user_agent: str

    @classmethod
    def load(cls, path: Path = GECKO_CONFIG) -> Settings:
        c = json.loads(path.read_text())
        return cls(base_url=c["base_url"], network=c["network"], batch_size=c["batch_size"],
                   timeout_s=c["request_timeout_seconds"], attempts=c["attempts"],
                   backoff_s=c["backoff_seconds"], min_interval_s=c["min_request_interval_ms"] / 1000,
                   user_agent=c["user_agent"])

    def gecko(self, transport: http.Transport | None = None,
              clock: Callable[[], Instant] | None = None) -> Gecko:
        client = http.HttpClient([http.Endpoint(ENDPOINT_NAME, self.base_url)],
                                 timeout_s=self.timeout_s, attempts=self.attempts,
                                 backoff_s=self.backoff_s, min_interval_s=self.min_interval_s,
                                 transport=transport or http.urllib_transport(self.user_agent))
        return Gecko(client, network=self.network, batch_size=self.batch_size,
                     clock=clock or (lambda: Instant(time.time_ns() // 1_000_000)))
