"""Probe 0.7d step 1 — did our handler run on the failed payment, or never get called?

Read-only, free.

0.7 left two hypotheses for the 500 (F0.7b.2): a deploy-config fault, or the
handler running and throwing. `bankr x402 revenue` reported 0 requests, which
*suggested* the handler never ran — but the pricing documentation says only
**settled** requests are counted, so a request that ran, threw, and was therefore
never charged would also show 0. The count cannot separate the hypotheses and
this probe does not rely on it.

The Bankr CLI has no `logs` command. The dashboard is documented as showing "every
request, payment, and console output", so the data exists; the path was found by
reading the installed CLI's own endpoint list (`@bankr/cli/dist/commands/x402.js`)
rather than guessed, and it answers to the ordinary read key.

Run:  PYTHONPATH=src python3 -m probes.x402_logs [service]
"""

from __future__ import annotations

import json
import pathlib
import sys

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

#: Not documented on the docs site. Read off the CLI's own source, which lists
#: /x402/endpoints, /x402/endpoints/deploy, /x402/endpoints/revenue/{name} and
#: this one alongside them.
LOGS_URL = "https://api.bankr.bot/x402/endpoints/logs/{service}"


def fetch_logs(service: str) -> dict:
    key = config.load(Role.ANALYST).secret("BANKR_KEY_READ")
    capture = _capture.call(
        label=f"logs/{service}", url=LOGS_URL.format(service=service),
        header_name="X-API-Key", header_value=key,
        # The stack trace is the artifact. Truncating it would leave us guessing
        # at the same question the probe exists to answer.
        max_body_chars=40000,
    )
    return {"status": capture.status, "parsed": _capture.as_json(capture),
            "body": capture.body}


def main() -> int:
    config.load_environment()
    service = sys.argv[1] if len(sys.argv) > 1 else "roundtrip"
    result = fetch_logs(service)
    entries = (result.get("parsed") or {}).get("logs") or []

    print(f"HTTP {result['status']} — {len(entries)} log entr"
          f"{'y' if len(entries) == 1 else 'ies'} for {service!r}\n")
    for entry in entries:
        print(f"  {entry.get('createdAt')}  {entry.get('method')} "
              f"{entry.get('routePath')}")
        print(f"  status={entry.get('statusCode')}  settled={entry.get('settled')}  "
              f"durationMs={entry.get('durationMs')}")
        print(f"  payerAddress={entry.get('payerAddress')}")
        print(f"  amount={entry.get('amountAtomic')} {entry.get('symbol')} "
              f"(${entry.get('amountUsd')})")
        print("  --- runtime output ---")
        for line in (entry.get("logs") or "").replace("\r", "\n").split("\n"):
            if line.strip():
                print(f"    {line.rstrip()}")
        print()

    # The question this probe exists to answer, stated as a boolean rather than
    # left for a reader to infer from a stack trace.
    ran = [e for e in entries if (e.get("logs") or "").strip()]
    print("=" * 68)
    print(f"handler invoked on at least one request: {bool(ran)}")
    if ran:
        print("  -> the deploy-config hypothesis is refuted: the platform routed the")
        print("     request, accepted the payment authorization and called our code.")
    print(f"any request settled: {any(e.get('settled') for e in entries)}")
    print("=" * 68)

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / f"x402_logs_{service}.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
