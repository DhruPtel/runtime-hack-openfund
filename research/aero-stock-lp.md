# aerofun — repository research

> **Target correction.** There is no `./aerofun` on this machine. `find / -maxdepth 7 -iname "*aerofun*"` returned nothing and `grep -ril aerofun` across `repo_research/` returned nothing. On your instruction this report covers the nearest match on disk: **`repo_research/skills/aero-stock-lp`**. Filename kept as requested.

---

## 2. IS IT RELEVANT?

**Yes — strongly, on four of your six axes, and it is the single most directly comparable artifact you have.** It is a production Bankr skill that range-LPs **tokenized equities** (NVDA, AAPL, GOOGL, META as Coinbase-backed Base predeploys) on **Aerodrome Slipstream** concentrated-liquidity pools, with a hard **LLM-vs-deterministic boundary**, **gate-based fail-closed risk control**, **unsigned-calldata-only money paths**, and a **position valuation + P&L** layer. It hits: tokenized equities (yes), Aerodrome/Uniswap-v3-style pools (yes — Slipstream is a v3 fork with `tickSpacing` in place of `fee`), agent orchestration (partially — single agent, no fan-out), financial accounting (partially — see §9), Bankr (yes, as the execution rail: `submit_raw_transaction`).

It does **not** touch: **x402** (zero occurrences), **chain 4663 / Robinhood Chain** (zero — it is hardcoded to Base 8453 at `scripts/lib/markets.mjs:5`), **USDG** (zero), `llm.bankr.bot` (zero), or the `/wallet/swap-quote` → `/wallet/swap` Bankr trade API (zero — it bypasses that entirely and builds raw router calldata itself). It has no agent fan-out, no supervisor/worker shape, no risk-veto agent, no schema validator, no accountability/statement layer.

So: **steal the shape, not the surfaces.** Sections 4, 5, 8 and 12 are where the value is.

---

## 1. ORIENTATION

**What it is.** A *skill*, not a product, framework, or demo — a `SKILL.md` prompt contract plus a bundled zero-dependency Node toolchain. The model is the operator; the scripts are the machine. It is shipped as an installable Bankr skill.

**Who made it.** `BankrBot/skills` (`git remote -v` → `https://github.com/BankrBot/skills.git`). Sole author across all 8 commits: **Igor Yuzovitskiy** (`igor@bankr.bot` / `igor.yuzovitskiy@gmail.com`). First commit `ad0032e` 2026-08-21, latest `365801e` 2026-08-27. Addresses annotated "verified on-chain Aug 2026" (`scripts/lib/markets.mjs:3`).

The commit titles read as a maturity curve worth noting:
```
ad0032e  focus the skill on core LPing; drop automation + dashboard app
9e9b03c  move deterministic work into bundled node scripts
3480785  v2: calldata hygiene, gas preflight, single-confirmation contract, Bankr automations
365801e  fix 0x0x calldata bug, dead trend brake, and audit findings
```
`9e9b03c` is the pivotal one — the deterministic work was *pulled out of the prompt into scripts* as a deliberate refactor. `365801e` is a post-audit hardening pass.

**Entry points.** Four CLI scripts, each printing exactly one JSON object to stdout (`scripts/entry.mjs:14`):

| Entry point | Phases | Role |
|---|---|---|
| `scripts/entry.mjs` | `plan` / `size` / `settle` | gates → band → swap → mint → route decision |
| `scripts/manage.mjs` | single | the read-everything, decide-everything, execute-nothing pass |
| `scripts/exit.mjs` | `begin` / `finish` / `sell-aero` | unwind, residual sells, burn |
| `scripts/selftest.mjs` | `[--live]` | 34 offline vectors + on-chain table verification |

**Directory map.** Flat; 11 files total.
```
SKILL.md              382 L   the prompt contract (§0–§9)
catalog.json           23 L   Bankr marketplace card
logo.svg               13 L
scripts/entry.mjs     479 L
scripts/manage.mjs    302 L
scripts/exit.mjs      230 L
scripts/selftest.mjs  171 L
scripts/lib/positions.mjs 247 L   discovery, valuation, state file
scripts/lib/chain.mjs     225 L   JSON-RPC, Multicall3, ABI codec, tx()
scripts/lib/markets.mjs   144 L   addresses, selectors, constants
scripts/lib/math.mjs       99 L   tick/price/band/share math
```

**LOC split.** 2,315 lines total. **Code: 1,897 (82%)** across 8 `.mjs` files. **Prose: 382 (17%)** — `SKILL.md` alone. Config/asset: 36 (1.5%). Zero runtime dependencies (no `package.json`, no lockfile, no `node_modules`); plain Node ≥ 18 using built-in `fetch`.

**Verified, not inferred:** `node scripts/selftest.mjs` runs clean in this environment — `{"ok":true,"checks":34,"failed":[]}`, exit 0.

---

## 3. ARCHITECTURE

**Agents: one.** A single LLM agent, no fan-out, no supervisor/worker, no sub-agents, no parallel analysts. The word "agent" in this codebase means "the one model running the skill."

**Where the control loop is: in the prompt, not in code.** This is the defining architectural fact. There is no daemon, no scheduler, no `while` loop, no orchestrator process. Each script is a pure, single-shot, stateless function of (chain state + args) → JSON. The loop that strings them together lives in `SKILL.md` §2/§3 as instructions to the model, and its cursor is the `next` field each script emits:

```
// scripts/entry.mjs:121  (SKILL.md §1)
// `txs` are unsigned; submit them in order via Bankr. `next` tells you the
// following command.
```

So the control flow is: script → JSON with `txs[]` + `next` → model submits txs via Bankr and waits for receipts → model runs `next` → repeat. The model is the runtime; the scripts are the ISA.

**Why it's phased rather than one call** (`SKILL.md:134`): "there are transaction boundaries. Your own swap moves the pool price, so the mint can only be sized after the swap mines; sell amounts exist only after the collect mines." Each phase re-reads chain state from scratch — `size` explicitly re-reads `slot0` post-swap (`scripts/entry.mjs:265-274`). Nothing is carried in memory across a transaction boundary except tick integers passed on the command line.

**Parallel fan-out — where it does exist, and how bounded.** Not at the agent layer; only at the RPC layer, and it is bounded three ways:

1. **Multicall3 batching with chunking + a concurrency cap** (`scripts/lib/chain.mjs:89-110`):
```js
const MULTICALL_CHUNK = 50;
...
const CONCURRENCY = 4;
```
Calls beyond 50 are split into chunks, then drained by exactly 4 worker closures over a shared cursor — a clean bounded worker pool in 8 lines. The comment gives the reason: "public RPCs reject oversized payloads (HTTP 413)."

2. **Enumeration cap** (`scripts/lib/positions.mjs:59`): `const ENUM_CAP = 400;` — "so a pathological wallet can't stall the pass." Truncation is surfaced, not swallowed (`manage.mjs:291`).

3. **Unbounded `Promise.all` fan-outs in `manage.mjs`** — `found.map(f => readPosition(...))` at `manage.mjs:100-102` and the per-market GeckoTerminal loop at `manage.mjs:77-81` have **no concurrency limit**. In practice this is bounded by the position count (5 markets), so it is safe here but would not survive a wider market table. Flagged.

**Scheduling** (`SKILL.md:220-237`) is explicitly delegated *outside* the codebase to the Bankr console's native automation system: a 2-hour scheduled manage pass plus two price triggers just inside each band edge. "no external cron, no webhooks." The triggers are wake-ups only — they never act; they launch a pass that re-applies the full gate stack.

---

## 4. LLM vs DETERMINISTIC BOUNDARY

**This is the section worth reading twice.** The boundary is drawn explicitly, in prose, at the top of the skill (`SKILL.md:14-22`):

> **Division of labor.** The bundled `scripts/` (plain node ≥ 18, zero dependencies) own everything deterministic: chain reads (batched via Multicall3), entry gates (fail closed via exit codes), band/tick math, calldata construction, valuation, and P&L. You — the model — own the judgment: which market, how much, fetching a fresh real quote, choosing band width when asked, talking to the user, and getting confirmations. Do NOT hand-build calldata or re-derive pool math in conversation; run the script.

**The model decides:** which market; how much USD; *fetching the real-world equity quote* (the one unavoidable model job — there is no keyed market-data feed, see §7); band width label when asked (`wide`/`standard`/`tight`); phrasing; when to ask the one confirmation.

**Code decides:** everything numeric. Specifically —

- **All arithmetic.** `scripts/lib/math.mjs` owns tick↔price conversion, band construction, and the token-ratio math. The file's header comment localizes the one thing models reliably get wrong:
```js
// USDC is token0 in every pool, so tick and human price move in OPPOSITE
// directions: the band's LOW price maps to the UPPER tick and vice versa.
// That inversion lives HERE, once, and nowhere else.
```
- **All thresholding.** Ten entry gates in a single declarative array (`scripts/entry.mjs:144-182`), each `{name, pass, value, limit}`, evaluated by `gates.find(g => !g.pass)` → `fail()` → exit 1.
- **All ranking.** The staked-vs-unstaked route choice is a pure comparison of two computed scalars (`scripts/entry.mjs:392-394`), and the rebalance decision is the conjunction of cost hurdle ∧ trend brake ∧ quote freshness (`scripts/manage.mjs:218-243`).

**Arithmetic, ranking or thresholding done by the model: none, by construction.** The skill goes out of its way to make model arithmetic structurally impossible rather than merely discouraged — the scripts emit `report` strings pre-formatted for verbatim relay (`SKILL.md:34-37`: "the scripts' `report` fields are written to be relayed nearly verbatim"), so the model never has a reason to compute a number it could then get wrong.

**The one place the model supplies a number that enters the math** is the equity quote (`--quote`, `--quote-age-s`) and the vol input (`--iv` or `--w`). Both are defended: the quote is cross-checked against pool price by two independent gates (`nav`: within 3%; `unseeded`: ratio in (0.5, 2)) and by a freshness gate (`quote-fresh`: ≤ 900s), and the vol input cannot be fabricated because a missing one throws rather than defaulting:
```js
// scripts/lib/math.mjs:55
if (!(w > 0)) throw new Error("no honest vol input -> no band -> no entry");
```
`SKILL.md:147` reinforces it: "No honest vol input → the script refuses — never guess one to get past it."

**And the boundary is defended at the calldata layer too.** `SKILL.md:68-95` is an entire section (§0) existing solely because a model corrupted calldata by reformatting it — "a duplicated `0x` prefix caused real failed submissions." The fix is belt *and* braces: a mechanical pre-submit checklist for the model (`data` chars 0–1 are `0x` and chars 2–3 are not), **and** a code-side normalizer that makes the class of bug unrepresentable:
```js
// scripts/lib/chain.mjs:210-219
export function tx(to, data, label) {
  const d = "0x" + strip0x(String(data)).toLowerCase();
  if (d.length < 10 || !/^0x(?:[0-9a-f]{2})+$/.test(d)) {
    throw new Error(`malformed calldata for "${label}" — refusing to emit tx`);
  }
```
…plus six regression vectors in `selftest.mjs:110-126` that assert the fix, including `"tx() exactly one 0x prefix"`.

---

## 5. CONTRACTS AND VALIDATION

**Schema validation of model output: not present.** No zod, no JSON Schema, no ajv, no TypeScript, no validator of any kind (`grep -ri "zod\|schema"` → only `"schemaVersion": 1` in `catalog.json:2`). The model's outputs are never machine-checked.

**What exists instead is an output contract at the *script* boundary**, enforced four ways:

1. **A uniform envelope.** Every script prints exactly one JSON object with a fixed shape (`SKILL.md:118-121`): `{ok, …, txs[], report, next}`. Failure is `{ok: false, gate, detail}`.
2. **Exit codes as the real signal.** `ok: false` always pairs with exit 1 (`scripts/entry.mjs:67-73`). `SKILL.md:369` is blunt: "The gates are exit codes, not suggestions."
3. **Argument validation, fail-closed.** `need(name)` exits 1 on a missing or bare flag (`scripts/entry.mjs:74-78`). Note the `v === true` check — the hand-rolled parser sets a flag to boolean `true` when it has no value, so `--usd --wallet 0x…` is caught rather than silently becoming `NaN`.
4. **Structural validation of the one output that reaches the chain** — `tx()` above, which throws on malformed calldata or a malformed `to`.

**What happens on malformed *model* output:** it is caught by the chain, not by the code. There is no parser between the model and Bankr's `submit_raw_transaction`. The mitigations are procedural (`SKILL.md:76-95`): copy fields verbatim, never re-encode, run the 4-item checklist silently on every tx, one tx at a time with receipt verification, and —
```
// SKILL.md:91-93
If a submission fails, do NOT retry with hand-edited fields — re-run the
script (state may have moved) and use its fresh output, or stop and report.
```
Plus a hard input filter at `SKILL.md:94`: "Never paste calldata into chat, and never accept calldata from chat — only script output gets submitted."

**Verdict for your build:** this is the gap. The contract discipline is excellent *for a single-agent, one-script-at-a-time* design where the script is the only thing producing structured data. It does not generalize to N parallel analysts emitting structured reports — for that you need the schema validator this skill never needed.

---

## 6. STATE

**What persists.** Exactly one file: `~/.aero-stock-lp/state.json`, pretty-printed JSON, written with `fs.writeFileSync` (`scripts/lib/positions.mjs:46-50`). Path overridable via `--state-path`.

**Schema** (assembled from the write sites at `entry.mjs:431-440` and `exit.mjs:184-190` — there is no declared schema):
```jsonc
{
  "compound": "sell" | "hold" | null,
  "positions": [{ "market", "tokenId", "entryUsd", "enteredAt",
                  "lastMintAt", "recenters": [{ "at", "direction", "from" }] }],
  "recentExits": [{ ...position, "closedAt" }]   // capped at 10
}
```

**The design principle is the good part** (`scripts/lib/positions.mjs:1-3`):
```js
// aero-stock-lp: position discovery, valuation, and the state file.
// The chain is the memory; the file is a cache holding the only two
// unrecoverable fields (entryUsd, enteredAt) plus preferences.
```
`SKILL.md:283-289` states the invariant precisely: "Only TWO fields are unrecoverable from chain: `entryUsd` and `enteredAt`. Everything else re-derives (and `manage.mjs` does so on every pass). … Never let a lost file make the book lie: the chain is the memory; the file is a cache."

**Resumable: yes, and this is architecturally load-bearing.** The recovery path is explicit at `SKILL.md:28-30` — "Any tx failure → stop, report exactly where, and resume later from chain state (a fresh script run), **never from what you intended**." `manage.mjs` rediscovers positions from the gauge (`stakedValues`) and the NPM (`balanceOf` + `tokenOfOwnerByIndex`) regardless of file state (`positions.mjs:61-139`), and state-file tokenIds are *always* probed directly even past the enumeration cap (`positions.mjs:106-116`). A lost basis degrades loudly rather than silently: `basisEstimated: true` (`manage.mjs:165`) and "tell the user loudly and ask for the real entry figure."

**Two state subtleties worth stealing.** (a) The trend-brake history must survive the exit→re-enter cycle, so `exit finish` *parks* the closed record in `recentExits` and `entry settle --recenter-of <oldTokenId>` pulls it forward (`exit.mjs:178-190`, `entry.mjs:410-429`) — "Without this hand-off the brake resets on every recenter," which is exactly the bug `365801e` fixed ("dead trend brake"). (b) A pointer line in the runtime's user-memory store (`SKILL.md:291-300`) because "future sessions start with no conversation history, and the memory line is how they learn positions exist at all." It is deliberately "a POINTER, not a store."

**Scheduled: yes, but externally** — Bankr console automations (§3 above). No cron, no timers, no persistent process in this repo.

---

## 7. EXTERNAL I/O

Complete inventory. **Every external call is unauthenticated — there is no API key, token, or `process.env` read anywhere in the repo** (verified: `grep -rn "process\.env\|privateKey\|PRIVATE_KEY\|mnemonic"` → zero hits).

| # | Endpoint | Auth | Purpose | Site |
|---|---|---|---|---|
| 1 | `https://mainnet.base.org` | none | JSON-RPC (primary) | `markets.mjs:8` |
| 2 | `https://base-rpc.publicnode.com` | none | JSON-RPC (fallback) | `markets.mjs:9` |
| 3 | `https://base.drpc.org` | none | JSON-RPC (fallback) | `markets.mjs:10` |
| 4 | `api.geckoterminal.com/api/v2/networks/base/pools/{pool}` | none | TVL, 24h volume, 24h change, pool creation time | `chain.mjs:177-188` |
| 5 | `api.exchange.coinbase.com/products/AERO-USD/ticker` | none | AERO spot (USD marking + emissions valuation) | `chain.mjs:190-195` |
| 6 | `api.exchange.coinbase.com/products/AERO-USD/candles?granularity=3600` | none | hourly candles → realized vol for the AERO band | `chain.mjs:197-202` |
| 7 | *the model's own market-data / web search* | n/a | **the equity quote** — passed in as `--quote` | `SKILL.md:141-147` |

**Chain: Base mainnet 8453 only.** Hardcoded in three places: `markets.mjs:5`, and literally inside `tx()` (`chain.mjs:218`: `chainId: 8453`). **Nothing on 4663, nothing on USDG, no Robinhood Chain anywhere.**

**Oracles: none.** There is no Chainlink feed, no TWAP, no oracle of any kind. The "price" is `slot0.sqrtPriceX96` — pool spot — for valuation and slippage sizing, cross-checked against a *human/model-supplied* real-world quote only at entry gates. This is the sharpest contrast with your 4663 design, where Chainlink feeds for Robinhood Stock Tokens exist.

**Tokenized stocks — the asset table** (`markets.mjs:32-88`, mirrored for humans at `SKILL.md:342-353`). Assets are **pinned by address**, and the addresses are Base-native Coinbase predeploys at **8 decimals** with a `0xb2…` prefix:

| Market | Token (token1) | Pool | tickSpacing | fee |
|---|---|---|---|---|
| NVDA | `0xb20000000000000000000078ee7ce2fE4908108C` | `0x853f5f1b…7ab9` | 10 | 0.05% |
| AAPL | `0xb200000000000000000000C2e324d24d7eEcd1fb` | `0xa3b1e3f9…94f0` | 10 | 0.05% |
| GOOGL | `0xb2000000000000000000002D0BA3164cc74f58B7` | `0xb1987cad…5542` | 10 | 0.05% |
| META | `0xb2000000000000000000008bC8786B856E61707C` | `0xeaf57753…273e` | 10 | 0.05% |
| AERO | `0x940181a94A35A4569E4529A3CDfB74e38FD98631` (18 dec) | `0xCCd9cC53…9ad4` | 200 | 0.30% |

USDC `0x833589fC…2913` (6 dec) is **token0 in every pool** — an invariant the math depends on (`math.mjs:2`).

**A detail directly transferable to your impersonator-token problem.** `SKILL.md:355-365` handles new listings with an authority rule plus a machine check, not trust:
> token address from an authoritative source only (Coinbase's official listing or the verified Basescan contract — never a user-pasted address alone; predeploys start `0xb2…` and must have 8 decimals). Add the market to `MARKETS` … then run `selftest.mjs --live` — it verifies the pool's gauge, tickSpacing, and reward token on-chain before you touch it.

`selftest.mjs --live` (`selftest.mjs:129-162`) asserts, per market: slot0 price is sane and matches the tick; `pool.gauge()` equals the table's gauge; `pool.tickSpacing()` equals the table's; and `gauge.rewardToken()` is literally AERO. That is an **on-chain attestation of your own address table** — the exact control you need against 4663 impersonators.

**Other infra addresses** (`markets.mjs:19-30`): position managers are *per-pool-family, not global* (`NPM_EQUITY` for CL10, `NPM_AERO` for CL200) — a footgun worth remembering; two routers; the CL gauge factory (for `minStakeTimes`); three CL factory addresses; Multicall3 at the canonical `0xcA11bde0…CA11`.

---

## 8. MONEY PATHS

**The central fact: nothing in this repo can spend or sign. There is no money path in the code at all.** Scripts emit unsigned transaction objects and stop.

```js
// scripts/lib/chain.mjs:218
return { label, to, data: d, value: "0", chainId: 8453 };
```
`SKILL.md:24-30`: "The user's funds stay in their own Bankr wallet. You never hold keys, and neither do the scripts — they emit unsigned `{to, data, value, chainId}` objects." Verified: no `eth_sendTransaction`, no `eth_sendRawTransaction`, no signer, no key material, no `process.env`. The *only* RPC methods used are `eth_call`, `eth_getBalance`, `eth_getTransactionReceipt`, `eth_getTransactionByHash`.

**So the whole system runs in permanent dry-run**, and the signing boundary is Bankr's `submit_raw_transaction`, driven by the model one transaction at a time. Note `value: "0"` is hardcoded — this skill can never move native ETH; the gas top-up is delegated to Bankr's own swap flow, outside the scripts.

**Every transaction the system can ever emit** (exhaustive):

| Tx | Built at | Notes |
|---|---|---|
| `approve(spender, MAX_UINT256)` | `entry.mjs:85-89`, `exit.mjs:157,169,221` | MAX by design — see below |
| `exactInputSingle` (USDC→stock) | `entry.mjs:207-221` | entry swap |
| `mint` (12-word Slipstream tuple) | `entry.mjs:317-333` | |
| `approve(NFT→gauge)` + `gauge.deposit` | `entry.mjs:396-402`, `manage.mjs:192-193` | stake |
| `gauge.withdraw` | `exit.mjs:96`, `manage.mjs:187` | also force-claims AERO |
| `gauge.getReward` | `manage.mjs:209` | compound claim |
| `decreaseLiquidity(full)` | `exit.mjs:98-104` | |
| `collect(MAX_UINT128, MAX_UINT128)` | `exit.mjs:106-108`, `manage.mjs:191` | |
| `exactInputSingle` (stock/AERO→USDC) | `exit.mjs:57-71` | residual sells |
| `burn(tokenId)` | `exit.mjs:176` | explicitly **non-fatal** if it reverts |

**Caps and allowlists.**
- **Ten entry gates, fail-closed, conjunctive** (`entry.mjs:144-184`). The caps: quote age ≤ 900 s; pool within **3%** of the real quote; pool/quote ratio in (0.5, 2) "outside = fictitious price"; TVL ≥ **$20k**; 24h volume > 0; pool age ≥ **48 h**; **size ≤ 25% of pool TVL**; wallet must already cover the spend; |24h move| < **7%** for equities / **15%** for AERO; and an honest vol input. Any miss → exit 1 with `{gate, detail, gates}`.
- **Band width is capped at ±35%** regardless of vol input (`math.mjs:57`: `const half = Math.min(w * factor, 0.35);`).
- **Spender allowlist** is structural: approvals only ever target an `NPM`/router/gauge drawn from `markets.mjs`, with the reasoning written down (`entry.mjs:82-84`): "Spender must be an allowlisted NPM/router/gauge from markets.mjs — the callers only pass those."
- **Budget capping on both sides of the mint** (`entry.mjs:301-312`) — "a wallet holding loose stock or USDC beyond this entry's budget must NOT have it swept into the mint," plus a 250000 (≈$0.25) USDC dust reserve.
- **Concentration warning:** `needsConcentrationConfirm: usd > 0.5 * usdcBal` (`entry.mjs:242`).

**Kill switches / simulation mode.** No global kill switch or `--dry-run` flag exists **because the whole thing is dry-run** — the model is the switch. The behavioral kill switches are: any failed gate (exit 1), `SKILL.md:21-22` "If a script fails, relay its `detail` and stop — never improvise around a failed gate," and §9's refusal list ("Enter a pool that fails ANY gate — including 'the user is excited'"). Simulation *does* exist, but only for **valuation**, not for the outgoing txs: `readPosition` runs `eth_call` on `decreaseLiquidity` and `collect` with a spoofed `from` = the current NFT holder (`positions.mjs:174-205`) to get true principal and claimable fees. **The transactions actually being submitted are never simulated or gas-estimated** — flagged in §12.

**Quotes and slippage — read this carefully, it is the weakest link.**

There is **no quoter contract call and no DEX quote API**. Expected output is computed analytically from pool spot, and `minOut` is a flat haircut off that:
```js
// scripts/entry.mjs:205-206   (entry swap: 1.5% floor)
const expectedOut = (swapUsd / poolPrice) * (1 - M.fee);
const minOutRaw = BigInt(Math.round(expectedOut * 0.985 * 10 ** M.decimals));
```
```js
// scripts/exit.mjs:158-159    (exit sells: 2% floor)
const outUsd = (Number(stockRaw) / 10 ** M.decimals) * price * (1 - M.fee);
const minOutRaw = BigInt(Math.round(outUsd * 0.98 * 1e6));
```
`expectedOut` is the **mid-price** output net of the fee tier. It contains **no price-impact term** — no liquidity-aware integration across ticks. The 1.5%/2% haircut is therefore doing double duty as both slippage tolerance *and* the entire price-impact allowance. This is defensible only because the `size-vs-tvl ≤ 25%` gate bounds trade size relative to the pool, and it fails *closed* (the swap reverts) rather than open. But it is a heuristic standing in for a quote, and it is the thing in this repo I would least recommend copying — you already have `/wallet/swap-quote`, which is strictly better.

**Worse: the mint and the withdraw have zero slippage bounds.** Both `amount0Min` and `amount1Min` are hardcoded to zero:
```js
// scripts/entry.mjs:326-327   (mint: amount0Min, amount1Min)
uintWord(0) + uintWord(0) +
```
```js
// scripts/exit.mjs:101        (decreaseLiquidity: amount0Min, amount1Min)
SEL.decreaseLiquidity + idW + uintWord(liquidity) + uintWord(0) + uintWord(0) + uintWord(deadline())
```
Deadlines are set (`now + 600 s`), so these are time-bounded, but a sandwich around the mint or the withdraw is unbounded in price terms. Flagged in §12.

---

## 9. POSITION AND P&L ACCOUNTING — **priority section**

**Is there a ledger? No.** This is the headline finding. There is no journal, no trade log, no fills table, no realized-P&L record, no cost-basis lots, no gas accounting, no fee accounting. Nothing is append-only. The entire accounting model is:

> **`pnl = (live chain valuation) − (one scalar `entryUsd` cached in a JSON file)`**

**Write path.** One scalar, once, at `entry.mjs settle`:
```js
// scripts/entry.mjs:407
const entryUsd = args["entry-usd"] !== undefined ? Number(args["entry-usd"]) : null;
```
…pushed into `state.positions[]` alongside `enteredAt` (`entry.mjs:431-440`) and `saveState`d. Note `entryUsd` is **whatever the agent passed on the command line** — it is not measured from the swap receipt, not recomputed from the mint amounts, not reconciled against anything. The `size` phase knows the true deployed amounts (`amount0Usdc`, `amount1Stock`, `entry.mjs:342-343`) and they are never persisted. On exit, the record is moved to `recentExits` (`exit.mjs:185-190`) and then aged out at 10 entries — after which the position's history is gone.

**Cost basis: a single USD scalar, no lots, no token-level basis.** There is no per-token cost basis (no "N shares of AAPL at $X"), no FIFO/LIFO/average-cost machinery, no partial-position accounting. A recenter closes the old basis and opens a new one from a fresh `--entry-usd`; the chain of basis across recenters is **not** linked (only the *trend-brake* history is carried forward via `--recenter-of`, `entry.mjs:414-429` — not the basis).

**Unrealized P&L — the computation.** `manage.mjs:104-168`:
```js
// scripts/manage.mjs:111-117
const earnedUsd = spot ? p.earnedAero * spot : 0;
const value = p.principalUsd + p.feesUsd + earnedUsd;
totalUsd += value;
const basis = rec?.entryUsd ?? null;
const pnl = basis !== null ? value - basis : null;
```
The three components of `value` come from `readPosition` (`positions.mjs:207-227`):
- `principalUsd` — from the **`eth_call` simulation of `decreaseLiquidity(full liquidity)`** with a spoofed `from`, converted at pool price. This is genuinely good: it's the exact token amounts a full withdraw would return right now, not a reimplementation of the v3 liquidity formula.
- `feesUsd` — from the **`eth_call` simulation of `collect(MAX_UINT128, MAX_UINT128)`**, wrapped in try/catch because "collect sim can revert on zero-fee positions" (`positions.mjs:203-205`).
- `earnedUsd` — `gauge.earned(wallet, tokenId)` × Coinbase AERO spot.

**What prices it marks against.** `principalUsd` and `feesUsd` are marked at **pool spot** (`priceFromSqrtX96(slot0.sqrtPriceX96)`, `positions.mjs:207`) — *not* against the real-world equity quote, even when the agent passed one via `--quote-AAPL`. The `--quote-<MARKET>` argument is read exactly once, at `manage.mjs:227`, and used **only** to gate re-entry — never to mark the book. AERO is the one thing marked to an off-chain venue (Coinbase spot). So: **the equity book is marked to the AMM, with no NAV check at valuation time.** For a tokenized-equity fund publishing statements, that is a materially different choice from marking to Chainlink, and it means a stale or manipulated pool marks the book.

**Realized P&L: not computed anywhere.** `exit finish` returns the basis and **delegates the arithmetic to the model in prose**:
```js
// scripts/exit.mjs:200
report: `Finishing exit of ${market} #${tokenId}: ${txs.length} txs; user lands in USDC. Report the full life-of-position P&L vs basis${rec?.entryUsd != null ? ` ($${rec.entryUsd})` : " (basis unknown — say so)"}.`,
```
This is the **one place the skill breaks its own LLM-vs-deterministic boundary** — the single most audit-sensitive number in the system, life-of-position realized P&L, is left to the model to compute from a sentence. Nothing verifies it and nothing records it.

**Four concrete accounting holes.**

1. **Doc/code divergence on loose balances — the skill says one thing, the code does another.** `SKILL.md:313-315` is emphatic:
> Value = principal + claimable fees/emissions + LOOSE wallet balances (mint remainders are real book money — `manage` includes them; a P&L that ignored them once showed −$17 on a healthy $1,223 position).

But `manage.mjs:112` computes `value = principalUsd + feesUsd + earnedUsd` — **loose balances are not in `value`, not in `valueUsd`, not in `pnlUsd`, and not in `totalPnl`.** They are computed separately (`manage.mjs:254-270`) and appended to the *total* line as a trailing clause (`manage.mjs:273`): `` `Total: $X in positions…; loose wallet balances ~$Y.` ``. So the exact bug the comment memorializes (a mint remainder making a healthy position read negative) **is still present in every per-position P&L line** — it has only been papered over at the portfolio total, and even there as a separate figure rather than a corrected one. This is the single clearest defect I found.

2. **Compounded AERO silently becomes a P&L loss.** Claim + sell converts `earnedAero` into loose USDC. `earnedUsd` then drops to 0, so `value` drops by the claimed amount, so `pnl = value − basis` falls by exactly the amount the user just realized as profit. Nothing credits it back. Per-position P&L systematically understates by cumulative realized emissions.

3. **Gas is never accounted.** Every sequence spends Base ETH across 3–7 transactions; no script reads a receipt's `gasUsed`, and gas appears in the P&L nowhere. `reentryCost` (`manage.mjs:219`) is a *forward-looking estimate* used only as a rebalance hurdle — never a booked cost:
```js
const reentryCost = value * (M.fee * 0.5 + 0.005) + 0.05;
```
4. **The book cannot be reconstructed.** With no ledger and a 10-entry `recentExits` ring, there is no way to produce a period statement, an attribution, or a tax lot. For your accountability layer this is a non-starter — it is precisely the thing you would have to build from scratch.

**Reporting discipline, on the other hand, is excellent and worth copying wholesale** (`SKILL.md:311-331`): impermanent loss is named as real loss, not excused; yields may never be annualized as promises — the only forward number allowed is `projectedAprPct`, always labeled "at this epoch's rate" and marked gross and in-range-conditional; out-of-range positions get "earning nothing" and never an APR; estimated basis is flagged inline (`basisEstimated`, `manage.mjs:165`); and **claims transparency is mandatory on every exit/recenter** — state exactly what was claimed, or why nothing was ("0 AERO accrued — position was out of range before the exit"). The APR calculation itself (`manage.mjs:120-147`) prefers *measured* return since entry and only falls back to pot-share projection when there's no history.

---

## 10. x402

**Neither publishes nor consumes. Zero occurrences of `x402` in the repository** (`grep -ril x402` → no hits across all 11 files). No HTTP server, no paywall, no payment-required handling, no signed decision record, no paid endpoint. The skill is a CLI + prompt; it has no served surface at all.

Nothing to report on flow. **This repo answers none of your x402 open questions.**

---

## 11. FAILURE HANDLING

**Timeouts: not present.** No `AbortController`, no `signal`, no timeout option on either `fetch` call (verified by grep: `setTimeout`, `AbortController`, `timeout` all zero hits in `scripts/`). A hanging RPC or a hanging GeckoTerminal request stalls the pass indefinitely. This is the most significant operational gap for a scheduled, unattended automation firing every 2 hours.

**Retries and backoff: one narrow form, no backoff.** The only retry is RPC endpoint rotation — a single pass over three URLs with no delay and no jitter:
```js
// scripts/lib/chain.mjs:55-75
export async function rpc(method, params) {
  let lastErr;
  for (let attempt = 0; attempt < RPCS.length; attempt++) {
    const url = RPCS[(rpcIndex + attempt) % RPCS.length];
    try { … rpcIndex = (rpcIndex + attempt) % RPCS.length; // stick with what worked
      return body.result;
    } catch (e) { lastErr = e; }
  }
  throw new Error(`all RPCs failed for ${method}: ${lastErr}`);
}
```
The sticky-index trick (remember which endpoint worked, start there next time) is a nice cheap touch. But: **the HTTP-only endpoints get no retry at all** — `geckoPool`, `aeroSpot` and `aeroHourlyCandles` go through `httpJson` (`chain.mjs:171-175`), which throws on the first non-2xx.

**Rate-limit headers: not present.** No `Retry-After`, no `X-RateLimit-*`, no 429 special-casing. `httpJson` treats 429 identically to 500. GeckoTerminal's public tier is rate-limited, and `manage.mjs:77-81` fires one request per market in the book with no throttle. Flagged.

**Partial-failure aggregation: this part is genuinely well done.** Multicall3 is called with `allowFailure = true` (`chain.mjs:114`), and **every single decode site checks `.ok` before reading**, with an explicit choice per field about whether the failure is fatal or degradable:

- *Fatal* — core reads: `if (!slot0.ok || !pos.ok || !owner.ok) throw` (`positions.mjs:162-164`); `if (!slot0Res.ok) fail("rpc", "slot0 read failed")` (`entry.mjs:114`, `entry.mjs:273`).
- *Fatal by deliberate choice, with the reasoning written down* (`exit.mjs:143-147`):
```js
// Fail closed: a failed balance/price read here would silently skip a
// residual sell while the report claims the user lands in USDC.
if (!stockBalRes.ok || !aeroBalRes.ok || !slot0Res.ok || !aeroSlot0Res.ok) {
  out({ ok: false, gate: "rpc", detail: "balance/price reads failed — cannot size residual sells; re-run finish" }, 1);
}
```
- *Degradable, with a documented default* — `skim` falls back to 0.1 (`entry.mjs:384`), `minStake` to 300 s (`manage.mjs:90`), `earned`/`rewardRate`/pool liquidity to 0 (`positions.mjs:222-226`), and `manage.mjs` wraps `aeroSpot`, `ethBalance` and `geckoPool` in `.catch(() => null)` (`manage.mjs:70-80`) so a price-feed outage degrades the *report* rather than killing the pass — downstream code then guards on `spot &&` / `g &&`.

**Three sharper observations.**
- **Asymmetric third-party dependency.** `manage.mjs` tolerates a GeckoTerminal outage; `entry.mjs plan` does not — `geckoPool(M.pool)` at `entry.mjs:104` is un-caught, so an outage rejects the `Promise.all`, hits the top-level `.catch` at `entry.mjs:479`, and reports `gate: "error"`. Entries are therefore blocked by a single unauthenticated third-party API with no retry. Fail-closed, but brittle for an automated system.
- **Deadline vs. sequence duration.** `deadline()` is `Date.now() + 600 s` evaluated when the *script* runs (`entry.mjs:80`), but the txs it emits are submitted serially with a mine-and-verify wait between each. A 3–7 tx sequence on a congested block or a slow confirmation can exceed 600 s, and the later txs revert on deadline. The recovery path (re-run the script for fresh output) handles it, but it will happen.
- **Non-fatal failure is named explicitly where it matters** — the burn (`exit.mjs:176`): `` `burn #${tokenId} (NON-FATAL if it reverts — funds are already out)` ``, carried through to `SKILL.md:130`. Encoding "which failures don't matter" *into the tx label the operator reads* is a small idea with a high hit rate.

---

## 12. VERDICT

### Patterns worth stealing

**1. Move deterministic work out of the prompt into bundled scripts — and say so in one paragraph at the top.** `SKILL.md:14-22`. Commit `9e9b03c` did exactly this as a refactor, which means it was learned, not designed. Your supervisor/worker split needs the same sentence: analysts judge, aggregator computes.

**2. Gates as a declarative array of `{name, pass, value, limit}`, evaluated by `find(g => !g.pass)`, failing to a non-zero exit code.** `entry.mjs:144-184`. The `value` and `limit` fields exist so the *failure message is self-explaining* without prose, and `SKILL.md:36-37` then instructs: report only failures, with the number. This is the cleanest risk-agent-veto primitive I have seen in a skill — your risk agent should emit exactly this shape, and your treasurer should refuse on a non-empty failure list.

**3. Localize the one inversion that models get wrong, once, with a comment saying why.** `math.mjs:1-4`. Then assert it in a test (`selftest.mjs:52-56`, `"inversion: high price -> lower tick"`). Applies directly to your `uiMultiplier` handling — put it in one function, note that Chainlink already includes it, and vector-test it.

**4. `tx()` as a validating constructor that is the *only* way to emit calldata.** `chain.mjs:210-219`. It normalizes the prefix, regex-validates the hex, validates the address, and refuses otherwise. The six regression vectors at `selftest.mjs:110-126` lock in a real production bug (`0x0x`, fixed in `365801e`). Your treasurer should have exactly one such chokepoint for the `/wallet/swap` payload.

**5. `selftest.mjs --live` as an on-chain attestation of your own address table.** `selftest.mjs:129-162` verifies `pool.gauge()`, `pool.tickSpacing()` and `gauge.rewardToken()` against the hardcoded table before you touch anything. Given impersonator tokens on 4663, make this a **preflight on every run**, not a first-use ritual — assert each pinned address still reports the symbol, decimals and pool you expect.

**6. "The chain is the memory; the file is a cache" — and prove it by naming the unrecoverable fields.** `positions.mjs:1-3`, `SKILL.md:283-289`. Exactly two fields can't be re-derived, so exactly two are persisted, and a lost cache degrades loudly (`basisEstimated: true`) instead of lying. Your frozen-snapshot-by-id design should be able to state its unrecoverable set just as crisply.

**7. Valuation by `eth_call` simulation with a spoofed `from`, rather than reimplementing protocol math.** `positions.mjs:174-205`. Simulating `decreaseLiquidity`/`collect` gets exact principal and claimable fees from the protocol itself. Cheaper and more correct than porting the AMM formulas into your mark-to-market.

**8. Bounded fan-out in 8 lines: chunk at 50, drain with 4 workers over a shared cursor.** `chain.mjs:91-110`. Plus `ENUM_CAP = 400` with truncation *surfaced* in the output (`manage.mjs:291`), not swallowed. This is the pattern for your N-analyst fan-out — a fixed worker pool and a visible truncation flag.

**9. Hysteresis and brakes as first-class, stateful concepts.** Route switches need `1.3×` (`manage.mjs:60`); rebalances need cost hurdle **∧** trend brake **∧** fresh quote (`manage.mjs:218-243`); and `SKILL.md:174` is a hard rule: "IN RANGE = HOLD… NEVER recenters a position that is in range." Critically, the brake's history is **carried across the exit/re-enter boundary** via `recentExits` + `--recenter-of` (`exit.mjs:178-190`, `entry.mjs:410-429`) — commit `365801e` fixed the "dead trend brake" where it silently reset. Any rebalancing fund needs this; almost none have it.

**10. The single-confirmation contract.** `SKILL.md:52-66`: exactly one confirmation per money-spending sequence, folding in *everything* the sequence will do (gas top-up, stake, residual sells), then zero further check-ins. "Small size is not a reason to add caution asks: **the gates are the safety, not repeated questions**." That last clause is the right policy for an autonomous treasurer.

**11. Honest-reporting rules as enforceable clauses.** `SKILL.md:311-331`: no promised or annualized yields; the only forward number is a labeled epoch-rate APR; IL named as real loss; estimated basis flagged inline; **mandatory claims transparency** on every exit/recenter, including the negative case with its reason. Lift this section almost verbatim into your accountability layer.

**12. Encode non-fatality in the operator-visible label.** `exit.mjs:176`. Small, cheap, effective.

### Anything fragile we shouldn't copy

1. **`minOut` derived from mid-price with a flat 1.5%/2% haircut and no price-impact term.** `entry.mjs:205-206`, `exit.mjs:158-159`. No quoter, no tick-walk. It only holds because `size-vs-tvl ≤ 25%` bounds the trade. **You have `/wallet/swap-quote` — use it; do not port this.**
2. **`amount0Min`/`amount1Min` hardcoded to 0 on both `mint` and `decreaseLiquidity`.** `entry.mjs:326-327`, `exit.mjs:101`. Deadline-bounded but not price-bounded; unbounded sandwich exposure on the two largest-value operations.
3. **Emitted transactions are never simulated or gas-estimated before submission.** Simulation exists for valuation only. A gate can pass and the tx still revert.
4. **Loose balances excluded from per-position `value`/`pnlUsd` despite `SKILL.md:313` stating they are included** (`manage.mjs:112` vs `manage.mjs:254-273`). The documented −$17-on-$1,223 bug survives at the position level. **Do not copy the pattern of asserting an accounting rule in prose that the code does not implement** — if your statements say "value includes X," a test must prove it.
5. **Realized P&L delegated to the model in a `report` string** (`exit.mjs:200`). The system's one audit-critical number escapes its own deterministic boundary. In your design this must be computed by the aggregator and signed.
6. **No ledger, no gas accounting, compounded AERO silently depressing P&L** (§9). Not reconstructable, not auditable, not statement-ready.
7. **No timeouts on any network call; no retry or backoff on HTTP; no 429/`Retry-After` handling.** `chain.mjs:60`, `chain.mjs:171-175`. Unacceptable for an unattended 2-hourly automation.
8. **`entry.mjs plan` hard-fails on a GeckoTerminal outage** (`entry.mjs:104`, un-caught) while `manage.mjs` tolerates it — inconsistent resilience, and entries gated on one unauthenticated third-party API.
9. **`deadline()` fixed at script time (+600 s) but consumed across a multi-transaction, multi-block sequence.** `entry.mjs:80`.
10. **`Number(BigInt)` on liquidity values** throughout the ratio math (`entry.mjs:392-393`, `manage.mjs:131-143`, `positions.mjs`). Liquidity routinely exceeds 2^53; these are ratios so relative error is small, but it is silent precision loss in numbers that reach the user as APR.
11. **`found.truncated = enumTruncated` sets an ad-hoc property on an array** (`positions.mjs:137`). Works, survives the one `.filter`-free path it takes, but breaks silently the moment anyone maps or spreads it.
12. **Infinite (`MAX_UINT256`) approvals** (`entry.mjs:88`). Justified in-comment ("pool math rounds amounts owed up a wei and an exact allowance makes mint revert STF") and the spender set is allowlisted — but for a fund with a treasurer, a revoke path should exist.
13. **Hand-rolled ABI encoding and hardcoded 4-byte selectors** (`markets.mjs:90-124`). Impressive and well-tested, but every selector is a silent-failure surface if a contract is ever swapped for a different implementation.

### Direct answers to your open questions

**Q: Any working x402 server or client beyond the Bankr CLI?**
**No.** Zero occurrences of `x402` in this repo. It contributes nothing here.

**Q: A production agent fan-out with schema-validated outputs?**
**No, on both halves.** Single agent, no fan-out (§3). And no schema validation anywhere — no zod, no JSON Schema, no TypeScript (§5). What it does have is the *adjacent* pattern: a rigid script→JSON envelope (`{ok, txs[], report, next}`) with exit codes as the contract, a bounded 4-worker RPC pool, and a validating constructor at the one point where data becomes irreversible. Steal the envelope discipline and the `tx()` chokepoint; you still have to build the validator.

**Q: Portfolio accounting — cost basis, realized P&L, mark-to-market?**
- **Cost basis:** one USD scalar per position, agent-supplied, unverified, cached in `~/.aero-stock-lp/state.json`, aged out 10 exits after close. No lots, no token-level basis, no basis chained across recenters.
- **Realized P&L:** **not computed by code at all** — delegated to the model in prose at `exit.mjs:200`.
- **Mark-to-market:** live and genuinely well-built — `eth_call` simulation of `decreaseLiquidity` + `collect` (`positions.mjs:174-205`) — but marked at **AMM pool spot**, not against the real-world quote the agent already holds and not against any oracle. AERO alone is marked to Coinbase spot.
- **Gas: never accounted. Loose balances: excluded from per-position P&L despite the docs. No ledger of any kind.**

**Net:** this repo answers *none* of your three open questions affirmatively. Its value is entirely in §4 (the LLM/deterministic boundary), §8's gate stack, and the negative space in §9 — it shows you precisely which accounting pieces a skill like this omits, and every one of them is something your accountability layer must supply.

### Anything contradicting the verified facts

**Nothing contradicts them.** The repo operates in a disjoint domain — Base 8453, Aerodrome Slipstream, Coinbase-backed equity predeploys, raw router calldata — and never touches Robinhood Chain 4663, USDG, `llm.bankr.bot`, x402, or the `/wallet/swap-quote` → `/wallet/swap` API. Three adjacent observations, offered as context rather than correction:

1. **It bypasses the Bankr trade API entirely.** It never calls `/wallet/swap-quote` or `/wallet/swap`; it builds `exactInputSingle` calldata by hand and submits via Bankr's **arbitrary-transaction** flow (`submit_raw_transaction`, `SKILL.md:69-71`). So it is not evidence about that API either way — but it does demonstrate that the raw-calldata path is production-viable when the swap endpoint doesn't fit.
2. **Your "addresses not tickers" and "pin assets by address" instincts are independently corroborated.** `markets.mjs` pins every asset by address; `SKILL.md:355-365` refuses user-pasted addresses, requires the `0xb2…`/8-decimal shape, and makes `selftest --live` verify gauge, tickSpacing and reward token on-chain before first use.
3. **Slipstream's `exactInputSingle` takes `tickSpacing`, not `fee`** (`markets.mjs:117`: `// 8-word static tuple (tickSpacing, not fee)`), and `mint` is a **12-word static tuple** with a trailing `sqrtPriceX96` (`markets.mjs:112`). If you use Uniswap v4 on 4663, neither encoding transfers — v4 is singleton/hook-based with a completely different call surface. Treat any calldata in this repo as Aerodrome-specific.

---

## Summary

**What I did.** Located the requested target: `./aerofun` does not exist anywhere on this filesystem (`find / -maxdepth 7 -iname "*aerofun*"` → empty; `grep -ril aerofun repo_research/` → empty). Per your direction, analyzed `repo_research/skills/aero-stock-lp` instead — all 11 files read in full (2,315 lines), git provenance traced (8 commits, BankrBot/skills, Igor Yuzovitskiy, 2026-08-21 → 2026-08-27), and `node scripts/selftest.mjs` executed to verify claims independently (**34/34 pass, exit 0**). Report covers all 12 requested sections with file:line evidence; "not present" used in place of inference throughout, and the two inferred items (deadline-overrun risk, unbounded `Promise.all` in `manage.mjs`) are flagged as such in context.

**Files created.** `research/aerofun.md` (this file). No other files created or modified; the target repo was read-only throughout.

**Headline findings.**
- **Relevant, but on shape rather than surface.** Tokenized equities, Aerodrome CL pools, gate-based risk control, and a rigorously enforced LLM/deterministic boundary — but **zero** x402, **zero** chain 4663, **zero** USDG, no agent fan-out, no schema validation, no ledger.
- **§9 is the priority answer and it is mostly negative:** no ledger, cost basis is one unverified agent-supplied scalar, **realized P&L is computed by the model in a prose string** (`exit.mjs:200`), gas is never accounted, and loose balances are excluded from per-position P&L *despite `SKILL.md:313` stating they are included* — the clearest defect found.
- **Best thing to steal:** the gate array (`entry.mjs:144-184`), the `tx()` validating chokepoint plus its regression vectors (`chain.mjs:210-219`, `selftest.mjs:110-126`), `selftest --live` as on-chain attestation of your own address table (`selftest.mjs:129-162`), and the trend-brake history carried across the exit/re-enter boundary (`exit.mjs:178-190`).
- **Worst thing to copy:** mid-price `minOut` with no price-impact term, and `amount0Min`/`amount1Min` hardcoded to `0` on both `mint` and `decreaseLiquidity`.

**Follow-up actions for you.**
1. **Decide the real `aerofun` target.** If it is a GitHub repo (`aero.fun`?), give me the URL and I'll run the same 12-section pass against it — this report can then be renamed or sit alongside it.
2. **Worth a decision now:** whether your mark-to-market uses Chainlink (which you've verified exists on 4663 with `uiMultiplier` baked in) or AMM spot. This repo chose AMM spot and has no oracle at all; for a fund publishing signed statements, that choice is load-bearing and hard to reverse later.
3. **Your ledger is greenfield.** Nothing here is reusable for cost basis, realized P&L, or per-analyst attribution — budget for it as original work rather than adaptation.
