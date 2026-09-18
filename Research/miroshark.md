# MiroShark → onchain fund: portability audit

Read-only survey of `miro_shark/` (the MiroShark repo; the `./miroshark` at the
repo root is the bash launcher, not a subdirectory). Nothing was modified.

All `file:line` references are relative to the repo root. Where I could not find
something, I say **not present** rather than guessing. Anything I inferred is
marked **[inferred]**.

---

## 1. ORIENTATION

### What it does

Drop in a document (or a question) → MiroShark extracts a Neo4j knowledge graph
from it, turns each graph entity into an LLM persona, runs those personas as
agents across three simulated platforms (Twitter / Reddit / a Polymarket-style
AMM) for N hourly rounds, then has a ReACT report agent write an analytical
report quoting what the agents actually said and how the market moved.
Pitch (`.github/README.md:17`): "**$1** · per simulation · **10 min** · first
result · **100+** · grounded agents". License AGPL-3.0.

Five phases, per `docs/ARCHITECTURE.md:5-15`: graph build → agent setup →
simulation → report → interaction.

### Entry points

| Entry | File | Role |
|---|---|---|
| Flask API | `backend/run.py:25` → `app/__init__.py` `create_app()` | HTTP surface, 19 blueprints |
| Simulation subprocess | `backend/scripts/run_parallel_simulation.py:2863` (`main()`) | the actual round loop; spawned via `subprocess.Popen` |
| Launcher | `./miroshark` (bash, 15.9 KB) | deps + Neo4j + both servers |
| CLI | `backend/cli.py:338+` | thin HTTP client (`ask/list/status/wait/frame/publish/report/cost/health/trending`) |
| MCP stdio server | `backend/mcp_server.py:217` (`list_tools`) | exposes graph queries to Claude Desktop/Cursor |
| Frontend | `frontend/src` (Vue 3 + Vite) | SPA |

### Directory map / LOC (code + md lines, counted with `find … -exec cat`)

```
backend/app/api            19 files   16,393   HTTP blueprints (simulation.py alone = 11,103)
backend/app/services       65 files   32,482   business logic
backend/app/storage        12 files    3,673   Neo4j graph-memory stack
backend/app/prompts        38 files    3,060   prompt registry + en/zh_CN/de/fr locales
backend/app/models          3 files      452   Project / Task dataclasses
backend/wonderwall         38 files    9,084   bundled camel-ai fork = the sim engine
backend/scripts            22 files    9,829   subprocess round loops + sim helpers
backend/tests              79 files   24,807   pytest (test_unit_* / test_integration_* / test_smoke_*)
frontend/src               53 files   50,183   Vue SPA
docs                       47 files    9,908   deep dives + zh-CN translations
```

Biggest single files: `app/api/simulation.py` (11,103), `app/services/report_agent.py`
(3,625), `scripts/run_parallel_simulation.py` (3,168), `app/services/graph_tools.py`
(2,040), `app/services/simulation_runner.py` (1,808), `wonderwall/social_platform/platform.py` (1,694).

---

## 2. THE PERSONA SYSTEM

### How a persona is defined

**Generated, then serialized to disk as a per-platform file.** Two layers:

1. **Internal dataclass** — `WonderwallAgentProfile`
   (`backend/app/services/wonderwall_profile_generator.py:31-71`): `user_id`,
   `user_name`, `name`, `bio`, `persona` (the long character brief), plus
   `karma / friend_count / follower_count / statuses_count`, `risk_tolerance`
   (`"high"|"moderate"|"low"`), `age / gender / mbti / country / profession /
   interested_topics`, provenance (`source_entity_uuid`, `source_entity_type`),
   and MCP tool flags (`tools_enabled`, `allowed_tools`).

2. **Engine-facing serialization** — three writers:
   `to_reddit_format()` (:73), `to_twitter_format()` (:101),
   `to_polymarket_format()` (:131). Persisted as `reddit_profiles.json`,
   `twitter_profiles.csv`, `polymarket_profiles.json` in the sim directory
   (`app/services/simulation_manager.py:434-461`). The Twitter path is CSV
   because the engine reads it with `pd.read_csv`
   (`wonderwall/social_agent/agents_generator.py:63`).

The engine wraps it once more in `UserInfo`
(`wonderwall/social_platform/config/user.py:23`), whose `to_twitter_system_message()`
/ `to_reddit_system_message()` render the actual system prompt. Note how thin
that is — the entire persona reaches the model as one interpolated string:

```python
# wonderwall/social_platform/config/user.py:66-73
# OBJECTIVE
You're a Twitter user, and I'll present you with some tweets...
# SELF-DESCRIPTION
Your actions should be consistent with your self-description and personality.
{description}
```

### How many run per scenario, and who decides

**N = the number of graph entities that survive type filtering. There is no cap
and no target count.** `EntityReader.filter_defined_entities()` returns all
matching entities; `prepare_simulation` generates exactly one profile per entity
(`app/services/simulation_manager.py:355-427`,
`app/api/simulation.py:1864-1870` for the pre-count). The only floor is
"non-zero or fail" (`simulation_manager.py:372-377`).

Per-round *participation* is a separate, random number:

```python
# scripts/run_parallel_simulation.py:1272-1285
base_min = time_config.get("agents_per_hour_min", 5)
base_max = time_config.get("agents_per_hour_max", 20)
target_count = int(random.uniform(base_min, base_max))
...
if random.random() < activity_level:
    candidates.append(agent_id)
selected_ids = random.sample(candidates, min(target_count, len(candidates)))
```

`agents_per_hour_min/max` are themselves **LLM-chosen** at config time, clamped
to 90% of the entity count (`app/services/simulation_config_generator.py:532`,
`:571-572`), with a deterministic fallback of `n//15` … `n//5` (:596-597).

### How scope is divided between personas

**Emergent, not explicit.** There is no scope field, no assignment table, no
"you cover X, they cover Y" language anywhere in the persona prompt. Division
comes from three indirect mechanisms:

- each persona is grounded in a *different graph entity* and that entity's
  neighborhood (`_build_entity_context`, `:523`);
- personas are round-robin interleaved by entity type so early results are
  diverse (`_interleave_by_type`, `:978`);
- individual vs. institutional personas get different prompts and different
  system messages (`_is_individual_entity`, `:610`; `prompts/locales/en/profile_generator.py`).

The persona brief asks for opinions, blind spots and posting style — not a
coverage boundary (`wonderwall_profile_generator.py:823-833`).

### What a persona receives as input, exactly

**At generation time** (`_build_individual_persona_prompt`, `:773-840`):
entity name + type, entity summary, entity attributes JSON, an optional
census "demographic anchor" row, and up to **3,000 chars** of context
(`context_str = context[:3000]`, `:794`). That context is assembled from five
layers (`_build_entity_context`, `:523-601`): entity attributes → its
`related_edges` facts → `related_nodes` summaries → a hybrid
vector+BM25 graph search (`_search_graph_for_entity`, top-30 edges / top-20
nodes, `:470-494`) → optional LLM web enrichment (`:592-598`).

**At simulation time**, per round, an active agent's system message accumulates
injected blocks, then the user message carries the environment dump:

- persona/system message (once, at signup);
- posting rules, injected once per run (`inject_posting_rules_into_graph`, `run_parallel_simulation.py:2452-2462`);
- belief state (`inject_belief_context`) — per-agent;
- round memory (`inject_round_memory`) — **identical string for all agents**;
- market prompt / sentiment prompt (`bridge.get_market_prompt()`) — identical;
- cross-platform digest (`cross_platform_log.build_digest(agent_id, …)`) — per-agent;
- director/counterfactual event text — identical;
- then `env_prompt = await self.env.to_text_prompt()`
  (`wonderwall/social_agent/agent.py:319`), which is a **per-agent recommender
  feed** (see §3).

### What it returns, and whether the schema is enforced

**Two different answers for the two stages.**

*Persona generation output is JSON-mode but only softly validated.*
`llm.chat(..., response_format={"type":"json_object"})` with 3 attempts and
decreasing temperature (`:667-700`); only `bio` and `persona` are checked for
presence and silently defaulted if missing (`:693-697`). Malformed JSON goes
through `repair_json`, then a regex scrape of `"bio"`/`"persona"`, then a
hand-built stub (`_try_fix_json`, `:721-762`). After 3 failures it falls back to
`_generate_profile_rule_based` (`:904`). **No schema library** — `pydantic` is a
declared dependency (`backend/pyproject.toml:50`) but `grep -rn pydantic --include=*.py`
over `app/ scripts/ wonderwall/` returns **nothing**. Everything is
`@dataclass` + `dict`.

*Simulation output is hard-constrained by tool calling.* Agents act via camel
tool calls, not free text:

```python
# wonderwall/social_agent/agent.py:341-353
response = await self.astep(user_msg)
for tool_call in response.info['tool_calls']:
    action_name = tool_call.tool_name
    args = tool_call.args
```

The action space is an explicit `ActionType` list passed in at graph build
(`TWITTER_ACTIONS` / `REDDIT_ACTIONS` / polymarket actions), and includes
`DO_NOTHING` — the existing analogue of `NO_CALL`. An agent that produces no
tool call simply performs nothing that round.

### Can a persona fetch its own data?

**Yes — this is the single biggest divergence from the fund's design rules.**

- At *generation* time the persona generator runs a live hybrid graph search per
  entity (`:470-494`) and an optional LLM web-research call
  (`web_enricher.enrich_if_needed`, `:594`). Every persona therefore sees a
  different, non-snapshotted slice of the graph.
- At *simulation* time each agent pulls its own feed every round:
  ```python
  # wonderwall/social_agent/agent_environment.py:62
  posts = await self.action.refresh()
  ```
  `refresh()` goes to the platform's recommender
  (`wonderwall/social_platform/recsys.py`, twhin-bert for Twitter), so agent 3
  and agent 40 literally see different posts.
- Agents can also call `SEARCH_POSTS` / `SEARCH_USER` / `TREND` as actions
  (`wonderwall/social_agent/agent_action.py`), i.e. issue their own queries
  mid-round.
- Optional per-agent MCP tools go further: a persona with `tools_enabled`
  can hit external MCP servers (`scripts/mcp_agent_bridge.py`, gated by
  `MCP_AGENT_TOOLS_ENABLED`, `run_parallel_simulation.py:2548-2570`).

---

## 3. CONTEXT PASSING

### Do personas see each other's output? When?

Yes, through three channels, all *lagged by at least one round*:

1. **The platform DB.** Agent A's `CREATE_POST` lands in
   `twitter_simulation.db`; agent B may be shown it by the recommender next
   time it refreshes. Within a round all agents step concurrently
   (`asyncio.gather`, `wonderwall/environment/env.py:261`) — so intra-round
   visibility is a race, not a guarantee. **[inferred from the concurrency
   structure; there is no ordering guarantee in code.]**
2. **Round memory.** Built once per round and injected into every active agent
   (`run_parallel_simulation.py:2619`, `round_memory.build_context`).
3. **Market–media bridge.** Twitter/Reddit sentiment → trader prompts; market
   prices → social prompts (`scripts/market_media_bridge.py`).

For the *report* stage, sections deliberately do **not** see each other:

```python
# app/services/report_agent.py:2655-2659
content = self._generate_section_react(
    section=section,
    outline=outline,
    previous_sections=[],  # parallel: sections don't see each other
```

A later synthesis pass stitches them (`_generate_synthesis`, `:2465`).

### Is there shared state, and who writes to it?

Multiple writers, no single one. Per run:

| State | Owner | Writers |
|---|---|---|
| `twitter/reddit/polymarket_simulation.db` (sqlite) | the `Platform` coroutine | every agent, via `Channel` messages |
| `RoundMemory._rounds` | `RoundMemory` | the round loop, once per platform per round (`record()`, `round_memory.py:201`) |
| `MarketMediaBridge` | bridge | round loop (`update_sentiment`, `update_prices`) |
| `CrossPlatformLog._log` | log | round loop (`record()`) |
| `BeliefTracker.belief_states` | per platform | `after_round()` |
| `<platform>/actions.jsonl` | `PlatformActionLogger` | round loop (append-only) |
| `run_state.json` | `SimulationRunner` | the Flask-side monitor thread, every 2 s (`simulation_runner.py:490`) |
| Neo4j graph | `GraphMemoryUpdater` (background thread) | batched agent activity (`graph_memory_updater.py:304`) |
| agent system messages | round loop | **mutated in place** each round by the `inject_*` helpers (`round_memory.py:447-466`) |

That last one matters: context is delivered by **string surgery on a mutable
system message**, marker-replace style, not by rebuilding a prompt. It works,
but the agent's prompt is stateful across rounds.

### Compression / summarization between stages

Yes, in four places:

1. **Round memory sliding window** (`scripts/round_memory.py:213-287`):
   ancient batched summary → individually LLM-compacted rounds → **full detail
   of round N-1** → partial detail of round N. Compaction of round N-2 runs in
   a background thread (`compact_previous_round`, `:289`) with a plain
   action-count fallback if it isn't ready.
2. **Feed compaction** before the env dump — `_compact_posts_for_agent`
   (`lib/env_compact.py`, called at `agent_environment.py:65`).
3. **Report section context budget**: `MAX_PREVIOUS_TOTAL = 6000` chars across
   all previous sections (`report_agent.py:2155`) — vestigial in parallel mode,
   which passes `[]`.
4. **Synthesis input truncation**: `sec[:3000]` per section (`:2484-2486`).

### Exact data path, scenario input → final report

```
document / URL / question
  └─ POST /api/graph/build                     (app/api/graph.py:285)
      └─ text_processor: chunk (1500/100)      (config.py:123-124)
          └─ graph_builder.add_text_batches    ThreadPoolExecutor max_workers=6
              └─ NER (NER_* slot) → embed → entity resolution
                 → contradiction detection → MERGE Entity / CREATE RELATION
                 carries: name, summary, attributes, fact, embeddings,
                          valid_at, invalid_at, kind, source_type, source_id
  └─ POST /api/simulation/prepare              (app/api/simulation.py:1746)
      ├─ EntityReader.filter_defined_entities  → N entities (+ edges)
      ├─ WonderwallProfileGenerator.generate_profiles_from_entities
      │     ThreadPoolExecutor(parallel_count, default 15)  (:1172)
      │     per entity: 5-layer context (≤3000 chars) → LLM → WonderwallAgentProfile
      │     writes reddit_profiles.json / twitter_profiles.csv / polymarket_profiles.json
      └─ SimulationConfigGenerator → simulation_config.json
            carries: time_config (hours, minutes_per_round, agents_per_hour_*,
            peak/off-peak hours), agent_configs (activity_level per agent),
            event_config (initial_posts, initial_markets), simulation_requirement
  └─ POST /api/simulation/start                (app/api/simulation.py:3124)
      └─ SimulationRunner.start_simulation     (simulation_runner.py:204)
          subprocess.Popen(run_parallel_simulation.py --config … [--max-rounds]
                           [--start-round] [--cross-platform])
          + monitor thread tailing actions.jsonl every 2 s
  └─ run_synchronized_simulation               (run_parallel_simulation.py:2332)
      setup: agent graphs per platform, wonderwall.make(semaphore=60), env.reset()
      round 0: initial_posts + initial_markets seeded as ManualActions
      for round_num in range(start_round, total_rounds):      (:2589)
          memory_ctx   = round_memory.build_context(round_num) (:2619)   ← identical to all
          market/sentiment prompts from bridge                          ← identical to all
          per platform: active = get_active_agents_for_round(...)        ← random subset
              inject belief / memory / market / cross-platform / director
              actions = {agent: LLMAction() for …}; await env.step(actions)
          asyncio.gather(all platform coros, timeout=600s)     (:2744)
          post-round: fetch_new_actions_from_db → belief.after_round →
                      bridge.update_* → round_memory.record → actions.jsonl
          round_memory.compact_previous_round(round_num)
      finalize: trajectories saved, log_simulation_end
  └─ POST /api/report/generate                 (app/api/report.py:38)  ← manual, not automatic
      └─ ReportAgent.generate_report           (report_agent.py:2511)
          plan_outline (SMART slot, chat_json, temp 0.3)       (:2011)
          ThreadPoolExecutor(min(6, n_sections))               (:2690)
            per section: ReACT ≤8 iterations, 2–6 tool calls   (:2181-2320)
              tools read sim_dir/<platform>/actions.jsonl, polymarket db,
              trajectory.json, Neo4j (search / clusters / paths / interviews)
            reasoning trace → (:Report)-[:HAS_SECTION]->(:ReportSection)-[:HAS_STEP]->(:ReasoningStep)
          _generate_synthesis over sec[:3000]                  (:2465)
          writes meta.json / outline.json / progress.json / section_NN.md / full_report.md
  └─ derived surfaces: signal.json → signed-result.json, cost.json, transcript.md,
     trajectory.csv, agents.json, chart.svg, notebook.ipynb, archive.zip, cite.bib
```

---

## 4. THE KNOWLEDGE GRAPH

### Stored what, where, queried how

**Engine:** Neo4j, one `:Graph` node per graph_id, accessed through
`Neo4jStorage` (`backend/app/storage/neo4j_storage.py`, 1,117 lines), which
`create_app()` puts on `app.extensions['neo4j_storage']` as a singleton
(per `CLAUDE.md`, "Neo4j is a singleton via DI").

**Schema** (`app/storage/neo4j_schema.py`):

- Node labels: `:Graph`, `:Entity`, `:Episode`, `:Community`, `:Report`,
  `:ReportSection`, `:ReasoningStep` — uniqueness constraints on each uuid.
- One edge type carries all knowledge: `:RELATION`, with properties
  `uuid, graph_id, name, fact, fact_embedding, attributes_json, episode_ids,
  created_at, valid_at, invalid_at, expired_at, kind, source_type, source_id`
  (`neo4j_storage.py:432-459`).
- Indexes: fulltext on `Entity(name, summary)` and `RELATION(fact, name)`;
  vector (cosine, `Config.EMBEDDING_DIMENSIONS`, default 768) on
  `Entity.embedding`, `RELATION.fact_embedding`, `Community.summary_embedding`;
  plain indexes on `valid_at`, `invalid_at`, `kind`.
- `:Community` clusters via Leiden + LLM title/summary; `MEMBER_OF` edges.
- Reasoning traces: `(:Report)-[:HAS_SECTION]->(:ReportSection)-[:HAS_STEP]->(:ReasoningStep)`,
  step `kind ∈ {thought, tool_call, observation, conclusion}`
  (`app/storage/reasoning_trace.py:1-20`).

**Query path:** `storage.search(graph_id, query, limit, scope, as_of,
include_invalidated, kinds)` (`neo4j_storage.py:559`) → `search_service.py`
fuses three retrievers (vector HNSW / BM25 fulltext / BFS from seed entities,
pool 30) → optional BGE-reranker-v2-m3 cross-encoder → top-`limit` tagged with
`_sources` ("v"/"k"/"g"). Also direct Cypher helpers:
`get_degree_centrality` (:910), `get_bridge_entities` (:931),
`get_shortest_path` (:971), `get_entity_communities` (:996).

### What makes it temporal

**Bi-temporal edge properties plus a point-in-time filter, i.e. Graphiti-style.**

```
# app/storage/search_service.py:31-36
"(($as_of IS NULL AND ($include_invalidated OR r.invalid_at IS NULL))"
"($as_of IS NOT NULL"
"  AND (r.valid_at IS NULL OR r.valid_at <= $as_of)"
"  AND (r.invalid_at IS NULL OR r.invalid_at > $as_of)))"
```

- `created_at` = ingestion time; `valid_at` = when the fact became true
  (caller-settable: `add_text(valid_at=…)`, `neo4j_storage.py:203`);
  `invalid_at`/`expired_at` set by `invalidate_edge()` (:604).
- Supersession is **LLM-adjudicated**: `ContradictionDetector.detect()` runs
  before each CREATE batch and returns edge uuids to invalidate
  (`neo4j_storage.py:411-421`).
- Epistemic dimension: `kind ∈ {fact, belief, observation}`, filterable
  (`_EDGE_KIND_FILTER`, `search_service.py:40`). Simulation-agent edges get
  `kind="belief"` when the whole batch is expressive actions, else
  `"observation"`; `source_type="agent"`; `source_id="<platform>:round_<n>"`
  (`app/services/graph_memory_updater.py:320-338`).
- Nothing is time-versioned at the *node* level — only edges.

### Could it store position history and per-analyst track record?

**Partly, and not the way you'd want.**

*Position history:* the graph is fed only through `add_text()`, i.e. free text →
NER → entities/relations. `GraphMemoryUpdater` literally renders actions as
prose first — `f"{self.agent_name}: {description}"`
(`graph_memory_updater.py:51`), e.g. `Posted a post: "…"`. Numbers survive only
as whatever NER happens to extract. Putting a position ledger through that is
lossy by construction. **[inferred: no numeric-fact ingestion path exists; the
only writer that bypasses NER is the reasoning-trace recorder, which writes its
own node labels directly.]**

The good news: a real ledger already exists elsewhere, in SQLite:

```sql
-- wonderwall/simulations/polymarket/schema/trade.sql
CREATE TABLE IF NOT EXISTS trade (
    trade_id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL, market_id INTEGER NOT NULL,
    side TEXT NOT NULL, outcome TEXT NOT NULL,
    shares REAL NOT NULL, price REAL NOT NULL, cost REAL NOT NULL,
    created_at TEXT NOT NULL, ...);
```

plus `position.sql` (current holdings, `UNIQUE(user_id, market_id, outcome)`)
and `portfolio.sql` (cash balance). That's append-only trade history + current
position — exactly the shape a fund needs, just scoped to one simulation's
sandbox DB.

*Per-analyst track record:* the ingredients exist but are per-run, not
cross-run: `/influence` leaderboard (`app/api/simulation.py:3811`),
`agents.json` roster with `final_stance / final_position / rounds_participated`
(`app/services/agent_export.py:20-45`), `trajectory.json`, and
`agents/sparklines`. There is **no cross-simulation agent identity** —
`user_id` is just the enumeration index (`generate_single_profile(idx, …)`,
`:1128`) and usernames get a random 3-digit suffix (`_generate_username`, `:397`).
So "was analyst #3 right last week" has no key to join on today.

---

## 5. ORCHESTRATION

### Who decides what runs when

**Code and config, not a lead agent.** There is no orchestrator agent anywhere
in the tree. The sequencing lives in three places:

1. **The caller** (frontend, CLI, or a test script like
   `scripts/test_full_pipeline.py:280` `main()`) drives phase order by calling
   `/api/graph/build` → `/api/simulation/prepare` → `/api/simulation/start` →
   `/api/report/generate`. Report generation is **not** auto-triggered on
   completion — `_monitor_simulation` fires push/webhook/Discord/Slack/email
   notifications only (`simulation_runner.py:505-534`).
2. **`run_synchronized_simulation`** (`scripts/run_parallel_simulation.py:2332`)
   owns the round loop, lock-step across platforms.
3. **An LLM decides the *parameters*** — total hours, minutes per round,
   agents-per-hour band, peak hours, initial posts, the prediction-market
   question — at config-generation time
   (`app/services/simulation_config_generator.py:522`, `:298-300`).

**No scheduler exists.** `grep -rni "apscheduler|celery|cron"` over `app/` and
`scripts/` returns only unrelated prose. Everything is request-triggered.

### Fan-out: parallel or sequential

Parallel at four levels, all thread/asyncio, all in-process:

| Level | Mechanism | Limit |
|---|---|---|
| Graph chunks | `ThreadPoolExecutor` | `max_workers=6` (`app/services/graph_builder.py:58`) |
| Persona generation | `ThreadPoolExecutor` | `parallel_count`, default 15 (`wonderwall_profile_generator.py:1172`); API default 5 (`app/api/simulation.py:1856`) |
| Platforms per round | `asyncio.gather(..., return_exceptions=True)` | 3, 600 s timeout (`run_parallel_simulation.py:2744`) |
| Agents within a platform | `asyncio.gather(*tasks)` | `asyncio.Semaphore(semaphore=60)` (`wonderwall/environment/env.py:86`, `:189-192`, `:261`) |
| Report sections | `ThreadPoolExecutor` | `MAX_PARALLEL_SECTIONS = 6` (`report_agent.py:1101`, `:2690`) |

The per-agent hot path:

```python
# wonderwall/environment/env.py:189-192
async def _perform_llm_action(self, agent):
    async with self.llm_semaphore:
        return await agent.perform_action_by_llm()
```

### Failure / timeout / garbage

Isolation is decent at the agent level and coarse at the platform level.

- **One agent fails:** swallowed. `perform_action_by_llm` catches everything,
  emits an error event, and **returns the exception object as its result**
  (`wonderwall/social_agent/agent.py:365-372`). Because `env.step` uses bare
  `asyncio.gather(*tasks)` without `return_exceptions`
  (`env.py:261`), this is what keeps one bad agent from killing the round.
- **Garbage output:** there is nothing to validate — output is a tool call or
  nothing. A model that emits prose instead of a tool call produces zero
  actions, silently. Empty/`<think>`-only LLM content is normalized to `None`
  by the client (`app/utils/llm_client.py` `chat()` tail) so callers' retry
  paths engage.
- **Platform hangs:** `MIROSHARK_ROUND_TIMEOUT`, default **600 s**
  (`run_parallel_simulation.py:181`). On timeout the round is abandoned for all
  platforms and the loop continues (`:2748-2755`).
- **Persona generation fails:** 3 attempts → `repair_json` → regex scrape →
  rule-based profile → per-entity fallback stub `WonderwallAgentProfile`
  (`wonderwall_profile_generator.py:1148-1160`, `:1216-1226`). A run never
  aborts over a bad persona; it silently ships a degraded one.
- **Report section fails:** the section body becomes the literal string
  `*(Section generation error: {e})*` and the report completes
  (`report_agent.py:2665-2668`).
- **Subprocess dies:** monitor thread marks FAILED, captures the last 2,000
  chars of `simulation.log`, fires failure notifications
  (`simulation_runner.py:543-566`).
- **Retries:** none in `LLMClient.chat` itself — it raises. Retry lives at call
  sites: persona gen `max_attempts=3` with `time.sleep(1*(attempt+1))`
  (`:667`, `:716`), config gen `max_attempts=3`
  (`simulation_config_generator.py:469`), graph-memory writes `MAX_RETRIES=3`
  (`graph_memory_updater.py:185`), Neo4j `MAX_RETRIES=3` / `max_attempts=5`
  (`neo4j_storage.py:40`, `:78`).

### Is a run resumable?

**Partially — the durable parts resume, the in-memory parts don't.**

`POST /api/simulation/start {"resume": true}` reads `current_round` from
`run_state.json` and passes `--start-round` (`app/api/simulation.py:3178-3184`
→ `simulation_runner.py:338-339`). What survives:

- ✅ sqlite platform DBs — deletion is guarded by `if start_round == 0`
  (`run_parallel_simulation.py:2394`, `:2423`, `:2441`);
- ✅ belief states — persisted to `belief_states_<platform>.json` and reloaded
  in the tracker's constructor (`scripts/belief_integration.py:138-141`);
- ✅ `actions.jsonl` (append mode; monitor seeks past existing bytes,
  `simulation_runner.py:459-469`);
- ❌ **round memory** — `RoundMemory` is in-memory only (`_rounds: Dict`,
  `round_memory.py:186`); no save/load. A resumed run starts with amnesia and
  rebuilds history from round `start_round` onward;
- ❌ `MarketMediaBridge` and `CrossPlatformLog` — same, in-memory only;
- ❌ round-0 seeding (initial posts/markets) is skipped on resume by design.

Report generation is not resumable, but it *is* incremental: every finished
section is written to `section_NN.md` immediately (`report_agent.py:2705`), so a
crash leaves partial output on disk.

---

## 6. THE REPORT / CITATION LAYER

### How citations are produced and attached

**By prompt instruction only. There is no citation data structure and no
verification step.** The report agent is told to quote:

```
# app/services/report_agent.py:828-830 (SECTION_SYSTEM_PROMPT_TEMPLATE)
   - QUOTE actual agent posts/comments — the report should cite what agents SAID
2. [Must Support Claims with Specific Evidence]
   - Every analytical claim needs a quote or data point as evidence:
```

…and given a tool that returns real quotes with agent name and round:

```python
# app/services/report_agent.py:1778
lines.append(f"  [R{rnd}] {agent} ({atype}): \"{content[:250]}\"")
```

`_execute_simulation_feed` (`:1714`) reads `sim_dir/<platform>/actions.jsonl`
verbatim, filters by platform / round / keyword, and shows up to 15
content-producing actions. So the *evidence* is real and round-addressed. But
the model retypes it into prose, the prompt even instructs it to **translate
quotes into fluent English** (`:837-840`), and nothing afterwards checks that a
quoted string exists in the log. `grep -rni "citation" --include=*.py app/`
finds only provenance surfaces (DKG anchoring, `cite.bib`, `reproduce.json`) —
nothing that binds a sentence to a source row.

What *is* recorded is the agent's own trail: every thought / tool_call /
observation / conclusion per section is flushed to Neo4j as a
`:ReasoningStep` chain (`app/storage/reasoning_trace.py`), queryable via
`storage.get_reasoning_trace(section_uuid)` (`neo4j_storage.py:705`), plus a
per-report JSONL agent log (`ReportLogger`, `report_agent.py:59`).

### Is synthesis LLM, code, or both?

**Both, in a fixed split.**

- LLM: outline planning (`plan_outline`, `:2011`, `chat_json`, temp 0.3);
  each section (`_generate_section_react`, `:2096`, ≤8 iterations, temp 0.5,
  `max_tokens=4096`); cross-section synthesis (`_generate_synthesis`, `:2465`,
  temp 0.4, `max_tokens=2048`).
- Deterministic code: section ordering and stitching, tool dispatch and
  argument validation (`_is_valid_tool_call` against `VALID_TOOL_NAMES`,
  `:1988`), the tool-call budget, markdown assembly, and **every derived
  numeric surface** — `signal_service.compute_signal` (plurality stance +
  confidence = `(leading-33.333)/66.667*100`, quality→risk-tier map),
  `_compute_quality_diagnostics` (`app/api/simulation.py:4279`),
  `run_summary._aggregate` (cost/tokens/latency), `peak-round`, `volatility`.

The numbers a fund would care about are on the deterministic side. The prose is
on the LLM side.

### Final artifact structure

On disk (`report_agent.py:2962-2972`):

```
reports/{report_id}/
  meta.json        # Report dataclass: report_id, simulation_id, graph_id,
                   # simulation_requirement, status, outline, markdown_content,
                   # created_at, completed_at, error   (:440-467)
  outline.json     # title, summary, sections[{title, content}]  (:417)
  progress.json
  section_01.md …
  full_report.md
```

Machine-readable siblings, all off the same simulation dir:
`signal.json` → `signed-result.json` (canonical JSON + HMAC-SHA256 over the
inner `result` block, keyed by `WEBHOOK_SECRET`, `app/services/signed_result.py`),
`cost.json`, `agents.json`, `trajectory.csv/.jsonl`, `polymarket.json`,
`transcript.md/.json`, `chart.svg`, `notebook.ipynb`, `reproduce.json`,
`cite.bib`, `archive.zip`, `badge.svg`, `share-card.png`, `replay.gif`.

---

## 7. LLM PLUMBING

### Providers and models

OpenAI-compatible HTTP (default OpenRouter), or the Claude Code CLI as an
alternate provider (`LLM_PROVIDER=claude-code` →
`app/utils/claude_code_client.py`), or local Ollama (detected by port 11434 in
the base URL, `llm_client.py` `_is_ollama`). Four named model slots in
`app/config.py`:

| Slot | Default | Used for |
|---|---|---|
| `LLM_MODEL_NAME` | `inception/mercury-2:nitro` (`config.py:38`) | general |
| `SMART_MODEL_NAME` | `google/gemini-3-flash-preview` (`:47`) | reports, ontology, market title |
| `NER_MODEL_NAME` | `google/gemini-3-flash-preview` (`:166`) | entity extraction |
| `WONDERWALL_MODEL_NAME` | `deepseek/deepseek-v4-flash:nitro` (`:155`) | the agents themselves |

Plus `WEB_SEARCH_MODEL` (`deepseek/deepseek-v4-flash:online`, `:136`),
`EMBEDDING_MODEL` (`nomic-embed-text` via Ollama, `:57`),
`RERANKER_MODEL` (`BAAI/bge-reranker-v2-m3`, `:70`).

### One call site or many?

**Two.** Orchestrator-side calls all go through `LLMClient.chat` /
`chat_json` (`app/utils/llm_client.py`), instantiated by three factories
(`create_llm_client`, `create_smart_llm_client`, `create_ner_llm_client`).
Agent-side calls go through camel's own model backend, built by
`create_model(config, use_boost)` (`run_parallel_simulation.py:1080`) inside the
subprocess — those do **not** pass through `LLMClient`.

Per-call handling in `LLMClient.chat`: no retry (raises to caller), client-level
`timeout=300.0` default (NER 120 s), `max_tokens=4096 + THINKING_BUDGET_TOKENS`,
optional Anthropic `cache_control` on the first system message when the model is
Claude-family and `LLM_PROMPT_CACHING_ENABLED`, `reasoning: {enabled: false}` by
default (`LLM_DISABLE_REASONING=true`, `:194`), `<think>` block stripping, and
an OpenRouter→Langfuse `trace` block carrying `run_id / simulation_id / caller /
prompt_type / sim_phase / agent_name / agent_id / round`.

Validation is JSON-mode + `json.loads`, with optional `repair_truncated`
salvage in `chat_json`. **No response-schema enforcement anywhere.**

### Is token usage or cost tracked?

**Yes, and this is the most directly reusable asset in the repo.**

Every call emits an `llm_call` event to `events.jsonl` with
`caller, model, temperature, tokens_input, tokens_output, tokens_total,
latency_ms, response_preview, error` (`_emit_llm_event`, `llm_client.py`);
`caller` is auto-derived by walking the stack. Aggregation lives in
`app/utils/run_summary.py`:

- `MODEL_PRICING` — hardcoded $/1M in/out for ~20 models (`:26-52`) plus
  `ONLINE_SEARCH_COST = 0.02` for `:online` suffixes (`:56`);
- `_get_model_cost` — exact match → substring match → **0.0 if unknown** (`:58-78`);
- `_aggregate` — totals plus breakdowns **by model, by caller, and by phase**
  (`phase_map` maps caller prefixes to "NER Extraction", "Profile Generation",
  "Report Generation", "Wonderwall Simulation", …, `:238-250`), with p50/p90/max
  latency and wall-clock span (`:318-338`);
- surfaced as `run_summary.md` on disk, `GET /api/simulation/<id>/cost.json`,
  `GET /api/observability/stats`, and `miroshark-cli cost`.

Granularity is therefore **per call, attributable to a caller function and a
pipeline phase**. `app/services/cost_service.py` wraps it with honesty flags
(`is_estimate`, `pricing_basis`) and lower-bound behavior for unpriced models,
tested offline in `tests/test_unit_cost_service.py`. Gas and revenue: **not
present** (no chain interaction anywhere in the repo).

---

## 8. CONFIG, TYPES, TESTS

### Tunables

- `app/config.py` (311 lines) — one `Config` class, env-driven, with
  `Config.validate()` called before `create_app()`. Covers LLM slots,
  embeddings, reranker, graph search hops/seeds, entity resolution,
  contradiction detection, communities, reasoning trace, chunking
  (`DEFAULT_CHUNK_SIZE=1500`, overlap 100), web enrichment, SearxNG/Firecrawl,
  webhooks, DKG, WaybackClaw, demographics. `.env.example` is 22 KB;
  `docs/CONFIGURATION.md` documents each. Feature flags default **on**.
- Hardcoded constants not exposed via config: `MAX_TOOL_CALLS_PER_SECTION = 6`,
  `MAX_PARALLEL_SECTIONS = 6` (`report_agent.py:1094-1101`), `semaphore=60`
  per platform, `max_iterations = 8` / `min_tool_calls = 2`
  (`report_agent.py:2181-2182`), `MAX_PREVIOUS_TOTAL = 6000`.
- **Drift worth knowing:** `Config.REPORT_AGENT_MAX_TOOL_CALLS`
  (`config.py:197`, default 5) is **never read by any code** — `grep` finds it
  only in `config.py` and in `docs/MCP.md:168`, which claims the report tools
  are "configured via `REPORT_AGENT_MAX_TOOL_CALLS`". The real limit is the
  hardcoded 6.
- Per-run env overrides passed into the subprocess: `MIROSHARK_ROUND_TIMEOUT`,
  `MIROSHARK_LOG_PROMPTS`, `MIROSHARK_SIM_DIR`, `MIROSHARK_LOCALE`,
  `MIROSHARK_RUN_ID`, `MCP_AGENT_TOOLS_ENABLED`, `OLLAMA_NUM_CTX`.

### Shared types module

**Not present as such.** Types are dataclasses colocated with their owner:
`WonderwallAgentProfile` (profile generator), `Report`/`ReportOutline`/
`ReportSection`/`ReportStatus` (report_agent), `SimulationRunState`
(`app/services/simulation_run_state.py`), `AgentActivity` (graph_memory_updater),
`TimeSimulationConfig` (config generator), `RoundRecord` (round_memory),
`BeliefState` (`wonderwall/social_agent/belief_state.py`), `UserInfo`
(wonderwall config). `app/models/` holds only `project.py` and `task.py`.
No pydantic models, no JSON Schema files. The one real contract is
`backend/openapi.yaml`, drift-tested against live routes by
`tests/test_unit_openapi.py`.

### Fixtures / offline mode

- 79 test files; `pytest -m "not integration"` is offline by contract — no live
  Flask, no Neo4j, no LLM (`pytest.ini`, `CLAUDE.md` CI section). CI runs it on
  a thin dependency set (no torch/transformers).
- Markers: `integration` (needs live backend at `$MIROSHARK_API_URL`), `slow`,
  `neo4j`. `tests/conftest.py` (108 lines) skips integration by default and
  provides `api_base_url`, `live_backend`, `sample_simulation_id`.
- Offline tests build their own fixtures inline — e.g.
  `tests/test_unit_cost_service.py:38` `_llm_event(...)` synthesizes
  `llm_call` JSONL rows. There is **no recorded-cassette / mock-LLM harness**
  and **no seeded deterministic mode** for the simulation itself.
- Third CI job: `tests/test_smoke_camel_agent.py` installs real camel-ai + torch
  and exercises the camel↔wonderwall agent loop — the only guard against a
  zero-action simulation.

---

## 9. PORTABILITY VERDICT

| Fund component | Verdict | Evidence | Why |
|---|---|---|---|
| persona definition → **analyst agent** | **ports with changes** | `app/services/wonderwall_profile_generator.py:31` | The dataclass + LLM-brief + provenance-to-source pattern is exactly right, and `risk_tolerance` / `interested_topics` already prefigure a mandate. But it has no scope field, no mandate boundary, and no stable cross-run identity (`user_id` = list index, `:1128`). Replace `bio/karma/follower_count` with `mandate / universe / scope_boundaries`. |
| fan-out mechanism → **analyst runner** | **ports directly** | `wonderwall_profile_generator.py:1172` (setup), `wonderwall/environment/env.py:189-261` (round) | `ThreadPoolExecutor` with pre-allocated positional result slots + per-worker exception→fallback is precisely an analyst runner. The asyncio+semaphore variant gives you concurrency capping for free. Keep the pattern, drop the CSV/JSON platform serializers. |
| output schema + validation → **analyst report contract** | **doesn't apply** | `wonderwall_profile_generator.py:693-697`; no pydantic in `app/` | There is no enforced output schema in the repo. Persona JSON is best-effort with silent field defaulting; agent output is tool-calls with no payload validation. A structured `AnalystReport` with hard validation must be built new. |
| context passing → **frozen-snapshot distribution** | **ports with changes** | `scripts/run_parallel_simulation.py:2619-2621`, `round_memory.py:213` | `memory_ctx = build_context(round)` computed **once** and injected into every active agent is the right shape — one object, built once, fanned out. Two changes needed: (a) it is delivered by mutating each agent's system-message string (`round_memory.py:447`), not passed as an immutable object with an id; (b) it is *supplementary* — the primary input is still each agent's own `refresh()` feed. |
| knowledge graph → **position history + analyst track record** | **doesn't apply** (for positions) / **ports with changes** (for track record) | `app/services/graph_memory_updater.py:51`, `:320`; `wonderwall/simulations/polymarket/schema/trade.sql` | The only graph write path is prose→NER, so numeric position history degrades on ingest. Use the SQLite `trade`/`position`/`portfolio` ledger shape instead — append-only trades plus current positions is already correct. The graph's *bi-temporal* `valid_at`/`invalid_at`/`kind` edge model (`search_service.py:31`) does port well for "what did we believe, and when did we stop believing it". |
| synthesis step → **aggregator** | **doesn't apply** | `app/services/report_agent.py:2465` | MiroShark's synthesis is an LLM prose pass over truncated section text. Your aggregator must be deterministic code turning report weights into proposed weights. The right precedent in this repo is `app/services/signal_service.py` — a documented, pure, tie-broken, reproducible derivation with no LLM in it. Port *that* style, not `_generate_synthesis`. |
| citation layer → **decision record** | **ports with changes** | `report_agent.py:1714` (real quotes), `:828` (prompt-only enforcement), `app/storage/reasoning_trace.py` | Two halves. The evidence retrieval (`actions.jsonl` → `[R{n}] {agent}: "{quote}"`) and the `:ReasoningStep` audit chain both port well. The binding between claim and source does not exist — it's a prompt instruction, and the prompt even asks the model to reword quotes (`:837`). For a decision record you need claim→source_id references validated in code. |
| orchestration loop → **cycle runner** | **ports with changes** | `run_parallel_simulation.py:2332`, `:2589`, `:2744` | The loop body is the right skeleton: build shared context → select participants → fan out with `return_exceptions=True` under a hard timeout → post-round reconcile → append to log → compact. What's missing for a cycle runner: no scheduler at all, no seeded determinism (`random.uniform`/`random.sample` at `:1274-1285`, no `random.seed` anywhere), and round-memory/bridge state doesn't survive a restart. |
| report artifact → **the thing we sell over x402** | **ports directly** | `app/services/signed_result.py`, `app/services/signal_service.py`, `app/api/simulation.py:5629` | `signal.json` → canonical JSON (`sort_keys=True, separators=(",",":")`) → HMAC-SHA256 envelope with `schema_version`, `algorithm`, `signed_at`, `signing_key_hint`, and a graceful `signed=false` when no secret is set. That is a paid-endpoint payload with offline verifiability, already documented and unit-tested. Swap HMAC for a wallet signature and swap the publish gate for x402 payment. |

---

## 10. WHAT'S MISSING

No analogue in this repo; must be built from nothing.

1. **Anything onchain.** No wallet, no RPC, no signing beyond HMAC, no contract
   ABIs, no chain config. `grep -rn x402` across `backend/app`, `docs`,
   `.github` hits two lines, both prose describing a *third party*
   ("Capacity-planning platform … citing the /x402/run surface"). The root
   `.x402books/wallets.json` is unreferenced by any code.
2. **A payment-gated endpoint.** All access control is `MIROSHARK_INTERNAL_KEY`
   or the `is_public` publish gate (`app/__init__.py` `internal_auth_guard`).
   No metering, no per-request payment, no paywall.
3. **A veto / gate / hard rule that blocks an output.** See targeted Q2 — there
   is nothing of this shape anywhere in the pipeline.
4. **Exactly-one-writer enforcement.** The opposite is true today: every agent
   writes to the shared platform DB, and the round loop, monitor thread, and
   graph-memory thread all write concurrently to different stores.
5. **A frozen immutable snapshot with an id.** Context is assembled per round
   and injected by string mutation; nothing is content-addressed, hashed, or
   referable by id. The closest existing primitive is `reproduce.json` +
   its SHA-256 citation hash (`app/services/repro_export.py:416`,
   `archive_service.py:144`) — that's snapshot *hashing* for a whole run, not
   per-cycle input freezing.
6. **A scheduler / unattended cycle trigger.** Not present. Everything is
   request-initiated.
7. **Determinism.** No `random.seed` anywhere in `scripts/` or `app/services/`;
   agent selection, username suffixes, and some `risk_tolerance` fallbacks are
   unseeded `random` calls. Two runs of the same config are not comparable.
8. **Revenue and gas accounting.** Cost tracking covers LLM spend only
   (`run_summary.MODEL_PRICING`). No revenue ledger, no fee accrual, no gas.
9. **Per-analyst attribution across cycles.** No durable agent identity, no
   cross-run store. `/influence` and `agents.json` are per-simulation.
10. **A structured report contract.** No pydantic/JSON-Schema validation of any
    LLM output in the whole tree.
11. **Portfolio P&L against real prices.** The AMM
    (`wonderwall/simulations/polymarket/amm.py`, constant-product) and the
    `market_state` tool compute sandbox P&L from simulated prices. No external
    price feed, no mark-to-market against a real venue.
12. **A trade-execution writer.** `buy_shares`/`sell_shares`
    (`wonderwall/simulations/polymarket/platform.py:122`, `:216`) write to
    SQLite. Useful as a ledger interface shape; not an execution path.

---

## Targeted questions

### 1. Does anything enforce that every worker sees identical input? How divergent can two personas' views get?

**Nothing enforces it, and divergence is unbounded by design.**

Three of the injected blocks are computed once per round and are byte-identical
across agents — `memory_ctx` (`run_parallel_simulation.py:2619`),
`bridge.get_market_prompt()` / `get_sentiment_prompt()` (`:2620-2621`), and the
director/counterfactual text (`:2600-2611`). That's the only "same input" property in
the system, and it is a convention of the loop body, not a check.

Everything else diverges:

- **The feed.** Each agent calls `self.action.refresh()`
  (`agent_environment.py:62`), which routes to the recommender
  (`wonderwall/social_platform/recsys.py`, twhin-bert embeddings for Twitter).
  Two agents in the same round are shown different posts. There is no shared
  "observation of record".
- **Self-initiated queries.** `SEARCH_POSTS`, `SEARCH_USER`, `TREND` are
  ordinary actions, so an agent can widen its own view mid-round.
- **Per-agent context.** Belief state and cross-platform digest are built
  per `agent_id` (`:2627-2641` for Twitter, and the sibling blocks for Reddit/Polymarket).
- **Optional external tools.** A `tools_enabled` persona can call MCP servers
  (`run_parallel_simulation.py:2548-2570`).
- **Setup-time divergence.** Even before the sim runs, each persona was
  generated from its own live graph search (`wonderwall_profile_generator.py:470`)
  and possibly its own web-research call (`:594`) — so the *priors* differ too,
  and nothing records which retrieval each persona got.

Worst case two personas share only the round-memory block and the platform's
current state; their post sets, their prior research, and their tool results can
be disjoint. For the fund's "one frozen snapshot passed by id" rule, this is the
rule that has no support here at all and must be imposed from outside.

### 2. Any concept of a veto, a gate, or a hard rule blocking an output?

**No.** `grep -rni "veto|guardrail|hard rule"` over `backend/app` and
`backend/scripts` returns zero hits for the concept; every `gate` hit is
access control (`is_public` publish gate, `internal_auth_guard`). The four
things that come closest, and why none is a veto:

1. **`ContradictionDetector`** (`app/storage/contradiction_detector.py`, 183
   lines; invoked `neo4j_storage.py:411-421`) — an LLM adjudicates same-endpoint
   edge pairs and returns uuids to invalidate. This *is* an LLM with authority
   to void a prior assertion. But it acts on already-stored edges, not on a
   pending output, and it can't block a report.
2. **Quality diagnostics** (`app/api/simulation.py:4232`) — computes
   participation rate, stance entropy, convergence speed, cross-platform rate
   and emits Excellent/Good/Low plus suggestions. Advisory only; nothing
   consumes it as a gate. It does flow into `signal_service`'s
   `risk_tier`, defaulting to `high-risk` on unknown quality — a
   conservative default, not a block.
3. **Tool-call budget / ReACT floor** (`report_agent.py:2181-2320`) — a section
   is nudged to make ≥2 and at most 6 tool calls. Enforced by prompt messages
   and a loop counter, and a section that ignores it still ships.
4. **The `signed-result.json` publish gate** (`:5629`) — 403 for private sims,
   404 for sims with no rounds, and stricter completed-only posture on some
   surfaces (`docs/FEATURES.md:538`). Access control on a finished artifact,
   not a decision veto.

Nothing anywhere reads all the workers' outputs and refuses to proceed. The risk
agent is a genuinely new component.

### 3. Slowest part of a run, roughly how long, and what timing instrumentation exists?

**Instrumentation: good, per-call, already aggregated.**
`latency_ms` on every `llm_call` event (`llm_client._emit_llm_event`), rolled up
by `run_summary._aggregate` into `total_latency_s`, `latency_p50_ms`,
`latency_p90_ms`, `latency_max_ms`, `wall_clock_start/end`, and per-model /
per-caller / per-phase latency sums (`app/utils/run_summary.py:318-338`), sorted
**by latency descending** for callers and phases (`:337-338`) — i.e. the repo
already ranks its own slow parts at the end of every run. Plus the round loop's
own elapsed print every 5 rounds (`run_parallel_simulation.py:2813-2827`) and a
final `Simulation complete! {elapsed:.0f}s` (`:2836`).

**Structurally slowest: the round loop.** It is `total_rounds` sequential
iterations (default 72 h / 60 min = 72 rounds, `simulation_config_generator.py:592-594`),
each gated on the slowest of up to 3 platforms, each platform gated on the
slowest of its `agents_per_hour` LLM calls at concurrency 60. Rounds cannot
overlap — round N+1's context depends on round N's reconcile step. Secondary
serial costs inside a round: `update_rec_table()` runs synchronous
PyTorch/twhin-bert embedding on the event loop (flagged in the code itself at
`wonderwall/environment/env.py:214-218`), and `twhin-bert-base` is pre-warmed at
setup (`run_parallel_simulation.py:2405-2411`).

**Wall-clock for a full run: not measured anywhere in the repo.** The only
figure is the marketing claim of "10 min · first result" and "$1 per simulation"
(`.github/README.md:17`). The hard ceiling per round is
`MIROSHARK_ROUND_TIMEOUT = 600 s` (`:181`), so a 72-round run's worst case is
12 hours; the advertised 10 minutes implies ~8 s/round in practice.
**[inferred — no committed benchmark, no `run_summary.md` fixture with real
numbers.]**

### 4. What breaks first if this ran hourly, unattended, for a week?

Ranked by how soon it bites (168 runs).

1. **`events.jsonl` grows without bound, and cost aggregation is O(all
   history).** `EventLogger` appends every `llm_call` to a single global
   `events.jsonl` with **no rotation or size cap** (`app/utils/event_logger.py:98-99`
   — the only bounds are an in-memory `Queue(maxsize=10_000)` and a
   `deque(maxlen=2000)` ring). `_collect_llm_events` then reads the **entire**
   global file line by line and filters in Python
   (`app/utils/run_summary.py:106-129`) on every `cost.json` request and every
   end-of-run summary. With hundreds of LLM calls per run × 168 runs, both the
   file and every cost query degrade linearly. This is the first thing to fail.
2. **Neo4j grows monotonically and never prunes.** With
   `enable_graph_memory_update`, every round's agent activity is NER'd into new
   entities and `:RELATION` edges (`graph_memory_updater.py:304`). Invalidation
   sets `invalid_at` but never deletes (`neo4j_storage.py:604`). `delete_graph`
   exists but nothing calls it on a schedule. Vector index size and search
   latency climb run over run.
3. **Nothing triggers the next cycle.** There is no scheduler (§5), so "hourly"
   requires an external cron calling `/prepare` then `/start` then
   `/report/generate` — and `/prepare` is a fire-and-forget thread returning a
   `task_id` you have to poll (`app/api/simulation.py:2000-2020`), as is report
   generation. An unattended driver has to own all the polling and all the
   failure branches itself.
4. **Silent degradation, not failure.** The fallback chains are deep and
   quiet: a bad persona becomes a stub (`wonderwall_profile_generator.py:1148`),
   a failed section becomes `*(Section generation error: …)*`
   (`report_agent.py:2667`), a timed-out round is skipped and logged
   (`run_parallel_simulation.py:2748`), a config-gen failure falls back to
   defaults (`simulation_config_generator.py:589`). Unattended, you get 168
   "successful" runs of steadily worse quality with no alert. `quality.json`
   would catch it but nothing reads it as a gate (targeted Q2).
5. **Unpriced models silently zero the cost line.** `_get_model_cost` returns
   `0.0` for any model absent from the hardcoded `MODEL_PRICING` table
   (`run_summary.py:70-77`). One OpenRouter model rename and the $/run figure
   quietly drops to near-zero while real spend continues. (`cost_service` at
   least flags `is_estimate` / `pricing_basis`.)
6. **Process and disk accumulation.** Each run is a `subprocess.Popen` with
   `start_new_session=True` plus a monitor thread, three sqlite DBs, several
   jsonl logs, `simulation.log`, and a `wonderwall-<timestamp>.log` created at
   *module import* time (`wonderwall/environment/env.py:40-42`, one per
   subprocess). `SimulationRunner._run_states` is a class-level dict that is
   popped only in `cleanup_simulation_logs` (`simulation_runner.py:1284`), not
   on normal completion — the monitor's `finally` clears processes, queues and
   file handles (`:596-611`) but leaves `_run_states` growing. Cleanup helpers
   exist (`cleanup_simulation_logs`, `cleanup_all_simulations`,
   `register_cleanup`) but nothing schedules them.
7. **Resume amnesia compounds.** Any restart loses round memory, the
   market–media bridge, and the cross-platform log (§5). Under an unattended
   loop with occasional timeouts, resumed runs quietly lose their history layer
   while still reporting as complete.
8. **Non-determinism blocks diagnosis.** With no seeding, you cannot replay run
   #57 to find out why it looked wrong.

---

## Notes on method

Read-only. No files created inside the MiroShark tree other than this report
(`research/miroshark.md`). Where the repo's own docs and code disagree —
`docs/MCP.md:168` on `REPORT_AGENT_MAX_TOOL_CALLS`, `docs/ARCHITECTURE.md`'s
"Polymarket sequential → all 3 parallel" table — I cite the code. Claims I could
not verify in code are marked **[inferred]** or **not present**.
