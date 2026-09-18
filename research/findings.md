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
> cost" would mislead.

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
