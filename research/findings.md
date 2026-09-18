# Findings

What the Phase 0 probes actually measured. This is the page the rest of the
build trusts, so it is written to a stricter standard than the plan it corrects.

**Confidence** is one of:

- **measured** — we observed it, from this machine, against the live surface, on
  the date given. The capture is in `probes/out/`.
- **documented** — a provider's documentation or a discovery report in
  `research/` says so, and we did not observe it.
- **inferred** — we reasoned to it from something measured. An inference is never
  promoted to a fact.

**Verdict** is **pass**, **fail**, or **unresolved**. Unresolved is a real
outcome and is never rounded up. A recorded fail is a completed probe.

Response bodies are redacted by `probes/_capture.py`, whose denylist derives from
the credential table. Public chain addresses are not secrets and are shown.

---

## 0.2 — Auth headers and key permissions

**Date:** 2026-09-17 · **Method:** `PYTHONPATH=src python3 -m probes.keys` ·
**Captures:** `probes/out/keys.json` (20 requests, all read-only GETs)

Each surface was called with `X-API-Key: <key>` and again with
`Authorization: Bearer <key>`. A never-issued key (`bk_000…`) ran as a negative
control on every surface, because "the key returned 200" is not evidence of
authorization unless a bad key is refused.

### Results

| Surface | Endpoint | Key | X-API-Key | Bearer |
|---|---|---|---|---|
| wallet | `GET /wallet/portfolio` | `BANKR_KEY_READ` | 200 | 200 |
| wallet | `GET /wallet/portfolio` | `BANKR_KEY_EXEC` | 200 | 200 |
| wallet | `GET /wallet/portfolio` | `BANKR_LLM_KEY` | 200 | 200 |
| wallet | `GET /wallet/portfolio` | *invalid (control)* | 401 | 401 |
| gateway | `GET /v1/models` | `BANKR_LLM_KEY` | 402 | 402 |
| gateway | `GET /v1/models` | `BANKR_KEY_READ` | 403 | 403 |
| gateway | `GET /v1/models` | *invalid (control)* | 401 | 401 |
| agent | `GET /agent/job/{unissued}` | `BANKR_KEY_READ` | 404 | 404 |
| agent | `GET /agent/job/{unissued}` | `BANKR_KEY_EXEC` | 404 | 404 |
| agent | `GET /agent/job/{unissued}` | *invalid (control)* | 401 | 401 |

Latency: 99–1999 ms, no timeouts, no transport errors. No `Retry-After` and no
`x-ratelimit-*` headers appeared on any response at this volume.

### F0.2.1 — Both auth headers are accepted on all three surfaces

**Confidence: measured. Verdict: pass.**

Every status is identical between `X-API-Key` and `Authorization: Bearer`, on
every surface, for every key including the control. The control's 401 proves the
header is read rather than ignored.

**This contradicts `research/openclaude.md` as stated.** That report's headline
correction was that the LLM gateway "does **not** take `Authorization: Bearer`.
It takes `X-API-Key`," documented as a named protocol exception alongside
Azure's. Measured here, `Authorization: Bearer` reaches the gateway and produces
a byte-identical response to `X-API-Key`. The report's evidence was
`openclaude`'s own client code, which is honest evidence about what that client
*sends* and was over-read into a claim about what the gateway *accepts*.

`research/agent-os.md` is corroborated: it sends both headers together and
reports Bearer is harmless alongside. It never claimed Bearer alone works; that
is new here.

**Plan change:** `planning/PLAN.md` §6 lists `BANKR_LLM_KEY` as "header
`X-API-Key`". Either header works; we keep `X-API-Key` as the one we send,
because it is the one both discovery reports observed in production traffic, but
it is now a preference and not a constraint.

### F0.2.2 — `BANKR_LLM_KEY` is not "gateway only"; it reads the Wallet API

**Confidence: measured. Verdict: fail** (against the scope `planning/PLAN.md` §6
claimed).

`BANKR_LLM_KEY` returned 200 and a full portfolio from `GET /wallet/portfolio`.
The plan scoped it "gateway only". That was never enforced.

**Inferred, not measured:** key scoping on this account appears to be by
*capability toggle* (Read Only, LLM Gateway, Agent API) rather than by surface. A
key with Read Only ON can reach any read endpoint on the account; what the
toggles separate is reading from transacting, not one surface from another.
Consistent with everything observed, but we have not tested a write with
`BANKR_LLM_KEY`, so it is an inference.

**This does not breach `planning/PLAN.md` §2 invariant 1.** The invariant is that
the analyst role cannot *transact*, and read access to a portfolio is not spend
authority. It does mean the analyst process can read the fund's holdings, which
was already true via `BANKR_KEY_READ`.

**Plan change:** §6's scope column must say what is true — Read Only ON, LLM
Gateway ON — rather than "gateway only". Recorded in `tracker/LESSONS.md`.

**Unresolved and deliberately not probed:** whether `BANKR_LLM_KEY` is refused on
a *write*. That is probe 0.5/0.10 territory and needs explicit authorization.

### F0.2.3 — All three keys resolve to one wallet

**Confidence: measured. Verdict: pass.**

Every authorized response returned the same `evmAddress`
`0x93faecde3c88a713e1edddf417c02c326889a3da` and the same `solAddress`.

This directly answers `planning/PLAN-technical-review.md` finding 2, which warned
that "the read account's authenticated portfolio is mistaken for the execution
account's portfolio, so a valid proposal is sized against the wrong wallet." With
one account there is no second portfolio to confuse it with. The warning is
retired as a *risk*, and replaced by the §13 limitation: the boundary is a
toggle, not an account.

The requirement in §6 that the execution wallet be **named explicitly in config
and read over RPC** still stands, and matters more now, not less — a single
authenticated portfolio endpoint is exactly the kind of convenience that hides a
wrong-wallet assumption.

### F0.2.4 — Gateway toggle: ON for `BANKR_LLM_KEY`, OFF for `BANKR_KEY_READ`

**Confidence: measured. Verdict: pass.**

The three gateway statuses separate cleanly and are self-describing:

- `BANKR_LLM_KEY` → **402** `insufficient_credits`
- `BANKR_KEY_READ` → **403** `auth_error`, *"This API key does not have LLM
  Gateway access enabled. Enable it in your API key settings."*
- invalid → **401** `auth_error`, *"Invalid or inactive API key"*

**Inferred:** 403 sits upstream of 402, so a key that reaches the billing layer
has passed the toggle check. Reaching 402 is therefore positive evidence the
gateway toggle is ON, not merely an absence of refusal.

### F0.2.5 — Agent API toggle state cannot be determined from a read

**Confidence: measured (the status). Verdict: unresolved (the toggle).**

Both Bankr keys returned **404** with *"Job not found or you don't have
permission to access it"*. That message conflates the two outcomes the probe
exists to separate, so it is not evidence either way.

The contrast is the point: the gateway names the missing toggle in its 403, and
the Agent API does not. We cannot say the Agent API is off, and we will not say
it is on.

**Not probed:** `POST /agent/prompt` would settle it, but it is a write, it
consumes the daily quota, and nothing in the system calls the Agent API.

**Plan change:** unit 0.2's done-condition required confirming Agent API **off**
for both Bankr keys. That cannot be confirmed by a read. The condition becomes:
the toggle is set off in the console, and the system contains no call to
`/agent/prompt` — asserted in code, not against the live surface.

### F0.2.6 — The fund wallet is empty

**Confidence: measured. Verdict: fail** (against the ~$200 capital in §11).

Every chain in the portfolio reports zero: `base`, `robinhood`, `mainnet` and
`polygon` each return `nativeBalance: "0"`, `nativeUsd: "0"`, an empty
`tokenBalances`, and `total: "0"`.

**Blocks:** probe 0.3 cannot quote a realistic $25 USDG→stock trade without USDG;
0.5 cannot attempt a swap; Phase 5's live leg has nothing to spend; and §11's
"~$200 capital" is currently aspirational.

### F0.2.7 — The LLM gateway has zero credits

**Confidence: measured. Verdict: fail** (against Phase 2 being runnable).

`402 insufficient_credits` on every gateway call. The key is authorized; the
balance is zero.

**Blocks:** unit 1.7 (analyst cost), all of Phase 2, and the risk agent. Probe
0.6 (`/v1/credits`, `/v1/usage`) will now also measure a zero balance, which is
still a useful shape check but not a useful number.

### What 0.2 changes

| Change | Where |
|---|---|
| `BANKR_LLM_KEY` scope is Read Only + LLM Gateway, not "gateway only" | `planning/PLAN.md` §6 |
| Either auth header works; `X-API-Key` is a preference | `planning/PLAN.md` §6 |
| Agent API "off" is asserted in code, not measured against the surface | 0.2 done-condition |
| Two funding blockers, both hard | §11, and probes 0.3 / 0.5 / 0.6 / 1.7 |

### Method limitations

- One machine, one egress IP, one account, one day. Nothing here is evidence
  about a different account or a deployed host with an IP allowlist.
- 20 requests is far below any rate limit, so the absence of `Retry-After` and
  `x-ratelimit-*` headers is **not** evidence that they never appear. Probe 0.10
  owns that question.
- Read endpoints only. Nothing here bounds write behaviour on any surface.
