"""The LLM gateway client (unit 2.4): one call, one attempt.

`adapters/http.py`'s client retries. A hang, a 5xx, a 429 or an unusable body
moves it to another attempt. A model call is billed whether or not its reply
arrives (F0.9.3), so a retried call can be billed twice. This client sends
exactly one request per call and hands back whatever came of it:
  - **a reply:** the text, why the model stopped, the usage block and the
    request id;
  - **a refusal:** the status and its body, kept. A 402 says
    `insufficient_credits`, and that is the evidence;
  - **a timeout or transport failure:** a named error, never an exception.

It retries nothing. Whether to try again is the worker's decision, and the
worker tries again only for a reply that arrived malformed.

The whole request is bounded by `http.with_deadline`. A socket timeout bounds
each blocking read, and a server that trickles bytes can outlast it.

It sends `X-API-Key`; either header works (F0.2.1). The key never appears in
what this returns: anything the server echoes, and any error text, is masked.
"""

from __future__ import annotations

import json
import socket
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping

from fund.adapters import http as shared_http

GATEWAY = "https://llm.bankr.bot"
COMPLETIONS = "/v1/chat/completions"
USER_AGENT = "openfund/2.4 (+one attempt per call)"
KEPT_BODY = 4000

#: `(url, body, headers, timeout_s) -> (status, body)`. An HTTP error status is an
#: answer, returned; only a transport failure raises.
Send = Callable[[str, bytes, Mapping[str, str], float], "tuple[int, bytes]"]


@dataclass(frozen=True)
class Reply:
    status: int | None
    text: str
    finish_reason: str | None
    usage: Mapping[str, Any]
    request_id: str | None
    model: str | None
    elapsed_ms: int
    error: str | None  # "timeout", "transport: …", "unreadable body", or None
    body: str = ""  # a refusal's or failure's raw body, masked; empty for a reply
    provider: Mapping[str, Any] = field(default_factory=dict)  # the reply's other fields, raw

    @property
    def arrived(self) -> bool:
        """A reply came back and was read. Not a verdict on what it says."""
        return self.status == 200 and self.error is None


def urllib_send(url: str, body: bytes, headers: Mapping[str, str], timeout_s: float
                ) -> tuple[int, bytes]:
    request = urllib.request.Request(url, data=body, method="POST", headers=dict(headers))
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return response.status, response.read()
    except urllib.error.HTTPError as error:
        return error.code, error.read()


def _timed_out(error: BaseException) -> bool:
    if isinstance(error, (socket.timeout, TimeoutError)):
        return True
    return isinstance(error, urllib.error.URLError) and isinstance(error.reason, socket.timeout)


def complete(key: str, *, model: str, system: str, user: str, max_tokens: int,
             timeout_s: float, base_url: str = GATEWAY, send: Send | None = None,
             clock: Callable[[], float] = time.monotonic) -> Reply:
    """One chat completion, one request. Never raises for anything the network does."""
    send = urllib_send if send is None else send
    mask = (lambda text: text.replace(key, "[GATEWAY_KEY]")) if key else (lambda text: text)
    payload = json.dumps({
        "model": model, "max_tokens": max_tokens, "temperature": 0,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": user}],
    }).encode("utf-8")
    headers = {"X-API-Key": key, "Content-Type": "application/json", "User-Agent": USER_AGENT}

    started = clock()
    elapsed = lambda: int((clock() - started) * 1000)
    failed = lambda error, body="": Reply(None, "", None, {}, None, None, elapsed(), error,
                                          mask(body)[:KEPT_BODY])
    try:
        status, raw = shared_http.with_deadline(
            lambda: send(base_url + COMPLETIONS, payload, headers, timeout_s), timeout_s)
    except shared_http._Hang:  # the whole-request deadline, not a socket read
        return failed("timeout")
    except Exception as error:  # a transport failure is a result, not a crash
        if _timed_out(error):
            return failed("timeout")
        return failed(mask(f"transport: {type(error).__name__}: {error}"))

    text = raw.decode("utf-8", errors="replace")
    if status != 200:
        return Reply(status, "", None, {}, None, None, elapsed(), None, mask(text)[:KEPT_BODY])
    try:
        parsed = json.loads(text)
        choice = parsed["choices"][0]
        content = choice["message"]["content"] or ""
    except (ValueError, KeyError, IndexError, TypeError):
        return Reply(status, "", None, {}, None, None, elapsed(), "unreadable body",
                     mask(text)[:KEPT_BODY])
    return Reply(status=status, text=mask(content), finish_reason=choice.get("finish_reason"),
                 usage=parsed.get("usage") or {}, request_id=parsed.get("id"),
                 model=parsed.get("model"), elapsed_ms=elapsed(), error=None,
                 provider={k: v for k, v in parsed.items() if k not in ("choices", "usage")})
