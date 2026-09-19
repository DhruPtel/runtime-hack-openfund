"""One HTTP client for every adapter. Built by unit 1.3 inside the chain adapter,
moved here at 1.4 so GeckoTerminal (1.4) and the Bankr quote (1.5) share one
transport instead of one adapter importing another (DECISION, LESSONS
2026-09-18).

What it does, and what each behaviour answers:

- **A whole-request deadline.** A socket timeout bounds each blocking operation
  only; a server that accepts and then says nothing can outlast it. Every
  request here is abandoned after `timeout_s` of wall-clock time.
- **Failover that advances on a hang.** Endpoints are tried in order. A hang, a
  dead connection, a 429, a 5xx or an unusable body moves on to the next one.
- **Pacing.** Every request waits out `min_interval_s` since the last one sent
  by the same client.
- **A doubling backoff** between passes over the endpoint list.
- **Retry-After, when it says something.** The 4663 RPC's 429 carries none
  (measured 2026-09-18). GeckoTerminal's carries `Retry-After: 0` (measured
  2026-09-19 UTC). That is a header with no information in it: polls a second apart
  stayed 429 for 4.3 s. So:
  - a positive value is waited out, in place of the backoff when it is longer;
  - a value longer than one request's deadline fails the request loudly
    instead of stalling the cycle;
  - 0, absent, already past or unparseable falls back to the doubling backoff.
- **A User-Agent on every request.** Three sources return 403 without one, and
  that 403 looks like an auth failure (probe 0.3).
- **Redaction.** Failures name an endpoint by its name, never its URL, because
  an RPC URL is a credential. Every message is also passed through the
  credential redactor.

Protocol meaning stays with the adapter. A JSON-RPC error inside a 200 is the
chain adapter's to judge, through the `accept` hook.
"""

from __future__ import annotations

import datetime
import email.utils
import threading
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from types import MappingProxyType
from typing import Any, Callable, Mapping, Sequence

from fund import redaction

RULE_TRANSPORT = "transport"

#: `(url, body, timeout_s) -> (status, body)` or `(status, body, headers)`. A
#: body of None is a GET; bytes are POSTed as JSON. Injected so tests can hang,
#: refuse or rate-limit on purpose, with no network.
Transport = Callable[[str, "bytes | None", float], tuple]


def urllib_transport(user_agent: str) -> Transport:
    def send(url: str, body: bytes | None, timeout_s: float) -> tuple[int, bytes, dict[str, str]]:
        headers = {"Accept": "application/json", "User-Agent": user_agent}
        if body is not None:
            headers["Content-Type"] = "application/json"
        request = urllib.request.Request(url, data=body, headers=headers)
        try:
            with urllib.request.urlopen(request, timeout=timeout_s) as response:
                return response.status, response.read(), _lowered(response.headers.items())
        except urllib.error.HTTPError as error:
            return error.code, error.read(), _lowered(error.headers.items())
    return send


def _lowered(items) -> dict[str, str]:
    return {name.lower(): value for name, value in items}


@dataclass(frozen=True)
class Endpoint:
    name: str                          # the credential's name, or the source's: what errors show
    url: str = field(repr=False)       # for the RPC this is the secret itself: never shown


@dataclass(frozen=True)
class Reply:
    """What came back. Header names are lower-case."""

    status: int
    body: bytes
    headers: Mapping[str, str]

    @classmethod
    def of(cls, result: tuple) -> Reply:
        status, body, *rest = result
        return cls(status, body, MappingProxyType(_lowered((rest[0] if rest else {}).items())))


class Unavailable(Exception):
    """Every attempt on every endpoint failed. `failures` names each one by
    endpoint name, never by URL."""

    rule = RULE_TRANSPORT

    def __init__(self, failures: Sequence[tuple[str, str]]):
        self.failures = tuple(failures)
        super().__init__(f"[{RULE_TRANSPORT}] " + "; ".join(f"{n}: {why}" for n, why in failures))


class Retry(Exception):
    """Raised by an `accept` hook: this 200 is a transient failure, such as a
    JSON-RPC 429, so the client moves on exactly as it would for an HTTP 429."""


class _Hang(Exception):
    pass


def with_deadline(fn: Callable[[], Any], deadline_s: float) -> Any:
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


def retry_after(headers: Mapping[str, str], now_s: float) -> tuple[float | None, str]:
    """The server's wait hint in seconds, or None when there is no usable one,
    with the words that describe it in a failure."""
    raw = headers.get("retry-after")
    if raw is None:
        return None, "no Retry-After"
    text = raw.strip()
    if text.isdigit():
        seconds = int(text)
        if seconds == 0:
            return None, "Retry-After 0, which says nothing about how long to wait"
        return float(seconds), f"Retry-After {seconds}s"
    try:
        when = email.utils.parsedate_to_datetime(text)
    except (TypeError, ValueError):
        return None, f"unparseable Retry-After {text!r}"
    if when.tzinfo is None:  # an HTTP-date is GMT by definition
        when = when.replace(tzinfo=datetime.timezone.utc)
    wait = when.timestamp() - now_s
    if wait <= 0:
        return None, f"Retry-After {text!r}, already past"
    return wait, f"Retry-After {text!r}, {wait:.0f}s away"


class HttpClient:
    """Requests over an ordered list of endpoints.

    Each pass tries every endpoint once, in order. A hang, a dead connection, a
    non-200, or a 200 the `accept` hook rejects with `Retry` moves on to the next
    endpoint and is retried on the next pass. Passes are separated by a doubling
    backoff, or by a longer Retry-After, up to `attempts` passes.
    """

    def __init__(self, endpoints: Sequence[Endpoint], *, timeout_s: float, attempts: int,
                 backoff_s: float, min_interval_s: float, transport: Transport,
                 sleep: Callable[[float], None] = time.sleep,
                 monotonic: Callable[[], float] = time.monotonic,
                 wall: Callable[[], float] = time.time):
        if not endpoints:
            raise ValueError("at least one endpoint")
        self.endpoints = tuple(endpoints)
        self.timeout_s, self.attempts = timeout_s, attempts
        self.backoff_s, self.min_interval_s = backoff_s, min_interval_s
        self._transport, self._sleep, self._monotonic, self._wall = transport, sleep, monotonic, wall
        self._last_request: float | None = None
        self._redactor = redaction.Redactor()

    def scrub(self, text: str) -> str:
        """Mask declared credentials, and every endpoint URL by its name. An
        exception from the transport can quote the URL, and an RPC URL is the
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

    def _limited(self, reply: Reply) -> tuple[float, str]:
        """A 429 or 503: how long it asks us to wait (0 for no usable hint), and
        the failure text."""
        wait, said = retry_after(reply.headers, self._wall())
        head = "rate limited: HTTP 429" if reply.status == 429 else f"HTTP {reply.status}"
        if wait is not None and wait > self.timeout_s:
            return wait, f"{head}, {said}: longer than the {self.timeout_s}s request deadline, so not waited"
        return wait or 0.0, f"{head}, {said}"

    def send(self, body: bytes | None = None, *, path: str = "",
             accept: Callable[[Reply], Any] = lambda reply: reply) -> Any:
        """One request, `body` None for a GET. Returns `accept(reply)` for the
        first acceptable 200, or raises `Unavailable` naming every failure."""
        failures: list[tuple[str, str]] = []
        hinted = 0.0
        for attempt in range(self.attempts):
            if attempt:
                if hinted > self.timeout_s:
                    break
                self._sleep(max(self.backoff_s * 2 ** (attempt - 1), hinted))
                hinted = 0.0
            for endpoint in self.endpoints:
                self._pace()
                try:
                    reply = Reply.of(with_deadline(
                        lambda: self._transport(endpoint.url + path, body, self.timeout_s),
                        self.timeout_s))
                except _Hang:
                    failures.append((endpoint.name, f"hang: no complete response in {self.timeout_s}s"))
                    continue
                except Exception as error:  # DNS, TLS, reset, socket timeout
                    failures.append((endpoint.name, "unreachable: " + self.scrub(
                        f"{type(error).__name__}: {error}")))
                    continue
                if reply.status in (429, 503):
                    wait, why = self._limited(reply)
                    hinted = max(hinted, wait)
                    failures.append((endpoint.name, why))
                    continue
                if reply.status == 403:
                    failures.append((endpoint.name, "HTTP 403: a missing User-Agent reads "
                                                    "exactly like this (probe 0.3)"))
                    continue
                if reply.status != 200:
                    failures.append((endpoint.name, f"HTTP {reply.status}"))
                    continue
                try:
                    return accept(reply)
                except Retry as transient:
                    failures.append((endpoint.name, self.scrub(str(transient))))
        raise Unavailable(failures)
