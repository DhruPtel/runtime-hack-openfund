"""The address table, attested against the chain at one pinned block. Unit 1.10.

    PYTHONPATH=src python3 -m fund.run.selftest --live      (make selftest)

Every address in config is read at one block. Each check is one a plausible
wrong value fails, not only an absurd one; `aero-stock-lp`'s `selftest --live`
is the pattern (research/aero-stock-lp.md).

- **Each registry token** (194 at the pinned version), three checks:
  - `decimals()` equals its record's;
  - `symbol()` equals its record's `tokenSymbol`, which catches two genuine
    tokens' addresses swapped;
  - its EIP-1967 beacon slot resolves to the issuer's beacon. This catches a
    counterfeit, which answers `decimals()` and `symbol()` exactly like the real
    token (F0.3.6, F0.8.3).
- **Each feed proxy** (37: 35 stocks, USDG and ETH), two checks:
  - `decimals()` equals the pinned directory's;
  - its own `description()` names the asset the map pins it to, which catches
    two proxies swapped. The chain writes the name three ways, 'Robinhood AAPL
    / USD', 'Robinhood DELL-USD' and, for nine feeds, 'RHAMD / USD', so a
    description names the asset by its registry symbol, or 'RH' and that
    symbol. It is not compared with the pinned directory's name, which for
    those nine says 'Robinhood AMD / USD': the two disagree on correct values
    (measured at the first live run).
- **The cash leg, USDG:** `decimals()` is its pinned 6, where the plausible
  wrong value is the 18 two documented sources gave (F0.3.1); and `symbol()`.
- **The issuer's beacon:** `implementation()` names an address that holds code.
- **Multicall3:** `getChainId()` is the configured chain, by a direct call.
- **The execution wallet:** its code is the EIP-7702 designator for the delegate
  pinned in `mandate.json` (F0.10.3).

Membership in the pinned registry is identity (0.8 decision), and is the table
itself. Whether the pin matches its bytes is 1.2's `load()`. `uiMultiplier()`
and the name marker are not attested, because they carry no identity weight
(0.8 decision).

A value that could not be read is undetermined, and undetermined fails: a
selftest that could not see an address has not attested it.
"""

from __future__ import annotations

import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Mapping, Sequence

from fund import config
from fund.adapters import cache, chain_4663, http
from fund.core import universe
from fund.core.types import BlockRef, Check, Instant
from fund.credentials import Role

ROOT = Path(__file__).resolve().parents[3]
MANDATE = ROOT / "config" / "mandate.json"

SEL_SYMBOL = "95d89b41"           # symbol()
SEL_DESCRIPTION = "7284e416"      # description()
SEL_IMPLEMENTATION = "5c60da1b"   # implementation(), IBeacon
SEL_GET_CHAIN_ID = "3408e470"     # getChainId(), Multicall3
DESIGNATOR = "0xef0100"           # EIP-7702: the code of a delegated account is this, then the delegate


@dataclass(frozen=True)
class Row:
    """One address and what the chain said about it."""

    address: str
    role: str
    checks: tuple[tuple[str, Check], ...]

    @property
    def passes(self) -> bool:
        return all(check.passes for _, check in self.checks)

    def line(self) -> str:
        failed = [(name, c) for name, c in self.checks if not c.passes]
        if not failed:
            return f"PASS  {self.address}  {self.role}: " + "; ".join(c.reason or n for n, c in self.checks)
        passed = [name for name, c in self.checks if c.passes]
        return f"FAIL  {self.address}  {self.role}: " + "; ".join(
            f"{name} {'undetermined' if c.value is None else 'wrong'}: {c.reason}" for name, c in failed
        ) + (f" (passed: {', '.join(passed)})" if passed else "")


@dataclass(frozen=True)
class Attestation:
    block: BlockRef
    rows: tuple[Row, ...]

    @property
    def passes(self) -> bool:
        return all(row.passes for row in self.rows)

    @property
    def failed(self) -> list[Row]:
        return [row for row in self.rows if not row.passes]


# --- reading ------------------------------------------------------------------------------------

def decode_string(data: bytes) -> str | None:
    """An ABI `string` return, or a `bytes32` one, which some tokens use."""
    try:
        if len(data) >= 64:
            offset = int.from_bytes(data[0:32], "big")
            length = int.from_bytes(data[offset:offset + 32], "big")
            raw = data[offset + 32:offset + 32 + length]
            if len(raw) == length:
                return raw.decode("utf-8")
        if len(data) == 32:
            return data.rstrip(b"\0").decode("utf-8")
    except (UnicodeDecodeError, ValueError):
        pass
    return None


def _read_strings(read: chain_4663.ChainReader, targets: Mapping[str, str], selector: str
                  ) -> dict[str, tuple[str | None, str]]:
    """key -> (the string, or None, and why none), one multicall per chunk."""
    keys = list(targets)
    try:
        results = read.multicall([(targets[k], bytes.fromhex(selector)) for k in keys])
    except chain_4663.ChainError as error:
        return {k: (None, f"not read: {error}") for k in keys}
    out = {}
    for k, (ok, data) in zip(keys, results):
        text = decode_string(data) if ok else None
        out[k] = (text, "" if text is not None else ("reverted" if not ok else "not a string"))
    return out


def _call(rpc: chain_4663.RpcClient, method: str, params: list) -> tuple[object | None, str]:
    try:
        return rpc.call(method, params), ""
    except chain_4663.ChainError as error:
        return None, f"not read: {error}"


def _address_word(result: object) -> str | None:
    if not isinstance(result, str) or len(result) != 66:
        return None
    return "0x" + result[-40:]


# --- judging --------------------------------------------------------------------------------------

def _decimals_check(observation, expected: int) -> Check:
    if not observation.ok:
        return Check(None, f"decimals not read: {observation.status.value}: {observation.detail}")
    got = observation.value.raw
    return Check(got == expected, f"decimals {got}" + ("" if got == expected else f", expected {expected}"))


def _equal(name: str, got: str | None, expected: str, why_none: str) -> Check:
    if got is None:
        return Check(None, f"{name} not read: {why_none}")
    return Check(got == expected, f"{name} {got!r}" + ("" if got == expected else f", expected {expected!r}"))


def feed_base(description: str) -> str:
    """The asset a feed describes: the part before the quote currency, less the
    'Robinhood ' prefix, from 'Robinhood AAPL / USD', 'Robinhood DELL-USD' or
    'RHAMD / USD'."""
    text = description.removeprefix("Robinhood ").strip()
    for sep in (" / ", "-"):
        if sep in text:
            return text.split(sep)[0].strip()
    return text


def names_asset(description: str, symbol: str) -> bool:
    """Does the description name this asset: its symbol, or 'RH' and its symbol?"""
    return feed_base(description) in (symbol, "RH" + symbol)


def attest(u: universe.Universe, *, rpc: chain_4663.RpcClient, settings: chain_4663.Settings,
           wallet: str, delegate: str, clock: Callable[[], Instant] = chain_4663.wall_clock
           ) -> Attestation:
    """Read every address in the table at one pinned block, and judge each."""
    block = chain_4663.pin_block(rpc, settings.chain_id, settings.block_tag)
    read = settings.reader(rpc, block, clock)
    at = {"blockHash": block.hash}

    stocks = sorted(a for a in u.records if a.chain_id == block.chain_id)
    carried = sorted(a for a in u.carried if a.chain_id == block.chain_id)
    tokens = stocks + carried + [u.cash_leg]
    expected_symbol = ({a: u.records[a].symbol for a in stocks} | {a: u.carried[a].symbol for a in carried}
                       | {u.cash_leg: "USDG"})
    expected_decimals = ({a: u.records[a].decimals for a in stocks}
                         | {a: u.carried[a].decimals for a in carried} | {u.cash_leg: u.cash_decimals})
    decimals = read.decimals(tokens)
    symbols = _read_strings(read, {a.address: a.address for a in tokens}, SEL_SYMBOL)
    beacons = read.beacon_slots(stocks + carried)
    feeds = dict(u.feeds)
    feed_decimals = read.feed_decimals(feeds)
    descriptions = _read_strings(read, {a.address: f.proxy.address for a, f in feeds.items()},
                                 SEL_DESCRIPTION)

    rows: list[Row] = []
    for a in tokens:
        role = ("cash leg" if a == u.cash_leg else "carried token" if a in u.carried
                else "registry token") + f" {expected_symbol[a]}"
        checks = [("decimals", _decimals_check(decimals[a], expected_decimals[a])),
                  ("symbol", _equal("symbol", *symbols[a.address][:1], expected_symbol[a],
                                    symbols[a.address][1]))]
        if a != u.cash_leg:
            slot = beacons[a]
            if not slot.ok:
                beacon = Check(None, f"beacon slot not read: {slot.status.value}: {slot.detail}")
            else:
                beacon = Check(slot.value == u.issuer_beacon,
                               "beacon is the issuer's" if slot.value == u.issuer_beacon
                               else f"beacon {slot.value.address}, not the issuer's "
                                    f"{u.issuer_beacon.address}")
            checks.append(("beacon", beacon))
        rows.append(Row(a.address, role, tuple(checks)))

    for a, feed in sorted(feeds.items(), key=lambda x: x[1].name):
        name = ("USDG" if a == u.cash_leg else "ETH" if a == u.gas_asset
                else u.records[a].symbol if a in u.records else None)
        text, why = descriptions[a.address]
        if name is None:
            names = Check(False, f"the map pins this feed to {a.address}, which the table does not list")
            name = a.address
        elif text is None:
            names = Check(None, f"description not read: {why}")
        else:
            names = Check(names_asset(text, name), f"describes {text!r}" if names_asset(text, name)
                          else f"describes {text!r}, which is not {name}")
        rows.append(Row(feed.proxy.address, f"feed for {name}",
                        (("decimals", _decimals_check(feed_decimals[a], feed.decimals)),
                         ("asset", names))))

    impl, why = _call(rpc, "eth_call", [{"to": u.issuer_beacon.address, "data": "0x" + SEL_IMPLEMENTATION}, at])
    impl_address = _address_word(impl)
    if impl_address is None:
        beacon_check = Check(None if impl is None else False,
                             f"implementation() {why or 'answered no address'}")
    else:
        code, why = _call(rpc, "eth_getCode", [impl_address, at])
        beacon_check = (Check(None, f"implementation's code not read: {why}") if code is None else
                        Check(len(code) > 2, f"implementation() is {impl_address}, "
                              + ("which holds code" if len(code) > 2 else "which holds no code")))
    rows.append(Row(u.issuer_beacon.address, "issuer beacon", (("implementation", beacon_check),)))

    chain_id, why = _call(rpc, "eth_call", [{"to": settings.multicall3, "data": "0x" + SEL_GET_CHAIN_ID}, at])
    if not isinstance(chain_id, str) or len(chain_id) != 66:
        mc = Check(None if chain_id is None else False, f"getChainId() {why or 'answered nothing usable'}")
    else:
        got = int(chain_id, 16)
        mc = Check(got == settings.chain_id, f"getChainId() is {got}"
                   + ("" if got == settings.chain_id else f", expected {settings.chain_id}"))
    rows.append(Row(settings.multicall3, "Multicall3", (("chain", mc),)))

    code, why = _call(rpc, "eth_getCode", [wallet, at])
    expected_code = DESIGNATOR + delegate.lower().removeprefix("0x")
    if code is None:
        delegation = Check(None, f"code not read: {why}")
    elif code == expected_code:
        delegation = Check(True, f"EIP-7702 delegated to {delegate}")
    elif isinstance(code, str) and code.startswith(DESIGNATOR):
        delegation = Check(False, f"delegated to 0x{code[len(DESIGNATOR):]}, not the pinned {delegate}")
    else:
        delegation = Check(False, f"code {str(code)[:20]}…, not a delegation to {delegate}"
                           if code not in ("0x", "") else f"no code: not delegated to {delegate}")
    rows.append(Row(wallet.lower(), "execution wallet", (("delegation", delegation),)))
    return Attestation(block, tuple(rows))


# --- the live run ---------------------------------------------------------------------------------

def main(argv: Sequence[str]) -> int:
    if list(argv) != ["--live"]:
        print("usage: python -m fund.run.selftest --live")
        return 2
    cfg = config.load(Role.ANALYST, require=False)
    settings = chain_4663.Settings.load()
    u = universe.load()
    mandate = json.loads(MANDATE.read_text())
    counter = cache.Recorder("chain", {n: cfg.secret(n) for n in settings.endpoints})
    rpc = settings.client(cfg.secret, counter.transport(http.urllib_transport(settings.user_agent)))
    started = time.monotonic()
    result = attest(u, rpc=rpc, settings=settings, wallet=mandate["execution_wallet"],
                    delegate=mandate["execution_wallet_delegate_4663"])
    elapsed = time.monotonic() - started
    for row in result.rows:
        print(row.line())
    statuses: dict[str, int] = {}
    for e in counter.exchanges:
        key = str(e.get("status", "no answer" if "raised" not in e else e["raised"]["type"]))
        statuses[key] = statuses.get(key, 0) + 1
    print(f"\n== {len(result.rows)} addresses at block {result.block.number}: "
          f"{len(result.rows) - len(result.failed)} pass, {len(result.failed)} fail; {elapsed:.1f}s")
    print(f"   {len(counter.exchanges)} requests to the RPC, by answer: {statuses}; paced at "
          f"{settings.min_interval_s * 1000:.0f} ms")
    for row in result.failed:
        print(f"   FAILED: {row.role} at {row.address}")
    return 0 if result.passes else 1


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
