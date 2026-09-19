"""Unit 1.10, the address selftest, offline: over the pinned table and a chain that
answers as it says, every address passes; each plausible wrong value, a swapped
token or feed, a counterfeit, USDG's documented 18, a changed delegate, fails its row."""

from __future__ import annotations

import dataclasses
import json
from types import MappingProxyType

import pytest

from fund.adapters import chain_4663 as chain
from fund.core import universe
from fund.core.types import AssetId, ChainAddress
from fund.run import selftest
from test_chain_4663 import decode_calls, encode_results, word

U = universe.load()
SETTINGS = dataclasses.replace(chain.Settings.load(), min_interval_s=0)
CHAIN, BLOCK_HASH = 4663, "0x" + "5e" * 32
WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"
DELEGATE = "0xd6cedde84be40893d153be9d467cd6ad37875b28"
IMPLEMENTATION = "0x" + "1a" * 20
FAKE_GAMESTOP = AssetId(CHAIN, "0x7e86381a763f0ecca2bdf27c54eac403ddd48123")  # probe 0.8's counterfeit


def listed(symbol: str) -> AssetId:
    """Test setup only: the product never resolves an asset by ticker."""
    return next(a for a, r in U.records.items() if r.symbol == symbol)


def abi_string(text: str) -> bytes:
    raw = text.encode()
    return word(32) + word(len(raw)) + raw + b"\0" * (-len(raw) % 32)


class Chain:
    """4663 as the pinned table says it is, until a test changes one thing."""

    def __init__(self):
        self.tokens = {a.address: (r.symbol, r.decimals, U.issuer_beacon.address) for a, r in U.records.items()}
        self.tokens[U.cash_leg.address] = ("USDG", 6, None)
        self.tokens[FAKE_GAMESTOP.address] = ("GME", 18, None)  # decimals and symbol like the real one
        self.feeds = {f.proxy.address: (f.name, f.decimals) for f in U.feeds.values()}
        self.code = {WALLET: "0xef0100" + DELEGATE[2:], IMPLEMENTATION: "0x6080"}
        self.multicall3, self.chain_id = SETTINGS.multicall3, CHAIN

    def answer(self, target: str, data: bytes) -> tuple[bool, bytes]:
        selector = data[:4].hex()
        if target in self.tokens and selector == chain.SEL_DECIMALS:
            return True, word(self.tokens[target][1])
        if target in self.tokens and selector == selftest.SEL_SYMBOL:
            return True, abi_string(self.tokens[target][0])
        if target in self.feeds and selector == chain.SEL_DECIMALS:
            return True, word(self.feeds[target][1])
        if target in self.feeds and selector == selftest.SEL_DESCRIPTION:
            return True, abi_string(self.feeds[target][0])
        return False, b""

    def transport(self, url, body, timeout):
        request = json.loads(body)
        method, params = request["method"], request["params"]

        def ok(result):
            return 200, json.dumps({"jsonrpc": "2.0", "id": request["id"], "result": result}).encode()

        def reverted():
            return 200, json.dumps({"jsonrpc": "2.0", "id": request["id"],
                                    "error": {"code": 3, "message": "execution reverted"}}).encode()

        if method == "eth_chainId":
            return ok(hex(self.chain_id))
        if method == "eth_getBlockByNumber":
            return ok({"number": hex(66_827_900), "timestamp": hex(1_789_795_000), "hash": BLOCK_HASH})
        if method == "eth_getStorageAt":
            beacon = self.tokens.get(params[0], (None, None, None))[2]
            return ok("0x" + (beacon[2:].rjust(64, "0") if beacon else "0" * 64))
        if method == "eth_getCode":
            return ok(self.code.get(params[0], "0x"))
        if method == "eth_call":
            to, data = params[0]["to"], params[0]["data"]
            if to == self.multicall3 and data.startswith("0x" + chain.SEL_AGGREGATE3):
                return ok(encode_results([self.answer(t, d) for t, d in decode_calls(data)]))
            if to == self.multicall3 and data == "0x" + selftest.SEL_GET_CHAIN_ID:
                return ok("0x" + word(getattr(self, "multicall_chain_id", self.chain_id)).hex())
            if to == U.issuer_beacon.address and data == "0x" + selftest.SEL_IMPLEMENTATION:
                return ok("0x" + word(int(IMPLEMENTATION, 16)).hex())
            return reverted()
        raise AssertionError(method)


def attest(u=U, fake=None, *, settings=SETTINGS, delegate=DELEGATE) -> selftest.Attestation:
    fake = fake or Chain()
    rpc = chain.RpcClient([chain.Endpoint("RPC_4663_MAINNET", "https://rpc.invalid/key")],
                          timeout_s=2, attempts=1, backoff_s=0, min_interval_s=0,
                          transport=fake.transport)
    return selftest.attest(u, rpc=rpc, settings=settings, wallet=WALLET, delegate=delegate)


def failing(result: selftest.Attestation) -> dict[str, list[str]]:
    """role -> the checks that did not pass."""
    return {row.role: [n for n, c in row.checks if not c.passes] for row in result.failed}


def test_the_pinned_table_passes_over_a_chain_that_agrees_with_it():
    result = attest()
    assert result.passes and len(result.rows) == 194 + 1 + 37 + 3  # tokens, USDG, feeds, the rest


def retarget(u: universe.Universe, asset: AssetId, address: str) -> universe.Universe:
    """The table with one record's address replaced: a plausible copy-paste error."""
    moved = AssetId(CHAIN, address)
    record = U.records[asset]
    record = dataclasses.replace(record, deployments=tuple(
        dataclasses.replace(d, contract=ChainAddress(CHAIN, address)) for d in record.deployments))
    records = {a: r for a, r in u.records.items() if a != asset} | {moved: record}
    feeds = {(moved if a == asset else a): f for a, f in u.feeds.items()}
    return dataclasses.replace(u, records=MappingProxyType(records), feeds=MappingProxyType(feeds))


def test_a_genuine_token_at_another_tokens_address_fails_only_at_symbol():
    # AAPL's record pointed at NVDA's contract: 18 decimals, the issuer's beacon.
    aapl, nvda = listed("AAPL"), listed("NVDA")
    fake = Chain()
    fake.tokens[aapl.address] = fake.tokens[nvda.address]  # the chain at the address answers as NVDA
    assert failing(attest(fake=fake)) == {"registry token AAPL": ["symbol"]}


def test_a_counterfeit_at_a_tokens_address_fails_only_at_the_beacon():
    # The GameStop impersonator answers decimals() and symbol() exactly like GME.
    u = retarget(U, listed("GME"), FAKE_GAMESTOP.address)
    result = attest(u)
    assert failing(result) == {"registry token GME": ["beacon"]}
    assert result.failed[0].line().endswith("(passed: decimals, symbol)")  # what it got past, named


def test_a_feed_pinned_to_another_assets_proxy_fails_at_its_description():
    aapl, msft = listed("AAPL"), listed("MSFT")
    feeds = dict(U.feeds) | {aapl: U.feeds[msft]}
    fake = Chain()
    fake.feeds[U.feeds[msft].proxy.address] = ("RHMSFT / USD", 8)  # as MSFT's feed describes itself
    u = dataclasses.replace(U, feeds=MappingProxyType(feeds))
    assert failing(attest(u, fake)) == {"feed for AAPL": ["asset"]}


def test_usdg_at_the_documented_but_wrong_18_decimals_fails():
    u = dataclasses.replace(U, cash_decimals=18)  # F0.3.1: two documented sources said 18
    assert failing(attest(u)) == {"cash leg USDG": ["decimals"]}


def test_a_feed_whose_decimals_disagree_with_the_directory_fails():
    fake = Chain()
    proxy = U.feeds[listed("TSLA")].proxy.address
    fake.feeds[proxy] = (fake.feeds[proxy][0], 18)
    assert failing(attest(fake=fake)) == {"feed for TSLA": ["decimals"]}


@pytest.mark.parametrize("code, wrong", [
    ("0xef0100" + "44" * 20, "delegated to 0x4444"),   # a changed delegation
    ("0x", "no code"),                                # an undelegated account: a wrong wallet
])
def test_a_wallet_not_delegated_to_the_pinned_delegate_fails(code, wrong):
    fake = Chain()
    fake.code[WALLET] = code
    result = attest(fake=fake)
    assert failing(result) == {"execution wallet": ["delegation"]}
    assert wrong in result.failed[0].checks[0][1].reason


def test_a_beacon_pin_at_another_address_fails_the_beacon_and_every_token():
    u = dataclasses.replace(U, issuer_beacon=ChainAddress(CHAIN, listed("AAPL").address))
    problems = failing(attest(u))
    assert problems.pop("issuer beacon") == ["implementation"]
    assert set(problems) == {f"registry token {r.symbol}" for r in U.records.values()}


def test_a_wrong_multicall3_leaves_nothing_attested():
    settings = dataclasses.replace(SETTINGS, multicall3=U.issuer_beacon.address)
    result = attest(settings=settings)
    assert not result.passes and failing(result)["Multicall3"] == ["chain"]
    assert all(c.value is None for row in result.rows if row.role.startswith("registry token")
               for name, c in row.checks if name in ("decimals", "symbol"))


def test_multicall3_answering_for_another_chain_fails():
    fake = Chain()
    fake.multicall_chain_id = 46630  # the testnet's
    assert failing(attest(fake=fake)) == {"Multicall3": ["chain"]}


def test_a_beacon_whose_implementation_holds_no_code_fails():
    fake = Chain()
    del fake.code[IMPLEMENTATION]
    assert failing(attest(fake=fake)) == {"issuer beacon": ["implementation"]}


def test_an_unreadable_chain_is_undetermined_and_fails():
    fake = Chain()
    real = fake.transport

    def dead_after_the_pin(url, body, timeout):
        if b"eth_chainId" in body or b"eth_getBlockByNumber" in body:
            return real(url, body, timeout)
        raise ConnectionRefusedError("[Errno 111] Connection refused")

    fake.transport = dead_after_the_pin
    result = attest(fake=fake)
    assert not result.passes and len(result.failed) == len(result.rows)
    assert all(c.value is None for row in result.rows for _, c in row.checks)


def test_a_feed_pinned_to_an_address_the_table_does_not_list_fails():
    # Found by the counterfeit test's first draft: such a feed was named "ETH".
    orphan = AssetId(CHAIN, "0x" + "77" * 20)
    u = dataclasses.replace(U, feeds=MappingProxyType(dict(U.feeds) | {orphan: U.feeds[listed("AAPL")]}))
    fake = Chain()
    assert failing(attest(u, fake))[f"feed for {orphan.address}"] == ["asset"]


def test_a_description_names_its_asset_in_each_way_the_chain_writes_it():
    assert selftest.names_asset("Robinhood AAPL / USD", "AAPL")
    assert selftest.names_asset("Robinhood DELL-USD", "DELL")
    assert selftest.names_asset("RHAMD / USD", "AMD")
    assert selftest.names_asset("USDG / USD", "USDG")
    assert not selftest.names_asset("RHINTC / USD", "AMD")
    assert not selftest.names_asset("Robinhood AMZN / USD", "AMD")
