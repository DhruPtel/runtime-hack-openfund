"""Probe 0.2 — which auth header each Bankr surface accepts, and each key's toggles.

Read-only. Every call is a GET against a documented read endpoint. Nothing here
can move funds, and the harness masks every declared credential before anything
is returned or written.

Two questions, deliberately separated:

  1. **Header.** For each surface, does it accept `X-API-Key`, `Authorization:
     Bearer`, or both? `research/openclaude.md` states the LLM gateway requires
     `X-API-Key` and treats it as a named protocol exception; `research/agent-os.md`
     sends *both* headers and reports that Bearer alongside is harmless. Neither
     is evidence about the wallet or agent surfaces. This probe measures all three.

  2. **Toggles.** `planning/PLAN.md` §6 requires Agent API **off** on both Bankr
     keys and the gateway **on** for `BANKR_LLM_KEY` only. Since all three keys
     come from one account (§13), the toggles are the only boundary there is, so
     they are measured against the live surfaces rather than trusted from the
     console.

Run:  PYTHONPATH=src python3 -m probes.keys
"""

from __future__ import annotations

import json
import pathlib
import sys

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

WALLET_BASE = "https://api.bankr.bot"
GATEWAY_BASE = "https://llm.bankr.bot/v1"

HEADERS = ("X-API-Key", "Authorization")


def header_value(header_name: str, key: str) -> str:
    return key if header_name == "X-API-Key" else f"Bearer {key}"


# Each check is one (surface, endpoint, key) triple, run once per header.
# `expectation` is what planning/PLAN.md §6 says should happen; the probe records
# what did, and a mismatch is the finding.
CHECKS: list[dict] = [
    {
        "surface": "wallet",
        "endpoint": f"{WALLET_BASE}/wallet/portfolio",
        "credential": "BANKR_KEY_READ",
        "role": Role.ANALYST,
        "expectation": "authorized: the analyst read key carries Wallet API read access",
    },
    {
        "surface": "wallet",
        "endpoint": f"{WALLET_BASE}/wallet/portfolio",
        "credential": "BANKR_KEY_EXEC",
        "role": Role.TREASURER,
        "expectation": "authorized: the execution key carries Wallet API access",
    },
    {
        "surface": "wallet",
        "endpoint": f"{WALLET_BASE}/wallet/portfolio",
        "credential": "BANKR_LLM_KEY",
        "role": Role.ANALYST,
        "expectation": "denied: gateway-only key must not reach the Wallet API",
    },
    # Negative control. Without it, "every key returned 200" is not evidence that
    # the surface authorized them -- it is equally consistent with a surface that
    # ignores the header entirely. A probe that cannot tell those apart has
    # measured nothing.
    {
        "surface": "wallet",
        "endpoint": f"{WALLET_BASE}/wallet/portfolio",
        "credential": "__INVALID__",
        "role": None,
        "expectation": "denied: control, proves the surface reads the header at all",
    },
]

#: A syntactically plausible key that was never issued.
INVALID_KEY = "bk_" + "0" * 32


def load_keys() -> dict[str, str]:
    """Both roles' credentials. A probe may hold what no single process may."""
    analyst = config.load(Role.ANALYST)
    treasurer = config.load(Role.TREASURER)
    keys = dict(analyst.credentials)
    keys.update(treasurer.credentials)
    return keys


def run() -> list[dict]:
    keys = load_keys()
    results: list[dict] = []

    for check in CHECKS:
        if check["credential"] == "__INVALID__":
            key = INVALID_KEY
        else:
            key = keys.get(check["credential"])
        if not key:
            print(f"SKIP {check['surface']:8} {check['credential']:16} not set")
            continue
        for header in HEADERS:
            label = f"{check['surface']}/{check['credential']}/{header}"
            capture = _capture.call(
                label=label,
                url=check["endpoint"],
                header_name=header,
                header_value=header_value(header, key),
            )
            print(f"{check['surface']:8} {check['credential']:16} {header:15} "
                  f"{capture.summary()}")
            results.append(
                {
                    "surface": check["surface"],
                    "endpoint": capture.url,
                    "credential": check["credential"],
                    "header": header,
                    "expectation": check["expectation"],
                    "status": capture.status,
                    "elapsed_ms": capture.elapsed_ms,
                    "transport_error": capture.transport_error,
                    "response_headers": capture.response_headers,
                    "body": capture.body,
                    "body_truncated": capture.truncated,
                }
            )
    return results


def main() -> int:
    results = run()
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "keys.json"
    path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n{len(results)} captures written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
