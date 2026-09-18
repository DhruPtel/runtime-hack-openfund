"""Unit 1.3: the chain adapter, offline.

Transports are injected to hang, refuse and rate-limit on purpose. The one
live read is the adapter's own `--prove` entry point, which is not part of
`make test`.
"""

from __future__ import annotations

import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from fund.adapters import chain_4663 as chain


def ok(result) -> tuple[int, bytes]:
    return 200, json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()


def client(*endpoints, transport, attempts=2, timeout_s=0.2, sleeps=None):
    sleeps = [] if sleeps is None else sleeps
    return chain.RpcClient(
        [chain.Endpoint(name, f"https://{name.lower()}.invalid/secret-key") for name in endpoints],
        timeout_s=timeout_s, attempts=attempts, backoff_s=1.0, min_interval_s=0.0,
        transport=transport, sleep=sleeps.append)


# --- failover ---------------------------------------------------------------------

def test_a_hang_advances_to_the_next_endpoint():
    used = []

    def transport(url, body, timeout):
        used.append(url)
        if "primary" in url:
            time.sleep(1.0)  # accepts, then never answers within the deadline
        return ok("0x1")

    rpc = client("PRIMARY", "SECONDARY", transport=transport)
    assert rpc.call("eth_blockNumber", []) == "0x1"
    assert ["primary" in u for u in used] == [True, False]


def test_a_rate_limit_backs_off_and_retries():
    replies = iter([(429, b"Too Many Requests"), ok("0x2")])
    sleeps: list[float] = []
    rpc = client("ONLY", transport=lambda *a: next(replies), sleeps=sleeps)
    assert rpc.call("eth_blockNumber", []) == "0x2"
    assert sleeps == [1.0]  # the backoff between passes, doubling from 1 s


def test_a_json_rpc_429_in_a_200_is_a_rate_limit_too():
    body = json.dumps({"jsonrpc": "2.0", "error": {"code": 429, "message": "Too Many Requests"}})
    replies = iter([(200, body.encode()), ok("0x3")])
    assert client("ONLY", transport=lambda *a: next(replies)).call("eth_chainId", []) == "0x3"


def test_when_every_endpoint_fails_the_error_names_them_and_hides_their_urls():
    def transport(url, body, timeout):
        raise ConnectionResetError(f"reset by {url}")

    with pytest.raises(chain.RpcUnavailable) as failure:
        client("PRIMARY", "SECONDARY", transport=transport).call("eth_blockNumber", [])
    assert failure.value.rule == chain.RULE_TRANSPORT
    assert [name for name, _ in failure.value.failures] == ["PRIMARY", "SECONDARY"] * 2
    assert "secret-key" not in str(failure.value)
    assert "<PRIMARY>" in str(failure.value)


def test_a_403_says_it_may_be_the_missing_user_agent():
    with pytest.raises(chain.RpcUnavailable) as failure:
        client("ONLY", transport=lambda *a: (403, b"forbidden"), attempts=1).call("eth_chainId", [])
    assert "User-Agent" in str(failure.value)


def test_a_revert_is_an_answer_and_does_not_fail_over():
    used = []

    def transport(url, body, timeout):
        used.append(url)
        return 200, json.dumps({"jsonrpc": "2.0", "id": 1,
                                "error": {"code": 3, "message": "execution reverted"}}).encode()

    with pytest.raises(chain.RpcError):
        client("PRIMARY", "SECONDARY", transport=transport).call("eth_call", [])
    assert len(used) == 1


def test_requests_are_paced():
    sleeps: list[float] = []
    clock = iter([0.0, 0.1, 0.5])  # first stamp; second call's check; second stamp
    rpc = chain.RpcClient([chain.Endpoint("ONLY", "https://only.invalid")], timeout_s=1,
                          attempts=1, backoff_s=1, min_interval_s=0.5,
                          transport=lambda *a: ok("0x1"), sleep=sleeps.append,
                          monotonic=lambda: next(clock))
    rpc.call("eth_blockNumber", [])
    rpc.call("eth_blockNumber", [])
    assert sleeps == [pytest.approx(0.4)]


def test_the_real_transport_sends_a_user_agent():
    seen = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self):
            seen["ua"] = self.headers.get("User-Agent")
            self.rfile.read(int(self.headers["Content-Length"]))
            body = json.dumps({"jsonrpc": "2.0", "id": 1, "result": "0x1263"}).encode()
            self.send_response(200)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def log_message(self, *args):
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.handle_request, daemon=True).start()
    try:
        rpc = chain.RpcClient([chain.Endpoint("LOCAL", f"http://127.0.0.1:{server.server_port}")],
                              timeout_s=5, attempts=1, backoff_s=0, min_interval_s=0,
                              transport=chain.urllib_transport("openfund-chain/1.3"))
        assert rpc.call("eth_chainId", []) == "0x1263"
    finally:
        server.server_close()
    assert seen["ua"] == "openfund-chain/1.3"
