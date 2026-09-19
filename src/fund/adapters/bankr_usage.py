"""/v1/usage, and the one reconciliation it supports (unit 2.5).

What the provider can tell us is narrow (F0.6.4). It attributes spend only per
key, per model and per day window, with no per-request row. Our own per-call
costs come from each reply's usage block (`bankr_llm.cost`), and each is an
estimate that says so. This module checks those estimates the only way the
provider allows: **aggregate against aggregate**, in one window, for one key.

Three rules come from the record:
- **The window is read back.** `days`, `startDate` and `endDate` are taken from
  the response, never from what was asked. The service coerces out-of-range
  values silently, turning `days=91` into 90 and `days=0` into 30 (F0.6.5).
- **Only a settled window is compared.** `/v1/usage` was seen going backwards
  around single calls, reporting 0, then 1, then 0, then 2 requests (F0.9.2).
  So a window is compared only when it closed at least `settle_seconds` after
  the last call in it. **A before-and-after delta around a call is never used.**
- **A difference is a finding, not an error to absorb.** The provider counts
  every call made with the key in the window: other seats sharing a key, and
  probes. Our figure counts only the calls we recorded. The difference is
  reported with that stated.

One attempt, like the model client. A refusal is kept and named.
"""

from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, Callable, Iterable, Mapping

from fund.adapters import http as shared_http

GATEWAY = "https://llm.bankr.bot"
USAGE = "/v1/usage"
USER_AGENT = "openfund/2.5 (+one attempt per read)"

#: `(url, headers, timeout_s) -> (status, body)`.
Get = Callable[[str, Mapping[str, str], float], "tuple[int, bytes]"]

LABEL = ("aggregate to aggregate, within one key and one settled window. The provider "
         "counts every call made with this key in the window, including other seats "
         "sharing it and probes, so a difference is a finding to explain, not an error to "
         "absorb. Our per-call figures are estimates; the provider's total is its own.")


def _when(text: str) -> datetime:
    return datetime.fromisoformat(text.replace("Z", "+00:00"))


@dataclass(frozen=True)
class Window:
    start: datetime
    end: datetime
    days: int  # as the provider states it
    requested_days: int | None
    total_cost: Decimal
    total_requests: int
    by_model: tuple[Mapping[str, Any], ...]

    @property
    def coerced(self) -> bool:
        """The provider answered for a different span than was asked (F0.6.5)."""
        return self.requested_days is not None and self.requested_days != self.days


@dataclass(frozen=True)
class Unread:
    status: int | None
    detail: str


@dataclass(frozen=True)
class Call:
    at: datetime
    usd: Decimal | None  # None: a call whose cost nothing here can know


def parse(body: Mapping[str, Any], requested_days: int | None = None) -> Window:
    """A usage summary, as the provider states it."""
    totals = body["totals"]
    return Window(start=_when(body["startDate"]), end=_when(body["endDate"]),
                  days=int(body["days"]), requested_days=requested_days,
                  total_cost=Decimal(str(totals["totalCost"])),
                  total_requests=int(totals["totalRequests"]),
                  by_model=tuple(body.get("byModel") or ()))


def urllib_get(url: str, headers: Mapping[str, str], timeout_s: float) -> tuple[int, bytes]:
    request = urllib.request.Request(url, method="GET", headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def fetch(key: str, *, days: int, base_url: str = GATEWAY, get: Get | None = None,
          timeout_s: float = 20.0) -> Window | Unread:
    """One read of one key's usage over `days`. Never raises for the network."""
    get = urllib_get if get is None else get
    headers = {"X-API-Key": key, "User-Agent": USER_AGENT}
    try:
        status, raw = shared_http.with_deadline(
            lambda: get(f"{base_url}{USAGE}?days={days}", headers, timeout_s), timeout_s)
    except shared_http._Hang:
        return Unread(None, "timeout")
    except Exception as error:
        return Unread(None, f"transport: {type(error).__name__}: {error}".replace(key, "[KEY]"))
    text = raw.decode("utf-8", errors="replace").replace(key, "[KEY]")
    if status != 200:
        return Unread(status, text[:600])
    try:
        return parse(json.loads(text), requested_days=days)
    except (ValueError, KeyError, TypeError) as error:
        return Unread(status, f"unreadable usage summary: {error}")


def calls_from_cycle(cycle: Mapping[str, Any]) -> list[Call]:
    """Every analyst call a runner cycle recorded, with when it was sent and its estimate."""
    return [Call(at=_when(attempt["at"]),
                 usd=None if attempt["cost"]["usd"] is None else Decimal(attempt["cost"]["usd"]))
            for slot in cycle["seats"].values() for attempt in slot.get("attempts") or ()]


def reconcile(calls: Iterable[Call], window: Window, *, settle_seconds: float) -> dict[str, Any]:
    """Our recorded calls in a window against the provider's total for it. Compared
    only once settled; a difference is reported, never absorbed."""
    calls = list(calls)
    inside = [c for c in calls if window.start <= c.at <= window.end]
    summary: dict[str, Any] = {
        "window": {"start": window.start.isoformat(), "end": window.end.isoformat(),
                   "days": window.days, "coerced": window.coerced},
        "our_calls": len(inside), "calls_outside_window": len(calls) - len(inside),
        "provider_requests": window.total_requests, "label": LABEL,
    }
    if not inside:
        return {**summary, "status": "nothing to compare"}
    latest = max(c.at for c in inside)
    settled_for = (window.end - latest).total_seconds()
    if settled_for < settle_seconds:
        return {**summary, "status": "unsettled", "settled_for_seconds": settled_for}
    known = [c.usd for c in inside if c.usd is not None]
    ours = sum(known, Decimal(0))
    return {**summary, "status": "compared", "settled_for_seconds": settled_for,
            "ours_usd": f"{ours.normalize():f}", "our_calls_of_unknown_cost": len(inside) - len(known),
            "provider_usd": f"{window.total_cost.normalize():f}",
            "difference_usd": f"{(window.total_cost - ours).normalize():f}"}
