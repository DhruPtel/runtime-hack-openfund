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

### 2.0 SIWE agent wallet, proven once · H

**Added by this plan.** It is a probe, in the manner of 0.x, placed before any
unit that assumes five wallets. It is owed into ROADMAP.

**Goal:** show that `bankr login siwe` can produce one agent account whose key is
read-only, can reach the LLM gateway, and has the Agent API off.

**Build:**
1. **Protect the fund's session first.** Run every agent login with
   `--config <a per-agent file>`, outside the repository, so
   `~/.bankr/config.json` is never touched. Check it afterwards: `bankr whoami`
   under the default config still answers as `0x93fa…a3da`.
2. **Generate one private key** for `price-integrity`. Store it outside the
   repository, mode 0600.
   - **It is setup material, never an agent credential.** It can mint a new key
     for the account, including a read-write one, so it is treated like
     `SIGNING_KEY`.
   - Keep it off the command line where possible. If the CLI's
     `--private-key` flag is the only way, the exposure is a few seconds in the
     process list on a single-user machine, with shell history off. That is
     stated, not hidden.
3. **Log in:**
   `bankr login siwe --private-key … --key-name openfund-price-integrity --no-agent-api --no-token-launch --config …`.
   Leave read-only at its default. Leave the Wallet API on, so the agent can
   read its own address.
4. **Measure the key as probe 0.2 did,** with a never-issued key as the
   control:
   - `GET /wallet/portfolio` returns an `evmAddress`. Record whether it
     differs from the fund's and whether it equals the signer's address.
   - `GET /v1/models`: a **402** `insufficient_credits` means the gateway is
     on. A **403** that names the gateway toggle means it is off. This is
     F0.2.4's discriminator.
   - `GET /v1/credits` shows the balance.
   - The Agent API's state cannot be read (F0.2.5). It is set off by flag and
     asserted in code: no call to `/agent/*`.
5. **Record it** in `research/findings.md` §2.0: measured, documented or
   inferred for each item.

**Artifact:** `research/findings.md` §2.0, and one agent account with its key
in `.env` under a new name.

**Done when:**
- one agent key is measured reaching the gateway (402 or 200, never 403);
- its wallet address is its own;
- it was created with Agent API and Token Launch off;
- the fund's CLI session is unchanged.

**Then:**
- create the other four the same way: three analysts and risk;
- the operator buys each account its credits. That is a spend. Whether
  `bankr llm credits add` works under a read-only key is measured on the first
  purchase.

**If it fails.** No gateway access is the likely way. These are the options, and
the operator chooses:
- **(a) Email sign-ups.** `bankr login email … --llm` is the CLI path that sends
  the gateway toggle. It keeps everything that was decided. It costs five email
  identities and five one-time codes. Whether plus-addressing works is unknown.
- **(b) Enable the gateway on the SIWE account another way.** The dashboard at
  `bankr.bot/api-keys` is one. Whether a SIWE-made account can sign in there is
  unknown.
- **(c) Own wallets, but inference on the fund's key.** Each agent keeps its
  own account and address. It **gives up** "each agent pays for its own
  inference", and per-agent cost goes back to F0.6.4's aggregate. This is a
  stated reduction, not a fallback.
- **Ruled out: one shared wallet.** It collapses what is being demonstrated.

**If credits cannot be bought under a read-only key,** the operator buys them
with a second, read-write key for that account. The operator holds that key and
it never enters an agent process. The SIWE private key can mint one.

**Full version:** a scripted onboarding for N agents, with each key's
permissions verified live, a refused write included, and keys rotated on a
schedule.

### 2.1 ▶ The report format · L · **a stop**

**Goal:** a report the operator would pay for, written by hand before any code.

**Build:** by hand, against the committed capture `253315c0…`:
- **four example reports, one per seat.** Each is in its seat's vocabulary and
  covers what that seat would really say about that snapshot;
- **every number checked against the snapshot;**
- **one short note** on how a reader tells evidence, which is snapshot values,
  from opinion, which is the model's prose.

The starting point is what the record settles (above) and the sketch in
SIMPLIFICATION.md, "The report format". **The stop decides the format. This
plan does not.** Questions the stop answers:
- how many calls a report makes;
- how a condition seat's caution attaches to an asset;
- whether key values are field paths that code resolves or numbers the model
  writes;
- what a whole-report `NO_CALL` looks like beside a per-asset one;
- what confidence means.

**Artifact:** `planning/REPORT-FORMAT.md`, the four hand-written reports.

**Done when:** the operator approves or amends it. The approval is recorded in
LESSONS, and 2.2 and 2.3 are built from what was approved.

**Could change:**
- the schema (2.2);
- the brief (2.3);
- the model;
- the price;
- whether four seats is right.

**Full version:** sections, depth, evidence citation and conviction told from
speculation, approved at its own stop (PLAN §8 2.1). The minimal version keeps
the stop and shortens the report: a summary and key values, not research.
