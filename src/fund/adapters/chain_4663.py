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
