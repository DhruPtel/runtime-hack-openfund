"""Probe 0.10, second half — what does Bankr's rate limit look like when we hit
it? Read-only and free.

    PYTHONPATH=src python3 -m probes.ratelimit

**Goal.** `planning/PHASE-0-1.md` 0.10: exceed a cheap endpoint's limit and record
the status, the body and whether `Retry-After` is present. Unit 1.3's client and
the treasurer's backoff need the real signal, not the documented one. The swap
docs say only *"429 — Rate limited, retry in a moment"*, and no numeric limit is
published for the Wallet API. F0.2's 20 requests and F0.8.1's burst of 10 saw no
rate-limit headers at all.

**The endpoint.** `GET /wallet/me` with `BANKR_KEY_READ`. It is the cheapest
authenticated read there is (it is what `bankr whoami` calls), it moves nothing,
and throttling the read key costs a few seconds of nothing.

**Bounded.** At most `MAX_REQUESTS`, sent from `WORKERS` threads. No new request
is issued after the first 429. If none arrives, the finding is a lower bound
("no limit within N requests in T seconds"), not the absence of a limit. After a
429, two single requests follow:

- one with `BANKR_LLM_KEY`, which reads the Wallet API too (F0.2.2): a 200 means
  the limit is per key, and a 429 means it sits higher, per account or per IP;
- one after waiting out `Retry-After` (capped at 120 s): does the key recover
  when told it will?

`_capture` keeps only an allowlist of headers, so this probe records every
header *name* on a 429 and the value of any header whose name mentions rate,
retry or limit, passed through `fund.redaction`.
"""

from __future__ import annotations

import json
import pathlib
import re
import sys
import threading
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from fund import config, redaction
from fund.credentials import Role

OUT_DIR = pathlib.Path(__file__).resolve().parent / "out"
URL = "https://api.bankr.bot/wallet/me"
MAX_REQUESTS = 150
WORKERS = 8
RETRY_AFTER_CAP_SECONDS = 120
INTERESTING = re.compile(r"rate|retry|limit", re.I)

_redactor = redaction.Redactor()
_stop = threading.Event()
_t0 = 0.0


def one(i: int, key: str) -> dict | None:
    if _stop.is_set():
        return None
    request = urllib.request.Request(URL, headers={
        "X-API-Key": key, "Accept": "application/json", "User-Agent": "openfund-probe/0.10"})
    started = time.monotonic()
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            status, headers, body = response.status, response.headers, response.read()
    except urllib.error.HTTPError as error:
        status, headers, body = error.code, error.headers, error.read()
    except Exception as error:  # transport fault: a result, not a crash
        return {"i": i, "t_ms": int((started - _t0) * 1000), "status": None,
                "error": _redactor.redact(f"{type(error).__name__}: {error}")}
    if status == 429:
        _stop.set()
    return {
        "i": i,
        "t_ms": int((started - _t0) * 1000),
        "ms": int((time.monotonic() - started) * 1000),
        "status": status,
        "header_names": sorted(k.lower() for k in headers.keys()),
        "limit_headers": {k.lower(): _redactor.redact(v) for k, v in headers.items()
                          if INTERESTING.search(k)},
        "body": _redactor.redact(body.decode("utf-8", "replace"))[:600] if status != 200 else None,
    }


def main() -> int:
    global _t0
    config.load_environment()
    analyst = config.load(Role.ANALYST)
    read_key = analyst.secret("BANKR_KEY_READ")
    llm_key = analyst.secret("BANKR_LLM_KEY")

    print("=" * 72)
    print(f"UNIT 0.10 — RATE LIMIT.  Up to {MAX_REQUESTS} x GET {URL}")
    print(f"  key BANKR_KEY_READ, {WORKERS} threads, stop issuing at the first 429.")
    print("  Read-only and free. Nothing is written, signed or spent.")
    print("=" * 72)

    _t0 = time.monotonic()
    with ThreadPoolExecutor(max_workers=WORKERS) as pool:
        results = [r for r in pool.map(lambda i: one(i, read_key), range(MAX_REQUESTS)) if r]
    elapsed = time.monotonic() - _t0
    results.sort(key=lambda r: r["t_ms"])

    counts: dict[str, int] = {}
    for r in results:
        counts[str(r["status"])] = counts.get(str(r["status"]), 0) + 1
    first_429 = next((r for r in results if r["status"] == 429), None)
    last_ok = [r for r in results if r["status"] == 200]
    last_ok = last_ok[-1] if last_ok else None

    followups = {}
    if first_429:
        followups["other_key_immediately"] = one(-1, llm_key)
        retry_after = first_429["limit_headers"].get("retry-after")
        wait = None
        if retry_after and retry_after.strip().isdigit():
            wait = min(int(retry_after), RETRY_AFTER_CAP_SECONDS)
        _stop.clear()
        if wait is not None:
            print(f"\n429 received; Retry-After {retry_after}s. Waiting {wait}s, then one request.")
            time.sleep(wait)
            followups["same_key_after_retry_after"] = {"waited_s": wait, **(one(-2, read_key) or {})}
        else:
            followups["same_key_after_retry_after"] = {"waited_s": None,
                                                       "note": "no numeric Retry-After to honour"}

    result = {
        "url": URL, "max_requests": MAX_REQUESTS, "workers": WORKERS,
        "requests_sent": len(results), "elapsed_s": round(elapsed, 2),
        "status_counts": counts,
        "first_429": first_429, "last_200_before_it": last_ok,
        "followups": followups,
        "requests": results,
    }
    OUT_DIR.mkdir(exist_ok=True)
    path = OUT_DIR / "ratelimit.json"
    path.write_text(json.dumps(result, indent=2), encoding="utf-8")

    print(f"\nsent {len(results)} in {elapsed:.1f}s: {counts}")
    if first_429:
        print(f"first 429: request #{first_429['i']} at {first_429['t_ms']} ms "
              f"(after {sum(1 for r in results if r['status'] == 200)} successes)")
        print(f"  headers: {first_429['header_names']}")
        print(f"  limit headers: {first_429['limit_headers']}")
        print(f"  body: {first_429['body']}")
        print(f"  last 200's limit headers: {last_ok and last_ok['limit_headers']}")
        for name, f in followups.items():
            print(f"  {name}: {f and f.get('status')} {f and f.get('limit_headers')}")
    else:
        print(f"no 429 within {len(results)} requests in {elapsed:.1f}s — a lower bound, "
              f"not the absence of a limit")
        print(f"  limit headers on the last 200: {last_ok and last_ok['limit_headers']}")
    print(f"written to {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
