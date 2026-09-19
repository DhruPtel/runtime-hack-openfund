"""The shared HTTP client, offline (unit 1.3's transport, moved at 1.4).

The chain adapter's own tests still drive it through `RpcClient`. These cover
what the move added: GETs for GeckoTerminal, and Retry-After, which the RPC
never sends and GeckoTerminal sends as 0.
"""

from __future__ import annotations

import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from fund.adapters import http


def client(*names, transport, attempts=3, timeout_s=0.2, backoff_s=1.0, sleeps=None, wall=None):
    return http.HttpClient(
        [http.Endpoint(name, f"https://{name.lower()}.invalid/secret-key") for name in names],
        timeout_s=timeout_s, attempts=attempts, backoff_s=backoff_s, min_interval_s=0.0,
        transport=transport, sleep=(sleeps if sleeps is not None else []).append,
        wall=wall or (lambda: 1_790_000_000.0))


def replies(*items):
    queue = iter(items)
    return lambda url, body, timeout: next(queue)


OK = (200, b"{}", {})


# --- what moved from the chain adapter ------------------------------------------------

def test_a_hang_advances_to_the_next_endpoint():
    used = []

    def transport(url, body, timeout):
        used.append(url)
        if "primary" in url:
            time.sleep(1.0)
        return OK

    assert client("PRIMARY", "SECONDARY", transport=transport).send(b"{}").status == 200
    assert ["primary" in u for u in used] == [True, False]


def test_passes_back_off_doubling():
    sleeps: list[float] = []
    transport = replies((500, b"", {}), (502, b"", {}), OK)
    assert client("ONLY", transport=transport, sleeps=sleeps).send().status == 200
    assert sleeps == [1.0, 2.0]


def test_a_failure_names_endpoints_and_hides_their_urls():
    def transport(url, body, timeout):
        raise ConnectionResetError(f"reset by {url}")

    with pytest.raises(http.Unavailable) as failure:
        client("PRIMARY", transport=transport, attempts=1).send()
    assert failure.value.rule == http.RULE_TRANSPORT
    assert "secret-key" not in str(failure.value) and "<PRIMARY>" in str(failure.value)


# --- Retry-After ------------------------------------------------------------------------

def test_a_positive_retry_after_longer_than_the_backoff_is_waited_out():
    sleeps: list[float] = []
    transport = replies((429, b"", {"Retry-After": "7"}), OK)
    assert client("ONLY", transport=transport, timeout_s=20, sleeps=sleeps).send().status == 200
    assert sleeps == [7.0]


def test_a_retry_after_shorter_than_the_backoff_does_not_shorten_it():
    sleeps: list[float] = []
    transport = replies((429, b"", {"retry-after": "1"}), (429, b"", {"retry-after": "1"}), OK)
    client("ONLY", transport=transport, timeout_s=20, backoff_s=3.0, sleeps=sleeps).send()
    assert sleeps == [3.0, 6.0]


def test_retry_after_zero_is_no_hint_and_the_backoff_applies():
    # GeckoTerminal's 429 says `Retry-After: 0`, and polls a second apart stayed
    # 429 for 4.3 s (measured 2026-09-19). Taking it literally would retry at once.
    sleeps: list[float] = []
    transport = replies((429, b"", {"Retry-After": "0"}), (429, b"", {"Retry-After": "0"}), OK)
    assert client("ONLY", transport=transport, sleeps=sleeps).send().status == 200
    assert sleeps == [1.0, 2.0]


def test_retry_after_zero_is_named_in_the_failure():
    transport = replies((429, b"", {"Retry-After": "0"}))
    with pytest.raises(http.Unavailable, match="Retry-After 0, which says nothing"):
        client("ONLY", transport=transport, attempts=1).send()


def test_a_retry_after_past_the_request_deadline_fails_loudly_without_waiting():
    sleeps: list[float] = []
    transport = replies((429, b"", {"Retry-After": "120"}), OK)
    with pytest.raises(http.Unavailable, match="longer than the 20s request deadline"):
        client("ONLY", transport=transport, timeout_s=20, sleeps=sleeps).send()
    assert sleeps == []


def test_retry_after_as_an_http_date_is_read_against_the_clock():
    sleeps: list[float] = []
    now = 1_790_000_000.0  # Mon, 21 Sep 2026 14:13:20 GMT
    transport = replies((503, b"", {"Retry-After": "Mon, 21 Sep 2026 14:13:32 GMT"}), OK)
    client("ONLY", transport=transport, timeout_s=20, sleeps=sleeps, wall=lambda: now).send()
    assert sleeps == [pytest.approx(12.0)]


@pytest.mark.parametrize("value", ["soon", "Mon, 21 Sep 2026 14:13:00 GMT"])
def test_an_unparseable_or_past_retry_after_falls_back_to_the_backoff(value):
    sleeps: list[float] = []
    transport = replies((429, b"", {"Retry-After": value}), OK)
    client("ONLY", transport=transport, sleeps=sleeps, wall=lambda: 1_790_000_000.0).send()
    assert sleeps == [1.0]


# --- the real transport ----------------------------------------------------------------

def test_the_real_transport_gets_with_a_user_agent_and_returns_headers():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            seen["ua"], seen["path"] = self.headers.get("User-Agent"), self.path
            self.send_response(429)
            self.send_header("Retry-After", "0")
            self.send_header("Content-Length", "2")
            self.end_headers()
            self.wfile.write(b"{}")

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    try:
        reply = http.Reply.of(http.urllib_transport("openfund-gecko/1.4")(
            f"http://127.0.0.1:{server.server_port}/networks/x", None, 5))
    finally:
        server.server_close()
    assert seen == {"ua": "openfund-gecko/1.4", "path": "/networks/x"}
    assert reply.status == 429 and reply.headers["retry-after"] == "0"
