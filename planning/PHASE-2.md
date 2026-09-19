# Phase 2: analyst contract and fan-out

**Status: a plan, awaiting the operator.** Written 2026-09-19, before any Phase 2
work. Nothing in it is built. It gives each unit at the minimal scope approved
in `SIMPLIFICATION.md`, in the shape `PHASE-0-1.md` uses:
- the goal;
- what gets built;
- the artifact;
- when it is done;
- the risk level;
- the full version, to build later.

**Read first:**
- `CLAUDE.md`;
- the pivot block at the start of PLAN §8;
- the Phase 2 rows in `SIMPLIFICATION.md`.

Phase 2 is the swarm: the first time the fund reasons about anything. Phase 1
gave it something to reason about. This phase gives it four analysts, each in
its own process and on its own Bankr account, reading one frozen snapshot.
Nothing yet combines what they say. That is Phase 3.

## In short

- **2.0 comes first, and it is new.** It proves that one agent account can be
  made by `bankr login siwe`: read-only, with LLM gateway access, Agent API off.
  It must pass before any unit assumes five wallets. The CLI's own source shows
  the SIWE request never asks for gateway access, so this is a real question,
  not a formality. If it fails, the options are below. One shared wallet is not
  among them.
- **2.1 is a stop:** a hand-written example report that the operator reads and
  approves before any code.
  - **This contradicts what the pivot recorded.** `CLAUDE.md`, PLAN §8, ROADMAP
    and SIMPLIFICATION.md say 2.1's stop was spent when the analysis was
    approved.
  - This plan follows the operator's instruction. The contradiction is recorded
    in LESSONS 2026-09-19. The fix to those four files is owed, outside this
    pass's paths.
  - Until it is fixed, `CLAUDE.md`'s "Stop only at…" line would let a session
    walk past 2.1.
- **Risk levels:**
  - **2.4 is H:** the runner, and the separation of keys between processes.
  - **2.0 is H,** because it is about keys (`CLAUDE.md`: spend authority means
    keys and roles).
  - Everything else is L.
- **The four null values that block 2.4,** each set from measurement:
  - `cycle_deadline_seconds`: 1,800;
  - `retry_budget_per_worker`: 1;
  - `risk_model`: `claude-sonnet-5`;
  - `context_budget_tokens`: 70,000.
- **The page: pull a minimal slice of 7.6 forward,** between 2.4 and 2.6, so
  the swarm's first real run is watched rather than read from files. It costs
  one small L unit now, plus one panel per later phase.
- **The spend:**
  - about $1.30 of inference: one call at 2.6 and four at the exit;
  - plus retries;
  - plus the operator's credit purchase in each agent account.

---

## What the record already settles

Not re-decided here.

- **Two vocabularies:**
  - **direction:** buy, hold or sell;
  - **condition:** proceed or caution.

  The one recorded execution-quality report answered `NO_CALL` on all 35
  assets, because buy, hold and sell have no answer for what trading costs
  (LESSONS 2026-09-19).
- **Four seats:** `price-trend`, `cross-asset-macro`, `execution-quality` and
  `price-integrity`. `price-integrity` replaced `fundamentals-calendar`, to which
  the snapshot gave only names and ISINs.
- **Scopes are disjoint in question,** not necessarily in asset set, and are
  partitioned in `config/analysts.json`.
- **One frozen snapshot per cycle,** delivered as bytes, identical for every
  analyst (invariant 2). `NO_CALL` is valid (invariant 6). Analysts never fetch
  their own data and never reach a signing path (invariant 1).
- **Measured:**

  | Fact | Value | Source |
  |---|---|---|
  | One analyst call against the real snapshot | 94,716 input tokens, $0.264, 60 s | 1.8a |
  | Earlier calls | 62–75 s | 1.7 |
  | Output between identical calls at temperature 0 | varies by about 18% (7,725 vs 9,087 tokens) | F1.7.1 |
  | A client-side timeout | is still billed | F0.9.3 |
  | Caching | the gateway does not honour it | F1.8a.4 |
  | Usage attribution | only per key, model and day window | F0.6.4 |
  | Billed output absent from the reply | about 37–50% | F1.7.5 |
  | Snapshot bytes per input token | 1.81 (1.7) and 2.0 (1.8a) | the 1.7 and 1.8a tables |
- **Set:**
  - `max_output_tokens` 12,000;
  - `transport_timeout_seconds` 600;
  - `worker_deadline_seconds` 630;
  - `analyst_model` `claude-sonnet-5` (provisional).

## What reading the code found

Checked read-only on 2026-09-19. **Documented by code, not measured.**

1. **The installed Bankr CLI (0.3.37),** `dist/commands/login.js` and
   `dist/lib/config.js`.
   - **What the SIWE request sends:**
     - `readOnly` (true unless `--read-write`);
     - `walletApiEnabled` (true);
     - `tokenLaunchApiEnabled` (true);
     - `agentApiEnabled` only when `--no-agent-api` is passed; otherwise the
       server decides, and the help text says "enabled by default";
     - `allowedIps` and `allowedRecipients`.
   - **It never sends `llmGatewayEnabled`.** The email flow does, with `--llm`.
     So a SIWE key's gateway access is whatever the server defaults to, which is
     unknown.
   - **The server "creates a wallet"** and returns `walletAddress` separately
     from the signer's address. The agent's wallet is probably a new Bankr
     wallet, not the signing key's own address. That is an inference.
   - **The new key overwrites the fund's session.** It is written to
     `~/.bankr/config.json` unless `--config <path>` or `BANKR_CONFIG` says
     otherwise. That is the fund's CLI session, which 0.7e used to sign.
   - **`--private-key` on the command line** lands in shell history and the
     process list.
   - **No command changes a key's permissions after creation.**
   - **`bankr llm credits add` buys credits "from your wallet".** That is a
     wallet write, which a read-only key may be refused.
2. **`config.load()` merges the whole `.env` into the process environment,**
   then hands the role only its subset.
   - So any process that calls it has `BANKR_KEY_EXEC` and `SIGNING_KEY` in its
     environment, whatever its role.
   - `config.py` already names this single-host case, and the deployed split is
     4.12's.
   - For Phase 2's new analyst processes, it is a design constraint (2.4).
3. **`adapters/http.py` retries.** It moves to another attempt on a hang, a
   5xx, a 429 or an unusable body. A retried model call can bill twice, since
   a timeout is billed (F0.9.3).
   - So the LLM client must make one attempt at the transport.
   - It must keep the refusal's body: a `402 insufficient_credits` names its
     cause.
   - This is the first of the two `http.py` changes owed since 1.5.

---

## The units, in order

2.0 → **2.1 ▶ stop** → 2.2 → 2.3 → 2.4 → *(7.6, first slice, if approved)* →
2.5 → 2.6 → 2.7 → 2.8 → the exit run.
