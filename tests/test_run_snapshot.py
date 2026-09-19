"""Unit 1.6's live read, `run/snapshot.py`, run offline end to end.

The whole path `main()` takes — pin, read the chain, GeckoTerminal, quotes,
judge, build — runs here with no network: `urlopen` is replaced by a failure.
The three transports answer in the shapes the real sources were recorded in:
- the chain speaks the real `aggregate3` ABI, as 1.3's fake does;
- GeckoTerminal's entries follow the batch response captured 2026-09-19 UTC;
- each quote is probe 0.3's recorded TSLA body, re-addressed to the token asked.

This is not 1.9's replay of a recorded run; it proves the composition, not the
data. The universe is the real pinned one, narrowed to three stocks with feeds
and one held stock without.
"""

from __future__ import annotations

import dataclasses
import json
import urllib.request
from types import MappingProxyType

import pytest

from fund.adapters import bankr_quote, chain_4663, gecko, http
from fund.core import universe, valuation
from fund.core.types import ChainAddress, FetchStatus, Instant
from fund.run import snapshot as run

U = universe.load()
CHAIN = 4663
SAT = 1_789_776_000                                    # Sat 2026-09-19 00:00:00Z
HOUR, DAY = 3_600, 86_400
BLOCK_TIME, BLOCK_NUMBER, BLOCK_HASH = SAT + 2 * HOUR, 66_716_733, "0x" + "8b" * 32
U64 = (1 << 64) - 1
WALLET = ChainAddress(CHAIN, "0x93faecde3c88a713e1edddf417c02c326889a3da")


def listed(symbol: str):
    """Test setup only: the product never resolves an asset by ticker."""
    return next(a for a, r in U.records.items() if r.symbol == symbol and a.chain_id == CHAIN)


NVDA, AMZN, CLSK, CRM = (listed(s) for s in ("NVDA", "AMZN", "CLSK", "CRM"))
SMALL = dataclasses.replace(
    U, records=MappingProxyType({a: U.records[a] for a in (NVDA, AMZN, CLSK, CRM)}),
    feeds=MappingProxyType({a: U.feeds[a] for a in (NVDA, AMZN, CLSK, U.cash_leg, U.gas_asset)}))

#: A round at 20:00Z on every weekday for 40 days, the newest Fri 09-18: past
#: the configured 30-day window, and none in a weekend's closed span.
WEEKDAYS = sorted(t for t in (SAT - 4 * HOUR - d * DAY for d in range(40))
                  if (t // DAY + 3) % 7 < 5)


def w(value: int) -> str:
    return format(value % (1 << 256), "064x")


def word(value: int) -> bytes:
    return bytes.fromhex(w(value))


class RecordedChain:
    """Answers every read `run/snapshot.py` makes, and records the block each
    one addressed."""

    def __init__(self):
        self.feeds = {  # proxy -> [(answer, updatedAt)], round 1 first
            U.feeds[NVDA].proxy.address: [(22_244_729_849 - 100 * i, t) for i, t in enumerate(WEEKDAYS)],
            U.feeds[AMZN].proxy.address: [(25_386_300_000 - 100 * i, t) for i, t in enumerate(WEEKDAYS)],
            U.feeds[CLSK].proxy.address: [(1_436_560_000 - 100 * i, t) for i, t in enumerate(WEEKDAYS)],
            U.feeds[U.cash_leg].proxy.address: [(99_995_090, SAT + HOUR)],
            U.feeds[U.gas_asset].proxy.address: [(261_753_000_000, SAT + HOUR)],
        }
        self.balances = {U.cash_leg.address: 78_742, CRM.address: 10**18}
        self.native = 460_162_486_507_929
        self.beacon = U.issuer_beacon.address
        self.block_params: list = []

    def transport(self, url, body, timeout):
        request = json.loads(body)
        method, params = request["method"], request["params"]
        if method == "eth_chainId":
            return self.ok(hex(CHAIN))
        if method == "eth_getBlockByNumber":
            return self.ok({"number": hex(BLOCK_NUMBER), "timestamp": hex(BLOCK_TIME),
                            "hash": BLOCK_HASH})
        if method == "eth_call":
            self.block_params.append(params[1])
            return self.ok(self.aggregate(params[0]["data"]))
        if method == "eth_getBalance":
            self.block_params.append(params[1])
            return self.ok(hex(self.native))
        if method == "eth_getStorageAt":
            self.block_params.append(params[2])
            return self.ok("0x" + "0" * 24 + self.beacon[2:])
        raise AssertionError(method)

    @staticmethod
    def ok(result):
        return 200, json.dumps({"jsonrpc": "2.0", "id": 1, "result": result}).encode()

    def aggregate(self, data: str) -> str:
        b = bytes.fromhex(data[10:])
        rd = lambda o: int.from_bytes(b[o:o + 32], "big")  # noqa: E731
        array, calls = rd(0), []
        for i in range(rd(array)):
            t = array + 32 + rd(array + 32 + 32 * i)
            payload = t + rd(t + 64)
            calls.append(("0x" + b[t + 12:t + 32].hex(), b[payload + 32:payload + 32 + rd(payload)]))
        results = [self.answer(target, call) for target, call in calls]
        tuples = [w(1 if ok else 0) + w(0x40) + w(len(d)) + (d + b"\0" * (-len(d) % 32)).hex()
                  for ok, d in results]
        offsets, position = [], 32 * len(results)
        for t in tuples:
            offsets.append(position)
            position += len(t) // 2
        return "0x" + w(0x20) + w(len(results)) + "".join(w(o) for o in offsets) + "".join(tuples)

    def answer(self, target: str, data: bytes) -> tuple[bool, bytes]:
        selector = data[:4].hex()
        rounds = self.feeds.get(target)
        if selector == chain_4663.SEL_LATEST_ROUND and rounds:
            return True, self.round(len(rounds), *rounds[-1])
        if selector == chain_4663.SEL_GET_ROUND and rounds:
            n = int.from_bytes(data[4:36], "big") & U64
            return (True, self.round(n, *rounds[n - 1])) if 1 <= n <= len(rounds) else (False, b"")
        if selector == chain_4663.SEL_BALANCE_OF:
            return True, word(self.balances.get(target, 0))
        return False, b""

    @staticmethod
    def round(n: int, answer: int, updated: int) -> bytes:
        rid = (1 << 64) | n
        return b"".join(word(v) for v in (rid, answer, updated, updated, rid))


#: GeckoTerminal's price and 24h volume per token: NVDA agrees, AMZN diverges
#: past the limit, CLSK trades below the $1M line.
GECKO = {NVDA.address: ("222.5312563313", "57356973.5948744"),
         AMZN.address: ("265.0947710163", "2210353.13452393"),
         CLSK.address: ("13.9896", "242.12")}


def recorded_gecko(url, body, timeout):
    asked = url.rsplit("/", 1)[1].split(",")
    data = [{"id": f"robinhood_{a}", "type": "token",
             "attributes": {"address": a, "decimals": 18, "price_usd": GECKO[a][0],
                            "volume_usd": {"h24": GECKO[a][1]}},
             "relationships": {"top_pools": {"data": [{"id": "robinhood_0xpool", "type": "pool"}]}}}
            for a in asked if a in GECKO]
    return 200, json.dumps({"data": data}).encode(), {"cf-cache-status": "MISS"}


IMPACT = {NVDA.address: 4, AMZN.address: 17, CLSK.address: 976}


def recorded_quote(url, body, timeout):
    """Probe 0.3's TSLA body, with the tokens, amount and impact of this request."""
    asked = json.loads(body)
    impact = IMPACT[asked["toToken"]]
    reply = {"from": {"chain": "robinhood", "token": asked["fromToken"], "amount": asked["amount"],
                      "formattedAmount": asked["amount"], "symbol": "USDG", "decimals": 6},
             "to": {"chain": "robinhood", "token": asked["toToken"], "amount": "67948238487403141",
                    "formattedAmount": "0.06794823848740314", "decimals": 18},
             "minBuyAmount": "0.064550826563032984", "feeBps": 0, "feeWaivedForEcosystemToken": False,
             "slippageBps": 500, "priceImpactBps": impact, "swapImpactBps": impact,
             "maxPriceImpactBps": 1500, "sellTokenPriceUsd": 1.0022236982588135,
             "buyTokenPriceUsd": 369.2925339180603, "quoteId": "c9f64995-fa7c-469b-a880-4796cfa739d9"}
    return 200, json.dumps(reply).encode(), {}


def ticking(start_s: int):
    now = [start_s * 1000]

    def clock() -> Instant:
        now[0] += 250
        return Instant(now[0])
    return clock


def sources(chain: RecordedChain, clock) -> run.Sources:
    rpc = chain_4663.RpcClient([http.Endpoint("RPC_4663_MAINNET", "https://rpc.invalid/key")],
                               timeout_s=2, attempts=1, backoff_s=0, min_interval_s=0,
                               transport=chain.transport)
    corroborator = gecko.Gecko(
        http.HttpClient([http.Endpoint(gecko.ENDPOINT_NAME, "https://api.geckoterminal.com/api/v2")],
                        timeout_s=2, attempts=1, backoff_s=0, min_interval_s=0,
                        transport=recorded_gecko),
        network="robinhood", batch_size=30, clock=clock)
    venue = bankr_quote.Settings.load().adapter(lambda name: "test-key", transport=recorded_quote,
                                                clock=clock)
    venue.client.min_interval_s = 0
    return run.Sources(rpc=rpc, corroborator=corroborator, venue=venue)


THRESHOLDS = json.loads((run.CONFIG / "thresholds.json").read_text())


def build(chain: RecordedChain | None = None) -> run.Built:
    chain = chain or RecordedChain()
    clock = ticking(BLOCK_TIME + 30)
    return run.read_and_build(sources(chain, clock), settings=chain_4663.Settings.load(), u=SMALL,
                              rule=valuation.DivergenceRule.from_thresholds(THRESHOLDS),
                              limits=bankr_quote.Limits.from_thresholds(THRESHOLDS),
                              wallet=WALLET, clock=clock)


@pytest.fixture(autouse=True)
def no_network(monkeypatch):
    def refuse(*args, **kwargs):
        raise AssertionError("the offline build reached for the network")
    monkeypatch.setattr(urllib.request, "urlopen", refuse)


def entry(built, symbol):
    return next(e for e in built.snapshot.document["assets"] if e["asset"]["symbol"] == symbol)


def test_the_live_path_builds_a_whole_snapshot_with_no_network():
    chain = RecordedChain()
    built = build(chain)
    doc = built.snapshot.document
    assert doc["block"]["number"] == BLOCK_NUMBER and doc["block"]["closed_sessions"] == ["us_equities_24/5"]
    assert all(p == {"blockHash": BLOCK_HASH} for p in chain.block_params)  # every read at the pin
    assert [(s, st) for s, st, _ in doc["summary"]["assets"]] == [
        ("AMZN", "tradeable"), ("CLSK", "below_corroborator_line"), ("NVDA", "tradeable")]
    assert doc["summary"]["findings"] == [["AMZN", "closed-session divergence", "-423.69"]]
    clsk = entry(built, "CLSK")
    assert clsk["quote"]["tradeable"]["verdict"] is False and "[impact]" in clsk["quote"]["tradeable"]["reason"]
    nvda = entry(built, "NVDA")
    assert nvda["quote"]["sell_amount"] == "25.001227"  # $25 at USDG's own mark
    assert nvda["timeline"]["columns"] == ["close_of", "updated_at", "price_usd"]  # the configured series
    assert nvda["timeline"]["rounds"] == 22 and nvda["timeline"]["coverage"]["verdict"] is True
    assert "8 days fell in the closed session" in nvda["timeline"]["coverage"]["reason"]
    assert nvda["mark"]["fresh"]["verdict"] is True and "of open session" in nvda["mark"]["fresh"]["reason"]


def test_a_held_stock_without_a_feed_is_carried_without_a_value():
    holdings = {h["asset"]["symbol"]: h for h in build().snapshot.document["holdings"]}
    assert set(holdings) == {"CRM", "ETH", "USDG"}
    assert holdings["CRM"]["value_usd"] is None and holdings["CRM"]["status"]["value"] == "unmarkable"
    assert holdings["USDG"]["value_usd"] == "0.0787381337678"


def test_the_same_recorded_responses_build_the_same_bytes_twice():
    first, second = build(), build()
    assert first.snapshot.sha256 == second.snapshot.sha256 and first.snapshot.body == second.snapshot.body


def test_a_cash_leg_with_no_mark_asks_for_no_quotes_and_says_why():
    chain = RecordedChain()
    del chain.feeds[U.feeds[U.cash_leg].proxy.address]  # the USDG feed reverts
    built = build(chain)
    assert built.offchain.quote_size is None
    assert all(q.status is FetchStatus.REFUSED and "not asked" in q.detail
               for q in built.offchain.quotes.values())
    nvda = entry(built, "NVDA")
    assert nvda["status"]["value"] == "not_tradeable" and nvda["status"]["verdict"] is None


def test_a_beacon_that_disagrees_stops_the_build():
    chain = RecordedChain()
    chain.beacon = "0x" + "66" * 20
    with pytest.raises(universe.BeaconDisagreement):
        build(chain)


def test_with_daily_closes_the_live_path_takes_one_close_a_day_and_none_at_the_weekend():
    chain = RecordedChain()
    clock = ticking(BLOCK_TIME + 30)
    settings = dataclasses.replace(chain_4663.Settings.load(), sampling="daily_close",
                                   window_s=7 * DAY, max_rounds=5000)
    built = run.read_and_build(sources(chain, clock), settings=settings, u=SMALL,
                               rule=valuation.DivergenceRule.from_thresholds(THRESHOLDS),
                               limits=bankr_quote.Limits.from_thresholds(THRESHOLDS),
                               wallet=WALLET, clock=clock)
    t = entry(built, "NVDA")["timeline"]
    assert t["columns"] == ["close_of", "updated_at", "price_usd"]
    assert [row[0] for row in t["points"]] == ["2026-09-14", "2026-09-15", "2026-09-16",
                                               "2026-09-17", "2026-09-18"]
    assert "2 days fell in the closed session and have no close" in t["coverage"]["reason"]
    assert entry(built, "NVDA")["status"]["value"] == "tradeable"
    assert "One close a day over 7 days" in built.snapshot.document["rules"]["timeline"]
