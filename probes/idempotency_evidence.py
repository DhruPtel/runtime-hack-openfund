"""Probe 0.10, the chain evidence for the swap `probes/idempotency.py` sent.
Read-only and free.

    PYTHONPATH=src python3 -m probes.idempotency_evidence

**Why this exists.** `idempotency.py` took the wallet's nonce as its arbiter, on
the assumption that the swap would be an ordinary transaction from our wallet.
It was not. The transaction Bankr returned is an **EIP-7702 set-code transaction
(type 4) sent by a bundler** to what appears to be the ERC-4337 EntryPoint v0.7.
It carries an authorization, signed by our wallet, delegating the wallet's code
on 4663, and the swap runs as a UserOperation whose `sender` is our wallet. The
nonce went 0 -> 1 because that authorization consumed it, not because the wallet
broadcast one transaction, and the `from == wallet` check reported False for a
swap that plainly moved our funds. Both were instrument errors. This probe reads
what is actually there:

- the transaction type, sender, target and authorization list;
- the EntryPoint's `UserOperationEvent`, whose `sender`, `success` and
  `actualGasCost` say who swapped, whether it filled, and who paid for gas;
- `EntryPoint.getNonce(wallet, key)` on the UserOperation's own nonce key: the
  chain's count of operations executed under that key;
- the wallet's code on 4663 and on Base;
- native balance deltas across the block, for every address the logs name,
  while the node still holds that recent state.
"""

from __future__ import annotations

import json
import pathlib
import sys
import urllib.request

from fund import config
from fund.credentials import Role

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"
BASE_RPC = "https://mainnet.base.org"
#: The address the transaction targeted, taken from its receipt and checked
#: for code below. It matches the canonical ERC-4337 EntryPoint v0.7 address.
ENTRYPOINT = "0x0000000071727de22e5e9d8baf0edac6f37da032"
#: keccak256("UserOperationEvent(bytes32,address,address,uint256,bool,uint256,uint256)")
USER_OP_EVENT = "0x49628fd1471006c1482da88028e9ce4dbb080b815c9b0344d39e5a8e6ec1419f"
TRANSFER = "0xddf252ad1be2c89b69c2b068fc378daa952ba7f163c4a11628f55a4df523b3ef"
GET_NONCE = "0x35567e1a"


def _rpc(url: str, method: str, params: list) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json", "User-Agent": "openfund-probe/0.10"})
    with urllib.request.urlopen(request, timeout=30) as response:
        return json.loads(response.read().decode("utf-8"))


def main() -> int:
    config.load_environment()
    rpc = config.load(Role.ANALYST).secret("RPC_4663_MAINNET")
    sent = json.loads((OUT_DIR / "idempotency.json").read_text())
    tx_hash = sent["receipts"][0]["hash"]
    call = lambda m, p: _rpc(rpc, m, p)

    tx = call("eth_getTransactionByHash", [tx_hash])["result"]
    rc = call("eth_getTransactionReceipt", [tx_hash])["result"]
    block = int(rc["blockNumber"], 16)

    user_ops = []
    for log in rc["logs"]:
        if log["address"].lower() == ENTRYPOINT and log["topics"][0] == USER_OP_EVENT:
            words = [int(log["data"][2 + i:2 + i + 64], 16) for i in range(0, len(log["data"]) - 2, 64)]
            nonce = words[0]
            key = nonce >> 64
            next_on_key = int(call("eth_call", [{"to": ENTRYPOINT, "data": GET_NONCE + "0" * 24
                                                 + WALLET[2:] + format(key, "064x")}, "latest"])["result"], 16)
            user_ops.append({
                "user_op_hash": log["topics"][1],
                "sender": "0x" + log["topics"][2][26:],
                "paymaster": "0x" + log["topics"][3][26:],
                "nonce_key": hex(key), "nonce_seq": nonce & ((1 << 64) - 1),
                "success": bool(words[1]), "actual_gas_cost_wei": words[2],
                "actual_gas_used": words[3],
                "ops_executed_on_this_key": (next_on_key & ((1 << 64) - 1)),
            })

    transfers = [{"token": l["address"], "from": "0x" + l["topics"][1][26:],
                  "to": "0x" + l["topics"][2][26:], "value": int(l["data"], 16)}
                 for l in rc["logs"] if l["topics"][0] == TRANSFER and len(l["topics"]) == 3]

    named = {WALLET, tx["from"].lower(), (tx["to"] or "").lower()}
    named |= {l["address"].lower() for l in rc["logs"]}
    named |= {a.get("address", "").lower() for a in tx.get("authorizationList") or []}
    named |= {t["from"] for t in transfers} | {t["to"] for t in transfers}
    deltas = {}
    for a in sorted(x for x in named if x and x != "0x" + "0" * 40):
        r0 = call("eth_getBalance", [a, hex(block - 1)])
        r1 = call("eth_getBalance", [a, hex(block)])
        deltas[a] = (int(r1["result"], 16) - int(r0["result"], 16)
                     if "result" in r0 and "result" in r1 else "state unavailable")

    sold = -(sent["chain_after_20s"]["eth_wei"] - sent["chain_before"]["eth_wei"])
    accounted = sum(v for a, v in deltas.items() if isinstance(v, int) and v > 0)
    evidence = {
        "tx_hash": tx_hash, "block": block,
        "tx_type": tx.get("type"), "tx_from": tx["from"], "tx_to": tx["to"],
        "tx_selector": tx["input"][:10],
        "entrypoint_code_bytes": (len(call("eth_getCode", [ENTRYPOINT, "latest"])["result"]) - 2) // 2,
        "authorization_list": tx.get("authorizationList"),
        "wallet_code_4663": call("eth_getCode", [WALLET, "latest"])["result"],
        "wallet_code_base": _rpc(BASE_RPC, "eth_getCode", [WALLET, "latest"])["result"],
        "user_operations": user_ops,
        "transfers": transfers,
        "outer_gas_paid_wei": int(rc["gasUsed"], 16) * int(rc["effectiveGasPrice"], 16),
        "native_deltas_at_block": deltas,
        "native_sold_by_wallet_wei": sold,
        "native_received_by_named_addresses_wei": accounted,
        "native_unaccounted_wei": sold - accounted,
        "tracing": {m: call(m, [tx_hash] + ([{"tracer": "callTracer"}] if m.startswith("debug") else [])).get("error", {}).get("message", "available")
                    for m in ("debug_traceTransaction", "trace_transaction")},
    }
    (OUT_DIR / "idempotency_evidence.json").write_text(json.dumps(evidence, indent=2), encoding="utf-8")

    print(f"tx {tx_hash}  block {block}  type {tx.get('type')}")
    print(f"  from {tx['from']} (bundler)  to {tx['to']} selector {tx['input'][:10]}")
    for a in tx.get("authorizationList") or []:
        print(f"  7702 authorization: chainId {int(a['chainId'], 16)} delegate {a['address']} nonce {int(a['nonce'], 16)}")
    print(f"  wallet code: 4663 {evidence['wallet_code_4663']}  |  Base {evidence['wallet_code_base']}")
    for op in user_ops:
        print(f"  UserOperation sender {op['sender']} success {op['success']} paymaster {op['paymaster']} "
              f"actualGasCost {op['actual_gas_cost_wei']} wei; ops executed on its nonce key: {op['ops_executed_on_this_key']}")
    print(f"  outer gas paid by bundler: {evidence['outer_gas_paid_wei']} wei")
    for a, d in deltas.items():
        if d:
            print(f"  native delta {a}: {d}")
    print(f"  native sold {sold} wei; received by named addresses {accounted}; unaccounted {sold - accounted}")
    print(f"  tracing: {evidence['tracing']}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
