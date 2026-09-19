# Phase 2: analyst contract and fan-out

**Status, 2026-09-19:**
- 2.0 ran, and SIWE gives no gateway access; the options wait on the operator;
- 2.1 was approved;
- **2.2 to 2.5 are built and tested offline** (LOGS);
- 2.6 onward needs a live key, and `BANKR_LLM_KEY` is still not read-only.

Nothing has run live. This file was written as the plan before any Phase 2 work,
and each unit below now carries a note on what was built. It gives each unit at
the minimal scope approved in `SIMPLIFICATION.md`, in the shape `PHASE-0-1.md`
uses:
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
  approves before any code. The pivot pass had recorded this stop as spent.
  That was corrected on 2026-09-19 in `CLAUDE.md`, PLAN §8, ROADMAP and
  SIMPLIFICATION.md (LESSONS 2026-09-19).
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

**Ran 2026-09-19. Three requirements pass, one fails** (`research/findings.md`
§2.0).

| Requirement | Result |
|---|---|
| Its own address | Pass. `0x42a9…3d27`, a new Bankr wallet that is neither the fund's nor the signer's. |
| Read-only | Pass. A signature and a swap were both refused 403 "Read-only API key". |
| Agent API off | Pass. `/agent/prompt` was refused 403 "Agent API access not enabled". |
| LLM gateway | **Fail.** Every gateway call was refused 403 "does not have LLM Gateway access enabled". That is the same body as `BANKR_KEY_READ`'s. |
| Buying its own credits | Refused too, at the gateway toggle. |

The fund's CLI session was untouched, and $0 was spent.

**The five-wallet plan cannot proceed as designed through SIWE alone.** The
options are in §2.0's verdict:
- (a) email sign-ups with `--llm`, untested;
- (b) the dashboard, unknown for a SIWE account;
- (c) own wallets with inference on the fund's key, available now.

One shared wallet stays ruled out. **2.4's credential rows and every live run
wait on the operator's choice.** 2.1, a stop, and the offline work in 2.2–2.4
do not.

**Measured later the same day, and it bears on (c)** (LESSONS 2026-09-19,
`probes/keymap.py`):
- `BANKR_LLM_KEY` is **not read-only**;
- the **Agent API is on** for all three fund keys.

Option (c) would put that key in every analyst process. As the keys stand, that
breaks invariant 1. Before (c) could be taken, the operator would have to change
`BANKR_LLM_KEY` to read-only with the Agent API off.

**2.1 shown, 2026-09-19:** `planning/REPORT-FORMAT.md`, four hand-written
reports and the decisions behind them. It waits at its stop.

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

### 2.2 Output schema · L

**Goal:** a reply is accepted only in the shape 2.1 approved, and refused by
name otherwise.

**Build:** `agents/schema.py`, stdlib only, like `core/types.py`. One validator
for the approved shape. It checks:
- required fields and their types;
- that each call comes from its seat's vocabulary;
- that confidence is between 0 and 1;
- that every asset is named by `(chain_id, address)` inside the snapshot's
  tradeable set, since tickers never resolve an asset;
- that every cited field path exists in the snapshot;
- that the snapshot hash is echoed back and equal;
- that a whole-report `NO_CALL` is accepted (invariant 6).

Each refusal names its rule.

**Artifact:** `agents/schema.py` and `tests/test_schema.py`, built from recorded
replies where they exist. 1.8's price-trend reply named assets by symbol and
called below-line names, so it is a real refusal at the address rule.

**Done when:** the approved example passes, and each rule refuses a recorded or
constructed bad reply at its own rule.

**Full version:** hard validation of every field, out-of-scope claims refused
per seat, and values checked as well as paths (§9 analyst contract).

**Built 2026-09-19** (`agents/schema.py`, `5f108aa`):
- all four approved examples are accepted, parsed straight from
  `REPORT-FORMAT.md`;
- a fabricated figure is refused, naming the field and its real value;
- each rule refuses by its own name.

**One rule changed while building.** A figure is the field it cites when the
field lies within half a unit of the figure's last digit, the midpoint included.
The capture holds AMZN's close of 266.085, which the approved report writes as
266.08. Strict round-half-up refused that correct figure (LESSONS 2026-09-19).

### 2.3 Brief · L

**Goal:** every seat gets the same snapshot bytes and a question of its own.

**Build:**
- **`agents/briefs/analyst.v1.md`,** versioned in its filename. It holds:
  - the seat's question from `config/analysts.json`;
  - the rules 0.9's brief states: answer only from the snapshot, respect
    `NO_CALL`, cite fields, and no sizing, execution or spend authority;
  - the approved format;
  - the snapshot's bytes, appended verbatim.
- **`config/analysts.json` to version 2:**
  - the fourth seat becomes `price-integrity`;
  - each seat's vocabulary;
  - every seat universe-wide, disjoint in question.

**Artifact:** the brief, `analysts.json` v2, and a test that the four rendered
briefs carry a byte-identical snapshot section with the same hash. That is §9's
"all analysts provably received the same snapshot".

**Done when:** that test passes, and a seat with no question in config refuses
to render.

**Full version:** mandate text, explicit scope boundaries, effort scaling, and
assets partitioned per seat.

**Built 2026-09-19, one file per seat, as the batch brief asked** (`de1a6af`):
- `briefs/<seat>.v1.md` holds each seat's mandate, vocabulary, what to read and
  effort guidance;
- the seat's question and the questions it leaves to others come from
  `config/analysts.json`, filled in when the brief is built;
- `briefs/analyst.v1.md` is the shared output contract, with the approved NVDA
  call as its example;
- the snapshot goes in as byte-identical text, named by its sha256.

### 2.4 Runner · **H**

**Goal:** four analyst processes on one snapshot, each bounded, and each
outcome disclosed.

**Build:**
- **`agents/runner.py` starts four analyst processes in parallel.**
- **Each child's environment is built from nothing:** its own gateway key, plus
  `PATH` and `PYTHONPATH`.
  - The runner never calls `load_environment()`, and never passes its own
    environment through.
  - Children never read `.env`, and take their one credential from their
    environment only.
  - This is what keeps `BANKR_KEY_EXEC`, `SIGNING_KEY` and every other agent's
    key out of each analyst process (finding 2).
  - `.env` is still readable on disk from any process on this machine.
    Separating the files is 4.12's work.
  - **The claim is about the environment, not the filesystem.**
- **`agents/analyst.py`:** brief, call, parse, validate (2.2), write the result.
- **`adapters/bankr_llm.py`:**
  - one attempt at the transport, with a 600 s timeout and no endpoint
    rotation;
  - the refusal's body kept (finding 3);
  - the `usage` block captured;
  - never retries a timeout, because a timeout is billed (F0.9.3).
- **The retry:** once, and only for a reply that arrived and failed 2.2. Its
  timeout is what remains of the worker's 630 s, less a margin. Everything
  else is a failed worker with its reason: timeout, transport, refused or
  invalid.
- **The result:** each seat is `ok`, `no_call` or `failed`, and the cycle is
  `partial` if any seat failed. Whether a partial cycle may decide is Phase 3's
  quorum.
- **The event log,** `runs/<cycle>/events.jsonl`, has one line per start,
  finish or failure: seat, agent address, latency, cost and status. It carries
  no secret, since redaction is installed.
- **`credentials.py`:** five new rows, four analysts and risk.
  - Each is loadable only by its own new role.
  - Each has `can_transact=False`.
  - Each has the scope measured at 2.0.
- **`.env.example`:** the five names.
- **Config:** the four values below.

**Artifact:** the runner, the analyst worker, the LLM client, and the
credential rows, with tests on a fake gateway.

**Done when, offline:**
- four processes run in parallel within their deadlines;
- a hung worker is cut at its deadline and the cycle completes;
- a malformed reply retries once, then fails with its rule named;
- the cycle says `partial` when a seat failed.

**The H proof, each rule broken in a copy and shown to fail a test:**
- inside each child, every declared credential except its own is absent from
  the environment. Break it by passing the runner's environment through;
- the deadline;
- the single retry;
- the partial flag.

**Full version:** bounded width from config, fallback models, pre-allocated
result slots, retry budgets per failure kind, and deployed isolation across
hosts with files per role (PLAN §8 2.4, 4.12).

**Built 2026-09-19** (`agents/runner.py`, `agents/analyst.py`,
`adapters/bankr_llm.py`; `f38596f`, `30cfb4e`):
- **Where keys come from is a parameter:** `PerAgentKeys` or
  `SharedGatewayKey`. Neither is hard-coded.
- **The H proof, each guard broken in a copy and caught by its own test:**
  - with the runner's environment passed through, every analyst could see
    `BANKR_KEY_EXEC`, `SIGNING_KEY`, `BANKR_KEY_READ`, the RPC URL, the other
    agents' keys and an unrelated secret, and the test failed;
  - so did skipping the check against treasurer keys, retrying a timeout,
    dropping the partial flag, not enforcing the cycle deadline, not bounding
    the width, and not retrying a malformed reply.
- **Not built yet:** no entry point runs it live. That is owed at 2.6, once a
  safe key exists.

### 7.6, first slice: the swarm on a page · L · *recommended, not yet approved*

See "The page" below. If approved, it lands here.

**Goal:** the swarm's first real run is watched, not read from files.

**Build:** one static HTML file with plain JavaScript, no build step and no
dependency. It is served locally by the standard library's `http.server` from
the run directory, and polls `events.jsonl` and the results every few seconds.
It shows:
- four seat cards: the seat, the agent's address, and a status (waiting,
  thinking with elapsed time, done, `NO_CALL`, or failed with its reason);
- latency and cost;
- then the summary and calls, with the key values shown;
- a banner when the cycle is partial.

It reads nothing outside the run directory.

**Artifact:** `surfaces/page/index.html`.

**Done when:** a fake-gateway run shows all four states, including a failed
seat.

**Full version:** 7.6's public page over published previews, with every later
panel.

### 2.5 Token accounting · L

**Goal:** every call's cost is recorded where it happens, against the agent
that paid.

**Build:** *(superseded by the batch brief, see "Built" below)* per call, in
the worker's result and the event log:
- the response's `usage` block;
- the price at the published rate, with where the rate came from;
- the agent account's `/v1/credits` before and after.

A timed-out call is recorded as billed with no report, its cost known only from
the balance. `/v1/usage` is not used, because it was seen going backwards
(F0.9.2).

**Artifact:** cost fields in results and events.

**Done when:** they are computed on the fake gateway. Then, live at 2.6, the
rate, the `usage` block and the balance agree, as they did at 0.9, or the gap
is recorded.

**Full version:** per-call counts reconciled to `/v1/usage` in settled windows,
aggregate to aggregate (F0.6.4).

A balance delta is that agent's spend only while nothing else uses the
account, because credits are wallet-scoped (F0.6.6). One account per agent is
what makes that hold.

**Built 2026-09-19, as the batch brief asked, and not as planned above**
(`bankr_llm.cost`, `adapters/bankr_usage.py`; `ac543bc`, `4b02ed7`):
- **Each call's cost** comes from its own usage block at the listed price. It
  reproduces 1.8a's $0.264272 exactly.
- **Every figure is labelled an estimate:** per call, per analyst and per
  cycle. Calls of unknown cost, such as a timeout, are counted, not zeroed.
- **The cross-check is aggregate against aggregate,** in one settled
  `/v1/usage` window, with the window's dates read back from the provider.
- **No before-and-after delta is used,** of credits or of usage.
- **Tested on real data.** The recorded settled window reconciles exactly
  against its six recorded calls ($1.105746).
- **What is given up:** per-agent credit deltas as the check. So "each agent
  pays" is shown by each call's key, not by a balance.

### 2.6 ▶ First real report · L · shown, not stopped

**Goal:** one real analyst report on a real snapshot, with its cost and
latency.

**Build:** nothing new. Run one seat through the runner on the committed
capture:
- **the seat is `price-integrity`:** it is new, and the closed-session risk
  moment rests on it (SIMPLIFICATION.md, Q2);
- **the key is its own account's,** if 2.0 passed;
- **if 2.0 has not passed,** it runs on the fund's key, labelled as such. It is
  only a quality check and never the swarm. $0.937 covers about three calls.

**Artifact:** the report, its raw reply, cost, latency and events, on the page
if the slice was pulled forward.

**Done when:**
- it validates;
- its key values resolve to the snapshot;
- its cost is within 1.8a's range, or the difference is explained;
- how far it sits from 2.1's example is written down.

**Full version:** a stop to judge the gap from 2.1.

### 2.7 Report store · L

**Goal:** a report is kept once, under its own hash, as the record every later
unit cites.

**Build:** each result written once as canonical JSON named by its sha256. It
holds:
- the parsed report;
- the raw reply;
- the `usage` block;
- the seat;
- the agent's address;
- the snapshot hash.

A second write of the same name must match, or it fails. Keeping the raw reply
is what lets 3.9 replay from recorded outputs (invariant 7).

**Artifact:** the store, and the exit run's reports committed as a fixture after
a scan for every declared credential. 3.x and 3.9 replay from that fixture.

**Done when:** a rewrite with different bytes is refused, and the fixture
round-trips.

**Full version:** a content-addressed store in SQLite, queryable (PLAN §5).

### 2.8 ▶ Failure drill · L · shown, not stopped

**Goal:** a broken worker is disclosed, and the cycle completes.

**Build:** three offline tests on the fake gateway:
- **malformed:** it retries once, then fails with its rule named;
- **hung:** it is cut at its deadline;
- **`NO_CALL`:** accepted and counted as an abstention.

Each ends with the cycle complete and marked `partial` where a seat failed. The
page shows a failed seat.

**Artifact:** the tests.

**Done when:** all three pass.

**Full version:** a live drill of all three.

### The exit run

**The phase's exit:** all four seats produce valid reports from one snapshot id,
each on its own account; failures are visible and non-fatal; and the format was
approved at 2.1.

**The run:** four calls, about $1.06, on the committed capture or a fresh live
snapshot. Whether the gateway serves four accounts' calls at once without
throttling is unmeasured, and this run measures it.

---

## The four null values that block 2.4

These are proposals. 2.4 writes them into config once approved.

| Key | Value | Why, from the record |
|---|---|---|
| `cadence.cycle_deadline_seconds` | **1,800** | A snapshot build takes about 150 s. The analysts run in parallel, bounded at 630 s. Risk is one call, also bounded at 630 s. Re-quoting a plan of at most 8 orders takes seconds. The bounds sum to about 1,410 s; the rest is margin. A typical cycle is about 4 minutes: 150 + 75 + 8 s. The deadline matters only in the tail. |
| `cadence.retry_budget_per_worker` | **1** | §9: a malformed reply retries once, then the worker is recorded as failed. A timeout is never retried, because it is billed (F0.9.3) and has used 600 s. After a typical 62–75 s first call about 550 s remain. That covers a retry at 1.7's fast rate (about 121 tokens/s) but not at 0.9's slowest (about 17 tokens/s). So a slow retry can be cut off and billed. This is stated, not hidden. |
| `models.risk_model` | **`claude-sonnet-5`** | 1.7 measured a risk call on it: $0.048, 7.7 s. It matches the analysts, so there is one pricing basis and one set of measurements. The 180× spread across models (F1.7.7) is a later lever, pulled with evidence. |
| `models.context_budget_tokens` | **70,000** | Invariant 3's bundle is every full report, the sized plan and the risk output. Four replies at the 12,000-token cap are 48,000 at most. The plan is at most 8 orders plus the demonstration leg, each with its asset's three prices and findings; about 8,000 with the risk brief. Risk's own reply is 12,000 at most. That totals about 68,000. |

**On the context budget.** It is measured before the call from the bundle's
bytes divided by 1.8, the lower of the two measured ratios, so it overcounts
and errs toward vetoing. The gateway has no token-count endpoint (F1.7.2).

**This corrects SIMPLIFICATION.md's proposed 60,000,** which left out the risk
reply that the config note says the budget must cover. The fold is owed.

It is well inside the model's window: 1.7 sent 185,168-token prompts. So it is
the invariant's bound, not the model's limit.

---

## The page: pull a minimal slice forward

**Recommendation: yes.** Build 7.6's first slice after 2.4 and before 2.6, as
planned above.

**Why:**
- **Watched, not read.** Without it, the swarm's first real run (2.6), the drill
  (2.8), and the stops at 2.1, 3.8, 5.4, 6.6 and 7.5 are shown as files and
  terminal output.
- **If time runs out before Phase 7, there is no page at all.** The demo cannot
  be terminal output. This is the strongest reason.
- **It shapes the event log.** A second reader of 2.4's log, arriving now, keeps
  the log's shape honest early.

**What it costs:**
- **Now:** one L unit. That is one static file, no dependency, no server beyond
  the standard library, and no network. A guess is about an hour. That is not
  measured.
- **Later:** a small panel per phase:
  - Phase 3: weights, plan, gates and the verdict;
  - Phases 4 and 5: orders and the transaction link;
  - Phase 6: the books;
  - Phase 7: the preview and the buy link.

  7.6 then becomes making the page public and switching it to previews, not
  building it.
- **Risk:** L. The page reads only the run directory, and the events hold no
  secret.

**What it changes:** the strict unit order decided on 2026-09-19. The first
slice of one Phase 7 unit moves into Phase 2. That is the operator's call. If
it is declined, 2.6 and 2.8 are shown as files and the plan is otherwise the
same.

---

## Where a minimal version would break an invariant

None is proposed. Each is named so it stays out:
- **Analyst processes that call `config.load()` as written** would hold every
  secret in their environment: invariant 1. 2.4 builds each environment
  instead.
- **A runner that passes its own environment to children** breaks invariant 1
  the same way. It is the first thing 2.4's H proof breaks on purpose.
- **Briefs that embed a re-serialised snapshot** instead of its bytes could
  differ between seats: invariant 2. 2.3 appends the bytes and tests that they
  are identical.
- **A store that keeps only a summary** could not replay from recorded outputs:
  invariant 7. 2.7 keeps the raw reply.

**Not an invariant, but ruled out by the operator:** one shared key or wallet
for the four seats. The only exception is 2.6's single quality check on the
fund's key, labelled, and only if 2.0 has not finished.

---

## What Phase 2 ends with

**What a judge could watch.** One command takes the committed weekend capture,
or a fresh live snapshot, and starts four analyst processes:
`price-trend`, `cross-asset-macro`, `execution-quality` and
`price-integrity`.
- Each runs on its own Bankr account, with its own wallet address.
- Each reads the same snapshot bytes, and the hash is shown.

With the page pulled forward, the judge sees:
- **the four seats thinking in parallel** for about a minute;
- **each report landing:** a short summary; calls in its seat's vocabulary,
  buy, hold or sell, or proceed or caution; key values from the snapshot; and
  the call's cost and latency, paid from that agent's own credits;
- **a seat that fails or hangs** shown as failed, with the cycle marked
  partial.

Without the page, the same run is files and terminal output. Behind all of it
sits the hand-written format approved at 2.1.

**What still would not exist.** Nothing combines the reports. There are:
- no weights, no plan and no gates;
- no risk verdict;
- no signed decision record;
- no order and no execution, paper or live;
- no books;
- no x402 sale;
- no public page.

The reports are opinions with no consequence yet. Phase 2 also does not show
that they are worth paying for. That judgment is 2.1's on the example, and 3.8's
on real output.

Identical calls differ by about 18%, so the same snapshot gives different
reports on different runs. Replay uses the recorded outputs (invariant 7), not
fresh calls.

---

## Owed outside this plan's paths, and what has been folded

- **Folded 2026-09-19:**
  - the 2.1 stop, unit 2.0 and the 70,000 budget, into `CLAUDE.md`, PLAN §8,
    ROADMAP and SIMPLIFICATION.md;
  - the stops from Phase 2 are 2.1, 3.8, 5.4, 6.6, 7.5 and 8.5.
- **ROADMAP, still owed:** the 7.6 slice, if approved.
- **Built by the units themselves:**
  - `config/analysts.json` (2.3);
  - `credentials.py` and `.env.example` (2.4);
  - the four config values (2.4);
  - the first of the two `http.py` changes (2.4).
