# Discovery report: `bankr-claude` (upstream `BankrBot/claude-plugins`)

Research only. No code was written, no changes proposed to this repo.

**Scope note up front:** this repo is **not an application and not an agent system**. It is a
Claude Code *plugin marketplace* — a bundle of markdown skills, agent definitions, slash commands,
and one small MCP server. 69 files, ~7,095 lines, 848K on disk. Only **~750 lines are executable
code**; the rest is prose. Several sections of the requested brief (state/persistence, money
guardrails, retry utilities, config modules) have honest answers of **"not present"** — recorded
below rather than guessed at.

A `codebase-explainer` skill was not available in this environment (checked `~/.claude/skills/`
and the three installed plugins), so this was done by direct reading.

---

## 1. ORIENTATION

### What it actually does

This repo packages three Claude Code plugins that teach an LLM how to talk to Bankr's hosted
crypto-agent infrastructure. It ships **no trading logic of its own**. The whole product is
(a) a 376-line MCP server that is a thin, stateless HTTP proxy to three Bankr endpoints, and
(b) ~40 markdown documents that get injected into an LLM's context so it phrases its natural-
language prompts to Bankr correctly. The intelligence lives server-side at `api.bankr.bot`;
this repo is the client-side instruction manual plus a transport shim.

The three plugins (`.claude-plugin/marketplace.json`):

| Plugin | Purpose |
|---|---|
| `bankr-agent` | End-user: talk to Bankr from Claude Code via MCP |
| `bankr-agent-dev` | Developer: scaffold TS projects against the **Agent API** (API-key auth) |
| `bankr-x402-sdk-dev` | Developer: scaffold TS projects against **`@bankr/sdk`** (x402 pay-per-call) |

### Entry points

There is one real runtime entry point and several LLM-mediated ones.

1. **MCP server over stdio** — the only process this repo starts.
   `bankr-agent/mcp-server/src/index.ts:367-376`:
   ```ts
   async function main() {
     const transport = new StdioServerTransport();
     await server.connect(transport);
     console.error("Bankr Agent MCP server running on stdio");
   }
   ```
   Launched by Claude Code from `bankr-agent/.mcp.json`:
   ```json
   { "mcpServers": { "bankr-agent-api": {
       "command": "node",
       "args": ["${CLAUDE_PLUGIN_ROOT}/mcp-server/dist/index.js"] } } }
   ```
   Note it runs **`dist/index.js`**, a committed minified build (see §5).

2. **Subagent** — `bankr-agent/agents/bankr-agent.md`, auto-triggered by its `description`
   frontmatter when the user mentions crypto/trading/Polymarket.

3. **Slash commands** — `/bankr-agent <query>` (`bankr-agent/commands/bankr-agent.md`),
   `/bankr-agent-dev:scaffold`, `/bankr-x402-sdk-dev:scaffold`.

4. **Skills** — 40 `SKILL.md` files, pulled in on demand by description-matching.

No cron, no HTTP server, no CLI binary, no `main` package script. `package.json` declares
`"validate": "node scripts/validate-plugins.js"` but **`scripts/` does not exist** in the repo.

### Directory map

```
.claude-plugin/       Marketplace manifest listing the 3 plugins
.github/workflows/    One CI job: builds the MCP server and commits dist/ back to the branch
bankr-agent/          End-user plugin: MCP server (the only real code) + 14 skills + agent + command
bankr-agent-dev/      Dev toolkit for the Agent API: 16 skills + scaffold command + 2 TS examples
x402-sdk-dev/         Dev toolkit for @bankr/sdk: 8 skills + sdk-assistant agent + scaffold command
research/             This report (created by this task; not part of the upstream repo)
```

---

## 2. AGENT ARCHITECTURE

### Shape: single agent + skill router. No multi-agent anything.

There are two agent definitions (`bankr-agent`, `sdk-assistant`) but they never talk to each
other and never spawn subagents. Each explicitly describes itself as a router over *documents*,
not over agents — `bankr-agent/agents/bankr-agent.md:46`:

```md
You are a **skill router** - identify what the user needs and load the appropriate skill for
detailed guidance. Don't duplicate skill content; reference and load skills instead.
```

`x402-sdk-dev/agents/sdk-assistant.md:35` is the same sentence verbatim. The routing target is
a lookup table of skill names (`bankr-agent.md:52-74`), and the "hop" is the host harness loading
a markdown file into context — not an agent invocation.

There **is** a second agent in the picture, but it is remote and opaque: the Bankr agent behind
`POST /agent/prompt`. The architecture is therefore **local LLM → natural-language string →
remote black-box agent**. Everything this repo controls is on the near side of that string.

### Where prompts live

All prompts are **standalone markdown files with YAML frontmatter** — never inline strings, never
templated. Three kinds:

- `*/skills/<name>/SKILL.md` — 40 of them, `name` + `description` + `version` frontmatter.
- `*/agents/*.md` — system prompts with `description`, `model: inherit`, `color`, optional `tools`.
- `*/commands/*.md` — `description`, `argument-hint`, `allowed-tools`; `$ARGUMENTS` is the only
  interpolation mechanism (`bankr-agent/commands/bankr-agent.md:6`).

The one place a prompt is assembled programmatically is string concatenation in a *user*-facing
doc, not in code — `bankr-agent-dev/skills/bankr-arbitrary-transaction/SKILL.md:86`:
```ts
const prompt = `Submit this transaction: ${JSON.stringify(tx)}`;
```

### Invocation: sequential, with one documented parallel pattern

The live path is strictly sequential: submit → poll every 2s → read terminal state. Code path
for a single call, `mcp-server/src/index.ts:283-310` → `submitPrompt()` at `:97-120` → one
`fetch` to `POST /agent/prompt`. Polling is **not** in the server; it is delegated to the calling
LLM by returning an instruction string (`:307`):

```ts
text: `Prompt submitted successfully.\n\nJob ID: ${result.jobId}\n...\nUse
bankr_agent_get_job_status with this job ID to check for results. Poll every 2 seconds
until status is "completed", "failed", or "cancelled".`
```

That is the actual control loop: the model is told, in prose, to keep calling a tool. There is
no timeout, no attempt cap, and no state on the server side enforcing it.

The only parallelism anywhere is a documented (not executed) fan-out in
`x402-sdk-dev/skills/sdk-job-management/SKILL.md:76-86`:
```ts
const jobs = await Promise.all(prompts.map(prompt => client.prompt({ prompt })));
const results = await Promise.all(jobs.map(job => client.pollJob({ jobId: job.jobId })));
```
Submit-all-then-poll-all, unbounded concurrency, no error isolation — `Promise.all`, not
`allSettled`, so one rejection discards every sibling result.

### Contract between components

| Boundary | Contract |
|---|---|
| User → agent | Free text |
| Agent → skill | Nothing; skill is a context injection, not a call |
| Agent → MCP tool | JSON Schema, hand-written inline (`index.ts:231-241`) — one `prompt` string |
| MCP → Bankr API | `{ "prompt": string }` JSON body |
| Bankr API → MCP | Typed-at-compile-time-only `JobStatusResponse` (`index.ts:79-94`) |
| MCP → agent | **Flat newline-joined text** — the interfaces are thrown away |

The last row is the important one. The TS interfaces exist for the developer's editor and are
erased before the data reaches the model.

### Malformed output handling: **nothing**

No runtime validation anywhere in the repo. No `zod`, no `ajv` use, no schema check, no repair
pass, no retry on bad shape. `response.json()` is returned directly and its type is *asserted*:

`mcp-server/src/index.ts:134-143`:
```ts
  if (!response.ok) {
    if (response.status === 401) { throw new Error(API_KEY_INVALID_ERROR); }
    const errorText = await response.text();
    throw new Error(`API request failed: ${response.status} - ${errorText}`);
  }
  return response.json();
```
The function signature promises `Promise<JobStatusResponse>`; a 200 response with an entirely
different body would satisfy it silently and surface as `undefined` fields in `formatJobStatus`.

HTTP status **is** checked (401 gets a bespoke message), and `success: false` is handled for
submit only (`:291-301`). Job-level failure is handled by *printing* `status.error`, not by
acting on it.

### Compression between steps

One function, and it is the most reusable idea in the repo. `mcp-server/src/index.ts:170-208`
collapses the full JSON job record into a short text block before it re-enters the model's
context — dropping `richData` base64 blobs, raw calldata, gas, and timestamps entirely:

```ts
function formatJobStatus(status: JobStatusResponse): string {
  const lines: string[] = [];
  lines.push(`Job ID: ${status.jobId}`);
  lines.push(`Status: ${status.status}`);
  lines.push(`Prompt: ${status.prompt}`);
  ...
  if (status.transactions && status.transactions.length > 0) {
    lines.push("\nTransactions:");
    for (const tx of status.transactions) {
      if (tx.metadata?.humanReadableMessage) {
        lines.push(`  - ${tx.metadata.humanReadableMessage}`);
      } else { lines.push(`  - ${tx.type}`); }
    }
  }
```

Note `humanReadableMessage` is produced **server-side by Bankr** — the API is designed so that
every transaction ships with its own pre-written one-line summary for exactly this purpose.

Also worth noting: incremental status updates are tracked by index so only *new* ones are shown.
`bankr-agent-dev/skills/bankr-client-patterns/SKILL.md:270-274`:
```ts
    if (onProgress && status.statusUpdates) {
      for (let i = lastUpdateCount; i < status.statusUpdates.length; i++) {
        onProgress(status.statusUpdates[i].message);
      }
      lastUpdateCount = status.statusUpdates.length;
    }
```

---

## 3. BOUNDARY: LLM vs DETERMINISTIC CODE

The boundary is drawn in an unusually extreme place: **the LLM decides everything of consequence,
and the code does transport only.**

| Decided by an LLM | Decided by plain code |
|---|---|
| Which skill to load | HTTP method/URL/header assembly |
| Which tool to call, with what prompt string | 401 → bespoke error message |
| Ticker, chain, direction, and **amount** of every trade | Presence of `prompt` / `job_id` args |
| When to stop polling | String formatting of the job record |
| Whether a result means success | — |
| Slippage, routing, execution (remote Bankr agent) | — |

**Is any arithmetic, ranking, or thresholding done by the LLM?** In this repo — yes, all of it,
because there is no arithmetic in the code to compare against. The entire numeric surface of the
codebase is three expressions:

1. Poll bookkeeping — `mcp-server` has none; in the shipped client template,
   `bankr-client-patterns/SKILL.md:262-266`:
   ```ts
   const pollInterval = options?.pollInterval || 2000;
   const maxAttempts = options?.maxAttempts || 150; // 5 minutes max
   for (let attempt = 0; attempt < maxAttempts; attempt++) {
   ```
2. Timeout comparison — `polling-with-updates.ts:37`: `while (Date.now() - startTime < maxDuration) {`
3. Rate-limit backoff — `bankr-safety/SKILL.md:90`: `const retryAfter = error.resetAt - Date.now();`

Everything financial is a string the model wrote. The *only* numeric guard in the whole repo is
a regex/allowlist check in a doc snippet, `bankr-arbitrary-transaction/SKILL.md:76-83`:

```ts
  if (!tx.to.match(/^0x[a-fA-F0-9]{40}$/)) { throw new Error("Invalid address format"); }
  if (!tx.data.startsWith("0x")) { throw new Error("Calldata must start with 0x"); }
  if (![1, 137, 8453, 130].includes(tx.chainId)) { throw new Error("Unsupported chain"); }
```
That validates *shape*, not value — and it is a documentation example, not executed code. There
is no amount cap, no notional check, no ranking, no threshold anywhere.

The amounts themselves are explicitly natural-language, `bankr-token-trading/SKILL.md:21-27`:
`$50` (USD), `50%` (percentage of balance), `0.1 ETH` (exact). A `50%` order means the remote
agent reads the balance and does the multiplication — the amount is never a number in this repo.

---

## 4. STATE AND PERSISTENCE

**Nothing is persisted. Not present.**

- No database, no ORM, no filesystem writes, no cache, no log file, no serialization.
- The MCP server holds zero in-memory state between tool calls — every handler re-reads
  `API_KEY` from module scope and issues a fresh `fetch`.
- All durable state (jobs, threads, wallet, balances) lives on Bankr's servers.

**Resumability after mid-pipeline failure:** partially, and only by accident of the job model.
The `jobId` is the resume token and the work continues remotely regardless of the client.
`bankr-agent/skills/bankr-job-workflow/SKILL.md:68-73` states this as the recovery procedure:
```md
If polling fails:
1. Retry after brief delay
2. Job continues server-side regardless
3. Can resume polling with same jobId
```
But the `jobId` is only ever held in the model's conversation context. Lose the context, lose
the handle — nothing writes it down.

**Querying history later:** no local mechanism. The nearest thing is server-side conversation
threading, documented only in the dev plugin — `bankr-api-workflow/SKILL.md:26-33`:
```ts
  body: JSON.stringify({
    prompt: "What is my ETH balance?",
    threadId: "thr_XYZ789", // optional: continue conversation
  }),
```
**Flagging an inconsistency I read rather than inferred:** `threadId` appears in
`bankr-api-workflow/SKILL.md` only. It is absent from the MCP server's `PromptResponse`
(`index.ts:42-48`), from `job-response-schema.md`, and from `bankr-client-patterns`. So the MCP
path — the one the end-user plugin actually uses — **cannot** continue a thread; every
`/bankr-agent` call starts a fresh conversation.

---

## 5. EXTERNAL I/O

### Every external call

| Service | Endpoint | Library | Auth |
|---|---|---|---|
| Bankr Agent API | `POST /agent/prompt` | global `fetch` | `x-api-key: bk_...` header |
| Bankr Agent API | `GET /agent/job/{id}` | global `fetch` | same |
| Bankr Agent API | `POST /agent/job/{id}/cancel` | global `fetch` | same |
| Bankr Agent API | `POST /agent/sign` | `fetch` *(documented only)* | same |
| Bankr Agent API | `POST /agent/submit` | `fetch` *(documented only)* | same |
| Bankr Agent API | `/agent/profile` CRUD | CLI / REST *(documented only)* | `X-API-Key` |
| Bankr LLM Gateway | `llm.bankr.bot/v1/{chat/completions,messages}` | *(documented only)* | `Bearer` / `x-api-key` |
| Bankr via SDK | `@bankr/sdk` `BankrClient` | *(documented only)* | **private key**, x402 |
| Chain RPC | — | `viem` *(documented only)* | private key |

Only the first three are executed by code in this repo. Everything else is prose in a skill.

`API_URL` default and override, `index.ts:11-12`:
```ts
const API_KEY = process.env.BANKR_API_KEY;
const API_URL = process.env.BANKR_API_URL || "https://api.bankr.bot";
```

### Adapter layer?

Yes, weakly, and it is duplicated four times. The three `submitPrompt` / `getJobStatus` /
`cancelJob` functions form a clean adapter in `index.ts:97-167`; the MCP handlers below never
touch `fetch`. But near-identical copies of those same three functions exist in
`examples/basic-client.ts:69-136`, `bankr-client-patterns/SKILL.md:192-255`, and
`bankr-api-basics/SKILL.md:65-148` — four hand-maintained variants with drifted error handling
(the MCP one has the 401 special case; the example does not).

There is one genuine adapter idea worth naming: `execute()` in
`bankr-client-patterns/SKILL.md:292-299` collapses submit+poll into a single awaitable.

### Response validation and caching

Validation: **none** (see §2). Caching: **none** — no cache layer, no memoization, no TTL, no
conditional requests anywhere. The dashboard template polls on a raw interval,
`bankr-project-templates/SKILL.md:203-210`:
```js
async function checkPrice() {
  const response = await fetch('/api/price/ETH');
  ...
}
setInterval(checkPrice, 30000);
```

### Secrets

Environment variables only, read at module scope, never logged. Documented consistently:

- `BANKR_API_KEY` (Agent API), `BANKR_LLM_KEY` (gateway, falls back to the API key),
  `BANKR_PRIVATE_KEY` (x402 payment wallet).
- Missing-key handling is a long human-readable setup guide rather than a stack trace —
  `index.ts:14-31`, reused for both the missing and invalid cases.
- `.gitignore` covers `.env*`; `bankr-safety/SKILL.md:106-111` adds `~/.bankr/` and mandates
  rotation. `x402-client-patterns/SKILL.md:23-28` fails fast at import time if the key is absent.

**One thing to be aware of:** the x402 path requires a raw private key in an env var
(`BANKR_PRIVATE_KEY=0x...`), mitigated only by advice to keep $1–2 in it
(`sdk-wallet-operations/SKILL.md:88`). The Agent-API path never touches a key locally — Bankr
custodies the wallet. Those are materially different trust models sold side by side.

### CI supply-chain detail

`.github/workflows/build-bankr-agent.yml` builds with Bun and **commits the minified bundle back
to the branch**, with `permissions: contents: write`:
```yaml
      - name: Commit dist
        run: |
          git add bankr-agent/mcp-server/dist/
          git diff --staged --quiet || git commit -m "chore: build bankr-agent mcp-server dist"
          git push
```
`.gitignore` carries the matching exception `!bankr-agent/mcp-server/dist/`. Installed users run
`dist/index.js` (a bot-authored 84-line minified blob), not the readable source.

---

## 6. MONEY PATHS

### Every path that can spend or sign

1. **`bankr_agent_submit_prompt` with a trade-shaped prompt** — the main one.
   `index.ts:289`: `const result = await submitPrompt(prompt);`
   No inspection of `prompt` before sending. A string containing "Sell all my ETH" is
   indistinguishable to this code from "What is the price of ETH?". Execution happens remotely
   on a Bankr-custodied wallet.
2. **`POST /agent/submit`** — documented, not implemented here. Signs and broadcasts raw
   calldata. `bankr-sign-submit-api/SKILL.md:168`:
   `- /agent/submit executes immediately — **no confirmation prompt**`
3. **`POST /agent/sign`** — `personal_sign`, `eth_signTypedData_v4`, `eth_signTransaction`.
   An EIP-712 permit signature is itself a spend authorization.
4. **Arbitrary transaction via prompt** — `bankr-arbitrary-transaction/SKILL.md:59`:
   `await execute(\`Submit this transaction: ${JSON.stringify(txJson)}\`);`
5. **`executeTransaction()` with viem** — `x402-client-patterns/SKILL.md:132-147`, signs locally
   with `BANKR_PRIVATE_KEY` and broadcasts. Called in a loop by `executeAllTransactions()` and,
   in the bot template (`x402-project-templates/SKILL.md:81-85`), **fully unattended**:
   ```ts
        if (result.transactions?.length) {
          for (const tx of result.transactions) {
            await executeTransaction(tx);
          }
        }
   ```
6. **Every `@bankr/sdk` call spends $0.01 USDC** via x402 before any trade occurs — the read path
   costs money too (`sdk-capabilities/SKILL.md:77`).
7. **LLM gateway credits** — separate USD balance, `bankr llm credits add 25`.

### Guardrails

| Guardrail | Status |
|---|---|
| Spend caps / max notional | **Not present** |
| Token or address allowlist | **Not present** |
| Dry-run mode | **Not present** |
| Kill switch | **Not present** (`cancelJob` stops one in-flight job; that is all) |
| Paper / simulation mode | **Not present** |
| Confirmation prompt before execution | **Not present** in code |
| Read-only credential | **Yes — server-side**, `readOnly` API-key flag |
| IP allowlist | **Yes — server-side**, `allowedIps` |
| Rate limit | **Yes — server-side**, 100/day standard, 1,000/day Club |
| Wallet isolation | **Advisory only** — "use a dedicated agent wallet" |
| Confirmation of on-chain inclusion | **Yes**, `waitForConfirmation: true` (default true) |

I grepped for `dry.run|dryrun|paper trad|simulat|kill switch|testnet|fixture|mock` across all
`.md` and `.ts` files: **zero hits**. There is no offline or simulated mode of any kind, and no
fixtures to drive one.

Every real control is a property of the **API key**, configured out-of-band at `bankr.bot/api`,
not a property of this code. `bankr-safety/SKILL.md:16-20`:
```md
| `agentApiEnabled` | `/agent/*` endpoints | false |
| `llmGatewayEnabled` | LLM Gateway at `llm.bankr.bot` | false |
| `readOnly` | Restricts agent to read-only tools | false |
```
That is a genuinely good separation — capability lives with the credential, so a leaked key is
bounded — but it means a client built from these templates has *no local ability* to constrain
itself. The blast radius is whatever the key permits and the wallet holds.

The closest thing to a risk control in the repo is a bulleted list of advice
(`bankr-safety/SKILL.md:113-118`): test small, verify calldata, keep a gas buffer.

---

## 7. FAILURE HANDLING

| Failure | What happens |
|---|---|
| **Timeout** | `waitForCompletion` throws after `maxAttempts` (150 → 5 min). The remote job keeps running and keeps spending. |
| **Rate limit (429)** | Not handled in the MCP server — falls to the generic `API request failed: 429 - ...` throw. Handled only in doc snippets via `error.resetAt`. |
| **Bad LLM output** | Not handled at all. Malformed JSON from the API produces `undefined` fields that print as `undefined` in `formatJobStatus`. |
| **Partial agent failure** | N/A — no fan-out to partially fail. The documented `Promise.all` batch has no isolation: one rejection loses all results. |
| **Auth (401)** | Special-cased with a setup guide, and an explicit no-retry rule: `bankr-error-handling/SKILL.md:37` — "**Important**: Do NOT retry when authentication fails." |
| **Tool-level throw** | Caught and converted to a non-fatal error result, `index.ts:352-363` — good MCP hygiene, the server never dies on a bad call. |
| **Process-level throw** | `main().catch(...)` → `process.exit(1)` (`:373-376`). |

### Retry/backoff utility

**Not present.** No retry helper, no backoff function, no jitter, no circuit breaker anywhere in
the repo. Two skills *advertise* one as a feature of the scaffolds they generate —
`bankr-project-templates/SKILL.md:46` and `x402-project-templates/SKILL.md:48` both say
"**Error handling**: Automatic retries with backoff" — but no such code exists in this repo to
generate it from. The bot template's actual error handling is
(`bankr-project-templates/SKILL.md:79-81`):
```ts
    } catch (error) {
      console.error("Error:", error);
    }
```
Log and continue to the next interval tick. `bankr-api-workflow/SKILL.md:127` says "retry with
backoff on fetch failures" as advice, with no implementation.

---

## 8. CONFIG AND TYPES

### Tunable values

There is **no config module**. Values live in three places, none of them centralized:

1. **Env vars** — `BANKR_API_KEY`, `BANKR_API_URL`, `BANKR_LLM_KEY`, `BANKR_PRIVATE_KEY`,
   `BANKR_WALLET_ADDRESS`. Read inline at module scope.
2. **Inline constants / default params** — `2000` ms poll, `150` / `120` max attempts,
   `240000` ms max duration, `60000` ms bot interval. Each is re-declared in every copy and the
   copies disagree: `basic-client.ts:150` uses `maxPolls ?? 120` (4 min) while
   `bankr-client-patterns/SKILL.md:263` uses `maxAttempts || 150` (5 min).
3. **Remote, out-of-band** — the security-relevant knobs (`readOnly`, `allowedIps`, rate tier)
   are set in the Bankr web UI, not in any file here.

The templates *name* a `config.ts` in their directory listings
(`bankr-project-templates/SKILL.md:37`) but no such file is provided.

### Shared types module

**Not present** — and this is the single most duplicated thing in the repo. The same core types
are hand-copied into four files with drift:

| Location | Notes |
|---|---|
| `mcp-server/src/index.ts:42-94` | Flat `metadata`, 4 interfaces |
| `examples/basic-client.ts:12-62` | Same four, re-typed |
| `bankr-api-basics/references/job-response-schema.md:20-62` | Doc form |
| `bankr-client-patterns/SKILL.md:25-186` | **Richest** — a 13-member discriminated union |

Only the last models transactions properly, `bankr-client-patterns/SKILL.md:51-64`:
```ts
export type Transaction =
  | SwapTransaction
  | ApprovalTransaction
  | TransferErc20Transaction
  ...
  | ManageBankrStakingTransaction;
```

**Core types, canonically:**
- `JobStatus = "pending" | "processing" | "completed" | "failed" | "cancelled"`
- `JobStatusResponse` — `{ success, jobId, status, prompt, response?, transactions?, richData?,
  statusUpdates?, error?, createdAt, startedAt?, completedAt?, cancelledAt?, processingTime?,
  cancellable? }`
- `Transaction` — discriminated on `type`, 13 members
- `StatusUpdate = { message, timestamp }`
- `RichData = SocialCard | Chart`

**Flagging a real divergence between the copies** (read, not inferred): the MCP server and the
example expect `tx.metadata.humanReadableMessage`, while the client-patterns union nests it as
`tx.metadata.__ORIGINAL_TX_DATA__.humanReadableMessage`. Both appear in usage examples
(`index.ts:191` vs `bankr-client-patterns/SKILL.md:467`). At most one is right for a given
transaction type; nothing in the repo reconciles them.

`tsconfig.json` is `strict: true`, ES2022, NodeNext, `declaration: true` — and identical in all
three places it appears.

---

## 9. DEPENDENCIES

**Runtime dependencies of this repo: exactly one.**

`bankr-agent/mcp-server/package.json`:
```json
"dependencies": { "@modelcontextprotocol/sdk": "^1.0.0" }
```
Dev: `typescript ^5`, `@types/node ^20`. Root `package.json` has **empty** `dependencies` and
`devDependencies`. HTTP is global `fetch`, so there is no axios/node-fetch. Node ≥18; build is Bun.

`@modelcontextprotocol/sdk@1.25.2` is heavier than it looks — `bun.lock` shows it pulls
`express@5`, `@hono/node-server`, `cors`, `ajv` + `ajv-formats`, `zod`, `zod-to-json-schema`,
`jose`, `eventsource`, `pkce-challenge`. Notably, **`zod` and `ajv` are already in the tree**
and the repo uses neither for its own validation.

Dependencies of the *generated* projects (documented, not installed here): `dotenv`, `tsx`,
optionally `express`/`fastify`/`commander`; for the x402 track, `@bankr/sdk` and `viem`.

**Heavy / avoid:** nothing heavy is actually pulled in. The one thing I would not inherit is the
committed-and-CI-regenerated `dist/` bundle (§5) — it makes the executed artifact unreviewable.

**Worth adopting:** `@modelcontextprotocol/sdk` if you want your fund's decision record readable
by any MCP client. `viem` for local signing. And since `zod` is already transitively present,
there is no dependency cost to typed parsing.

---

## 10. VERDICT

### Patterns worth stealing

1. **Pre-computed human-readable summaries carried on structured data.** Bankr returns
   `humanReadableMessage` next to raw calldata so the client never has to re-describe a
   transaction. `mcp-server/src/index.ts:190-196`. Our treasurer should emit exactly this on
   every trade in the ordered list — the accountability swarm and the x402 decision record then
   consume the summary and never re-derive prose from calldata.

2. **One function that compresses a record before it re-enters context.** `formatJobStatus`,
   `index.ts:170-208`, drops base64, calldata, and gas, keeping ~8 lines. We need the same choke
   point between analyst reports → aggregator and between treasurer → public page. Making it a
   *named function* rather than ad-hoc slicing is the actual lesson.

3. **Index-tracked incremental progress.** `bankr-client-patterns/SKILL.md:270-274` replays only
   `statusUpdates[lastUpdateCount..]`. Cheap, and it is how you stream a long analyst run to a
   judge watching the demo without re-printing the whole log each tick.

4. **Capability flags bound to the credential, not the code.** `bankr-safety/SKILL.md:16-20`
   (`readOnly`, `allowedIps`, rate tier). Our N analyst agents are specified read-only — giving
   them a literally read-only credential makes that structural rather than aspirational, and it
   is a one-line thing a judge can verify.

5. **Skill-router agent with an explicit "load before you act" rule.**
   `bankr-agent/agents/bankr-agent.md:102`: *"**CRITICAL**: Never call
   `bankr_agent_submit_prompt` without first loading the relevant skill."* A hard precondition
   stated in the system prompt, with the reason given. The same shape fits our risk agent: never
   hand weights to the treasurer without the risk check having run.

6. **Error text as a setup runbook.** `index.ts:14-39` — the missing-key error *is* the
   instructions, with the same block reused for missing and invalid. Good demo hygiene.

### Do not copy

1. **No validation on any boundary.** Every `response.json()` is type-asserted, not checked
   (`index.ts:142`). For us this is fatal, not stylistic: analyst reports are LLM-authored, so
   `{ticker, direction, conviction, reasoning, citations}` must be schema-parsed at the seam or
   the aggregator computes weights from hallucinated fields. `zod` is already in the MCP tree.

2. **The control loop living in a prose instruction to the model.** `index.ts:307` tells the LLM
   "Poll every 2 seconds until…". A loop with no bound, no owner, and no enforcement. Our
   pipeline needs the sequencing in code; the model must not be the scheduler.

3. **Four hand-maintained copies of the same types, already drifted.** §8 —
   `metadata.humanReadableMessage` vs `metadata.__ORIGINAL_TX_DATA__.humanReadableMessage`, and
   120 vs 150 poll caps. With two swarms and a shared decision record, one `types.ts` is
   non-negotiable. Judges will read the code and duplication is the first thing they'll see.

4. **Zero local guardrails on the money path.** §6 — no cap, no allowlist, no dry-run, no kill
   switch, and `executeAllTransactions` looping unattended over model-produced transactions
   (`x402-client-patterns/SKILL.md:152-163`). Our treasurer is the only writer precisely so it
   can be the only place these live.

5. **`Promise.all` for the fan-out.** `sdk-job-management/SKILL.md:78-85`. One analyst failing
   must not void the other N−1 reports — `allSettled`, with the aggregator recording which
   mandates came back empty.

6. **Claiming features the code doesn't have.** "Automatic retries with backoff"
   (`bankr-project-templates/SKILL.md:46`) with no retry utility in the repo; a `validate` npm
   script pointing at a non-existent `scripts/`. Our README should describe only what runs.

7. **Advisory-only safety.** Most of `bankr-safety` is bullet points a reader may ignore. Our
   risk agent's veto must be a code path the treasurer cannot proceed past, not a paragraph.

### Direct answers to our open questions

**Reading DEX pool depth on an Arbitrum-Orbit chain — nothing here.** I grepped for
`pool depth|liquidity|orbit|uniswap|robinhood|tokenized stock`: the only hits are a passing
"Check market liquidity for best prices" in the Polymarket skill and `Arbitrum | 42161` in a
chain-ID table (`job-response-schema.md:72`). Supported chains are Base, Ethereum, Polygon,
Unichain, Solana — **Arbitrum is not among them**, and Robinhood Chain appears nowhere. Bankr
gives us no reachable path to Robinhood Chain pools today; we read that chain ourselves.

**Price oracles for tokenized stocks — nothing here.** No oracle integration, no TWAP, no
Chainlink/Pyth. Prices are whatever prose the remote agent returns
(`bankr-market-research/SKILL.md:50-65` lists price, market cap, RSI, MACD as *available data*
with no source named). The **only** named price source in the entire repo is in
`bankr-agent-profiles/SKILL.md:61-62`: `marketCapUsd` updated every 5 min from **CoinGecko**,
`weeklyRevenueWeth` every 30 min from **Doppler fee data**. Neither covers tokenized equities.
This is a dead end for us — the oracle question is unanswered by this repo.

**x402 handler patterns — nothing here either, and this is the sharpest gap.** All 30 `x402`
matches are the *client* side: the plugin's own name, and "$0.01 USDC per request, paid on Base,
signed by `BANKR_PRIVATE_KEY`". There is **no server-side x402 code** — no 402 response
construction, no payment-header verification, no facilitator call, no settlement. The payment
logic is inside the closed-source `@bankr/sdk`. The only 402 *handling* is a troubleshooting row:
`402 | Payment required | Ensure wallet has BNKR on Base` (`bankr-error-handling/SKILL.md:55`).
For our paid decision-record endpoint we get **no reusable pattern from this repo**; we need the
x402 spec or a server-side reference implementation elsewhere. What we *do* get is a clear
picture of the client contract we'd be serving.

**Bankr API usage — this is what the repo is genuinely good for, and it's complete.**
- Agent API: `POST /agent/prompt` (async job), `GET /agent/job/{id}`, `POST /agent/job/{id}/cancel`,
  auth `x-api-key: bk_...`, base `https://api.bankr.bot`, prompt max 10,000 chars, optional
  `threadId` for conversation continuity.
- Sync endpoints that skip polling entirely: `POST /agent/sign` (`personal_sign`,
  `eth_signTypedData_v4`, `eth_signTransaction`) and `POST /agent/submit`
  (`{to, chainId, value, data, gas, maxFeePerGas, maxPriorityFeePerGas}` + `waitForConfirmation`,
  default true, returning `{transactionHash, status, blockNumber, gasUsed}`).
  `bankr-sign-submit-api/SKILL.md:84-130`. **For our treasurer, `/agent/submit` is the right
  primitive** — deterministic, synchronous, confirmable, and it keeps trade construction in our
  code rather than in a prompt string.
- Full response schema incl. the 13-member transaction union:
  `bankr-client-patterns/SKILL.md:51-186`.
- Access control we should use: `readOnly` keys for the analyst swarm, `allowedIps` for the
  treasurer host, separate `BANKR_LLM_KEY` so LLM spend is metered apart from trading
  (`bankr-safety/SKILL.md:16-27`) — which maps directly onto the accountability swarm's
  "LLM spend vs gas" cost split.
- LLM gateway: `https://llm.bankr.bot`, OpenAI- and Anthropic-shaped
  (`/v1/chat/completions`, `/v1/messages`), `Bearer` or `x-api-key`, USD credit balance separate
  from the trading wallet, 402 when empty (`bankr-llm-gateway/SKILL.md:93-107`). **Per-request
  cost attribution for our analyst agents would come from here**, though this repo documents no
  usage/cost-reporting endpoint — only `bankr llm credits` as a CLI balance check. Model IDs
  listed there are Bankr's own catalog and do not match current Anthropic model IDs; treat that
  table as stale.
- Rate limits that bound our analyst fan-out: **100 messages/day** standard, 1,000/day Bankr Club,
  rolling 24h from first message (`bankr-safety/SKILL.md:57-65`). With N analysts on a schedule,
  this is a real constraint to design around.
