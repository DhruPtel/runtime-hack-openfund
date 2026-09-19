"""Raw source responses to disk, timestamped by code, never by an agent. Unit 1.9.

A capture is what one live build heard, recorded at the transport, the seam
every adapter already takes (`http.Transport`), so no adapter changes shape:

- **every exchange**, request and answer as the bytes that crossed the wire,
  with its endpoint by name (an RPC URL is a declared credential), when it was
  sent and received, and the block it addressed;
- **every reading of each source's clock**, so a replay never asks today's
  clock about last week's data.

A replay serves those answers back through the same adapters and opens no
connection. A request the capture did not record, or a clock read past the end
of its tape, is `ReplayMiss`. That is not an `Exception`, so no client can take
it for an unreachable source and carry on with a degraded snapshot; the build
stops and names the request. `no_network()` makes the same true of the socket
layer, for anything that would bypass the transports.

On disk, one directory per capture:
- `manifest.json`: the block, the endpoints, when it was captured and by which
  commit, each file's sha256, the raw answers' one hash, and the snapshot the
  live build produced;
- `<source>.jsonl.gz`: one exchange per line, in the order it began, its
  headers as sent except `Set-Cookie`, a server's session cookie, which no
  adapter reads and which does not belong in a repository;
- `clock.json.gz`: each source's clock readings, in order;
- `config/`: the config files the build read. The registry and the feed
  directory are referenced by sha256, not copied: they are already pinned in
  `config/registry/` under their hashes (1.2);
- `snapshot.json`: the live build's snapshot, byte for byte, to compare with.

Everything written passes through the credential redactor (0.1), and is then
checked for every declared credential value the environment holds.
"""

from __future__ import annotations

import base64
import contextlib
import gzip
import hashlib
import json
import socket
import threading
import time
from collections import deque
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Iterator, Mapping

from fund import redaction
from fund.adapters.http import Transport
from fund.core.types import Instant

FORMAT = "openfund.capture/1"
MANIFEST = "manifest.json"
CLOCK = "clock.json.gz"
DROPPED_HEADERS = ("set-cookie",)
SNAPSHOT = "snapshot.json"
CONFIG_DIR = "config"


class ReplayMiss(BaseException):
    """The replay was asked for something the capture does not hold. A
    BaseException, so no adapter's `except Exception` can turn it into an
    unreachable reading."""


class NetworkDisabled(BaseException):
    """Something tried to open a connection during a replay."""


@contextlib.contextmanager
def no_network() -> Iterator[None]:
    """Refuse every connection and name lookup in this process until exit."""
    def refusing(what: str) -> Callable[..., Any]:
        def refuse(*args: Any, **kwargs: Any) -> Any:
            raise NetworkDisabled(f"{what}{args!r}: the network is disabled during a replay")
        return refuse

    saved = (socket.socket.connect, socket.socket.connect_ex, socket.create_connection,
             socket.getaddrinfo)
    socket.socket.connect = refusing("socket.connect")                  # type: ignore[method-assign]
    socket.socket.connect_ex = refusing("socket.connect_ex")            # type: ignore[method-assign]
    socket.create_connection = refusing("socket.create_connection")     # type: ignore[assignment]
    socket.getaddrinfo = refusing("socket.getaddrinfo")                 # type: ignore[assignment]
    try:
        yield
    finally:
        (socket.socket.connect, socket.socket.connect_ex, socket.create_connection,
         socket.getaddrinfo) = saved


def _ms() -> int:
    return time.time_ns() // 1_000_000


def _text(data: bytes | None) -> dict[str, str] | None:
    if data is None:
        return None
    try:
        return {"text": data.decode("utf-8")}
    except UnicodeDecodeError:
        return {"base64": base64.b64encode(data).decode("ascii")}


def _bytes(field: dict[str, str] | None) -> bytes | None:
    if field is None:
        return None
    return field["text"].encode("utf-8") if "text" in field else base64.b64decode(field["base64"])


def _block(body: bytes | None) -> str | None:
    """The block a JSON-RPC request addressed by hash, if it named one."""
    if body is None:
        return None
    try:
        params = json.loads(body).get("params", [])
    except (ValueError, AttributeError):
        return None
    for p in params if isinstance(params, list) else []:
        if isinstance(p, dict) and "blockHash" in p:
            return p["blockHash"]
    return None


def _split(url: str, endpoints: Mapping[str, str]) -> tuple[str, str]:
    """(endpoint name, what follows its URL): a request is never kept by URL."""
    for name, base in sorted(endpoints.items(), key=lambda e: -len(e[1])):
        if url.startswith(base):
            return name, url[len(base):]
    raise ValueError("a request to an endpoint this source does not declare")


def _named(text: str, endpoints: Mapping[str, str]) -> str:
    for name, base in endpoints.items():
        text = text.replace(base, f"<{name}>")
    return text


class Recorder:
    """One source's exchanges, in the order they began, and its clock readings."""

    def __init__(self, source: str, endpoints: Mapping[str, str]):
        self.source, self.endpoints = source, dict(endpoints)
        self.exchanges: list[dict[str, Any]] = []
        self.readings: list[int] = []
        self._lock = threading.Lock()

    def transport(self, inner: Transport) -> Transport:
        def send(url: str, body: bytes | None, timeout_s: float) -> tuple:
            name, path = _split(url, self.endpoints)
            record = {"endpoint": name, "path": path, "request": _text(body), "block": _block(body),
                      "timeout_ms": int(timeout_s * 1000), "sent_at": _ms()}
            with self._lock:
                n = len(self.exchanges)
                self.exchanges.append(record | {"n": n, "outcome": "no answer: abandoned"})
            started = time.monotonic()
            try:
                result = inner(url, body, timeout_s)
            except Exception as error:
                self.exchanges[n] = record | {
                    "n": n, "received_at": _ms(), "elapsed_ms": int((time.monotonic() - started) * 1000),
                    "raised": {"type": type(error).__name__,
                               "message": _named(str(error), self.endpoints)}}
                raise
            status, reply, *rest = result
            headers = ({k: v for k, v in rest[0].items() if k.lower() not in DROPPED_HEADERS}
                       if rest else None)
            self.exchanges[n] = record | {
                "n": n, "received_at": _ms(), "elapsed_ms": int((time.monotonic() - started) * 1000),
                "status": status, "headers": headers, "body": _text(reply)}
            return result
        return send

    def clock(self, inner: Callable[[], Instant]) -> Callable[[], Instant]:
        def read() -> Instant:
            reading = inner()
            self.readings.append(reading.epoch_ms)
            return reading
        return read


def _hung(record: Mapping[str, Any]) -> bool:
    """The client gave up on it: no answer, or one later than its deadline."""
    return "received_at" not in record or record["elapsed_ms"] > record["timeout_ms"]


class Replayer:
    """Serves one source's recorded answers back, and its clock readings in
    order. Nothing else: an unrecorded request or an extra clock read is a
    `ReplayMiss`."""

    def __init__(self, source: str, endpoints: Mapping[str, str], exchanges: list[dict],
                 readings: list[int]):
        self.source, self.endpoints = source, dict(endpoints)
        self._queues: dict[tuple, deque] = {}
        for record in exchanges:
            key = (record["endpoint"], record["path"], json.dumps(record["request"]))
            self._queues.setdefault(key, deque()).append(record)
        self._tape = deque(readings)

    def transport(self) -> Transport:
        def send(url: str, body: bytes | None, timeout_s: float) -> tuple:
            name, path = _split(url, self.endpoints)
            queue = self._queues.get((name, path, json.dumps(_text(body))))
            if not queue:
                shown = (body or b"").decode("utf-8", "replace")[:160]
                raise ReplayMiss(f"{self.source}: {name}{path} was asked {shown!r}, which the "
                                 f"capture does not hold")
            record = queue.popleft()
            if _hung(record):
                time.sleep(timeout_s + 0.25)  # the client gives up at its deadline, as it did live
            if "raised" in record:
                raised = record["raised"]
                raise type(raised["type"], (Exception,), {})(raised["message"])
            return record["status"], _bytes(record["body"]), record["headers"] or {}
        return send

    def clock(self) -> Callable[[], Instant]:
        def read() -> Instant:
            if not self._tape:
                raise ReplayMiss(f"{self.source}'s clock was read more often than the capture "
                                 f"recorded: a replay never falls back to today's clock")
            return Instant(self._tape.popleft())
        return read

    def unused(self) -> tuple[int, int]:
        """(exchanges, clock readings) the replay never asked for."""
        return sum(len(q) for q in self._queues.values()), len(self._tape)


# --- on disk ---------------------------------------------------------------------------------

def _lines(records: list[dict]) -> bytes:
    return b"".join(json.dumps(r, sort_keys=True, separators=(",", ":")).encode("utf-8") + b"\n"
                    for r in records)


def _pretty(document: Any) -> bytes:
    return json.dumps(document, indent=1, sort_keys=True, ensure_ascii=False).encode("utf-8") + b"\n"


def answers_sha256(answers: Mapping[str, str]) -> str:
    """One hash for a capture's raw answers and clock tape, from each file's
    sha256: what a snapshot cites, so every captured byte moves its hash."""
    listing = json.dumps(dict(sorted(answers.items())), separators=(",", ":"))
    return hashlib.sha256(listing.encode("utf-8")).hexdigest()


def _is_answer(name: str) -> bool:
    """The raw answers and the clock tape. Config copies are cited by the
    snapshot's own config hashes; the snapshot and manifest are outputs."""
    return name.endswith(".jsonl.gz") or name == CLOCK


@dataclass(frozen=True)
class Sealed:
    """A capture's files, masked and checked, before a snapshot is built from them."""

    files: Mapping[str, bytes]           # every file but the snapshot and the manifest
    exchanges: Mapping[str, int]
    clock_readings: Mapping[str, int]
    masked: int

    @property
    def answers(self) -> dict[str, str]:
        return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(self.files.items())
                if _is_answer(name)}

    @property
    def sha256(self) -> str:
        return answers_sha256(self.answers)


def _leaked(*blobs: bytes) -> list[str]:
    return sorted({label for value, label in redaction.build_denylist().items()
                   for data in blobs if value.encode("utf-8") in data})


def seal(recorders: Mapping[str, Recorder], config_files: Mapping[str, bytes]) -> Sealed:
    """A capture's files, masked by the credential redactor, then refused if any
    declared credential value the environment holds is still anywhere in them."""
    redactor = redaction.Redactor()
    masked = 0

    def clean(text: str) -> str:
        nonlocal masked
        out = redactor.redact(text)
        masked += out != text
        return out

    files: dict[str, bytes] = {}
    talkers = {source: r for source, r in recorders.items() if r.endpoints}  # a clock alone has none
    for source, recorder in talkers.items():
        records = json.loads(clean(json.dumps(recorder.exchanges)))
        files[f"{source}.jsonl.gz"] = _lines(records)
    files[CLOCK] = _pretty({source: r.readings for source, r in recorders.items()})
    for name, data in config_files.items():
        files[f"{CONFIG_DIR}/{name}"] = clean(data.decode("utf-8")).encode("utf-8")
    leaked = _leaked(*files.values())
    if leaked:
        raise ValueError(f"refusing a capture that still holds {', '.join(leaked)}")
    return Sealed(files, {s: len(r.exchanges) for s, r in talkers.items()},
                  {s: len(r.readings) for s, r in recorders.items()}, masked)


def write(directory: Path, sealed: Sealed, *, manifest: Mapping[str, Any],
          snapshot_body: bytes) -> dict[str, Any]:
    """Write a sealed capture, the snapshot built from it, and its manifest."""
    files = dict(sealed.files) | {SNAPSHOT: snapshot_body}
    document = json.loads(redaction.Redactor().redact(json.dumps(dict(manifest)))) | {
        "format": FORMAT,
        "files": {name: {"sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)}
                  for name, data in sorted(files.items())},
        "answers_sha256": sealed.sha256,
        "exchanges": dict(sealed.exchanges),
        "headers_dropped": list(DROPPED_HEADERS),
        "clock_readings": dict(sealed.clock_readings),
        "redaction": {"credentials_checked": sorted(set(redaction.build_denylist().values())),
                      "strings_masked": sealed.masked},
    }
    leaked = _leaked(snapshot_body, _pretty(document))
    if leaked:
        raise ValueError(f"refusing to write a capture that still holds {', '.join(leaked)}")
    directory.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        path = directory / name
        path.parent.mkdir(parents=True, exist_ok=True)
        if name.endswith(".gz"):
            with open(path, "wb") as raw, gzip.GzipFile(fileobj=raw, mode="wb", mtime=0) as gz:
                gz.write(data)
        else:
            path.write_bytes(data)
    (directory / MANIFEST).write_bytes(_pretty(document))
    return document


class Capture:
    """A capture read back from disk, each file checked against the manifest."""

    def __init__(self, directory: Path):
        self.directory = directory
        self.manifest = json.loads((directory / MANIFEST).read_text())
        if self.manifest.get("format") != FORMAT:
            raise ValueError(f"{directory} is not a {FORMAT} capture")
        self._files = {name: self._read(name) for name in self.manifest["files"]}
        self.altered = sorted(name for name, data in self._files.items()
                              if hashlib.sha256(data).hexdigest() != self.manifest["files"][name]["sha256"])
        self.readings: dict[str, list[int]] = json.loads(self._files[CLOCK])

    def _read(self, name: str) -> bytes:
        path = self.directory / name
        return gzip.decompress(path.read_bytes()) if name.endswith(".gz") else path.read_bytes()

    def exchanges(self, source: str) -> list[dict]:
        data = self._files.get(f"{source}.jsonl.gz", b"")
        return [json.loads(line) for line in data.splitlines()]

    def config_files(self) -> dict[str, bytes]:
        prefix = CONFIG_DIR + "/"
        return {name[len(prefix):]: data for name, data in self._files.items()
                if name.startswith(prefix)}

    @property
    def snapshot_body(self) -> bytes:
        return self._files[SNAPSHOT]

    @property
    def answers(self) -> dict[str, str]:
        """Each raw-answer file's sha256, from the bytes on disk: an altered
        file changes it, and with it the rebuilt snapshot."""
        return {name: hashlib.sha256(data).hexdigest() for name, data in sorted(self._files.items())
                if _is_answer(name)}

    @property
    def sha256(self) -> str:
        return answers_sha256(self.answers)

    def replayer(self, source: str, endpoints: Mapping[str, str]) -> Replayer:
        return Replayer(source, endpoints, self.exchanges(source), self.readings.get(source, []))
