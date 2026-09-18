"""Probe harness: one timed HTTP call, captured with every secret masked.

Throwaway, like everything under `probes/`. Nothing in `src/` imports it.

Three rules it exists to enforce, because a probe's whole value is its recorded
evidence and a probe that leaks a key into `research/findings.md` has poisoned
the artifact it was written to produce:

  - every captured string passes through `fund.redaction` before it is returned,
  - a transport failure is a *result* with a reason, never an exception that
    loses the evidence of what was attempted,
  - a response body is truncated to a stated length, and the truncation is
    visible rather than silent.

stdlib only. `pyproject.toml` declares no runtime dependencies yet; unit 1.3
picks the real HTTP client, and a throwaway probe should not make that choice.
"""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any

from fund import redaction

#: Probes are read-only and cheap. A surface that has not answered in this long
#: is itself the finding.
TIMEOUT_SECONDS = 20

#: Enough to see the shape of an error body without pasting a page into findings.
MAX_BODY_CHARS = 600


@dataclass
class Capture:
    """One request and what came back. Every string field is already redacted."""

    label: str
    method: str
    url: str
    header_name: str
    request_body: str = ""
    status: int | None = None
    elapsed_ms: int | None = None
    body: str = ""
    truncated: bool = False
    transport_error: str | None = None
    response_headers: dict[str, str] = field(default_factory=dict)

    @property
    def reached_server(self) -> bool:
        return self.status is not None

    def summary(self) -> str:
        if self.transport_error:
            return f"transport error: {self.transport_error}"
        return f"HTTP {self.status} in {self.elapsed_ms} ms"


#: Response headers worth keeping. Everything else is noise, and an
#: allowlist means a provider cannot hand us a header we echo into findings
#: without having thought about it.
KEEP_HEADERS = (
    "content-type",
    "retry-after",
    "x-ratelimit-limit",
    "x-ratelimit-remaining",
    "x-ratelimit-reset",
    "x-request-id",
    "www-authenticate",
)


def call(
    label: str,
    url: str,
    header_name: str,
    header_value: str,
    *,
    method: str = "GET",
    json_body: Any | None = None,
    timeout: int = TIMEOUT_SECONDS,
) -> Capture:
    """Make one request and capture it. Never raises for an HTTP or network fault.

    ``json_body`` is sent as the request body and recorded on the capture: a
    probe that discovers a request schema by reading validation errors is
    worthless unless the exact payload that produced each error is kept with it.
    """
    redactor = redaction.Redactor()
    if json_body is not None and method == "GET":
        method = "POST"
    capture = Capture(label=label, method=method, url=redactor.redact(url),
                      header_name=header_name)

    data = None
    if json_body is not None:
        data = json.dumps(json_body, sort_keys=True).encode("utf-8")
        capture.request_body = redactor.redact(data.decode("utf-8"))

    request = urllib.request.Request(url, data=data, method=method)
    request.add_header(header_name, header_value)
    request.add_header("Accept", "application/json")
    if data is not None:
        request.add_header("Content-Type", "application/json")

    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            capture.status = response.status
            raw = response.read().decode("utf-8", errors="replace")
            capture.response_headers = _kept_headers(response.headers, redactor)
    except urllib.error.HTTPError as error:
        # A 4xx/5xx is the answer, not a failure. Its body is the evidence.
        capture.status = error.code
        raw = error.read().decode("utf-8", errors="replace")
        capture.response_headers = _kept_headers(error.headers, redactor)
    except Exception as error:  # timeout, DNS, TLS, connection reset
        capture.transport_error = redactor.redact(f"{type(error).__name__}: {error}")
        capture.elapsed_ms = int((time.monotonic() - started) * 1000)
        return capture

    capture.elapsed_ms = int((time.monotonic() - started) * 1000)

    body = redactor.redact(raw.strip())
    if len(body) > MAX_BODY_CHARS:
        body = body[:MAX_BODY_CHARS]
        capture.truncated = True
    capture.body = body
    return capture


def _kept_headers(headers: Any, redactor: redaction.Redactor) -> dict[str, str]:
    kept = {}
    for name in KEEP_HEADERS:
        value = headers.get(name)
        if value:
            kept[name] = redactor.redact(str(value))
    return kept


def as_json(capture: Capture) -> Any:
    """Parse a captured body, or None. Used only to read a field, never to trust one."""
    try:
        return json.loads(capture.body)
    except Exception:
        return None
