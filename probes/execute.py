"""Probe 0.5 — execution eligibility. **This one spends money.**

Every other probe in this directory is read-only. This one signs and broadcasts a
real transaction with the real execution key, so it will not send anything unless
invoked with `--confirm`:

    PYTHONPATH=src python3 -m probes.execute            # pre-flight only, sends nothing
    PYTHONPATH=src python3 -m probes.execute --confirm  # sends once

**Goal.** `planning/PHASE-0-1.md` 0.5 calls this the binary that decides whether
Phase 5 exists. The expected verdict is **fail** — Bankr gates tokenized-stock
execution behind a location check that excludes the US and the operator is
US-based (`research/bankr-skills.md`, quoting `tokenized-stocks.md:73-79`) — and
it is run anyway, because a documented claim is not a measurement and because the
exact refusal body is what unit 5.6 has to decode at 2am.

**The second question, which matters as much as the verdict.** A 403 on
`/wallet/swap` has seven documented causes behind one status code. If the body
cannot tell a location refusal from a read-only key, the treasurer cannot surface
a useful error and every failure looks identical. So this probe narrows the
candidates *before* spending anything — four of the seven are excluded by a free
quote and by the size we chose — and then reports whether the body distinguishes
what is left.

**What we do not do.** No retry. A refusal is the result; adjusting parameters
until something goes through would tell us nothing about the gate and would cost
gas each time. One send, one capture.

Run:  PYTHONPATH=src python3 -m probes.execute [--confirm]
"""

from __future__ import annotations

import json
import pathlib
import sys
import uuid

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

QUOTE_URL = "https://api.bankr.bot/wallet/swap-quote"
SWAP_URL = "https://api.bankr.bot/wallet/swap"
PORTFOLIO_URL = "https://api.bankr.bot/wallet/portfolio"
CHAIN = "robinhood"

#: The native-gas sentinel, documented at `https://docs.bankr.bot/wallet-api/swap/`
#: read 2026-09-18: "For native ETH / POL / BNB, pass the native sentinel address
#: 0xeeee…eeee (the zero address works too)". We sell native ETH because it is the
#: only thing the wallet holds on 4663 — there is no USDG (F0.2.6 still holds for
#: tokens), and quoting from a balance we do not have would fail on funds rather
#: than at the gate this probe exists to test.
NATIVE_SENTINEL = "0xeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee"

#: Apple. Chosen because it is the best-evidenced address we have: it carries a
#: Chainlink equity feed (F0.4.1), answers `uiMultiplier()` (F0.4.6), and has
#: twenty pools with $3M of reserve behind it (F0.4.3). Picking a thinly-evidenced
#: address would risk a refusal that is really about the address.
STOCK_SYMBOL = "AAPL"
STOCK_ADDRESS = "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9"

#: 0.0001 ETH, about $0.26. The smallest size that still quotes cleanly. Small on
#: purpose: it puts the trade three orders of magnitude below the $500 platform
#: caps and keeps price impact near zero, so neither can be the reason for a
#: refusal.
SELL_AMOUNT_ETH = "0.0001"

#: Native balance we refuse to dip below, so the send cannot fail for gas.
#: `planning/PHASE-0-1.md` 0.5 is only meaningful if the refusal fires at the gate
#: being tested; running the tank dry would produce a different failure wearing
#: the same status code.
GAS_RESERVE_ETH = 0.0002

#: ERC-20 `balanceOf(address)`.
SELECTOR_BALANCE_OF = "0x70a08231"


# --- the seven documented causes of a 403 on this endpoint -------------------
#
# From `https://docs.bankr.bot/wallet-api/swap/`, read 2026-09-18. The Errors
# table names six; the seventh comes from the Access Control section on the same
# page, which says token-security refusals apply "at both quote and execution".
# That split is recorded rather than smoothed over: six are quoted, one is
# reconstructed, and the reconstruction is labelled.
#
# `excluded_by` is what lets this probe say something sharper than "we got a
# 403". Each entry names the evidence that rules the cause out *before* the
# send, or None if only the response body can settle it.

DOCUMENTED_403_CAUSES = (
    {
        "id": "read_only_key",
        "text": "Read-only API key",
        "source": "Errors table",
        "excluded_by": None,
    },
    {
        "id": "wallet_paused",
        "text": "Wallet paused",
        "source": "Errors table",
        "excluded_by": None,
    },
    {
        "id": "price_impact",
        "text": "Price impact above your wallet's own protection limit",
        "source": "Errors table",
        "excluded_by": "quote: swapImpactBps far below maxPriceImpactBps",
    },
    {
        "id": "location_check",
        "text": "Failed location check",
        "source": "Errors table",
        "excluded_by": None,
    },
    {
        "id": "fee_beneficiary",
        "text": "Fee beneficiary selling its own fee token",
        "source": "Errors table",
        "excluded_by": "structural: this wallet is not a fee beneficiary, and feeBps is 0",
    },
    {
        "id": "spend_limit",
        "text": "A Bankr Terminal spend limit would be exceeded",
        "source": "Errors table",
        "excluded_by": "size: ~$0.26 against documented $500/tx and $500/24h caps",
    },
    {
        "id": "banned_token",
        "text": "Buy token is banned or flagged by the security scan",
        "source": "Access Control section (reconstructed; not in the Errors table)",
        "excluded_by": "quote: token-security refusals apply at quote too, and the quote returned 200",
    },
)


def _preflight_balance(key: str) -> tuple[float, dict]:
    """What the wallet actually holds on 4663, before anything is sent."""
    capture = _capture.call(label="preflight/portfolio", url=PORTFOLIO_URL,
                            header_name="X-API-Key", header_value=key,
                            max_body_chars=8000)
    parsed = _capture.as_json(capture) or {}
    robinhood = (parsed.get("balances") or {}).get(CHAIN, {})
    native = float(robinhood.get("nativeBalance") or 0)
    return native, {
        "status": capture.status,
        "evm_address": parsed.get("evmAddress"),
        "native_balance_eth": robinhood.get("nativeBalance"),
        "native_usd": robinhood.get("nativeUsd"),
        "token_balances": robinhood.get("tokenBalances"),
    }


def quote(key: str) -> tuple[dict, dict]:
    """A fresh quote with the execution identity, not the read key.

    `planning/PHASE-0-1.md` 0.5 asks for "the intended execution identity and
    production-shaped permissions", and the treasurer will quote with its own key
    in Phase 4. Quoting with the read key here would test a path we do not ship.
    """
    capture = _capture.call(
        label="quote", url=QUOTE_URL, header_name="X-API-Key", header_value=key,
        max_body_chars=4000,
        json_body={
            "fromChain": CHAIN, "fromToken": NATIVE_SENTINEL,
            "toChain": CHAIN, "toToken": STOCK_ADDRESS,
            "amount": SELL_AMOUNT_ETH,
        },
    )
    return _capture.as_json(capture) or {}, {
        "status": capture.status, "elapsed_ms": capture.elapsed_ms,
        "request_body": capture.request_body, "body": capture.body,
        "response_headers": capture.response_headers,
    }


def narrow_causes(quoted: dict) -> list[dict]:
    """Which of the seven a 403 could still be, given what we already know."""
    impact = quoted.get("swapImpactBps")
    limit = quoted.get("maxPriceImpactBps")
    impact_is_safe = (
        impact is not None and limit is not None and impact < limit
    )
    causes = []
    for cause in DOCUMENTED_403_CAUSES:
        excluded = cause["excluded_by"]
        # The price-impact exclusion is the one that depends on this run's
        # numbers rather than on the size or the structure, so it is re-derived
        # from the quote instead of asserted.
        if cause["id"] == "price_impact" and not impact_is_safe:
            excluded = None
        causes.append({**cause, "excluded_by": excluded,
                       "still_possible": excluded is None})
    return causes


def main() -> int:
    config.load_environment()
    confirmed = "--confirm" in sys.argv

    # The execution key. Loaded through the treasurer role, which is the only
    # role permitted to hold it; an analyst asking for it raises.
    key = config.load(Role.TREASURER).secret("BANKR_KEY_EXEC")

    native, portfolio = _preflight_balance(key)
    quoted, quote_capture = quote(key)

    if quote_capture["status"] != 200:
        print(f"quote failed: HTTP {quote_capture['status']}\n{quote_capture['body']}")
        print("\nSTOPPING. Without a quote there is no minBuyAmount to send, and a "
              "refusal here would be about the quote, not the execution gate.")
        return 1

    causes = narrow_causes(quoted)
    possible = [c for c in causes if c["still_possible"]]

    print("=" * 72)
    print("UNIT 0.5 — EXECUTION ELIGIBILITY.  THIS SENDS A REAL TRANSACTION.")
    print("=" * 72)
    print(f"  wallet     {portfolio['evm_address']}")
    print(f"  chain      {CHAIN} (4663)")
    print(f"  sell       {SELL_AMOUNT_ETH} ETH  (~${quoted['from'].get('usdValue')})")
    print(f"  buy        {STOCK_SYMBOL}  {STOCK_ADDRESS}")
    print(f"  expect     {quoted['to'].get('formattedAmount')} {STOCK_SYMBOL}, "
          f"min {quoted.get('minBuyAmount')}")
    print(f"  impact     swapImpactBps {quoted.get('swapImpactBps')} against a "
          f"limit of {quoted.get('maxPriceImpactBps')}")
    print(f"  balance    {portfolio['native_balance_eth']} ETH "
          f"(${portfolio['native_usd']}), reserve {GAS_RESERVE_ETH} ETH for gas")
    print(f"  key        BANKR_KEY_EXEC (treasurer role, can_transact=True)")
    print()
    print(f"  a 403 could still be {len(possible)} of 7 documented causes:")
    for cause in causes:
        mark = "?" if cause["still_possible"] else "x"
        note = "" if cause["still_possible"] else f"  <- ruled out by {cause['excluded_by']}"
        print(f"    [{mark}] {cause['text']}{note}")
    print("=" * 72)

    # The blocked-not-failed check. planning/PHASE-0-1.md 0.5 is only meaningful
    # if the refusal fires at the gate being tested, and an empty tank produces a
    # different failure wearing the same status code.
    if native < float(SELL_AMOUNT_ETH) + GAS_RESERVE_ETH:
        print(f"\nBLOCKED, not failed: {native} ETH on {CHAIN} is below "
              f"{SELL_AMOUNT_ETH} + {GAS_RESERVE_ETH} reserve. A send from here "
              f"would fail on funds, not at the gate. Nothing sent.")
        return 2

    if not confirmed:
        print("\nPre-flight only. Nothing was sent. Re-run with --confirm to send once.")
        return 0

    idempotency_key = str(uuid.uuid4())
    body = {
        "fromChain": CHAIN, "fromToken": NATIVE_SENTINEL,
        "toChain": CHAIN, "toToken": STOCK_ADDRESS,
        "amount": SELL_AMOUNT_ETH,
        "minBuyAmount": quoted["minBuyAmount"],
        "quoteId": quoted.get("quoteId"),
        "idempotencyKey": idempotency_key,
    }
    print(f"\nSENDING ONCE. idempotencyKey {idempotency_key}")
    print(json.dumps(body, indent=2, sort_keys=True))

    capture = _capture.call(
        label="swap", url=SWAP_URL, header_name="X-API-Key", header_value=key,
        json_body=body,
        # The body is the entire artifact of this probe. Truncating it would
        # discard the thing we spent money to obtain.
        max_body_chars=20000,
    )

    print(f"\n{capture.summary()}")
    print(f"headers: {capture.response_headers}")
    print(f"body:\n{capture.body}")

    result = {
        "sent": True,
        "idempotency_key": idempotency_key,
        "preflight": portfolio,
        "quote": quote_capture,
        "quote_parsed": quoted,
        "causes_before_send": causes,
        "swap": {
            "request_body": capture.request_body,
            "status": capture.status,
            "elapsed_ms": capture.elapsed_ms,
            "body": capture.body,
            "body_truncated": capture.truncated,
            "response_headers": capture.response_headers,
            "transport_error": capture.transport_error,
        },
    }
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "execute.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")

    # A 200 is not automatically a fill: the endpoint returns 200 with
    # success:false for a mined revert, and the plan requires a pass here to be
    # an actual fill rather than an absence of error.
    parsed = _capture.as_json(capture) or {}
    if capture.status == 200 and parsed.get("success") is True:
        print("\n*** UNEXPECTED SUCCESS. The swap filled. This contradicts the "
              "documented location gate and reopens Phase 5's scope and "
              "planning/PLAN.md §13. STOPPING. ***")
    return 0


if __name__ == "__main__":
    sys.exit(main())
