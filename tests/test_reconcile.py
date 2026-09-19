"""Unit 5.3: what the chain says about a swap. H: this decides what is booked.

The receipt is real: probe 0.10's swap on 4663, recorded in `tests/data/`, which sold
0.00003 ETH for 0.078742 USDG as a gas-sponsored 4337 operation inside a 7702
transaction sent by a bundler. The balances are the probe's measured ones, because the
node no longer serves state at that block.
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import pytest

from fund.adapters.chain_4663 import RpcError
from fund.core.types import AssetId, ChainAddress, OrderState
from fund.treasurer import reconcile

CHAIN = 4663
RECORDED = json.loads((Path(__file__).parent / "data" / "swap_receipt_0_10.json").read_text())
WALLET = ChainAddress(CHAIN, "0x93faecde3c88a713e1edddf417c02c326889a3da")
ETH = AssetId.native(CHAIN)
USDG = AssetId(CHAIN, "0x5fc5360d0400a0fd4f2af552add042d716f1d168")
BLOCK = int(RECORDED["receipt"]["blockNumber"], 16)
#: The wallet's native balance either side of that block, from probe 0.10's own
#: measurement: it sold 0.00003 ETH and paid no gas.
BEFORE, SOLD = 490162486507929, 30_000_000_000_000


class FakeRpc:
    """The node, answering from the recording."""

    def __init__(self, *, head=BLOCK + 100, receipt=RECORDED["receipt"], balances=True):
        self.head, self.receipt, self.balances, self.asked = head, receipt, balances, []

    def call(self, method, params):
        self.asked.append(method)
        if method == "eth_getTransactionReceipt":
            return self.receipt
        if method == "eth_blockNumber":
            return hex(self.head)
        if method == "eth_getTransactionByHash":
            return RECORDED["transaction"]
        if method == "eth_getBlockByNumber":
            return RECORDED["block"]
        if method == "eth_getBalance":
            if not self.balances:
                raise RpcError(-32000, "historical state at block is not available")
            return hex(BEFORE if int(params[1], 16) == BLOCK - 1 else BEFORE - SOLD)
        raise AssertionError(f"unexpected call {method}")


def read(rpc=None, **rest):
    return reconcile.read(rpc or FakeRpc(), RECORDED["tx_hash"], wallet=WALLET, chain_id=CHAIN,
                          confirmations=rest.pop("confirmations", 100), sell=ETH, sell_decimals=18,
                          buy=USDG, buy_decimals=6, **rest)


def test_a_real_swap_reconciles_to_what_moved_and_names_what_it_cannot_explain():
    done = read()
    assert done.state is OrderState.CONFIRMED and done.settled
    assert done.gave.raw == SOLD and done.gave.asset == ETH          # from the balance
    assert done.got.raw == 78_742 and done.got.asset == USDG          # from the Transfer log
    assert done.gas is None                                           # sponsored: 0 wei
    assert done.unaccounted == 18_000_000_000                         # F0.10.4, 18 gwei
    assert "18000000000 wei the logs do not name (F0.10.4)" in done.why
    operation = done.execution.user_operation
    assert operation.sender == WALLET and operation.success.passes
    assert done.execution.transaction.submitted_by != WALLET          # a bundler sent it
    assert done.execution.transaction.tx_type == 4                    # EIP-7702
    assert [t.token for t in done.execution.transfers] == [USDG]      # only the wallet's own


def test_a_mined_revert_is_not_a_fill_however_the_venue_answered():
    done = read(FakeRpc(receipt=charged(RECORDED["receipt"], 21_000_000_000_000, success=False)))
    assert done.state is OrderState.FAILED and not done.settled
    assert done.gave is None and done.got is None                        # nothing was bought
    assert done.gas.raw == 21_000_000_000_000                            # and gas was charged
    assert "reverted" in done.why


def charged(receipt, wei: int, success: bool = True):
    """The same receipt with the operation charged `wei` of gas."""
    changed = copy.deepcopy(receipt)
    for log in changed["logs"]:
        if log["topics"][0] == reconcile.USER_OP_EVENT:
            words = [log["data"][2 + i * 64:2 + (i + 1) * 64] for i in range(4)]
            words[1] = f"{int(success):064x}"
            words[2] = f"{wei:064x}"
            log["data"] = "0x" + "".join(words) + log["data"][2 + 256:]
    return changed


def test_gas_the_operation_paid_comes_off_what_the_wallet_gave():
    """Every swap so far was sponsored (F0.10.3), so this path has never run live: if
    the bundler stops paying, the gas is the wallet's and is not part of the sale."""
    done = read(FakeRpc(receipt=charged(RECORDED["receipt"], 5_000_000_000_000)))
    assert done.state is OrderState.CONFIRMED
    assert done.gas.raw == 5_000_000_000_000
    assert done.gave.raw == SOLD - 5_000_000_000_000
    assert "less 5000000000000 wei of gas" in done.why


def test_an_outcome_that_is_not_settled_yet_is_unknown_not_failed():
    assert read(FakeRpc(receipt=None)).state is OrderState.UNKNOWN
    shallow = read(FakeRpc(head=BLOCK + 99))
    assert shallow.state is OrderState.UNKNOWN and "99 of 100 confirmations" in shallow.why
    assert read(confirmations=None).state is OrderState.UNKNOWN          # null blocks
    unevidenced = read(FakeRpc(balances=False))
    assert unevidenced.state is OrderState.UNKNOWN and "no longer holds the balance" in unevidenced.why
    assert unevidenced.execution is not None                             # what it did read


def test_another_wallets_operation_in_the_same_bundle_is_not_ours():
    stranger = copy.deepcopy(RECORDED["receipt"])
    for log in stranger["logs"]:
        if log["topics"][0] == reconcile.USER_OP_EVENT:
            log["topics"][2] = "0x" + "00" * 12 + "ab" * 20
    done = read(FakeRpc(receipt=stranger))
    assert done.state is OrderState.UNKNOWN and "not our swap" in done.why
