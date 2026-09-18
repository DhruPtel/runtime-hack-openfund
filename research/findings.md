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
