# openclaude (Gitlawb/openclaude) — Bankr integration review

Read-only review. Repo: `./openclaude`, branch `main`, HEAD `d16318a4`.
Scope: 3,460 files (excluding `.git`/`node_modules`).

---

## TL;DR — the headline finding

**openclaude uses Bankr for exactly one thing: as an OpenAI-compatible LLM
inference endpoint.** It is one of ~44 provider presets in a provider-routing
table, sitting next to OpenRouter, Groq, Venice and Azure.

There is **no wallet, no swap, no x402, no signing, no chain, no token, no
Bankr skill, and no Bankr Agent API** anywhere in this repository. Verified by
negative grep across the whole tree:

| Searched for | Hits outside `.git`/`node_modules` |
|---|---|
| `x402` | **0** |
| `swap-quote`, `/wallet/swap`, `/agent/prompt`, `/agent/job` | **0** |
| `minBuyAmount`, `idempotencyKey`, `USDG`, `4663` | **0** |
| `viem`, `ethers`, `web3`, `wagmi`, `@bankr`, `coinbase` in `package.json` | **0** |
| `privateKey` / `PRIVATE_KEY` as a credential | **0** (only in redaction denylists, `src/utils/redaction.ts:136`) |

⚠️ **False positive to discard:** `robinhood` appears in 17 files, but it is a
pixel-art mascot — "the green archer" — in the `/buddy` easter-egg subsystem
(`README.md:353`, `src/buddy/types.ts:17`, `web/public/buddy/robinhood.svg`).
It has nothing to do with Robinhood Chain.

So for your questions 2, 4, 6, 7 and 8, the honest answer is **not present**.
The value this repo has for you is narrower but real: it is a careful,
tested, production reference for **how to talk to `llm.bankr.bot`**, and its
provider-descriptor pattern is worth stealing wholesale.

---

## 1. Inventory — every file that touches Bankr

29 files match `bankr` case-insensitively. Grouped by role:

### Core definition (the only file that is "about" Bankr)

| File | Lines | Kind | What it does |
|---|---|---|---|
| `src/integrations/vendors/bankr.ts` | 40 | code | The entire Bankr descriptor: base URL, default model, env vars, auth mode, catalog |

### Request path (Bankr-specific branches inside generic code)

| File | Lines (file) | Kind | Bankr's share |
|---|---|---|---|
| `src/services/api/openaiShim/requestExecutor.ts` | 1,188 | code | `X-API-Key` header branch, ~10 lines (`:413-420`, `:454-456`) |
| `src/services/api/openaiShim/requestPlanner.ts` | 461 | code | env aliasing `BANKR_* → OPENAI_*`, 4 lines (`:30-33`) |
| `src/utils/model/openaiModelDiscovery.ts` | 210 | code | `isBankrBaseUrl()` + header selection (`:44-62`) |
| `src/utils/providerDiscovery.ts` | 543 | code | label detection (`:227-230`); `/models` auth headers (`:270-277`, `:317-324`) |

### Configuration / credential plumbing

| File | Lines (file) | Kind | Bankr's share |
|---|---|---|---|
| `src/utils/providerFlag.ts` | 940 | code | `case 'bankr'` env application (`:573-584`); route inference (`:381-385`); preference order (`:48-50`) |
| `src/utils/providerProfile.ts` | 2,721 | code | `buildBankrProfileEnv()` (`:1111-1145`); env var lists (`:110-112`, `:212-214`) |
| `src/utils/providerProfiles.ts` | 2,275 | code | key round-tripping to `BNKR_API_KEY` (`:915-918`, `:1168-1170`, `:1736-1738`) |
| `src/utils/envFile.ts` | 381 | code | allowlists `BANKR_BASE_URL`, `BANKR_MODEL`, `BNKR_API_KEY` (`:26-29`) |
| `src/utils/providerSecrets.ts` | 388 | code | `BNKR_API_KEY` in fallback redaction denylist (`:22`) |
| `src/components/StartupScreen.ts` | 269 | code | displays "Bankr" in the startup banner (`:149-150`) |

### Generated artifacts (do not hand-edit)

| File | Kind | Bankr's share |
|---|---|---|
| `src/integrations/generated/integrationManifest.generated.ts` | generated code | preset entry (`:134-147`), ordered list (`:597`) |
| `src/integrations/generated/integrationArtifacts.generated.ts` | generated code | import + `VENDOR_DESCRIPTORS` (`:9`, `:95`) |

### Tests (7 files)

`src/services/api/openaiShim/requestExecutor.test.ts` (env save/restore +
`:2370` negative test), `requestExecutor.integration.test.ts`,
`requestPlanner.test.ts` (`:63-90`), `openaiShim.test.ts`,
`src/utils/providerFlag.test.ts` (`:989-1002`),
`src/utils/providerValidation.test.ts` (`:557-564`),
`src/utils/providerProfiles.test.ts`, `src/integrations/compatibility.test.ts`
(`:48`), `scripts/system-check.test.ts` (`:76-78`),
`src/components/ProviderManager.test.tsx` (`:142`),
`src/commands/provider/provider.test.tsx` (`:437`, comment only).

### Prose

| File | Kind | Content |
|---|---|---|
| `README.md:39-40,61` | prose | Bankr.bot logo + sponsor/partner table row |
| `docs/architecture/integrations.md:205-206,233` | prose | documents the `X-API-Key` exception |
| `docs/integrations/glossary.md:57,173` | prose | classifies Bankr as a "Vendor" |
| `web/src/data/partners.ts:16` | code (data) | partner logo |
| `web/src/data/providers.ts:176-182` | code (data) | public provider table row |

**Notable absence:** `.env.example` is 28,529 bytes and documents dozens of
providers, but contains **no** `BNKR_API_KEY` / `BANKR_*` entry. Confirmed by
`grep -n "BNKR\|BANKR\|bankr" .env.example` → no match. That is a documentation
gap in their repo, not an inference.

---

## 2. Every Bankr call

Two, both plain HTTP against `llm.bankr.bot`. Bankr is never called by a
dedicated client module — it flows through the generic OpenAI-compatible shim.

| # | Endpoint | Method | Auth header | Request body | Response handling | file:line |
|---|---|---|---|---|---|---|
| 1 | `{base}/chat/completions` (OpenAI-compatible; base = `https://llm.bankr.bot/v1`) | POST | `X-API-Key: <key>` (raw, **no `Bearer`**) | Standard OpenAI chat-completions payload built by `requestPlanner.ts` | Streamed/parsed by the shared shim; usage tokens fed to `cost-tracker.ts` | header branch: `src/services/api/openaiShim/requestExecutor.ts:454-456`; route detect `:413-420` |
| 2 | `{base}/models` | GET | `X-API-Key: <key>` | none | Model list for the `/provider` picker & model discovery | `src/utils/providerDiscovery.ts:279-284` and `:326-330`; header choice `:270-277`, `:317-324`; parallel path `src/utils/model/openaiModelDiscovery.ts:60-62` |

The auth branch, verbatim (`requestExecutor.ts:454-456`):

```ts
} else if (isBankr) {
  // Bankr uses X-API-Key header instead of Bearer token
  headers['X-API-Key'] = authValue
```

### How a request is identified as Bankr

Two independent mechanisms, and they disagree in strictness:

```ts
// requestExecutor.ts:413-420
let isBankr = false
try {
  isBankr =
    runtimeShimContext.routeId === 'bankr' ||
    request.baseUrl.toLowerCase().includes('bankr')
} catch {
  /* malformed URL — not Bankr */
}
```

versus the stricter hostname check used by model discovery
(`openaiModelDiscovery.ts:44-50`):

```ts
function isBankrBaseUrl(baseUrl: string): boolean {
  try {
    return new URL(baseUrl).hostname.toLowerCase().includes('bankr')
  } catch { return false }
}
```

`providerDiscovery.ts:270` and `:317` use the loose `baseUrl.includes('bankr')`
form. See §14 — this is the fragile bit.

### Contradictions with your stated Bankr facts

**One correction, and it matters.**

> "The LLM gateway is llm.bankr.bot, OpenAI- and Anthropic-compatible, billed
> from a credit balance."

Confirmed as to the URL and OpenAI compatibility. But this repo says the gateway
does **not** take `Authorization: Bearer`. It takes **`X-API-Key`**, and they
treat that as a first-class protocol exception, documented alongside Azure's
`api-key` quirk (`docs/architecture/integrations.md:205-206`):

> - Azure OpenAI and Bankr have distinct auth/header contracts.
>   Azure uses `api-key` and deployment URLs; Bankr uses `X-API-Key`.

They also list "Bankr auth/header aliasing" as a standing exception to their
generic transport (`docs/architecture/integrations.md:233`).

⚠️ Note this is **the LLM gateway's** auth scheme. It says nothing about the
Bankr Agent API (`/agent/prompt`, `/wallet/swap`), which this repo never calls.
Do not assume the two share a header contract — this repo is not evidence either
way.

Everything else on your list (swap flow, 403 gating, agent tiers, x402 handler
shape) is simply **not present**. No contradiction, no confirmation.

---

## 3. Credentials

### Which credential

Exactly one: **`BNKR_API_KEY`**. Note the spelling — the key is `BNKR_`, while
the *other two* Bankr vars are `BANKR_`. This is deliberate and consistent
across all 29 files (`src/integrations/vendors/bankr.ts:9,13,21`;
`src/utils/envFile.ts:26-29`). It is an easy typo to inherit.

```ts
// src/integrations/vendors/bankr.ts:9-14
requiredEnvVars: ['BNKR_API_KEY'],
setup: {
  requiresAuth: true,
  authMode: 'api-key',
  credentialEnvVars: ['BNKR_API_KEY'],
},
```

Three env vars total: `BNKR_API_KEY`, `BANKR_BASE_URL`, `BANKR_MODEL`
(`src/utils/envFile.ts:26-29`, `src/utils/providerProfile.ts:110-112`).

### How it is loaded

Four converging paths, all landing on `OPENAI_API_KEY` in `process.env`:

1. **`--provider bankr` flag** — `src/utils/providerFlag.ts:573-584`:
```ts
case 'bankr':
  process.env.CLAUDE_CODE_USE_OPENAI = '1'
  applyOpenAIBaseUrlDefault(provider, defaultBaseUrl ?? 'https://llm.bankr.bot/v1')
  process.env.OPENAI_MODEL ??= 'claude-opus-4.6'
  if (model) process.env.OPENAI_MODEL = model
  if (process.env.BNKR_API_KEY && !process.env.OPENAI_API_KEY) {
    process.env.OPENAI_API_KEY = process.env.BNKR_API_KEY
  }
  break
```
2. **Bare env vars** — `requestPlanner.ts:30-33` aliases `BANKR_BASE_URL →
   OPENAI_BASE_URL` and `BANKR_MODEL → OPENAI_MODEL`, then resolves the
   credential from the base URL.
3. **Saved profile** — `buildBankrProfileEnv()`
   (`src/utils/providerProfile.ts:1111-1145`) emits `{BNKR_API_KEY, BANKR_MODEL,
   BANKR_BASE_URL?}` with `'claude-opus-4.6'` as the model fallback.
4. **Reverse inference** — if `OPENAI_API_KEY === BNKR_API_KEY`, the active
   route is inferred to be `bankr` (`src/utils/providerFlag.ts:383-385`).

Validation accepts either var (`src/integrations/vendors/bankr.ts:29-31`):
```
credentialEnvVars: ['BNKR_API_KEY', 'OPENAI_API_KEY'],
missingCredentialMessage:
  'Bankr auth is required. Set BNKR_API_KEY or OPENAI_API_KEY.',
```
Test coverage at `src/utils/providerValidation.test.ts:557-564`.

### Where stored

Saved provider profiles persist the **plaintext API key** into the global
config via `getGlobalConfig()` under `providerProfiles`
(`src/utils/providerProfiles.ts:625,1452,2127`). On activation the key is
written back into *both* `OPENAI_API_KEY` and `BNKR_API_KEY`
(`:1168-1170`, `:1736-1738`). No OS keychain, no encryption-at-rest.

### Ever logged?

**Structurally, no — and this is the best thing in the repo.**
`src/utils/providerSecrets.ts` derives the redaction denylist *from the
descriptor graph itself* (`:28-60`), so a new provider cannot silently create an
unredacted path. `BNKR_API_KEY` is additionally hard-pinned in the manual
fallback list (`:22`). Diagnostic logging runs values through
`redactSecretSubstringsForDisplay` / `redactEncodedSecretSubstringsForDisplay`
(imported at `requestExecutor.ts:6-9`), and URLs through
`redactUrlForDiagnostics` (`:622`, `:700`, `:761`).

The module's own comment states the intent (`providerSecrets.ts:66-72`):

> Derived from `PROVIDER_PRESET_MANIFEST` plus descriptor setup and
> validation metadata so adding a new provider cannot silently create an
> unredacted path.

### Agent wallet vs user wallet; key scoping

**Not present.** There are no wallets. The key is a single global process-env
credential shared by the main loop and every subagent; there is no per-agent
key, no scope, no read-only/execute distinction, no IP allowlist. Subagents
inherit `process.env`.

The one relevant nuance is **`CredentialPool`**
(`src/services/api/credentialPool.ts`) — a rotating pool built from a
comma-separated `OPENAI_API_KEYS`, with per-key `disabled` / `cooldownUntil`
state and round-robin `next()` (`:38-50`). It is provider-agnostic, so a Bankr
route can be given multiple keys. Nothing Bankr-specific configures it.

---

## 4. Wallet and money paths

**Not present.** No code in this repository can spend, sign, or move funds.
No caps, no allowlists, no dry-run, no confirmation prompt, no kill switch, no
simulation mode — because there is nothing to guard.

The only money-adjacent machinery is **LLM cost accounting**, which is not a
spend path (it observes, it does not authorize):

- `src/cost-tracker.ts` (421 lines) accumulates per-model input/output/cache
  tokens and `costUSD` (`:220-260`), via `calculateUSDCost()` from
  `src/utils/modelCost.js` (`:57`).
- It surfaces an honest caveat when pricing is unknown (`:274`):
  `' (costs may be inaccurate due to usage of unknown models)'`
- `src/QueryEngine.customPricingBudget.test.ts` exists, implying a budget
  concept in the query engine. ⚠️ *Inferred from the filename; I did not read
  the budget implementation, so treat "there is an LLM spend budget" as
  unverified.*

---

## 5. LLM routing

**Yes — this is the whole integration.** Inference is routed through
`llm.bankr.bot` as one selectable provider among many.

### Model choice

Static, single-model catalog (`src/integrations/vendors/bankr.ts:33-38`):

```ts
catalog: {
  source: 'static',
  models: [
    { id: 'claude-opus-4.6', apiName: 'claude-opus-4.6', label: 'Claude Opus 4.6' },
  ],
},
```

Precedence: `--model` flag → `BANKR_MODEL` → `OPENAI_MODEL` → default
`'claude-opus-4.6'` (`providerFlag.ts:579-580`; `providerProfile.ts:1125-1131`;
preset `modelEnvVars: ['BANKR_MODEL', 'OPENAI_MODEL']` at `bankr.ts:22`).

A live `GET /models` call can override the static catalog for the picker
(`providerDiscovery.ts:279`, `:326`).

Bankr is ranked **second** in the provider preference order, right after
Anthropic itself (`src/utils/providerFlag.ts:48-51`):
```ts
const PREFERRED_PROVIDER_ORDER = [
  'anthropic',
  'bankr',
  'zai',
```

### Cost / token tracking per call

Token usage **is** tracked generically — the shim reports `tokensIn`/`tokensOut`
per response (`requestExecutor.ts:910-914`) into `cost-tracker.ts`. Dollar
figures depend on `modelCost.js` having an entry for `claude-opus-4.6` on the
Bankr route; otherwise the "unknown models" caveat fires.

**Bankr credit balance is explicitly not readable** — the descriptor opts out
(`src/integrations/vendors/bankr.ts:39`):

```ts
usage: { supported: false },
```

Consumed at `src/commands/usage/index.ts:170` (`supported: usage.supported`),
so `/usage` reports Bankr as unsupported. Contrast MiniMax, which the docs note
has a dedicated `/usage` endpoint (`docs/architecture/integrations.md:235`).

⚠️ **Relevant to your fund's cost accounting:** if you bill LLM spend through
Bankr credits, this repo shows there is no programmatic balance readout wired
up here. You would be reconciling against your own token counts, not against
Bankr's ledger.

---

## 6. x402

**Neither publishes nor consumes. Zero occurrences of `x402` in the entire
repository.** No discovery, no validation, no payment, no spend cap.

---

## 7. Chains and assets

**None.** No chain IDs, no token addresses, no RPC URLs, no `4663`, no `USDG`,
no USDC, no tokenized stocks. No EVM library in `package.json`.

The only `USDC`-looking symbol is `calculateUSDCost` (`src/cost-tracker.ts:57`)
— a dollar-cost function, not a token.

---

## 8. Skills

openclaude has a full skills subsystem, but **no Bankr skill** — `grep -rn -i
bankr src/plugins/` returns nothing, and no bundled skill references Bankr.

The loading model is worth noting anyway, because it is what a Bankr skill would
plug into:

- Skills are folders with a `SKILL.md`, loaded from `.openclaude/skills`
  (project) and a user skills dir at startup; the model invokes by name
  (`docs/skills.md:3`).
- `src/skills/loadSkillsDir.ts` (1,221 lines) does disk loading;
  `src/skills/bundledSkills.ts` (239) registers compiled-in skills;
  `src/skills/mcpSkills.ts` (116) bridges MCP-provided skills.
- Bundled skills can carry `files: Record<string,string>` extracted to disk on
  first invocation, with the prompt prefixed by a "Base directory for this
  skill" line so the model can `Read`/`Grep` references on demand
  (`bundledSkills.ts:31-40`).
- Invocation is via the `SkillTool` (`src/tools/SkillTool/`), plus
  `DiscoverSkillsTool`.

**Supply-chain hardening in the installer is genuinely good** and directly
relevant if you ship a Bankr skill (`docs/skills.md:27-33`):

> 1. Reads the registry entry and refuses to install if it has no `sha256`.
> 2. Reads `revocations.json` next to the registry and refuses to install a
>    skill that matches an entry there.
> 3. Fetches the `SKILL.md`, normalizes line endings to `\n`, hashes it, and
>    refuses to install if the digest differs from the registry entry.

And the honest caveat they publish about the escape hatch (`docs/skills.md:33`):

> If the install spec names an existing file or directory in the working tree,
> the installer takes the local path instead and runs none of them, even when
> the spec looks like a registry id such as `gitlawb/ci-fix`.

---

## 9. Architecture

**Supervisor + workers**, with forks as a third mode. It is a Claude Code
derivative, so the shape is a main REPL loop (`src/query.ts`, 3,204 lines;
`src/QueryEngine.ts`, 1,555) that dispatches subagents through
`src/tools/AgentTool/` (`AgentTool.tsx` is ~79KB; `runAgent.ts` ~39KB).

- Agents are defined as markdown-with-frontmatter, loaded by
  `loadAgentsDir.ts` (27KB), plus built-ins (`builtInAgents.ts`).
- A **fork** (`forkSubagent.ts`) inherits the parent's full context and shares
  its prompt cache — distinct from a fresh subagent.
- There is also a **team/swarm** layer (`TeamCreateTool`, `SendMessageTool`,
  `src/hooks/useSwarmInitialization.ts`, `src/daemon/workerRegistry.ts`) —
  peer messaging between sessions.

### Parallel fan-out and how it's bounded

Fan-out is encouraged at the prompt level (`src/tools/AgentTool/prompt.ts:86`):

> **Research**: fork open-ended questions. If research can be broken into
> independent questions, launch parallel forks in one message.

⚠️ **The bound I found is provider-specific, not global.** The only concurrency
cap in `AgentTool` is `GITHUB_COPILOT_MAX_SUBAGENTS`
(`AgentTool.tsx:589,700,714`), gating Copilot subagent launches. A scheduler
coalesces "concurrency-safe" blocks into batches and isolates unsafe ones
(`AgentTool.copilotScheduling.test.ts:208-240`). I found **no general
`MAX_CONCURRENT_AGENTS`** for other providers, Bankr included.

For your N-analyst fan-out under a 100-msg/day Bankr agent tier, this repo gives
you the *dispatch* pattern but **not** a reusable rate budget.

---

## 10. Context and state

- **Command history:** `~/.claude/.../history.jsonl` via
  `getClaudeConfigHomeDir()` (`src/history.ts:115,299`). Current-session entries
  are yielded before other sessions' so concurrent sessions don't interleave
  (`:185-186`). Verification/test sessions are excluded (`:413`).
- **Cost/session stats** persist into project config (`lastCost`,
  `lastAPIDuration`, `lastLinesAdded`, …) — `src/cost-tracker.ts:135-141`.
- **Provider profiles** (including plaintext API keys) persist in global config
  (`src/utils/providerProfiles.ts:1452,2127`).
- **Agent memory:** `AgentTool/agentMemory.ts` + `agentMemorySnapshot.ts`.
- **Resume:** `resumeAgent.ts` reloads transcript + meta in parallel (`:63`).

**Compaction exists and is a first-class state machine.** `QueryEngine` carries
`AutoCompactTrackingState` (`src/QueryEngine.ts:38,203,499,766-768`), backed by
`src/services/compact/autoCompact.ts`, with a cooldown regression test
(`src/QueryEngine.autoCompactCooldown.test.ts`). Additional summarizers:
`src/utils/memoryCompaction.ts`, `src/utils/taskSummary.ts`,
`src/utils/collapseHookSummaries.ts`.

---

## 11. Tool interface

Tools are objects with a **Zod v4** `inputSchema` (`src/Tool.ts:10,429`).
Notably there is also an **optional `outputSchema`** (`src/Tool.ts:435`):

```ts
outputSchema?: z.ZodType<unknown>
```

Input validation is two-stage: schema parse, then an optional semantic
`validateInput?()` hook, and the comment at `src/Tool.ts:530` pins the ordering
guarantee:

> Determines if the user is asked for permission. Only called after
> validateInput() passes.

That ordering is the good part — **permission prompts cannot be reached with
inputs that failed validation.**

⚠️ **Is tool output validated before re-entering context?** `outputSchema` is
declared as an optional field, but I did **not** verify that the query loop
enforces it on the return path — my grep for the result-mapping call sites in
`src/query.ts`/`src/tools.ts` came back empty. Treat "tool output is
schema-validated before re-entering context" as **unverified**; the capability
is declared, the enforcement is unconfirmed.

---

## 12. Failure handling

### What Bankr traffic gets

- **Rate-limit headers: read, but only as a display hint.**
  `requestExecutor.ts:12-15`:
```ts
export function formatRetryAfterHint(response: Response): string {
  const retryAfter = response.headers.get('retry-after')
  return retryAfter ? ` (Retry-After: ${retryAfter})` : ''
}
```
  It formats a string appended to the error. Nothing sleeps on it.

- ⚠️ **Automatic 429 backoff is GitHub-gated and Bankr does not get it.**
  `requestExecutor.ts:918`:
```ts
if (isGithub && response.status === 429 && attempt < maxAttempts - 1) {
```
  Exponential backoff (`GITHUB_429_BASE_DELAY_SEC * 2 ** attempt`, clamped to
  `GITHUB_429_MAX_DELAY_SEC`, `:919-922`) plus credential cooldown is inside
  that `isGithub` branch. A Bankr 429 surfaces to the caller with a hint string
  and no retry.
- **Attempt budget:** `maxAttempts = max(isGithub ? GITHUB_429_MAX_RETRIES : 1,
  credentialPoolAttempts) + …` (`:666`). With a single key on Bankr, that is
  **one attempt**.
- **Self-heal base-URL retry is local-only:** `maxSelfHealAttempts = isLocal ?
  localRetryBaseUrls.length + 1 : 0` (`:662`).
- **Timeouts:** stream idle timeout via `CLAUDE_STREAM_IDLE_TIMEOUT_MS`
  (`src/services/api/openaiShim/streamControl.ts:59`); 5s timeout on `/models`
  discovery (`providerDiscovery.ts:267,314`); response-headers timeout marked
  non-retryable (`requestExecutor.ts:826`).
- **Abort classification:** `isAbortLikeError` (`:31-40`) distinguishes
  user-abort from failure — there is a dedicated
  `src/query.abortClassification.test.ts`.
- **Provider fallback:** `src/utils/providerFallback.ts:54` guards against an
  infinite "ratelimit → ratelimit → first profile" loop.
- **Elsewhere in the codebase, `Retry-After` *is* honoured properly** — the
  telemetry uploader parses it into `retryAfterMs` and clamps
  (`src/cli/transports/ccrClient.ts:609,680`;
  `src/cli/transports/SerialBatchEventUploader.ts:19,240`). The inference path
  just never adopted that.

---

## 13. Patterns worth stealing

1. **The descriptor pattern — steal this first.**
   `src/integrations/vendors/bankr.ts` is 40 declarative lines and that is the
   *entire* provider. `defineVendor()` (`src/integrations/define.ts:14`) is a
   typed identity function, so contributors never import registry internals.
   Manifests are generated (`integrationArtifacts.generated.ts:95`) rather than
   hand-maintained. For your fund: model your analyst agents, risk agent and
   treasurer as descriptors, not classes.

2. **Redaction derived from the config graph, not a hand-list.**
   `src/utils/providerSecrets.ts:28-60` walks every descriptor's
   `setup.credentialEnvVars` and `validation.credentialEnvVars` to build the
   denylist, with a manual fallback for legacy paths (`:13-26`). This is the
   single best idea in the repo and it directly protects a wallet key. Your
   treasurer will hold the only execute-scoped credential; make it impossible
   to add one without redaction.

3. **A capability that can honestly say "no."**
   `usage: { supported: false }` (`bankr.ts:39`) with a typed `UsageMetadata`
   (`src/integrations/descriptors.ts:172-184`) including `delegateToVendorId`,
   `fallbackMessage` and `silentlyIgnore`. Declaring absence beats an unhandled
   404. Use this for "risk agent has not yet reported."

4. **`validateInput()` strictly before the permission prompt.**
   `src/Tool.ts:524-530`. For a treasurer that is the only writer, this
   ordering is exactly the invariant you want: nothing malformed can even reach
   a confirmation dialog.

5. **`CredentialPool` with per-key cooldown.**
   `src/services/api/credentialPool.ts:38-50` +
   `hasAvailableCredential()` guarding against retrying a cooled key
   (`requestExecutor.ts:934`). Directly applicable to N analysts sharing a
   rate-limited Bankr tier.

6. **Skill install: mandatory `sha256` + revocation list.**
   `docs/skills.md:27-33`. If you publish a Bankr skill, this is the bar.

7. **Lazy descriptor evaluation for startup cost.**
   `providerSecrets.ts:36-42` — a deliberate `require()` inside a cached
   function so importing the module on the bootstrap path doesn't evaluate the
   full descriptor graph. Well-commented reasoning.

8. **Regression test for credential cross-contamination.**
   `requestExecutor.test.ts:2370`:
   `'does not use BNKR_API_KEY for non-Bankr OpenAI-compatible routes'`, and
   `providerFlag.test.ts:989` `'clears BNKR_API_KEY copied into OPENAI_API_KEY
   when switching routes'`. Both encode a real leak class. Write the equivalent
   for your treasurer key the day you add a second provider.

---

## 14. Fragile — do not copy

1. **Substring routing on the base URL.**
   `request.baseUrl.toLowerCase().includes('bankr')`
   (`requestExecutor.ts:417`; same at `providerDiscovery.ts:270,317`). Any URL
   containing "bankr" anywhere — path, query string, a proxy hostname like
   `mybankr-proxy.evil.com` — gets the `X-API-Key` header, which means **a
   credential is placed in a header based on a substring match against an
   attacker-influenceable URL**. `openaiModelDiscovery.ts:44-50` does it
   correctly via `new URL().hostname`; the request path does not. Match on
   `routeId`, or on an exact host allowlist.

2. **`BNKR_` vs `BANKR_` split.** `BNKR_API_KEY` but `BANKR_BASE_URL` /
   `BANKR_MODEL` (`src/utils/envFile.ts:26-29`). A silent misconfiguration
   generator.

3. **Credentials copied across env vars in several directions.**
   `BNKR_API_KEY → OPENAI_API_KEY` (`providerFlag.ts:581-583`),
   `profile.apiKey → BNKR_API_KEY` (`providerProfiles.ts:1168-1170,1736-1738`),
   and route *inferred* by comparing key equality
   (`providerFlag.ts:383-385`). It works, and it is guarded by two regression
   tests — but it is aliasing state through a global mutable namespace. For a
   wallet key, use an explicit credential object.

4. **Plaintext API keys in the global config file.**
   `providerProfiles.ts:1452,2127`. Acceptable for an LLM key; **not**
   acceptable for a key that can execute a swap.

5. **No 429 backoff on non-GitHub routes.** `requestExecutor.ts:918`. Bankr
   gets a hint string and one attempt. Given Bankr's rolling-window agent
   quota, you must build this yourself.

6. **No global subagent concurrency cap.** Only
   `GITHUB_COPILOT_MAX_SUBAGENTS` (§9). N-way analyst fan-out against a quota
   needs a bound this repo does not provide.

7. **`.env.example` omits all three Bankr vars** despite being 28KB of provider
   docs. Discoverability gap.

8. **Single hardcoded model in the catalog** (`bankr.ts:36`). Ages badly;
   `claude-opus-4.6` is already behind.

---

## 15. Direct answer: minimum to quote and execute a swap

**This repository does not show you.** It contains zero swap code, zero wallet
code, and zero calls to the Bankr Agent API. I will not reconstruct the steps
from your prompt and present them as findings — that would be inference
dressed as evidence.

What openclaude **does** establish, and all it establishes:

1. To reach a Bankr HTTP surface you need one API key in `BNKR_API_KEY`
   (`src/integrations/vendors/bankr.ts:9`).
2. For the **LLM gateway** (`https://llm.bankr.bot/v1`), auth is
   `X-API-Key: <key>` — **not** `Authorization: Bearer`
   (`requestExecutor.ts:454-456`, `docs/architecture/integrations.md:205-206`).
3. That gateway is otherwise plain OpenAI-compatible: `POST /chat/completions`,
   `GET /models` (`providerDiscovery.ts:279,326`).
4. Credit balance is **not** programmatically readable through the path this
   repo uses (`bankr.ts:39` `usage: { supported: false }`).

Everything in your swap flow — `/wallet/swap-quote`, `/wallet/swap`, chain
`"robinhood"`, `minBuyAmount`, `idempotencyKey`, the 403 location gate —
is **outside this repository's evidence**. Your existing notes remain your only
source; this repo neither confirms nor refutes them.

The one transferable, load-bearing question it raises: **the LLM gateway uses
`X-API-Key`. Verify empirically whether the Agent/wallet API does too, or
whether it uses `Authorization: Bearer`.** Getting that wrong is a silent 401
on your first execute call. This repo is a strong reason not to assume.

---

## 16. Contradictions with your stated Bankr facts

| Your fact | Verdict | Evidence |
|---|---|---|
| Trades: `POST /wallet/swap-quote` → `POST /wallet/swap`, chain `"robinhood"`, contract addresses, `minBuyAmount` + `idempotencyKey` | **Not present** — no evidence either way | 0 hits repo-wide |
| Quotes ungated / execution gated by location verification, 403 with seven causes | **Not present** | 0 hits for `403`-gated swap logic |
| Agent prompts: `POST /agent/prompt` → poll `/agent/job/{id}`; 100 msg/day rolling | **Not present** | 0 hits |
| LLM gateway is `llm.bankr.bot`, OpenAI-compatible | **Confirmed** | `src/integrations/vendors/bankr.ts:7`; `web/src/data/providers.ts:181` |
| LLM gateway is *also* Anthropic-compatible | **Unconfirmed here** — openclaude classifies it strictly `'openai-compatible'` and routes it through the OpenAI shim, never the Anthropic-proxy descriptor type | `bankr.ts:6,15-17`; contrast `ANTHROPIC_PROXY_DESCRIPTORS` at `integrationArtifacts.generated.ts:97`, which contains only `anthropicproxy-custom` |
| Billed from a credit balance | **No contradiction, but balance is unreadable on this path** | `bankr.ts:39` |
| x402 Cloud handlers are bare `Request → Response` | **Not present** | 0 hits for `x402` |
| *(implicit)* gateway auth | ⚠️ **Refinement — the one thing to update in your notes:** auth is `X-API-Key`, treated as a named protocol exception alongside Azure's | `requestExecutor.ts:454-456`; `docs/architecture/integrations.md:205-206,233` |

**Nothing in this repo contradicts your list.** One item refines it
(`X-API-Key`), one is unconfirmed as stated (Anthropic-compatibility of the
gateway — openclaude models it as OpenAI-only), and the rest fall outside its
scope entirely.
