"""Probe 0.10, first half — does a repeated swap with the same idempotency key
broadcast twice? **This one spends: an ungated swap of ~$0.08 of ETH.**

    PYTHONPATH=src python3 -m probes.idempotency            # pre-flight only, sends nothing
    PYTHONPATH=src python3 -m probes.idempotency --confirm  # two submissions, once

**Goal.** `planning/PHASE-0-1.md` 0.10: submit the same swap payload twice with
the same key and record whether the second is rejected, deduped or filled.
`planning/PLAN.md` §4 builds the order state machine on this — "we never mint a
new idempotency key to escape uncertainty" is only safe if the key actually
dedupes. Bankr documents that it does (`https://docs.bankr.bot/wallet-api/swap/`,
read 2026-09-18): *"A repeat POST with the same key returns the original result,
never a second broadcast"*, and *"While the original is still in flight, a
repeat returns 409."* That is documented; this measures it.

**The asset.** Tokenized stocks are location-gated for this operator (F0.5.1), so
a stock swap would 403 before idempotency was ever tested. This sells native ETH
into USDG on 4663, which is not a stock and is not gated. It is also the first
attempt to show `BANKR_KEY_EXEC` can transact at all, which 0.5 could not
(F0.5.5) and Phase 5 depends on.

**The size.** 0.00003 ETH, about $0.08: the smallest amount that quoted on
2026-09-18. 0.00001 was refused with "The amount is too small to swap".

**The arbiter is the chain, not the HTTP bodies.** The wallet's ETH and USDG
balances are read over RPC before and after; two fills would show twice the
sell and twice the buy, whatever either response claims.

**Corrected after the one run (2026-09-18).** This probe also took the wallet's
nonce and the transaction's `from` as arbiters, on the assumption that the swap
would be an ordinary transaction from our wallet. It was not. Bankr runs it as
an ERC-4337 UserOperation inside an EIP-7702 transaction sent by a bundler, so
`from` is the bundler, and the nonce moved because the wallet's 7702
authorization consumed it — not because a transaction was broadcast. Both
printed lines are relabelled below. The chain evidence is read by
`probes/idempotency_evidence.py`.

**What we do not do.** No retry and no loop. Two submissions, the second sent as
soon as the first returns, each printed before it is sent. The timeout is
raised to 120 s, because a client-side timeout on the first would leave it in
flight and turn the second into a different experiment.
"""

from __future__ import annotations

import json
import pathlib
import sys
import time
import urllib.request
import uuid

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

QUOTE_URL = "https://api.bankr.bot/wallet/swap-quote"
SWAP_URL = "https://api.bankr.bot/wallet/swap"
CHAIN = "robinhood"
WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"

#: Native-gas sentinel, per the swap docs (see probes/execute.py).
NATIVE_SENTINEL = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
#: USDG on 4663, 6 decimals (F0.3.1).
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"

SELL_AMOUNT_ETH = "0.00003"
SELL_WEI = 30_000_000_000_000
#: Enough ETH must remain for gas even if the key does NOT dedupe and both
#: submissions fill, so the guard assumes two fills.
GAS_RESERVE_WEI = 200_000_000_000_000

SWAP_TIMEOUT_SECONDS = 120
RECEIPT_WAIT_SECONDS = 90


def _rpc(url: str, method: str, params: list) -> object:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    request = urllib.request.Request(url, data=payload, headers={
        "Content-Type": "application/json", "User-Agent": "openfund-probe/0.10"})
    with urllib.request.urlopen(request, timeout=20) as response:
        body = json.loads(response.read().decode("utf-8"))
    if "error" in body:
        raise RuntimeError(f"{method}: {body['error']}")
    return body["result"]


def chain_state(rpc: str) -> dict:
    """Nonce and balances, read directly from the chain, never from the portfolio."""
    usdg = _rpc(rpc, "eth_call", [{"to": USDG, "data": "0x70a08231" + "0" * 24 + WALLET[2:]},
                                  "latest"])
    return {
        "block": int(_rpc(rpc, "eth_blockNumber", []), 16),
        "nonce": int(_rpc(rpc, "eth_getTransactionCount", [WALLET, "latest"]), 16),
        "eth_wei": int(_rpc(rpc, "eth_getBalance", [WALLET, "latest"]), 16),
        "usdg_raw": int(usdg, 16),
    }


def receipt(rpc: str, tx_hash: str) -> dict:
    """The transaction and its receipt, waiting for it to mine."""
    deadline = time.monotonic() + RECEIPT_WAIT_SECONDS
    tx = rcpt = None
    while time.monotonic() < deadline:
        tx = tx or _rpc(rpc, "eth_getTransactionByHash", [tx_hash])
        rcpt = _rpc(rpc, "eth_getTransactionReceipt", [tx_hash])
        if rcpt:
            break
        time.sleep(3)
    return {
        "hash": tx_hash,
        "found": tx is not None,
        "from": (tx or {}).get("from"),
        "to": (tx or {}).get("to"),
        "nonce": int(tx["nonce"], 16) if tx else None,
        "block": int(rcpt["blockNumber"], 16) if rcpt else None,
        "status": int(rcpt["status"], 16) if rcpt else None,
        "gas_used": int(rcpt["gasUsed"], 16) if rcpt else None,
        "effective_gas_price": int(rcpt["effectiveGasPrice"], 16) if rcpt and rcpt.get("effectiveGasPrice") else None,
    }


def quote(key: str) -> tuple[dict, _capture.Capture]:
    capture = _capture.call(
        label="quote", url=QUOTE_URL, header_name="X-API-Key", header_value=key,
        max_body_chars=4000,
        json_body={"fromChain": CHAIN, "fromToken": NATIVE_SENTINEL,
                   "toChain": CHAIN, "toToken": USDG, "amount": SELL_AMOUNT_ETH})
    return _capture.as_json(capture) or {}, capture


def submit(label: str, key: str, body: dict) -> _capture.Capture:
    return _capture.call(label=label, url=SWAP_URL, header_name="X-API-Key",
                         header_value=key, json_body=body,
                         timeout=SWAP_TIMEOUT_SECONDS, max_body_chars=20000)


def dump(capture: _capture.Capture) -> dict:
    return {"status": capture.status, "elapsed_ms": capture.elapsed_ms,
            "body": capture.body, "body_truncated": capture.truncated,
            "response_headers": capture.response_headers,
            "transport_error": capture.transport_error,
            "request_body": capture.request_body}


def classify(first: dict, second: dict) -> str:
    h1, h2 = first.get("hash"), second.get("hash")
    if second.get("_status") == 409:
        return "rejected: 409, original still in flight"
    if h2 and h1 and h2 == h1:
        return "deduped: returned the original result"
    if h2 and h1 and h2 != h1:
        return "FILLED A SECOND TIME: a different transaction"
    return f"other: HTTP {second.get('_status')}"


def main() -> int:
    config.load_environment()
    confirmed = "--confirm" in sys.argv
    treasurer = config.load(Role.TREASURER)
    key = treasurer.secret("BANKR_KEY_EXEC")
    rpc = treasurer.secret("RPC_4663_MAINNET")

    before = chain_state(rpc)
    quoted, quote_capture = quote(key)
    if quote_capture.status != 200:
        print(f"quote failed: {quote_capture.summary()}\n{quote_capture.body}\nSTOPPING.")
        return 1

    print("=" * 72)
    print("UNIT 0.10 — IDEMPOTENCY.  THIS SENDS A REAL SWAP, THEN REPEATS IT ONCE.")
    print("=" * 72)
    print(f"  wallet     {WALLET}  (chain {CHAIN}, 4663)")
    print(f"  sell       {SELL_AMOUNT_ETH} ETH  (~${quoted['from'].get('usdValue')})")
    print(f"  buy        USDG {USDG}")
    print(f"  expect     {quoted['to'].get('formattedAmount')} USDG, min {quoted.get('minBuyAmount')}")
    print(f"  impact     swapImpactBps {quoted.get('swapImpactBps')} / limit "
          f"{quoted.get('maxPriceImpactBps')}; feeBps {quoted.get('feeBps')}")
    print(f"  chain now  block {before['block']}, nonce {before['nonce']}, "
          f"{before['eth_wei'] / 1e18:.9f} ETH, {before['usdg_raw'] / 1e6:.6f} USDG")
    print(f"  key        BANKR_KEY_EXEC (treasurer role)")
    print("=" * 72)

    needed = 2 * SELL_WEI + GAS_RESERVE_WEI
    if before["eth_wei"] < needed:
        print(f"\nBLOCKED: {before['eth_wei']} wei is below two sells plus the gas "
              f"reserve ({needed} wei). Nothing sent.")
        return 2
    if not confirmed:
        print("\nPre-flight only. Nothing was sent. Re-run with --confirm.")
        return 0

    idempotency_key = str(uuid.uuid4())
    body = {"fromChain": CHAIN, "fromToken": NATIVE_SENTINEL, "toChain": CHAIN,
            "toToken": USDG, "amount": SELL_AMOUNT_ETH,
            "minBuyAmount": quoted["minBuyAmount"], "quoteId": quoted.get("quoteId"),
            "idempotencyKey": idempotency_key}

    print(f"\nSUBMISSION 1 of 2 — sells {SELL_AMOUNT_ETH} ETH into USDG. "
          f"idempotencyKey {idempotency_key}")
    print(json.dumps(body, indent=2, sort_keys=True))
    first = submit("swap-1", key, body)
    print(f"-> {first.summary()}\n{first.body}")

    print(f"\nSUBMISSION 2 of 2 — the identical body, the same idempotencyKey, sent "
          f"now. Documented: the original result, never a second broadcast.")
    second = submit("swap-2", key, body)
    print(f"-> {second.summary()}\n{second.body}")

    p1 = {**(_capture.as_json(first) or {}), "_status": first.status}
    p2 = {**(_capture.as_json(second) or {}), "_status": second.status}
    hashes = [h for h in dict.fromkeys([p1.get("hash"), p2.get("hash")]) if h]
    receipts = [receipt(rpc, h) for h in hashes]
    after = chain_state(rpc)
    time.sleep(20)
    after_settle = chain_state(rpc)

    verdict = classify(p1, p2)
    broadcast = after_settle["nonce"] - before["nonce"]
    transacted = any(r["from"] and r["from"].lower() == WALLET and r["status"] == 1
                     for r in receipts)

    result = {
        "sent": True,
        "idempotency_key": idempotency_key,
        "quote": {**dump(quote_capture), "parsed": quoted},
        "submission_1": dump(first),
        "submission_2": dump(second),
        "receipts": receipts,
        "chain_before": before,
        "chain_after": after,
        "chain_after_20s": after_settle,
        "transactions_broadcast_by_wallet": broadcast,
        "second_submission": verdict,
        "exec_key_transacted": transacted,
    }
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "idempotency.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print("\n" + "=" * 72)
    print(f"second submission:        {verdict}")
    print(f"EOA nonce delta:          {broadcast}  (nonce {before['nonce']} -> "
          f"{after_settle['nonce']}; counts 7702 authorizations too — not a swap count)")
    for r in receipts:
        print(f"  {r['hash']}  from {r['from']}  block {r['block']}  status {r['status']}  "
              f"gas {r['gas_used']}")
    print(f"tx sent from our wallet:  {transacted}  (False for a bundled UserOperation; "
          f"see idempotency_evidence.py)")
    print(f"ETH  {before['eth_wei']} -> {after_settle['eth_wei']} wei "
          f"(delta {after_settle['eth_wei'] - before['eth_wei']})")
    print(f"USDG {before['usdg_raw']} -> {after_settle['usdg_raw']} raw "
          f"(delta {after_settle['usdg_raw'] - before['usdg_raw']})")
    print(f"written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
