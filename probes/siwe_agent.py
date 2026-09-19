"""Unit 2.0 — does the SIWE-made agent account hold up, measured rather than read?

    PYTHONPATH=src python3 -m probes.siwe_agent            # reads and pre-flight only
    PYTHONPATH=src python3 -m probes.siwe_agent --confirm  # plus the refusal attempts, once

Everything in Phase 2 assumes each agent has its own Bankr account with its own
address and pays for its own inference. The login (`probes/siwe/hook.mjs`, run
once under a separate CLI config) reported `readOnly: true` and a wallet
address, and nothing else about the key: not the Agent API, not the gateway. So
each property is tested by what the key does, not by what a flag says:

  - **its own address:** `/wallet/me` and `/wallet/portfolio`, compared with the
    fund's wallet and with the SIWE signer's address;
  - **the gateway:** `GET /v1/credits`, which answers 200 with a gateway-enabled
    key and 403 naming the toggle without one, with `BANKR_KEY_READ` (gateway
    off, F0.2.4) and a never-issued key as controls; then `/v1/models` and one
    minimal completion;
  - **cannot transact:** a message signature (`/wallet/sign`), which needs no
    balance, so a refusal cannot be an empty wallet; and a quoted swap;
  - **Agent API off:** `/agent/sign` and `/agent/prompt`, the endpoint the
    invariant names;
  - **can it fund itself:** `/llm/credits/topup`, the call `bankr llm credits
    add` makes.

**Nothing here can spend.** Every write is sent only after the agent wallet is
read empty on both chains it could spend from, so even a key that should have
been refused has nothing to move: a swap of ETH it does not hold, a top-up from
USDC it does not hold. A signature over a plain message moves nothing either.
Each attempt is sent once.

**The agent's key is not a declared credential** (it joins `credentials.py` at
2.4, and `src/` is outside this unit's paths), so `fund.redaction` does not know
it. Every capture is masked here, before truncation, and the stored file is
checked for the raw value before it is written.
"""

from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

from fund import config, credentials
from probes import _capture

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "probes" / "out" / "siwe_agent.json"
AGENT_DIR = Path.home() / ".openfund" / "agents" / "price-integrity"

API = "https://api.bankr.bot"
LLM = "https://llm.bankr.bot"
BASE_RPC = "https://mainnet.base.org"
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"

FUND_WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"
NEVER_ISSUED = "bk_0000000000000000000000000000000000000000"

CHAIN = "robinhood"
NATIVE = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"
USDG = "0x5fc5360d0400a0fd4f2af552add042d716f1d168"
SELL_ETH = "0.00003"  # 0.10's size: the smallest that quoted

SIGN_MESSAGE = "openfund unit 2.0: an analyst key must not be able to sign this."
MODEL = json.loads((ROOT / "config" / "models.json").read_text())["analyst_model"]
BODY_LIMIT = 4000


def agent_key() -> str:
    return json.loads((AGENT_DIR / "bankr-config.json").read_text())["apiKey"]


def login_record() -> dict:
    """The login's own answer, as the hook kept it (key already masked)."""
    record = json.loads((AGENT_DIR / "siwe-login.json").read_text())
    verify = next(r for r in record if r["url"].endswith("/cli/siwe/verify"))
    sent = json.loads(verify["request_body"])
    signer = sent["message"].split("\n")[1]
    sent.pop("message")
    sent.pop("signature", None)
    return {"status": verify["status"], "at": verify["at"], "signer": signer,
            "sent": sent, "answered": json.loads(verify["response_body"])}


class Masked:
    """Every capture passes through here, so the agent key never reaches disk."""

    def __init__(self, secret: str):
        self.secret = secret

    def text(self, value: str) -> str:
        return value.replace(self.secret, "[AGENT_API_KEY]") if value else value

    def call(self, label: str, url: str, key: str, **kwargs) -> dict:
        capture = _capture.call(label=label, url=url, header_name="X-API-Key",
                                header_value=key, max_body_chars=200_000, **kwargs)
        body = self.text(capture.body)
        entry = {
            "label": label,
            "method": capture.method,
            "url": self.text(capture.url),
            "request_body": self.text(capture.request_body),
            "status": capture.status,
            "elapsed_ms": capture.elapsed_ms,
            "transport_error": self.text(capture.transport_error or ""),
            "body": body[:BODY_LIMIT],
            "truncated": len(body) > BODY_LIMIT,
        }
        print(f"  {label:<44} {capture.summary():<22} {entry['body'][:150]}")
        return entry


def rpc(url: str, method: str, params: list) -> str:
    capture = _capture.call(label=method, url=url, header_name="Accept",
                            header_value="application/json", method="POST",
                            json_body={"jsonrpc": "2.0", "id": 1, "method": method,
                                       "params": params})
    return (_capture.as_json(capture) or {}).get("result")


def balances(address: str, rpc_4663: str) -> dict:
    """What the agent wallet could spend from, read at the chain, not the portfolio (F0.7b.8)."""
    padded = address.lower().removeprefix("0x").rjust(64, "0")
    usdc = rpc(BASE_RPC, "eth_call", [{"to": USDC_BASE, "data": "0x70a08231" + padded}, "latest"])
    return {
        "eth_4663_wei": int(rpc(rpc_4663, "eth_getBalance", [address, "latest"]), 16),
        "eth_base_wei": int(rpc(BASE_RPC, "eth_getBalance", [address, "latest"]), 16),
        "usdc_base_units": int(usdc, 16) if usdc and usdc != "0x" else None,
    }


def main(confirmed: bool) -> int:
    fund = config.load(credentials.Role.ANALYST, require=False)
    read_key = fund.secret("BANKR_KEY_READ")
    rpc_4663 = fund.secret("RPC_4663_MAINNET")
    key = agent_key()
    masked = Masked(key)
    login = login_record()
    runs: dict = {"login": login, "model": MODEL, "reads": [], "writes": []}

    print("LOGIN, as the API answered it")
    print(f"  sent     {json.dumps(login['sent'], sort_keys=True)}")
    print(f"  answered {json.dumps(login['answered'], sort_keys=True)}")
    print(f"  signer   {login['signer']}")

    print("\nADDRESS")
    me = masked.call("wallet/me: agent", f"{API}/wallet/me", key)
    runs["reads"] += [me, masked.call("wallet/me: never-issued control", f"{API}/wallet/me", NEVER_ISSUED)]
    portfolio = masked.call("wallet/portfolio: agent", f"{API}/wallet/portfolio", key)
    runs["reads"].append(portfolio)
    try:
        address = json.loads(portfolio["body"]).get("evmAddress")
    except (ValueError, AttributeError):
        address = None
    address = address or login["answered"].get("walletAddress")
    runs["address"] = {
        "agent": address,
        "fund": FUND_WALLET,
        "signer": login["signer"],
        "distinct_from_fund": bool(address) and address.lower() != FUND_WALLET,
        "equals_signer": bool(address) and address.lower() == login["signer"].lower(),
    }
    print(f"  agent {address} · fund {FUND_WALLET} · signer {login['signer']}")

    print("\nGATEWAY")
    for label, k in (("agent", key), ("BANKR_KEY_READ control (gateway off)", read_key),
                     ("never-issued control", NEVER_ISSUED)):
        runs["reads"].append(masked.call(f"v1/credits: {label}", f"{LLM}/v1/credits", k))
    runs["reads"].append(masked.call("v1/models: agent", f"{LLM}/v1/models", key))
    runs["reads"].append(masked.call(
        "v1/chat/completions: agent, 5 tokens", f"{LLM}/v1/chat/completions", key,
        json_body={"model": MODEL, "max_tokens": 5, "temperature": 0,
                   "messages": [{"role": "user", "content": "Reply with the word ok."}]},
        timeout=60))

    print("\nWHAT THE AGENT WALLET HOLDS, before any write")
    before = balances(address, rpc_4663)
    runs["before"] = before
    print(f"  {before}")
    empty = before["eth_4663_wei"] == 0 and before["eth_base_wei"] == 0 and before["usdc_base_units"] == 0
    if not empty:
        print("\nBLOCKED: the agent wallet is not empty, so a write could move value. Nothing sent.")
        runs["blocked"] = "wallet not empty"
    elif not confirmed:
        print("\nPre-flight only. No write was sent. Re-run with --confirm.")
    else:
        print("\nWRITES, each expected to be refused, each sent once")
        quote = masked.call("wallet/swap-quote: agent (a read)", f"{API}/wallet/swap-quote", key,
                            json_body={"fromChain": CHAIN, "fromToken": NATIVE, "toChain": CHAIN,
                                       "toToken": USDG, "amount": SELL_ETH})
        quoted = json.loads(quote["body"]) if quote["status"] == 200 else {}
        runs["reads"].append(quote)
        writes = [
            ("wallet/sign: never-issued control", f"{API}/wallet/sign", NEVER_ISSUED,
             {"signatureType": "personal_sign", "message": SIGN_MESSAGE}),
            ("wallet/sign: agent", f"{API}/wallet/sign", key,
             {"signatureType": "personal_sign", "message": SIGN_MESSAGE}),
            ("wallet/swap: agent", f"{API}/wallet/swap", key,
             {"fromChain": CHAIN, "fromToken": NATIVE, "toChain": CHAIN, "toToken": USDG,
              "amount": SELL_ETH, "minBuyAmount": quoted.get("minBuyAmount"),
              "quoteId": quoted.get("quoteId"), "idempotencyKey": str(uuid.uuid4())}),
            ("agent/sign: agent", f"{API}/agent/sign", key,
             {"signatureType": "personal_sign", "message": SIGN_MESSAGE}),
            ("agent/prompt: agent", f"{API}/agent/prompt", key,
             {"prompt": "Reply with the single word ok. Do not take any action."}),
            ("llm/credits/topup: agent, $1 from empty", f"{API}/llm/credits/topup", key,
             {"amountUsd": 1, "chain": "base"}),
        ]
        for label, url, k, body in writes:
            runs["writes"].append(masked.call(label, url, k, json_body=body, timeout=60))
        after = balances(address, rpc_4663)
        runs["after"] = after
        print(f"\nAFTER\n  {after}  unchanged: {after == before}")

    serialized = json.dumps(runs, indent=2, sort_keys=True)
    if key in serialized:
        print("REFUSING TO WRITE: the agent key would reach disk")
        return 3
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialized + "\n")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main("--confirm" in sys.argv[1:]))
