"""Probe 0.7d step 3 — pay our own endpoint once, and verify it from the chain.

**Spends $0.001 USDC.** Nothing is paid without `--confirm`, and the endpoint,
price, wallet and balance are printed first.

This is the controlled test. Between 0.7's failure and now, **exactly one thing
changed**: the handler returns `Response.json(...)` instead of a plain object.
Same service name, same URL, same $0.001, same network, same asset, same
hand-written config — which F0.7d.3 showed was never the problem — and the
handler still does no work. If this settles, the cause was the return shape and
nothing else.

**Settlement is verified on chain, not from the 200.** F0.7b.4 measured
settlement arriving *after* the HTTP response: the balance had not moved when the
CLI returned. So a 200 is not the proof here. The proof is the `PaymentSettled`
event with our address as `owner`, plus the USDC transfer into our wallet, both
polled until they appear.

Run:  PYTHONPATH=src python3 -m probes.x402_paid [--confirm]
"""

from __future__ import annotations

import json
import pathlib
import re
import subprocess
import sys
import time
import urllib.error
import urllib.request

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"
SERVICE = "roundtrip"
ENDPOINT = f"https://x402.bankr.bot/{WALLET}/{SERVICE}"
PRICE_USD = "0.001"
MAX_PAYMENT_USD = "0.01"

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_RPC = "https://mainnet.base.org"
USER_AGENT = "openfund-probe/0.7d"

#: BankrFeeRouterV2, and the settlement event decoded in F0.7b.6.
ROUTER = "0x8AEE621035D93Deb3C0C1177fac252dC2dd501a0"
PAYMENT_SETTLED = "0xfdc355c44a725f89b3989010cdad404cf378ba8db57896a4b7a623cdd66d30d9"

LOGS_URL = f"https://api.bankr.bot/x402/endpoints/logs/{SERVICE}"


def _rpc(method: str, params: list) -> dict:
    payload = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                          "params": params}).encode("utf-8")
    request = urllib.request.Request(
        BASE_RPC, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.loads(response.read().decode("utf-8"))
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}


def usdc_balance() -> int | None:
    raw = _rpc("eth_call", [{"to": USDC_BASE,
                             "data": "0x70a08231" + "0" * 24 + WALLET[2:]},
                            "latest"]).get("result")
    return int(raw, 16) if raw and raw != "0x" else None


def settlements_as_owner(from_block: int) -> list[dict]:
    """PaymentSettled events where `owner` is us. `owner` is topic[3], indexed."""
    topic = "0x" + "0" * 24 + WALLET[2:]
    result = _rpc("eth_getLogs", [{"fromBlock": hex(from_block), "toBlock": "latest",
                                   "address": ROUTER,
                                   "topics": [PAYMENT_SETTLED, None, None, topic]}])
    out = []
    for log in result.get("result", []) or []:
        data = log["data"][2:]
        words = [int(data[i:i + 64], 16) for i in range(0, len(data), 64)]
        out.append({
            "block": int(log["blockNumber"], 16),
            "tx": log["transactionHash"],
            "token": "0x" + log["topics"][1][-40:],
            "payer": "0x" + log["topics"][2][-40:],
            "owner": "0x" + log["topics"][3][-40:],
            "totalAmount": words[0], "ownerAmount": words[1],
            "bankrFee": words[2], "feeBps": words[3],
        })
    return out


def endpoint_logs() -> list[dict]:
    key = config.load(Role.ANALYST).secret("BANKR_KEY_READ")
    capture = _capture.call(label="logs", url=LOGS_URL, header_name="X-API-Key",
                            header_value=key, max_body_chars=40000)
    return ((_capture.as_json(capture) or {}).get("logs") or [])


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def main() -> int:
    config.load_environment()
    confirmed = "--confirm" in sys.argv
    before = usdc_balance()
    start_block = int(_rpc("eth_blockNumber", []).get("result", "0x0"), 16)

    print("=" * 72)
    print("PROBE 0.7d — PAY OUR OWN ENDPOINT.  THIS SPENDS REAL USDC.")
    print("=" * 72)
    print(f"  endpoint   {ENDPOINT}")
    print(f"  price      ${PRICE_USD} USDC on Base")
    print(f"  wallet     {WALLET}  (payer and owner, the fund has one wallet)")
    print(f"  balance    {before} base units (${(before or 0) / 1e6:.6f}) over RPC")
    print(f"  changed    handler now returns Response.json(...) — nothing else")
    print(f"  base block {start_block}")
    print("=" * 72)

    if not confirmed:
        print("\nPre-flight only. Nothing paid. Re-run with --confirm.")
        return 0
    if before is None or before < 3000:
        print(f"\nBLOCKED, not failed: balance {before} too low. Nothing paid.")
        return 2

    print("\nPAYING ONCE. No retry.")
    started = time.monotonic()
    proc = subprocess.run(
        ["bankr", "x402", "call", ENDPOINT, "-y", "--max-payment", MAX_PAYMENT_USD],
        capture_output=True, text=True, timeout=300)
    elapsed = int((time.monotonic() - started) * 1000)
    stdout = strip_ansi(proc.stdout)
    print(f"rc={proc.returncode} in {elapsed} ms")
    print(stdout[:1500] or strip_ansi(proc.stderr)[:900])

    result = {"endpoint": ENDPOINT, "price_usd": PRICE_USD, "wall_ms": elapsed,
              "returncode": proc.returncode, "stdout": stdout[-6000:],
              "usdc_before": before, "start_block": start_block}

    if proc.returncode != 0:
        print("\nSTOPPING: payment failed again. Not adjusting and not retrying.")
        result["verdict"] = "failed"
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "x402_paid.json").write_text(
            json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
        return 1

    # The 200 is not the proof. Poll the chain until settlement appears.
    print("\nwaiting for on-chain settlement (the 200 is not proof of it)...")
    events: list[dict] = []
    after = before
    for attempt in range(20):
        time.sleep(3)
        events = settlements_as_owner(start_block - 5)
        after = usdc_balance()
        if events:
            break
        print(f"   ...{(attempt + 1) * 3}s, no PaymentSettled yet")
    result["usdc_after"] = after
    result["usdc_delta"] = None if None in (before, after) else after - before
    result["settlements_as_owner"] = events

    print(f"\nUSDC before={before} after={after} delta={result['usdc_delta']}")
    if events:
        print(f"\nPaymentSettled with OUR ADDRESS AS OWNER — {len(events)} event(s):")
        for e in events:
            print(f"   block {e['block']}  tx {e['tx']}")
            print(f"   payer={e['payer']}")
            print(f"   owner={e['owner']}")
            print(f"   total={e['totalAmount']}  ownerAmount={e['ownerAmount']}  "
                  f"bankrFee={e['bankrFee']}  feeBps={e['feeBps']}")
    else:
        print("\nNo PaymentSettled event found as owner within the poll window.")

    logs = endpoint_logs()
    result["endpoint_logs"] = logs
    print(f"\nendpoint logs: {len(logs)} entries")
    for entry in logs[:3]:
        report = ""
        for line in (entry.get("logs") or "").replace("\r", "\n").split("\n"):
            if "Init Duration" in line or "REPORT" in line:
                report = line.strip()
        print(f"   {entry.get('createdAt')} status={entry.get('statusCode')} "
              f"settled={entry.get('settled')} durationMs={entry.get('durationMs')}")
        if report:
            print(f"      {report}")

    result["verdict"] = "settled" if events else "paid-but-unverified"
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "x402_paid.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
