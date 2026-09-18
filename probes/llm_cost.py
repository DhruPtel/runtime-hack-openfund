"""Probe 0.9 — what does one analyst call cost, in tokens, latency and dollars?

**Spends LLM credits.** One call, never a sweep, and nothing runs without
`--confirm`.

**This measures a floor, not a forecast, and the number must never be quoted
without that.** `planning/PHASE-0-1.md` relocated this unit to 1.7 precisely
because snapshot bytes dominate the token count and no snapshot exists until 1.6.
The block below is hand-assembled from real 0.4 numbers for **six** assets; a real
snapshot covers the whole admissible universe, is content-hashed, and carries
provenance and quote data per asset. The input token count will rise
substantially. Recording this as "the analyst cost" would be misleading, so every
figure it produces is labelled a floor.

**The provider cannot confirm a single call's cost.** F0.6.4 measured usage as
attributable only at `(API key × model × day-window)` — no per-request rows, no
request id. So the primary measurement is the response's own `usage` block, and
`/v1/usage` is read before and after as an *independent aggregate check* on
whether the two agree. They are different instruments, not one.

**Output quality is irrelevant here.** This measures cost, not capability. The
prompt is run once and not iterated toward a better answer.

Run:  PYTHONPATH=src python3 -m probes.llm_cost [--confirm]
"""

from __future__ import annotations

import json
import pathlib
import sys
import time

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

GATEWAY = "https://llm.bankr.bot/v1"

#: `config/models.json` has `analyst_model: null` — it is pinned at unit 2.4 and
#: informed by this measurement, so there is no "intended model" to read. Sonnet
#: is chosen as a defensible mid-tier analyst model and the choice is
#: **provisional**; the cost table below prices the same token counts across the
#: whole catalogue so the decision does not depend on this pick.
MODEL = "claude-sonnet-5"

#: The roster is four analysts plus one risk call (`config/analysts.json`,
#: and `planning/PHASE-0-1.md` 1.7 says "four analysts plus one risk call").
ANALYSTS_PER_CYCLE = 4
RISK_CALLS_PER_CYCLE = 1
CYCLES_PER_DAY = 1  # daily cadence, LESSONS 2026-09-17

#: planning/PLAN.md §11.
X402_PRICE_USD = 0.05

#: Real values measured in probe 0.4 at block 66,353,908 on chain 4663. Shaped
#: like a snapshot row without being one: a real snapshot is content-hashed,
#: covers the admissible universe, and carries per-asset provenance.
SNAPSHOT_ROWS = [
    {"symbol": "AAPL", "address": "0xaf3d76f1834a1d425780943c99ea8a608f8a93f9",
     "feed_usd": 335.3847, "feed_decimals": 8, "ui_multiplier": 1.0005660800610925,
     "updated_at": 1789744288, "corroborator_usd": 334.7069, "quote_usd": 334.9733,
     "divergence_bps": 20.3, "pool_vol_24h_usd": 12349658.22,
     "pool_reserve_usd": 3025580.58},
    {"symbol": "NVDA", "address": "0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec",
     "feed_usd": 219.3155, "feed_decimals": 8, "ui_multiplier": 1.0007751591646306,
     "updated_at": 1789741887, "corroborator_usd": 219.3661, "quote_usd": 219.6670,
     "divergence_bps": -2.3, "pool_vol_24h_usd": 54904178.96,
     "pool_reserve_usd": 14169726.56},
    {"symbol": "TSLA", "address": "0x322f0929c4625ed5bad873c95208d54e1c003b2d",
     "feed_usd": 361.8450, "feed_decimals": 8, "ui_multiplier": 1.0,
     "updated_at": 1789746163, "corroborator_usd": 364.3306, "quote_usd": 362.2910,
     "divergence_bps": -68.2, "pool_vol_24h_usd": 5676292.26,
     "pool_reserve_usd": 3051919.31},
    {"symbol": "SPY", "address": "0x117cc2133c37b721f49de2a7a74833232b3b4c0c",
     "feed_usd": 761.5508, "feed_decimals": 8, "ui_multiplier": 1.001717991187472,
     "updated_at": 1789734121, "corroborator_usd": 760.1769, "quote_usd": 759.6787,
     "divergence_bps": 18.1, "pool_vol_24h_usd": 68773085.99,
     "pool_reserve_usd": 16227942.78},
    {"symbol": "ORCL", "address": "0xb0992820e760d836549ba69bc7598b4af75dee03",
     "feed_usd": 145.6573, "feed_decimals": 8, "ui_multiplier": 1.0022109149710134,
     "updated_at": 1789741078, "corroborator_usd": 148.1544, "quote_usd": 146.0255,
     "divergence_bps": -168.5, "pool_vol_24h_usd": 105544.87,
     "pool_reserve_usd": 76885.18},
    {"symbol": "GME", "address": "0x1b0e319c6a659f002271b69db8a7df2f911c153e",
     "feed_usd": 22.5650, "feed_decimals": 8, "ui_multiplier": 1.0,
     "updated_at": 1789746671, "corroborator_usd": 22.5444, "quote_usd": 22.5462,
     "divergence_bps": 9.1, "pool_vol_24h_usd": 3432018.78,
     "pool_reserve_usd": 1775129.48},
]

#: A rough version of the brief, not the brief. The real one is settled at
#: checkpoint 2.1 and this deliberately does not try to anticipate it — it exists
#: to be the right *shape* and roughly the right length.
SYSTEM_PROMPT = """You are one of four analysts in an autonomous onchain fund.
You receive a frozen, block-pinned market snapshot and return a structured report.

Rules that bind you:
- Answer only from the snapshot. It is the complete set of facts available.
- NO_CALL is a valid and respected answer. Do not manufacture a view.
- Every claim must cite the field it rests on.
- You do not size trades, you do not decide execution, and you have no spend
  authority. Your report is one input among several.
- Return strict JSON matching the schema given. No prose outside the JSON.
"""

USER_TEMPLATE = """## Your scope

Analyst id: price-trend
Objective: recent price action and trend for the assets assigned to you.

## Snapshot

chain_id: 4663
block: 66353908
snapshot_hash: 0e2b1c9f4a7d8e5b3c6a1f0d9b8e7c4a2f5d3b1e8c7a6f4d2b9e0c3a5f1d7b8e
captured_at: 2026-09-18T15:52:00Z
mark_basis: chainlink_feed
corroborator: geckoterminal_pool

{rows}

## Field notes

- feed_usd is the Chainlink mark, {decimals} decimals, already multiplier-adjusted.
- ui_multiplier is the ERC-8056 corporate-action factor; do NOT apply it again.
- divergence_bps is signed: feed against corroborator. Negative means the feed is
  below the corroborator.
- quote_usd is the execution venue's own price and is NOT independent of it.
- updated_at is a unix timestamp; feeds carry an 86400s heartbeat and a 0.5%
  deviation threshold, so a feed hours old during market hours is normal.
- pool_vol_24h_usd describes the corroborator's quality, not our fill. Execution
  is RFQ against USDG.

## Required output

Strict JSON:
{{"reports": [{{"symbol": str, "call": "BUY"|"SELL"|"HOLD"|"NO_CALL",
  "confidence": 0.0-1.0, "reasoning": str, "cites": [str]}}],
  "abstained": [str], "notes": str}}
"""


def build_prompt() -> tuple[str, str]:
    rows = "\n".join(
        "- " + json.dumps(row, sort_keys=True) for row in SNAPSHOT_ROWS)
    return SYSTEM_PROMPT, USER_TEMPLATE.format(rows=rows, decimals=8)


def usage_snapshot(key: str) -> dict:
    capture = _capture.call(label="usage", url=f"{GATEWAY}/usage",
                            header_name="X-API-Key", header_value=key,
                            max_body_chars=8000)
    return (_capture.as_json(capture) or {}).get("totals") or {}


def credits(key: str) -> float | None:
    capture = _capture.call(label="credits", url=f"{GATEWAY}/credits",
                            header_name="X-API-Key", header_value=key,
                            max_body_chars=4000)
    return (_capture.as_json(capture) or {}).get("balanceUsd")


def price_table() -> dict:
    capture = _capture.call(label="models", url=f"{GATEWAY}/models",
                            header_name="X-API-Key",
                            header_value=config.load(Role.ANALYST).secret("BANKR_LLM_KEY"),
                            max_body_chars=200000)
    data = (_capture.as_json(capture) or {}).get("data") or []
    return {m["id"]: m.get("pricing", {}) for m in data}


def main() -> int:
    config.load_environment()
    confirmed = "--confirm" in sys.argv
    key = config.load(Role.ANALYST).secret("BANKR_LLM_KEY")

    system, user = build_prompt()
    approx_chars = len(system) + len(user)

    print("=" * 72)
    print("UNIT 0.9 — ANALYST COST.  THIS SPENDS LLM CREDITS.")
    print("=" * 72)
    print(f"  model        {MODEL}  (provisional: config/models.json is null)")
    print(f"  prompt       {approx_chars} chars across system + user")
    print(f"  snapshot     {len(SNAPSHOT_ROWS)} assets, hand-assembled from 0.4")
    print(f"  balance      ${credits(key)}")
    print(f"  calls        1")
    print(f"  FLOOR ONLY   a real snapshot (unit 1.6) covers the whole universe")
    print("=" * 72)

    if not confirmed:
        print("\nPre-flight only. Nothing spent. Re-run with --confirm.")
        return 0

    before_usage = usage_snapshot(key)
    before_credits = credits(key)

    started = time.monotonic()
    capture = _capture.call(
        label="analyst-call", url=f"{GATEWAY}/chat/completions",
        header_name="X-API-Key", header_value=key, max_body_chars=30000,
        json_body={
            "model": MODEL,
            "messages": [{"role": "system", "content": system},
                         {"role": "user", "content": user}],
            "max_tokens": 2000,
            "temperature": 0,
        },
    )
    latency_ms = int((time.monotonic() - started) * 1000)
    parsed = _capture.as_json(capture) or {}
    usage = parsed.get("usage") or {}

    print(f"\nHTTP {capture.status} in {latency_ms} ms")
    if capture.status != 200:
        print(capture.body[:1200])
        return 1

    prompt_tokens = usage.get("prompt_tokens")
    completion_tokens = usage.get("completion_tokens")
    total_tokens = usage.get("total_tokens")
    print(f"usage: {json.dumps(usage, sort_keys=True)}")

    pricing = price_table().get(MODEL, {})
    in_rate = pricing.get("input", 0) / 1e6
    out_rate = pricing.get("output", 0) / 1e6
    call_cost = (prompt_tokens or 0) * in_rate + (completion_tokens or 0) * out_rate

    # Let the aggregate settle, then read it as an independent check.
    time.sleep(8)
    after_usage = usage_snapshot(key)
    after_credits = credits(key)
    delta = {k: (after_usage.get(k, 0) - before_usage.get(k, 0))
             for k in set(before_usage) | set(after_usage)}

    per_cycle_calls = ANALYSTS_PER_CYCLE + RISK_CALLS_PER_CYCLE
    result = {
        "model": MODEL, "latency_ms": latency_ms, "usage": usage,
        "pricing_per_million": pricing, "call_cost_usd": call_cost,
        "prompt_chars": approx_chars, "snapshot_assets": len(SNAPSHOT_ROWS),
        "usage_before": before_usage, "usage_after": after_usage,
        "usage_delta": delta,
        "credits_before": before_credits, "credits_after": after_credits,
        "credits_delta": (None if None in (before_credits, after_credits)
                          else round(after_credits - before_credits, 8)),
        "per_cycle_calls": per_cycle_calls,
        "cost_per_cycle_usd": call_cost * per_cycle_calls,
        "cost_per_day_usd": call_cost * per_cycle_calls * CYCLES_PER_DAY,
        "cost_per_month_usd": call_cost * per_cycle_calls * CYCLES_PER_DAY * 30,
        "x402_price_usd": X402_PRICE_USD,
        "records_to_break_even_per_cycle": (
            (call_cost * per_cycle_calls) / X402_PRICE_USD if call_cost else None),
        "response_text": ((parsed.get("choices") or [{}])[0]
                          .get("message", {}).get("content", ""))[:400],
    }

    print(f"\ncost of this call: ${call_cost:.6f} "
          f"(in {in_rate * 1e6}/M, out {out_rate * 1e6}/M)")
    print(f"\n/v1/usage delta across the call — the independent check:")
    for k in sorted(delta):
        print(f"   {k:32} {delta[k]}")
    print(f"credits: {before_credits} -> {after_credits} "
          f"(delta {result['credits_delta']})")

    print(f"\nmultiplied out ({per_cycle_calls} calls per cycle, "
          f"{CYCLES_PER_DAY}/day) — ALL FLOORS:")
    print(f"   per analyst call   ${call_cost:.6f}")
    print(f"   per cycle          ${result['cost_per_cycle_usd']:.6f}")
    print(f"   per day            ${result['cost_per_day_usd']:.6f}")
    print(f"   per 30 days        ${result['cost_per_month_usd']:.4f}")
    print(f"   records sold at ${X402_PRICE_USD} to cover one cycle: "
          f"{result['records_to_break_even_per_cycle']:.3f}")

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "llm_cost.json"
    path.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
