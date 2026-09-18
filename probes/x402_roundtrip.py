"""Probe 0.7 — x402 round trip: timing, payability, and the payer header.

**This unit spends USDC on Base.** It will not pay anything without `--confirm`,
and it prints the endpoint, the price, the wallet and the balance before it does.

Three timings, and they are not interchangeable:

  - **unpaid** — the 402 challenge. Free, and it never reaches our handler,
    because the payment gate sits in front of it.
  - **paid, cold** — the first call that actually invokes the handler container.
    This is what a real first caller experiences, and it is the number that
    decides whether the cached-record design is *required* rather than merely
    prudent.
  - **paid, warm** — a second call against a container that is already up.

Reporting the warm number as typical would be the easy mistake here, so the two
are measured and reported separately and never averaged.

**The handler does no work** (`x402/roundtrip/index.ts` returns a frozen
literal). That is deliberate: anything it did would be added to every number
above and could not be separated out afterwards, and the question is what the
*platform* costs, not what our code costs.

**On what "a standard client" means here, because it bounds the verdict.** The
fund's wallet is custodial — Bankr holds its EVM key — so we cannot sign an
EIP-3009 authorization ourselves and cannot drive `x402-fetch` directly. Payment
therefore goes through `bankr x402 call`. What that measures is a *Bankr-wallet*
client paying us. The separate question `research/x402-cli-example.md` raises —
whether a standard `x402-fetch` client could pay this endpoint — is settled from
the **challenge body**, not from the payment: that report established that
`NetworkSchema` is a closed enum which rejects chain 4663 outright, so what
matters is which network and asset our challenge actually advertises.

Run:  PYTHONPATH=src python3 -m probes.x402_roundtrip [--confirm]
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
ENDPOINT = f"https://x402.bankr.bot/{WALLET}/roundtrip"
PRICE_USD = "0.001"

#: Base mainnet USDC, pinned from `research/x402-cli-example.md` §7.
USDC_BASE = "0x833589fCD6eDb6E08f4c7C32D4f71b54bdA02913"
BASE_RPC = "https://mainnet.base.org"

USER_AGENT = "openfund-probe/0.7"

#: `bankr x402 call` caps payment in USD. Set barely above the price: the point
#: is that a cap exists and is ours to set, and a probe should not authorise
#: more than the thing it is buying costs.
MAX_PAYMENT_USD = "0.01"


def usdc_balance() -> int | None:
    """Read USDC over RPC rather than from the portfolio endpoint.

    Not a stylistic choice. The Bankr portfolio endpoint reported
    `tokenBalances: []` for this wallet on this date while the token contract
    reported a non-zero balance, so the portfolio under-reports (F0.7.1).
    `planning/PLAN.md` §6 already requires the treasurer to read balances over
    RPC; this is the measurement behind that requirement.
    """
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


def timed_get(url: str) -> dict:
    """One unpaid GET, timed. A 402 is the expected answer, not a failure."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=60) as response:
            status, body, headers = response.status, response.read(), response.headers
    except urllib.error.HTTPError as error:
        status, body, headers = error.code, error.read(), error.headers
    except Exception as error:
        return {"error": f"{type(error).__name__}: {error}",
                "elapsed_ms": int((time.monotonic() - started) * 1000)}
    elapsed = int((time.monotonic() - started) * 1000)
    text = body.decode("utf-8", errors="replace")
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    return {"status": status, "elapsed_ms": elapsed, "body": text,
            "parsed": parsed, "headers": dict(headers)}


def timed_cli(args: list[str]) -> dict:
    """One CLI invocation, wall-clock timed.

    The number includes node startup and the CLI's own work, which is why
    `cli_baseline` below is measured and reported alongside rather than quietly
    subtracted — an adjusted figure presented as a measurement is worse than two
    honest ones.
    """
    started = time.monotonic()
    proc = subprocess.run(args, capture_output=True, text=True, timeout=300)
    elapsed = int((time.monotonic() - started) * 1000)
    return {"args": args, "elapsed_ms": elapsed, "returncode": proc.returncode,
            "stdout": proc.stdout[-4000:], "stderr": proc.stderr[-2000:]}


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*[A-Za-z]", "", text)


def main() -> int:
    confirmed = "--confirm" in sys.argv
    results: dict = {"endpoint": ENDPOINT, "price_usd": PRICE_USD, "wallet": WALLET}

    before = usdc_balance()

    # --- the unpaid call. Free, and it is the evidence for payability. --------
    unpaid = timed_get(ENDPOINT)
    results["unpaid"] = unpaid

    print("=" * 72)
    print("UNIT 0.7 — x402 ROUND TRIP.  THE PAID CALLS SPEND REAL USDC.")
    print("=" * 72)
    print(f"  endpoint   {ENDPOINT}")
    print(f"  price      ${PRICE_USD} USDC per request")
    print(f"  wallet     {WALLET}  (payer and payee are the same wallet)")
    print(f"  balance    {before} USDC base units "
          f"(${(before or 0) / 1e6:.6f}) read over RPC")
    print(f"  max spend  ${MAX_PAYMENT_USD} per call, 2 paid calls authorised")
    print(f"  handler    static literal, no work")
    print("=" * 72)

    print(f"\nunpaid  HTTP {unpaid.get('status')} in {unpaid.get('elapsed_ms')} ms")
    print(json.dumps(unpaid.get("parsed"), indent=2, sort_keys=True)
          if unpaid.get("parsed") else unpaid.get("body", "")[:600])

    if not confirmed:
        print("\nPre-flight only. Nothing was paid. Re-run with --confirm.")
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "x402.json").write_text(
            json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        return 0

    if before is None or before < 3000:
        print(f"\nBLOCKED, not failed: USDC balance {before} base units is below "
              f"the 3 paid calls this probe may need. Nothing paid.")
        return 2

    # CLI startup baseline, so the paid numbers can be read honestly.
    results["cli_baseline"] = timed_cli(["bankr", "x402", "schema", ENDPOINT])
    print(f"\ncli baseline (unauthenticated read, no payment): "
          f"{results['cli_baseline']['elapsed_ms']} ms")

    call = ["bankr", "x402", "call", ENDPOINT, "-y",
            "--max-payment", MAX_PAYMENT_USD, "--raw"]

    print("\nPAYING (cold) — one call, no retry.")
    cold = timed_cli(call)
    results["paid_cold"] = cold
    print(f"cold   rc={cold['returncode']} in {cold['elapsed_ms']} ms")
    print(strip_ansi(cold["stdout"])[:1200] or strip_ansi(cold["stderr"])[:800])

    if cold["returncode"] != 0:
        print("\nSTOPPING: the paid call failed. Not adjusting price or asset "
              "and not retrying — the failure is the result.")
        OUT_DIR.mkdir(exist_ok=True)
        (OUT_DIR / "x402.json").write_text(
            json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
        return 1

    print("\nPAYING (warm) — one call, no retry.")
    warm = timed_cli(call)
    results["paid_warm"] = warm
    print(f"warm   rc={warm['returncode']} in {warm['elapsed_ms']} ms")
    print(strip_ansi(warm["stdout"])[:1200] or strip_ansi(warm["stderr"])[:800])

    after = usdc_balance()
    results["usdc_before"] = before
    results["usdc_after"] = after
    results["usdc_delta"] = None if after is None or before is None else after - before

    print(f"\nUSDC before={before} after={after} delta={results['usdc_delta']} "
          f"base units (6dp)")
    print(f"\ntimings: unpaid {unpaid.get('elapsed_ms')} ms | "
          f"cold {cold['elapsed_ms']} ms | warm {warm['elapsed_ms']} ms "
          f"| cli baseline {results['cli_baseline']['elapsed_ms']} ms")

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "x402.json"
    path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
