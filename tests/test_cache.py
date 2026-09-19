"""Unit 1.9, the capture at the transport: what was recorded is served back exactly,
by endpoint name and never by URL, and anything else (an unrecorded request, a clock
read past the tape, a connection) stops the build instead of degrading it."""

from __future__ import annotations

import gzip
import json
import socket
import urllib.request

import pytest

from fund.adapters import cache, http
from fund.core.types import Instant

SECRET_URL = "https://rpc.example.invalid/v2/secret-key"
LIVE = {"RPC_4663_MAINNET": SECRET_URL}
REPLAY = {"RPC_4663_MAINNET": "replay://RPC_4663_MAINNET"}
T0 = 1_790_000_000_000


def client(endpoints, transport) -> http.HttpClient:
    return http.HttpClient([http.Endpoint(n, u) for n, u in endpoints.items()], timeout_s=2,
                           attempts=2, backoff_s=0, min_interval_s=0, transport=transport)


def live_run():
    """A 429 then a 200 for one request, a refused second request, and one clock read."""
    replies = iter([(429, b"busy", {"retry-after": "0"}), (200, b'{"result":"0x1"}', {"x-a": "b"})])

    def wire(url, body, timeout):
        if body == b'{"id":2}':
            raise ConnectionResetError(f"reset by {url}")
        return next(replies)

    recorder = cache.Recorder("chain", LIVE)
    rpc = client(LIVE, recorder.transport(wire))
    answer = rpc.send(b'{"id":1}')
    with pytest.raises(http.Unavailable) as failure:
        rpc.send(b'{"id":2}')
    stamp = recorder.clock(lambda: Instant(T0))()
    return recorder, answer, str(failure.value), stamp


def test_an_exchange_is_kept_by_endpoint_name_and_never_by_url():
    recorder, *_ = live_run()
    assert [e["endpoint"] for e in recorder.exchanges] == ["RPC_4663_MAINNET"] * 4
    assert [e.get("status") for e in recorder.exchanges] == [429, 200, None, None]
    assert "secret-key" not in json.dumps(recorder.exchanges)
    assert "<RPC_4663_MAINNET>" in recorder.exchanges[2]["raised"]["message"]


def test_a_replay_serves_the_same_answers_and_failures_in_order():
    recorder, answer, failure, stamp = live_run()
    replayer = cache.Replayer("chain", REPLAY, recorder.exchanges, recorder.readings)
    rpc = client(REPLAY, replayer.transport())
    again = rpc.send(b'{"id":1}')  # the 429, retried, then the 200: as it happened live
    assert (again.status, again.body, dict(again.headers)) == (answer.status, answer.body, dict(answer.headers))
    with pytest.raises(http.Unavailable) as replayed:
        rpc.send(b'{"id":2}')
    assert str(replayed.value) == failure
    assert replayer.clock()() == stamp
    assert replayer.unused() == (0, 0)


def test_an_unrecorded_request_stops_the_build_instead_of_reading_as_unreachable():
    recorder, *_ = live_run()
    rpc = client(REPLAY, cache.Replayer("chain", REPLAY, recorder.exchanges, []).transport())
    with pytest.raises(cache.ReplayMiss, match="does not hold"):
        rpc.send(b'{"id":3}')


def test_a_clock_read_past_the_tape_never_falls_back_to_today():
    tape = cache.Replayer("run", {}, [], [T0]).clock()
    assert tape() == Instant(T0)
    with pytest.raises(cache.ReplayMiss, match="today's clock"):
        tape()


def test_no_network_refuses_connections_urllib_cannot_swallow():
    with cache.no_network():
        with pytest.raises(cache.NetworkDisabled):
            socket.create_connection(("127.0.0.1", 9), timeout=1)
        with pytest.raises(cache.NetworkDisabled):  # not a URLError: urllib cannot catch it
            urllib.request.urlopen("http://127.0.0.1:9/", timeout=1)
    with pytest.raises(OSError):  # restored on exit: a real, refused connection
        socket.create_connection(("127.0.0.1", 9), timeout=1)


def written(tmp_path, monkeypatch):
    monkeypatch.setenv("RPC_4663_MAINNET", SECRET_URL)
    recorder, *_ = live_run()
    recorder.exchanges[1]["body"] = {"text": f'{{"echo":"{SECRET_URL}"}}'}  # a body quoting it
    manifest = cache.write(tmp_path, recorders={"chain": recorder}, manifest={"block": {}},
                           config_files={"chain.json": b"{}"}, snapshot_body=b"{}\n")
    return manifest


def test_a_capture_is_masked_by_the_credential_table_before_it_is_written(tmp_path, monkeypatch):
    manifest = written(tmp_path, monkeypatch)
    assert manifest["redaction"]["strings_masked"] == 1
    everything = b"".join(p.read_bytes() if p.suffix != ".gz" else gzip.decompress(p.read_bytes())
                          for p in tmp_path.rglob("*") if p.is_file())
    assert SECRET_URL.encode() not in everything and b"[REDACTED:RPC_4663_MAINNET]" in everything


def test_a_changed_byte_in_a_captured_answer_is_named_on_load(tmp_path, monkeypatch):
    written(tmp_path, monkeypatch)
    assert cache.Capture(tmp_path).altered == []
    path = tmp_path / "chain.jsonl.gz"
    raw = gzip.decompress(path.read_bytes())
    assert raw.count(b"busy") == 1
    path.write_bytes(gzip.compress(raw.replace(b"busy", b"bust")))
    assert cache.Capture(tmp_path).altered == ["chain.jsonl.gz"]
