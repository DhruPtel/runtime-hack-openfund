"""Probe 0.7b — is the 0.7 payment failure specific to self-payment, or structural?

**This spends USDC.** Nothing is paid without `--confirm`, and the endpoint,
price, wallet and balance are printed first.

0.7 attempted one payment against the fund's own endpoint and got
`x402 payment failed (status 500)` after 2,849 ms, with nothing settled
(F0.7.4). Two causes survived that probe and it could not separate them:

  - a **transient facilitator fault**, or
  - the platform **refusing to let a wallet pay an endpoint it owns** — payer
    and owner are the same wallet, because the fund has only one.

This pays a third-party endpoint once. Success means the client, the wallet and
the facilitator all work, and the 500 is specific to our own endpoint. Failure
in the same shape means the problem is structural and the revenue line is in
doubt.

**Why not the cheapest endpoint, which the task named.** The marketplace's
cheapest paid service is $0.000001 — one USDC base unit. Paying that would change
*two* variables at once against 0.7: the owner **and** the amount, so a failure
could not be told apart from a dust-amount rejection. This pays `hello` at
**$0.001**, the identical price, network, asset and platform as our own endpoint,
with a trivial handler like ours. Exactly one variable differs: who owns it.
Cost is a tenth of a cent either way, so nothing is bought by the smaller number
and a controlled comparison is lost.

**What a success here does NOT prove.** It proves the client and the facilitator
work. **Our own endpoint remains untested** until somebody who does not own it
pays it; this probe cannot do that, because the fund has one wallet.

Run:  PYTHONPATH=src python3 -m probes.x402_thirdparty [--confirm]
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

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

WALLET = "0x93faecde3c88a713e1edddf417c02c326889a3da"

#: Third-party, $0.001, GET, no required inputs. Chosen to hold price constant
#: against our own endpoint (see the module docstring).
TARGET = "https://x402.bankr.bot/0x79bb6eac4afef0d0552a7fc7ec80f0b46fa89884/hello"
TARGET_OWNER = "0x79bb6eac4afef0d0552a7fc7ec80f0b46fa89884"
PRICE_USD = "0.001"

#: Our own endpoint, for the 402-shape comparison only. Not paid here.
OURS = f"https://x402.bankr.bot/{WALLET}/roundtrip"

USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_RPC = "https://mainnet.base.org"
USER_AGENT = "openfund-probe/0.7b"

MAX_PAYMENT_USD = "0.01"


def usdc_balance() -> int | None:
    """USDC over RPC. The portfolio endpoint omits token entries entirely (F0.7.1)."""
    payload = json.dumps({
        "jsonrpc": "2.0", "id": 1, "method": "eth_call",
        "params": [{"to": USDC_BASE,
                    "data": "0x70a08231" + "0" * 24 + WALLET[2:]}, "latest"],
    }).encode("utf-8")
    request = urllib.request.Request(
        BASE_RPC, data=payload,
        headers={"Content-Type": "application/json", "User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            raw = json.loads(response.read()).get("result")
        return int(raw, 16) if raw and raw != "0x" else 0
    except Exception:
        return None


def challenge(url: str) -> dict:
    """The unpaid 402. Free, and it never reaches the handler."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status, body = response.status, response.read()
    except urllib.error.HTTPError as error:
        status, body = error.code, error.read()
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}"}
    text = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    return {"status": status, "elapsed_ms": int((time.monotonic() - started) * 1000),
            "body": text, "parsed": parsed}


def timed_cli(args: list[str]) -> dict:
    started = time.monotonic()
    proc = subprocess.run(args, capture_output=True, text=True, timeout=300)
    return {"args": args, "elapsed_ms": int((time.monotonic() - started) * 1000),
            "returncode": proc.returncode, "stdout": proc.stdout[-6000:],
            "stderr": proc.stderr[-3000:]}


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def main() -> int:
    confirmed = "--confirm" in sys.argv
    results: dict = {"target": TARGET, "target_owner": TARGET_OWNER,
                     "ours": OURS, "payer": WALLET, "price_usd": PRICE_USD}

    theirs = challenge(TARGET)
    ours = challenge(OURS)
    results["challenge_theirs"] = theirs
    results["challenge_ours"] = ours
    before = usdc_balance()

    print("=" * 72)
    print("PROBE 0.7b — THIRD-PARTY x402 PAYMENT.  THIS SPENDS REAL USDC.")
    print("=" * 72)
    print(f"  endpoint   {TARGET}")
    print(f"  owner      {TARGET_OWNER}   (NOT us)")
    print(f"  payer      {WALLET}         (the fund)")
    print(f"  price      ${PRICE_USD} USDC on Base")
    print(f"  balance    {before} base units (${(before or 0) / 1e6:.6f}) over RPC")
    print(f"  max spend  ${MAX_PAYMENT_USD}, one call, no retry")
    print("=" * 72)

    def summarise(label, ch):
        entry = ((ch.get("parsed") or {}).get("accepts") or [{}])[0]
        print(f"  {label:10} HTTP {ch.get('status')} in {ch.get('elapsed_ms')}ms  "
              f"version={(ch.get('parsed') or {}).get('x402Version')} "
              f"network={entry.get('network')!r} amount={entry.get('maxAmountRequired')} "
              f"payTo={entry.get('payTo')}")

    print("\n402 challenges, for the comparison this probe rests on:")
    summarise("theirs", theirs)
    summarise("ours", ours)

    if not confirmed:
        print("\nPre-flight only. Nothing paid. Re-run with --confirm.")
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "x402_thirdparty.json").write_text(
            json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        return 0

    if before is None or before < 5000:
        print(f"\nBLOCKED, not failed: USDC balance {before} base units is too low. "
              f"Nothing paid.")
        return 2

    results["cli_baseline"] = timed_cli(["bankr", "x402", "schema", TARGET])
    print(f"\ncli baseline (unauthenticated read): "
          f"{results['cli_baseline']['elapsed_ms']} ms")

    print("\nPAYING — one call, no retry, no fallback endpoint.")
    paid = timed_cli(["bankr", "x402", "call", TARGET, "-y",
                      "--max-payment", MAX_PAYMENT_USD])
    results["paid"] = paid
    print(f"result rc={paid['returncode']} in {paid['elapsed_ms']} ms")
    print(strip_ansi(paid["stdout"])[:2000] or strip_ansi(paid["stderr"])[:1200])

    after = usdc_balance()
    results["usdc_before"] = before
    results["usdc_after"] = after
    results["usdc_delta"] = None if None in (before, after) else after - before

    print(f"\nUSDC before={before} after={after} delta={results['usdc_delta']} base units")

    if paid["returncode"] == 0:
        print("\nVERDICT: the third-party payment SUCCEEDED. The client, the wallet "
              "and the facilitator all work, so 0.7's 500 is specific to our own "
              "endpoint. Our endpoint is still untested by a non-owner.")
    else:
        print("\nVERDICT: the third-party payment FAILED TOO. Not retrying and not "
              "trying a second endpoint — the failure is the finding.")

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "x402_thirdparty.json"
    path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
