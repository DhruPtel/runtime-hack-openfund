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


# --- the RPC client, over the shared transport ------------------------------------

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


def test_a_backend_missing_the_pinned_state_is_retried():
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message":
                       "historical state 61928c68 is not available"}}).encode()
    replies = iter([(200, body), ok("0x4")])
    sleeps: list[float] = []
    rpc = client("ONLY", transport=lambda *a: next(replies), sleeps=sleeps)
    assert rpc.call("eth_call", []) == "0x4"
    assert sleeps == [1.0]


def test_header_not_found_is_an_answer_and_is_not_retried():
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "error": {"code": -32000, "message": "header not found"}}).encode()
    used = []

    def transport(*args):
        used.append(1)
        return 200, body

    with pytest.raises(chain.RpcError, match="header not found"):
        client("ONLY", transport=transport).call("eth_call", [])
    assert len(used) == 1

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


def test_a_reply_with_neither_result_nor_error_is_an_error_not_a_crash():
    rpc = client("ONLY", transport=lambda *a: (200, b'{"jsonrpc": "2.0", "id": 1}'))
    with pytest.raises(chain.RpcError, match="neither result nor error"):
        rpc.call("eth_chainId", [])


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


# --- a fake chain that answers the way 4663 does ------------------------------------
#
# It decodes the adapter's real aggregate3 calldata and encodes aggregate3's
# real return layout, so the ABI code is exercised, not bypassed. Every read's
# block parameter is recorded, to prove each one addresses the pinned hash.

from fund.core import universe
from fund.core.types import (
    AssetId, BlockRef, ChainAddress, Check, FeedRef, FetchStatus, Fixed, Instant, Observation,
    Series, Source,
)

CHAIN = 4663
T = 1_790_000_000                 # the pinned block's time, in seconds
N = 5_000_000                     # the pinned block's number
H = "0x" + "ab" * 32              # the pinned block's hash
HOUR, DAY = 3600, 86400
U64 = (1 << 64) - 1
PHASE = 1                         # so every round id is above 2**64, far past 2**53
HOLDER = "0x93faecde3c88a713e1edddf417c02c326889a3da"
MULTICALL3 = "0xca11bde05977b3631167028862be2a173976ca11"


def w(value: int) -> str:
    return format(value % (1 << 256), "064x")


def word(value: int) -> bytes:
    return bytes.fromhex(w(value))


def round_bytes(n: int, answer: int, updated: int) -> bytes:
    rid = (PHASE << 64) | n
    return b"".join(word(v) for v in (rid, answer, updated, updated, rid))


def decode_calls(data: str) -> list[tuple[str, bytes]]:
    assert data.startswith("0x" + chain.SEL_AGGREGATE3)
    b = bytes.fromhex(data[10:])
    rd = lambda o: int.from_bytes(b[o:o + 32], "big")  # noqa: E731
    array, out = rd(0), []
    for i in range(rd(array)):
        t = array + 32 + rd(array + 32 + 32 * i)
        assert rd(t + 32) == 1, "every call allows failure"
        payload = t + rd(t + 64)
        out.append(("0x" + b[t + 12:t + 32].hex(), b[payload + 32:payload + 32 + rd(payload)]))
    return out


def encode_results(results: list[tuple[bool, bytes]]) -> str:
    tuples = [w(1 if ok_ else 0) + w(0x40) + w(len(d)) + (d + b"\0" * (-len(d) % 32)).hex()
              for ok_, d in results]
    offsets, position = [], 32 * len(results)
    for t in tuples:
        offsets.append(position)
        position += len(t) // 2
    return "0x" + w(0x20) + w(len(results)) + "".join(w(o) for o in offsets) + "".join(tuples)


class FakeChain:
    def __init__(self):
        self.chain_id = CHAIN
        self.feeds: dict[str, list[tuple[int, int]]] = {}  # proxy -> [(answer, updatedAt)], round 1 first
        self.decimals: dict[str, int] = {}
        self.balances: dict[tuple[str, str], int] = {}
        self.native: dict[str, int] = {}
        self.slots: dict[str, str] = {}
        self.block_params: list = []
        self.calls = 0
        self.fail_after: int | None = None

    def transport(self, url, body, timeout):
        request = json.loads(body)
        method, params = request["method"], request["params"]
        self.calls += 1
        if self.fail_after is not None and self.calls > self.fail_after:
            raise ConnectionRefusedError("[Errno 111] Connection refused")
        if method == "eth_chainId":
            return ok(hex(self.chain_id))
        if method == "eth_getBlockByNumber":
            return ok({"number": hex(N), "timestamp": hex(T), "hash": H})
        if method == "eth_call":
            self.block_params.append(params[1])
            return ok(encode_results([self.answer(t, d) for t, d in decode_calls(params[0]["data"])]))
        if method == "eth_getBalance":
            self.block_params.append(params[1])
            return ok(hex(self.native[params[0]]))
        if method == "eth_getStorageAt":
            self.block_params.append(params[2])
            return ok(self.slots[params[0]])
        raise AssertionError(method)

    def answer(self, target: str, data: bytes) -> tuple[bool, bytes]:
        selector = data[:4].hex()
        if selector == chain.SEL_LATEST_ROUND and target in self.feeds:
            rounds = self.feeds[target]
            return True, round_bytes(len(rounds), *rounds[-1])
        if selector == chain.SEL_GET_ROUND and target in self.feeds:
            rid = int.from_bytes(data[4:36], "big")
            rounds, n = self.feeds[target], rid & U64
            if rid >> 64 != PHASE or not 1 <= n <= len(rounds):
                return False, b""
            return True, round_bytes(n, *rounds[n - 1])
        if selector == chain.SEL_DECIMALS and target in self.decimals:
            return True, word(self.decimals[target])
        if selector == chain.SEL_BALANCE_OF and target in self.decimals:
            return True, word(self.balances.get((target, "0x" + data[16:36].hex()), 0))
        return False, b""  # a revert


def rpc_for(fake: FakeChain) -> chain.RpcClient:
    return chain.RpcClient([chain.Endpoint("RPC_4663_MAINNET", "https://rpc.invalid/key")],
                           timeout_s=2, attempts=1, backoff_s=0, min_interval_s=0,
                           transport=fake.transport)


def dead_rpc() -> chain.RpcClient:
    def transport(url, body, timeout):
        raise ConnectionRefusedError("[Errno 111] Connection refused")
    return chain.RpcClient([chain.Endpoint("RPC_4663_MAINNET", "https://rpc.invalid/key")],
                           timeout_s=2, attempts=1, backoff_s=0, min_interval_s=0,
                           transport=transport)


BLOCK = BlockRef(CHAIN, N, Instant.from_seconds(T), H)
FETCHED = Instant.from_seconds(T + 5)


def reader(rpc, block=BLOCK) -> chain.ChainReader:
    return chain.ChainReader(rpc, block, multicall3=MULTICALL3, chunk=50,
                             clock=lambda: FETCHED)


def addr(n: int) -> str:
    return "0x" + format(n, "040x")


def feed(proxy: str, name: str = "TEST / USD") -> FeedRef:
    return FeedRef(proxy=ChainAddress(CHAIN, proxy), decimals=8, heartbeat=Fixed(DAY, 0, "s"),
                   deviation_threshold=Fixed.parse("0.5", "%"), market_hours="us_equities_24/5",
                   name=name)


def hourly(days: float, newest_age_s: int, price: int = 25_000_000_000) -> list[tuple[int, int]]:
    """Rounds every hour for `days`, the newest `newest_age_s` before the block."""
    count = int(days * 24)
    return [(price + i, T - newest_age_s - (count - 1 - i) * HOUR) for i in range(count)]


MARGIN = 3600


# --- the pinned block ----------------------------------------------------------------

def test_pin_block_refuses_a_node_on_another_chain():
    fake = FakeChain()
    fake.chain_id = 46630  # the testnet URL in the mainnet slot
    with pytest.raises(chain.ChainError) as refused:
        chain.pin_block(rpc_for(fake), CHAIN)
    assert refused.value.rule == chain.RULE_BLOCK_PIN


def test_every_read_addresses_the_pinned_block_by_hash():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(1, 600)
    fake.decimals[addr(2)] = 6
    fake.native[HOLDER] = 10 ** 15
    fake.slots[addr(2)] = "0x" + "0" * 24 + "e10b6f6b275de231345c20d14ab812db62151b00"
    r = reader(rpc_for(fake))
    stock, cash, eth = AssetId(CHAIN, addr(9)), AssetId(CHAIN, addr(2)), AssetId.native(CHAIN)
    r.latest_rounds({stock: feed(addr(1))})
    r.decimals([cash])
    r.balances(ChainAddress(CHAIN, HOLDER), {cash: 6, eth: 18})
    r.beacon_slots([cash])
    r.price_series(stock, feed(addr(1)), window_s=7 * DAY, max_rounds=100, scale_break_ratio=10_000)
    assert fake.block_params and all(p == {"blockHash": H} for p in fake.block_params)


def test_a_reader_refuses_a_block_pinned_without_its_hash():
    with pytest.raises(ValueError, match="by hash"):
        reader(rpc_for(FakeChain()), BlockRef(CHAIN, N, Instant.from_seconds(T)))


# --- one block per bundle --------------------------------------------------------------

def test_a_mixed_block_bundle_is_refused_by_name():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(1, 600)
    fake.feeds[addr(3)] = hourly(1, 600)
    aapl, gme = AssetId(CHAIN, addr(11)), AssetId(CHAIN, addr(13))
    here = reader(rpc_for(fake)).latest_rounds({aapl: feed(addr(1))})[aapl]
    later = BlockRef(CHAIN, N + 1, Instant.from_seconds(T + 1), "0x" + "cd" * 32)
    elsewhere = reader(rpc_for(fake), later).latest_rounds({gme: feed(addr(3))})[gme]

    chain.require_one_block([here], BLOCK)  # one block: accepted
    with pytest.raises(chain.MixedBlocks) as refused:
        chain.require_one_block([here, elsewhere], BLOCK)
    assert refused.value.rule == chain.RULE_BLOCK_PIN
    assert refused.value.offenders == ((f"chainlink-feed:{addr(3)}", N + 1),)
    assert str(N + 1) in str(refused.value) and addr(1) not in str(refused.value)


def test_an_unpinned_observation_in_a_chain_bundle_is_refused_too():
    offchain = Observation(value=None, source=Source("geckoterminal", "/pools/x"), source_time=None,
                           fetch_time=FETCHED, block=None, status=FetchStatus.UNREACHABLE,
                           detail="not read")
    with pytest.raises(chain.MixedBlocks, match="no block"):
        chain.require_one_block([offchain], BLOCK)


# --- feeds -----------------------------------------------------------------------------

def test_latest_rounds_reads_several_feeds_with_exact_round_ids():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(1, 600)
    fake.feeds[addr(3)] = hourly(2, 7200, price=2_300_000_000)
    aapl, gme = AssetId(CHAIN, addr(11)), AssetId(CHAIN, addr(13))
    readings = reader(rpc_for(fake)).latest_rounds({aapl: feed(addr(1)), gme: feed(addr(3))})

    a = readings[aapl]
    assert a.ok and a.block == BLOCK
    assert a.value.raw == 25_000_000_000 + 23 and a.value.decimals == 8 and a.value.base == aapl
    assert a.source_ref == str((PHASE << 64) | 24)  # exact, and past 2**53
    assert int(a.source_ref) > 2 ** 53
    assert a.source_time == Instant.from_seconds(T - 600)
    assert "not applied" in a.detail and "F0.4.4" in a.detail
    assert readings[gme].source_ref == str((PHASE << 64) | 48)


def test_a_reverting_feed_is_one_refused_reading_not_a_failed_bundle():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(1, 600)
    good, gone = AssetId(CHAIN, addr(11)), AssetId(CHAIN, addr(12))
    readings = reader(rpc_for(fake)).latest_rounds({good: feed(addr(1)), gone: feed(addr(2))})
    assert readings[good].ok
    assert readings[gone].status is FetchStatus.REFUSED and "reverted" in readings[gone].detail


def test_a_round_that_fails_chainlinks_rules_is_refused_and_says_which():
    fake = FakeChain()
    fake.feeds[addr(1)] = [(0, T - 600)]
    fake.feeds[addr(2)] = [(-5, T - 600)]
    fake.feeds[addr(3)] = [(100, 0)]
    a, b, c = (AssetId(CHAIN, addr(n)) for n in (11, 12, 13))
    readings = reader(rpc_for(fake)).latest_rounds({a: feed(addr(1)), b: feed(addr(2)),
                                                    c: feed(addr(3))})
    assert "non-positive answer 0" in readings[a].detail
    assert "non-positive answer -5" in readings[b].detail  # int256, decoded signed
    assert "not complete" in readings[c].detail
    assert all(r.status is FetchStatus.REFUSED and r.value is None for r in readings.values())


# --- freshness: heartbeat plus margin, at the block's time ------------------------------

def reading_aged(age_s: int) -> Observation:
    fake = FakeChain()
    fake.feeds[addr(1)] = [(100, T - age_s)]
    asset = AssetId(CHAIN, addr(11))
    return reader(rpc_for(fake)).latest_rounds({asset: feed(addr(1))})[asset]


@pytest.mark.parametrize("age_s, fresh", [
    (600, True),
    (DAY + MARGIN, True),        # at the limit: still fresh
    (DAY + MARGIN + 1, False),   # one second past it: stale
    (3 * DAY, False),
])
def test_freshness_is_the_feeds_heartbeat_plus_the_margin(age_s, fresh):
    verdict = chain.freshness(reading_aged(age_s), feed(addr(1)), BLOCK.timestamp, MARGIN)
    assert verdict.value is fresh
    assert f"age {age_s}s" in verdict.reason and "heartbeat 86400s" in verdict.reason


def test_freshness_reads_the_heartbeat_from_the_feed_not_a_constant():
    hourly_feed = FeedRef(proxy=ChainAddress(CHAIN, addr(1)), decimals=8,
                          heartbeat=Fixed(HOUR, 0, "s"), deviation_threshold=Fixed.parse("0.5", "%"),
                          market_hours=None, name="ETH / USD")
    verdict = chain.freshness(reading_aged(3 * HOUR), hourly_feed, BLOCK.timestamp, MARGIN)
    assert verdict.value is False


def test_an_unreachable_feed_is_undetermined_not_stale_and_not_zero():
    asset = AssetId(CHAIN, addr(11))
    reading = reader(dead_rpc()).latest_rounds({asset: feed(addr(1))})[asset]
    assert reading.status is FetchStatus.UNREACHABLE and reading.value is None
    assert "RPC_4663_MAINNET" in reading.detail and "rpc.invalid" not in reading.detail
    verdict = chain.freshness(reading, feed(addr(1)), BLOCK.timestamp, MARGIN)
    assert verdict.value is None and verdict.value is not False
    assert not verdict.passes and "unreachable" in verdict.reason


# --- the price series ----------------------------------------------------------------------

def series(fake, *, days=7, cap=1000, ratio=10_000, rpc=None) -> Series:
    return reader(rpc or rpc_for(fake)).price_series(
        AssetId(CHAIN, addr(11)), feed(addr(1)), window_s=days * DAY, max_rounds=cap,
        scale_break_ratio=ratio)


def test_a_week_of_rounds_covers_the_window_and_only_the_newest_is_judged():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(10, 600)
    s = series(fake)
    assert s.status is FetchStatus.OK and s.coverage.value is True
    assert s.window_start == Instant.from_seconds(T - 7 * DAY)
    assert s.oldest.source_time <= s.window_start < s.points[1].source_time  # one anchor round
    assert len(s.points) == 7 * 24 + 1
    assert all(p.block == BLOCK for p in s.points)
    # The oldest point is a week old, far past heartbeat + margin, and that is fine:
    oldest_alone = chain.freshness(s.oldest, feed(addr(1)), BLOCK.timestamp, MARGIN)
    assert oldest_alone.value is False
    assert chain.series_freshness(s, feed(addr(1)), BLOCK.timestamp, MARGIN).value is True


def test_a_series_whose_newest_point_is_old_is_stale():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(10, 2 * DAY)
    assert chain.series_freshness(series(fake), feed(addr(1)), BLOCK.timestamp, MARGIN).value is False


def test_a_feed_younger_than_the_window_gives_a_series_visibly_short():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(2, 600)
    s = series(fake)
    assert s.status is FetchStatus.OK and len(s.points) == 48
    assert s.coverage.value is False and "round 1" in s.coverage.reason
    assert s.oldest.source_time > s.window_start


def test_the_round_cap_gives_a_series_visibly_short():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(10, 600)
    s = series(fake, cap=30)
    assert len(s.points) == 30
    assert s.coverage.value is False and "round cap 30" in s.coverage.reason


def test_a_scale_break_stops_the_series_and_leaves_the_old_units_out():
    fake = FakeChain()
    rounds = hourly(10, 600)
    # The first 100 rounds report 1e8 too large, as 32 of 37 real feeds did at launch.
    fake.feeds[addr(1)] = [(a * 10 ** 8, t) for a, t in rounds[:100]] + rounds[100:]
    s = series(fake)
    assert s.coverage.value is False and "scale break" in s.coverage.reason
    assert len(s.points) == len(rounds) - 100
    assert max(p.value.raw for p in s.points) < 10 ** 12


def test_a_read_that_fails_partway_keeps_its_points_and_is_undetermined():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(10, 600)
    fake.fail_after = 2  # latestRoundData and one batch, then the RPC goes away
    s = series(fake)
    assert s.status is FetchStatus.OK and len(s.points) == 51
    assert s.coverage.value is None and "read failed" in s.coverage.reason


def test_an_unreachable_rpc_gives_no_series_and_an_undetermined_verdict():
    s = series(None, rpc=dead_rpc())
    assert s.status is FetchStatus.UNREACHABLE and s.points == ()
    assert s.coverage.value is None
    verdict = chain.series_freshness(s, feed(addr(1)), BLOCK.timestamp, MARGIN)
    assert verdict.value is None and "unreachable" in verdict.reason


def test_a_round_dated_after_its_successor_stops_the_walk():
    fake = FakeChain()
    rounds = hourly(10, 600)
    rounds[-3] = (rounds[-3][0], rounds[-1][1] + 60)
    fake.feeds[addr(1)] = rounds
    s = series(fake)
    assert s.coverage.value is None and "order in doubt" in s.coverage.reason
    assert len(s.points) == 2


# --- tokens, balances, the beacon --------------------------------------------------------

def test_a_feeds_own_decimals_are_read_from_its_proxy():
    fake = FakeChain()
    fake.decimals[addr(1)] = 8
    asset = AssetId(CHAIN, addr(11))
    got = reader(rpc_for(fake)).feed_decimals({asset: feed(addr(1))})[asset]
    assert got.value == Fixed(8, 0, "decimals")
    assert got.source == Source("chainlink-feed", addr(1)) and got.block == BLOCK

def test_decimals_and_balances_are_read_at_the_pinned_block():
    fake = FakeChain()
    usdg, stock, eth = (AssetId(CHAIN, addr(2)), AssetId(CHAIN, addr(4)), AssetId.native(CHAIN))
    fake.decimals.update({addr(2): 6, addr(4): 18})
    fake.balances[(addr(2), HOLDER)] = 1_234_567
    fake.native[HOLDER] = 3 * 10 ** 15
    r = reader(rpc_for(fake))
    assert r.decimals([usdg])[usdg].value == Fixed(6, 0, "decimals")
    held = r.balances(ChainAddress(CHAIN, HOLDER), {usdg: 6, stock: 18, eth: 18})
    assert held[usdg].value.raw == 1_234_567 and held[usdg].value.decimals == 6
    assert held[stock].value.raw == 0
    assert held[eth].value.raw == 3 * 10 ** 15 and held[eth].source.system == "native-balance"
    assert all(o.block == BLOCK for o in held.values())


def test_an_unreachable_balance_is_not_a_zero_balance():
    usdg = AssetId(CHAIN, addr(2))
    held = reader(dead_rpc()).balances(ChainAddress(CHAIN, HOLDER), {usdg: 6})
    assert held[usdg].status is FetchStatus.UNREACHABLE and held[usdg].value is None


def test_the_beacon_read_feeds_the_cross_check_in_universe():
    u = universe.load()
    gme = next(a for a in u.feeds if u.records[a].symbol == "GME")
    beacon = u.issuer_beacon.address
    fake = FakeChain()
    fake.slots[gme.address] = "0x" + "0" * 24 + beacon[2:]
    reads = reader(rpc_for(fake)).beacon_slots([gme])
    assert reads[gme].value == ChainAddress(CHAIN, beacon)
    assert u.cross_check_beacons(reads)[gme].value is True

    unread = reader(dead_rpc()).beacon_slots([gme])
    assert unread[gme].status is FetchStatus.UNREACHABLE
    assert u.cross_check_beacons(unread)[gme].value is None  # undetermined, never False


def test_a_malformed_slot_word_is_a_refused_read():
    fake = FakeChain()
    fake.slots[addr(2)] = "0x1234"
    reads = reader(rpc_for(fake)).beacon_slots([AssetId(CHAIN, addr(2))])
    assert reads[AssetId(CHAIN, addr(2))].status is FetchStatus.REFUSED


def test_a_multicall_reply_with_the_wrong_count_is_refused_not_trusted():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(1, 600)
    real = fake.transport

    def short(url, body, timeout):
        status, raw = real(url, body, timeout)
        reply = json.loads(raw)
        if isinstance(reply.get("result"), str) and len(reply["result"]) > 200:
            reply["result"] = encode_results([])
        return status, json.dumps(reply).encode()

    fake_rpc = chain.RpcClient([chain.Endpoint("X", "https://x.invalid")], timeout_s=2, attempts=1,
                               backoff_s=0, min_interval_s=0, transport=short)
    asset = AssetId(CHAIN, addr(11))
    got = reader(fake_rpc).latest_rounds({asset: feed(addr(1))})[asset]
    assert got.status is FetchStatus.REFUSED and "0 results for 1 calls" in got.detail


def test_settings_come_from_chain_json_and_the_margin_from_thresholds(tmp_path):
    # Values other than the configured ones, so a number written into the code
    # instead of read from these files cannot pass.
    chain_doc = json.loads(chain.CHAIN_CONFIG.read_text())
    chain_doc["series_window_seconds"] = 7 * DAY
    thresholds = json.loads(chain.THRESHOLDS.read_text())
    thresholds["feed_staleness_margin_seconds"] = 7200
    (tmp_path / "chain.json").write_text(json.dumps(chain_doc))
    (tmp_path / "thresholds.json").write_text(json.dumps(thresholds))
    s = chain.Settings.load(chain_path=tmp_path / "chain.json",
                            thresholds_path=tmp_path / "thresholds.json")
    assert s.chain_id == CHAIN and s.endpoints == ("RPC_4663_MAINNET",)
    assert s.staleness_margin_s == 7200 and s.window_s == 7 * DAY
    rpc = s.client(lambda name: f"https://{name}.invalid/key")
    assert [e.name for e in rpc.endpoints] == ["RPC_4663_MAINNET"]
    assert "invalid/key" not in repr(rpc.endpoints)


def test_a_proxy_answering_a_different_round_than_asked_is_not_believed():
    fake = FakeChain()
    fake.feeds[addr(1)] = hourly(10, 600)
    real_answer = fake.answer

    def always_latest(target, data):
        if data[:4].hex() == chain.SEL_GET_ROUND:
            return real_answer(target, bytes.fromhex(chain.SEL_LATEST_ROUND))
        return real_answer(target, data)

    fake.answer = always_latest
    s = series(fake)
    assert s.coverage.value is None and "returned round" in s.coverage.reason
    assert len(s.points) == 1


# --- market sessions, inferred from rounds ----------------------------------------------------

MONDAY = 1_789_948_800            # Mon 2026-09-21 00:00:00Z
SAT_0005, SUN_2355 = 5 * DAY + 300, 7 * DAY - 300


def weekday_rounds(weeks: int, *, skip=lambda week, day, hour: False, extra=()) -> list[int]:
    """Hourly rounds Monday 00:00Z to Friday 23:00Z, for `weeks` weeks from MONDAY."""
    times = [MONDAY + w * 7 * DAY + d * DAY + h * HOUR
             for w in range(weeks) for d in range(5) for h in range(24) if not skip(w, d, h)]
    return sorted(times + list(extra))


def test_a_closure_may_run_over_monday_midnight():
    c = chain.WeeklyClosure("x", 6 * DAY, 7 * DAY + HOUR)  # Sun 00:00Z to Mon 01:00Z
    assert c.contains(MONDAY + 30 * 60) and c.contains(MONDAY - 1) and not c.contains(MONDAY + HOUR)
    assert c.closed_ms(MONDAY * 1000, (MONDAY + 2 * HOUR) * 1000) == HOUR * 1000


def test_the_quiet_span_is_pooled_over_every_week_and_shrunk_inward():
    rounds = {"A": weekday_rounds(6), "B": weekday_rounds(6)}
    ev = chain.infer_closure("us_equities_24/5", rounds, guard_s=60, grid_s=300, min_weekends=4)
    assert ev.refusal is None and len(ev.weekends) == 5
    assert ev.quiet == (4 * DAY + 23 * HOUR, 7 * DAY)          # Fri 23:00Z, then Mon 00:00Z
    assert (ev.closure.start_s, ev.closure.end_s) == (4 * DAY + 23 * HOUR + 300, 7 * DAY - 300)


def test_one_weekend_is_not_a_pattern():
    ev = chain.infer_closure("us_equities_24/5", {"A": weekday_rounds(2)}, guard_s=60, grid_s=300,
                             min_weekends=4)
    assert ev.closure is None and "1 complete weeks" in ev.refusal


def test_one_round_in_one_week_is_enough_to_move_the_span():
    stray = MONDAY + 3 * 7 * DAY + 5 * DAY + 10 * HOUR  # Saturday 10:00Z, in week 4 only
    ev = chain.infer_closure("x", {"A": weekday_rounds(6, extra=[stray])}, guard_s=60, grid_s=300,
                             min_weekends=4)
    assert not ev.closure.contains(stray)


def test_a_missing_weekday_does_not_move_the_span_and_shows_as_an_unexplained_gap():
    holiday = weekday_rounds(6, skip=lambda w, d, h: (w, d) == (2, 4))  # week 3's Friday is silent
    ev = chain.infer_closure("x", {"A": holiday}, guard_s=60, grid_s=300, min_weekends=4)
    assert (ev.closure.start_s, ev.closure.end_s) == (4 * DAY + 23 * HOUR + 300, 7 * DAY - 300)
    start, end, open_s = ev.open_gaps[0]
    assert start == MONDAY + 2 * 7 * DAY + 3 * DAY + 23 * HOUR and open_s >= DAY


def test_replaying_the_rule_the_weekend_is_expected_and_the_holiday_is_stale():
    # Week 3: Thursday goes quiet after 20:00Z, as real feeds do, and Friday is a
    # holiday. A silent Friday alone is 24h05m of open session, inside the limit.
    times = weekday_rounds(6, skip=lambda w, d, h: w == 2 and (d == 4 or (d == 3 and h > 20)))
    closure = chain.WeeklyClosure("x", 4 * DAY + 23 * HOUR + 300, 7 * DAY - 300)
    limit = DAY + MARGIN
    with_span = chain.stale_spans(times, times[-1], limit, closure)
    thursday_2000 = MONDAY + 2 * 7 * DAY + 3 * DAY + 20 * HOUR
    assert len(with_span) == 1                                  # the holiday, and nothing else
    assert with_span[0][0] == thursday_2000 + limit + 1          # the first second past the limit
    assert with_span[0][1] == MONDAY + 3 * 7 * DAY              # until Monday's first round
    without = chain.stale_spans(times, times[-1], limit, None)
    assert len(without) == 5  # every one of the five weekends, the holiday merged into its own


# --- freshness in open-session time (DECISION 2026-09-18) ---------------------------------------

EQUITY_CLOSED = {"us_equities_24/5": chain.WeeklyClosure("us_equities_24/5", SAT_0005, SUN_2355)}
FRI, SAT, SUN = MONDAY - 3 * DAY, MONDAY - 2 * DAY, MONDAY - DAY  # the weekend before MONDAY


def reading_at(epoch_s: int) -> Observation:
    fake = FakeChain()
    fake.feeds[addr(1)] = [(100, epoch_s)]
    asset = AssetId(CHAIN, addr(11))
    return reader(rpc_for(fake)).latest_rounds({asset: feed(addr(1))})[asset]


def judged(round_s: int, as_of_s: int, sessions=EQUITY_CLOSED) -> Check:
    return chain.freshness(reading_at(round_s), feed(addr(1)), Instant.from_seconds(as_of_s),
                           MARGIN, sessions)


def test_a_weekend_gap_is_expected_and_the_last_round_stands():
    verdict = judged(FRI + 20 * HOUR, SUN + 23 * HOUR)  # 51 h by the wall clock
    assert verdict.value is True and "of open session" in verdict.reason
    assert judged(FRI + 20 * HOUR, SUN + 23 * HOUR, sessions={}).value is False  # the rule it replaces


# Friday 23:00Z to Saturday 00:05Z is 1h05m of open session; the other 23h55m of
# the 25 h allowance runs from Sunday 23:55Z, so the limit falls at Monday 23:50Z.
@pytest.mark.parametrize("as_of_s, fresh", [
    (MONDAY + 23 * HOUR + 50 * 60 - 1, True),
    (MONDAY + 23 * HOUR + 50 * 60, True),        # exactly heartbeat + margin of open session
    (MONDAY + 23 * HOUR + 50 * 60 + 1, False),   # one second past it
])
def test_open_session_time_resumes_at_the_end_of_the_span(as_of_s, fresh):
    assert judged(FRI + 23 * HOUR, as_of_s).value is fresh


def test_a_gap_in_an_open_session_is_stale_and_names_the_holiday_it_may_be():
    verdict = judged(MONDAY + HOUR, MONDAY + DAY + 3 * HOUR)  # Monday 01:00Z to Tuesday 03:00Z
    assert verdict.value is False and "holiday" in verdict.reason


def test_a_friday_holiday_is_stale_through_the_weekend():
    # Thursday 20:00Z, then nothing: 28h05m of open session by Saturday 00:05Z.
    thursday = FRI - DAY + 20 * HOUR
    assert judged(thursday, SAT + 12 * HOUR).value is False
    assert judged(thursday, SUN + 23 * HOUR).value is False


def test_a_round_inside_the_closed_span_contradicts_it_and_is_undetermined():
    verdict = judged(SAT + 12 * HOUR, SAT + 13 * HOUR)
    assert verdict.value is None and "contradicts the inference" in verdict.reason


def test_a_series_whose_history_crosses_the_span_reopens_the_question():
    fake = FakeChain()
    fake.feeds[addr(1)] = [(100, SAT + 12 * HOUR), (101, MONDAY + HOUR)]
    s = reader(rpc_for(fake)).price_series(AssetId(CHAIN, addr(11)), feed(addr(1)),
                                           window_s=7 * DAY, max_rounds=100, scale_break_ratio=10_000)
    verdict = chain.series_freshness(s, feed(addr(1)), Instant.from_seconds(MONDAY + 2 * HOUR),
                                     MARGIN, EQUITY_CLOSED)
    assert verdict.value is None and "1 of the series' 2 rounds" in verdict.reason


def test_a_feed_whose_schedule_has_no_span_counts_every_second():
    crypto = FeedRef(proxy=ChainAddress(CHAIN, addr(1)), decimals=8, heartbeat=Fixed(DAY, 0, "s"),
                     deviation_threshold=Fixed.parse("0.5", "%"), market_hours="Crypto",
                     name="ETH / USD")
    verdict = chain.freshness(reading_at(FRI + 20 * HOUR), crypto,
                              Instant.from_seconds(SUN + 23 * HOUR), MARGIN, EQUITY_CLOSED)
    assert verdict.value is False and "of open session" not in verdict.reason


def test_settings_load_the_closed_span_and_the_rule_that_uses_it():
    s = chain.Settings.load()
    span = s.sessions["us_equities_24/5"]
    assert (span.start_s, span.end_s) == (SAT_0005, SUN_2355)
    assert "Crypto" not in s.sessions


def test_a_missing_trie_node_is_missing_state_too_and_is_retried():
    # The wording 1.7's snapshot met on SPCX's series walk, which was not retried.
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "error": {"code": -32000, "message":
                       "[0xcd846d85d33ab63d464d9399be8cde4a4e2a6e4732e8a427bd357395098e0907] layer stale\n"
                       "missing trie node b6546d9229d5e7b8ae6a6f485d68c46484547fbfc138dc8b322e1673c840fd51 "
                       "(path 0d) layer stale"}}).encode()
    replies = iter([(200, body), ok("0x5")])
    sleeps: list[float] = []
    assert client("ONLY", transport=lambda *a: next(replies), sleeps=sleeps).call("eth_call", []) == "0x5"
    assert sleeps == [1.0]


# --- daily closes (DECISION 2026-09-18, measured before it is adopted) ------------------------

def two_weeks_of_weekdays(silent=(MONDAY - 5 * DAY,)) -> list[tuple[int, int]]:
    """Rounds at 00, 06, 12 and 18Z on weekdays from Mon 2026-09-07 up to the
    block (Mon 09-21 14:13Z), none on the days in `silent`."""
    out, day = [], MONDAY - 14 * DAY
    while day <= T:
        if chain.week_position(day) < 5 * DAY and day not in silent:
            out += [(25_000_000_000 + len(out), day + h * HOUR) for h in (0, 6, 12, 18)
                    if day + h * HOUR <= T]
        day += DAY
    return out


def closes(fake, closure=EQUITY_CLOSED["us_equities_24/5"], days=10):
    return reader(rpc_for(fake)).daily_closes(
        AssetId(CHAIN, addr(11)), feed(addr(1)), days=days, cut_s=20 * HOUR, closure=closure,
        max_rounds=5000, scale_break_ratio=10_000)


def test_daily_closes_skip_the_weekend_and_a_silent_day_and_end_with_the_latest_round():
    fake = FakeChain()
    fake.feeds[addr(1)] = two_weeks_of_weekdays()  # Wed 09-16 is silent, like a holiday
    s = closes(fake)
    stamp = lambda i: time.strftime("%a %m-%d %H:%M", time.gmtime(i.epoch_ms // 1000))  # noqa: E731
    assert [stamp(p.source_time) for p in s.points] == [
        "Fri 09-11 18:00", "Mon 09-14 18:00", "Tue 09-15 18:00", "Thu 09-17 18:00",
        "Fri 09-18 18:00", "Mon 09-21 12:00"]
    assert [stamp(x) for x in s.samples[:-1]] == [
        "Fri 09-11 20:00", "Mon 09-14 20:00", "Tue 09-15 20:00", "Thu 09-17 20:00", "Fri 09-18 20:00"]
    assert s.samples[-1] == BLOCK.timestamp  # the latest round, sampled at the block
    assert s.coverage.value is True and "5 daily closes at 20:00Z over 10 days" in s.coverage.reason
    assert "4 days fell in the closed session" in s.coverage.reason
    assert "1 had no new round since the previous close" in s.coverage.reason
    assert chain.series_freshness(s, feed(addr(1)), BLOCK.timestamp, MARGIN, EQUITY_CLOSED).value is True


def test_daily_closes_keep_the_walks_stops_a_feed_younger_than_the_window_is_short():
    fake = FakeChain()
    fake.feeds[addr(1)] = [r for r in two_weeks_of_weekdays() if r[1] >= MONDAY - 6 * DAY]
    s = closes(fake)
    assert s.coverage.value is False and "round 1" in s.coverage.reason


def test_daily_closes_over_an_unreachable_rpc_are_no_series():
    s = reader(dead_rpc()).daily_closes(AssetId(CHAIN, addr(11)), feed(addr(1)), days=10,
                                        cut_s=20 * HOUR, closure=None, max_rounds=5000,
                                        scale_break_ratio=10_000)
    assert s.status is FetchStatus.UNREACHABLE and s.points == () and s.coverage.value is None


def test_settings_carry_the_sampling_and_refuse_an_unknown_one(tmp_path):
    s = chain.Settings.load()
    assert s.sampling in chain.SAMPLINGS and s.cut_s == 20 * HOUR
    doc = json.loads(chain.CHAIN_CONFIG.read_text())
    doc["series_sampling"] = "hourly"
    path = tmp_path / "chain.json"
    path.write_text(json.dumps(doc))
    with pytest.raises(ValueError, match="unknown series sampling"):
        chain.Settings.load(chain_path=path)
