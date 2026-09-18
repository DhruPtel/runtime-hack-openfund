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
