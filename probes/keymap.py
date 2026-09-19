"""Which key in `.env` is which, measured: so the dashboard's rows can be matched.

    PYTHONPATH=src python3 -m probes.keymap

The dashboard lists several keys, and their labels do not say which is which.
For each Bankr key in `.env`, this reports its wallet and what the key actually
does. It prints names, addresses and capabilities, never a key's value. The
2.0 agent key, from its own account outside `.env`, rides along as a calibration
key whose Agent API was measured off by refusal (research/findings.md F2.0.4).

**Read-only, and changes nothing.** No key setting is touched, and no request
here can move value or leave a trace:
  - **wallet:** `GET /wallet/me`;
  - **LLM gateway:** `GET /v1/credits`. 200 means the toggle is on; a 403 that
    names the toggle means off (F0.2.4, F2.0.5);
  - **Agent API:** `GET /agent/profile?multi=true`, a read. Calibrated first
    against the 2.0 key: if that key draws a 403 naming the Agent API, the read
    is gated by the toggle, and the same answer from a fund key means off;
  - **read-only:** `POST /wallet/sign` with `personal_sign` and **no message**.
    A read-only key is refused by name before the body is read (F2.0.3). A key
    that may sign gets past that gate and fails validation instead. Either way
    nothing is signed;
  - **token launch:** not measured. The CLI's token-launch reads are
    unauthenticated, so no read is gated by the toggle. The only test is a
    deploy request, which this probe does not send.

A never-issued key is the control on every request (401). The fund's keys are
declared credentials, so `probes/_capture` masks them. The 2.0 key is not, so
it is masked here before anything is stored.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from fund import config, credentials
from probes import _capture

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "probes" / "out" / "keymap.json"
AGENT_CONFIG = Path.home() / ".openfund" / "agents" / "price-integrity" / "bankr-config.json"

API = "https://api.bankr.bot"
LLM = "https://llm.bankr.bot"
NEVER_ISSUED = "bk_0000000000000000000000000000000000000000"
BANKR_KEYS = ("BANKR_KEY_READ", "BANKR_KEY_EXEC", "BANKR_LLM_KEY")


def verdict(status: int | None, body: str, on_refusal: str, refusal_words: str,
            passed: str) -> str:
    if status == 401:
        return "invalid key"
    if status == 403 and refusal_words.lower() in body.lower():
        return on_refusal
    if status in (200, 201, 400, 404, 422):
        return passed
    return f"unresolved (HTTP {status})"


def probe(name: str, key: str, mask) -> dict:
    def call(label, url, **kw):
        c = _capture.call(label=f"{name}: {label}", url=url, header_name="X-API-Key",
                          header_value=key, max_body_chars=200_000, **kw)
        return c.status, mask(c.body)[:1500]

    me_status, me = call("wallet/me", f"{API}/wallet/me")
    try:
        wallets = [w["address"] for w in json.loads(me).get("wallets", [])]
    except (ValueError, AttributeError):
        wallets = []
    gw_status, gw = call("v1/credits", f"{LLM}/v1/credits")
    ag_status, ag = call("agent/profile", f"{API}/agent/profile?multi=true")
    ro_status, ro = call("wallet/sign, no message", f"{API}/wallet/sign",
                         json_body={"signatureType": "personal_sign"})
    row = {
        "key": name,
        "wallets": wallets,
        "llm_gateway": verdict(gw_status, gw, "off", "LLM Gateway access", "on"),
        "agent_api": verdict(ag_status, ag, "off", "Agent API access not enabled",
                             "not refused by the toggle"),
        "read_only": verdict(ro_status, ro, "read-only", "Read-only API key",
                             "not read-only (passed the permission gate)"),
        "token_launch": "not measured: no read is gated by it",
        "answers": {"wallet/me": me_status, "v1/credits": [gw_status, gw[:200]],
                    "agent/profile": [ag_status, ag[:200]],
                    "wallet/sign, no message": [ro_status, ro[:200]]},
    }
    print(f"\n{name}")
    for field in ("wallets", "llm_gateway", "agent_api", "read_only", "token_launch"):
        print(f"  {field:<13} {row[field]}")
    for label, answer in row["answers"].items():
        print(f"    {label:<24} {answer if isinstance(answer, int) else answer[0]}  "
              f"{'' if isinstance(answer, int) else answer[1][:110]}")
    return row


def main() -> int:
    analyst = config.load(credentials.Role.ANALYST, require=False)
    treasurer = config.load(credentials.Role.TREASURER, require=False)
    held = {name: (analyst if analyst.has(name) else treasurer).secret(name)
            for name in BANKR_KEYS}
    agent_key = json.loads(AGENT_CONFIG.read_text())["apiKey"] if AGENT_CONFIG.exists() else None
    mask = lambda text: text.replace(agent_key, "[AGENT_API_KEY]") if agent_key and text else text

    rows = []
    if agent_key:
        rows.append(probe("2.0 agent key (calibration; its own account, not in .env)", agent_key, mask))
    for name in BANKR_KEYS:
        rows.append(probe(name, held[name], mask))
    rows.append(probe("never-issued control", NEVER_ISSUED, mask))

    serialized = json.dumps(rows, indent=2, sort_keys=True)
    secrets = [v for v in held.values()] + ([agent_key] if agent_key else [])
    if any(secret and secret in serialized for secret in secrets):
        print("REFUSING TO WRITE: a key value would reach disk")
        return 3
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(serialized + "\n")
    print(f"\nwrote {OUT.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
