"""Probe 1.7 — what one analyst call costs against a real snapshot.

**Spends LLM credits.** Four calls and no more, and nothing is sent without
`--confirm`:
1. an analyst call over the whole snapshot;
2. the same call again, because one call says nothing about variance (F0.9.3);
3. the same prompt with every asset's `timeline` removed and one output token,
   whose input count, subtracted from call 1's, is what the timeline costs. The
   gateway has no count-tokens endpoint (`/v1/messages/count_tokens` is a 404,
   measured);
4. a risk call reading four reports and a sized plan. There are no real reports
   before Phase 2, so call 1's report stands in four times, labelled as such.

**What it measures, and from what.** Tokens come from each response's own
`usage` block. Cost is those tokens at the gateway's listed price. The credit
balance, read before and after each call, is the independent check: in 0.9 the
three agreed to the last digit (F0.9.1). `/v1/usage` is read once, for a settled
window after the calls, never as a delta around one call, because it went
backwards (F0.9.2).

**Nothing is dropped to make the snapshot fit.** The prompt embeds the snapshot
file's exact bytes, and their sha256 must equal the hash in the file's name. A
snapshot too large for the model's context window is the finding, not something
to trim. The preflight says so and stops.

**The client waits 900 s.** That is far past both configured timeouts. A call
cut off on our side is still billed and returns nothing (F0.9.3), so this probe
must not cut one off: its job is to find out how long a real call takes.

**Output quality is not the subject.** The brief is 0.9's, unchanged, so the two
measurements compare; the real brief is 2.1's. The analyst covers every asset in
the snapshot. That is right for the universe-wide roles and an upper bound for
the asset-partitioned ones (`config/analysts.json`).

**Two narrower modes, added after 1.7** (DECISIONs, LESSONS 2026-09-18):
- `--one`: a single analyst call, for measuring another snapshot shape against
  1.7's (daily closes). Its report is compared with 1.7's on how it uses
  history: whether reports cite the timeline, quote dated points and more
  than one price level, and how many abstain. That is a proxy for quality,
  stated as one.
- `--cache`: two calls on the Anthropic-shaped `/v1/messages`, with the
  system prompt and the snapshot marked `cache_control`. The first writes the
  cache. The second reads it under a *different* analyst's scope, as four
  analysts sharing one snapshot would. It measures whether the gateway honours
  cache control, and what that saves.

Run:  PYTHONPATH=src python3 -m probes.analyst_cost fixtures/live/snapshot-<sha256>.json [--one | --cache] [--confirm]
"""

from __future__ import annotations

import hashlib
import json
import pathlib
import re
import sys
import time

from fund import config
from fund.core import snapshot as snap
from fund.credentials import Role

from . import _capture
from .llm_cost import SYSTEM_PROMPT  # 0.9's brief, unchanged, so the numbers compare

ROOT = pathlib.Path(__file__).resolve().parents[1]
OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
GATEWAY = "https://llm.bankr.bot/v1"
MODEL = json.loads((ROOT / "config" / "models.json").read_text())["analyst_model"]
MODELS = json.loads((ROOT / "config" / "models.json").read_text())
CLIENT_TIMEOUT_S = 900
MAX_TOKENS = 16_000
CAPPED_TOKENS = MODELS["max_output_tokens"]  # 12,000 since the DECISION after 1.7
ANALYSTS_PER_CYCLE, RISK_CALLS_PER_CYCLE, CYCLES_PER_DAY = 4, 1, 1
X402_PRICE_USD = 0.05

USER_TEMPLATE = """## Your scope

Analyst id: price-trend
Objective: recent price action and trend for the assets assigned to you.
Assigned assets: every asset in the snapshot's `assets` list.

## Snapshot

This is the complete set of facts. Its sha256 is {sha256}. Its own `about` and
`rules` fields say how to read it.

{snapshot}

## Required output

Strict JSON:
{{"reports": [{{"symbol": str, "call": "BUY"|"SELL"|"HOLD"|"NO_CALL",
  "confidence": 0.0-1.0, "reasoning": str, "cites": [str]}}],
  "abstained": [str], "notes": str}}
"""

RISK_SYSTEM = """You are the risk agent of an autonomous onchain fund. You read every
analyst report in full and the sized plan, and return a verdict. Fixed gates are
applied in code and cannot be overridden by your text; you explain, you do not
authorise. Return strict JSON only."""

RISK_TEMPLATE = """## Analyst reports

These four reports stand in for four analysts' reports: they are one measured
report repeated, because no real reports exist before Phase 2.

{reports}

## Sized plan

{plan}

## Required output

Strict JSON:
{{"verdict": "APPROVE"|"VETO", "reasons": [str],
  "per_order": [{{"symbol": str, "verdict": "APPROVE"|"VETO", "reason": str}}]}}
"""

#: A stand-in plan of the size 3.3 might produce: five $25 buys. Labelled as one.
STAND_IN_PLAN = json.dumps({"note": "stand-in, not a real plan: 3.3 builds plans", "orders": [
    {"symbol": s, "side": "BUY", "sell": "25.001227 USDG", "min_buy": "from the quote"}
    for s in ("NVDA", "AAPL", "SPY", "MSFT", "GOOGL")]}, indent=1)


def get(path: str, key: str) -> dict:
    capture = _capture.call(label=path, url=f"{GATEWAY}{path}", header_name="X-API-Key",
                            header_value=key, max_body_chars=400_000)
    return _capture.as_json(capture) or {}


def balance(key: str) -> float | None:
    return get("/credits", key).get("balanceUsd")


def chat(label: str, key: str, system: str, user: str, max_tokens: int) -> dict:
    """One call, measured: latency by our clock, tokens by its `usage` block,
    and the balance either side of it."""
    before = balance(key)
    started = time.monotonic()
    capture = _capture.call(
        label=label, url=f"{GATEWAY}/chat/completions", header_name="X-API-Key",
        header_value=key, timeout=CLIENT_TIMEOUT_S, max_body_chars=400_000,
        json_body={"model": MODEL, "max_tokens": max_tokens, "temperature": 0,
                   "messages": [{"role": "system", "content": system},
                                {"role": "user", "content": user}]})
    latency_ms = int((time.monotonic() - started) * 1000)
    parsed = _capture.as_json(capture) or {}
    choice = (parsed.get("choices") or [{}])[0]
    time.sleep(3)
    return {"label": label, "status": capture.status, "latency_ms": latency_ms,
            "transport_error": capture.transport_error, "usage": parsed.get("usage") or {},
            "finish_reason": choice.get("finish_reason"),
            "text": (choice.get("message") or {}).get("content") or "",
            "prompt_chars": len(system) + len(user), "balance_before": before,
            "balance_after": balance(key),
            "extra": {k: v for k, v in parsed.items() if k not in ("choices", "usage")}}


def cost(usage: dict, price: dict) -> float:
    return ((usage.get("prompt_tokens") or 0) * price["input"]
            + (usage.get("completion_tokens") or 0) * price["output"]) / 1e6


# --- how a report uses history: a proxy, stated as one --------------------------------------

_DATED = re.compile(r"\b\d{1,2}/\d{1,2}\b|\b(?:2026-)?\d{2}-\d{2}\b|\b(?:Aug|Sep)\w*\.? \d{1,2}\b")
_PRICE = re.compile(r"\b\d{1,5}\.\d{1,4}\b")


def report_shape(text: str) -> dict:
    """Counts from one analyst reply: how many reports, how many abstain or
    say NO_CALL, and how many cite the timeline, quote dated points, and name
    more than one price level. A proxy for using history, not a grade."""
    body = re.sub(r"^```(?:json)?|```$", "", text.strip()).strip()
    try:
        parsed = json.loads(body)
    except ValueError as error:
        return {"parsed": False, "error": str(error)}
    reports = parsed.get("reports") or []
    reasoning = [str(r.get("reasoning", "")) for r in reports]
    calls: dict[str, int] = {}
    for r in reports:
        calls[r.get("call")] = calls.get(r.get("call"), 0) + 1
    return {
        "parsed": True, "reports": len(reports), "abstained": len(parsed.get("abstained") or []),
        "calls": calls,
        "cite_timeline": sum(any("timeline" in c for c in (r.get("cites") or [])) for r in reports),
        "quote_dated_points": sum(bool(_DATED.search(t)) for t in reasoning),
        "name_two_price_levels": sum(len(set(_PRICE.findall(t))) >= 2 for t in reasoning),
        "reasoning_chars_mean": round(sum(map(len, reasoning)) / len(reasoning)) if reasoning else 0,
    }


def messages(label: str, key: str, cached: str, rest: str, max_tokens: int) -> dict:
    """One call on the Anthropic-shaped endpoint, with the system prompt and
    `cached` marked for caching and `rest` after it."""
    before = balance(key)
    started = time.monotonic()
    capture = _capture.call(
        label=label, url=f"{GATEWAY}/messages", header_name="X-API-Key", header_value=key,
        timeout=CLIENT_TIMEOUT_S, max_body_chars=400_000,
        json_body={"model": MODEL, "max_tokens": max_tokens, "temperature": 0,
                   "system": [{"type": "text", "text": SYSTEM_PROMPT}],
                   "messages": [{"role": "user", "content": [
                       {"type": "text", "text": cached, "cache_control": {"type": "ephemeral"}},
                       {"type": "text", "text": rest}]}]})
    latency_ms = int((time.monotonic() - started) * 1000)
    parsed = _capture.as_json(capture) or {}
    time.sleep(3)
    text = "".join(b.get("text", "") for b in (parsed.get("content") or []) if isinstance(b, dict))
    return {"label": label, "status": capture.status, "latency_ms": latency_ms,
            "transport_error": capture.transport_error, "usage": parsed.get("usage") or {},
            "stop_reason": parsed.get("stop_reason"), "text": text,
            "error": None if capture.status == 200 else capture.body[:800],
            "balance_before": before, "balance_after": balance(key),
            "extra": {k: v for k, v in parsed.items() if k not in ("content", "usage")}}


def cached_cost(usage: dict, price: dict) -> float:
    return ((usage.get("input_tokens") or 0) * price["input"]
            + (usage.get("cache_creation_input_tokens") or 0) * price.get("cache_write", price["input"])
            + (usage.get("cache_read_input_tokens") or 0) * price.get("cache_read", price["input"])
            + (usage.get("output_tokens") or 0) * price["output"]) / 1e6


def main() -> int:
    flags = {"--confirm", "--one", "--cache"}
    args = [a for a in sys.argv[1:] if a not in flags]
    confirmed, one, cache = ("--confirm" in sys.argv, "--one" in sys.argv, "--cache" in sys.argv)
    if len(args) != 1 or (one and cache):
        print(__doc__.strip().splitlines()[-1])
        return 2
    path = ROOT / args[0]
    body = path.read_bytes()
    sha256 = hashlib.sha256(body).hexdigest()
    if f"snapshot-{sha256}.json" != path.name:
        print(f"refused: {path.name} does not hash to its name ({sha256})")
        return 2
    document = json.loads(body)
    if snap.canonical(document) != body:
        print("refused: the file is not the snapshot's canonical bytes")
        return 2
    stripped_doc = {**document, "assets": [{k: v for k, v in e.items() if k != "timeline"}
                                           for e in document["assets"]]}
    stripped = snap.canonical(stripped_doc)
    rounds = sum(e["timeline"]["rounds"] for e in document["assets"])

    key = config.load(Role.ANALYST).secret("BANKR_LLM_KEY")
    catalogue = {m["id"]: m for m in get("/models", key).get("data", [])}
    model = catalogue[MODEL]
    price, window = model["pricing"], model["context_window"]
    user = USER_TEMPLATE.format(sha256=sha256, snapshot=body.decode("utf-8"))
    stripped_user = USER_TEMPLATE.format(sha256=sha256, snapshot=stripped.decode("utf-8"))
    assert body.decode("utf-8") in user  # the whole snapshot, byte for byte
    ceiling = (len(SYSTEM_PROMPT) + len(user)) // 2  # 0.9 measured 2.02 chars a token
    worst = (2 * (ceiling * price["input"] + MAX_TOKENS * price["output"])
             + len(stripped_user) // 2 * price["input"] + 40_000 * price["input"]
             + 4_000 * price["output"]) / 1e6
    funds = balance(key)

    print("=" * 76)
    print("UNIT 1.7 — ANALYST COST AGAINST A REAL SNAPSHOT.  THIS SPENDS LLM CREDITS.")
    print("=" * 76)
    print(f"  snapshot     {path.relative_to(ROOT)}")
    print(f"               {len(body):,} bytes, {len(document['assets'])} assets, {rounds:,} rounds; "
          f"sha256 verified against the name")
    print(f"  timeline     {len(body) - len(stripped):,} of {len(body):,} bytes "
          f"({(len(body) - len(stripped)) / len(body):.0%}) by bytes; tokens measured by call 3")
    print(f"  prompt       {len(SYSTEM_PROMPT) + len(user):,} chars; at 0.9's 2.02 chars a token "
          f"about {ceiling:,} tokens, against a {window:,}-token window")
    print(f"  model        {MODEL} (config/models.json analyst_model, provisional): "
          f"${price['input']}/M in, ${price['output']}/M out")
    print(f"  calls        2 analyst (max_tokens {MAX_TOKENS:,}), 1 breakdown (max_tokens 1), 1 risk")
    print(f"  worst case   ${worst:.2f}; balance ${funds}")
    print(f"  client       waits {CLIENT_TIMEOUT_S} s; configured: transport "
          f"{MODELS['transport_timeout_seconds']} s, worker deadline {MODELS['worker_deadline_seconds']} s")
    print("=" * 76)
    if ceiling > window:
        print("does not fit the context window at a generous estimate: that is the finding. Stopping.")
        return 1
    if funds is None or funds < worst:
        print("the balance does not cover the worst case. Stopping.")
        return 1
    if not confirmed:
        print(f"\nPre-flight only{' (--one: 1 call)' if one else ' (--cache: 2 calls)' if cache else ''}. "
              f"Nothing spent. Re-run with --confirm.")
        return 0
    if one:
        return run_one(key, user, price, path, sha256, document, rounds, len(body))
    if cache:
        return run_cache(key, body, sha256, price, path)

    calls = []
    for n in (1, 2):
        calls.append(chat(f"analyst-{n}", key, SYSTEM_PROMPT, user, MAX_TOKENS))
        c = calls[-1]
        print(f"analyst {n}: HTTP {c['status']} in {c['latency_ms']:,} ms; usage {json.dumps(c['usage'])}; "
              f"finish {c['finish_reason']}; balance {c['balance_before']} -> {c['balance_after']}")
        if c["status"] != 200:
            print(c["transport_error"] or c["text"][:800])
            return 1
    calls.append(chat("breakdown-no-timeline", key, SYSTEM_PROMPT, stripped_user, 1))
    c = calls[-1]
    print(f"breakdown: HTTP {c['status']} in {c['latency_ms']:,} ms; usage {json.dumps(c['usage'])}; "
          f"balance {c['balance_before']} -> {c['balance_after']}")
    report = calls[0]["text"]
    risk_user = RISK_TEMPLATE.format(reports="\n\n".join(f"### Report {i}\n\n{report}" for i in range(1, 5)),
                                     plan=STAND_IN_PLAN)
    calls.append(chat("risk", key, RISK_SYSTEM, risk_user, 4_000))
    c = calls[-1]
    print(f"risk: HTTP {c['status']} in {c['latency_ms']:,} ms; usage {json.dumps(c['usage'])}; "
          f"finish {c['finish_reason']}; balance {c['balance_before']} -> {c['balance_after']}")

    print("\nwaiting 90 s for /v1/usage to settle before reading one window")
    time.sleep(90)
    settled = get("/usage?days=1", key)

    for c in calls:
        c["cost_usd"] = cost(c["usage"], price)
        if c["balance_before"] is not None and c["balance_after"] is not None:
            c["balance_delta"] = round(c["balance_before"] - c["balance_after"], 8)
    a1, a2, b, r = calls
    full_in = a1["usage"].get("prompt_tokens")
    timeline_in = full_in - b["usage"].get("prompt_tokens") if full_in and b["usage"] else None
    analyst = (a1["cost_usd"] + a2["cost_usd"]) / 2
    cycle = ANALYSTS_PER_CYCLE * analyst + RISK_CALLS_PER_CYCLE * r["cost_usd"]
    in_cost = full_in * price["input"] / 1e6
    cached_cycle_inputs = (full_in * price.get("cache_write", price["input"])
                           + (ANALYSTS_PER_CYCLE - 1) * full_in * price.get("cache_read", price["input"])
                           ) / 1e6
    fits = sorted(((m["id"], m.get("context_window"), cost(a1["usage"], m["pricing"]))
                   for m in catalogue.values()
                   if m.get("pricing") and m.get("context_window") and "text" in (m.get("output_modalities") or [])),
                  key=lambda row: row[2])

    result = {
        "snapshot": {"path": str(path.relative_to(ROOT)), "sha256": sha256, "bytes": len(body),
                     "timeline_bytes": len(body) - len(stripped), "assets": len(document["assets"]),
                     "rounds": rounds, "block": document["block"]},
        "model": MODEL, "pricing_per_million": price, "context_window": window,
        "calls": calls, "timeline_input_tokens": timeline_in,
        "analyst_call_usd_mean": analyst, "risk_call_usd": r["cost_usd"],
        "cycle_usd": cycle, "day_usd": cycle * CYCLES_PER_DAY, "thirty_days_usd": cycle * 30,
        "x402_records_per_cycle": cycle / X402_PRICE_USD,
        "cycle_analyst_input_usd_uncached": ANALYSTS_PER_CYCLE * in_cost,
        "cycle_analyst_input_usd_if_cached": cached_cycle_inputs,
        "catalogue": [{"model": m, "context_window": w, "analyst_call_usd": c_,
                       "fits": w >= (full_in or 0) + MAX_TOKENS} for m, w, c_ in fits],
        "usage_settled_window": settled,
    }
    OUT_DIR.mkdir(exist_ok=True)
    out = OUT_DIR / "analyst_cost.json"
    out.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")

    print(f"\ninput tokens: analyst {full_in:,} (timeline {timeline_in:,}, the rest "
          f"{b['usage'].get('prompt_tokens'):,}); chars per token {(len(SYSTEM_PROMPT) + len(user)) / full_in:.2f}")
    for c in calls:
        print(f"  {c['label']:22} in {c['usage'].get('prompt_tokens')!s:>7} out "
              f"{c['usage'].get('completion_tokens')!s:>6} {c['latency_ms'] / 1000:7.1f} s  "
              f"${c['cost_usd']:.6f}  balance moved ${c.get('balance_delta')}")
    print(f"  per analyst call ${analyst:.6f}; risk ${r['cost_usd']:.6f}; cycle ${cycle:.6f}; "
          f"30 days ${cycle * 30:.2f}; records at ${X402_PRICE_USD} per cycle {cycle / X402_PRICE_USD:.1f}")
    print(f"  analyst inputs per cycle: ${ANALYSTS_PER_CYCLE * in_cost:.4f} uncached, "
          f"${cached_cycle_inputs:.4f} if cached (priced, not measured)")
    print(f"  models whose window holds the prompt: "
          f"{sum(1 for m, w, _ in fits if w >= full_in + MAX_TOKENS)} of {len(fits)}")
    print(f"  /v1/usage, one settled window: {json.dumps(settled)[:600]}")
    print(f"\nwritten to {out}")
    return 0


def run_one(key: str, user: str, price: dict, path: pathlib.Path, sha256: str, document: dict,
            rounds: int, size: int) -> int:
    """One analyst call against this snapshot, set beside 1.7's."""
    call = chat("analyst-one", key, SYSTEM_PROMPT, user, CAPPED_TOKENS)
    call["cost_usd"] = cost(call["usage"], price)
    call["report_shape"] = report_shape(call["text"])
    before = json.loads((OUT_DIR / "analyst_cost.json").read_text())
    earlier = before["calls"][:2]  # 1.7's two identical calls: they differ, so both are the baseline
    result = {"snapshot": {"path": str(path.relative_to(ROOT)), "sha256": sha256, "bytes": size,
                           "rounds": rounds, "block": document["block"]},
              "call": call, "compared_with": {"snapshot": before["snapshot"], "calls": earlier,
                                              "report_shapes": [report_shape(c["text"]) for c in earlier]}}
    (OUT_DIR / "analyst_cost_one.json").write_text(json.dumps(result, indent=2, sort_keys=True),
                                                   encoding="utf-8")
    u = call["usage"]
    print(f"analyst: HTTP {call['status']} in {call['latency_ms']:,} ms; in {u.get('prompt_tokens')} out "
          f"{u.get('completion_tokens')} finish {call['finish_reason']}; ${call['cost_usd']:.6f}; "
          f"balance {call['balance_before']} -> {call['balance_after']}")
    print(f"  this snapshot  {size:,} bytes, {rounds:,} points: {json.dumps(call['report_shape'])}")
    for n, c in enumerate(earlier, 1):
        eu = c["usage"]
        print(f"  1.7's call {n}   {before['snapshot']['bytes']:,} bytes, {before['snapshot']['rounds']:,} "
              f"points; in {eu.get('prompt_tokens')} out {eu.get('completion_tokens')} "
              f"${c['cost_usd']:.6f}: {json.dumps(report_shape(c['text']))}")
    return 0 if call["status"] == 200 else 1


def run_cache(key: str, body: bytes, sha256: str, price: dict, path: pathlib.Path) -> int:
    """Two calls sharing one cached prefix: the system prompt and the snapshot."""
    cached = (f"## Snapshot\n\nThis is the complete set of facts. Its sha256 is {sha256}. Its own "
              f"`about` and `rules` fields say how to read it.\n\n{body.decode('utf-8')}")
    schema = USER_TEMPLATE.split("## Required output", 1)[1]
    scopes = [("price-trend", "recent price action and trend for the assets assigned to you."),
              ("execution-quality", "quote age, impact, spread and tradeability, per asset.")]
    calls = []
    for n, (analyst, objective) in enumerate(scopes, 1):
        rest = (f"## Your scope\n\nAnalyst id: {analyst}\nObjective: {objective}\nAssigned assets: "
                f"every asset in the snapshot's `assets` list.\n\n## Required output{schema}")
        calls.append(messages(f"cache-{n}-{analyst}", key, cached, rest, CAPPED_TOKENS))
        c = calls[-1]
        c["cost_usd"] = cached_cost(c["usage"], price)
        print(f"cache {n} ({analyst}): HTTP {c['status']} in {c['latency_ms']:,} ms; usage "
              f"{json.dumps(c['usage'])}; stop {c['stop_reason']}; ${c['cost_usd']:.6f}; balance "
              f"{c['balance_before']} -> {c['balance_after']}")
        if c["status"] != 200:
            print(c["error"] or c["transport_error"])
            break
    time.sleep(20)
    settled = balance(key)
    (OUT_DIR / "analyst_cost_cache.json").write_text(json.dumps(
        {"snapshot": {"path": str(path.relative_to(ROOT)), "sha256": sha256, "bytes": len(body)},
         "pricing_per_million": price, "calls": calls, "balance_settled": settled},
        indent=2, sort_keys=True), encoding="utf-8")
    print(f"  balance settled at {settled}; costs at listed prices: "
          + ", ".join(f"${c['cost_usd']:.6f}" for c in calls))
    return 0 if all(c["status"] == 200 for c in calls) else 1


if __name__ == "__main__":
    sys.exit(main())
