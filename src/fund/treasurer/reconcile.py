"""What actually happened on chain (unit 5.3).

A swap on 4663 is not an ordinary transaction from the fund's wallet. It is a
gas-sponsored **ERC-4337 UserOperation** inside an **EIP-7702 transaction sent by a
bundler** (F0.10.3). Probe 0.10's first verdict was wrong for exactly that reason: it
checked `tx.from == wallet` and the wallet's nonce, and both said no about a swap that
plainly moved the fund's money. So this module reads what is actually there:

- **who swapped** is the EntryPoint's `UserOperationEvent.sender`, never `tx.from`;
- **whether it filled** is that event's `success`, never the HTTP status and never the
  outer receipt's status, which says only that the bundle mined;
- **what moved** is the `Transfer` logs into and out of the wallet. The native leg
  emits no log, so its amount is the wallet's own balance across the swap's block,
  less any gas the operation was charged. Probe 0.10 left 18 gwei of a previous sale
  unaccounted (F0.10.4); this records the gap rather than hiding it;
- **how settled** it is: `cadence.confirmation_depth` blocks behind the head. Under
  that, the outcome is unknown, not failed.

**Unknown is an answer.** A receipt that is not there yet, a depth not reached, or a
native leg whose balance the node no longer holds all return `unknown`, and the order
stays in flight until this module can say otherwise. Nothing is booked from a guess,
and no new idempotency key is ever minted to escape one (PLAN §4).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Mapping

from fund.adapters.chain_4663 import RpcClient, RpcError
from fund.core.types import (
    Amount, AssetId, BlockRef, ChainAddress, Check, Execution, Instant, OrderState,
    TokenTransfer, TransactionRef, UserOperationRef,
)

#: The canonical ERC-4337 EntryPoint v0.7, which the swap's transaction targeted and
#: whose code probe 0.10 read (16,035 bytes) at this address.
ENTRYPOINT = "0x0000000071727de22e5e9d8baf0edac6f37da032"
#: keccak256("UserOperationEvent(bytes32,address,address,uint256,bool,uint256,uint256)")
USER_OP_EVENT = "0x49628fd1471006c1482da88028e9ce4dbb080b815c9b0344d39e5a8e6ec1419f"
#: keccak256("Transfer(address,address,uint256)")
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"


@dataclass(frozen=True)
class Reconciled:
    """What the chain says about one submitted swap."""

    state: OrderState               # confirmed, failed, or unknown
    why: str
    execution: Execution | None = None
    paid: Amount | None = None      # what left the wallet, from the logs or its balance
    received: Amount | None = None  # what reached it
    gas: Amount | None = None       # what the operation was charged, if anything
    unaccounted: int = 0            # native units the logs and the balance do not explain

    @property
    def settled(self) -> bool:
        return self.state is OrderState.CONFIRMED


def _word(data: str, index: int) -> int:
    return int(data[2 + index * 64:2 + (index + 1) * 64] or "0", 16)


def _address(topic: str) -> str:
    return "0x" + topic[26:]


def _transfers(receipt: Mapping[str, Any], chain_id: int, wallet: ChainAddress,
               decimals: Mapping[str, int]) -> list[TokenTransfer]:
    """The `Transfer` logs that touch the fund's wallet. The rest of a swap's logs are
    the venue's own routing, in tokens whose decimals the fund has never read, and it
    does not record an amount it cannot state."""
    out = []
    for index, log in enumerate(receipt.get("logs") or []):
        topics = log.get("topics") or []
        if len(topics) != 3 or topics[0] != TRANSFER:
            continue
        token = AssetId(chain_id, log["address"].lower())
        sender = ChainAddress(chain_id, _address(topics[1]))
        recipient = ChainAddress(chain_id, _address(topics[2]))
        if wallet not in (sender, recipient) or token.address not in decimals:
            continue
        out.append(TokenTransfer(
            token=token, sender=sender, recipient=recipient,
            amount=Amount(int(log["data"], 16), decimals[token.address], token),
            log_index=int(log.get("logIndex", hex(index)), 16)))
    return out


def _operation(receipt: Mapping[str, Any], wallet: ChainAddress,
               chain_id: int) -> tuple[UserOperationRef, bool] | None:
    for log in receipt.get("logs") or []:
        topics = log.get("topics") or []
        if log["address"].lower() != ENTRYPOINT or not topics or topics[0] != USER_OP_EVENT:
            continue
        if _address(topics[2]).lower() != wallet.address:
            continue  # someone else's operation in the same bundle
        nonce, success, gas_cost = _word(log["data"], 0), _word(log["data"], 1), _word(log["data"], 2)
        paymaster = _address(topics[3])
        return UserOperationRef(
            entry_point=ChainAddress(chain_id, ENTRYPOINT), user_op_hash=topics[1],
            sender=wallet, nonce_key=hex(nonce >> 64), nonce_seq=nonce & ((1 << 64) - 1),
            paymaster=None if int(paymaster, 16) == 0 else ChainAddress(chain_id, paymaster),
            success=Check(bool(success), "the EntryPoint says the operation "
                          + ("succeeded" if success else "reverted")),
            actual_gas_cost=Amount(gas_cost, 18, AssetId.native(chain_id))), bool(success)
    return None


def read(rpc: RpcClient, tx_hash: str, *, wallet: ChainAddress, chain_id: int,
         confirmations: int | None, sell: AssetId, sell_decimals: int, buy: AssetId,
         buy_decimals: int) -> Reconciled:
    """The outcome of one swap, from its receipt. Never from the HTTP reply."""
    if confirmations is None:
        return Reconciled(OrderState.UNKNOWN, "cadence.confirmation_depth is null: unresolved, "
                                              "and it blocks")
    receipt = rpc.call("eth_getTransactionReceipt", [tx_hash])
    if receipt is None:
        return Reconciled(OrderState.UNKNOWN, f"{tx_hash} has no receipt yet: not mined")
    block_number = int(receipt["blockNumber"], 16)
    head = int(rpc.call("eth_blockNumber", []), 16)
    depth = head - block_number
    if depth < confirmations:
        return Reconciled(OrderState.UNKNOWN, f"mined in {block_number}, {depth} of "
                                              f"{confirmations} confirmations behind head {head}")

    transaction = rpc.call("eth_getTransactionByHash", [tx_hash])
    block = rpc.call("eth_getBlockByNumber", [hex(block_number), False])
    reference = TransactionRef(
        tx_hash=tx_hash, tx_type=int(transaction.get("type", "0x0"), 16),
        block=BlockRef(chain_id=chain_id, number=block_number, hash=receipt["blockHash"],
                       timestamp=Instant.from_seconds(int(block["timestamp"], 16))),
        submitted_by=ChainAddress(chain_id, transaction["from"].lower()),
        outer_status=int(receipt.get("status", "0x1"), 16))
    found = _operation(receipt, wallet, chain_id)
    if found is None:
        return Reconciled(OrderState.UNKNOWN, f"no UserOperationEvent for {wallet.address} in "
                                              f"{tx_hash}: this is not our swap, or not yet")
    operation, succeeded = found
    transfers = _transfers(receipt, chain_id, wallet,
                           {sell.address: sell_decimals, buy.address: buy_decimals})
    execution = Execution(transaction=reference, user_operation=operation,
                          transfers=tuple(transfers))
    gas = operation.actual_gas_cost if operation.actual_gas_cost.raw else None
    if not succeeded:  # 200 or not, a reverted operation is not a fill (F0.10.3)
        return Reconciled(OrderState.FAILED, "the operation reverted: no fill, and gas was "
                          f"charged at {operation.actual_gas_cost.raw} wei", execution=execution,
                          gas=gas)

    def moved(asset: AssetId, decimals: int, incoming: bool) -> tuple[Amount | None, str]:
        """What the wallet received or paid of one asset: its `Transfer` logs, or — for
        the native asset, which emits none — its own balance across the block."""
        if not asset.is_native:
            total = sum(t.amount.raw for t in transfers if t.token == asset
                        and (t.recipient == wallet if incoming else t.sender == wallet))
            return (Amount(total, decimals, asset) if total else None), "from its Transfer logs"
        try:
            before = int(rpc.call("eth_getBalance", [wallet.address, hex(block_number - 1)]), 16)
            after = int(rpc.call("eth_getBalance", [wallet.address, hex(block_number)]), 16)
        except RpcError as unavailable:
            return None, f"the node no longer holds the balance at {block_number}: {unavailable}"
        delta = after - before
        charged = operation.actual_gas_cost.raw
        raw = delta if incoming else -delta - charged
        return ((Amount(raw, decimals, asset) if raw > 0 else None),
                f"from its balance across block {block_number}"
                + (f", less {charged} wei of gas" if charged else ", gas sponsored"))

    received, received_how = moved(buy, buy_decimals, incoming=True)
    paid, paid_how = moved(sell, sell_decimals, incoming=False)
    if received is None or paid is None:
        return Reconciled(OrderState.UNKNOWN, "the operation succeeded, and the amounts are not "
                          f"evidenced: paid {paid_how}, received {received_how}",
                          execution=execution, gas=gas)
    unaccounted = 0
    if sell.is_native:  # what the receipt's logs name against what the wallet actually paid
        wrapped = sum(int(log["data"], 16) for log in receipt.get("logs") or []
                      if (log.get("topics") or [None])[0] == TRANSFER
                      and len(log["topics"]) == 3 and int(log["topics"][1], 16) == 0)
        unaccounted = paid.raw - wrapped if wrapped and paid.raw > wrapped else 0
    return Reconciled(OrderState.CONFIRMED,
                      f"the operation succeeded in block {block_number}, {depth} confirmations "
                      f"deep; paid {paid.raw} {paid_how}, received {received.raw} {received_how}"
                      + (f"; {unaccounted} wei the logs do not name (F0.10.4)"
                         if unaccounted else ""),
                      execution=execution, paid=paid, received=received, gas=gas,
                      unaccounted=unaccounted)
