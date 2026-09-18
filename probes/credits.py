"""Probe 0.6 — credits and usage: can inference cost be reconciled, or only estimated?

Read-only. `GET /v1/credits` and `GET /v1/usage` are documented as reads, and the
gateway documentation states explicitly that every GET keeps working even when a
spend budget is exceeded. Nothing here can consume credits — and rather than
assert that, the probe reads the balance before and after its own calls and
reports the difference.

**Why this unit exists.** It decides whether the income statement's largest cost
line reads "cost: $X", backed by the provider's own accounting, or
"cost: $X (estimated)", backed only by tokens we counted ourselves.

**There is history, and this probe is the third position on it.**
`planning/PLAN-v1.md` §4 asserted "credit balance is not programmatically
readable, so our cost figures are our own token counts and must be labelled as
estimates". That came from `research/openclaude.md`, whose own wording was
careful — not readable *"through the path this repo used"* — and which got
generalised into a fact about the platform. `planning/REVIEW-RESPONSE.md`
finding 13 adopted the correction. This probe checks the correction against the
live surface rather than trusting either.

**Readable and attributable are different properties, and only the second helps.**
A balance we can read tells us what we spent in total. Unit 6.3 needs to know
whether a cost can be attributed to a *cycle*, an *analyst*, or a *call*. So the
probe records the field set as returned and then asks what the finest available
attribution actually is — and anything not demonstrated is recorded as inferred.

Run:  PYTHONPATH=src python3 -m probes.credits
"""

from __future__ import annotations

import json
import pathlib
import sys

from fund import config
from fund.credentials import Role

from . import _capture

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"

GATEWAY_BASE = "https://llm.bankr.bot/v1"

#: The negative control, exactly as probe 0.2 used it. Without it, a 200 is not
#: evidence of authorization — it is equally consistent with a surface that
#: ignores the header entirely (F0.2.1).
INVALID_KEY = "bk_" + "0" * 32

#: Documented at `https://docs.bankr.bot/llm-gateway/api-reference/`, read
#: 2026-09-18. Recorded so the probe can report *as returned against as
#: documented* rather than simply echoing the docs back.
DOCUMENTED_CREDITS_FIELDS = (
    "object", "balanceUsd", "effectiveBalanceUsd", "undeductedCostUsd",
    "dailyBudget",
)
DOCUMENTED_USAGE_FIELDS = ("object", "days", "startDate", "endDate", "totals", "byModel")
DOCUMENTED_TOTALS_FIELDS = (
    "totalRequests", "totalInputTokens", "totalOutputTokens",
    "totalCacheReadInputTokens", "totalCacheWriteInputTokens", "totalTokens",
    "totalCost", "totalCacheCost",
)

#: `days` is documented as 1-90, default 30. The out-of-range values are sent to
#: learn whether the bound is enforced or silently clamped: a probe that only
#: sends valid input cannot tell a validated parameter from an ignored one.
DAYS_VALUES = (None, 1, 7, 90, 0, 91)


def _call(label: str, path: str, key: str) -> dict:
    capture = _capture.call(
        label=label, url=f"{GATEWAY_BASE}{path}", header_name="X-API-Key",
        header_value=key,
        # The field set is the artifact. A truncated body would turn "the
        # response has no per-request rows" into an artefact of the capture
        # limit rather than a fact about the endpoint.
        max_body_chars=8000,
    )
    return {
        "label": label,
        "path": path,
        "status": capture.status,
        "elapsed_ms": capture.elapsed_ms,
        "body": capture.body,
        "body_truncated": capture.truncated,
        "response_headers": capture.response_headers,
        "transport_error": capture.transport_error,
        "parsed": _capture.as_json(capture),
    }


def _balance(key: str) -> float | None:
    parsed = _call("balance-check", "/credits", key).get("parsed") or {}
    return parsed.get("balanceUsd")


def main() -> int:
    config.load_environment()
    llm_key = config.load(Role.ANALYST).secret("BANKR_LLM_KEY")
    read_key = config.load(Role.ANALYST).secret("BANKR_KEY_READ")

    results: list[dict] = []

    # Cost guard. Both endpoints are documented reads; this measures it.
    before = _balance(llm_key)

    results.append(_call("credits/llm-key", "/credits", llm_key))
    for days in DAYS_VALUES:
        suffix = "" if days is None else f"?days={days}"
        results.append(_call(f"usage/llm-key{suffix or '/default'}",
                             f"/usage{suffix}", llm_key))

    # Two controls, both from 0.2. The invalid key proves the header is read;
    # the read key proves these endpoints sit behind the gateway toggle rather
    # than being open to any key on the account (F0.2.4).
    results.append(_call("credits/invalid-control", "/credits", INVALID_KEY))
    results.append(_call("usage/invalid-control", "/usage", INVALID_KEY))
    results.append(_call("credits/read-key", "/credits", read_key))
    results.append(_call("usage/read-key", "/usage", read_key))

    after = _balance(llm_key)

    for row in results:
        parsed = row["parsed"]
        fields = sorted(parsed.keys()) if isinstance(parsed, dict) else []
        print(f"{row['label']:28} HTTP {row['status']!s:4} "
              f"{row['elapsed_ms']!s:>5}ms  fields={fields}")

    credits = next(r for r in results if r["label"] == "credits/llm-key")
    usage = next(r for r in results if r["label"] == "usage/llm-key/default")
    credits_body = credits["parsed"] or {}
    usage_body = usage["parsed"] or {}

    print(f"\nbalanceUsd before={before} after={after} "
          f"delta={None if before is None or after is None else round(after - before, 6)}")

    print("\n--- /v1/credits as returned ---")
    print(json.dumps(credits_body, indent=2, sort_keys=True))
    print("\n--- /v1/usage as returned ---")
    print(json.dumps(usage_body, indent=2, sort_keys=True))

    # Attribution. The question 6.3 actually needs answered.
    totals = usage_body.get("totals") or {}
    by_model = usage_body.get("byModel")
    per_request_rows = [
        k for k, v in usage_body.items()
        if isinstance(v, list) and k != "byModel"
    ]
    id_like = [
        k for k in usage_body
        if any(token in k.lower() for token in ("id", "request", "trace"))
        and k != "totalRequests"
    ]

    analysis = {
        "credits_fields_returned": sorted(credits_body) if credits_body else [],
        "credits_documented_but_absent": sorted(
            set(DOCUMENTED_CREDITS_FIELDS) - set(credits_body)) if credits_body else [],
        "credits_undocumented": sorted(
            set(credits_body) - set(DOCUMENTED_CREDITS_FIELDS)) if credits_body else [],
        "usage_fields_returned": sorted(usage_body) if usage_body else [],
        "usage_documented_but_absent": sorted(
            set(DOCUMENTED_USAGE_FIELDS) - set(usage_body)) if usage_body else [],
        "usage_undocumented": sorted(
            set(usage_body) - set(DOCUMENTED_USAGE_FIELDS)) if usage_body else [],
        "totals_fields_returned": sorted(totals),
        "totals_documented_but_absent": sorted(set(DOCUMENTED_TOTALS_FIELDS) - set(totals)),
        "by_model_present": by_model is not None,
        "by_model_entries": len(by_model) if isinstance(by_model, list) else None,
        "per_request_arrays": per_request_rows,
        "id_like_fields": id_like,
        "accepts_time_range": None,  # filled below
        "balance_before": before,
        "balance_after": after,
    }

    # Does `days` actually change the window, or is it ignored?
    windows = {}
    for row in results:
        if row["path"].startswith("/usage") and row["status"] == 200:
            parsed = row["parsed"] or {}
            windows[row["path"]] = (parsed.get("days"), parsed.get("startDate"),
                                    parsed.get("endDate"))
    analysis["windows_by_request"] = windows
    distinct = {v[0] for v in windows.values()}
    analysis["accepts_time_range"] = len(distinct) > 1

    print("\n--- window behaviour by `days` ---")
    for path, window in windows.items():
        print(f"   {path:20} days={window[0]!s:5} {window[1]} -> {window[2]}")

    print("\n--- attribution ---")
    print(f"   byModel present: {analysis['by_model_present']} "
          f"({analysis['by_model_entries']} entries)")
    print(f"   per-request arrays in the response: "
          f"{analysis['per_request_arrays'] or 'NONE'}")
    print(f"   id-like fields: {analysis['id_like_fields'] or 'NONE'}")
    print(f"   `days` changes the window: {analysis['accepts_time_range']}")

    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "credits.json"
    path.write_text(json.dumps({"results": results, "analysis": analysis},
                               indent=2, sort_keys=True), encoding="utf-8")
    print(f"\nwritten to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
