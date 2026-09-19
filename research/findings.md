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

## Phase 0 exit summary (0.11 ▶)

**Date:** 2026-09-18. The detail sections below are the evidence, in the order
the probes ran; this is the one page to read first. The Phase 0 exit condition —
*every probe has a recorded verdict, including fail and unresolved* — **is met**.
Two units are only **half met** against their own done-conditions (0.4 and 0.10)
and are marked as such rather than rounded up.

| Probe | Question | Method | Result | Confidence | Verdict |
|---|---|---|---|---|---|
| 0.1 | Can a declared credential reach a log? | `tests/test_redaction.py`, offline | Masked, including a credential added after the redactor was written | measured | pass |
| 0.2 | Which auth header does each Bankr surface take; are the key toggles as planned? | `probes/keys.py`: 20 read GETs, invalid-key control | Both headers work everywhere (F0.2.1). `BANKR_LLM_KEY` reads the Wallet API (F0.2.2). All keys resolve to one wallet (F0.2.3). The gateway toggle behaves as planned (F0.2.4). The Agent API toggle cannot be read (F0.2.5). | measured | pass; F0.2.2 **fail** against the plan's scope; F0.2.5 **unresolved** |
| 0.3 | What does a real stock quote on 4663 contain? | `probes/quote.py`: 6 quotes, 3 tickers at $5 and $25, empty wallet | All 12 documented fields present (F0.3.2). USDG is 6 decimals, not 18 (F0.3.1). Quotes are not balance-checked (F0.3.3). Impact is signed (F0.3.4). | measured; which impact field gates is documented | pass; F0.3.1 **fail** against two sources; the gating field **unresolved** by measurement |
| 0.4 ▶ | Do Chainlink equity feeds exist, what corroborates them, is the multiplier applied? | `probes/feed.py`: 33 tickers at one pinned block | 35 of 57 feeds are equity (F0.4.1). GeckoTerminal covers 32 of 32 (F0.4.2). Stocks do have AMM pools (F0.4.3). Divergence tracks the corroborator's liquidity (F0.4.5). Feeds cover 19% of tokens (F0.4.8). | measured | pass; F0.4.3 **fail** against the plan; the multiplier **unresolved** (F0.4.4) — **half met**; checkpoint held, 3 decisions |
| 0.8 | How does the fund know a token is the real one? | `probes/identity.py`: registry snapshot, 5 checks × 9 candidates, 381-address sweep | The registry is the authority and carries no version, so sha256 serves (F0.8.1). Feed presence admits both counterfeits (F0.8.3). Registry and beacon agree on all 381 (F0.8.4). The registry alone is sufficient (F0.8.5). | measured; the trust argument inferred | pass; 4 decisions |
| 0.5 | Can this operator execute a stock swap? | `probes/execute.py`: one AAPL attempt | 403 location gate, before broadcast, no gas (F0.5.1–F0.5.2). The body is prose with no code (F0.5.3). | measured; the seven causes documented, one reconstructed (F0.5.4) | **fail**, as expected; whether the key can transact was unresolved (F0.5.5) until 0.10 |
| Testnet | Can chain 46630 host an execution demo? | `probes/testnet.py` | None of the issuer's 194 assets is there (F0.T.2). The Stock contracts exist (F0.T.3). The identity heuristics invert (F0.T.4). No feed directory (F0.T.5). No Bankr routing (F0.T.6). | measured; F0.T.6 documented | **fail** for the demo |
| 0.6 | Can cost be reconciled, not just estimated? | `probes/credits.py`: 13 GETs, two controls | Both endpoints answer and are free (F0.6.1–F0.6.2). Attribution is aggregate only (F0.6.4). `days` is silently coerced (F0.6.5). Credits are wallet-scoped and usage key-scoped (F0.6.6). | measured; F0.6.6 documented | pass; per-call attribution **fail**; F0.6.6's gap later explained (F0.7b.10) |
| 0.7 ▶ (a–e) | Is a paid call fast enough, and who can pay us? | `x402_roundtrip`, `x402_thirdparty`, `portfolio_check`, `x402_logs`, `x402_paid`, `x402_clients/` | Settles once the handler returns a `Response` (F0.7d.2–F0.7d.4). ~4.6 s paid, ~0.5 s cold start (F0.7d.5). Revenue is an on-chain `PaymentSettled` (F0.7b.5–F0.7b.6). The payer header is platform-asserted (F0.7d.7). The portfolio endpoint omits tokens (F0.7b.8). v1 clients cannot pay; `@x402/fetch` v2 can (F0.7e). No in-band receipt (F0.7e.7). | measured; a third-party buyer **inferred** (F0.7e.6) | pass; v1 clients **fail**; checkpoint: buyer client decided, **price undecided** |
| 0.9 | What does an analyst call cost? (a floor; 1.7 owns the number) | `probes/llm_cost.py`: 2 calls at Sonnet 5, 6 assets | $0.0134 and 58 s per call (F0.9.1). `/v1/usage` went backwards (F0.9.2). A client timeout is still billed (F0.9.3). Model choice is a 139× lever (F0.9.5). One block gives a trend analyst nothing (F0.9.6). | measured; the 35-asset column is arithmetic | pass, as a floor; F0.9.2 **fail** for per-call reconciliation |
| 0.10 | Does a same-key repeat broadcast twice? What does a rate limit look like? | `probes/idempotency.py` (one $0.08 swap), `idempotency_evidence.py`, `ratelimit.py` | Same-key repeat deduped (F0.10.1). The execution key can transact (F0.10.2). The swap is a sponsored 4337 UserOperation in a 7702 transaction (F0.10.3). 6 bps unaccounted for (F0.10.4). No 429 within 150 requests in 4.1 s (F0.10.5). | measured; the 409 path documented | pass; rate limit **unresolved**; F0.10.4 **unresolved** — **half met** |

### Assumptions that died in Phase 0

Each was stated or relied on somewhere in the plan or the discovery reports, and
each is now recorded against the finding that ended it:

- **About the data.**
  - Tokenized stocks have no AMM pool (F0.4.3).
  - USDG has 18 decimals (F0.3.1).
  - Chainlink has no equity feeds on 4663 — a sampling artefact (F0.4.1).
  - A single-block snapshot is enough for an analyst (F0.9.6).
- **About the Bankr surfaces.**
  - The credit balance cannot be read (F0.6.1).
  - `BANKR_LLM_KEY` is gateway-only (F0.2.2).
  - The gateway rejects `Authorization: Bearer` (F0.2.1).
  - The portfolio endpoint describes the wallet's holdings (F0.7b.8).
- **About identity.** The name marker or `uiMultiplier()` identifies a genuine
  stock (F0.3.6 and F0.4.6, retired by the 0.8 decisions).
- **About x402 revenue.**
  - Revenue lands at a shared address we cannot evidence (F0.7.6, corrected by
    F0.7b.5).
  - No standard client can pay us (F0.7.3, corrected by F0.7e).
- **About execution.** The execution wallet sends its own transactions
  (F0.10.3).

### What Phase 1 needs that Phase 0 did not deliver

**Config values that a probe was named to resolve and did not.** Each is still
`null`, and `null` blocks the check that reads it:

| Value | File | Named resolver | What Phase 0 did deliver | Still needed | Blocks |
|---|---|---|---|---|---|
| `feed_staleness_max_seconds` | `thresholds.json` | probe 0.4 | Across 33 feeds at one block in market hours, `updatedAt` spanned 13,063 s, against an 86,400 s heartbeat and a 0.5% deviation threshold. Any single bound under ~14,000 s rejects live feeds. The recommendation is a per-feed heartbeat rule, not a constant (F0.4.7). | A decision on the rule's shape and its numbers. Overnight and weekend behaviour is unmeasured. | 1.3 |
| `quote_max_age_seconds` | `thresholds.json` | probe 0.3 | Only that stale `quoteId`s "fall back silently" (documented). Nothing on how fast a quote drifts. | A number, ideally from a measurement of quote drift | 1.5, 1.6 (tradeability) |
| `impact_max_bps` | `thresholds.json` | probe 0.3 | Impact is signed; observed −15 to +2 bps at $5 and $25 (F0.3.4); platform cap 1,500. `swapImpactBps` gates execution (documented). | A number, compared signed (`impact > limit`) | 1.6 (tradeability) |
| `worker_deadline_seconds` | `models.json` | 2.4, informed by 1.7 (0.9 relocated) | 58 s for one call at the floor (F0.9.1), and a client-side timeout is still billed (F0.9.3). `transport_timeout_seconds` and `cadence.json`'s `cycle_deadline_seconds` are also null. | Numbers set from 1.7's measurement. 1.7 itself needs a transport timeout above 58 s to run safely. | 1.7, Phase 2 |
| `analyst_model` | `models.json` | 2.4, informed by 1.7 (0.9 relocated) | Priced across the catalogue: 139×, $0.07–$10.05 a month (F0.9.5). Sonnet 5 was used provisionally. | A decision; 1.7 runs "against the intended model" | 1.7, Phase 2 |

**Open decisions and gaps, as recorded, not resolved:**

- **Contradiction.** `planning/PLAN.md` §11's reason for selling on Base is that
  "the standard client's network enum excludes 4663". That is true of the v1
  client and false of the decided v2 client. It is marked in §11 and not
  reconciled. It does not block Phase 1.
- **Gap.** The staleness and replay rules in PHASE-0-1 1.11 and PLAN §9 were
  written for single observations, and invariant 2 now carries a price series.
  Whether they bind a series' newest point or every point is undecided, and it
  **blocks 1.3's and 1.11's tests.**
- **The 0.7 price.** $0.05 needs 1.3–2.3 sales a day to cover inference at the
  floor (F0.9.4). This is revisited at 1.7 and does not block Phase 1.
- **The live-leg asset** for Phase 5. This checkpoint is where
  `planning/PHASE-0-1.md` asks for the decision. The evidence so far is that
  ETH↔USDG on 4663 executes, deduplicates, and was gas-sponsored for one $0.08
  sell (§0.10). Not decided.
- **Funding.** 1.5 must re-run probe 0.3 at $25 against a USDG-funded wallet. The
  wallet holds 0.078742 USDG and 0.000460 ETH (about $1.21) on 4663, against the
  ~$200 target.
- **Still open, but not blocking — each has a stated way to proceed:**
  - The multiplier (F0.4.4): 1.4 follows the documented rule and says so.
  - The in-flight `409` path (F0.10.1): exercised at 4.10.
  - The rate limit (F0.10.5): 1.3 backs off on a bare 429.
  - What the 7702 delegate permits (F0.10.3).
  - The 6 bps gap (F0.10.4).
  - A third-party buyer (F0.7e.6): settled at 7.5.
  - `config/universe.json`'s own note still calls the beacon a secondary flag;
    1.2 rewrites that file.

**For the operator at this checkpoint:** which of these to settle before 1.1
starts, and which ungated asset carries the live leg. Phase 1 does not start
until you have looked.

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

---

## 0.3 — Quote shape

**Date:** 2026-09-17 · **Method:** `PYTHONPATH=src python3 -m probes.quote` and
`python3 -m probes.assets` · **Captures:** `probes/out/quote.json` (6 quotes)

> **Sizing caveat, and it bounds everything below.** The wallet holds ~$2 of ETH
> on Base and nothing on Robinhood Chain (F0.2.6). This is a **shape probe, not a
> realistic-size probe**: it establishes which fields exist, not what the fund
> could actually trade. `planning/PLAN.md` §11 sets the nominal size at $25 and
> unit 1.5 exists precisely because a small quote tells you nothing about a real
> position. **Unit 1.5 must re-run this against a funded wallet** before any
> number here is treated as evidence about executable liquidity.

> **Address caveat.** `config/universe.json` is empty until 0.8. Addresses came
> from `https://tokens.coingecko.com/robinhood/all.json`, the discovery list
> `research/agent-os.md` documents *and distrusts*. They are **unverified**.

### F0.3.1 — USDG is 6 decimals, not 18

**Confidence: measured, three independent ways. Verdict: fail** (against the
research and `planning/PLAN-v1.md` §4).

| Source | Says |
|---|---|
| `research/agent-os.md` (`poolsfun/chains.py:70`) | 18 |
| `planning/PLAN-v1.md` §4 | 18 |
| CoinGecko discovery list | 6 |
| **`decimals()` on chain**, block 65,979,130 | **6** |
| **`/wallet/swap-quote` response**, `from.decimals` | **6** |

The two documented sources agree with each other and are both wrong. A sizing
path that trusted them would be off by 10^12 — $25 would become $25 × 10^-12, or
an attempted spend of $25 trillion, depending on direction.

Robinhood stock tokens are confirmed **18** decimals (AAPL, NVDA, TSLA, GME), so
the research is right about stocks and wrong about the cash leg. The two are
different, which is exactly the shape of error a single "tokens on 4663 are 18
decimals" mental model produces.

**Plan change:** nothing in `planning/PLAN.md` §7–§13 states USDG decimals, so
there is nothing to correct there; the number is recorded in `probes/assets.py`
with its on-chain provenance and belongs in `config/universe.json` at 1.2. The
general lesson is in `tracker/LESSONS.md`.

### F0.3.2 — The documented response schema matches reality exactly

**Confidence: measured. Verdict: pass.**

All 12 documented fields were present in all 6 responses. Nothing documented was
absent; nothing undocumented appeared.

```
from{chain, token, amount, formattedAmount, symbol, decimals, usdValue}
to  {chain, token, amount, formattedAmount, symbol, decimals, usdValue}
minBuyAmount  feeBps  feeWaivedForEcosystemToken  slippageBps
priceImpactBps  swapImpactBps  maxPriceImpactBps
sellTokenPriceUsd  buyTokenPriceUsd  quoteId
```

PHASE-0-1 0.3's done-condition assumed only three fields were guaranteed —
`from`, `to`, `minBuyAmount`. In practice all 12 appeared every time. **This does
not upgrade them to guarantees.** Six responses, three tickers, one size pair,
one minute. Unit 1.5 still treats an absent field as `null`, never as zero.

`amount` is **human-readable** in the request (`"5"`, not base units), while the
response carries both `amount` (raw integer string) and `formattedAmount`. That
matches our `(raw_int, decimals, asset_id)` convention on the way out and breaks
it on the way in, so 1.5 owns the conversion at the adapter edge.

### F0.3.3 — A $25 quote prices fine against an empty wallet

**Confidence: measured. Verdict: pass** (and it is the useful kind of pass).

Every $25 quote returned 200 with a full price, though the wallet holds no USDG
at all. Quotes are documented as ungated; this measures that they are also not
balance-checked.

**Consequence, and it is the one that matters:** a successful quote is not
evidence of anything about ability to execute. This is the concrete instance of
`planning/PLAN-technical-review.md` finding 3 — "a small snapshot quote supports a
stock, but the eventual position requires a much larger order" — and it means
unit 3.3's planner must size against *reconciled holdings*, never against the
fact that a quote returned.

### F0.3.4 — Impact can be negative, and the two impact fields never differed

**Confidence: measured. Verdict: unresolved** (on which field gates).

| Ticker | $5 | $25 |
|---|---|---|
| AAPL | +2 bps | 0 bps |
| NVDA | 0 bps | −2 bps |
| TSLA | −12 bps | −15 bps |

Two things follow.

**Impact is signed.** Negative is price improvement. A gate written as
`abs(impact) > limit` would reject a *better* price; it must be
`impact > limit`. Recorded for unit 3.4.

**`priceImpactBps` and `swapImpactBps` were identical in all 6 responses.**
`planning/PLAN-v1.md` §4 claims execution gates on `swapImpactBps` while
`priceImpactBps` is display-only. This probe cannot distinguish them — at these
sizes they never diverged. Unresolved, and it stays unresolved until a size large
enough to separate them is quotable, which needs a funded wallet.

`maxPriceImpactBps` came back **1500** on every quote, confirming the documented
15% platform limit. `slippageBps` defaulted to **500** and `feeBps` was **0**.

### F0.3.5 — The quote carries a USD price per token

**Confidence: measured. Verdict: pass, with a caveat for 0.4.**

`buyTokenPriceUsd`: AAPL 337.10, NVDA 221.36, TSLA 369.29. `sellTokenPriceUsd`
for USDG was 1.0022, so USDG is not exactly a dollar and $25 nominal is ~24.94
USDG — a rounding the planner must do, not assume away.

This is a **candidate corroborating price source for probe 0.4**, which matters
because 0.4's fallback plan already anticipates GeckoTerminal having no coverage
for stock tokens. It is the fallback the plan named, and it carries the same
caveat the plan gave it: **not independent of the execution venue.** It is the
venue's own price.

### F0.3.6 — Three tokens answer to the symbol GME, identically

**Confidence: measured. Verdict: pass** (as a warning, not a capability).

The discovery list carries `GameStop • Robinhood Token` (`0x1b0e…`), `GameStop`
(`0x7e86…`) and `Greatest Meme Ever` (`0xef67…`). All three are on 4663, all
three are 18 decimals, and all three answer `decimals()` on chain
indistinguishably. Only the `• Robinhood Token` name marker separates them, and
`research/agent-os.md` records that the same list truncates `name` at 60
characters, chopping that marker off longer names.

This is the concrete case probe 0.8 has to solve, and it is why
`planning/PLAN.md` §2 invariant 8 pins assets by `(chain_id, address)`.

### Two operational notes

**Both discovery sources and the 4663 RPC return 403 without a `User-Agent`
header.** `tokens.coingecko.com`, `reference-data-directory.vercel.app` and
`RPC_4663_MAINNET` all refused a bare `urllib` request and all answered with one
set. Unit 1.3's HTTP client must send a User-Agent, and a 403 from any of them
should not be read as an auth failure.

**The quote endpoint leaks no schema.** Five differently-shaped bodies all
returned an identical `{"message":"Invalid request body"}`. The request schema
came from `https://docs.bankr.bot/wallet-api/swap/`, read 2026-09-17 —
**documented**, not measured, except that the documented shape demonstrably works.

### What 0.3 changes

| Change | Where |
|---|---|
| USDG is 6 decimals; stock tokens are 18 | `config/universe.json` at 1.2 |
| Impact gates compare signed values, not magnitudes | 3.4 |
| A successful quote is not evidence of executability | 3.3 planner |
| Request `amount` is human-readable; adapter owns conversion | 1.5 |
| HTTP client must send a User-Agent | 1.3 |
| `swapImpactBps` vs `priceImpactBps` distinction unproven | re-run at 1.5 |

---

## 0.4 — Chainlink equity feeds, coverage, and the multiplier

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.feed` ·
**Captures:** `probes/out/feed.json` · **Pinned block:** 66,353,908 (`0x3f47af4`)
on chain 4663

> **This unit opened by correcting the previous session's own record.** At the
> close of 0.3 the directory was fetched, reported 57 feeds, and four were
> sampled — BTC, ETH, LINK, USDG. No equity feed was seen, and `tracker/LOGS.md`
> recorded that as *an observation, not a finding*, because the other 53 were
> never enumerated. That caution was correct: the equity feeds were there all
> along.

### F0.4.1 — 35 of the 57 feeds are equity feeds

**Confidence: measured. Verdict: pass.**

Every row of `feeds-robinhood-mainnet.json` enumerated, none sampled:

| Class | Count | Examples |
|---|---|---|
| Equity / ETF (`us_equities_24/5`) | **35** | AAPL, NVDA, TSLA, GME, SPY, QQQ, SLV, USO |
| Crypto, stablecoin, exchange rate | 22 | BTC, ETH, LINK, USDG, USDC, WSTETH/STETH |

The equity feeds are named `Robinhood <TICKER> / USD`, carry
`docs.assetClass: "Equity"`, `heartbeat` 86,400 s and `threshold` 0.5 %, and
report 8 decimals. A sample drawn on crypto tickers cannot hit that naming, which
is exactly how four draws returned four crypto feeds.

**`planning/PLAN.md` §11's "Chainlink marks the book" survives.** It was the
premise most at risk in this unit and it is now measured rather than assumed. The
divergence veto has two genuinely different prices to compare (F0.4.2), and
1.4's design stands as written.

Two equity rows — `Robinhood SGOV-USD` and `Robinhood USAR-USD` — carry no
`docs.baseAsset`. They are reported unresolved rather than repaired by parsing
the display name.

### F0.4.2 — GeckoTerminal covers every stock token we could address: 32 of 32

**Confidence: measured. Verdict: pass.**

`planning/PHASE-0-1.md` 0.4 required coverage to be settled before divergence,
and `tracker/LESSONS.md` (2026-09-17, *probe 0.4 tests GeckoTerminal coverage
before divergence*) expected it to be **absent**, on the reasoning that
GeckoTerminal prices come from pools and tokenized stocks have no pool of their
own. Measured: the `robinhood` network slug returns a `price_usd` for **all 32**
addressable tickers.

**The fallback is not needed.** The corroborating source stays GeckoTerminal, it
*is* independent of the execution venue, and the divergence veto stays
cross-source rather than degrading to quote-versus-feed. The contingency in that
lessons entry does not fire.

### F0.4.3 — Tokenized stocks do have AMM pools, contradicting the documented claim

**Confidence: measured. Verdict: fail** (against `planning/PLAN.md` §13).

This is why F0.4.2 came out the way it did, and it contradicts a sourced
statement the plan is built on. `research/bankr-skills.md` quotes
`bankr/references/tokenized-stocks.md:42`: *"tokenized stocks have no AMM pool of
their own."* On chain:

| Token | Pools listed | Deepest pool | Reserve |
|---|---|---|---|
| SPY | 20 | `SPY / USDG 0.3%` | $9,160,174 |
| AAPL | 20 | `AAPL / USDG 0.3%` | $1,077,549 |
| CLSK | 20 | `CLSK / USDG 4.68%` | $2,456 |

Real pairs against USDG and WETH, real reserves, real 24 h volume — $68.8 M on
SPY, $54.9 M on NVDA, $0.01 on CLSK.

**What this reopens, and it is not ours to close.** `tracker/LESSONS.md`
(2026-09-17, *"depth" removed as a concept*) deleted depth from the vocabulary
because the plan asserted there was no pool to measure. The premise was wrong.
Whether depth returns is a decision for the operator, not a repair to make here;
the operational definition of tradeable in `config/thresholds.json` is unchanged
by this probe. **`planning/PLAN.md` §13's "Tokenized stocks have no AMM pool of
their own" must be corrected regardless of that decision**, because it is stated
as fact and it is false.

### F0.4.4 — Is the feed already multiplier-adjusted? **Unresolved.**

**Confidence: measured (the numbers). Verdict: unresolved (the question).**

This is the half of 0.4's done-condition that is **not met**, and the reason is
the effect size, not a gap in the method.

Nine of the 33 tokens carry a `uiMultiplier()` other than exactly 1.0. The other
23 carry exactly 1.0, where both hypotheses are identical by construction, so
they measure the noise floor:

| | n | median | mean abs | range |
|---|---|---|---|---|
| **The effect** — multiplier size | 9 | 5.7 bps | 8.4 | 0.7 – 22.1 bps |
| **The noise** — control vs GeckoTerminal | 23 | −4.7 bps | **141.9** | −610.4 – +506.9 |
| Treatment as-is vs GeckoTerminal | 9 | 18.1 | 62.1 | −168.5 – +112.7 |
| Treatment ×multiplier vs GeckoTerminal | 9 | 25.9 | 64.4 | −163.7 – +113.4 |

The largest multiplier in the whole set is ORCL at 22.1 bps. The noise between
the feed and its corroborator averages 141.9 bps and reaches 610. **The effect is
roughly an order of magnitude smaller than the measurement error**, so neither
hypothesis can be rejected. Applying the multiplier makes the mean absolute
divergence marginally *worse* (62.1 → 64.4 bps), which leans toward
already-adjusted, but 2.3 bps of movement inside a 142 bps noise floor is not
evidence and is not recorded as any.

**What remains documented, and stays documented.** `research/agent-os.md:333`
quotes `robinhood-chain-stocks/SKILL.md:51-53` — *"Prices come from a per-asset
Chainlink `AggregatorV3Interface` feed (8 decimals) and already incorporate the
multiplier… do not multiply it by `uiMultiplier()` again"* — and
`planning/PLAN-technical-review.md` finding 6 cites Robinhood's own oracle
documentation to the same effect. Two independent documented sources agree. This
probe neither confirms nor contradicts them; it establishes that **at today's
multiplier sizes the question is not observable from prices**, which is a
different and weaker statement than agreement.

**The Bankr quote cannot break the tie, and must not be used to.**
`tokenized-stocks.md:67`, quoted in `research/bankr-skills.md`, states *"Token
price = the underlying equity's price × that multiplier, so Bankr prices these
off the equity rather than off pool liquidity."* The venue applies the multiplier
itself, so comparing the feed against the venue's quote asks the multiplier
question of a source that has already answered it. It is circular here, on top of
being venue-dependent.

**What would settle it:** an asset whose multiplier is large enough to clear the
noise — a corporate action moving it well past 100 bps — or an archive read
across a multiplier change, which the one public 4663 endpoint cannot serve
(`research/agent-os.md` §8). Neither is available today.

**Consequence for 1.4.** `planning/PHASE-0-1.md` 1.4 says the mark handles the
multiplier "per probe 0.4" and warns against applying it twice. 0.4 does not
supply that answer. 1.4 must follow the documented rule — do not apply
`uiMultiplier` again — and the comment in `core/valuation.py` must point here and
say the basis is **documented, corroborated by two sources, and not measured**,
rather than pointing at a finding that settled it.

### F0.4.5 — Divergence tracks pool liquidity, not feed quality

**Confidence: measured. Verdict: pass.** This is the checkpoint's own question:
is the divergence threshold we chose for a veto realistic?

| 24 h pool volume | n | median abs divergence | worst |
|---|---|---|---|
| ≥ $1 M | 19 | **19.5 bps** | 499.5 bps (AMZN) |
| < $1 M | 13 | **164.7 bps** | 610.4 bps (EWY) |

The four worst rows — EWY 610, RGTI 545, CLSK 507, IONQ 241 — have 24 h volumes
of $3,502, $503, $0.01 and $97. The divergence is the *pool* being wrong, not the
feed.

**AMZN is the exception that stops this being a clean rule.** It diverges 499.5
bps on $2.19 M of volume, while the feed (252.60) and the Bankr quote (253.11)
agree to 20 bps. One liquid name can still carry a 5 % stale pool price.

**Consequence for `config/thresholds.json`.** `divergence_max_bps` is null and
this is the probe that resolves it. A single flat threshold cannot work: set at
50 bps it vetoes eleven of 32 assets on a quiet day; set above 610 bps to
accommodate EWY it will not catch a genuinely broken mark. The threshold needs to
be conditioned on corroborator liquidity, or illiquid names excluded from the
universe at 1.2 and the veto applied only where the corroborator is worth
comparing against. **Recommended and not decided** — it changes 3.4's gate shape
and belongs at the checkpoint.

### F0.4.6 — `uiMultiplier()` reverting is the impersonator discriminator 0.8 needs

**Confidence: measured. Verdict: pass.**

`tracker/LESSONS.md` (2026-09-17, *three tokens answer to GME*) concluded that
probe 0.8 "cannot lean on the discovery list, the name, or a decimals read". A
fourth test does work:

| Address | Name | `uiMultiplier()` |
|---|---|---|
| `0x1b0e…153e` | GameStop • Robinhood Token | **1.0** |
| `0x7e86…8123` | GameStop | **execution reverted** |
| `0xef67…d5f6` | Greatest Meme Ever | **execution reverted** |
| `0x5fc5…d168` | Global Dollar (USDG) | **execution reverted** |

All 32 addressable RH-marked stock tokens answered; every non-stock address
tested reverted. This is the ERC-8056 check `research/agent-os.md:374` predicted
(selector `0xa60bf13d`, recomputed from the signature here rather than copied),
and it is **positive evidence of a genuine Stock Token**, unlike `decimals()`
which all three GME tokens answer identically.

**It is a necessary condition, not a sufficient one.** Nothing stops an
impersonator implementing a function that returns a number. 0.8's allowlist still
comes from the issuer's own deployment list; this belongs alongside the beacon
check as a second consistency flag that a counterfeit must also forge.

### F0.4.7 — Feed decimals, staleness, and the block pin

**Confidence: measured. Verdict: pass.**

**Decimals.** All 33 feeds report **8** from `decimals()` on chain, agreeing with
the directory on every row. Note the asymmetry the sizing code has to carry:
feeds are 8 decimals, stock tokens are 18, USDG is 6 (F0.3.1).

**Staleness.** Observed `updatedAt` spanned 13,063 s across the 33 feeds at one
block — oldest SPY at 12:22:01 UTC, newest GOOGL at 15:59:44 UTC, against an
86,400 s heartbeat and a 0.5 % deviation threshold. A feed 3.6 hours old is
normal here, not stale. `feed_staleness_max_seconds` is null in
`config/thresholds.json`; any bound below ~14,000 s would reject live feeds
during market hours, and this observation is one block on one day and does not
bound the tail. Unit 1.3's staleness rule should key on the published heartbeat
per feed rather than a single constant.

**The block pin is real.** `research/agent-os.md` §8 records the one public 4663
endpoint as carrying no archive data, which would make "readings at one pinned
block" a fiction if the node ignored the block parameter and served current state
— self-consistent output either way. Falsified directly: the same feed read at
block `0x1` returns nothing while the pinned block returns data, so the parameter
is honoured. **Not** evidence of general archive availability; the deep read
returning empty is consistent with both an honoured pin and pruned state.

### F0.4.8 — Chainlink covers 19 % of the tokens, which caps the universe

**Confidence: measured. Verdict: pass, as a constraint.**

The discovery list carries 1,062 tokens on 4663, of which 187 carry the
`• Robinhood Token` marker. Chainlink publishes **35** equity feeds — **19 %**.

If Chainlink marks the book (§11), an asset with no feed cannot be marked, and
therefore cannot be held. The investable universe is **~35 names, not ~190**.
This partly answers `planning/PLAN.md` §12's *"how many of the ~190 tickers are
actually tradeable at our $25 size?"* — tradeability is a separate question, but
markability already removes 81 % of them before it is asked. Unit 1.2's loader
should treat presence of a feed as a membership condition.

### What 0.4 changes

| Change | Where |
|---|---|
| Chainlink equity feeds exist; §11 survives, 1.4 unchanged in shape | `planning/PLAN.md` §11 |
| GeckoTerminal coverage is total; the veto stays cross-source and independent | 1.4, 3.4 |
| "Tokenized stocks have no AMM pool of their own" is false | `planning/PLAN.md` §13 |
| Multiplier handling is documented-only; 1.4's comment must say so | 1.4, `core/valuation.py` |
| A flat `divergence_max_bps` cannot work; condition it on liquidity | `config/thresholds.json`, 3.4 |
| `uiMultiplier()` answering is a second identity flag | 0.8, 1.2 |
| Staleness should key on per-feed heartbeat, not one constant | 1.3, `config/thresholds.json` |
| Universe is capped at the 35 assets with feeds | 1.2, `config/universe.json` |

### Method limitations

- **One block, one day, one machine.** Every divergence number is a single
  observation during US market hours. Nothing here bounds the overnight or
  weekend tail, which is when `us_equities_24/5` feeds and 24/7 pools drift
  furthest apart.
- **Addresses are still unverified.** They come from the 0.3 discovery list,
  filtered on the name marker and on `uiMultiplier()` answering. That is stronger
  than 0.3 and still not the issuer-derived allowlist unit 0.8 owns.
- GeckoTerminal's batch endpoint truncates `top_pools` to one entry where the
  single-token endpoint lists twenty, so the per-asset pool count in the capture
  is a floor and is named as one.
- Nothing was written, submitted or signed. All reads.

---

## 0.5 — Execution eligibility

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.execute --confirm` ·
**Captures:** `probes/out/execute.json` (1 quote, 1 execution attempt, 2 portfolio reads)

> **This probe spent money, or tried to.** It is the only unit so far that used
> `BANKR_KEY_EXEC`. One execution attempt was sent, once, and no retry followed.
> Wallet `0x93faecde3c88a713e1edddf417c02c326889a3da`, chain `robinhood` (4663),
> selling 0.0001 ETH (~$0.26) into AAPL
> (`0xaf3d76f1834a1d425780943c99ea8a608f8a93f9`).

### The refusal, verbatim

```
HTTP 403 in 115 ms
content-type: application/json; charset=utf-8

{"message":"Tokenized stocks (AAPL) are not available in your region."}
```

Untruncated. The response carried exactly one field, `message`, and no other
headers worth keeping.

### F0.5.1 — Tokenized-stock execution is location-gated, confirmed

**Confidence: measured. Verdict: fail** — which is the expected verdict, and it
is now measured rather than documented.

`research/bankr-skills.md`, quoting `tokenized-stocks.md:73-79`, documented that
tokenized-stock trades require location verification and are unavailable in the
US and UK. The operator is in the US. The probe returns exactly that, and
**names both the gate and the asset**: *"Tokenized stocks (AAPL) are not
available in your region."*

**This changes nothing in the plan and confirms a great deal of it.**
`tracker/LESSONS.md` (2026-09-17) already moved stock legs to paper and rescoped
Phase 5 on the documented claim. That decision was taken on documentation and is
now taken on evidence. `planning/PLAN.md` §13's "no live tokenized-stock fills"
is correct as written.

**The refusal fired at the gate being tested**, which
`planning/PHASE-0-1.md` 0.5 requires and which four separate precautions
establish rather than assume:

| Confound | Ruled out by |
|---|---|
| Empty balance | 0.000490 ETH held on 4663 against a 0.0001 sell plus a 0.0002 gas reserve, checked before sending |
| Wrong or dead address | AAPL carries a Chainlink feed (F0.4.1), answers `uiMultiplier()` (F0.4.6) and has 20 pools (F0.4.3) |
| Price-impact rejection | `swapImpactBps` 13 against `maxPriceImpactBps` 1500 on the quote that was sent |
| Spend limit | ~$0.26 against documented $500/tx and $500/24h caps |

### F0.5.2 — The refusal is free: pre-broadcast, no gas, no transaction

**Confidence: measured. Verdict: pass.**

The 403 came back in **115 ms** with no `hash` field, and the wallet's native
balance was identical to the wei before and after — `0.000490162486507929` ETH
both times. Nothing was signed, nothing was broadcast, nothing was billed.

This matters more than it looks. Bankr's own documentation warns that a swap
which mines and reverts returns **200 with `success: false`** and a real hash,
and that gas is charged for it. The location gate sits well upstream of that: it
is checked before the transaction is built. So a treasurer that repeatedly
attempts a gated stock leg burns no gas — it wastes wall-clock and rate-limit
budget, and nothing else.

### F0.5.3 — The cause is identifiable, but only by matching prose

**Confidence: measured for this cause. Verdict: pass, narrowly — and the narrowness is the finding.**

The concern this half of the probe exists to test is whether a 403 can be
decoded at all, given seven causes behind one status code. For **this** cause the
answer is yes: the body names the region gate unambiguously and even names the
offending asset, which is more than the plan expected. It is not the opaque
refusal `planning/PLAN-technical-review.md` finding 15 warned about, and we do
not record a problem where there is not one.

**What is genuinely weak is the envelope, not the wording.** Three Bankr surfaces
return three different error shapes, and the one that matters most here is the
least structured of them:

| Surface | Status | Shape |
|---|---|---|
| LLM gateway | 403 | `{"error":{"message":"…","type":"auth_error"}}` — machine-readable `type` |
| Wallet API | 401 | `{"error":"Invalid API key","message":"…"}` — two flat strings, no code |
| **Wallet API `/wallet/swap`** | **403** | **`{"message":"…"}` — one field, prose, no code at all** |

There is **no machine-readable discriminator** on the swap refusal. Not a code,
not a type, not even the flat `error` field the same API's 401 carries. Unit
5.6's decoder can only match on English prose, and a reworded message — *"your
region"* to *"your location"*, say — silently breaks the match. Whatever the
treasurer does with this, the code must **fail closed on an unrecognised 403**
and surface the raw body, never assume the one cause it knows how to parse.

**Six of the seven causes remain unmeasured.** One sample tells us the location
body is clear; it says nothing about what a paused wallet or a read-only key
returns, or whether those are distinguishable from each other. We do not
generalise from one.

### F0.5.4 — The seven causes exist, but the list was never written down here

**Confidence: documented. Verdict: pass** (as a correction to our own records).

`planning/PLAN-v1.md` §4 and `planning/PHASE-0-1.md` 0.5 both refer to "seven
documented causes" and instruct this probe to map against them. **No file in this
repository enumerates them.** The number was carried forward without the list.

Recovered from `https://docs.bankr.bot/wallet-api/swap/`, read 2026-09-18 — six
from the Errors table, verbatim:

1. Read-only API key
2. Wallet paused
3. Price impact above your wallet's own protection limit
4. **Failed location check** ← measured, F0.5.1
5. Fee beneficiary selling its own fee token
6. A Bankr Terminal spend limit would be exceeded

The seventh is **reconstructed, not quoted**: the same page's Access Control
section says token-security refusals apply "at both quote and execution", making
*buy token banned or flagged by the security scan* a 403 cause on this endpoint
although the Errors table omits it. That is an inference, and it is the one the
count depends on — six are documented and the seventh is ours.

The list is now pinned in `probes/execute.py` with its provenance and the
quoted/reconstructed split preserved.

### F0.5.5 — 0.5 does **not** establish that `BANKR_KEY_EXEC` can transact

**Confidence: measured (the gap). Verdict: unresolved.**

The probe proves a stock swap is refused for region. It does **not** prove the
execution key is write-enabled, because we cannot see the order in which Bankr
evaluates its checks: a location refusal fired, and a read-only key would have
produced a different 403 we never saw. Cause 1 and cause 4 were both live
candidates going in (`probes/out/execute.json`, `causes_before_send`), and only
one of them was eliminated — by the body's wording, not by the status.

**This leaves Phase 5's live leg unproven.** `tracker/LESSONS.md` (2026-09-17)
rescoped Phase 5 around an ungated 4663 swap executed by the treasurer, so that
receipts, reconciliation and the order state machine run against a real chain.
That path depends on `BANKR_KEY_EXEC` being able to transact, which remains
exactly as unresolved as F0.2.2 left it — 0.2 read a portfolio with every key and
deliberately did not test a write.

**What would settle it:** one ungated swap on 4663 with the same key — ETH into
USDG, which quotes at the same size and is not a tokenized stock, so the location
gate does not apply. That is a second spend and is **not** authorised by this
unit, so it was not run. It is the natural first unit of Phase 5 rather than a
repair to 0.5.

### What 0.5 changes

| Change | Where |
|---|---|
| Stock execution gated by region — measured, not documented | `planning/PLAN.md` §13, Phase 5 |
| A gated stock refusal costs no gas and broadcasts nothing | 4.x treasurer, 5.6 |
| `/wallet/swap` 403 carries no machine-readable cause; decode fails closed | 5.6, `core/errors.py` |
| The seven causes are now enumerated, six quoted and one reconstructed | `probes/execute.py` |
| `BANKR_KEY_EXEC`'s ability to transact is still unproven | Phase 5 entry, 4.12 |

### A note that belongs to 0.3

Reading the swap documentation for this unit resolved an open question from
F0.3.4. `planning/PLAN-v1.md` §4 claimed execution gates on `swapImpactBps` while
`priceImpactBps` is display-only, and 0.3 recorded it **unresolved** because the
two fields never diverged at $5 and $25. The documentation states it directly:
`swapImpactBps` is *"the number server-side execution gates on"*, and
`priceImpactBps` is *"for display"*. That makes the claim **documented**, not
measured — the two fields still have not been observed to differ, and F0.3.4's
requirement for a size large enough to separate them stands.

### Method limitations

- **One attempt, one cause, one region, one account, one day.** Everything here
  is evidence about a US-resident operator on this account. It is not evidence
  about what a verified account sees, and 0.5 passing for someone else would not
  make it pass for us.
- Six of the seven 403 causes were never triggered, so nothing here bounds how
  distinguishable they are from one another.
- The attempt used native ETH rather than the documented USDG cash leg, because
  the wallet holds no USDG. A USDG-funded attempt is a different request shape
  and was not tested.
- Nothing was broadcast, so this says nothing about receipt handling, revert
  behaviour, or the `200 success:false` path that unit 4.x must handle.

---

## Testnet — can chain 46630 host an execution demo?

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.testnet` ·
**Captures:** `probes/out/testnet.json`

Out-of-order probe, run because 0.5 measured the mainnet stock gate closed
(F0.5.1) and testnet was still an open question at the Phase 1 gate. Read-only
throughout; no transaction was attempted on testnet, and the Bankr API was never
called with a testnet chain parameter.

### The three-line verdict

| # | Question | Answer | Confidence |
|---|---|---|---|
| 1 | Do tokenized stock tokens exist on 46630? | **The issuer's 194 listed assets: no. The Stock Token contract family: yes — 5 tokens.** | **measured** |
| 2 | Do Chainlink equity feeds exist there? | **No feeds published in Chainlink's reference directory.** Not exhaustively searched on chain. | **measured** (directory level) |
| 3 | Does Bankr route to testnet? | **No.** The documented chain list is mainnet-only. | **documented** |

### F0.T.1 — The endpoint is live, so absence below means absence

**Confidence: measured. Verdict: pass.**

Every claim in this section is a negative, and a negative against a dead endpoint
is worthless. `RPC_4663_TESTNET` — the public endpoint named in the issuer's own
network table — answers `eth_chainId` **0xb626 = 46630**, `net_version` 46630, and
`web3_clientVersion` `nitro/v3.12.0-rc.2`. Block 121,324,358 advanced by ~30
blocks in 4 seconds, and the latest block carried transactions. The explorer
reports 277,060,820 transactions and 23,637,014 addresses with a 212 ms average
block time.

Testnet is not a ghost town — it has **more blocks than mainnet** (121.3M against
66.4M) and heavy traffic.

**A second control, for the method rather than the endpoint.** Of 40 addresses
that recent testnet transactions actually touched, **39 have code**. So
`eth_getCode` is answering, and "no code at this address" below is a fact about
the chain rather than about the probe.

### F0.T.2 — None of the issuer's 194 assets is deployed on testnet

**Confidence: measured. Verdict: fail** (for the demo's purposes), and it is
established from a deployment list, not a sample.

`https://docs.robinhood.com/chain/stock-tokens/` documents an issuer assets API,
and it turns out to be the authoritative registry this build has needed since
0.8 was written. `GET https://api.robinhood.com/rhj/assets` returns **194
assets**, each with a `deployments` array carrying an explicit `chainId`:

```
deployments by chain id: {4663: 194}
```

Every asset, exactly one deployment, all of them on **4663**. **Zero on 46630.**
Each row also carries `tokenSymbol`, `tokenName`, `contractAddress`,
`currentMultiplier`, `tradingCapabilities` and an `isin`.

Corroborated independently by an **exhaustive same-address check**: of the 194
issuer addresses, plus all 187 `• Robinhood Token` entries from the 0.3 discovery
list, plus all 35 mainnet equity feed proxies (F0.4.1), plus USDG — **not one has
code at the same address on testnet.** Same-address deployment: no.

**This is the answer to question 1 as the plan meant it.** The tokenized stocks
the fund would hold do not exist on testnet.

### F0.T.3 — But the issuer's Stock Token *contracts* are deployed there: five of them

**Confidence: measured. Verdict: pass.** Different-address deployment, and it is
a genuinely different answer from F0.T.2.

Five equity-named tokens on testnet are the same contract family as mainnet stock
tokens:

| Symbol | Name | Address | Holders | `uiMultiplier()` | Decimals |
|---|---|---|---|---|---|
| AMZN | Amazon | `0x5884aD2f920c162CFBbACc88C9C51AA75eC09E02` | 286,850 | **1.0** | 18 |
| TSLA | Tesla | `0xC9f9c86933092BbbfFF3CCb4b105A4A94bf3Bd4E` | 223,165 | **1.0** | 18 |
| AMD | AMD | `0x71178BAc73cBeb415514eB542a8995b82669778d` | 223,026 | **1.0** | 18 |
| PLTR | Palantir Technologies | `0x1FBE1a0e43594b3455993B5dE5Fd0A7A266298d0` | 220,569 | **1.0** | 18 |
| NFLX | Netflix | `0x3b8262A63d25f0477c4DDE23F83cfe22Cb768C93` | 219,034 | **1.0** | 18 |

`uiMultiplier()` answers on all five. That alone proves little (F0.T.4), so three
harder checks were run:

**The proxy bytecode is byte-identical to mainnet's.** Both are 283-byte
`BeaconProxy` runtimes. Removing the embedded beacon address and the solc
metadata trailer leaves 428 hex characters on each side that are **identical**.
This is the technique `research/bankr-skills.md` records for `pantheon-staking`
— "byte-identical (ex-metadata)" — applied here.

**They share one beacon, and it is not mainnet's.** All five resolve through
EIP-1967 to beacon `0x1df3ca0fd30ed5eeb09eb01938f4e9c5196e6ca5` (verified,
`AccessControlsRegistry`) → implementation
`0xbd14156e05c6af28ad39aa53a2ab8eb9cdf657da`. Mainnet stock tokens resolve to
beacon `0xe10b6f6b275de231345c20d14ab812db62151b00` → implementation
`0xb35490d6f9163de4f80d88dc75c3516eb64c5ae2`. Different addresses, and different
sizes — 21,986 bytes on testnet against 23,230 on mainnet — so testnet runs a
different version of the contract.

**The implementation is a verified contract named `Stock`.** solc
`v0.8.33+commit.64118f21`, verified 2026-03-13, exposing exactly the Robinhood
stock-token surface: `uiMultiplier`, `newUIMultiplier`, `updateMultiplier`,
`effectiveAt`, `balanceOfUI`, `totalSupplyUI`, `adminBurn`, `mint`, `pause`,
`tokenPaused`, `uid`, `ACCESS_CONTROLLED_REGISTRY`.

**What this does and does not establish.** It establishes that the Stock Token
machinery runs on 46630 and that five equity-named tokens use it. It does **not**
establish that Robinhood deployed them: attribution rests on identical proxy
bytecode, the contract name, and verification, all of which are circumstantial,
and the mainnet explorer returned 403 so the deployer addresses could not be
compared. The five are also an arbitrary subset — no AAPL, no NVDA, no SPY — and
carry no `isin`, no `tradingCapabilities`, and no entry in the issuer's registry.

### F0.T.4 — On testnet the identity heuristics invert, and `uiMultiplier()` is worthless

**Confidence: measured. Verdict: pass, as a warning.**

F0.4.6 recorded `uiMultiplier()` answering as "necessary, not sufficient — nothing
stops an impersonator implementing a function that returns a number". Testnet is
that caveat made real, at scale:

- **23 distinct tokens claim the symbol AAPL**, among them `Mock Apple Stock`,
  `Apple (test)`, `AAPLProject`, `Pledge Finance mAAPL` and `vibecat`.
- The explorer returns **140 distinct tokens with Robinhood-flavoured names** —
  `Apple • Robinhood Token`, `AAPL Robinhood Token`, `TEST Robinhood AAPL Stock
  Token`, `Mock Robinhood Stock`. **Not one of the 140 sits behind the Stock
  beacon.** Every token that advertises itself as Robinhood's is a fake.
- The five genuine-looking ones are named plainly — `Amazon`, `Tesla` — with no
  marker at all, and hold 219k–287k holders against the fakes' 11–23.

**The mainnet marker is an anti-signal here.** F0.3.6 established that the
`• Robinhood Token` name marker was the only thing separating the real GME from
two impersonators on mainnet. On testnet the marker appears **only** on fakes.
Any identity rule written at 1.2 or 0.8 that leans on the name marker, or on
`uiMultiplier()` answering, would resolve every one of these the wrong way. The
check that survived is the EIP-1967 beacon.

### F0.T.5 — Chainlink publishes no reference directory for Robinhood testnet

**Confidence: measured, at the directory level. Verdict: fail.**

Four namings were tried and all 404: `feeds-robinhood-testnet.json`,
`feeds-robinhood-testnet-sepolia.json`, `feeds-robinhood-chain-testnet.json`,
`feeds-robinhood-mainnet-testnet.json`.

**With a positive control, because 0.4's mistake was concluding absence from a
guess.** `feeds-ethereum-testnet-sepolia.json` returns **200 with 60 feeds**, so
the `feeds-<chain>-testnet-<name>.json` convention exists and is served. A 404 on
the Robinhood testnet spellings is therefore evidence of absence from the
directory, not evidence of a wrong guess.

**The limit of this finding, stated plainly:** it is about the *directory*, not
the *chain*. No exhaustive on-chain search for `AggregatorV3Interface` contracts
was run, and none is practical without a list to search. Unpublished feeds cannot
be ruled out. What can be said is that nothing publishes them, so a consumer
would have no way to discover a feed address — which for our purposes is the same
constraint.

### F0.T.6 — Bankr does not route to testnet

**Confidence: documented. Verdict: fail.**

`https://docs.bankr.bot/wallet-api/swap/`, read 2026-09-18, gives the chain
parameter as *"one of `base`, `mainnet` (Ethereum), `polygon`, `unichain`,
`arbitrum`, `bnb`, `worldchain`, `robinhood`, `solana`"*. All mainnet chains; no
testnet variant of any of them. The string `testnet` appears **zero** times
across the Bankr swap, portfolio, wallet-api and root documentation pages, and
`46630` appears zero times.

**Deliberately not measured.** Calling `/wallet/swap` or `/wallet/swap-quote` with
a testnet chain value would settle it empirically, but that is a write path on an
unfamiliar parameter and this probe had no authorization to poke it. The
documented answer is unambiguous enough that an unauthorized experiment is not
worth it.

### What this means for the demo

Stated as consequence, not as design — the execution path is not this probe's to
choose.

The combination is **(1) partially yes, (2) no, (3) no**. Five stock-family
tokens exist on testnet, but Bankr cannot reach them, so any execution there
means calling a DEX directly — which the plan already identifies as "a different
and larger piece of work". And with no discoverable price feed, `planning/PLAN.md`
§11's "Chainlink marks the book" has nothing to mark with on 46630, so a testnet
demo would need a different mark as well as a different executor.

Testnet does not rescue the execution story. What Phase 5 already planned — a
real ungated swap on 4663 mainnet through the treasurer — remains the only path
that exercises the real executor, and F0.5.5's open question about whether
`BANKR_KEY_EXEC` can transact still gates it.

### What this changes

| Change | Where |
|---|---|
| The issuer's asset registry is found; it is the deployment list 0.8 needs | 0.8, 1.2; `config/universe.json` |
| Identity must key on the EIP-1967 beacon, not the name marker or `uiMultiplier()` | 0.8, 1.2 |
| Testnet carries no issuer assets, no published feeds, no Bankr routing | Phase 1 gate, Phase 5 |

### Method limitations

- **The token sweep is not exhaustive.** The explorer's token list was walked to
  60,000 entries, ordered by holder count descending, and the cut fell at **7
  holders** — so every testnet ERC-20 with more than 7 holders was examined, and
  anything below that was not. The *absence* claim in F0.T.2 does not rest on
  this sweep; it rests on the issuer registry and the same-address check.
- Attribution of the five tokens to Robinhood is **circumstantial**. The mainnet
  Blockscout API returned 403 to this probe, so deployer addresses could not be
  compared across chains.
- The public testnet RPC rate-limits aggressively (HTTP 429 under batching).
  Calls retry with backoff and a rate-limit is recorded as its own outcome,
  never as a missing contract — a 429 read as "no code" would manufacture
  exactly the absence this probe is testing for.
- No transaction was attempted on testnet, so nothing here says whether a swap
  there would succeed, what DEX liquidity exists, or whether the five tokens are
  transferable by an ordinary holder.

---

## 0.6 — Credits and usage

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.credits` ·
**Captures:** `probes/out/credits.json` (13 read-only GETs)

**One-line verdict on attribution granularity:** usage is attributable to an
**(API key × model × rolling day-window)** aggregate and to nothing finer — there
are no per-request rows and no request identifier anywhere in the response.
**Measured** for the response envelope; the per-model row shape is **documented,
not measured**, because this key has zero usage and `byModel` came back empty.

### F0.6.1 — Both endpoints exist and answer; finding 13 is confirmed

**Confidence: measured. Verdict: pass.**

| Call | Status | Fields returned |
|---|---|---|
| `GET /v1/credits` (`BANKR_LLM_KEY`) | **200** | `object`, `balanceUsd`, `effectiveBalanceUsd`, `undeductedCostUsd` |
| `GET /v1/usage` (`BANKR_LLM_KEY`) | **200** | `object`, `days`, `startDate`, `endDate`, `totals`, `byModel` |
| `GET /v1/credits` (*invalid key, control*) | **401** | `{"error":{"message":"Invalid or inactive API key","type":"auth_error"}}` |
| `GET /v1/usage` (*invalid key, control*) | **401** | same |
| `GET /v1/credits` (`BANKR_KEY_READ`) | **403** | *"This API key does not have LLM Gateway access enabled…"* |
| `GET /v1/usage` (`BANKR_KEY_READ`) | **403** | same |

The controls are what make the 200s evidence. The invalid key is refused on both
endpoints, so the header is read rather than ignored (the F0.2.1 argument), and
`BANKR_KEY_READ` is refused with the toggle named explicitly, so these endpoints
sit behind the LLM Gateway capability and are not open to any key on the account
(consistent with F0.2.4).

**`planning/REVIEW-RESPONSE.md` finding 13 is confirmed, and
`planning/PLAN-v1.md` §4 is refuted.** §4 asserted "credit balance is not
programmatically readable, so our cost figures are our own token counts and must
be labelled as estimates". The balance reads in 132 ms. The original source,
`research/openclaude.md`, was careful — it said unreadable *through the path that
repo used* — and the generalisation into a platform fact happened downstream of
it. **This is the same over-reading as F0.2.1**, from the same report, on a
different claim: a scoped negative about one client turned into a claim about the
provider.

**But finding 13 must not be over-read in the other direction either.** It says
cost estimates "get reconciled against provider **totals**", and totals is exactly
what is on offer. It does not promise per-call attribution, and F0.6.4 is why
that distinction decides unit 6.3.

### F0.6.2 — The reads cost nothing, measured rather than assumed

**Confidence: measured. Verdict: pass.**

`balanceUsd` was read before the probe's calls and again after: **2.825608 both
times, delta 0.0**, with `undeductedCostUsd: 0` and
`effectiveBalanceUsd == balanceUsd` (nothing in flight). The documentation states
every GET keeps working even when a spend budget is exceeded; this confirms they
are also free. Thirteen requests changed nothing.

### F0.6.3 — Field sets as returned, against as documented

**Confidence: measured. Verdict: pass, with two additions and one informative absence.**

**`/v1/credits`.** Every documented field was present except `dailyBudget`, which
is documented as *"Present only when a daily spend budget is set on the wallet.
Omitted entirely when spend is uncapped."* Its absence is therefore a measurement,
not a gap: **this wallet has no daily spend cap set.** The documentation adds that
there are no per-key spending caps at all — the balance is the whole limit. So the
only thing bounding gateway spend today is the $2.83 balance itself.

**`/v1/usage`.** All six documented top-level fields present. `totals` carried
**ten** fields where the documentation lists eight — two undocumented:
`totalImageOutputTokens` and `totalImageCost`. Both zero here. They cost nothing
to carry and unit 2.5 should read them rather than assume image spend is
impossible.

```
totals: totalRequests, totalInputTokens, totalOutputTokens,
        totalCacheReadInputTokens, totalCacheWriteInputTokens, totalTokens,
        totalCost, totalCacheCost, totalImageOutputTokens, totalImageCost
```

Everything is **zero** and `byModel` is `[]`. Expected — no successful inference
call has ever been made on this key. F0.2.7 recorded the gateway at zero credits
and every call returning 402; it has since been funded, and nothing has spent it.

### F0.6.4 — Attribution is aggregate only. There is no per-request evidence.

**Confidence: measured (the envelope). Verdict: fail, against per-call reconciliation.**

This is the finding unit 6.3 turns on, and *readable* is not the same property as
*attributable*.

The response contains no array other than `byModel`, no `requestId`, no `traceId`,
and no identifier field of any kind — `totalRequests` is a **count**, not a
handle. The finest attribution the provider offers is:

| Axis | Available? | How we know |
|---|---|---|
| Per API key | yes | the endpoint is scoped to the authenticated key (documented), and `BANKR_KEY_READ` is refused rather than returning its own row |
| Per model | field present | `byModel` is present as a key — **but empty**, so the row shape is documented and not measured |
| Per time window | yes | `days` measurably moves `startDate`/`endDate` (F0.6.5) |
| **Per request** | **no** | no array, no id field, in a complete envelope |
| **Per analyst** | **no** | nothing in the response knows what an analyst is |

**The honest limit of this finding.** With zero usage on the key, an empty
per-request array could in principle be omitted rather than returned as `[]` —
though `byModel` *was* returned as `[]`, which is evidence the endpoint does emit
empty collections rather than dropping them. The documented schema independently
shows no per-request rows. Both point the same way; neither is a demonstration
against live data.

**What would settle it, and why this probe did not do it:** one real gateway
completion, followed by re-reading `/v1/usage` to see whether a row appears and
whether it carries anything that maps back to that call. That spends credits and
is outside 0.6's scope, which is two GETs. It belongs with unit 1.7's cost
measurement, which has to make real calls anyway.

**Consequence for 6.3, stated as a constraint and not a design.** A per-cycle or
per-analyst cost line cannot be evidenced by the provider. It can only be *our*
token count, allocated, and reconciled in aggregate against `totals.totalCost` for
a window. So the total may be booked as measured; any finer breakdown must carry
`is_estimate: true`. `planning/PLAN.md` §2.5's "token accounting per call,
reconciled against `/v1/usage`" remains correct only if "reconciled" means
aggregate-to-aggregate — the per-call half is ours alone.

### F0.6.5 — `days` is accepted, and silently coerced out of range

**Confidence: measured. Verdict: pass, with a trap.**

| Request | `days` returned | Window |
|---|---|---|
| `/usage` | 30 | 2026-08-19 → 2026-09-18 |
| `/usage?days=1` | 1 | 2026-09-17 → 2026-09-18 |
| `/usage?days=7` | 7 | 2026-09-11 → 2026-09-18 |
| `/usage?days=90` | 90 | 2026-06-20 → 2026-09-18 |
| `/usage?days=0` | **30** | 2026-08-19 → 2026-09-18 |
| `/usage?days=91` | **90** | 2026-06-20 → 2026-09-18 |

A time range is accepted and genuinely moves the window. Out-of-range values are
**silently coerced** — `0` falls back to the default 30 and `91` clamps to 90,
both returning **200** with no warning. A caller that asks for 91 days and books
the answer as 91 days of cost is wrong by a day and has nothing in the status code
to tell it. The window is self-describing, so the rule for 1.7 and 6.3 is to read
`days`, `startDate` and `endDate` back off the response and never trust the value
that was sent.

Also note `endDate` is **now**, not midnight: the window trails the request
instant. Two calls seconds apart cover different windows, so a cost figure is only
meaningful with the returned `startDate`/`endDate` attached.

### F0.6.6 — Credits and usage are different accounting boundaries

**Confidence: documented, with a measured discrepancy that it explains.**
**Verdict: unresolved.**

`/v1/usage` is scoped to *"the authenticated API key"*. `/v1/credits` reports the
*wallet*, and the documentation says the wallet's spend *"spans all metered LLM
spend on the wallet, not just gateway traffic: requests from every API key it
owns, plus Max Mode and app-invoked Bankr agent runs."* **These are not the same
boundary**, so a balance movement cannot be explained by one key's usage, and the
two endpoints cannot be reconciled against each other without knowing every other
consumer of the wallet.

The measured hint: the balance reads **$2.825608**, while `tracker/LOGS.md` records
the gateway being funded to **$3.00**, and `/v1/usage` reports **0 requests and
$0.00 cost across a full 90-day window**. A gap of roughly **$0.174** is
unaccounted for by this key's gateway traffic.

**Marked unresolved, deliberately.** The $3.00 is our own note of an operator
action, not a provider receipt, so the gap may be a funding fee, a rounding, or
spend by another consumer of the same wallet — the documentation makes the last
one entirely ordinary. It is recorded because it is exactly the class of
discrepancy the books are supposed to surface rather than smooth away, and because
a reconciliation built on "balance delta equals our usage" would already be wrong
by $0.17 before the fund has made a single inference call.

### What 0.6 changes

| Change | Where |
|---|---|
| Finding 13 confirmed; §4's "not readable" is refuted | `planning/PLAN-v1.md` §4 (superseded), 6.3 |
| Aggregate reconciliation only; per-analyst cost stays `is_estimate: true` | 6.3, 2.5 |
| Read `days`/`startDate`/`endDate` back; never trust the value sent | 1.7, 6.3 |
| `totals` carries two undocumented image fields | 2.5 |
| No daily budget and no per-key cap: the balance is the only bound | 0.10, `config/thresholds.json` |
| Credits is wallet-scoped, usage is key-scoped — not reconcilable to each other | 6.3 |

### Method limitations

- **Zero usage on the key.** Every number is a zero, so this measures the
  *shape* of the endpoints and not their behaviour under load. `byModel`'s row
  contents, the cache-token fields and per-model cost are all unobserved.
- One key, one wallet, one account, one day. Nothing here bounds what a wallet
  with a daily budget set would return.
- Read-only GETs only. No inference call was made, so nothing here demonstrates
  how quickly usage appears after a request, or whether it appears at all before
  a request settles.

---

## 0.7 — x402 round trip

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.x402_roundtrip --confirm` ·
**Captures:** `probes/out/x402.json` · **Handler:** `probes/x402/roundtrip/index.ts`

**Headline: the paid call failed, so two of the three timings do not exist.** The
endpoint deployed, the 402 is captured in full, and payment was attempted once
and refused by the platform. No retry was made and no parameter was adjusted.
Nothing was spent.

### F0.7.1 — `/wallet/portfolio` under-reports token balances

**Confidence: measured. Verdict: fail.**

Found before the probe proper, while checking whether 0.7 was fundable.
`GET /wallet/portfolio` returned `tokenBalances: []` for `base`. `balanceOf` on
USDC (`0x8335…2913`) at the same moment returned **108,346 base units =
$0.108346**.

The endpoint did not report a zero balance — it reported **no token entry at
all**, which is indistinguishable from "this wallet holds no tokens". Had the
probe trusted it, 0.7 would have been recorded as blocked on funding when the
funds were there.

**This is the measurement behind `planning/PLAN.md` §6.** That section already
requires the treasurer to read the execution wallet's balances over RPC rather
than trusting an authenticated portfolio endpoint, and F0.2.3 called that
requirement "more important, not less". It is no longer a precaution: the
portfolio endpoint is **wrong** about this wallet today. Unit 1.5's sizing and
Phase 6's reconciliation must read balances over RPC, and F0.2.6's "the fund
wallet is empty" should be re-read with this in mind — it measured the same
endpoint that is now known to omit tokens.

### F0.7.2 — The 402 challenge, verbatim

**Confidence: measured. Verdict: pass.** Unpaid GET, no authentication, free.

```json
{
  "x402Version": 2,
  "error": "Payment Required",
  "facilitator": "https://api.bankr.bot/facilitator",
  "accepts": [
    {
      "scheme": "exact",
      "network": "eip155:8453",
      "asset": "0x833589fcd6edb6e08f4c7c32d4f71b54bda02913",
      "amount": "1000",
      "maxAmountRequired": "1000",
      "payTo": "0x8AEE621035D93Deb3C0C1177fac252dC2dd501a0",
      "resource": "https://x402.bankr.bot/0x93faecde3c88a713e1edddf417c02c326889a3da/roundtrip",
      "description": "Phase 0 probe: static response, no work. Measures x402 platform round-trip overhead only.",
      "maxTimeoutSeconds": 60,
      "mimeType": "",
      "extra": { "name": "USD Coin", "version": "2" }
    }
  ]
}
```

`maxTimeoutSeconds: 60` is the payment authorization's validity window, **not** a
handler runtime budget — `research/x402-cli-example.md` Q1 is explicit about that
distinction and it holds here.

### F0.7.3 — A standard published x402 client cannot pay this endpoint

**Confidence: measured. Verdict: fail** — and it is the most consequential
finding in this unit.

The challenge advertises `x402Version: 2` and `network: "eip155:8453"`. Against
the published client libraries:

| Package | Latest on npm | Speaks protocol v2? | Knows `eip155:*`? |
|---|---|---|---|
| `x402` | **1.2.0** | no — `x402Versions = [1]` | no — `eip155` appears **once** in the whole package |
| `x402-fetch` | 1.2.0 (depends `x402@^1.2.0`) | no | **zero** occurrences of `eip155` |
| `@coinbase/x402` | 2.1.0 | 3,746-byte wrapper, no protocol code | zero |

`NetworkSchema` in `x402@1.2.0` is still the closed zod enum the research
described — 17 bare names: `abstract, abstract-testnet, base-sepolia, base,
avalanche-fuji, avalanche, iotex, solana-devnet, solana, sei, sei-testnet,
polygon, polygon-amoy, peaq, story, educhain, skale-base-sepolia`. **`base` is in
it. `eip155:8453` is not.** Every `accepts` entry is parsed through that schema,
so a standard client throws before selection or signing — for two independent
reasons, the version and the network identifier format.

**This does not overturn the decision to price in USDC on Base; it shows the
decision was necessary and is not sufficient.**
`research/x402-cli-example.md` §7 correctly established that a USDG-on-4663
endpoint is unpayable because the chain is absent from a closed enum. Pricing in
USDC on Base removed that blocker. What this probe measures is that **the blocker
moved** — from the *chain* to the *protocol version and identifier format* — and
the fund's endpoint is still not payable by the published ecosystem.

**Not our misconfiguration.** A live third-party endpoint
(`0x79bb…9884/crypto-price`, $0.002) returns a structurally identical challenge:
same `x402Version: 2`, same `eip155:8453`, same asset, same facilitator, same
`payTo`, same `maxTimeoutSeconds`. Only the amount differs. This is how the
platform speaks to everyone.

**What is unresolved:** whether an unpublished or pre-release v2-aware client
exists, and whether Bankr intends `x402Version: 2` to be reachable by non-Bankr
callers at all. Bankr's own CLI clearly implements it. We measured the published
packages, not the whole world.

### F0.7.4 — The paid call failed. Two of the three timings do not exist.

**Confidence: measured. Verdict: fail.**

| Call | Result |
|---|---|
| unpaid (402) | **280 ms**, then 156 ms and 107 ms on later observations |
| CLI baseline (`bankr x402 schema`, unauthenticated read) | 423 ms |
| **paid, cold** | **failed after 2,849 ms** — `API error (400): x402 payment failed (status 500)` |
| **paid, warm** | **not attempted** — the probe stopped |

The probe stopped on the failure by design rather than adjusting the price or the
asset and trying again, so there is no warm number and **the unit's central
timing question is unanswered**. We cannot state the end-to-end latency of a paid
call, and the cached-record design is therefore still supported by
`research/x402-cli-example.md` Q1's architectural argument alone — Bankr itself
returns a job handle rather than doing the work inside the handler — and **not**
by a measurement of our own.

**Nothing was spent.** USDC read over RPC before and after: **108,346 base units
both times, delta 0.** `bankr x402 list` and `bankr x402 revenue roundtrip` both
report **0 requests, $0.000000 earned**, consistent with a payment that never
settled and with the documented rule that 402 responses are free and do not
count.

**The cause is not diagnosed, and one 500 does not separate transient from
structural.** What the evidence rules out: it is not a malformed challenge
(F0.7.3 shows ours matches a working endpoint's), not an empty balance
($0.108 against a $0.001 price), not the price cap (`--max-payment $0.01`), and
not a handler error (the handler never ran — the payment gate sits in front of
it, and 0 requests were counted). What remains, untested: a transient
facilitator fault, or a platform refusal to let a wallet pay an endpoint it owns
— **the payer and the endpoint owner are the same wallet here, because the fund
has only one**. Distinguishing those needs either a second attempt later or a
call to a third-party endpoint from this wallet. Both spend money, neither is
authorised by this unit, and guessing between them would be manufacturing a
finding.

### F0.7.5 — The payer header was not observed

**Confidence: unresolved.**

`x-402-payer` reaches the **handler**, after settlement. No payment settled, so
the handler never ran and the header's real shape is **unmeasured**. Unit 7.3
binds a purchase to a decision id using it, and that binding still rests on
`research/x402-cli-example.md` Q2, which found no server code anywhere and marked
the header's existence *"[INFERRED as plausible but unverifiable from these
sources]"*.

**That inference is not promoted here.** Observing it needs a handler that echoes
the header and one settled payment — deliberately not bundled into this probe,
because a handler that reads request state is no longer a handler that does no
work, and the timing measurement was the reason it exists.

### F0.7.6 — Every Bankr endpoint collects to one shared address

**Confidence: measured. Verdict: pass, as a constraint on the books.**

`payTo` is `0x8AEE621035D93Deb3C0C1177fac252dC2dd501a0` — **a contract**, 6,978
bytes of code on Base, and **the same address the third-party endpoint
advertises**. Payment does not go to the fund's wallet. It goes to a shared Bankr
router which credits the endpoint owner internally, surfaced through
`bankr x402 revenue`.

**Consequence for `planning/PLAN.md` §2 invariant 9** — *"revenue is evidenced by
settlement"*. Settlement lands at an address we do not control, so revenue cannot
be evidenced by a USDC inflow to our own wallet. It can only be read from Bankr's
accounting until a payout moves funds to us. This is the same shape as F0.6.6:
the provider's books and ours have different boundaries, and Phase 6 must treat
the x402 revenue line as a claim reconciled against a payout, not as an observed
on-chain receipt.

**Fee treatment (documented, not measured):** 0% platform fee for the first 1,000
settled requests per month, 5% after. Only settled requests with a handler status
below 400 count; 402 responses are free and excluded. Nothing settled here, so
none of it was exercised.

### What 0.7 changes

| Change | Where |
|---|---|
| `/wallet/portfolio` omits token balances; read over RPC | 1.5, Phase 6; `planning/PLAN.md` §6 |
| Published x402 clients cannot parse our challenge (v2 + `eip155:*`) | 7.2, the revenue line, `planning/PLAN.md` §11 |
| Revenue settles to a shared Bankr address, not our wallet | 6.x, 7.4; invariant 9 |
| Paid-call latency remains unmeasured; cached-record design rests on architecture | 1.4, 7.x |
| `x-402-payer` shape still inferred, not measured | 7.3 |

### Method limitations

- **One payment attempt, one endpoint, one wallet, one minute.** A single 500
  bounds nothing about reliability, and the probe deliberately did not retry.
- The payer and payee are the same wallet, which is not how a real purchase
  works and is a plausible contributor to the failure. The fund has one wallet,
  so this probe could not avoid it.
- Timings for the paid path include Bankr CLI startup; the 423 ms unauthenticated
  baseline is reported alongside rather than subtracted, because an adjusted
  number presented as a measurement is worse than two honest ones.
- `x402Version: 2` was measured against the **published** npm packages only.
- The endpoint is left deployed and active at $0.001 so the attempt can be
  repeated once the cause is decided.

---

## 0.7b — The payment failure, separated

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.x402_thirdparty --confirm` ·
**Captures:** `probes/out/x402_thirdparty.json` (1 payment, 2 unpaid challenges)

### F0.7b.1 — A third-party payment succeeds. The 500 is specific to our endpoint.

**Confidence: measured. Verdict: pass** (for the client, the wallet and the
facilitator).

One payment, no retry, no fallback endpoint. The target was `hello`
(`0x79bb…9884`) at **$0.001** — deliberately not the marketplace's cheapest
($0.000001), because paying one base unit would have changed the owner *and* the
amount against 0.7 and left a failure indistinguishable from a dust rejection.
Price, network, asset, platform and handler triviality all match our own
endpoint. Exactly one variable differs: who owns it.

| | ours (0.7) | third party (0.7b) |
|---|---|---|
| `x402Version` / `network` | 2 / `eip155:8453` | 2 / `eip155:8453` |
| amount / asset / `payTo` | 1000 / USDC / `0x8AEE…01a0` | 1000 / USDC / `0x8AEE…01a0` |
| payer wallet | `0x93fa…a3da` | `0x93fa…a3da` |
| **result** | **500, nothing settled** | **200, settled** |

```
Paid $0.0010 USDC on eip155:8453
Status 200
{"message":"Hello, World! Powered by Bankr x402 Cloud.",
 "timestamp":"2026-09-18T18:00:05.196Z"}
```

**So the client works, the wallet can pay, and the facilitator settles.** A
transient facilitator fault is no longer a good explanation for 0.7's 500.

**What this does not prove, and it is the trap worth naming.** It proves *we can
pay*. **Our own endpoint is still untested** — nobody other than its owner has
ever paid it, and the fund has one wallet, so this probe could not arrange that.

### F0.7b.2 — The mechanism behind the 500 is still unresolved

**Confidence: measured that it is endpoint-specific. Verdict: unresolved** (on why).

Two hypotheses survive, and this probe cannot separate them:

1. **Self-payment refused** — the platform declines to let a wallet pay an
   endpoint it owns. Fits every observation.
2. **Something specific to our endpoint's payment setup** — it was deployed by a
   hand-written `bankr.x402.json` rather than the interactive scaffold, so a
   field the wizard would have set may be missing or wrong.

A third — **our handler failing to execute** — fits less well but is not
excluded. Bankr documents *settle-after-response*: "payments are only collected
if your endpoint returns successfully", and only a handler status below 400
counts. A handler that threw would therefore also produce a 500 with nothing
settled and 0 requests counted. Against it: the CLI's wording was *"x402 payment
failed"*, naming the payment step rather than the handler. **That is a client's
prose error string and F0.5.3 is the standing warning about reading those as
structured causes**, so it lowers the probability rather than eliminating it.

**What would separate them:** a payment to our endpoint from a wallet that does
not own it. That needs a second wallet, which the fund does not have, and it is
the same experiment the demo's buyer agent will perform anyway.

### F0.7b.3 — A paid round trip is ~4.6 s, and that supports the cached-record design

**Confidence: measured, with a caveat on "cold".**

| | ms |
|---|---|
| unpaid 402 (ours) | 107–280 |
| unpaid 402 (third party) | 163–316 |
| CLI baseline, unauthenticated read | 453 |
| **paid call, end to end** | **4,589** |

Roughly **4.1 s** of that is the payment round trip once CLI startup is removed —
reported alongside rather than subtracted, per 0.7's method note.

**This is not cleanly a cold start.** `hello` is a public endpoint that other
callers use, so its container may have been warm; we control neither its
traffic nor its state. The honest reading is that **~4.6 s is what a paid call
costs against a trivial third-party handler**, and a genuine cold start is at
least that.

**It still settles the design question 0.7 could not.** Against a documented 30
second handler ceiling, ~4 s of platform overhead on a handler that does
*nothing* leaves little room, and `research/x402-cli-example.md` Q1's
architectural argument — Bankr itself returns a job handle rather than working
inside the handler — now has a measurement consistent with it. **Serving a
cached record is required, not merely prudent.**

### F0.7b.4 — Settlement is asynchronous to the HTTP response

**Confidence: measured. Verdict: pass, and it matters for the books.**

The probe read USDC before and after the paid call and saw **no change** —
108,346 base units both times, even though the CLI reported `Paid $0.0010 USDC`
and returned a 200 with the response body. Re-reading moments later:

```
USDC now: 107,346  (delta -1,000 = exactly $0.001)
USDC Transfer, Base block 51,482,531:
  0x93fa…a3da  ->  0x8aee…01a0   1000  (0.001000 USDC)
  tx 0x4a44835a9fea6d71af…
```

**The buyer receives its answer before the money moves.** A 200 is therefore not
evidence of settlement, which is `planning/PLAN.md` §2 invariant 9 stated from
the other side — *"nothing is booked from an HTTP status"* — and this is the
concrete instance. Any accounting that booked x402 spend or revenue at
response-time would book it before it happened, and would be wrong for any call
that failed to settle afterwards.

**One more thing the transfer shows:** the payment goes **directly from the
payer's wallet** to the shared router, on chain, in a single USDC transfer. So
the *spend* side is observable on chain from our own wallet. The revenue side is
F0.7b.5.

### F0.7b.5 — Revenue *is* an on-chain receipt. This corrects F0.7.6.

**Confidence: measured. Verdict: pass — and it reverses an inference of ours.**

F0.7.6 observed that `payTo` is a shared contract used by every endpoint and drew
the conclusion that *"payment does not go to the fund's wallet… revenue cannot be
evidenced by a USDC inflow to our own wallet."* **The observation was right and
the conclusion was wrong.** The settlement transaction contains **two** USDC
transfers, atomically:

```
tx 0x4a44835a9fea6d71af6cd90182e536ddb359f337d994657dd2c5972e1afa6604
  0x93fa…a3da (payer)  ->  0x8aee…01a0 (router)   1000
  0x8aee…01a0 (router) ->  0x79bb…9884 (seller)   1000
```

`0x8AEE…01a0` is **`BankrFeeRouterV2`**, verified on Base, solc 0.8.25. It is a
pass-through splitter, not a custodial collector: `settleAndSplit`,
`settleUptoAndSplit`, `splitAfterPermit2`, with `MAX_FEE_BPS = 2000` and a
separate `bankrFeeWallet` (`0xf606…163e`). The seller's share moves to the
seller's own wallet in the same transaction.

**So `planning/PLAN.md` §2 invariant 9 — "revenue is evidenced by settlement" — is
satisfiable exactly as written**, and no rewording is needed on this account. We
do not redesign it here; we record that the evidence exists.

### F0.7b.6 — The settlement evidence available to us, in full

**Confidence: measured.**

The router emits one event per settlement, and it is better evidence than a bare
transfer because three of its fields are indexed:

```solidity
event PaymentSettled(
    address indexed token,
    address indexed payer,
    address indexed owner,
    uint256 totalAmount,
    uint256 ownerAmount,
    uint256 bankrFee,
    uint16  feeBps
)
```

topic0 `0xfdc355c44a725f89b3989010cdad404cf378ba8db57896a4b7a623cdd66d30d9`.
As emitted for our payment: token USDC, payer `0x93fa…a3da`, owner
`0x79bb…9884`, `totalAmount` 1000, `ownerAmount` 1000, `bankrFee` **0**,
`feeBps` **0**.

Both queries were run and both work:

| Filter | Meaning | Result today |
|---|---|---|
| `topics[3] == our wallet` | every sale we make | **0 events** — nobody has bought from us |
| `topics[2] == our wallet` | every x402 purchase we make | **1 event** — the payment above |

**What this makes obtainable, without trusting any HTTP status or any provider
ledger:** every sale, its buyer, its gross, its net and the fee taken, addressed
by our own wallet, from a public log. Three independent corroborations of one
sale are available — the `PaymentSettled` event, the USDC `Transfer` into our
wallet in the same transaction, and Bankr's own `bankr x402 revenue` figures.

**The fee is measured, not merely documented.** `feeBps: 0` and `bankrFee: 0` on
a real settlement is the free tier (first 1,000 settled requests per month)
observed rather than read off a pricing page. The contract's own ceiling is
`MAX_FEE_BPS = 2000` — 20%, well above the documented 5% Pro rate, so the
contract permits more than the published price list promises. Worth knowing; not
alarming on its own, since the rate applied is in the event.

**Buyer identity does not depend on the `x-402-payer` header.** `payer` is an
indexed field on the settlement event, so a purchase can be bound to a buyer
address from the chain even if the header proves unavailable or unreliable. That
is evidence for unit 7.3 to use; designing the binding is 7.3's job, not this
probe's.

### F0.7b.7 — Self-payment works for someone else, which weakens F0.7b.2's first hypothesis

**Confidence: measured (one counterexample). Verdict: unresolved, and shifted.**

While querying settlements platform-wide over a 400-block window, two events
appeared. One of them is:

```
blk 51482249  payer=0xf4a46667d75fa9663ab7a297af20d3623aaa8b52
              owner=0xf4a46667d75fa9663ab7a297af20d3623aaa8b52
              total=10000  ownerAmount=10000  fee=0  feeBps=0
```

**Payer and owner are the same address, and it settled.** Another wallet
successfully paid its own endpoint, for $0.01, minutes before our attempt.

This is a direct counterexample to F0.7b.2's first hypothesis — that the platform
refuses to let a wallet pay an endpoint it owns. It does not refuse categorically.

**Weight therefore shifts to the second hypothesis:** something specific to our
endpoint, most plausibly that it was deployed from a hand-written
`bankr.x402.json` rather than the interactive `bankr x402 configure` wizard, so a
field that wizard sets may be missing or wrong. Handler execution failure remains
possible for the same reason.

**Still unresolved, and deliberately so.** One counterexample from one unknown
wallet does not establish that self-payment is *always* permitted — that wallet's
account, plan or endpoint configuration may differ from ours in ways this probe
cannot see. What it does establish is that "the platform forbids self-payment" is
no longer a sufficient explanation, and that the next thing to try is our own
configuration rather than a second wallet.

### F0.7b.8 — The portfolio endpoint reports native exactly and omits every token

**Confidence: measured. Verdict: fail.**
**Method:** `PYTHONPATH=src python3 -m probes.portfolio_check` ·
**Capture:** `probes/out/portfolio_check.json`

| Chain | native, portfolio vs chain | token entries returned | tokens actually held |
|---|---|---|---|
| base | identical to the wei ✓ | **0** | **2** |
| robinhood | identical to the wei ✓ | 0 | 0 ✓ |

Held on Base and absent from the endpoint:

| Token | On chain | Priced by the explorer? |
|---|---|---|
| USDC `0x8335…2913` | **0.107346** | yes (0.999772) |
| USER `0xbc7d…0db6` | **10.0** | no |

On 4663 the empty list is **correct** — the wallet holds none of USDG, AAPL,
NVDA or TSLA.

**Of the three explanations, one is eliminated and two cannot be separated.**

- **Staleness — rejected.** The USDC arrived at 05:33:13 and was still missing at
  18:00, twelve and a half hours later, while the native balance tracked the
  chain exactly throughout.
- **Specific tokens — poor fit.** It omits USDC, the most mainstream ERC-20 on
  Base. It is not skipping an obscure contract; it is returning nothing at all.
- **A value threshold — consistent, and untestable here.** Every token this
  wallet holds is worth under $0.11, so there is no holding large enough to sit
  above a plausible threshold and prove one exists.

**So the honest statement is narrower than "it filters small balances":
`tokenBalances` returned an empty list for every ERC-20 this wallet has ever
held, and we cannot say whether a larger holding would appear.** At the fund's
intended size — $200 capital, $25 trades — a threshold of the usual kind would
not bite, but that is a hope and not a measurement.

**Consequence.** `planning/PLAN.md` §6 already requires the treasurer to read the
execution wallet's balances over RPC. Unit 1.5's sizing against "reconciled
holdings" and Phase 6's reconciliation must do the same, and **no unit may treat
an empty `tokenBalances` as evidence that a token is not held.** Native balances
from this endpoint are exact and may be used.

### F0.7b.9 — Re-checking F0.2.6: the finding stands, its evidence does not

**Confidence: measured. Verdict: F0.2.6 stands.**

F0.2.6 recorded *"the fund wallet is empty"* from the endpoint now known to omit
tokens, so the conclusion had to be re-derived from the chain.

The wallet's **complete** ERC-20 transfer history on Base is five transfers with
no further pages, and the earliest is **2026-09-18T05:33:13Z**. Probe 0.2 ran on
**2026-09-17**. No ERC-20 had ever touched the wallet on Base at that point, and
native balances — which the endpoint reports exactly — were genuinely zero.

**F0.2.6's conclusion was correct. Its evidence was weaker than it appeared:** the
same endpoint would have reported `tokenBalances: []` whether or not tokens were
present, so "empty" was never something that reading could establish. It happened
to be true. No other finding depends on the portfolio endpoint for a *token*
balance — F0.2.3 (one wallet across three keys) rests on `evmAddress`, which is
unaffected.

**One gap, stated rather than papered over:** 4663 has no reachable token
enumeration — its Blockscout sits behind Cloudflare — so the 4663 half of F0.2.6
rests on a pinned four-token check rather than on history. A token outside that
set could have been held and missed, then as now.

### F0.7b.10 — The F0.6.6 credit gap is explained by the funding transfer

**Confidence: measured (the transfers). Verdict: the discrepancy resolves; the
fee is inferred.**

F0.6.6 recorded $0.174392 of unexplained difference between the $3.00 the LOGS
say funded the gateway and the $2.825608 `/v1/credits` reports, and left it
**unresolved**, noting it might be a fee or spend by another consumer of the
wallet. The Base transfer history settles the shape of it:

```
05:33:13   +3,108,346 USDC   from 0x4f6f…C059   (funding arrives)
05:33:17   -3,000,000 USDC   to   0x071F…0c31   (credit purchase, four seconds later)
```

Exactly **$3.000000** left the wallet for a single address, and credits read
**$2.825608** — a **5.81%** difference. So the gap is on the **purchase** side,
not the usage side, and F0.6.6's worry that another consumer of the wallet had
spent it is not supported: `/v1/usage` reporting zero requests was accurate.

**Inferred, not measured:** that the 5.81% is a funding fee or spread. No fee is
disclosed on any page we read, and we did not observe the credit being minted.
What is measured is that $3.000000 went out and $2.825608 arrived as credit.

**This does not weaken F0.6.6's structural point**, which stands untouched:
`/v1/credits` is wallet-scoped and `/v1/usage` is key-scoped, so the two cannot
be reconciled against each other. It removes the specific unexplained number, not
the boundary problem.

### What 0.7b / 0.7c change

| Change | Where |
|---|---|
| The 500 is endpoint-specific, not a facilitator fault | 7.2 |
| Self-payment is not categorically refused; our config is the next suspect | 7.2 |
| Revenue **is** an on-chain receipt — F0.7.6 corrected, invariant 9 satisfiable | `planning/PLAN.md` §2 inv. 9; 6.x, 7.4 |
| `PaymentSettled(token, payer, owner, …)` is the revenue evidence, `owner` indexed | 6.x, 7.3, 7.4 |
| Platform fee measured at 0 bps on a real settlement; contract ceiling 20% | 6.x |
| A paid round trip is ~4.6 s — cached-record design required | 1.4, 7.x |
| Settlement is asynchronous to the 200; never book from a response | 4.x, 6.x, 7.4 |
| `tokenBalances` is empty for every token held; use RPC, never the endpoint | 1.5, 6.x; `planning/PLAN.md` §6 |
| F0.2.6 stands; F0.6.6's unexplained $0.174 resolves to the purchase side | — |

### Method limitations

- **Our endpoint is still untested.** One third-party payment proves the client,
  the wallet and the facilitator. Nobody but the owner has ever paid
  `roundtrip`, and the fund has one wallet, so this probe could not arrange it.
- **One payment each way.** No retry was made anywhere, so nothing here bounds
  reliability or variance; the 4,589 ms figure is a single observation against a
  third-party handler whose warm/cold state we do not control.
- The self-payment counterexample is one settlement by one unknown wallet, whose
  account, plan or configuration may differ from ours.
- The value-threshold hypothesis for `tokenBalances` is untestable on this
  wallet: nothing it holds is worth more than $0.11.
- 4663 has no reachable token enumeration (Cloudflare), so its balance check is a
  pinned four-token set, not a sweep.
- `x-402-payer` remains unobserved. It reaches the handler after settlement, and
  no payment to our handler has settled.

---

## 0.7d — The endpoint fixed, and which hypothesis was right

**Date:** 2026-09-18 · **Captures:** `probes/out/x402_logs_roundtrip.json`

### F0.7d.1 — The handler ran and threw. The config hypothesis is refuted.

**Confidence: measured. Verdict: fail** (against F0.7b.2's leading hypothesis).
**Method:** `PYTHONPATH=src python3 -m probes.x402_logs`

`bankr x402 revenue` reporting **0 requests** looked like evidence the handler
never ran. It is not: Bankr counts only **settled** requests, so a request that
ran, threw, and was therefore never charged also shows 0. The count cannot
separate the two hypotheses, and this is a small instance of the standing rule —
an absence produced by a filter is not an absence.

The CLI has no `logs` command, but the dashboard is documented as showing console
output, so the data exists. Reading the installed CLI's own source
(`@bankr/cli/dist/commands/x402.js`) gave the path —
`GET /x402/endpoints/logs/{service}`, undocumented on the docs site and answering
to the ordinary read key. It returns:

```
2026-09-18T17:50:54.518Z  GET /0x93fa…a3da/roundtrip
status=500  settled=false  durationMs=1485
payerAddress=0x93faecde3c88a713e1edddf417c02c326889a3da
amount=1000 USDC ($0.001000)

ERROR  error: fetch() did not return a Response
       at fetch (/opt/runtime.ts:611:17)
       at async #acceptRequest (/opt/runtime.ts:526:29)
       at async accept (/opt/runtime.ts:505:32)
REPORT Duration: 209.24 ms  Billed Duration: 716 ms
       Memory Size: 256 MB  Max Memory Used: 87 MB  Init Duration: 506.38 ms
```

**So the platform routed the request, accepted the payment authorization, and
called our code, which threw.** Everything the config governs — the route, the
price, the asset, the network, the payment gate — worked. **F0.7b.2's leading
hypothesis is wrong**, and so is the plan that followed from it: redeploying
through the wizard would have fixed nothing about the config, because the config
was never broken.

**`settled: false` confirms settle-after-response from the seller's side.** The
handler returned 500, so the authorization was never captured — which is why
nothing was charged and why F0.7b.4's on-chain check found no transfer.

**Two numbers fall out of the trace that 0.7 could not measure:**

| | |
|---|---|
| **Init Duration (cold start)** | **506.38 ms** |
| Handler duration | 209.24 ms |
| Billed duration | 716 ms |
| Container | 256 MB, 87 MB used |

That is a **real cold start**, from our own container, on a handler that does no
work — the number F0.7b.3 could only bound from the outside at ~4.6 s end to end.
Roughly half a second of it is container init.

**`payerAddress` is recorded by the platform** and appears in the log even for an
unsettled request. That is adjacent to the `x-402-payer` question (F0.7b.5) but is
not the same thing: this is a field in an operator-facing log, not a header our
handler received.

### F0.7d.2 — The cause: the handler's return shape, not the deploy

**Confidence: measured (the error). Verdict: our bug.**

The runtime error is `fetch() did not return a Response`, raised at
`/opt/runtime.ts:611` — the host expects the module's default export to behave as
a `fetch` handler returning a `Response`. Our handler was:

```ts
export default function handler(_req: Request) {
  return { ok: true, probe: "0.7", work: "none" };
}
```

The quick-start documents exactly this as supported — *"You can return plain
objects, strings, or any JSON-serializable value — Bankr auto-wraps them into a
JSON response"* — and its own example is `export default async function
handler(req: Request)`. Ours differs in one respect: it is **not `async`**. The
auto-wrap did not happen, and the raw object reached a runtime that required a
`Response`.

**Documented behaviour and measured behaviour disagree**, and the measured one is
what ships. Whether the trigger is specifically the missing `async` is tested in
F0.7d.3 by changing that and nothing else.

### F0.7d.3 — The config diff: no meaningful difference. The handler diff: the whole fault.

**Confidence: measured. Verdict: the leading hypothesis is refuted.**

`bankr x402 add wizardcheck` then `bankr x402 configure wizardcheck` were run
through a pty, accepting every default, and the generated config compared to our
hand-written one field by field. The CLI's own source
(`@bankr/cli/dist/commands/x402.js:226,286`) was read alongside and agrees with
what the wizard produced.

| Field | Wizard | Ours | Material? |
|---|---|---|---|
| `price` | `"0.001"` | `"0.001"` | identical |
| `description` | present | present | identical in kind |
| `methods` | `["GET"]` | `["GET"]` | identical |
| `schema` | present | present | identical in kind |
| `currency` | `"USDC"` per service | inherited from top level | **no** — documented as inherited |
| `network` | `"base"` per service | inherited from top level | **no** — documented as inherited |
| `paymentScheme` | `"exact"` | absent | **no** — defaulted correctly; the live 402 advertised `"scheme":"exact"` |
| `category`, `tags` | absent | `"data"`, `["probe"]` | ours has *extra* documented fields |

**The wizard sets nothing our config lacked in any way that mattered.** Two
fields it writes per-service are inherited from the top level in ours, one
defaulted to exactly the value the wizard would have set — proven by the 402
challenge captured in F0.7.2 — and the only asymmetry runs the other way, with
ours carrying two extra documented fields.

**So the plan this task was built on does not survive its own first step, and the
contingency fires: there is no meaningful config difference, and the cause is
elsewhere.** F0.7d.1 already located it.

**The handler is where the two diverge, and it is not subtle:**

```ts
// the CLI's scaffold
export default async function handler(req: Request): Promise<Response> {
  const url = new URL(req.url);
  return Response.json({ message: "Hello from wizardcheck!",
                         timestamp: new Date().toISOString() });
}

// ours
export default function handler(_req: Request) {
  return { ok: true, probe: "0.7", work: "none" };
}
```

Three differences: **`async`**, the declared **`Promise<Response>`** return type,
and returning **`Response.json(...)` rather than a plain object**. The runtime
raised `fetch() did not return a Response`, which names the third directly.

**The documentation is wrong on this point, and that is worth recording
separately from our bug.** The quick-start states *"You can return plain objects,
strings, or any JSON-serializable value — Bankr auto-wraps them into a JSON
response"*. The platform's own scaffold does not rely on that, and our handler,
which did, failed. Either the auto-wrap requires something the docs do not state
(a promise, most likely) or it does not exist on this runtime path. Unit 7.2
should follow the scaffold, not the prose.

### F0.7d.4 — The endpoint works. One variable changed, and it settled.

**Confidence: measured. Verdict: pass.**
**Method:** `PYTHONPATH=src python3 -m probes.x402_paid --confirm`

Between the failure and this attempt, exactly one thing changed: the handler
returns `Response.json({...})` instead of a plain object. Same service name, same
URL, same $0.001, same network, same asset, same hand-written config, still no
work in the handler.

```
rc=0 in 4,615 ms
Paid $0.0010 USDC on eip155:8453
Status 200
{"ok": true, "probe": "0.7", "work": "none"}
```

**Verified from the chain, not from the 200** (F0.7b.4's rule):

```
PaymentSettled — block 51,482,994
tx 0x769587739708e5d7fe1b111381d6e2bfdf460d4f349533e6dcfdf870e61a5a16
payer = 0x93faecde3c88a713e1edddf417c02c326889a3da
owner = 0x93faecde3c88a713e1edddf417c02c326889a3da
total = 1000   ownerAmount = 1000   bankrFee = 0   feeBps = 0
```

**This is the first revenue evidence the fund has produced** — a `PaymentSettled`
event with our own address as `owner`, queryable by anyone from a public log.

And the endpoint's own log agrees: `status=200`, **`settled=true`**, against the
earlier `status=500`, `settled=false`. Both entries are now visible side by side,
which is as clean a before-and-after as this probe could hope for.

**So the cause is settled: the handler's return shape, and nothing else.** The
config was never at fault (F0.7d.3), and self-payment was never refused
(F0.7b.7, now confirmed directly — payer and owner are the same address in a
settlement that went through).

**What this does not isolate.** Three things changed in the handler at once —
`async`, the `Promise<Response>` type, and `Response.json(...)`. The runtime error
named the return value, so that is the likely trigger, but each further variant
would cost another paid call and the unit authorised one. Unit 7.2 should copy
the scaffold's shape entirely rather than pick at which part mattered.

### F0.7d.5 — A real cold start: ~513 ms of container init

**Confidence: measured.**

| | failed attempt (v1) | successful attempt (v2) |
|---|---|---|
| **Init Duration** | 506.38 ms | **512.98 ms** |
| Handler duration | 209.24 ms | **148.20 ms** |
| Billed duration | 716 ms | 662 ms |
| Platform `durationMs` | 1,485 | 1,480 |
| Client wall clock | 2,849 (failed) | **4,615** |
| Memory | 256 MB, 87 MB used | 256 MB, 86 MB used |

Both attempts were fresh deploys, so **both init figures are genuine cold
starts**, and they agree within 7 ms.

The layers separate cleanly: **~513 ms container init**, **~148 ms** running a
handler that does nothing, **~1,480 ms** total platform-side, and **~4,615 ms**
end to end for the client including CLI startup and payment signing. So roughly
**3.1 s of the round trip is payment and client work outside the platform's own
handler path.**

**This confirms the cached-record design as required, with our own numbers.**
F0.7b.3 could only bound it from outside at ~4.6 s against a third-party handler.
Now: against a documented 30-second handler ceiling, a handler that does
*literally nothing* already consumes ~1.5 s platform-side and ~4.6 s end to end. A
multi-analyst cycle takes minutes. The handler must serve something already
computed.

### F0.7d.6 — A self-paid sale nets to zero, and the balance is not the evidence

**Confidence: measured. Verdict: pass, as a warning for the books.**

USDC before and after: **107,346 both times, delta 0** — even though a sale
settled. The transaction explains it:

```
0x93fa…a3da  ->  0x8aee…01a0 (router)   1000
0x8aee…01a0  ->  0x93fa…a3da (us)       1000
```

We are both payer and owner, so the money left and came back in the same
transaction. Gas was paid by the facilitator (`0x4a15…a584`), not by us.

**A balance delta is therefore not a revenue signal.** Here it is zero for a real,
settled, fee-free sale. `PaymentSettled` is the evidence — which is what F0.7b.6
already concluded, now with a case that would have defeated the naive check.

This is an artefact of the fund owning both sides, and it will not arise once a
separate buyer agent pays. It is worth recording anyway, because the demo's buyer
agent is not built yet and any reconciliation written before it exists would be
tested against exactly this net-zero case.

### F0.7d.7 — `x-402-payer` exists, and this is its real shape

**Confidence: measured. Verdict: pass** — and it settles an inference that has
been open since the discovery reports.

`research/x402-cli-example.md` Q2 found no server code anywhere and marked the
header *"[INFERRED as plausible but unverifiable from these sources]"*. F0.7.5
left it unmeasured because no payment to our handler had ever settled. With the
endpoint working, a handler that echoes its request headers answers it.

**The full header set a paid handler receives** (12, via four independent access
methods that all agree):

```
accept                          */*
access-control-expose-headers   PAYMENT-RESPONSE,X-PAYMENT-RESPONSE
content-length                  0
host                            x402.bankr.bot
user-agent                      Bun/1.3.14
x-402-payer                     0x93faecde3c88a713e1edddf417c02c326889a3da
x-amzn-trace-id                 Root=1-6aad8052-4c4cb2245d6d44f9357b4941
x-forwarded-for                 44.232.70.184
x-forwarded-port                443
x-forwarded-proto               https
x-original-method               GET
x-original-path                 /0x93fa…a3da/roundtrip
```

**`x-402-payer` is a lowercase `0x`-prefixed 42-character EVM address** — the
payer's wallet, and nothing else. No scheme, no amount, no nonce, no signature.

**The header the handler does *not* get is the important one.**
`req.headers.get("x-payment")` returns **null**: the raw `X-PAYMENT` payload,
which carries the signed EIP-3009 authorization, is consumed by the platform and
not passed through. So the handler **cannot independently verify** that a payment
occurred or that the address is genuine — `x-402-payer` is a **platform
assertion**, trusted exactly as far as Bankr is trusted.

**For unit 7.3 this means two sources of buyer identity, not one, and they differ
in kind:**

| Source | Available | Trust |
|---|---|---|
| `x-402-payer` header | inside the request, immediately | platform-asserted; not verifiable by us |
| `PaymentSettled.payer` (F0.7b.6) | after settlement, on chain | cryptographically settled |

Binding a purchase to a buyer is 7.3's design and not this probe's. What is
recorded here is that the fast source is not the authoritative one, and the
authoritative one arrives late (F0.7b.4).

**A false negative we nearly recorded.** The first attempt at this returned *zero
headers* and would have supported "the header does not exist". It was our own
fault — a regex in the probe matched the CLI's schema line instead of the
response body — not a fact about the platform. It was caught by re-testing with
four access methods plus a description of the `Request` object, on the grounds
that zero headers on a real HTTP request is implausible enough to suspect the
instrument first. **Absence measured through one accessor is not absence.**

Also measured incidentally: the handler runtime is **Bun 1.3.14** behind an AWS
load balancer, consistent with the Lambda-style `REPORT` lines in F0.7d.5.

### F0.7d.8 — Cost of this unit: nothing

**Confidence: measured.**

Three payments of $0.001 were made — one to prove the fix, two to settle the
header question. USDC before the first and after the last: **107,346 base units,
unchanged**. Every payment was self-paid, so the money left and returned in the
same transaction (F0.7d.6), `feeBps` was 0 on all of them, and gas was paid by
the facilitator. **Net spend: $0.00.**

The endpoint is left deployed at version 5, restored to the no-work handler that
the timings in F0.7d.5 were taken against, so what is deployed matches what this
file describes and what the repository contains.

### What 0.7d changes

| Change | Where |
|---|---|
| 0.7's 500 was our handler's return shape; config and self-payment are exonerated | 7.2 |
| Return a `Response`; the quick-start's "plain objects are auto-wrapped" is wrong here | 7.2 |
| Cold start ~513 ms; ~1.5 s platform-side for a no-work handler; ~4.6 s end to end | 1.4, 7.x |
| `GET /x402/endpoints/logs/{service}` exists and is undocumented — the only view of handler errors | 7.x, 8.x |
| `x-402-payer` is a bare payer address, platform-asserted, not verifiable by the handler | 7.3 |
| `X-PAYMENT` is not forwarded to handlers | 7.3 |
| First `PaymentSettled` with the fund as `owner` — revenue evidence exists in practice | 6.x, 7.4 |

### Method limitations

- **Three changes were made to the handler at once** for the fix (`async`, the
  return type, `Response.json`). The runtime error names the return value, but
  which alone would have sufficed is untested; each variant costs a paid call.
- All three payments were self-paid. **No third party has ever paid this
  endpoint**, so nothing here tests a real buyer's path, and the net-zero
  balance in F0.7d.6 is an artefact of that.
- Timings are single observations. The two cold starts agree within 7 ms, which
  is reassuring and is still n=2.
- `x-402-payer` was observed for one payer on one request. Its shape for a
  contract wallet, or a Solana payer, is unknown.

---

## 0.8 — Asset identity: how the fund knows a token is the real one

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.identity` ·
**Captures:** `probes/out/identity.json`, `probes/out/registry_snapshot.json`

### F0.8.1 — The issuer registry: what it is, and what it does not give us

**Confidence: measured.**

`GET https://api.robinhood.com/rhj/assets`, documented at
`https://docs.robinhood.com/chain/stock-tokens/` as the way to query assets.

| Property | Measured |
|---|---|
| Authentication | **none required**; an `X-API-Key`, valid or invalid, changes nothing (200 either way — the header is ignored) |
| Rate limiting | none observed in a burst of 10; no `x-ratelimit-*`, no `Retry-After` |
| Size / count | 154,149 bytes, **194 assets** |
| **Version field** | **none** |
| **`ETag` / `Last-Modified`** | **neither** |
| Response headers | `content-type: application/json`, `date`, and an empty `grpc-message` |

Every record carries all eleven fields, and the invariants are clean:

```
status              194/194 ASSET_STATUS_ACTIVE
deployments/asset   194/194 exactly one
chainId             194/194 = 4663
tokenDecimals       194/194 = 18
isin                194/194 present, 194 distinct
contractAddress     194 distinct, mixed-case (EIP-55), so compare case-insensitively
tokenSymbol         194 distinct — unique within the registry
```

Each record gives `id`, `tokenSymbol`, `tokenName`, `deployments[{contractAddress,
chainId, networkName}]`, `currentMultiplier`, `pendingMultiplier`, `status`,
`logoUrl`, `tradingCapabilities`, `tokenDecimals`, `isin`.

**Coverage is complete against the feed set.** All 35 Chainlink equity feeds
resolve to registry assets. The apparent gap — `RHDELL` — is a naming artefact in
the *feed directory*, not a missing asset: the directory writes that row's
`docs.baseAsset` as `RHDELL` and omits it entirely for SGOV and USAR, while the
registry carries DELL, SGOV and USAR normally. **Never join the two sources on
ticker.**

**What the registry does not supply, and it matters for invariant 8.**
`planning/PLAN.md` §2 invariant 8 wants a **versioned** allowlist with recorded
provenance. The endpoint offers no version, no `ETag` and no `Last-Modified`, so
there is nothing to pin to and no way to ask "has this changed since?" without
refetching and diffing.

**So the snapshot has to carry its own version.** Recorded with this one:

```
url        https://api.robinhood.com/rhj/assets
fetched_at 2026-09-18T18:24:30.262548+00:00
bytes      154149
sha256     442718b5843e448e…
assets     194
```

Unit 1.2 must treat **the content hash as the version**, pin a snapshot rather
than query live, and diff on refresh. A live lookup at cycle time would make the
universe depend on an unversioned third-party endpoint with no integrity signal.

**Untestable today, and stated rather than assumed:** every asset is
`ACTIVE` with an empty `pendingMultiplier` and exactly one deployment, so we have
**no example** of how a delisted asset, a pending corporate action, or a
multi-chain asset is represented. 1.2 must not assume `status == ACTIVE` is the
only value, and must not assume `deployments` has length 1.

### F0.8.2 — Every check against every candidate

**Confidence: measured.** Nine candidates, including six the checks are supposed
to **admit** — a check only ever pointed at things it obviously catches proves
nothing.

| Candidate | registry | beacon | feed | `uiMultiplier` | name marker | should be |
|---|---|---|---|---|---|---|
| GME `0x1b0e…153e` (issuer) | ✓ | ✓ | ✓ | ✓ | ✓ | admit |
| GME fake `0x7e86…8123` "GameStop" | ✗ | ✗ | **✓** | ✗ | ✗ | reject |
| GME fake `0xef67…d5f6` "Greatest Meme Ever" | ✗ | ✗ | **✓** | ✗ | ✗ | reject |
| AAPL `0xaf3d…93f9` | ✓ | ✓ | ✓ | ✓ | ✓ | admit |
| NVDA `0xd060…9eec` | ✓ | ✓ | ✓ | ✓ | ✓ | admit |
| TSLA `0x322f…3b2d` | ✓ | ✓ | ✓ | ✓ | ✓ | admit |
| ORCL `0xb099…ee03` | ✓ | ✓ | ✓ | ✓ | ✓ | admit |
| CRM `0xd95b…6D44` (genuine, no feed) | ✓ | ✓ | **✗** | ✓ | ✓ | admit, unmarkable |
| USDG `0x5fc5…d168` (genuine, not a stock) | ✗ | ✗ | ✗ | ✗ | ✗ | reject as a stock |

**Beacon resolution is confirmed on mainnet**, not carried over from testnet. The
real GME resolves through EIP-1967 to beacon `0xe10b6f6b…1b00` →
implementation `0xb35490d6…5ae2`; both fakes have **no beacon slot set at all**
(their code is 9,662 and 6,498 bytes of ordinary ERC-20, against the genuine
token's 568-byte proxy).

### F0.8.3 — Feed presence is worthless as an identity check. It admits both fakes.

**Confidence: measured. Verdict: fail.**

This is the finding the unit exists to produce, and it is the one that would have
been missed by testing only against things a check obviously catches.

Feed presence **admitted both counterfeits**. The reason is structural: a
Chainlink feed exists for the *ticker* `GME`, and a counterfeit picks its own
ticker. The check asks "does a feed exist for the symbol this contract claims",
which a forger satisfies by typing three characters. **It carries zero identity
weight and must never appear in an admissibility rule.**

It remains required for a *different* question. The 0.4 checkpoint decided feed
presence is a **membership condition for markability** — no feed, no independent
mark, so the asset is not held. CRM shows the two questions are genuinely
separate: genuine, in the registry, behind the issuer's beacon, and correctly
**not markable**. Identity and markability must be two rules, evaluated
independently, and 1.2 should not collapse them.

### F0.8.4 — Registry and beacon never disagree, on anything we can test

**Confidence: measured, exhaustively over both available populations.**

| Population | Both admit | Registry only | Beacon only | Neither |
|---|---|---|---|---|
| All **194** registry assets | **194** | 0 | 0 | 0 |
| All **187** `• Robinhood Token`-marked addresses from the untrusted CoinGecko list | **187** | 0 | 0 | 0 |

Every registry asset resolves to the issuer's beacon; every marked discovery-list
address is in the registry *and* behind the beacon. **Zero disagreements in 381
addresses.** The only counterexamples available anywhere — the two GME fakes —
are rejected by both.

**So no mainnet evidence separates these two checks, and we say that rather than
implying the second is pulling weight.** They agree on every address we can put
to them. The mainnet `• Robinhood Token` marker also happens to be perfectly
accurate today — all 187 carrying it are genuine — which is exactly the
comfortable position that made F0.3.6 trust it before testnet found 140
forgeries.

### F0.8.5 — The minimum sufficient combination is the registry alone

**Confidence: measured for sufficiency on the available counterexamples;
inferred for the trust argument.**

**Registry membership, keyed by `(chain_id, address)`, is necessary and
sufficient.** It admitted every genuine asset and rejected every counterfeit, and
it is the only source that supplies what an allowlist actually needs — the
address-to-asset mapping itself, plus ISIN, status, decimals and multiplier. The
other three checks cannot name an asset; they can only opine on one.

What each of the others contributes, stated plainly:

| Check | Catches anything the registry misses? | Keep? |
|---|---|---|
| **EIP-1967 beacon** | **No** — 0 of 381 | **Judgement call, not a discrimination one** (below) |
| **Feed presence** | No, and it *admits counterfeits* (F0.8.3) | **Not for identity.** Required for markability, a separate rule |
| **`uiMultiplier()`** | No — rejected exactly what the beacon rejected, and testnet showed five tokens answering it, so it is a function anyone can implement | **Drop** |
| **Name marker** | No — and testnet measured 140 forgeries carrying it (F0.T.4) | **Drop** |

**On the beacon, the honest position.** It caught nothing. The argument for
keeping it is not discrimination but **an independent trust root**: the registry
is plain HTTPS with no auth, no signature, no version and no `ETag`, so its
authority rests entirely on TLS to `api.robinhood.com`, while the beacon rests on
the chain and the beacon contract's owner. They fail in different ways — a
hijacked or stale registry response does not move the beacon, and a compromised
beacon upgrade does not change the registry. It is also the *only* check that
speaks to the contract's state **now**, where a pinned snapshot is by
construction historical.

That is a real argument, and it is still an argument for **insurance, not for
detection**. Whether the fund pays for that insurance is a design decision for
1.2, and this probe's recommendation is: **one rule, registry membership, plus
the beacon as a cheap assertion that fails the cycle loudly if it ever
disagrees** — because the day it disagrees is the day one of the two is
compromised, and that is worth knowing. Both `uiMultiplier()` and the name marker
should be deleted from the vocabulary rather than kept for reassurance; they cost
code and would hide which check is load-bearing.

**Stated limitation:** sufficiency is established against **two** counterfeits and
381 genuine-or-absent addresses. A counterfeit that got itself *into* the registry
would defeat every check here, and nothing in this probe bounds that risk — it is
the issuer's control, not ours.

### What 0.8 changes

| Change | Where |
|---|---|
| Identity = registry membership on `(chain_id, address)`; that is the rule | 1.2 |
| The snapshot carries its own version (sha256 + fetched_at); pin it, never query live | 1.2; `config/universe.json` |
| Feed presence is markability, not identity — two independent rules | 1.2, 3.4 |
| `uiMultiplier()` and the name marker are dropped as identity signals | 1.2; retires part of F0.3.6 and F0.4.6 |
| Beacon kept as an independent-trust-root assertion, not a filter | 1.2 |
| Never join the registry to the feed directory on ticker | 1.2, 1.4 |

### Method limitations

- **Two counterfeits.** Both are crude — ordinary ERC-20s with no beacon slot.
  Nothing here tests a forgery that clones the proxy and points at its own
  beacon, which is what a serious attacker would deploy, and which only the
  registry would catch.
- Registry and beacon agree on all 381 testable addresses, so **their relative
  strength is untested**. The preference for the registry rests on what it
  supplies, not on a case where it won.
- One fetch, one day, one chain. The registry carries no version, so we cannot
  tell whether it changed yesterday or has been static for a month.
- Every asset is `ACTIVE` with one deployment; delisting and multi-chain
  representation are unobserved.
- The 4663 explorer is behind Cloudflare, so there is no enumeration of all
  tokens on the chain — "no other token is behind the issuer's beacon" is **not**
  established, only that none of the 381 checked is anomalous.

---

## 0.9 — Analyst cost

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.llm_cost --confirm` ·
**Captures:** `probes/out/llm_cost.json`

> **Every number below is a FLOOR, not a forecast, and this caveat is the
> finding's first line rather than its last.** `planning/PHASE-0-1.md` relocated
> this unit to 1.7 because snapshot bytes dominate the token count and no
> snapshot exists until 1.6. The prompt here carries **6** hand-assembled assets;
> the admissible universe is **35** markable ones (0.4 decision) out of 194.
> F0.9.4 extrapolates the gap. Quoting the cost-per-cycle below as "the analyst
> cost" would mislead. **The real number is §1.7:** $0.454 an analyst call and
> $1.87 a cycle against a real snapshot, 28 times this floor.

### F0.9.1 — One analyst call: 1,793 in, 982 out, $0.013406, 58 seconds

**Confidence: measured.**

`claude-sonnet-5`, one call, temperature 0, `max_tokens` 2000, a rough
price-trend brief over six assets built from real 0.4 values.

| | |
|---|---|
| Input tokens | **1,793** |
| Output tokens | **982** |
| Total tokens | 2,775 |
| **Latency** | **58,070 ms** |
| Cost | **$0.013406** |
| Cached tokens | 0 |

Cost checks out against the published rate exactly: 1,793 × $2/M + 982 × $10/M =
$0.013406, and the credit balance moved by precisely that — `2.813382 →
2.799976`. **The published price list, the response's `usage` block and the
credit balance agree to the last digit.**

**58 seconds is the number that should worry a cycle designer, not the cost.**
`config/models.json` leaves `worker_deadline_seconds` and
`transport_timeout_seconds` null. A single analyst on six assets took nearly a
minute; four in parallel plus a risk call that must read all four reports will
not fit inside a naive 30-second budget, and it dwarfs the ~4.6 s x402 round trip
(F0.7b.3), which is why the handler must serve a cached record rather than run a
cycle.

**The model is provisional.** `config/models.json` has `analyst_model: null`,
pinned at 2.4 and informed by this unit, so `claude-sonnet-5` is a defensible
mid-tier pick and not a decision. F0.9.5 prices the same token counts across the
catalogue so nothing here depends on it.

### F0.9.2 — `/v1/usage` was observed going *backwards*

**Confidence: measured. Verdict: fail**, against using it as a per-call check.

Two calls were made (see F0.9.3). `/v1/usage` was read repeatedly around them:

| When | `totalRequests` reported |
|---|---|
| shortly after call 1 | **0** |
| ~a minute later | **1** |
| immediately before call 2 | **0** ← *went backwards* |
| ~8 s after call 2 | **2** |

The aggregate is **eventually consistent and not monotonic as observed**. It
reported a call, then stopped reporting it, then reported both. The final state
is correct — 2 requests, 3,586 input, 1,846 output, **$0.025632**, exactly the sum
of the two calls — so nothing is lost; it simply cannot be trusted at a point in
time.

**Mechanism, inferred not measured:** the gateway documentation states that "each
gateway instance caches independently" when describing budget enforcement, which
would produce exactly this if reads land on instances with different views.

**Consequence for 6.3, and it sharpens F0.6.4.** A before/after delta around one
call is **not** a sound reconciliation technique: the "before" read can already
be stale and the delta can capture calls that are not the ones being measured —
here it captured two calls for one. Cost reconciliation must compare a *settled*
window well after the fact, never a delta taken across an individual call. The
credit balance, by contrast, moved by the exact amount both times and did not go
backwards.

### F0.9.3 — The first call was billed and measured nothing, and that is a probe defect worth recording

**Confidence: measured.**

The first attempt returned `HTTP None` after **20,114 ms** — `probes/_capture.py`
carries a 20-second default timeout, which is right for the read probes it was
written for and far too short for inference. The call **completed server-side and
was billed $0.012226**; only the client gave up. It is visible in the aggregate
as 1,793 input / 864 output tokens.

**Two things follow.**

A timeout that fires client-side does **not** cancel the work or the charge, so a
transport timeout in the analyst path costs money and returns nothing. Unit 1.3's
HTTP client and 2.4's `worker_deadline_seconds` must be set from the 58-second
measurement above, not from a default, and a timed-out analyst call must be
booked as a cost with no report rather than treated as a non-event.

**The two calls also differ.** Same prompt, same model, `temperature: 0` — and
output came back **864 tokens** the first time and **982** the second, a 14%
spread. That is direct corroboration of `tracker/LESSONS.md`
(2026-09-17, *invariant 6 reworded*): seeding and zero temperature do not produce
comparable model runs, and deterministic replay has to come from **recorded
outputs**. Cost per call is therefore a distribution, not a constant, and a
budget built on one observation should carry headroom.

**Total spend for this unit: $0.025632**, two calls, balance $2.825608 →
$2.799976.

### F0.9.4 — Multiplied out, with the extrapolation kept separate from the measurement

**Confidence: measured for the 6-asset column; the 35-asset column is
arithmetic, not a measurement.**

Roster is four analysts plus one risk call (`config/analysts.json`;
`planning/PHASE-0-1.md` 1.7), daily cadence.

| | 6 assets (**measured**) | 35 assets (**extrapolated**) |
|---|---|---|
| Input tokens / call | 1,793 | ~6,400 |
| Cost / analyst call | **$0.013406** | ~$0.023 |
| Cost / cycle (5 calls) | **$0.067030** | ~$0.117 |
| Cost / day | **$0.067030** | ~$0.117 |
| Cost / 30 days | **$2.011** | ~$3.51 |

The extrapolation splits the measured prompt into ~847 fixed tokens and ~158
tokens per asset (2.02 chars/token observed), then scales to 35. **It assumes
output length does not grow with asset count, which it certainly will**, so even
the right-hand column is a floor. A real snapshot also carries provenance, quote
data and a content hash per asset that this hand-assembled block does not.

**Against the $0.05 x402 price:** one cycle costs **1.34 decision records** at the
measured floor, or **~2.3** at the 35-asset extrapolation. The endpoint must sell
between one and three records a day merely to cover inference — before the $3.00
credit purchase's 5.8% funding overhead (F0.7b.10), before gas, and before
anything is earned. **The $0.05 price is not confirmed by this unit**; it is shown
to need a buyer volume the project has never observed, since no third party has
ever paid our endpoint (F0.7d.8). Whether the price moves is a decision for the
0.7 checkpoint and not this probe's to take.

### F0.9.5 — Model choice swings the budget 139×, and it dominates every other lever

**Confidence: measured (the token counts) × published rates.**

Same 1,793 in / 982 out priced across the catalogue:

| Model | $/call | $/cycle (5) | $/30 days |
|---|---|---|---|
| `gpt-5-nano` | 0.000482 | 0.002412 | **0.07** |
| `glm-5.3-flash` | 0.000760 | 0.003800 | 0.11 |
| `gemini-3-flash` | 0.003842 | 0.019213 | 0.58 |
| `claude-haiku-4.5` | 0.006703 | 0.033515 | 1.01 |
| **`claude-sonnet-5`** (measured) | **0.013406** | **0.067030** | **2.01** |
| `claude-opus-5` | 0.033515 | 0.167575 | 5.03 |
| `claude-fable-5.1` | 0.067030 | 0.335150 | **10.05** |

The gateway lists 68 text models spanning $0.05–$10 per million input tokens. **A
monthly budget of $0.07 or $10.05 is the same fund with the same prompt**, so
unit 2.4's model pin is worth more than any prompt optimisation, and the
`analyst_model` null in `config/models.json` is the single most expensive
unresolved value in the config tree.

### F0.9.6 — The analyst abstained on all six, correctly, and that is a snapshot-design signal

**Confidence: measured. Not a capability claim.**

Output quality was explicitly not the subject, and this is recorded because of
what it says about the *snapshot*, not the model. Every one of the six assets came
back `NO_CALL`, with the reasoning that a single block-pinned reading carries no
history:

> *"Snapshot provides only a single point-in-time feed_usd/quote_usd/
> corroborator_usd reading with no historical price series, so no trend or
> 'recent price action' can be established."*

**A price-trend analyst cannot function on a single-block snapshot**, which is
what `planning/PLAN.md` §2 invariant 2 specifies. Either the snapshot carries a
time series, or the roster's `price-trend` scope has nothing to answer and
checkpoint 2.1 should replace it. That is a real input to 1.6 and 2.1 and it cost
nothing to learn — but it is one observation from one model on one prompt, and it
is evidence about the prompt we wrote, not proof about the design.

It also confirms `NO_CALL` is reachable in practice rather than theoretically
(invariant 6), which the aggregator must handle as a total function.

### What 0.9 changes

| Change | Where |
|---|---|
| Analyst cost floor $0.0134/call, $0.067/cycle, $2.01/30d at Sonnet 5 | 6.3, 7.2; `config/thresholds.json` |
| Latency 58 s per call sets `worker_deadline_seconds`, not a default | 2.4; `config/models.json` |
| `/v1/usage` is non-monotonic; reconcile settled windows, never per-call deltas | 6.3, 2.5 |
| A client timeout still bills; book it as cost with no report | 1.3, 2.4, 6.3 |
| Model pin is the dominant cost lever — 139× across the catalogue | 2.4; `config/models.json` |
| $0.05 x402 price needs 1.3–2.3 records/day just to cover inference | 0.7 checkpoint, 7.2 |
| A single-block snapshot gives a trend analyst nothing | 1.6, 2.1; `config/analysts.json` |

### Method limitations

- **Two calls, one model, one prompt, one day.** The 14% output spread between
  two identical calls is the only variance evidence there is.
- The 35-asset column is arithmetic on a per-asset token estimate, not a
  measurement, and assumes output does not grow with input.
- The prompt is a rough brief, not the brief; checkpoint 2.1 settles that, and
  the risk call — which reads all four reports plus the sized plan — is priced
  here as if it were an analyst call, which it is not.
- No retries, no cache reads (`cached_tokens: 0` both calls). Prompt caching
  would change the economics materially and is untested.
- The response carried an undocumented `buyer_cost_micro: 6033` — $0.006033
  against the $0.013406 charged. **Unresolved:** it may be the gateway's own
  wholesale cost, implying roughly a 2.2× markup, but the field is undocumented
  and nothing was measured that confirms the interpretation.

---

## 0.7e — Who can pay us: the x402 client gap, measured

**Date:** 2026-09-18 · **Method:** `node probes/x402_clients/gap.mjs`,
`adapter.mjs` and `v2.mjs` (one free unpaid GET, then offline), and
`node probes/x402_clients/pay.mjs --confirm` (one payment) · **Captures:**
`probes/out/x402_clients.json`, `probes/out/x402_logs_roundtrip.json` ·
**Packages:** pinned exactly in `probes/x402_clients/package-lock.json`, installed
unmodified

Question: F0.7.3 measured that the published `x402` / `x402-fetch` 1.2.0 cannot
parse our challenge. Is the only client that can pay us Bankr's own? This section
does not re-derive F0.7.3, F0.7b or F0.7d; it tests clients against them.

The offline runs replay the live 402 byte for byte — body and headers — to the
unmodified client, answer its unpaid request, and **refuse** any request carrying
a payment header. That drives a client exactly to the point of signing and no
further. Each run signs with a key generated for that process, never printed and
never funded.

### The answer

| Buyer | Can pay our endpoint today? | Confidence |
|---|---|---|
| **`@x402/fetch` 2.26.0 + `@x402/evm`**, unmodified — Coinbase's current v2 client | **Yes. Paid once, settled on chain.** | **measured** (F0.7e.5) — with a Bankr-custodied signer (F0.7e.6) |
| The same client with a key the buyer holds, and no Bankr account | Yes | **inferred** — the server sees only the library's payload and an EOA signature |
| Bankr CLI / `POST /wallet/x402-pay` | Yes, **for Bankr account holders only** | measured (F0.7b.1, F0.7d.4); mechanism F0.7e.4 |
| **`x402-fetch` / `x402` 1.2.0**, unmodified — the client **Bankr's own docs recommend** | **No.** Throws before signing. | **measured** (F0.7e.1) |
| `x402-fetch` 1.2.0 plus an adapter the buyer installs | Reaches signing with a valid signature; the server's answer is **unresolved** | measured to signing (F0.7e.3) |
| Other v2-line clients (`@x402/axios`, PyPI `x402` 2.23.0) | Probably | **inferred** from the shared core and version line; not tested |

**The claim this supports:** *payable by any x402 v2 client, and by Bankr users.*
It does **not** support *payable by any x402 client*: the v1 packages cannot pay
us unmodified, and Bankr's own documentation points buyers at them. The CLI
working answers only the Bankr-user case. What answers the non-Bankr buyer is
F0.7e.5, and its last step from measured to inferred is F0.7e.6.

### F0.7e.1 — The gap, field by field: one client-side blocker, not two

**Confidence: measured. Verdict: fail** for `x402-fetch@1.2.0` unmodified, and a
partial correction of F0.7.3.

The live 402 carries the same JSON three times: the body, a base64
`payment-required` header, and a base64 `x-payment-required` header. Checked
with `x402@1.2.0`'s own zod schemas rather than read off its source:

| Field of `accepts[0]` | Present | `PaymentRequirementsSchema` |
|---|---|---|
| `scheme` | yes | ok |
| **`network`** | yes | **fails** — `eip155:8453` is not in the 17-name enum |
| `maxAmountRequired` | yes | ok |
| `resource`, `description`, `mimeType` | yes | ok (`mimeType: ""` is a valid string) |
| `outputSchema` | no | ok (optional) |
| `payTo`, `maxTimeoutSeconds`, `asset`, `extra` | yes | ok |
| `amount` | yes | unknown to v1; zod strips it |

At the top level, `x402Version: 2`, `error: "Payment Required"` (not one of
`ErrorReasons`) and `accepts` all fail `x402ResponseSchema`, and `facilitator` is
unknown to it. **But `x402-fetch` never applies that schema.** It destructures
`{ x402Version, accepts }` from the body (`x402-fetch/dist/cjs/index.js:39`) and
parses only the `accepts` entries. Driving the unmodified client, one field
changed at a time:

| Replay | Result |
|---|---|
| unmodified | throws before signing — `network: Invalid enum value … received 'eip155:8453'` |
| `network` → `"base"` only | **reaches signing**; sends `X-PAYMENT` `{x402Version: 2, network: "base", …}` |
| `x402Version` → `1` only | throws before signing — the same network error |

**So the network identifier is the only thing that stops the v1 client.** The
version is carried straight into its payment header rather than rejected. F0.7.3's
*"throws before selection or signing — for two independent reasons"* is one
reason on the client side; whether version 2 in a v1-shaped header matters to the
*server* is F0.7e.3's open question.

**An instrument error, caught before it was recorded.** The first run reported the
network-only variant as *"Invalid evm wallet client provided"*. `createSigner` is
async in `x402@1.2.0` and was passed unawaited, and a Promise fails the library's
wallet check with a message that reads like a protocol rejection. Once it was
awaited, the variant reached signing. This is the same class of error as F0.7d.7's
regex, where the probe was at fault rather than the platform.

### F0.7e.2 — The signature does not cover the fields an adapter would rewrite

**Confidence: measured** (source read, then confirmed by recovering signatures).
**Verdict: pass** — an adapter is not ruled out by the cryptography.

`x402@1.2.0` signs EIP-3009 `TransferWithAuthorization`
(`x402/dist/cjs/client/index.js:453`):

```
domain   { name: extra.name, version: extra.version,
           chainId: getNetworkId(network), verifyingContract: asset }
message  { from, to: payTo, value: maxAmountRequired,
           validAfter, validBefore, nonce }
```

`x402Version` and the network *string* are envelope fields outside the
signature. The network enters only as `chainId`, and `"base"` resolves to 8453,
the same chain `eip155:8453` names. `@x402/evm@2.26.0` signs the **identical**
typed data (`chunk-6RBEXVZ5.mjs:26`) — same domain, same message. The one
difference is `validAfter`: v1 uses now − 600 s and v2 uses `"0"`, and both are
valid EIP-3009 values.

Confirmed by recovery: each adapter signature in F0.7e.3 recovers to its signer
under the live USDC domain on chain 8453, and its `to`/`value` equal the live
`payTo`/`amount`. Rewriting did not change what was signed.

### F0.7e.3 — A thin adapter gets the v1 client to signing; whether Bankr accepts the result is unresolved

**Confidence: measured to the signing stage. Verdict: unresolved** at the server.

Two depths, both wrapping the fetch *underneath* the unmodified `x402-fetch`
(`probes/x402_clients/adapter.mjs`):

| Depth | What it does | Sends | Result |
|---|---|---|---|
| **inbound** (~20 lines) | rewrites the 402: `eip155:<id>` to the v1 name via `x402`'s own `ChainIdToNetwork`, `x402Version` to 1, `maxAmountRequired` from `amount` if absent | `X-PAYMENT` `{x402Version: 1, scheme, network: "base", payload}` | reaches signing, signature valid |
| **envelope** | also re-wraps that payload as v2 | `PAYMENT-SIGNATURE` `{x402Version: 2, payload, accepted}` | reaches signing, signature valid |

**Neither was sent.** Whether Bankr's server accepts a v1 `X-PAYMENT` is not
known, and it cannot be read for free: the facilitator the challenge advertises
has no `GET /supported`, and both `/facilitator/supported` and `/facilitator/`
return 404. So the (version, network) kinds it verifies are not published. The
one authorised payment went to the v2 client (F0.7e.5), on purpose.

**The envelope depth is not really an adapter.** Its output has the same three
keys as the v2 client's own payload (F0.7e.5), so at that depth it reimplements
`@x402/fetch`. A buyer willing to install it should install `@x402/fetch`
instead.

**The buyer bears it; we cannot absorb it.** The challenge is emitted by Bankr's
platform in front of our handler (F0.7d.1). Our `bankr.x402.json` already says
`"network": "base"`, and the platform emits `eip155:8453` regardless. The
documented config offers `network` and nothing about protocol version or
identifier format (`docs.bankr.bot/docs/x402-cloud/config-file.md`, read
2026-09-18). **Documented, not tested**, and changing the endpoint config is
outside this unit's authorisation anyway.

### F0.7e.4 — Bankr's CLI does not implement x402: Bankr pays on your behalf, server-side

**Confidence: measured (source read). Verdict: pass, as a constraint.**

`@bankr/cli` 0.3.37 depends on `@inquirer/prompts`, `chalk`, `commander`, `open`,
`ora` and `viem`, and on **no x402 package**. `x402CallCommand`
(`dist/commands/x402.js:978`) optionally probes the 402 for the price, then
POSTs `{url, method, body, maxPaymentUsd}` to **`/wallet/x402-pay`** with the
CLI's API key (`:1167`). Bankr's server builds and signs the payment from the
custodial wallet. The CLI is a thin client of a Bankr payment service, not an
x402 client.

**As a library it offers nothing a non-Bankr buyer can use.** An `x402Pay`
function exists in `dist/lib/api.js:350` but is not exported from the package
entry (`dist/index.js` re-exports config helpers and agent-prompt calls only). The
usable surface is the HTTP endpoint, which appears nowhere in the pages read —
the docs index (`llms.txt`), the Wallet API overview, or the x402 examples. Its
request shape is known only from the CLI source. **Either way it needs a Bankr
account and a Bankr-held wallet: this is the "agents already inside Bankr" case.**

**Bankr's own documentation recommends the client that fails.**
`docs.bankr.bot/docs/x402-cloud/examples.md` (read 2026-09-18), under *"TypeScript
— x402-fetch"*: `bun add x402-fetch viem`, then `wrapFetchWithPayment(fetch,
wallet, …)`. That is exactly the v1 client F0.7e.1 measured throwing on our
challenge. The same page's cURL sample shows `"network": "base"` where the live
challenge says `eip155:8453`, so the docs describe a challenge the platform no
longer emits. **Documented against measured, and the measured one is what buyers
hit.** The same page's "Manual 402 Flow" uses `PAYMENT-SIGNATURE`, the v2
header.

**Inferred, circumstantial.** The request Bankr's payer sent our handler (F0.7d.7)
carried `access-control-expose-headers: PAYMENT-RESPONSE,X-PAYMENT-RESPONSE`.
That is the exact string `@x402/fetch` 2.x sets on its paid request
(`dist/esm/index.mjs:60`). It is consistent with Bankr's server-side payer being
built on the v2 client line, and it proves nothing.

### F0.7e.5 — The standard v2 client paid us, and it settled

**Confidence: measured. Verdict: pass — and it refutes F0.7.3's headline.**

**The v2 client line exists and is published.** `@x402/core`, `@x402/fetch` and
`@x402/evm` are at **2.26.0**, last published 2026-09-15. `@x402/fetch` first
appeared as 0.0.1 on **2025-12-11**, 28 published versions in all. The maintainers
are the same two Coinbase accounts that publish `x402` and `x402-fetch`, and the
repository is the same `x402-foundation/x402`. PyPI's `x402` is at 2.23.0. F0.7.3
looked at `x402`, `x402-fetch` and `@coinbase/x402` — the right names for v1 and
the wrong names for v2 — and recorded *"a standard published x402 client cannot
pay this endpoint"*. That is the same over-reading as F0.2.1 and F0.6.1: a
negative about the packages examined, generalised into a negative about the
ecosystem.

**Offline** (`v2.mjs`). The client is unmodified and configured exactly as its
README's Quick Start shows a buyer (`ExactEvmScheme` on `eip155:8453`). It reads
the `PAYMENT-REQUIRED` header (`@x402/core chunk-UF6R7D6H.mjs:2156`), selects
`eip155:8453` natively, and signs. It sends `PAYMENT-SIGNATURE`
`{x402Version: 2, payload, accepted}`, where `accepted` is our live requirement
verbatim. There is no top-level `resource`, because our challenge has none:
Bankr puts `resource` inside `accepts[]`, which is where v1 puts it.

**Paid** (`pay.mjs --confirm`), once:

```
unpaid GET → 402                              51 ms
signTypedData via /wallet/sign               841 ms
paid GET (PAYMENT-SIGNATURE) → 200         6,165 ms   {"ok":true,"probe":"0.7","work":"none"}
end to end                                 7,062 ms
paid requests sent                             1
```

**Verified from the chain, not from the 200:**

```
PaymentSettled   tx 0xa8c461f23b0693cf05bc6825aec0dc11798f31db3c1e31911e5186a75faf22cc
                 Base block 51,490,128
                 payer = owner = 0x93fa…a3da   total 1000   ownerAmount 1000
                 bankrFee 0   feeBps 0
AuthorizationUsed (USDC, same tx)
                 authorizer 0x93fa…a3da
                 nonce 0xd6855b8c858062277d8a5ee6a335258ec7e9c907e4be72ea61c88cf30f5da272
                 — the nonce this client signed
tx sender        0x4a15fc613c713fc52e907a77071ec2d0a392a584 (the facilitator; the payer paid no gas)
```

The `AuthorizationUsed` nonce ties the settlement to *this* client's
authorization, not just to some payment by our wallet. The endpoint's own log
agrees: `2026-09-18T22:13:21.695Z status=200 settled=true durationMs=1521`, with
a cold `Init Duration` of 496.31 ms and 173.03 ms in the handler, consistent with
F0.7d.5. USDC was 107,346 before and after, since the payment was self-paid
(F0.7d.6).

**What a non-Bankr buyer needs, as measured here:** `@x402/fetch` and
`@x402/evm`, a signer that can do `signTypedData`, and USDC on Base. No ETH,
because the facilitator paid the gas. No Bankr account. Whether that holds when
the key is not Bankr's is F0.7e.6.

**0.7's done-condition** — *"confirm a standard client can pay us"* — is met by a
v2 client, subject to F0.7e.6.

### F0.7e.6 — What this payment does not prove, stated before anyone rounds it up

**Confidence: measured (the gap). Verdict: the non-Bankr buyer is inferred, not measured.**

- **The signer was Bankr's.** The fund has one funded wallet, so the client's
  `signTypedData` was answered by `POST /wallet/sign` through the logged-in CLI.
  Everything the server received — header name, envelope, `accepted`,
  authorization — was built by the published library. The signature is plain
  ECDSA from an **EOA** (`eth_getCode` on Base returns `0x`) and recovers to it
  locally. A buyer holding their own key produces a payload of the same shape,
  and nothing on the path can see where a key is held. **That is an inference,
  and a strong one, not a measurement.** Settling it takes one payment from a
  fresh local key holding ≥ $0.001 USDC on Base, which needs a funding transfer
  this unit was not authorised to make.
- **It was self-paid again.** Payer and owner are the same address, as in every
  payment this endpoint has ever received. F0.7d.4 had already shown that
  self-payment settles; **no third party has ever paid us.**
- Smart-contract-wallet buyers (ERC-1271 / ERC-6492 signatures) are untested.
- Only `@x402/fetch` was run. `@x402/axios` shares `@x402/core` and PyPI `x402`
  2.23.0 is on the v2 version line; both are inferred to work and neither was
  tried.

### F0.7e.7 — A paid response carries no settlement receipt

**Confidence: measured (one response). Verdict: fail, against the buyer getting in-band proof of payment.**

The paid 200 carried neither `PAYMENT-RESPONSE` nor `X-PAYMENT-RESPONSE`. Its
headers were `apigw-requestid`, `connection`, `content-length`, `content-type` and
`date`, nothing else. `@x402/fetch` tolerates the absence silently
(`processPaymentResult` swallows the missing header). **A buyer using a standard
client receives the content and no transaction hash.** The only evidence that
they paid is on chain, which is consistent with settlement arriving after the
response (F0.7b.4). Our own books were already going to read `PaymentSettled`
(F0.7b.6), so nothing changes for us. What changes is what a buyer can show for
their money, and handing them a receipt is 7.3's and 7.4's decision, not this
probe's.

### What 0.7e changes

| Change | Where |
|---|---|
| F0.7.3's headline refuted: a published standard client (v2, `@x402` scope) pays us | 0.7 checkpoint, 7.2, the pitch |
| The honest claim is "any x402 v2 client, and Bankr users" — not "any x402 client" | README, 8.x |
| v1 clients fail on the network enum alone; the version passes through | 7.2 |
| Bankr's docs point buyers at the v1 client that fails; our buyer instructions must name `@x402/fetch` | 7.2, 8.x |
| A thin v1 adapter reaches signing but is the buyer's to install, and its server acceptance is unresolved | — |
| The CLI pays via Bankr's undocumented `/wallet/x402-pay`; it is not a client a non-Bankr buyer can adopt | — |
| No in-band settlement receipt for the buyer | 7.3, 7.4 |

### Method limitations

- **One payment**, self-paid, with a Bankr-custodied signer. The non-Bankr buyer
  is inferred (F0.7e.6).
- The offline runs replay the live 402 byte for byte, so they test each client
  against exactly what the endpoint emitted today. A later change on the platform
  is not covered.
- The adapter's server-side acceptance is unmeasured. The facilitator publishes
  no `/supported`, and the payment was spent on the v2 client.
- The package survey is npm plus the top-level PyPI release, on one day.
  "Published" means published there.
- Timings are single observations, and the paid wire time (6,165 ms) includes
  the platform's cold start.
- **Cost:** $0.001 paid and returned in the same transaction, `feeBps` 0, gas paid
  by the facilitator. **Net spend: $0.00.**

---

## 0.10 — Idempotency and rate limits

**Date:** 2026-09-18 · **Method:** `PYTHONPATH=src python3 -m probes.idempotency --confirm`,
`python3 -m probes.idempotency_evidence` (read-only), `python3 -m probes.ratelimit`
(read-only) · **Captures:** `probes/out/idempotency.json`,
`probes/out/idempotency_evidence.json`, `probes/out/ratelimit.json`

> **This unit spent, once.** It made one ungated swap with `BANKR_KEY_EXEC`:
> 0.00003 ETH (~$0.08) into USDG on 4663, the smallest size that quoted (0.00001
> was refused as "too small to swap"). It was the wallet's first transaction on
> 4663. The ETH was converted, not lost: the wallet now holds 0.078742 USDG. It
> paid no gas (F0.10.3).

### F0.10.1 — The same idempotency key returns the original result and does not broadcast twice

**Confidence: measured. Verdict: pass**, for a repeat sent after the original
completed.

| | Status | Time | Body |
|---|---|---|---|
| Submission 1 | 200 | 5,734 ms | `{"success":true,"hash":"0xb9e4…e2a5","amountSold":0.00003,"amountReceived":0.078742,…}` |
| Submission 2 — identical body, same `idempotencyKey`, sent as soon as 1 returned | 200 | **178 ms** | **byte-identical**, same hash |

**The chain agrees that there was one fill, not two.** The wallet's ETH fell by
exactly one sell (30,000 gwei), and its USDG rose by exactly one
`amountReceivedRaw` (78,742). The EntryPoint reports **one** operation executed
under the UserOperation's own nonce key (F0.10.3). The 178 ms reply is the
stored result, not a fresh quote-and-execute. Bankr's documentation — *"A repeat
POST with the same key returns the original result, never a second broadcast"* —
is now measured for this case.

**Not measured: the in-flight case.** The documented reply to a repeat sent while
the original is still processing is `409`. That is the case `planning/PLAN.md` §4
actually worries about, a retry after a timeout. This run sent the repeat only
after the original had returned, so the 409 path is still **documented**. The
crash drill (4.10) is where it gets exercised.

### F0.10.2 — `BANKR_KEY_EXEC` can transact. F0.5.5 is settled.

**Confidence: measured. Verdict: pass.**

The swap moved the fund wallet's ETH and delivered USDG to it. The UserOperation
that did it names **our wallet as `sender`** and reports `success: true`. This is
the first evidence that the execution key can transact at all. 0.5 could not show
it, because the location gate fired first (F0.5.5), and Phase 5's live leg rested
on it. The evidence is narrow: one sell of $0.08, ETH into USDG, on 4663. The
buy-and-sell round trip that 5.2 requires has not been done.

### F0.10.3 — Bankr runs the swap as a sponsored ERC-4337 UserOperation, and our wallet is now EIP-7702-delegated on 4663

**Confidence: measured** (the transaction and its logs); **inferred** where
noted. **Verdict: pass, as a constraint on 4.x and 5.x.**

```
tx 0xb9e412815dc9bce933100bf23ece1e2b24fedcbcb91a4fa90c49ad36e64ae2a5   block 66,586,209
  type 0x4 (EIP-7702 set-code)
  from 0x8e3435ad7c1183bc0e34f9ec34ea3423182e1c67        a bundler, account nonce 76,800
  to   0x0000000071727de22e5e9d8baf0edac6f37da032        16,035 bytes; selector 0x765e827f
  authorizationList  chainId 4663  delegate 0xd6cedde84be40893d153be9d467cd6ad37875b28  nonce 0
UserOperationEvent  sender 0x93fa…a3da (us)   paymaster 0x0   success true
                    actualGasCost 0 wei   actualGasUsed 353,353
outer gas           24,352,064,730,000 wei, paid by the bundler
wallet code         4663: 0xef0100d6cedde84be40893d153be9d467cd6ad37875b28     Base: 0x
```

The target address matches the canonical ERC-4337 EntryPoint v0.7 address, and
it emits `UserOperationEvent` with the canonical signature. The identification
rests on that match, which is **inferred**; we did not verify its source. The
authorization carries our wallet's signature for chain 4663 only, so the wallet
now runs the delegate's code **on 4663** and is still a plain EOA on Base.

**Consequences, stated as constraints; the design belongs to 4.x and 5.x:**

- **`tx.from` is the bundler, not us.** Receipt reconciliation (5.3) must key on
  `UserOperationEvent.sender` and on `Transfer` logs to or from our wallet. A
  check that the transaction was sent from our wallet returns False for a swap
  that plainly moved our funds, and this probe's first cut made exactly that
  mistake.
- **The outer receipt's `status` says the bundle mined, not that our swap
  worked.** The swap's own outcome is `UserOperationEvent.success`, so a reverted
  swap can sit inside a status-1 transaction. Bankr's documented
  `200 success:false` presumably reflects the latter. That is **inferred**; no
  revert was observed.
- **Gas was sponsored.** Our wallet paid nothing, and the bundler paid ~$0.06.
  Whether sponsorship is permanent, or depends on size or plan, is undocumented.
  The journal's gas line for these swaps is zero, measured once.
- **The wallet's nonce no longer counts our transactions.** The first swap
  consumed nonce 0 with the delegation. That is why this probe's first arbiter —
  nonce delta equals broadcasts — was wrong (corrected in `probes/idempotency.py`).
- **The fund's wallet now runs code chosen by Bankr on 4663.** Custody was
  already Bankr's, so the trust boundary barely moves, but it is now enforced by
  code as well as by key custody. What the delegate at `0xd6ce…5b28` permits
  (24,469 bytes; not read) is **unresolved**.

### F0.10.4 — 6 bps of the sale is unaccounted for, although the quote said `feeBps: 0`

**Confidence: measured (the gap). Verdict: unresolved.**

The wallet sold 30,000 gwei of ETH; WETH minted 29,982 gwei. The other 18 gwei
(0.06%) went to an address that appears in no log and in no field of the
transaction. The native balances of every address the transaction names were
read at blocks N−1 and N, and none of them received it. The RPC exposes neither
`debug_traceTransaction` nor `trace_transaction`, so the recipient cannot be
found from here. The USDG received equalled the quoted `formattedAmount`
exactly, which suggests the cost is priced into the quote rather than added on
top. That is **inferred**.

**For the books:** a quote's `feeBps: 0` is not evidence of a fee-free fill.
Reconcile from balances. The gap is $0.00005 here, and would be about $0.015 on a
$25 trade.

### F0.10.5 — No rate limit within 150 requests in 4.1 s, and no rate-limit headers at all

**Confidence: measured (a lower bound). Verdict: unresolved.**

`GET /wallet/me` with `BANKR_KEY_READ`, 8 threads, 150 requests in 4.1 s (~37
per second): **150 × 200**, p50 142 ms, max 1,309 ms. No response carried
`Retry-After`, `X-RateLimit-*` or `RateLimit-*`. The full header set is recorded,
and it shows an AWS load balancer (`AWSALB*` cookies) and an
`access-control-expose-headers` naming only the x402 headers. The limit
follow-ups never fired.

The shape of a 429 — body, `Retry-After` — is therefore still only
**documented** (*"429 — Rate limited, retry in a moment"*). The burst was not
escalated, and no other endpoint was tried: "adjust until something trips" is the
loop this repository avoids, and the result is stated as the bound it is.
**Consequence for 1.3:** there are no advance-warning headers to pace against, so
the client treats a 429 as its only signal and backs off without a published
budget.

### What 0.10 changes

| Change | Where |
|---|---|
| A repeat with the same key returns the original result; §4's "never mint a new key" rule holds for completed swaps | §4, 4.2, 4.9 |
| The 409-in-flight path is still documented only | 4.10 |
| `BANKR_KEY_EXEC` can transact — F0.5.5 settled for one ungated sell | Phase 5, 5.2 |
| Swaps are sponsored 4337 UserOperations inside 7702 transactions; reconcile on `UserOperationEvent` and `Transfer` logs, never `tx.from` or the EOA nonce | 4.6, 5.3 |
| The wallet is 7702-delegated to a Bankr delegate on 4663 | `planning/PLAN.md` §6, §13 |
| 6 bps unaccounted for despite `feeBps: 0`; reconcile fills from balances | 4.6, 6.2 |
| No rate-limit headers; no limit reached at ~37 req/s for 4 s | 1.3 |

### Method limitations

- **One swap:** one direction, one asset, $0.08, one day. Nothing here bounds
  larger sizes, sells of USDG, or sponsorship that depends on plan or size.
- The repeat was sequential; the in-flight 409 is untested.
- The EntryPoint and the delegate are identified by canonical address, code
  presence and event signature. Neither contract's source was read.
- No tracing on the RPC, so internal calls, including the 18 gwei, are not
  visible.
- Rate limit: one endpoint, one key, one burst. The result is a lower bound, and
  the per-key and recovery follow-ups never ran.
- **Cost:** 0.00003 ETH converted to 0.078742 USDG, gas $0 to us, and 18 gwei
  (~$0.00005) unaccounted for.

---

## 1.7 — Analyst cost against a real snapshot

**Date:** 2026-09-19 UTC · **Method:** `PYTHONPATH=src python3 -m probes.analyst_cost
fixtures/live/snapshot-7eba62122aab747f911d3001ed7846a7187b346aa1af17877c7bbe12ce3f97dd.json --confirm`
· **Captures:** `probes/out/analyst_cost.json`

> **This is the number 0.9 deferred to.** The snapshot is a real one:
> - sha256 `7eba62122aab…`, block 66728957, Sat 02:34Z, 335,294 bytes;
> - 35 assets and 4,628 rounds;
> - embedded byte for byte, with the hash checked before any call.
>
> One of its series is short (F1.7.8), so its timeline is about 2% lighter than
> a clean read. The brief is 0.9's, unchanged: the real one is 2.1's. The
> analyst covered all 35 assets, which is right for the universe-wide roles and
> an upper bound for the asset-partitioned ones. Four calls were made, at
> `claude-sonnet-5`.

### F1.7.1 — One analyst call: 185,168 in, 7,725–9,087 out, $0.448–$0.461, 62–75 s

**Confidence: measured, two identical calls.**

| | Call 1 | Call 2 |
|---|---|---|
| Input tokens | **185,168** | **185,168** |
| Output tokens | **9,087** | **7,725** |
| Latency | **75.0 s** | **62.4 s** |
| Cost at $2/M in, $10/M out | **$0.461206** | **$0.447586** |
| Finish | stop | stop |
| Cached tokens | 0 | 0 |

- **Input is identical,** as it must be for identical bytes.
- **Output differs by 18%** between two identical calls at temperature 0:
  1,362 tokens over 7,725, reckoned the way 0.9's 14% was (F0.9.3). Two calls show that the spread exists and
  is of that order. They do not measure its distribution, and a budget built on
  them should carry headroom.
- **Input is 81% of the cost:** $0.370 of $0.454.
- **The snapshot fits.** 185,168 tokens is 18.5% of the model's 1,000,000-token
  window. It came to 1.82 characters a token, denser than 0.9's 2.02.

### F1.7.2 — The timeline is two thirds of the input

**Confidence: measured, by difference.** The gateway has no count-tokens
endpoint (`/v1/messages/count_tokens` returned 404), so a third call sent the
same prompt with every asset's `timeline` removed, and `max_tokens` 1.

| Part | Input tokens | Share | Per analyst call |
|---|---|---|---|
| Timeline, 4,628 rounds | **123,765** | **66.8%** | $0.2475 |
| Everything else: the other snapshot fields, 0.9's brief, the output schema | 61,403 | 33.2% | $0.1228 |
| **Total** | **185,168** | | $0.3703 |

By bytes the timeline is 62% (208,518 of 335,294). By tokens it is more,
because a `[time, price]` pair is dense digits: about **26.7 tokens a round**.
- **Per cycle,** at four analysts, the timeline's input is **$0.99 of $1.87**:
  53% of the whole cycle.
- **What thinning would buy,** as arithmetic: every 1,000 rounds cut saves about
  26,700 tokens a call, $0.053 a call and $0.21 a cycle. Halving the history
  saves about $0.50 a cycle, $15 a month.

Whether to thin, and how, is the operator's decision, not this probe's.

### F1.7.3 — A cycle costs $1.87: 28 times the 0.9 floor

**Confidence: the analyst and risk calls measured; the multiplication is
arithmetic.**

| | 0.9 floor (6 assets) | **1.7 (real snapshot)** |
|---|---|---|
| Analyst call | $0.0134 | **$0.4544** (mean of two) |
| Risk call | priced as an analyst call | **$0.0484** (measured, stand-in reports) |
| Cycle (4 analysts + 1 risk) | $0.0670 | **$1.8659** |
| Day (daily cadence) | $0.067 | **$1.87** |
| 30 days | $2.01 | **$55.98** |
| x402 records at $0.05 to cover one cycle | 1.3 | **37.3** |

- **The risk call** read four copies of call 1's report, 11,380 visible
  characters each, plus a five-order stand-in plan: 20,963 in, 643 out, 7.7 s.
  Its input is a stand-in until Phase 2 produces real, different reports.
- **The x402 price.** At $0.05 a record, the endpoint must sell **37 records a
  day** to cover inference alone. That comes before funding overhead and gas,
  and no third party has yet paid it (F0.7d.8). The price is the operator's to
  confirm or revise (0.11 decision).

### F1.7.4 — The timeouts cover today's calls, and are not sized for the evidence

**Confidence: latencies measured; the recommendation is inference from them.**

The configuration is `transport_timeout_seconds` 180 and
`worker_deadline_seconds` 120.

| Call | Output tokens | Latency | Output rate |
|---|---|---|---|
| 1.7 analyst 1 | 9,087 | 75.0 s | ~121 tokens/s |
| 1.7 analyst 2 | 7,725 | 62.4 s | ~124 tokens/s |
| 1.7 risk | 643 | 7.7 s | — |
| 1.7 input only, 61k tokens | 16 | 4.0 s | — |
| 0.9 analyst (F0.9.1) | 982 | 58.1 s | ~17 tokens/s |

**Verdict: not correctly sized.**
- **Today they suffice.** Both analyst calls finished inside 120 s, the slower
  with 45 s to spare.
- **But output is uncapped.** `max_output_tokens` is null, and the replies ran
  to 9,087 tokens.
- **And throughput has varied sevenfold.** It ran at ~17 tokens/s at 0.9 and
  ~121 today. A 9,087-token reply at 0.9's rate takes about 535 s. The 120 s
  deadline would cut that off, and a call cut off client-side is still billed
  with no report (F0.9.3).
- **And the two are inverted.** The 120 s worker deadline fires before the
  180 s transport timeout, so inside the runner the transport timeout never
  acts (LESSONS 2026-09-18).

**What they should be,** recommended and not set, since the values are 2.4's
and the operator's:
- **`max_output_tokens`: about 12,000,** 1.3 times the largest reply measured.
  A deadline can only be derived from a cap.
- **`transport_timeout_seconds`: at least 600.** That covers a 9,000-token
  reply at the slowest rate measured, 535 s. At a 12,000 cap and that rate the
  bound would be about 710 s.
- **`worker_deadline_seconds`: at least the transport timeout plus a margin,**
  such as 630, so the transport ends a call and the inversion goes.

At daily cadence a ten-minute bound costs nothing. A cut-off call costs a full
call with no report.

### F1.7.5 — About half the billed output is not in the reply

**Confidence: inferred, not measured.** The `usage` block gives no breakdown.

| Call | Output tokens billed | Visible reply | Characters a token |
|---|---|---|---|
| Analyst 1 | 9,087 | 11,380 chars | **1.25** |
| Analyst 2 | 7,725 | 12,092 chars | **1.57** |
| Risk | 643 | 1,610 chars | 2.50 |

At the risk reply's 2.5 characters a token, the analyst replies' visible text
would be about 4,550 and 4,840 tokens. So roughly **37–50% of each analyst
call's billed output is not in what comes back.** Hidden reasoning is the likely cause, and
it is not confirmed. It costs about $0.03–0.05 a call, and it counts toward
latency and toward any output cap.

### F1.7.6 — No automatic caching; explicit caching would roughly halve a cycle

**Confidence: no caching measured; the saving priced from listed rates, not
measured.**
- **Nothing was cached.** Two byte-identical calls reported `cached_tokens: 0`
  both times, so the gateway does not cache automatically on
  `/v1/chat/completions`.
- **The price list offers caching.** It lists `cache_write` $2.50/M and
  `cache_read` $0.20/M for this model.
- **Four analysts read the same bytes** (PLAN §2 invariant 2). So one cache
  write and three cache reads would take a cycle's analyst inputs from **$1.48
  to $0.57**, and the cycle from $1.87 to about **$0.96**.
- **Untested.** Whether the gateway honours explicit cache control, on
  `/v1/messages`, and at what time-to-live, is unknown.

### F1.7.7 — 62 of 65 text models hold this prompt; the per-call price spans 180×

**Confidence: measured tokens at listed prices; arithmetic.**
- **Three models are too small** once a 16,000-token output allowance is
  added: `deepseek-v3.2` (163,840 window), `claude-haiku-4.5` and
  `claude-opus-4.5` (200,000 each). The 185,168-token prompt alone fits the
  last two.
- **The same measured call ranges from $0.0129 to $2.306.**

| Model | Per analyst call |
|---|---|
| `gpt-5-nano` | $0.0129 |
| `claude-haiku-4.5` | $0.2306 |
| `claude-sonnet-5` | $0.4612 |
| `claude-opus-5` | $1.153 |
| `claude-fable-5.1` | $2.306 |

As at 0.9 (F0.9.5), the model pin is the largest lever. It is 2.4's to pull.

### F1.7.8 — The measured snapshot had one short series: an unretried missing-state error

**Confidence: measured.** SPCX's walk stopped after its newest round:

> `read failed at round 18446744073709554893: [rpc] -32000: … layer stale
> missing trie node … (path 0d) layer stale`

The snapshot says so:
- coverage is `null` with that reason;
- the timeline has one point.

The analyst read that, and abstained on SPCX for exactly that reason. Nothing
was silent, but the read should not have stopped there.
- **It is a missing-state error.** 1.3's client retries missing state only when
  the message says "historical state … not available", and this one is worded
  differently. A read by block hash is safe to retry either way. The client
  change is owed in `adapters/chain_4663.py`.
- **The snapshot still says tradeable.** Its status judges the newest round,
  not coverage, so SPCX stays tradeable with a one-point history. Whether short
  coverage should affect status is open.

### Reconciliation

**Confidence: measured.** The three instruments agree to the last digit:
- **Listed price times tokens:** $1.080114 for the four calls.
- **Credit balance:** $2.799976 before and $1.719862 once settled, a fall of
  $1.080114. Deductions lagged by about one call during the run.
- **`/v1/usage`, one settled window** read after the calls: 6 requests, 456,288
  input and 19,317 output tokens, $1.105746. That is these four calls plus
  0.9's two (F0.9.3), exactly. It was not read as a delta around any call.

Two undocumented fields also came back. Their meaning is unresolved:
- `buyer_cost_micro`, 115,302 against $0.461 charged, a ratio of 4.0 (it was
  2.2 at 0.9);
- `"cost": {"diem": 0.691809, "usd": 0}`, with the `/v1/usage` row naming the
  provider `surplus`.

### What the reports said, as a snapshot-design signal only

At 0.9, one-block data drew `NO_CALL` on all six assets (F0.9.6). Against this
snapshot, call 1 returned **35 reports**:
- 16 BUY, 15 HOLD, 3 SELL and 1 NO_CALL, plus one abstention, SPCX, for its
  missing history;
- the reasoning cites the timeline, for example "a tight range 330-339 over
  the week".

This is one call with a draft brief. It shows that the history is read and
used, not that the calls are any good.

### What 1.7 changes

| Change | Where |
|---|---|
| A cycle is $1.87, $56 a month, at Sonnet 5 uncached | 2.4, 6.3, 7.2; the price |
| The timeline is 67% of input and 53% of a cycle | 1.6 history window, the operator |
| $0.05 a record needs 37 sales a day to cover inference | 0.7 checkpoint, 7.2 |
| The timeouts must come from an output cap and the slowest rate, not today's | 2.4; `config/models.json` |
| Explicit prompt caching could halve a cycle; untested | 2.4 |
| Missing-state errors come in more than one wording; retry them | 1.3's client |
| A short series leaves the status unchanged; open | 1.6, 1.11 |

### Method limitations

- **Two analyst calls, one risk call, one model, one brief, one snapshot, and
  one hour.** The latency and output spreads are what two samples show, not
  distributions.
- **The risk call's input is four copies of one report,** not four different
  ones.
- **The hidden-output reading (F1.7.5) is inferred** from character ratios.
- **The measured snapshot's timeline is about 2% light,** because of SPCX
  (F1.7.8).
- **Spent: $1.080114.** The balance went from $2.799976 to $1.719862.

---

## 1.8a — Daily closes and prompt caching, measured (DECISIONs after 1.7)

**Date:** 2026-09-19 UTC · **Method:** `PYTHONPATH=src python3 -m probes.analyst_cost
fixtures/live/snapshot-2e95fab1437593aa4722e8e96153e21fffcaf1e32c919be72a64b52f662ce524.json
--one --confirm`, then `--cache --confirm` · **Captures:** `probes/out/analyst_cost_one.json`,
`probes/out/analyst_cost_cache.json`

> **Three calls, both measurements on one snapshot.** Snapshot `2e95fab1…`:
> - block 66742900, Sat 02:57Z;
> - 189,357 bytes, 35 assets;
> - a timeline of **daily closes over 30 days**: 763 points, where 1.7's
>   snapshot had 4,628.
>
> The brief is 0.9's, as at 1.7, at `claude-sonnet-5` with the 12,000 output
> cap now set.

### F1.8a.1 — Daily closes halve the input and cut an analyst call by 42%

**Confidence: measured, one call, against 1.7's two.**

| | 1.7 call 1 | 1.7 call 2 | **Daily closes** |
|---|---|---|---|
| Snapshot | 335,294 B, 4,628 pts | same | **189,357 B, 763 pts** |
| Input tokens | 185,168 | 185,168 | **94,716** (−48.8%) |
| Output tokens | 9,087 | 7,725 | 7,484 |
| Latency | 75.0 s | 62.4 s | 60.0 s |
| Cost | $0.4612 | $0.4476 | **$0.2643** (−41.8% on the mean) |

The timeline went from 62% of the snapshot's bytes to 32%.

### F1.8a.2 — The reports used history as much as 1.7's did

**Confidence: measured counts. As a judge of quality it is a proxy.**

| Reports that… | 1.7 call 1 | 1.7 call 2 | **Daily closes** |
|---|---|---|---|
| cite the timeline | 35 of 35 | 20 of 35 | **35 of 35** |
| quote dated points | 31 | 10 | **18** |
| name two or more price levels | 34 | 33 | **35** |
| say `NO_CALL` or abstain | 1 + 1 | 16 + 0 | **0 + 0** |

- **The daily call sits inside the range** that 1.7's two *identical* calls
  spanned on every count. The two identical calls already disagreed from 1
  `NO_CALL` to 16. One call against two cannot show variance, and it does not
  show that daily closes are better.
- **Read, the reasoning uses the longer view.** "30-day closes rose from 310.85
  (08-20) to 335.38 latest, +7.9%… accelerating over the last two weeks", and
  "net still down ~3.9% but momentum has turned up".
- **Some calls change with the window.** BABA reads as a 30-day downtrend
  (−12.3%, SELL) where the 7-day view saw "a steady climb" (+4%, BUY). Both are
  right for their window, and a fund that rebalances daily is better served by
  the longer one.
- **On these measures the analysts are not worse,** so the decision's
  condition is met and daily closes are adopted.

### F1.8a.3 — The series is honest across a weekend and a holiday

**Confidence: measured.** Take NVDA's timeline. From 2026-08-20 to 09-18 it has
21 closes at 20:00Z:
- **8 weekend days** fell in the inferred closed session and have **no close**;
- **1 day, Mon 09-07 (Labor Day),** had no new round since Friday's close, so
  it has **no close** either;
- **nothing is carried forward or interpolated;**
- **the coverage reason names both counts.**

The latest round is always the last point. At this block that was Friday's
close itself, so no separate `latest` row appeared. Freshness and the mark
still judge the newest round, not a close.

The 20:00Z cut is 16:00 in New York in daylight time. From 1 November it will
be 15:00. That is recorded, and it is not a close under any exchange's
definition.

### F1.8a.4 — The gateway does not honour prompt caching

**Confidence: measured. Verdict: fail.** Two calls on `/v1/messages`, with the
system prompt and the snapshot marked `cache_control: {"type": "ephemeral"}`:
- the first under the price-trend scope;
- the second, 62 s later, under the execution-quality scope, over the same
  prefix, as four analysts sharing one snapshot would.

| Call | Input tokens | Output | Cost at listed rates | Balance fell by |
|---|---|---|---|---|
| 1, write expected | 94,719 | 7,470 | $0.264138 | $0.264138 |
| 2, read expected | 94,722 | 6,486 | $0.254304 | $0.254304 |

- **Neither response's `usage` carries `cache_creation_input_tokens` or
  `cache_read_input_tokens`.** Both were billed full input at $2/M.
- **The gateway's own settled window agrees.** `/v1/usage` records
  `totalCacheReadInputTokens: 0` and `totalCacheWriteInputTokens: 0`, although
  the price list offers `cache_read` $0.20/M and `cache_write` $2.50/M.
- **The provider named is `surplus`.**
- **The saving F1.7.6 priced, from $1.87 to $0.96 a cycle, is not available**
  on this path. Whether another request shape would be honoured is untested:
  the decision allowed two calls.

### F1.8a.5 — The cycle, repriced

**Confidence: analyst call measured; risk call is 1.7's measurement; the rest is
arithmetic.**

| | 1.7 (every round, 7 days) | **1.8 (daily closes, 30 days)** |
|---|---|---|
| Analyst call | $0.4544 | **$0.2643** |
| Risk call | $0.0484 | $0.0484 (1.7's; its input is the reports, not the snapshot) |
| **Cycle** | $1.866 | **$1.106** |
| 30 days | $55.98 | **$33.16** |
| Records to cover a cycle at $0.25 | 7.5 | **4.4** |

### Reconciliation

**Confidence: measured.**
- **The balance** went from $1.719862 to $0.937148, a fall of $0.782714. That
  is exactly the three calls at listed prices: $0.264272 + $0.264138 +
  $0.254304.
- **`/v1/usage`'s settled window** holds 9 requests and $1.88846. That is
  0.9's two calls, 1.7's four and these three, exactly.

### Method limitations

- **One daily-close analyst call,** against 1.7's two. The report counts are a
  proxy, not a grade. The 2.1 brief will change what "using history" looks
  like.
- **Caching was tested on one endpoint, in one request shape, twice.**
- **Spent: $0.782714.** The balance went from $1.719862 to $0.937148.

---

## 2.0 — Can SIWE make an agent account? Measured once

**Date:** 2026-09-19 · **Method:**
- one `bankr login siwe` (installed CLI 0.3.37) under a separate config file;
- the SIWE key fed in from a file by `probes/siwe/hook.mjs`, which also kept
  the login's own answer;
- then `PYTHONPATH=src python3 -m probes.siwe_agent --confirm`.

**Captures:** the gitignored `probes/out/siwe_agent.json`. The login record and
the agent's key and config sit outside the repository, in
`~/.openfund/agents/price-integrity/`, mode 0600.

**The question.** Phase 2 assumes each agent has its own Bankr account and
address, a key that cannot transact, the Agent API off, and access to the LLM
gateway so it pays for its own inference. The CLI's help and source cast doubt
on the last: the SIWE request never asks for the gateway (LESSONS 2026-09-19).
**Each property was tested by what the key does,** not by a flag.

| Requirement | Result | Verdict |
|---|---|---|
| Its own address, distinct from the fund's | `0x42a9…3d27`, not the fund's and not the signer's | **pass**, measured |
| Its key cannot transact | a signature and a quoted swap each refused 403 "Read-only API key" | **pass**, measured |
| Agent API off | `/agent/prompt` refused 403 "Agent API access not enabled" | **pass**, measured |
| Reaches the LLM gateway | every gateway call refused 403 "does not have LLM Gateway access enabled" | **fail**, measured |
| Can buy its own credits | the top-up refused 403 at the gateway toggle, before anything else was checked | **fail** for this key; read-only's own effect **unresolved** |

### F2.0.1 — The account exists, with its own address

**Confidence: measured. Verdict: pass.**

The login returned `walletAddress` `0x42a9bd235aedd68e9f2881710577105cb46e3d27`.
- `/wallet/me` and `/wallet/portfolio`, read with the new key, name the same
  address.
- It is neither the fund's `0x93fa…a3da` nor the SIWE signer's
  `0x45e1E65c…94bd1`.
- `/wallet/me` lists the account's one identity as a social account of
  platform `api`, whose username is the signer's address.

So the signer is the account's sign-in identity, and **the wallet is a new
Bankr-custodied wallet, not the signer's own address.** The CLI's source implied
this; this measures it. A never-issued key drew 401 on the same endpoint.

### F2.0.2 — The login reports one flag: `readOnly: true`

**Confidence: measured.**
- **Sent:** `readOnly: true`, `walletApiEnabled: true`, `agentApiEnabled:
  false`, `tokenLaunchApiEnabled: false`, and no `llmGatewayEnabled`.
- **Answered:** `success`, `apiKey`, `walletAddress` and `readOnly: true`.
  Nothing more.

So "the key's flags as the API reports them" is `readOnly` alone. The Agent API
and the gateway are not reported, and F2.0.3 to F2.0.5 establish them by
behaviour.

### F2.0.3 — The key cannot transact, and says why

**Confidence: measured. Verdict: pass.**

| Request, with the agent key | Answer |
|---|---|
| `POST /wallet/sign`, `personal_sign` of a plain message | **403** `{"error":"Read-only API key","message":"This API key has read-only access and cannot sign messages or transactions. …"}` |
| `POST /wallet/swap`, 0.00003 ETH → USDG on 4663, with a live quote's `minBuyAmount` and `quoteId` | **403** `{"error":"Read-only API key","message":"This API key has read-only access and cannot execute swaps. …"}` |
| `POST /wallet/sign` with a never-issued key (control) | **401** |

**Why the refusals are attributable.**
- A signature needs no balance, so the empty wallet cannot be why it was
  refused.
- Both bodies name the permission, and the swap's quote succeeded first (200).
- The wallet was read empty on every chain it could spend from, before and
  after: 0 ETH on 4663, 0 ETH and 0 USDC on Base. **Nothing could have moved,
  and nothing did.**

The one signing surface that exists, `/wallet/sign`, is guarded by the
read-only toggle.

### F2.0.4 — The Agent API is off, measured by refusal

**Confidence: measured. Verdict: pass.**
- **`/agent/prompt`,** with a prompt asking for no action, drew **403**
  `{"error":"Agent API access not enabled", …}`. This settles for this key
  what F0.2.5 could not settle by a read. A refused write names the toggle,
  where a read of an unknown job did not.
- **`POST /agent/sign`** drew **404** `Cannot POST /agent/sign`. The route
  `research/bankr-claude.md` lists (from `bankr-sign-submit-api/SKILL.md`)
  does not exist at `api.bankr.bot` for POST. The signing surface is
  `/wallet/sign` (F2.0.3).

### F2.0.5 — The key cannot reach the LLM gateway

**Confidence: measured. Verdict: fail, against the plan.**
- `GET /v1/credits`, `GET /v1/models` and `POST /v1/chat/completions` (5
  tokens, `claude-sonnet-5`) all drew **403** `{"error":{"message":"This API
  key does not have LLM Gateway access enabled. Enable it in your API key
  settings at bankr.bot/api-keys","type":"auth_error"}}`.
- **This is the same body `BANKR_KEY_READ` draws,** and that key is the known
  gateway-off control (F0.2.4). A never-issued key drew 401.
- It agrees with the CLI's source: the SIWE request never sends
  `llmGatewayEnabled`. **For this key, measured, the server's default is off.**

Without the gateway, the agent cannot run inference on its own account at all.

### F2.0.6 — The agent cannot buy its own credits with this key

**Confidence: the refusal is measured. The read-only question is unresolved.**

`POST /llm/credits/topup` is the call `bankr llm credits add` makes. It was
sent for $1 from Base, from a wallet read as holding 0 USDC, so it could not
spend. It drew **403** `{"error":"LLM Gateway access not enabled", …}`.

The gateway check fires first. **So whether a read-only key *with* gateway
access could buy credits is not measured.** The top-up moves the wallet's USDC,
and read-only might refuse it too.

### F2.0.7 — The fund's session and both secrets stayed where they belong

**Confidence: measured.**
- **The fund's CLI config** hashed `ae5bcd22…` before and after, and
  `bankr whoami` still answers `0x93fa…a3da`.
- **The agent key** was written only to its own config file, outside the
  repository, and is masked in every capture.
- **The SIWE key** never appeared on a command line: the hook spliced it in
  inside the process. It never entered the probe that tested the agent key.
- **A scan of the working tree,** gitignored files included, finds neither
  secret.

### Verdict

**The five-wallet plan cannot proceed as designed through SIWE alone.**
- Three of the four requirements hold, each measured by a refusal that names
  its reason.
- The fourth fails: the key cannot reach the LLM gateway. So the agent can
  neither run inference nor buy credits on its own account.

**The options** are recorded, not chosen:
- **(a) Email sign-ups.** `bankr login email <address> --llm`, which is the CLI
  path that sends `llmGatewayEnabled` (documented by code, **not tested**),
  with `--read-only --no-agent-api --no-token-launch`. It costs five email
  identities and five one-time codes. Whether plus-addressing gives distinct
  accounts is unknown. Each key would need the same four measurements.
- **(b) The dashboard.** The 403 itself names `bankr.bot/api-keys`. Whether a
  SIWE-made account can sign in there is **unknown**. Its only identity is the
  `api` account keyed to the signer. Signing in with a browser wallet would
  expose the SIWE key in a new place.
- **(c) Own wallets, inference on the fund's key.** **Available now,
  measured.**
  - Each agent keeps an account like this one: its own address, read-only,
    Agent API off.
  - Its inference bills to the fund's `BANKR_LLM_KEY`, which reaches the
    gateway (F0.6.1) and holds $0.937148.
  - It gives up "each agent pays for its own inference", and per-agent cost
    goes back to F0.6.4's aggregate.
- **Untested, recorded rather than tried:** a direct `/cli/siwe/verify` with
  `llmGatewayEnabled: true`. That is the field the email flow's key creation
  takes. Whether the SIWE route accepts it is unknown, and trying it mints a
  second key on this account.
- **Ruled out:** one shared wallet.

### What 2.0 changes

| Change | Where |
|---|---|
| The five-wallet plan waits on the operator's choice among (a), (b) and (c). 2.4's credential rows wait with it. | `planning/PHASE-2.md` 2.0 and 2.4 |
| One agent account exists: `price-integrity`, `0x42a9…3d27`. Its key is outside the repository and not in `.env`. | — |
| A refused write names its toggle, so the Agent API's state is measurable. That is cheaper than F0.2.5 thought. | F0.2.5 |
| `POST /agent/sign` does not exist at `api.bankr.bot`. | `research/bankr-claude.md` |

### Method limitations

- **One account, one key, one moment.** The gateway default could differ by
  account type or change over time.
- **The refusals were all sent to an empty wallet.** They are attributable
  because each body names the permission, and because a signature needs no
  balance.
- **Not tried:** `/wallet/submit`, `/wallet/transfer`, typed-data signing.
  F2.0.3's body says read-only refuses "messages or transactions".
- **F2.0.4's prompt call ran once and was then removed from the probe.**
  `tests/test_boundaries.py` forbids any call to that endpoint under `probes/`
  (0.2's done-condition), and it failed on the probe as it should. The call was
  taken out rather than disguised, so the rule holds and the answer stays here.
  Re-measuring it needs the rule relaxed by name, which is the operator's call.
- **Spent: $0.** Nothing was bought, nothing moved, and every attempt was sent
  once.


---

## 2.6 — The first real analyst report

**Date:** 2026-09-19, sent 15:39:00Z. **Method:**
`PYTHONPATH=src python3 -m fund.agents.runner --snapshot
fixtures/snapshots/66852293-253315c0e691/snapshot.json --seats price-integrity
--retries 0 --confirm`. That is one seat and one call. The runner's retry was
held at 0 so the measurement is a single call. **Captures:**
`fixtures/live/cycles/20260919T153900Z/` (gitignored): the result, the job and
the event log.

### The keys, measured before anything ran

`probes/keymap.py`, read-only, with the 2.0 key and a never-issued key as
controls:

| Key | Wallet API | Read-only | LLM gateway | Agent API |
|---|---|---|---|---|
| `BANKR_LLM_KEY` | **off**: `/wallet/sign` refused 403 "Wallet API access not enabled" | not measurable: the Wallet API refuses first | on, balance $15.791107 | **off**, refused 403 |
| `BANKR_KEY_READ` | on | yes: 403 "Read-only API key" | off | off |
| `BANKR_KEY_EXEC` | on | no: 400 validation, as labelled | off | off |

**Verdict: the key the analysts hold is refused by name on both surfaces that
can sign or transact.** It matches the dashboard's word, where the 2026-09-19
measurement did not.

**Two things this cannot measure:** the read-only toggle itself on this key,
and token launch on any key. No read is gated by token launch, and a deploy
request was not sent.

### The report, as it came back, unedited

```
REPORT price-integrity 0x93faecde3c88a713e1edddf417c02c326889a3da 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The block carries a closed us_equities_24/5 session: every stock's Chainlink mark is frozen at its last pre-close round while GeckoTerminal and the venue AMM keep trading. The snapshot already flags five tradeable assets as closed-session divergences past 100bps (AMD, AMZN, GOOGL, MSTR, SGOV). Because a divergence alone doesn't say which of the three prices is wrong, I checked pairwise agreement: where GeckoTerminal and the venue land close to each other and far from the mark, the mark is the stale/broken one; where the mark and venue agree and only GeckoTerminal is the outlier, the mark still holds up despite the flagged finding. The other fifteen flagged assets sit below the GeckoTerminal volume line and are not tradeable, so I make no call on them. The remaining tradeable assets show no material three-way disagreement and need no comment.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc caution medium
GeckoTerminal and the venue sit within ~30bps of each other while the frozen mark is ~136bps above both, so the closed-session freeze looks like it is overstating AMD, not the two live sources disagreeing.
- 559.42445 mark [mark.price_usd]
- 553.5582086607 GeckoTerminal [corroboration.price_usd]
- 551.9120935475604 venue [quote.venue_price_usd]
- mark vs venue diverges ~136bps, GeckoTerminal vs venue only ~30bps [mark.price_usd, quote.venue_price_usd, corroboration.price_usd]
Wrong if: GeckoTerminal and the venue diverge from each other by more than 50bps at reopen, which would undercut the assumption that they, not the mark, are in agreement.

CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 proceed low
The recorded -450.32bps finding is GeckoTerminal versus the mark, but the mark and the venue agree closely; the finding is GeckoTerminal's problem, not the mark's.
- 253.863 mark [mark.price_usd]
- 253.28085544501803 venue, ~23bps from mark [quote.venue_price_usd, mark.price_usd]
- 265.8339854153 GeckoTerminal, divergence -450.32bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price moves to track GeckoTerminal instead, diverging from the mark by more than 100bps.

CALL GOOGL 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 proceed low
Same pattern as AMZN: mark and venue are ~12bps apart while GeckoTerminal sits ~147bps from the venue, so the flagged -132.33bps finding traces to GeckoTerminal, not the mark.
- 350.47135177 mark [mark.price_usd]
- 350.04082044804966 venue, ~12bps from mark [quote.venue_price_usd, mark.price_usd]
- 355.171284689 GeckoTerminal, divergence -132.33bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price drifts toward GeckoTerminal, diverging from the mark by more than 100bps.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution medium
GeckoTerminal and the venue are only ~55bps apart from each other, but the frozen mark is ~132-187bps from both, marking it as the outlier this close.
- 152.643 mark [mark.price_usd]
- 155.5016463786 GeckoTerminal [corroboration.price_usd]
- 154.65896270001573 venue [quote.venue_price_usd]
- mark vs venue diverges ~132bps, GeckoTerminal vs venue only ~55bps [mark.price_usd, quote.venue_price_usd, corroboration.price_usd]
Wrong if: GeckoTerminal and the venue diverge from each other by more than 80bps at reopen, undercutting the case that mark alone is off.

CALL SGOV 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 proceed low
The 124.7bps finding is GeckoTerminal versus the mark; mark and venue are only ~22bps apart, so GeckoTerminal, likely thin here, is the one out of line, not the mark.
- 101.10821255 mark [mark.price_usd]
- 100.88197839075325 venue, ~22bps from mark [quote.venue_price_usd, mark.price_usd]
- 99.8629967858 GeckoTerminal, divergence 124.7bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price drifts down toward GeckoTerminal, diverging from the mark by more than 80bps.
```

### F2.6.1 — It was refused, on one real rule and one validator defect

**Confidence: measured.**

**As run, the verdict was `invalid`, with six refusals:**
- **`header`:** the agent field is `0x93fa…a3da`, the fund's wallet, where the
  brief gave `0x…` and said the first line "must be exactly" as given.
  - The model read the unassigned placeholder as an elided address and filled
    in the only wallet the snapshot names.
  - **This is a real failure,** and it is the brief's and the placeholder's as
    much as the model's.
- **Five `figure` refusals:** `136bps`, `23bps`, `12bps`, `132bps`, `22bps`.
  - Each is a divergence the model computed between the prices it cited.
  - **All five are correct** to within a basis point (checked by hand below).
  - **The validator was wrong to refuse them.** 2.2 treats any number followed
    by "bps" as a claim about a `_bps` field. The approved rule says a computed
    figure is cited and not checked.

**Re-validating the same recorded text** in a scratch copy, with no new call:
- with only the bps rule corrected (a bps figure is checked only when its line
  cites a `_bps` field), **the sole refusal is the header**;
- with the header's agent also as expected, **the report is accepted.** Its five
  calls are MSTR and AMD `caution medium`, and AMZN, GOOGL and SGOV
  `proceed low`.

**The fix is owed.** It is the bps rule and its test, and `tests/` was outside
this unit's paths. Nothing in `src/` changed after the call.

### F2.6.2 — No figure was fabricated

**Confidence: measured.**
- **Every figure that is a single field matched it.** The model copied each
  field at full precision, such as `551.9120935475604`. The two divergence
  fields it cited (`-450.32`, `-132.33`) matched `corroboration.divergence_bps`.
- **Its computed figures, checked by hand against the snapshot:**
  - AMD: mark against venue 136.1 bps, GeckoTerminal against venue 29.8.
  - AMZN: 23.0.
  - GOOGL: 12.3 and 146.6.
  - MSTR: 130.3, 54.5 and 183.8.
  - SGOV: 22.4.

  All are right except one clause. "The frozen mark is ~136bps above both" is
  true of the venue, but the mark sits 106 bps above GeckoTerminal.
- **The validator catches none of the prose.** It did not catch "venue AMM" (the
  venue is RFQ, and the snapshot never calls it an AMM). Nor did it catch "the
  other fifteen flagged assets", which are below the volume line, not flagged,
  or "GeckoTerminal, likely thin here" for SGOV, whose $2.35M of volume is over
  the line and was not cited. **These are the kind of thing the validator
  cannot see, as designed.**

### F2.6.3 — Cost, tokens and latency

**Confidence: measured.**

| | This call | 1.8a (daily closes) | 1.7 |
|---|---|---|---|
| Input tokens | 98,438 | 94,716 | 185,168 |
| Output tokens | 7,628, of which 5,858 are reasoning | 7,484 | 7,725–9,087 |
| Cost | **$0.273156** | $0.2643 | $0.448–0.461 |
| Latency, the call alone | **78.6 s** | 60 s | 62–75 s |

- **The input is 3,722 tokens more than 1.8a.** That is the per-seat brief and
  the shared contract, about 10.4 KB of text.
- **Latency is a little past 1.7's upper end.** The process took 82 s from
  start to result.
- **The reply's own usage block now states its cost.** `usage.cost` 0.273156
  and `cost_details.upstream_inference_cost` 0.273156 equal our listed-price
  estimate to the digit: prompt $0.196876 plus completions $0.07628. That is
  provider evidence per request, in the reply, which F0.6.4 found `/v1/usage`
  does not give. `buyer_cost_micro` (68,289) is still unexplained.
- **Hidden reasoning, measured.** `completion_tokens_details.reasoning_tokens`
  is 5,858 of 7,628 (77%). F1.7.5 inferred 37–50% of billed output absent from
  the reply; here it is counted, and higher.
- **The settled-window cross-check is owed.** It can run once the window has
  been closed for `usage_settle_seconds` (3,600 s) after 15:40Z.

### F2.6.4 — The judgement: a real view, done mechanically

**Confidence: a judgement, on one call.**
- **It is not the feared failure,** a report that validates and says nothing.
  - It names the five divergences the snapshot flags.
  - For each, it decides which of the three prices is out of line, using
    arithmetic that is right.
  - It gives each a testable "wrong if" for the reopen.
  - A risk agent could act on it. So could a buyer, as a triage of the weekend's
    divergences.
- **It reads as a method applied, not a view formed.**
  - The method is the brief's own sentence: "when two of the three prices
    agree, the third is usually the one that is wrong."
  - It reaches exactly the hand-written example's five calls, all low or
    medium.
- **It lacks what made the hand-written one worth reading:**
  - AMD's corroborator sits barely over the $1M line, a reason for less
    confidence;
  - a Treasury-bill fund cannot fall 1.2% over a weekend.
- **It adds one unsupported guess** (SGOV "likely thin") and one invented
  description ("venue AMM").
- **It writes numbers as a machine would,** to 16 digits.
- **Worth $0.25?** As one of four seats feeding a decision, yes. On its own as
  the product, it is thin.
- **Not changed here, by instruction.** The brief is 2.3's; this is the
  measurement.

### What 2.6 changes

| Change | Where |
|---|---|
| The bps rule refuses correct computed figures. Check a bps figure only when its line cites a `_bps` field, with a test. **Done after 2.6** (`ea39fd6`) | 2.2, `agents/schema.py` |
| The unassigned agent `0x…` reads to a model as an address to fill in. It needs a token that cannot be mistaken for one, or a real agent address. **Done after 2.6: the token is now `unassigned`** (`5d6a3dd`) | 2.3's brief, the runner's `UNASSIGNED_AGENT`, 2.0's choice |
| The reply states its own cost per request | 2.5: `bankr_llm.cost` could use it, and the estimate label could narrow |
| Reasoning tokens are counted in the usage block | F1.7.5, the output cap |
| The settled `/v1/usage` cross-check for this call | owed, after 16:40Z |

### Method limitations

- **One call, one seat, on the weekend capture.** Identical calls differ by
  about 18% (F1.7.1), so another run could differ.
- **The re-validation was run in a scratch copy** and is not the committed
  validator's verdict.
- **Spent:** $0.273156 by the reply's own statement and by our estimate.


---

## 2.6, continued — The other three seats, on the same snapshot

**Date:** 2026-09-19, sent 15:58:33Z. **Method:** `python -m fund.agents.runner
--seats price-trend,cross-asset-macro,execution-quality --retries 0 --confirm`
on the same capture as §2.6, snapshot `253315c0…`, one call per seat. It ran
after the validator and placeholder fixes (`ea39fd6`, `5d6a3dd`). **Keys:**
`probes/keymap.py` measured `BANKR_LLM_KEY` exactly as in §2.6, refused by the
Wallet API and the Agent API. The balance read $15.517951, which is the §2.6
figure less that call's own stated cost.

**Captures:**
- `fixtures/live/cycles/20260919T155833Z/`, gitignored;
- the report store `fixtures/live/reports/`, gitignored. Price-trend is report
  `9398838…`, execution-quality `1b9f7a7…`, and §2.6's price-integrity
  `569d406…`. Each reads back byte-identical to its recorded reply.

| Seat | Validated | Cost | Latency | Tokens in / out (reasoning) | What it said |
|---|---|---|---|---|---|
| price-integrity (§2.6) | refused as run; since the fixes, the header only | $0.273156 | 78.6 s | 98,438 / 7,628 (5,858) | Of the five weekend divergences, AMD's and MSTR's marks are stale, and GeckoTerminal is the outlier for AMZN, GOOGL and SGOV |
| price-trend | **refused:** call shape, asset, figure | $0.273142 | 83.3 s | 98,356 / 7,643 (5,799) | Buy AMD (a breakout), META (high: a clean uptrend) and GME; hold NVDA (a range) and USO (stalled); sell AMZN (lower highs) |
| cross-asset-macro | **no report:** the gateway answered HTTP 504 "Gateway Time-out" | unknown: no usage block | 113.3 s | — | — |
| execution-quality | **accepted** | $0.249594 | 58.2 s | 98,412 / 5,277 (4,434) | Trading is cheap everywhere (no fee, impact at most about 21 bps, a uniform 5% slippage bound). Caution on MSTR: a buyer pays 132 bps over the price it would be booked at |

### The price-trend report, unedited

```
REPORT price-trend unassigned 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The market is shut (`block.closed_sessions` lists `us_equities_24/5`), so every mark below is each feed's last round before the weekend close while GeckoTerminal and the venue keep pricing through it — that shows up as the closed-session divergence findings on AMD, AMZN, GOOGL, MSTR and SGOV. None of that changes what the 30 closes say about direction; it just means today's mark is a Friday print, not a live one. Most of the tradeable book is either range-bound (NVDA, SPY, QQQ, PLTR) or too choppy this month to call (COIN, CRCL, MSTR, TSLA), so I'm limiting calls to the names with a clean signal.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc buy medium
AMD has broken out of its August range in the last week, up double digits in four sessions on top of an already-positive month.
- 468.2354 close on 2026-08-20 [timeline 2026-08-20]
- 494.73 close on 2026-09-14, then 559.42445 on 2026-09-18, +13.1% in four sessions [timeline 2026-09-14, mark.price_usd]
- +19.5% over the 30-day window [timeline 2026-08-20, mark.price_usd]
Wrong if: it closes back below 494.73, the pre-breakout level, erasing the acceleration.

CALL META 0xc0d6457c15e6ba2ebb19ea114ea508d14c1af2e buy high
Meta has climbed almost every day this month, a textbook uptrend with only a shallow pullback at the very end.
- 544.70535 close on 2026-08-20 vs 666.7615 now, +22.4% [timeline 2026-08-20, mark.price_usd]
- peaked at 682.42815 on 2026-09-17 before the latest -2.3% pullback [timeline 2026-09-17, mark.price_usd]
- higher low at 646.9696 on 2026-09-11 [timeline 2026-09-11]
Wrong if: it closes below 646.9696, the most recent swing low, breaking the sequence of higher lows.

CALL GME 0x27c71df6a64fb476468edf256cf72c038bab5b67 buy medium
GameStop has risen in an almost unbroken line for a month, +25% with no material give-back.
- 18.015 close on 2026-08-20 vs 22.55175 now, +25.2% [timeline 2026-08-20, mark.price_usd]
- low of 17.925 on 2026-08-28, high of 22.713 on 2026-09-17 [timeline 2026-08-28, timeline 2026-09-17]
- steady day-over-day gains since 2026-09-08 (18.925 to 22.68305 by 2026-09-17) [timeline 2026-09-08, timeline 2026-09-17]
Wrong if: it closes below 19.235, the early-September level, giving back most of the move.

CALL NVDA 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec hold low
Nvidia is still range-bound for the month, sitting about two-thirds up a 208-230 band after bouncing off a mid-September low.
- 207.91 low on 2026-08-24, 230.23665 high on 2026-09-04 [timeline 2026-08-24, timeline 2026-09-04]
- 222.44729849 now, roughly 65% up the range [mark.price_usd]
- bounced from 211.92474816 on 2026-09-15 [timeline 2026-09-15]
Wrong if: it closes above 230.23665, a breakout and a buy, or below 207.91, where the range breaks and it becomes a sell.

CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 sell low
Amazon has made a run of lower highs since late August and has not reclaimed its prior levels despite a small bounce.
- 266.085 high on 2026-08-28 vs 253.863 now, -4.6% [timeline 2026-08-28, mark.price_usd]
- low of 245.74465 on 2026-09-16 before the bounce [timeline 2026-09-16]
- 259.03 on 2026-09-03 is the most recent swing high, still unreclaimed [timeline 2026-09-03]
Wrong if: it closes above 259.03, the recent swing high, reversing the pattern of lower highs.

CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 hold medium
USO's month-long climb has stalled into a plateau over the last week and a half rather than continuing to make new highs.
- 126.33345 low on 2026-08-25 vs 161.405 high on 2026-09-15, +27.8% [timeline 2026-08-25, timeline 2026-09-15]
- 154.54265 now, -4.3% off that high and roughly flat since 2026-09-10 (158.4) [mark.price_usd, timeline 2026-09-10]
- last six closes have ranged only 153.38-161.405 [timeline 2026-09-15, timeline 2026-09-18]
Wrong if: it closes above 161.405, a continuation buy, or below 141.995 (2026-09-03 level), breaking the uptrend into a sell.
```

### The execution-quality report, unedited

```
REPORT execution-quality unassigned 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The block's closed_sessions list is non-empty: every stock mark here is the feed's last round before the US equities close, while the venue itself keeps quoting live. That means the "gap between price paid and mark booked" figure I track is inflated by session drift for many names, not by an execution problem per se. Setting that aside, the mechanics of a trade at the quoted $25 size are cheap and clean across the board: fee_bps is 0 for every tradeable asset, price/swap impact sits in single digits to the low twenties of bps (a couple even show negative impact, i.e. price improvement), the venue's slippage allowance is a uniform 500 bps on every quote, and every quote used here is under 20 seconds old at built_at. Given that, the one place actual cost stands out is not fee or impact but the paid-vs-booked gap: buying MSTR at the quoted venue price and booking it at the mark would cost roughly 132 bps immediately, an order of magnitude past the ~0-25 bps gap seen on the rest of the tradeable list (AAPL -20bps, GOOGL -12bps, SPY +13bps, META +23bps, TSLA +7bps). Everything else tradeable looks unremarkable for cost purposes and I leave it uncalled.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution medium
A buy fills at the venue's price of 154.65896270001573 but would book at the mark of 152.643, a gap of about 132 bps against the buyer before any impact or fee is counted — the largest such gap among tradeable names this snapshot, even though the trade mechanics themselves (fee, impact, quote freshness) look fine.
- venue_price_usd 154.65896270001573 vs mark.price_usd 152.643, a ~132 bps gap [quote.venue_price_usd, mark.price_usd]
- fee_bps 0, swap_impact_bps 16, both unremarkable on their own [quote.fee_bps, quote.swap_impact_bps]
- quote age 0.725s, well within the 60s tradeability window [quote.age_s]
- slippage_bps 500 (5%) is the venue's standard allowance, not unusual to this asset [quote.slippage_bps]
Wrong if: the venue_price_usd and mark.price_usd converge to within a few tens of bps on a later quote/mark pull.
```

### F2.6.5 — Price-trend was refused for errors that are the model's

**Confidence: measured.** Unlike §2.6's refusals, all three are real errors:
- **`call-shape`, META.** It wrote `0xc0d6457c15e6ba2ebb19ea114ea508d14c1af2e`: 39
  hex digits, right for its first 8, then invented. The real address is
  `0xc0d6457c16cc70d6790dd43521c899c87ce02f35`.
- **`asset`, GME.** It wrote `0x27c71df6…5b67`, which is GME's
  `mark.feed_proxy`: the Chainlink feed's address, not the token's
  (`0x1b0e319c…153e`). **Two addresses in one entry, and the model took the
  wrong one.** Identity rests on the address (PLAN §2 invariant 8), and the
  validator refused it.
- **`figure`, GME.** It wrote "18.925 to 22.68305 by 2026-09-17". 22.68305 is
  GME's close on 2026-09-18, not the 17th (22.713). With both addresses put
  right, as a diagnostic only, this is still refused. It is a mis-dated figure,
  caught.

**Its other figures check out,** including computed ones. AMD is +13.1% in
four sessions, USO +27.8% from low to high, AMZN −4.6% off its high, and the
USO six-close range is 153.38 to 161.405.

### F2.6.6 — Price-trend's NVDA call is the brief's own example, so it cannot be judged

**Confidence: measured.** The shared brief, `analyst.v1.md`, carries the
approved NVDA call as its example and labels it "From an earlier snapshot". It
was written against *this* snapshot. The model's NVDA call repeats it: the
208–230 range, "about two-thirds up", the bounce off 211.92, and the same
"Wrong if" nearly word for word.

**The label is false for this capture,** and the test you set for price-trend
("can you tell what it thinks about NVDA") is contaminated here. Its other five
calls are its own:
- AMD, META and AMZN converge with the hand-written report, which it never saw;
- GME and USO are new.

The brief is 2.3's, and it is not changed here.

### F2.6.7 — Cross-asset-macro timed out at the gateway, not at our transport

**Confidence: measured, once.** The gateway returned HTTP 504 "Gateway
Time-out", an HTML page, after 113.3 s. Our transport allows 600 s, and the
other calls took 58 to 83 s.
- **What is inferred,** from one observation: the gateway has an upstream
  limit near 110 to 120 s. The seat whose question asks for correlations
  across every series likely reasoned longest.
- **Why it was not retried.** A refusal from the gateway is never retried
  (2.4), and the rule here was one call per seat.
- **Whether it was billed is unknown.** No usage block came back. The settled
  `/v1/usage` window will show it, by comparing its request count with our
  recorded calls.
- **If the limit is real, 600 s is moot:** a reply longer than about 113 s never
  arrives.

### F2.6.8 — Are the seats different views? Three of four, yes; the fourth did not answer

**Confidence: a judgement, on three reports and one missing.**
- **Price-trend** gives direction, from the closes. **Price-integrity** says
  which of three prices is wrong. **Execution-quality** gives the cost of a
  trade now. **Different questions, different content.** No two reports are the
  same report.
- **One overlap, on one fact.** Both condition seats caution MSTR on its 132 bps
  gap between venue and mark. Price-integrity reads it as a stale mark;
  execution-quality as a cost to a buyer. The aggregator takes the largest
  caution, so it is not counted twice, but a reader meets it twice. Each seat
  also adds what the other lacks: GeckoTerminal's triangulation, and fee,
  impact and slippage.
- **The seat most likely to overlap with price-trend is the one with no
  report.** Cross-asset-macro is the other direction seat. Price-trend
  called USO "hold" on a stalled trend; the hand-written cross-asset example
  called it "buy" as a diversifier. That disagreement would have been the test,
  and it is untested.
- **So:** not four seats asking one question, as far as three reports can show.
  The claim is not proven for four.

### F2.6.9 — Cost, and what the reply says about itself

**Confidence: measured.**
- **Every reply that arrived states its cost in `usage.cost`,** and it equals
  our listed-price estimate to the digit ($0.273142, $0.249594).
- **Hidden reasoning** is 76% (price-trend) and 84% (execution-quality) of
  billed output.
- **Spent here:** $0.522736 on the two replies, and an unknown amount, possibly
  none, on the 504.


## 3.8 — The exit run: four seats live, one call each, and the decision

**Run 2026-09-19 at 17:13:51Z,** on the committed capture `253315c0…`, the
snapshot every earlier call used. Settings:
- `BANKR_LLM_KEY`, shared, measured first by `probes/keymap.py`: gateway on,
  Agent API off, refused by the Wallet API;
- `--retries 0`, so one call per seat;
- width 4, so all four ran at once.

Before the run, the shared brief's example was relabelled, not replaced. Its
old label, "From an earlier snapshot", was false. The operator's instruction was
one call per seat, no brief iterated, and a weak report is a finding.

The decision then ran on the cycle with live quotes and a live risk call
available: `python -m fund.run.decide --cycle … --live-quotes --confirm`. It
spent nothing more: with no accepted report there was no order, so no quote and
no risk call.

The recording is `fixtures/cycles/20260919T171351Z/`:
- the cycle as the runner wrote it;
- each stored reply by its id;
- the decision's files and the signed envelope.

| Seat | Result | Refusals | Cost | Time | Tokens in | Tokens out | Reasoning |
|---|---|---|---|---|---|---|---|
| price-integrity | refused | 4 | $0.265618 | 71.9 s | 98,469 | 6,868 | 75% |
| price-trend | refused | 1 | $0.260564 | 76.5 s | 98,387 | 6,379 | 72% |
| execution-quality | refused | 5 | $0.288326 | 103.6 s | 98,443 | 9,144 | 87% |
| cross-asset-macro | refused | 7 | $0.273198 | 89.4 s | 98,444 | 7,631 | 71% |

**Spent:** $1.087706 by the replies' own `usage.cost`, which equals our
estimate to the digit for each.

### The price-trend report, unedited

```
REPORT price-trend unassigned 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The US equities session is shut (block.closed_sessions: us_equities_24/5), so every mark below is the feed's last pre-close round, not a live print. That doesn't change what the 30 daily closes say, since venue/GeckoTerminal action after the close isn't part of my series. Reading only the closes plus the latest round, five tradeable names show a real month-long climb (three of them breaking out in just the last week), one is flat-to-choppy in range, and I found no tradeable name showing a clean downtrend worth calling. I limit calls to the clearest six.

CALL AAPL 0xaf3d76f1834a1d425780943c99ea8a608f8a93f9 buy medium
Apple has climbed almost every week for a month and just broke above its prior high to a fresh 30-day peak.
- 310.85 close on 2026-08-20 vs. 335.38 mark, +7.9% [timeline 2026-08-20, mark.price_usd]
- prior high 328.80 (2026-09-03) cleared by 337.06 on 2026-09-17 [timeline 2026-09-03, timeline 2026-09-17]
- pulled back to 320.52 on 2026-09-04 before resuming up [timeline 2026-09-04]
Wrong if: it closes back below 320.52, the last pullback low, undoing the breakout.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc buy medium
AMD is up almost 20% over the month, and over half of that came in the last four sessions alone.
- 468.24 close on 2026-08-20 vs. 559.42 mark, +19.5% [timeline 2026-08-20, mark.price_usd]
- 494.73 close on 2026-09-14 to 559.42 latest, +13.1% in four sessions [timeline 2026-09-14, mark.price_usd]
Wrong if: it closes below 494.73, the base this week's rally launched from.

CALL GME 0x1b0e319c6a659f002271b69db8a7df2f911c153e buy medium
GameStop's closes form the cleanest staircase in the book: nearly every day higher for three weeks straight.
- 18.02 close on 2026-08-20 vs. 22.55 mark, +25.2% [timeline 2026-08-20, mark.price_usd]
- last local low 20.45 on 2026-09-10, never revisited since [timeline 2026-09-10]
Wrong if: it closes below 20.45, breaking the run of higher lows.

CALL META 0xc0d6457c16cc70d6790dd43521c899c87ce02f35 buy medium
Meta rose in almost a straight line from late August into mid-September, +22% for the month, though the mark sits 2.3% off this week's peak.
- 544.71 close on 2026-08-20 vs. 666.76 mark, +22.4% [timeline 2026-08-20, mark.price_usd]
- peak 682.43 on 2026-09-17, mark now 666.76, -2.3% off the top [timeline 2026-09-17, mark.price_usd]
- last higher-low 646.97 on 2026-09-11 [timeline 2026-09-11]
Wrong if: it closes below 646.97, turning the month's climb into a reversal.

CALL INTC 0xc72b96e0e48ecd4dc75e1e45396e26300bc39681 buy medium
Intel is up 18% for the month and just broke past both its early-September high and its mid-month pullback low to a fresh peak.
- 92.43 close on 2026-08-20 vs. 109.05 mark, +18.0% [timeline 2026-08-20, mark.price_usd]
- prior high 105.95 on 2026-09-09, cleared to 109.20-109.05 on 2026-09-17/18 [timeline 2026-09-09, timeline 2026-09-17]
- pullback low 97.49 on 2026-09-14 [timeline 2026-09-14]
Wrong if: it closes below 97.49, the pullback that this breakout needs to hold above.

CALL SPCX 0x4a0e65a3eccec6dbe60ae065f2e7bb85fae35eea buy medium
SpaceX has climbed steadily for a month with only shallow pullbacks, +14% top to bottom.
- 134.05 close on 2026-08-20 vs. 152.82 mark, +14.0% [timeline 2026-08-20, mark.price_usd]
- last pullback low 143.88 on 2026-09-15 [timeline 2026-09-15]
Wrong if: it closes below 143.88, breaking the sequence of higher lows.

MSTR jumped 16% in a single session (132.19 to 153.44, then 152.64 latest) [timeline 2026-09-17, timeline 2026-09-18, mark.price_usd] after three weeks of range-bound chop between roughly 123 and 144 — a week's spike, not a month's trend, so I make no call there. AMZN, COIN, MSFT, MU, PLTR, QQQ, SPY and TSLA are all range-bound or too choppy over the 30 closes to support a directional call.
```

### The cross-asset-macro report, unedited

```
REPORT cross-asset-macro unassigned 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The market is shut (block.closed_sessions lists us_equities_24/5), so every stock mark below is the last Chainlink round before the close while GeckoTerminal pools kept trading; several tickers (AMD, AMZN, GOOGL, MSTR, SGOV) already show closed-session divergence findings against that live pool price. That freezes tonight's exact level, but the 30-day daily-close series is unaffected by the close and is what this seat reads. Two clusters stand out. First, a chip/semis group (NVDA, AMD, MU, INTC) traced the same wave shape all month: a trough around 8/24, a peak near 9/3-9/4, a second trough mid-September (9/14-9/15), then a sharp jump into 9/17-9/18 — the timing lines up even though the amplitudes differ hugely (NVDA +2.6% vs AMD +19.5%, INTC +18.0%, MU +3.9%). Second, SPY and QQQ, the index holdings, moved far less than their own largest constituents: SPY is flat over 30 days (-0.09%) and QQQ only +1.4%, while several of the book's individual megacap and chip holdings ran 10-25% higher — the indices are diluted mirrors of names the book already owns directly. Away from equities, SGOV (bills) barely moved (+0.22%) and did not track any of the equity swings, and USO (oil) rose steadily and mostly independently of the SPY chop, including a divergence in mid-September when SPY fell into 9/16 while USO was still near its highs. Confidence throughout is modest: twenty-odd daily closes are thin for correlation claims, and several instruments here are frozen marks in a closed session.

CALL SPY 0x117cc2133c37b721f49de2a7a74833232b3b4c0c hold medium
SPY is flat over the window while several of the book's own megacap holdings (AAPL, META, AMD, INTC) ran far ahead of it; SPY is a diluted echo of exposure the book already carries directly, so adding it doubles that bet rather than diversifying.
- SPY +(-0.09)% over 30 days: 762.21 to 761.55079369 [timeline 2026-08-20, timeline 2026-09-18]
- SPY's own low of 751.28 on 9/16 vs its 771.19 high on 9/3, a 2.6% range while book names moved 10-25% [timeline 2026-09-16, timeline 2026-09-03]
Wrong if: SPY starts moving with a magnitude the book's individual names aren't already producing, i.e. it decouples upward from its constituents rather than trailing them.

CALL QQQ 0xd5f3879160bc7c32ebb4dc785f8a4f505888de68 hold medium
QQQ's +1.4% over 30 days is a muted version of the far larger moves already sitting in the book's own tech names (META +22%, AMD +19.5%, INTC +18%); it does not add a distinct risk, it re-buys a slice of what is already held.
- QQQ +1.4%: 710.195 to 720.3651 [timeline 2026-08-20, timeline 2026-09-18]
- META over the same window: 544.70535 to 666.7615, +22.4% [timeline 2026-08-20, timeline 2026-09-18]
Wrong if: QQQ's daily moves stop tracking its megacap tech constituents and start showing an independent pattern.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc hold low
AMD, MU and INTC traced the same trough-peak-trough-spike shape all month (troughs near 8/24 and 9/14-15, peaks near 9/3-4 and 9/17-18); AMD is the loudest voice in a chip-beta cluster the book already holds through NVDA, INTC and MU, so it looks like the same bet run larger rather than a new one.
- AMD +19.5% over 30 days: 468.2354 to 559.42445 [timeline 2026-08-20, timeline 2026-09-18]
- INTC's matching shape, +18.0% over the same window: 92.425 to 109.05 [timeline 2026-08-20, timeline 2026-09-18]
- NVDA's smaller but same-timed wave, +2.6%: 216.7739 to 222.44729849 [timeline 2026-08-20, timeline 2026-09-18]
Wrong if: AMD's path clearly detaches from INTC/MU/NVDA's timing (its own troughs and peaks stop lining up with theirs), which would make it a distinct bet worth adding rather than doubling.

CALL SGOV 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 buy medium
SGOV moved almost nothing over 30 days and shows no relation to the equity swings elsewhere in the book (it kept climbing gently through the mid-September equity dip); this is the one instrument that plainly diversifies rather than doubling an existing bet.
- SGOV +0.22% over 30 days: 100.88489612 to 101.10821255 [timeline 2026-08-20, timeline 2026-09-18]
- SPY fell to 751.28 on 9/16 while SGOV was still rising, at 101.04790643 that same day [timeline 2026-09-16]
Wrong if: SGOV's daily closes start moving with the size and direction of the equity book, which would erase the diversification case.

CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 buy low
USO climbed steadily and largely apart from the equity chop: SPY fell into its 9/16 low while USO was still near its 9/15 high, and USO's 30-day gain (+14.5%) has no equivalent shape in SPY or QQQ. It reads as a source of return with its own driver, which is what a diversifier should look like.
- USO +14.5% over 30 days: 134.96975 to 154.54265 [timeline 2026-08-20, timeline 2026-09-18]
- USO near its high, 161.405, on 9/15 while SPY was falling toward 751.28 on 9/16 [timeline 2026-09-15, timeline 2026-09-16]
Wrong if: USO's daily path starts moving in lockstep with SPY/QQQ's swings rather than on its own schedule.
```

### The execution-quality report, unedited

```
REPORT execution-quality unassigned 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The market is shut (`block.closed_sessions` lists us_equities_24/5), so every mark is frozen at its last pre-close round while the venue keeps quoting live. Across all 20 tradeable names the mechanics of a $25 buy are close to free: `fee_bps` is 0 everywhere, `swap_impact_bps` tops out in the low twenties (well inside the 50 bps gate that made ASML, DELL, IONQ, NBIS, RGTI, CLSK etc. untradeable), the venue's allowed `slippage_bps` is a uniform, generous 500, and every quote is under 20 seconds old. Fee and impact are simply not where the cost is right now. The real story is the gap between the venue price a buy actually fills at and the mark it gets booked against: for most names (SPY, TSLA, QQQ, CRCL, GOOGL, AMZN, SGOV, COIN, GME, NVDA, SPCX) that gap sits inside ±25 bps, which is noise. Two names stand well outside that band and are worth flagging on cost grounds alone, independent of which way the stock is moving or whether the mark itself is trustworthy.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution medium
The venue would fill this buy at a clear premium to the price it books at: paying 154.65896270001573 [quote.venue_price_usd] against a mark of 152.643 [mark.price_usd] is +132 bps, ten times the size of the swap impact the quote itself reports.
- venue_price_usd 154.65896270001573, mark.price_usd 152.643 → +132.1 bps gap [quote.venue_price_usd, mark.price_usd]
- swap_impact_bps 16, fee_bps 0, both look trivial next to the gap [swap_impact_bps, fee_bps]
- quote age 0.725s, so this isn't a stale-quote artifact [quote.age_s]
Wrong if: the venue_price_usd/mark.price_usd gap narrows back under ~30 bps on a fresh quote.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc proceed low
AMD's closed-session divergence is flagged elsewhere in the snapshot, which could read as a costly name to trade, but on pure execution terms it is not: fee is 0, swap impact is only 10 bps, and the fill (551.9120935475604) is actually below the mark (559.42445) it would book at, a -134 bps gap that favors the buyer rather than costing them.
- venue_price_usd 551.9120935475604 vs mark.price_usd 559.42445 → -134.3 bps [quote.venue_price_usd, mark.price_usd]
- swap_impact_bps 10, fee_bps 0, slippage_bps allowance 500 [swap_impact_bps, fee_bps, slippage_bps]
- quote age 11.126s [quote.age_s]
Wrong if: a refreshed quote shows the venue price rising above the mark, turning this favorable gap into a paid premium.

NO CALLS beyond these two: every other tradeable name's fee/impact is negligible and its venue-vs-mark gap sits under roughly 60 bps, not large enough to be the story on its own.
```

### The price-integrity report, unedited

```
REPORT price-integrity unassigned 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The US equities session is closed (`block.closed_sessions: ["us_equities_24/5"]`), so every stock's Chainlink mark is frozen at its last pre-close round while GeckoTerminal and the venue quote keep trading. That means most of the closed-session divergences the snapshot flags are expected and don't by themselves say the mark is wrong — what tells the story is which two of the three prices agree. Five tradeable assets carry an explicit closed-session-divergence finding (AMD, AMZN, GOOGL, MSTR, SGOV); for each I checked whether the mark or the corroborator is the odd one out against the venue quote, which is the one price still being made live.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc caution medium
The mark sits well above both the other two reads, which cluster together, so the frozen Chainlink round looks like the stale side of this divergence, not GeckoTerminal.
- mark 559.42445 vs corroboration 553.5582086607, a 105.98 bps gap [mark.price_usd, corroboration.price_usd, corroboration.divergence_bps]
- venue 551.9120935475604 is only ~30 bps from GeckoTerminal's 553.5582086607, much tighter than either is to the mark [quote.venue_price_usd, corroboration.price_usd]
Wrong if: the venue price rises to meet the mark rather than staying near GeckoTerminal.

CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 proceed medium
The finding reads -450.32 bps mark-vs-GeckoTerminal, but the venue quote — which trades live through the close — sits close to the mark, so the mark holds up; GeckoTerminal looks like the outlier here, not the book price.
- mark 253.863 vs venue 253.28085544501803, roughly 23 bps apart [mark.price_usd, quote.venue_price_usd]
- corroboration 265.8339854153 is the away price, -450.32 bps from mark on $2,101,924.28 of 24h volume [corroboration.price_usd, corroboration.divergence_bps, corroboration.volume_24h_usd]
Wrong if: the venue price drifts toward GeckoTerminal's 265.83, which would show both mark and venue were stale together.

CALL GOOGL 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 proceed medium
Same shape as AMZN: mark and venue agree closely while GeckoTerminal is the one that has moved away, so the -132.33 bps finding is not the mark's fault.
- mark 350.47135177 vs venue 350.04082044804966, about 12 bps apart [mark.price_usd, quote.venue_price_usd]
- corroboration 355.171284689 is -132.33 bps from mark on $11,953,068.67 of 24h volume [corroboration.price_usd, corroboration.divergence_bps, corroboration.volume_24h_usd]
Wrong if: the venue price converges toward GeckoTerminal's 355.17 instead of the mark.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution medium
Here the mark is the odd one out again: venue and GeckoTerminal sit closer to each other than either does to the frozen mark, and the mark's own freshness note shows it updated right at the close (only ~1,414s of open-session time), consistent with it lagging a move that continued after close.
- mark 152.643 vs corroboration 155.5016463786, -183.84 bps [mark.price_usd, corroboration.price_usd, corroboration.divergence_bps]
- venue 154.65896270001573 is only ~54 bps from GeckoTerminal, versus ~132-187 bps from the mark [quote.venue_price_usd, corroboration.price_usd, mark.price_usd]
Wrong if: the venue price falls back to meet the mark near 152.6 rather than tracking GeckoTerminal.

CALL SGOV 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 proceed high
SGOV is a cash-like Treasury-bill fund that should barely move; mark and venue agree within a quarter of a percent while GeckoTerminal is off by over a point, so the +124.7 bps finding is GeckoTerminal's problem, not the mark's.
- mark 101.10821255 vs venue 100.88197839075325, about 22 bps apart [mark.price_usd, quote.venue_price_usd]
- corroboration 99.8629967858 is 124.7 bps from mark on $2,349,606.90 of 24h volume [corroboration.price_usd, corroboration.divergence_bps, corroboration.volume_24h_usd]
Wrong if: the venue price drops toward GeckoTerminal's 99.86, which would make GeckoTerminal the one that was right.
```

### F3.8.1 — All four were refused, and none invented a figure

**Confidence: measured.** Every refusal is about where a figure is cited, not
whether it is true. Each refused figure was checked against the capture, and
each is a real value of a real field.

| Seat | Refusal | Whose |
|---|---|---|
| price-integrity | `924.28`, `068.67`, `606.90`: volumes written with thousands separators, `$2,101,924.28` | **ours** (F3.8.2) |
| price-integrity | `"us_equities_24/5"`: a JSON value in brackets inside a code span, in prose | **ours** (F3.8.2) |
| execution-quality | `[swap_impact_bps, fee_bps]`, `[slippage_bps]` without `quote.`, five times | the model's, by the format's rule |
| price-trend | `109.05`, INTC's mark, on a line citing only the 9 and 17 September closes | the model's |
| cross-asset-macro | six figures of another asset cited without its symbol: META's under QQQ, INTC's and NVDA's under AMD, SPY's under SGOV and USO. And USO's mark cited as its 18 September close | the model's |
| cross-asset-macro | `-0.09`, written `+(-0.09)%`, read as a plain figure | **ours**, in part (F3.8.2) |

### F3.8.2 — Two validator defects, and neither changes the quorum

**Confidence: measured, on this run's replies.**
- **Thousands separators.** `$2,101,924.28` is read as the plain figure
  `924.28` and refused against the field's 2,101,924.2837. `$N.NNM` is handled,
  and a comma is not. Three correct figures from price-integrity were refused.
- **Brackets that are not citations.** Every bracketed span is read as a
  citation. That includes one inside a code span in the prose, and it includes
  a percentage whose sign sits in parentheses.
- **Fixed, they would rescue price-integrity alone.** Its only refusals are
  these. That makes one accepted report of four, still below the quorum of 3.
  The other three seats' refusals stand under the format as approved.
- **Not changed.** The validator stays as it was at the call; the fixes are the
  operator's call.

### F3.8.3 — Citing another asset is where the models fail, and it is the cross-asset seat's whole job

**Confidence: measured, once per seat.** The format says a field of another
asset is cited with its symbol, as `[SPY mark.price_usd]`.
- **cross-asset-macro** compares assets in almost every line, and left the
  symbol out six times.
- **execution-quality** wrote field names as the snapshot's `quote` block
  names them, but without the block's name.
- **At 2.6** price-trend's refusals were identity errors: an invented address
  and a feed address taken for a token. This run's are all citation paths. No
  address was wrong.

### F3.8.4 — No quorum, so no rebalance, no orders, no risk call, and no veto

**Confidence: measured.** The fund's real decision for this cycle:
- `0 seat(s) reported, below the quorum of 3`;
- no rebalance;
- no order.

It is signed with the fund's key (`1c232435…`), and its decision id is
`2c9c1a79ae3438fb32b51b337f5fddf01948a3a1fe66666ea03ee8e205b6cc74`.
- **The risk agent was not called.** 3.5 makes no call on a plan with no
  orders. So no real model has yet read `risk.v1.md`.
- **The signed record does not mention the four refused replies.**
  - 3.7's row says the record carries the sha256 of every report.
  - `run/decide.py` offers the record only the accepted reports of a cycle.
  - So the record says why nothing happened (quorum), but not which replies
    were refused or why. They are in the fixture and the report store, not in
    what was signed. Owed.

### F3.8.5 — Cross-asset-macro answered this time

**Confidence: measured, once.** It replied in 89.4 s. At 2.6 it got a 504 at
113.3 s. Execution-quality took 103.6 s and returned. Four calls on one key at
once were all served. So a gateway limit near 113 s is neither shown nor ruled
out: every reply this time came in under it.

### F3.8.6 — The relabelled example: price-trend made no NVDA call

**Confidence: one observation.** Under the old label, price-trend repeated the
brief's NVDA example almost word for word (F2.6.6). Under the new one, it made
no NVDA call at all. One run cannot tell the label's effect from a call's
ordinary variation.

### F3.8.7 — What the four say: the direction seats disagree, and the condition seats agree with the hand-written example

**Confidence: a judgement on four reports.**
- **price-trend:** six buys at medium: AAPL, AMD, GME, META, INTC and SPCX. It
  makes no sell call, and passes on MSTR as "a week's spike, not a month's
  trend".
- **cross-asset-macro:**
  - hold SPY and QQQ, as diluted echoes of names the book would own;
  - hold AMD low, as the loudest voice in a chip cluster;
  - buy SGOV medium and USO low, as diversifiers.

  Its reasoning is about co-movement, not trend. **It disagrees with
  price-trend on AMD,** buy against hold, which is the test F2.6.8 left open.
- **execution-quality:** caution MSTR, where a buy pays 132 bps over the mark
  it books at, and proceed AMD, where the fill is 134 bps below the mark.
- **price-integrity:** the same five calls as the hand-written example:
  - caution AMD and MSTR, whose marks are stale;
  - proceed AMZN, GOOGL and SGOV, where GeckoTerminal is the outlier.

  Its MSTR call is medium where the example said high.

### F3.8.8 — If all four had been accepted: a hypothetical, unsigned

**Confidence: computed offline from the four replies' own calls.** This is not
the fund's decision, and it is not in the record.
- **Eight buys, $168.75 of the $200 paper book:** GME, SPCX, SGOV, AAPL, META
  and INTC at $25 each; USO $12.50; AMD $6.25.
- **AMD** is cut from $25 to $6.25 by two things:
  - the direction seats' disagreement, (0.5 + 0) / 2;
  - price-integrity's medium caution.
- **MSTR gets no order,** because no direction seat calls it. Two cautions on
  it therefore touch nothing.
- **The fixed gates would very likely all pass.** Live quotes are fresh, impact
  is small, and cash of $31.25 is above the floor. So a veto could come only
  from the risk agent's own judgement. AMD's stale mark, which price-integrity
  names, is the likeliest place for one.

### F3.8.9 — The credit balance, before the run

**Confidence: the balance is measured; what it implies is inferred.**
`/v1/credits` read $14.678389 before this run. The last reading was $15.517951
before 2.6's three calls. Those calls' replies cost $0.522736, so $14.995215
was expected if the 504 was free. The $0.316826 difference is consistent with
the 504 having been billed, but it is a before-and-after delta, which the
operator ruled out as the check (F0.9.2). The settled `/v1/usage` window is
still owed.

### What would have to be true for a veto

1. **A quorum.** At least three accepted reports on one snapshot. Today that
   needs one of:
   - the models citing other assets by symbol and fields by full path;
   - the operator loosening what counts as a valid citation;
   - more seats re-run, which this stop forbade.

   Fixing F3.8.2's two defects is needed in any case, but it rescues only
   price-integrity.
2. **An order the evidence argues against.** In a closed session no fixed gate
   fires on a tradeable name (SIMPLIFICATION Q2). The veto would be the risk
   agent's judgement, most plausibly on AMD, the one order a condition seat
   cautions.
3. **A risk agent that says so.** It has not yet run on real input.

## 3.8, revisited — The four replies re-validated after the operator's rule on citations

**Run offline, 2026-09-19,** on the stored text of the four 3.8 replies
(`fixtures/cycles/20260919T171351Z/`). No new call was made.

**What changed in the validator** (LESSONS 2026-09-19; `agents/schema.py`):
- a figure written with thousands separators is read as one number;
- a bracket that is not a field reference is prose, not a citation;
- a real value cited under a loose reference is accepted, and the imprecision
  is recorded in the parsed result and in the signed record;
- a figure that matches no value of the assets its line is about still refuses
  the report.

The search covers the call's own asset and the assets the line names, not the
whole snapshot.

| Seat | At 3.8 | Now | Imprecisions recorded | What still refuses |
|---|---|---|---|---|
| price-trend | refused (1) | **accepted** | 1: INTC's 109.05, cited to two closes, is its mark | — |
| execution-quality | refused (5) | **accepted** | 5: `swap_impact_bps`, `fee_bps` and `slippage_bps` resolve to `quote.…` | — |
| price-integrity | refused (4) | **accepted** | 0: the separators are read, and its bracket was prose | — |
| cross-asset-macro | refused (7) | **refused (1)** | 9: META's, INTC's, NVDA's and SPY's figures, each found under the asset the line names, and USO's mark | `-0.09`, written `+(-0.09)%`: a percentage the parser does not read as one, so it is checked as a figure and found nowhere |

**Three of four now pass: a quorum.** The one refusal left is a parser gap on
our side, listed in the sweep and not fixed.

**The fabrication check still holds** (`tests/test_schema.py`):
- six figures from these replies, each changed to a value the snapshot does not
  hold, all refuse. They include figures on loose lines, a figure written with
  separators, and a figure that belongs to another asset;
- a real value of an asset the line does not name refuses;
- a figure behind a bracket of prose is checked.

Four ways of weakening the check were each broken in a copy, and each was
caught.

## The sweep after 3.8 — what else of this kind is waiting

**Done 2026-09-19, read-only.** Four sweeps were made:
- my own;
- three reviewers, each reading one area without my conclusions: the Phase 3
  code, the analyst contract, and the snapshot rules with the gates;
- every serious finding was reproduced offline before it was listed here.

**Nothing below is fixed.** Each is the operator's call.

### Real bugs: the code does the wrong thing

| # | Where | What | Evidence |
|---|---|---|---|
| R1 | `core/gates.py` `evaluate`, `agents/risk.py` `decide` | **The cash floor is judged on the whole plan, not the orders approved.** When a gate or the risk agent blocks a sell, the buys its proceeds paid for still clear, so approved cash can go below the floor and below zero. | Reproduced: approved cash **−$17.49** (and −$4.98 in a second case) |
| R2 | `core/aggregate.py` against `core/plan.py` | **The aggregator and planner count cash differently.** The aggregator treats a cut's exact dollars as freed. The planner sells less: it rounds down to the cent and drops dust. So the planner writes plans its own cash-floor gate refuses, and every order is blocked, the sell included. | Reproduced: a $25.625 cut sold as $25; "leaves $19.38 … below the floor of $20" |
| R3 | `core/plan.py` `size`, `gates.order_size` | **The per-trade limit can be passed on a cut to zero.** The last piece sells everything left, including the dust that was dropped, while its `usd` label says $25, and the gate reads the label. The overrun is under $1. | Reproduced: labelled $25, sells **$25.90** at the mark, gate passes |
| R4 | `run/decide.py:260` | **A replay is not byte-stable.** The record's `risk.agent` is `"unassigned"` live and `null` on replay, so 3.9 would fail on the 3.8 fixture. | Read, and reproduced by a reviewer: `fe3ed128…` against `2c9c1a79…` |
| R5 | `agents/schema.py` | **Two ways a fabricated figure passes the check that matters most:** a figure line with no citation is never checked, and a decimal right before a full stop is never read. | Reproduced: `- 999.99, Friday's close` and `- The close was 999.99. [mark.price_usd]` accepted |
| R6 | `agents/schema.py` `parse` | **An indented or bolded `CALL` line is not a call.** It drops out of what the aggregator reads, while the risk agent and a buyer read it. The brief's own template is indented. | Reproduced: META's call gone from the parsed calls |
| R7 | `agents/risk.py` `review` | **`context-budget` appears twice** in an order's `vetoed_by`, in the signed record. Cosmetic. | Read |

### Strictness mismatches: a check asks more or less than the record says, or requires what no one is told

| # | Where | What |
|---|---|---|
| S1 | `agents/schema.py` | **A computed decimal on a line that cites a single field is refused as fabricated.** Only `%`, and `bps` with no bps field cited, count as computed. `a 2.02 premium`, `8.3x`, `1.9 %`, `4.5pp`, `$4.42m` and `0.78 correlation` are all refused. The brief tells analysts to cite the fields a computed figure comes from, and that is what gets it checked. **The likeliest refusal on the next live run,** most of all for cross-asset-macro. Reproduced. |
| S2 | `agents/schema.py` | **Every bps figure on a line citing a `_bps` field is checked against it.** No brief gives `divergence_bps`'s sign convention: `450.32 bps above` against AMZN's −450.32 is refused. |
| S3 | `agents/schema.py` | **A loose citation puts every computed figure on its line through the fabrication check.** New with the check by value, but no stricter than before, when such a line was refused outright. The latest round has no citation form at all. |
| S4 | `agents/schema.py` | **`+(-0.09)%` is not read as a percentage.** It is the one refusal left in the 3.8 replies. |
| S5 | `agents/schema.py` | **`NO CALLS` must be exact, and cannot stand beside calls.** The brief says neither. Execution-quality nearly tripped this at 3.8. |
| S6 | `agents/risk.py` `parse` | **The risk parser refuses any variation from its template,** such as `ORDER 1 AMD veto (quote-age)` or `OVERALL: approve`, and a refused reply vetoes everything. The brief invites naming the gate. Fails closed. No real model has seen it. |
| S7 | `briefs/analyst.v1.md` | **The brief says code checks every figure.** Figures in the prose are not checked, by design (below). |
| S8 | `core/gates.py` `tradeable`, `agents/schema.py` | **Sells are gated by buy-side status.** A held name that falls below the corroborator line can never be sold, and a sell call on it refuses the whole report. 1.2's DECISION says such a name is "refused for buying, never dropped as a holding". Reproduced. |
| S9 | `core/gates.py` `cash_floor` | **The cash floor blocks sells that raise cash.** A book already below the floor cannot sell its way back. Reproduced. |
| S10 | `core/gates.py` `mandate_allows` | **The mandate gate checks only the order's labelled asset,** not the legs traded. Reproduced on a constructed plan; the planner does not build such plans. |
| S11 | `core/gates.py` `tradeable` | **The snapshot's verdicts have no age limit.** At 3.8 the decision came 11 h 15 m after the block. A Saturday snapshot decided after Monday's open would pass an open-session divergence as a finding. |
| S12 | `core/plan.py` `book`, `run/decide.py` | **One unmarkable holding stops the cycle with no signed record.** A paused name, or a stale USDG mark on a sell-only plan, does it. The holiday case is recorded; these are not. |
| S13 | `run/decide.py` | **"authorizes True" only shows the envelope agrees with itself.** It is checked against the key the envelope names. No published key is configured. |

### Already planned, not bugs

- **Numbers in report prose are not checked:** SIMPLIFICATION 2.2, "Given
  up". The brief's wording is S7.
- **A fresh quote before submission:** 4.4. **Stock legs to paper, since
  `executable` is null:** 4.5.
- **The ETH↔USDG leg:** Phase 5. **The mandate's approval and expiry:** 4.1.
- **The refused replies, absent from the signed record:** owed since 3.8.
- **Co-movement is ignored:** a recorded limit.
- **Holidays and daylight saving:** recorded, with the re-derivation dated
  2026-11-09.
- **The output cap:** 12,000 tokens, documented. Execution-quality used 9,144
  at 3.8, a 24% margin.

**One cause behind R1 to R3:** the aggregator, the planner and the gates each
count cash their own way. **One cause behind S1 to S3:** the figure check works
per line, not per figure.

## After the sweep — the four 3.8 replies again, with the sweep's fixes

**Run offline, 2026-09-19,** on the stored text. No new call was made.

| Seat | At 3.8 | After the citation rule | Now | Loose citations recorded |
|---|---|---|---|---|
| price-trend | refused | accepted | **accepted** | 1 |
| cross-asset-macro | refused | refused, on `+(-0.09)%` | **accepted** | 9 |
| execution-quality | refused | accepted | **accepted** | 5 |
| price-integrity | refused | accepted | **accepted** | 0 |

**All four pass.** Cross-asset-macro's `+(-0.09)%` is now accepted as SPY's
change between the two closes its line cites: (761.55 − 762.21) / 762.21 is
−0.087%, written −0.09. That is S1's rule, one arithmetic step from two cited
fields, not the notation. The parser still does not read `+(-0.09)%` as a
percentage (S4), and `+(-0.19)%` in its place refuses.

**Every hole R5 named is closed, and was attacked:**
- `- 999.99, Friday's close` with no citation refuses;
- `- The close was 999.99. [mark.price_usd]` refuses;
- `- The close was 999.99.` refuses;
- a fabricated figure under an indented CALL refuses (R6);
- each hole reopened in a copy is caught.

**The same four replies through the aggregator** would give the hypothetical
of F3.8.8, now with every call counted. AMD's two direction seats disagree,
buy against hold, and price-integrity cautions it.


## 3.8, finished — the exit run that ends Phase 3

**Run 2026-09-19, starting 20:20Z, inside the closed session.**
- **The snapshot:** a fresh one, `c06abd9e…` at block 67364057, captured in
  `fixtures/snapshots/67364057-c06abd9e89f0/`. 17 names are tradeable (AMD,
  COIN and MSFT have left the buy universe since 06:01Z), with five
  closed-session findings: AMZN, MSTR, MU, PLTR and SGOV.
- **Four analyst calls,** one per seat, on the shared `BANKR_LLM_KEY` with the
  key measured first, at 20:22:59Z.
- **Then the decision:** live quotes, read-only, and one live risk call, signed
  with the fund's key.

The cycle is `fixtures/cycles/20260919T202259Z/`. Its record rebuilds byte for
byte offline from that directory, so it is 3.9's cycle.

| Call | Result | Cost | Time | Tokens in | Tokens out |
|---|---|---|---|---|---|
| price-trend | accepted | $0.242438 | 59.1 s | 97,644 | 4,715 |
| cross-asset-macro | accepted, 2 loose citations | $0.277032 | 92.4 s | 97,701 | 8,163 |
| execution-quality | accepted | $0.251220 | 70.4 s | 97,700 | 5,582 |
| price-integrity | accepted | $0.272702 | 83.3 s | 97,726 | 7,725 |
| risk | replied, read with no deviation | $0.099454 | 45.9 s | 29,202 | 4,105 |

**Spent:** $1.142846 by the replies' own figures. The balance was $14.678389
before 3.8's first run and was not re-read.

### The price-trend report, unedited

```
REPORT price-trend unassigned c06abd9e89f007c5c665dc5fdd1104b6824c6a05f0c47a76058b3e0bce729783

The market is shut (us_equities_24/5 closed), so every stock's mark is its last round before the weekend while GeckoTerminal and the venue keep pricing off-feed; the 30-day closes and the latest round are still the cleanest read of trend, but the "latest round" figure for a few names sits well off the corroborator (AMZN, MSTR, MU, PLTR, SGOV per findings) — a price-integrity matter, not mine, but it means I lean on the close series more than the single latest print. Most names are simply chopping inside a range; a handful show a genuine, sustained slope worth acting on.

CALL AAPL 0xaf3d76f1834a1d425780943c99ea8a608f8a93f9 buy medium
Apple has climbed almost the whole month, with a shallow pullback mid-month that held above 315 before pushing to new highs.
- 308.93973568 close on 2026-08-21, the 30-day low [timeline 2026-08-21]
- 337.05904445 close on 2026-09-17, the 30-day high [timeline 2026-09-17]
- 335.3847472 latest mark, +8.6% over the window [mark.price_usd, timeline 2026-08-21]
Wrong if: it closes back below 315.69360675, the 2026-09-09 pullback low [timeline 2026-09-09].

CALL GME 0x1b0e319c6a659f002271b69db8a7df2f911c153e buy high
GameStop's closes are the cleanest trend on the sheet: a near-monotonic climb from 18 to nearly 23 with no material give-back.
- 18.00445 close on 2026-08-24, the low of the window [timeline 2026-08-24]
- 22.713 close on 2026-09-17, the high [timeline 2026-09-17]
- 22.55175 latest mark, +25% off the low [mark.price_usd, timeline 2026-08-24]
Wrong if: it closes below 20.445, the 2026-09-10 higher-low that anchors this move [timeline 2026-09-10].

CALL INTC 0xc72b96e0e48ecd4dc75e1e45396e26300bc39681 buy high
Intel spent three weeks range-bound near 88-92, then broke out in the second half of September and is holding the new range above 100.
- 87.16499999 close on 2026-08-24, the pre-breakout low [timeline 2026-08-24]
- 109.205 close on 2026-09-17, the high of the window [timeline 2026-09-17]
- 109.05 latest mark, +25% off the low [mark.price_usd, timeline 2026-08-24]
Wrong if: it closes back below 97.225, the 2026-09-15 higher-low that held the breakout [timeline 2026-09-15].

CALL MU 0xff080c8ce2e5feadaca0da81314ae59d232d4afd buy medium
Micron dipped into mid-September, then broke to a new 30-day high on the last two closes.
- 924.43916433 close on 2026-09-14, the recent low [timeline 2026-09-14]
- 1014.42589693 close on 2026-09-18, a new high [timeline 2026-09-18]
- 1014.42589693, +9.7% off the 2026-09-14 low [timeline 2026-09-14, timeline 2026-09-18]
Wrong if: it closes back below 924.43916433, erasing the recent breakout [timeline 2026-09-14].

CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 buy medium
Oil has trended up all month off the August low, and even the latest pullback from the mid-September high has held well above where it started.
- 126.33345 close on 2026-08-25, the 30-day low [timeline 2026-08-25]
- 161.405 close on 2026-09-15, the high [timeline 2026-09-15]
- 154.54265 latest round, +22% off the low [mark.price_usd, timeline 2026-08-25]
Wrong if: it closes below 141.995, the 2026-09-03 level that marks the start of this leg [timeline 2026-09-03].

CALL NVDA 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec hold low
Nvidia is still doing what it did a month ago: chopping in the 208-230 band, now sitting mid-range after bouncing off this month's low.
- 211.92474816 close on 2026-09-15, the recent low [timeline 2026-09-15]
- 230.23665 close on 2026-09-04, the range high [timeline 2026-09-04]
- 222.44729849 latest close, roughly mid-range [timeline 2026-09-18]
Wrong if: it closes above 230.23665, a breakout and a buy, or below 207.91, the August low, and a sell [timeline 2026-09-04, timeline 2026-08-24].
```

### The cross-asset-macro report, unedited

```
REPORT cross-asset-macro unassigned c06abd9e89f007c5c665dc5fdd1104b6824c6a05f0c47a76058b3e0bce729783

The venue's equities session is shut (`block.closed_sessions: ["us_equities_24/5"]`), so every stock mark below is the last pre-close round while GeckoTerminal and the venue continue to trade; several names (AMZN, MSTR, MU, PLTR, SGOV) already show closed-session divergence findings past 100bps. That does not block a co-movement read: 20 daily closes over 30 days is enough to see three clusters. First, SPY and QQQ move almost as one — over 8/14→9/16 SPY fell 1.15% (760.04→751.28) and QQQ fell 1.13% (710.25→702.19) the same two days, so the book cannot buy diversification by holding both. Second, the mega-cap/semis complex (AAPL, GOOGL, NVDA, MU, INTC) rallies together on the same sessions — on 9/16→9/17 NVDA +2.6%, MU +5.5%, INTC +8.2%, AAPL +1.5%, GOOGL +1.4% all moved up the same day — one correlated tech bet, not five. Third, the macro sleeve diverges from that complex: USO (oil) rose 14.3% over the window while SPY and QQQ were flat to down, and SGOV barely moved at all (+0.18%), both genuinely uncorrelated to the equity beta. MSTR is its own animal, spiking 17.4% on 9/2→9/3 while SPY/QQQ moved about 1% — a single-name, crypto-linked driver, not something the book's other positions already express, but too idiosyncratic and too divergence-flagged to call cleanly.

CALL QQQ 0xd5f3879160bc7c32ebb4dc785f8a4f505888de68 hold medium
QQQ tracks SPY almost tick-for-tick over the window; owning both index vehicles is one basket-beta bet, not two, so adding here does not diversify the book.
- QQQ -1.13% from 2026-09-14 to 2026-09-16 (710.245→702.1937) [timeline 2026-09-14, timeline 2026-09-16]
- SPY -1.15% over the same two days (760.04→751.28) [SPY timeline 2026-09-14, SPY timeline 2026-09-16]
- QQQ +0.92% over 30 days (713.7894→720.3651) [timeline]
Wrong if: QQQ and SPY start printing opposite-signed daily moves for a week, showing the two indices decoupling.

CALL NVDA 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec hold medium
NVDA moves with the same-day mega-cap/semis cluster (AAPL, GOOGL, MU, INTC); adding NVDA on top of that cluster doubles a bet the book already gets from the other names, it does not diversify.
- NVDA +2.57% on 2026-09-17 (214.17088793→219.67214898) [timeline 2026-09-16, timeline 2026-09-17]
- MU +5.51%, INTC +8.22%, AAPL +1.49%, GOOGL +1.44% the same day [MU timeline 2026-09-16, MU timeline 2026-09-17, INTC timeline 2026-09-16, INTC timeline 2026-09-17, AAPL timeline 2026-09-16, AAPL timeline 2026-09-17, GOOGL timeline 2026-09-16, GOOGL timeline 2026-09-17]
Wrong if: NVDA prints a session where the rest of that cluster is flat or down, breaking the cluster's shared move.

CALL SGOV 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 buy medium
SGOV barely moves at all across the window while the equity book's names swing several percent daily; it is the one asset here with no correlation to the tech/index cluster, the cleanest diversifier in the set.
- +0.18% over 30 days (100.92501538→101.10821255) [timeline 2026-08-21, timeline]
- range of only ~0.19 across all 20 closes (100.9172→101.1082) [timeline]
- QQQ moved -1.13% in two days over the same window while SGOV moved essentially zero [QQQ timeline 2026-09-14, QQQ timeline 2026-09-16]
Wrong if: SGOV's daily closes start moving by more than a few bps in step with the equity names, which would say the ballast has broken.

CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 buy low
Oil ran up hard this window while the equity index legs stayed flat to down, so USO's move this month did not track the book's other risk — real diversification, not a duplicate of an existing bet.
- +14.27% over 30 days (135.255→154.54265) [timeline 2026-08-21, timeline 2026-09-18]
- SPY -0.60% and QQQ +0.92% over the same 30 days [SPY timeline 2026-08-21, SPY timeline, QQQ timeline 2026-08-21, QQQ timeline]
Wrong if: USO starts tracking SPY/QQQ day to day rather than moving on its own path.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 hold low
MSTR's single-day swings dwarf the index's on the same date, meaning it moves on its own driver, not the book's equity beta — a genuine diversifier by co-movement, but the size of the moves and its closed-session divergence finding argue for watching rather than sizing up now.
- +17.36% on 2026-09-03 (123.05705→144.415) [timeline 2026-09-02, timeline 2026-09-03]
- SPY +1.01% and QQQ +1.07% the same day [SPY timeline 2026-09-02, SPY timeline 2026-09-03, QQQ timeline 2026-09-02, QQQ timeline 2026-09-03]
- closed-session divergence -384.05 bps recorded against GeckoTerminal [corroboration.divergence_bps]
Wrong if: MSTR's daily moves start lining up in size and direction with SPY/QQQ, showing it has re-joined the equity beta.
```

### The execution-quality report, unedited

```
REPORT execution-quality unassigned c06abd9e89f007c5c665dc5fdd1104b6824c6a05f0c47a76058b3e0bce729783

The market is shut (`block.closed_sessions` lists `us_equities_24/5`), so every mark is the feed's last pre-close round while the venue and GeckoTerminal keep moving; a buy still fills at the venue's live price but books at that frozen mark, so the fill-to-book gap is the number that matters tonight, not the impact alone. Across the 17 tradeable names the mechanics of the quote itself are uniformly cheap: `fee_bps` is 0 everywhere, quotes are 0.7–26s old (well inside the 60s tradeability window), and `swap_impact_bps` sits in the single digits to low tens for all of them, so the venue's own execution cost is not the story. What is the story is the gap between `quote.venue_price_usd` and `mark.price_usd`: most names show 0–50 bps of gap (AAPL ~4bps, NVDA ~1bp, SPY ~45bps, GOOGL ~33bps), but Strategy (MSTR) shows a gap of roughly 362bps and Amazon (AMZN) compounds a 19bps venue impact with a 27.7bps fill-to-book gap, both traceable to their feeds being frozen well behind live trading (both also carry closed-session divergence findings). A buyer of MSTR right now pays the venue's live price and is booked ~3.6% worse immediately, before any market move — that is a pure execution-quality cost, independent of whether the mark itself is "right."

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution high
Filling at the venue's live price and booking at the frozen mark costs about 362 bps on entry alone, even though the quote itself looks clean (low impact, sub-second age).
- venue_price_usd 158.172427417523 vs mark.price_usd 152.643, a gap of ~362 bps [quote.venue_price_usd, mark.price_usd]
- swap_impact_bps 10, fee_bps 0, well within limits [quote.swap_impact_bps, quote.fee_bps]
- quote age 0.735s, essentially instant [quote.age_s]
- mark last updated 2026-09-18T23:41:26Z, 74346s of feed age with the closed session inferred [mark.updated_at, mark.fresh]
Wrong if: the venue price and the mark converge to within ~50bps at the next fresh round, at which point the entry gap disappears.

CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 caution medium
The venue itself already prices in 19 bps of impact, and on top of that the fill books against a mark that sits 27.7 bps below the venue price, stacking to roughly 47 bps of round-trip-relevant cost for a name whose feed is frozen mid-close.
- venue_price_usd 254.5649498937818 vs mark.price_usd 253.863, a gap of ~27.7 bps [quote.venue_price_usd, mark.price_usd]
- swap_impact_bps 19, the highest quoted impact among the tradeable names besides ASML/CLSK-tier exclusions [quote.swap_impact_bps]
- quote age 24.322s, still within the 60s window but the widest among the low-impact set [quote.age_s]
Wrong if: swap_impact_bps drops back toward single digits and the venue/mark gap narrows below 10 bps on the next quote.
```

### The price-integrity report, unedited

```
REPORT price-integrity unassigned c06abd9e89f007c5c665dc5fdd1104b6824c6a05f0c47a76058b3e0bce729783

The book is closed (`block.closed_sessions: ["us_equities_24/5"]`): every Chainlink mark here is its last pre-close round, while GeckoTerminal and the venue keep pricing live. That is exactly the setting where mark-vs-corroborator divergence is expected and not, by itself, a defect — the question is whether the venue (also live) sides with the frozen mark or with GeckoTerminal. Five tradeable assets carry closed-session divergence findings; I checked each against the venue. Four of them are not the mark's fault: the venue agrees with the frozen mark and it is GeckoTerminal, not Chainlink, that has moved off. One, MSTR, is the opposite pattern — venue and GeckoTerminal agree with each other and both sit well away from the mark, which is the real story. I also flag USO, unflagged but showing the same two-against-one shape at lower magnitude.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution high
The mark is the outlier: venue and GeckoTerminal agree with each other to within 36bps, but the mark sits ~360bps away from both, on a book that only just closed (99.6% of its round age is closed-session).
- mark 152.643 [mark.price_usd]
- venue 158.172427417523, +362bps from mark [quote.venue_price_usd]
- GeckoTerminal 158.7392617361, -384.05bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price reverts toward 152.6 rather than toward GeckoTerminal's 158.7, which would show the venue itself was the transient outlier.

CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 proceed medium
Carries a closed-session divergence finding (-428.73bps vs GeckoTerminal) but the venue confirms the mark, not GeckoTerminal: venue is only ~28bps from the mark. GeckoTerminal is the one that has drifted.
- mark 253.863 [mark.price_usd]
- venue 254.5649498937818, ~28bps from mark [quote.venue_price_usd]
- GeckoTerminal 265.2342975081, -428.73bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price moves to converge on GeckoTerminal's 265 rather than staying near the mark.

CALL MU 0xff080c8ce2e5feadaca0da81314ae59d232d4afd proceed medium
Carries a closed-session divergence finding (+170.59bps vs GeckoTerminal); venue sits much closer to the mark (~43bps) than to GeckoTerminal (~127bps from venue), so the mark still holds and GeckoTerminal is the stale/thin read here.
- mark 1014.42589693 [mark.price_usd]
- venue 1010.0912233694492, ~43bps from mark [quote.venue_price_usd]
- GeckoTerminal 997.4118039747, +170.59bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price drops toward GeckoTerminal's 997 instead of holding near 1010–1014.

CALL PLTR 0x894e1ec2d74ffe5aef8dc8a9e84686accb964f2a proceed medium
Same shape: a +160.91bps closed-session finding against GeckoTerminal, but the venue is only ~54bps from the mark versus ~106bps from GeckoTerminal, so the mark, not GeckoTerminal, is the one to trust here.
- mark 177.6031 [mark.price_usd]
- venue 176.64144579270487, ~54bps from mark [quote.venue_price_usd]
- GeckoTerminal 174.7906936484, +160.91bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price falls toward GeckoTerminal's 174.8 rather than staying near 176.6–177.6.

CALL SGOV 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 proceed medium
Carries a +111.97bps closed-session finding, just past the 100bps line, but venue and mark are nearly identical (~8bps apart) while GeckoTerminal sits ~104bps from the venue — for a cash-like bond ETF that is GeckoTerminal mispricing a thin pool, not the mark drifting.
- mark 101.10821255 [mark.price_usd]
- venue 101.02841109470803, ~8bps from mark [quote.venue_price_usd]
- GeckoTerminal 99.9886955829, +111.97bps from mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price moves down toward GeckoTerminal's 99.99 rather than staying pinned near 101.

CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 caution low
Unflagged (mark-vs-gecko divergence is only 67.46bps, under the veto line) but the pattern still points at the mark: venue and GeckoTerminal sit only ~45bps apart from each other, while the mark is ~112bps above the venue and ~67bps above GeckoTerminal — both live sources agree below the frozen mark.
- mark 154.54265 [mark.price_usd]
- venue 152.82654076484644, ~112bps below mark [quote.venue_price_usd]
- GeckoTerminal 153.5072322941, +67.46bps vs mark [corroboration.price_usd, corroboration.divergence_bps]
Wrong if: the venue price rises to converge on 154.5 rather than GeckoTerminal's 153.5, showing the mark was fine and the venue was lagging.
```

### The aggregation, as the command printed it

```
4 of 4 seats reported · 4 seat(s) reported, at least the quorum of 3
rebalance: quorum met: targets from the calls
confidence: low 0.25, medium 0.5, high 0.75 · a score moves a weight by score x the position limit

asset  price-trend     cross-asset-macro  execution-quality  price-integrity    direction  caution  score     now  target    change $
AMZN   ·               ·                  caution med 0.5    proceed med 0      ·          0.5      ·         0    0         ·
GME    buy high +0.75  ·                  ·                  ·                  +0.75      ·        +0.75     0    0.1875    +37.50
PLTR   ·               ·                  ·                  proceed med 0      ·          ·        ·         0    0         ·
SGOV   ·               buy med +0.5       ·                  proceed med 0      +0.5       ·        +0.5      0    0.125     +25.00
USO    buy med +0.5    buy low +0.25      ·                  caution low 0.25   +0.375     0.25     +0.28125  0    0.070312  +14.06
AAPL   buy med +0.5    ·                  ·                  ·                  +0.5       ·        +0.5      0    0.125     +25.00
INTC   buy high +0.75  ·                  ·                  ·                  +0.75      ·        +0.75     0    0.1875    +37.50
NVDA   hold low 0      hold med 0         ·                  ·                  0          ·        0         0    0         ·
QQQ    ·               hold med 0         ·                  ·                  0          ·        0         0    0         ·
MSTR   ·               hold low 0         caution high 0.75  caution high 0.75  0          0.75     0         0    0         ·
MU     buy med +0.5    ·                  ·                  proceed med 0      +0.5       ·        +0.5      0    0.125     +25.00
cash                                                                                                          1    0.179688  -164.06

residual 0.0000005: what rounding each change toward zero left in cash · targets are what the calls want; the plan funds raises only from cash above the floor
```

### The risk agent's reply, unedited

```
RISK 520ebf1f12002cbd2de8f39301905f988c9ca5ebe5879782a94012021b0802ce
ORDER 1 GME approve
Price-trend calls GME a high-conviction buy on a clean uptrend, corroboration divergence is a modest 27.75bps with no finding raised, and the quote/impact figures are clean; approved as the single GME leg to the 0.1875 target.
ORDER 2 GME veto
This is a second, near-identical $18.75 GME buy stacked on order 1 with the same 0.1875 target-weight math; executing both would push the actual GME position to ~0.375 of NAV, breaching the 0.25 position-weight cap the gate only checked in isolation — no report supports a double-sized GME position.
ORDER 3 SGOV approve
Price-integrity confirms the venue sits within 8bps of the mark and identifies GeckoTerminal's pool as the stale side of the divergence; macro report calls it the cleanest ballast in the book. Evidence supports the buy.
ORDER 4 USO approve
Price-trend shows a sustained 22% uptrend and macro flags USO as genuine diversification versus the equity sleeve; price-integrity's caution is that the frozen mark sits above live venue/Gecko prices, meaning the position books at a higher value than paid — not a basis to veto a buy.
ORDER 5 AAPL approve
Price-trend documents a sustained month-long uptrend, divergence is a modest -14.31bps with no finding, and execution metrics are clean.
ORDER 6 INTC approve
Price-trend calls a high-conviction breakout above the prior range, corroboration divergence is a modest -31.64bps with no finding raised, and quote/impact figures are clean; approved as the single INTC leg to the 0.1875 target.
ORDER 7 INTC veto
Duplicate of order 6 with the same $18.75 size and identical 0.1875 stand-alone target math; filling both would double the intended INTC weight to ~0.375 of NAV, past the 0.25 cap the gate checked only order-by-order, with no report calling for that much INTC exposure.
ORDER 8 MU approve
Price-trend calls a fresh breakout to a 30-day high and price-integrity confirms the venue sides with the mark (~43bps) rather than GeckoTerminal's stale pool (~127bps away), so the closed-session divergence finding does not undercut the mark used for this buy.
OVERALL approve
Six of the eight orders are supported by the reports and clean evidence; the two duplicate GME/INTC legs are vetoed because filling them alongside their twins would push those positions well past the mandate's 0.25 weight cap that the gate never saw because it checked each order in isolation.
```

### F3.8.10 — Four of four accepted: the first cycle made wholly of real output

**Confidence: measured.** Every report passed the validator as amended after
the sweep.
- **Loose citations:** cross-asset-macro cited SGOV's and USO's marks as
  closes, and both were recorded. The brief's new line held: every figure of
  another asset was cited under that asset's symbol.
- **Cross-asset-macro answered in 92 s,** with no 504.

### F3.8.11 — The decision: eight buys planned, six approved, two vetoed by the risk agent

**Confidence: measured.**
- **The plan:** eight buys of $164.06, every raise funded in full from cash
  above the floor. GME and INTC were each one $37.50 move, split in two by the
  $25 per-trade limit.
- **The gates:** every order cleared, quorum, turnover and the context budget
  included. The bundle came to about 48,700 tokens against 70,000.
- **Approved:** GME $18.75, SGOV $25, USO $14.06, AAPL $25, INTC $18.75 and MU
  $25, which leave $73.44 of paper cash against the $20 floor.
- **Vetoed by `risk`:** the second GME leg and the second INTC leg.
- **Signed** with the fund's key as `732161ded89aee8367509069809b34e4fec901035a83011ebbf839d1bbe126fc`.
  It authorizes against the key it names. Nothing was executed.

### F3.8.12 — The veto that fired rests on a misreading the plan invited

**Confidence: measured, from the plan and the gates as the risk agent read
them.** The risk agent vetoed each second leg because "executing both would push
the actual GME position to ~0.375 of NAV, breaching the 0.25 position-weight cap
the gate only checked in isolation".

**That is false.**
- The two legs are halves of one move to 0.1875, and together they reach it.
- The position gate sums every order for an asset.

**The plan made the misreading easy.**
- Each leg carries the same weight block, `current 0, target 0.1875, after
  0.1875`, where `after` is the position once all its orders have run.
- Each carries the same gate reason, "the position would be 0.187500 of the
  NAV".
- Nothing says "part 1 of 2".

So the only veto is the risk agent's own judgement, not a gate. It is aimed at a
real concern, over-sizing past the cap, but wrong on the facts, and the cause is
ours. **The effect:** GME and INTC are bought at half the size the calls wanted,
which is the conservative direction.

**Real bug, owned by 3.3:** how the written plan presents the pieces of a
split move. Each order should show its part, and the weight after that order.

### F3.8.13 — Is the risk agent's reasoning substantive, or restating the gates?

**Confidence: a judgement on one reply, with every cited figure checked
against the snapshot.** It is substantive: it reads the reports and the evidence
the gates do not judge.
- **MU and SGOV:** it weighs price-integrity's reading that the venue sides with
  the mark. MU's venue is 43 bps from the mark against 127 bps from
  GeckoTerminal; SGOV's is 8 bps. That is the closed-session judgement the
  divergence finding was carried to the record for.
- **USO:** it reads price-integrity's caution correctly. The frozen mark sits
  above both live prices, so a buy books a gain it did not earn, and it judges
  that no reason to veto.
- **GME, AAPL and INTC:** it quotes their divergences, 27.75, −14.31 and −31.64
  bps, each exactly the snapshot's.

Its one error is structural, F3.8.12. It argued past the gates, and on a
misread plan.

### F3.8.14 — Why the expected veto did not happen

**Confidence: measured.** The story on record was price-integrity naming a
stale mark and risk vetoing the buy.
- **The stale mark was named.** Price-integrity and execution-quality both
  caution MSTR high: the venue sits 362 bps above a mark frozen at Friday's
  close.
- **But no direction seat bought MSTR.** Cross-asset-macro holds it low, and
  price-trend passes on it. So there was no MSTR order to veto.
- **AMD,** the other stale mark of the morning's capture, has left the buy
  universe.

The fixed gates passed everything, as SIMPLIFICATION's Q2 predicted for a closed
session.

For the expected veto:
- a direction seat must buy an asset whose mark price-integrity calls stale;
- the risk agent must weigh that caution into a veto.

MSTR at a 362 bps gap is where that would happen.

### F3.8.15 — The NVDA example still shapes price-trend's NVDA call

**Confidence: one observation.**
- **What it wrote:** "hold low", "chopping in the 208-230 band", with a "Wrong
  if" breaking out either way. That is the structure of the brief's example,
  with figures of its own.
- **What the label did:** at 3.8's first run price-trend made no NVDA call. So
  relabelling did not cure the copying; replacing the example would.
- **Why it cost nothing:** it is a hold, and no order came of it.
