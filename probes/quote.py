"""Probe 0.3 — the real response shape of a stock quote on 4663.

Read-only. `POST /wallet/swap-quote` is documented as ungated and returns a
price, not an order; nothing here can move funds.

**Sizing caveat, stated up front because it bounds every conclusion.** The fund
wallet holds roughly $2 of ETH on Base and nothing on Robinhood Chain (finding
F0.2.6). `planning/PLAN.md` §11 sets the nominal quoting size at $25, and unit
1.5's whole point is that a small quote tells you nothing about a real position.
So this is a **shape probe, not a realistic-size probe**: it establishes which
fields exist and which are absent, and it deliberately asks for $25 as well as $5
to learn whether the endpoint prices a size the wallet cannot cover. Unit 1.5
must be re-run against a funded wallet before any of this is treated as evidence
about executable liquidity.

Request schema is from `https://docs.bankr.bot/wallet-api/swap/`, read on
2026-09-17, because the endpoint answers every malformed body with an identical
`{"message":"Invalid request body"}` and leaks no field names. Note `amount` is
**human-readable** ("5"), not raw base units.

Run:  PYTHONPATH=src python3 -m probes.quote
"""

from __future__ import annotations

import json
import pathlib
import sys

from fund import config
from fund.credentials import Role

from . import _capture, assets

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
URL = "https://api.bankr.bot/wallet/swap-quote"
CHAIN = "robinhood"

#: $5 is what the wallet could plausibly cover; $25 is the nominal size from
#: planning/PLAN.md §11. Asking for both is the point: quotes are documented as
#: ungated, so whether an unfundable size still prices is itself a finding.
SIZES_USDG = ("5", "25")

#: Several tickers, because PHASE-0-1 0.3 warns that a single stock with no quote
#: returns an error that looks like a bug.
TICKERS = ("AAPL", "NVDA", "TSLA")

#: Documented as guaranteed in the response. Everything else is observed.
DOCUMENTED_FIELDS = (
    "from", "to", "minBuyAmount", "feeBps", "feeWaivedForEcosystemToken",
    "slippageBps", "priceImpactBps", "swapImpactBps", "maxPriceImpactBps",
    "sellTokenPriceUsd", "buyTokenPriceUsd", "quoteId",
)


def body_for(ticker: str, amount: str) -> dict:
    return {
        "fromChain": CHAIN,
        "fromToken": assets.CANDIDATES["USDG"]["address"],
        "toChain": CHAIN,
        "toToken": assets.CANDIDATES[ticker]["address"],
        "amount": amount,
    }


def run() -> list[dict]:
    key = config.load(Role.ANALYST).secret("BANKR_KEY_READ")
    results: list[dict] = []

    for ticker in TICKERS:
        for amount in SIZES_USDG:
            label = f"quote/{ticker}/{amount}USDG"
            capture = _capture.call(
                label=label, url=URL, header_name="X-API-Key", header_value=key,
                json_body=body_for(ticker, amount),
                # The response shape is the subject of this probe, so it must
                # arrive whole and parseable.
                max_body_chars=4000,
            )
            parsed = _capture.as_json(capture)
            present = sorted(parsed.keys()) if isinstance(parsed, dict) else []
            print(f"{ticker:5} {amount:>3} USDG -> {capture.summary():24} "
                  f"fields={len(present)}")
            results.append(
                {
                    "label": label,
                    "ticker": ticker,
                    "amount_usdg": amount,
                    "request_body": capture.request_body,
                    "status": capture.status,
                    "elapsed_ms": capture.elapsed_ms,
                    "transport_error": capture.transport_error,
                    "response_headers": capture.response_headers,
                    "body": capture.body,
                    "body_truncated": capture.truncated,
                    "fields_present": present,
                    "documented_but_absent": sorted(
                        set(DOCUMENTED_FIELDS) - set(present)
                    ) if present else [],
                    "present_but_undocumented": sorted(
                        set(present) - set(DOCUMENTED_FIELDS)
                    ),
                }
            )
    return results


def main() -> int:
    results = run()
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "quote.json"
    path.write_text(json.dumps(results, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n{len(results)} captures written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
