1. **A successful swap can disappear from the ledger, and recovery can spend twice.**

   **Plan:** §7 steps 7–8 execute before appending trades; §10 probe 10 repeats an idempotency key; §9 Phase 8 introduces resumability after Phase 5 permits live execution.

   **Classification:** Missing specification. **Impact:** Critical.

   **Failure:** Bankr accepts a swap, but the connection drops or the process dies before the result is committed. The next cycle reads old positions and submits a new order with a new key. Alternatively, a retry receives an in-flight response and is incorrectly treated as a failed order whose reservation can be released. Two concurrent cycles can also spend the same available balance without repeating any individual key.

   **What breaks / who:** Fund holdings, cash limits, subsequent sizing, and published P&L diverge. The operator and every research buyer receive an incorrect account of what happened.

   **Evidence / confidence:** High confidence in the design gap, not a measured failure. Bankr documents duplicate-key replay and an in-flight `409`; it also documents HTTP `200` with `success:false` for a mined revert. A successful HTTP request is therefore insufficient evidence of a fill. Idempotency retention, request-payload binding, key/account scope, and recovery after credential rotation are not established in the supplied plan. [Bankr Swap](https://docs.bankr.bot/wallet-api/swap/)

   **Smallest coherent correction:** Persist an order intent, exact request payload, stable idempotency key, mandate reference, and balance reservation *before* submission. Record durable states for prepared, submitted, unknown, confirmed, and failed, with transaction hashes and receipt evidence where available. A timeout is unknown; a mined revert is failed with an actual transaction and possible expense. Serialize fund execution through one durable owner. On restart, reconcile unresolved intents before accepting another rebalance. Dependent purchases wait for confirmed sale proceeds; partial baskets remain explicitly partial. Define confirmation depth/finality and compensating events for reorganizations. A kill switch stops new submissions, not reconciliation or transactions already broadcast.

   **Fix limitations:** A database transaction cannot atomically commit an external chain trade. Do not promise exactly-once execution merely because there is a SQL transaction or a queue. Same-key retries rely on demonstrated provider semantics. If recovery cannot identify the outcome, keep the wallet reserved and require reconciliation; never generate a replacement key to escape uncertainty. Bankr remains the chain signing/nonce owner; local serialization controls business orders, not its nonce allocator. Robinhood distinguishes sequencer confirmation from Ethereum finality. [Robinhood finality](https://docs.robinhood.com/chain/transaction-finality/)

   **Targeted test:** Kill the runner before send, after acceptance but before response, and after response but before ledger commit. Repeat under two simultaneous runners and during deployment restart. Inject `409`, `200 success:false`, delayed receipts, and a receipt becoming noncanonical. **Pass:** one economic order at most per intent; no dependent overspend; unresolved cases remain unknown; every eventual fill is booked once. **Fail:** a new key is issued for an unresolved order, an HTTP status creates a false fill, or a restart loses reservations.

2. **The claimed single-writer boundary is an import rule, not an enforced authority boundary.**

   **Plan:** §2 invariant 1 promises structural separation; §6 prohibits signing imports; §8 says two Bankr accounts prevent a compromised analyst path from trading. §7 step 1 reads wallet balances without identifying which account owns them.

   **Classification:** Missing specification. **Impact:** Critical.

   **Failure:** Analyst and treasurer entrypoints share an environment or OS identity. Compromised worker code reads the execution key and calls the HTTP API without importing `bankr_exec`. Separately, the read account's authenticated portfolio is mistaken for the execution account's portfolio, so a valid proposal is sized against the wrong wallet.

   **What breaks / who:** Fund spend authority and every risk calculation based on available capital. A recipient allowlist does not itself enforce approved assets or position limits.

   **Evidence / confidence:** High. The plan specifies modules and credential names, but no process, secret, filesystem, or caller-authentication isolation. Bankr keys are account credentials with independent permissions; the Wallet API reads the authenticated wallet, and swap proceeds return to that wallet. The endpoint-specific documentation explicitly says the recipient allowlist is not enforced on `/wallet/swap`. [Bankr API keys](https://docs.bankr.bot/security/developer-api/), [Wallet API access control](https://docs.bankr.bot/wallet-api/overview/)

   **Smallest coherent correction:** Keep the two accounts if desired, but name the fund execution wallet explicitly in every snapshot and order. Read that address through RPC or a proven read-only credential for that same account; never assume a separate account's `/wallet/portfolio` refers to it. Run analysts without access to execution or envelope-signing secrets. Put the treasurer behind an authenticated, narrow interface that accepts structured approved intents and independently checks asset, amount, recipient, mandate, and current-state constraints. Only that service can sign envelopes or authorize Bankr writes. Disable unused write-capable Bankr surfaces and define the human administrator who can change keys, limits, mandates, and the kill switch.

   **Fix limitations:** Separate containers with the same mounted secrets do not fix this. An authenticated caller can still send a malicious intent, so the treasurer must validate it. RPC balances identify assets but do not replace reservations for in-flight orders. The Bankr account owner remains an administrative authority; “one writer” must mean one automated execution authority, with manual activity either prohibited operationally or reconciled explicitly.

   **Targeted test:** From the actual deployed analyst environment, attempt to read execution credentials and submit an HTTP swap without using the prohibited module. Give the read account and execution account deliberately different balances. **Pass:** the worker lacks spend capability, unauthorized treasurer calls fail, and sizing uses the declared execution wallet plus its reservations. An import-graph test alone is not a pass.

3. **Risk approves weights before the information needed to approve execution exists.**

   **Plan:** §7 step 5 evaluates risk; step 7 subsequently determines ordered trades and live quote sizes. §11 expects liquidity, turnover, cash-floor, and quote/feed divergence gates. §4 describes stock execution as RFQ; §5 calls pool spot the execution-sizing input; §6 filters by depth without defining its source.

   **Classification:** Missing specification. **Impact:** High.

   **Failure:** A small snapshot quote supports a stock, but the eventual position requires a much larger order. Risk approves the weights; actual depth, fees, or a re-quote make the trade unacceptable. A failed sale then leaves insufficient cash for later buys. Alternatively, an AMM-liquidity filter excludes every RFQ-tradeable stock.

   **What breaks / who:** The fund either trades outside the risk approval or never trades despite apparently healthy data. Signed approvals do not describe the execution they purport to authorize.

   **Evidence / confidence:** High for the missing handoff. No sized order or execution evidence is an input to the listed risk stage. Bankr documents that stale or unsuitable quote IDs can fall back to fresh pricing and that `swapImpactBps` can be unknown with server-side fail-open behavior. Platform impact protection cannot substitute for the fund's explicit unknown policy. [Bankr Swap](https://docs.bankr.bot/wallet-api/swap/)

   The blanket statement that stocks have no AMM pool should also be narrowed: Robinhood documents RFQ, AMM, and propAMM venues. This establishes supported venue types, not measured liquidity for any selected asset. [Robinhood trading venues](https://docs.robinhood.com/chain/building-with-stock-tokens/)

   **Smallest coherent correction:** After deterministic aggregation, create a read-only candidate trade plan using the execution wallet's reconciled holdings and reservations. Include sized, directional quotes, explicit units, fees, quote age, minimum proceeds, and projected post-trade holdings. Risk still reads every full report and can veto. Before every submission, the treasurer reruns the same deterministic gates against fresh evidence and checks actual proceeds from prior trades. Use executable quotes at intended sizes for the selected RFQ route; preserve the liquidity requirement by defining it operationally, not by inventing AMM reserves. Required checks must be explicitly true; unknown blocks execution.

   **Fix limitations:** A preflight quote does not lock a provider's eventual quote. Enforce the approved economic floor through `minBuyAmount`, cap the sell amount, and prove these survive server-side re-pricing. A buy quote alone does not prove exit capacity. Do not call quote/feed divergence “market impact” unless its definition actually measures that quantity. This correction retains all analysts and the risk veto; it adds execution validation, not another autonomous decision-maker.

   **Targeted test:** A quote at small size passes, but the intended-size quote fails; a quote expires; impact is unknown; a sale reverts; fees consume the cash floor. **Pass:** each case prevents the disallowed submission, no buy spends unconfirmed proceeds, and an acceptable refreshed plan still executes. **Fail:** approval of old weights is enough to authorize any newly sized order.

4. **The Python runner, durable state, hosted paid handler, and public page are not connected by a deployment design.**

   **Plan:** §6 uses Python modules, disk cache, SQL ledger, and an unspecified report store; §4 says the x402 handler serves the latest cached record while cycles run separately; §9 Phase 7 deploys the surfaces and Phase 8 schedules the runner.

   **Classification:** Missing specification. **Impact:** High.

   **Failure:** The runner writes a signed record to local disk. The hosted handler cannot read it, or serves a file bundled at deployment forever. A restart loses state, two scheduler instances overlap, or new egress IPs fail the execution key's allowlist.

   **What breaks / who:** Paid buyers receive unavailable/stale data; the operator cannot recover the fund after deployment. A successful local cycle and a trivial hosted handler can both pass while the product remains disconnected.

   **Evidence / confidence:** High. The actual runner host, paid hosting tier, database engine, storage owner, publication protocol, and public-page host are **not specified**. Bankr documents TypeScript handlers and server-side bundling, a 1 MB handler-source cap, a 30-second execution ceiling, 256 MB memory, and ephemeral `/tmp`. These are documented limits, not deployed measurements. [x402 deployment](https://docs.bankr.bot/x402-cloud/cli-reference/), [x402 runtime isolation](https://docs.bankr.bot/x402-cloud/security/)

   Do not overcorrect this into “Bankr has no persistence”: its current overview describes opt-in `ctx.files` and `ctx.appKV`. Those capabilities do not establish how an external Python process writes the same record, their atomicity, or their suitability for a trading ledger. [x402 handler context](https://docs.bankr.bot/x402-cloud/overview/)

   **Smallest coherent correction:** Specify one Python execution host, one authoritative durable database, and one publication interface. A coherent minimal arrangement is an isolated Python runner/treasurer with persistent SQL state, plus a small TypeScript x402 handler that fetches immutable published records over authenticated HTTPS; the public page reads the same published version. Commit record bytes and their manifest before atomically advancing a latest pointer. Store and serve explicit freshness, cycle, and execution-status fields. Keep trading and inference outside the paid request lifecycle, as already intended.

   **Fix limitations:** This introduces a real host/database/publication dependency; it is not “just a cache.” The plan must choose and verify their actual tier, persistence, locking, backup/recovery, and network behavior. Reusing Bankr's persistent capabilities is an alternative only after proving the required external-write and consistency contracts. Do not import generic AWS, Vercel, or Cloudflare limits into an unnamed runtime. Do not assume Python dependencies or native modules run in the TypeScript handler.

   **Targeted test:** Deploy the actual packages. Run a live-shaped cycle, restart the runner, cold-start the paid handler, publish while reads are concurrent, and roll the deployment. **Pass:** the handler and page return the same complete committed record/hash; state and reservations survive; no duplicate scheduler execution occurs; execution originates from an allowed IP; the maximum supported record is returned within the platform ceiling. A `hello world` payment round trip does not pass this test.

5. **The specified trade ledger cannot produce the promised reconciled financial statements.**

   **Plan:** §7 step 8 derives positions from trades; step 9 computes revenue, cost, P&L, and attribution. §1 includes x402 revenue and LLM cost. §6 names an append-only trade schema but no accounting-event schema. The opening description promises audited books.

   **Classification:** Missing specification. **Impact:** High.

   **Failure:** The fund is initially funded in USDG, receives research revenue in Base USDC, buys prepaid LLM credits, incurs inference cost, and receives an external token transfer. Every swap is booked correctly, but the statement omits assets, counts funding as profit, double-counts top-ups and consumption, or reports sales that never settled.

   **What breaks / who:** The accountability product can produce arithmetically consistent but economically false statements. Fund owners and research customers cannot reconcile the report to assets or provider charges.

   **Evidence / confidence:** High, based on the listed data flow and schema responsibilities. Generic “event logs” appear in §11, but their producers, event types, completeness, and reconciliation contract are not defined. Bankr's paid handler returns before settlement is finalized, so a handler invocation is not a revenue receipt. [x402 settlement behavior](https://docs.bankr.bot/x402-cloud/security/)

   **Smallest coherent correction:** Define the reporting entity and all in-scope wallets/accounts. Extend the append-only store to cover opening balances, contributions/withdrawals, transfers, actual fills, fees/gas, payment settlements/refunds, prepaid credits, usage expense, and valuation adjustments. For chain events, persist chain ID, contract, transaction hash, log index, block hash, raw integer amount, decimals, and event time. Keep observed/ingested time separately. For providers, preserve request/settlement identifiers and pagination checkpoints. Reconcile against independent wallet balances and provider evidence at the reporting cutoff. Choose an explicit cost-basis policy. Base revenue can remain on Base; no bridge is required merely to include it in consolidated USD books.

   Retain Chainlink marking, but distinguish that accounting mark from realizable sale proceeds. Use raw token units times the per-token feed; do not apply the multiplier again or also book the same reinvested dividend as a separate cash receipt. Robinhood confirms that its feed incorporates the multiplier. [Robinhood price semantics](https://docs.robinhood.com/chain/oracles-and-price-feeds/)

   **Fix limitations:** A journal does not establish completeness. It needs independently sourced balance/settlement checks and explicit treatment of unresolved items. A signature proves record provenance, not the correctness of the books. Define what “audited” requires, who verifies which assertions, and where the evidence is published; an internal reconciliation cannot silently fulfill an unspecified independent assurance promise.

   **Targeted test:** A known-answer accounting fixture includes opening capital, partial sales, an external transfer, a reverted transaction expense, settled and unsettled x402 payments, refund, LLM credit purchase and consumption, plus a corporate-action multiplier change. **Pass:** every asset balance reconciles, contributions do not become income, expense is recognized once, and net-asset movement reconciles to capital flows and net income within declared rounding. **Fail:** reconciliation only compares two calculations derived from the same incomplete trade table.

Review basis: I read the supplied PLAN.md in full. The seven discovery reports and their probe outputs were not attached or located in the available files. Repository names are not sufficient to identify reviewed commits. I verified material platform claims against current official documentation on 17 September 2026; I did not run authenticated API calls, deploy a service, or submit a transaction. Findings distinguish documented behavior from design inference. No proposed fix below is claimed as production-tested. Product requirements retained: Robinhood Chain fund, frozen shared snapshot, read-only analysts, deterministic aggregation, full-report risk veto, sole automated treasurer, signed paid research, public page, and financial accountability. Timeline and team size are not assessed.

Additional findings follow.

6. **A frozen object can preserve an inconsistent market state perfectly.**

   **Plan / classification:** §2 invariant 2; §7 steps 1–2; §11 snapshot tests. **Missing specification.**

   **Failure / affected:** Balances and feeds come from different blocks; a recently fetched HTTP response contains old source data; a weekend or corporate-action pause is treated as a fresh usable price or causes a held asset to disappear from the book. Risk and valuation agree on the same incorrect snapshot.

   **Evidence / confidence:** High. Code-generated retrieval timestamps are specified, but source timestamps, block alignment, maximum cross-source skew, and held-but-untradeable assets are not. Chainlink documents off-hours prices that remain callable without off-hours heartbeats and paused oracles retaining their last value. [Chainlink Robinhood feed behavior](https://docs.chain.link/data-feeds/tokenized-equity-feeds/robinhood)

   **Correction:** Pin chain reads to an identified block/hash with a declared finality policy; record source time and fetch time separately for offchain observations. Preserve raw observations and normalized units. Define per-feed session/age/pause rules. An asset removed from the buy universe remains a holding with an explicit valuation/execution status. If briefs need trends or fundamentals, specify and freeze those historical inputs too; the currently listed point-in-time prices do not supply them. Public RPC failover does not prove archival access: Robinhood recommends production providers and archive endpoints for historical reads. [Robinhood RPC documentation](https://docs.robinhood.com/chain/connecting/)

   **Fix check:** Do not casually add a Robinhood Chainlink sequencer-uptime feed as if its address were known. Robinhood recommends one, but Chainlink's supported-network list does not list Robinhood and says expansion has stopped. That dependency remains unverified. Require demonstrated chain-progress/freshness evidence and halt on uncertainty; acknowledge that this is not an equivalent sequencer attestation. [Chainlink sequencer support](https://docs.chain.link/data-feeds/l2-sequencer-feeds)

   **Test:** Mix two blocks, replay an old HTTP body with a new fetch timestamp, simulate a paused oracle and market closure, then exclude a held asset from trading. **Pass:** bad trading evidence blocks execution; holdings remain; stale/last-valid marks are labeled; historical replay uses saved evidence without silently substituting current data.

7. **A beacon-slot match is not issuer authentication.**

   **Plan / classification:** §3 AgentOS impersonator check; §10 probe 5 compares one good token and fake GME. **Unverified dependency.**

   **Failure / affected:** A counterfeit mimics the expected proxy layout or points to the same beacon and passes the heuristic. The fund buys the wrong instrument despite an apparently verified token.

   **Evidence / confidence:** High that the proposed positive/negative pair cannot establish authenticity; the exact imported check is unavailable. ERC-1967 specifies storage locations, not issuer authorization. Robinhood identifies canonical stock tokens by deployment address. [ERC-1967](https://eips.ethereum.org/EIPS/eip-1967), [Robinhood canonical contracts](https://docs.robinhood.com/chain/contracts/)

   **Correction:** Pin a versioned issuer-derived allowlist keyed by `(chain_id, token_address)` and its corresponding feed. Use beacon/implementation checks only as extra consistency checks. Require explicit approval for registry/address changes. Validate asset identity at the structured-report boundary as well: §11 currently mentions ticker scope, which is weaker than §2's address invariant.

   **Fix check:** An address hash proves which address was pinned, not that it was canonical. Record provenance. The official assets API exposes per-chain deployments, but any reliance on it must preserve a reviewed snapshot and handle unavailable/inactive metadata. [Robinhood assets API](https://docs.robinhood.com/chain/stock-token-apis/)

   **Test:** Present an unlisted clone with matching ticker and beacon, a correct token on the wrong chain, and an address-update proposal. **Pass:** none enters the approved universe without explicit canonical identity and version acceptance.

8. **The aggregation contract has no defined result for the most important abstention cases.**

   **Plan / classification:** §2 invariant 5; §7 steps 3–4; §11 excludes `NO_CALL`, requires weights summing to one, and discloses missing analysts. **Missing specification.**

   **Failure / affected:** Every analyst abstains or fails. Normalization divides by zero, retains an old buy recommendation, or liquidates holdings by interpreting no opinion as zero target exposure. A missing bearish analyst can turn a mixed view into a buy even if a partial-failure flag is displayed.

   **Evidence / confidence:** High. The scoring equation, confidence calibration, quorum, distinction between abstain/failure/hold/sell, cash representation, and rounding residual policy are not specified.

   **Correction:** Define a total function from validated structured reports to either a proposal or a recorded no-rebalance decision. Specify asset identity, confidence scale, opinion horizon, quorum, caps, cash weight, and tie-breaking. The all-abstain or insufficient-quorum outcome should perform no rebalance while still producing reports and books. Disclosure is not permission to execute a materially incomplete proposal.

   **Fix check:** No-rebalance means preserve actual holdings; it must not silently mean convert to cash. Keep collection, reconciliation, and reporting running on a no-trade cycle.

   **Test:** All abstain, all fail, one dissenting worker fails, duplicate reports arrive, and weights require rounding. **Pass:** a documented deterministic result, valid cash treatment, no unintended liquidation, and no duplicate analyst contribution.

9. **“All full reports reach risk” and seeded inference are not executable contracts yet.**

   **Plan / classification:** §2 invariants 3 and 6; §3 ThreadPoolExecutor pattern; §9 Phase 2 and Phase 3 exits. **Missing specification.**

   **Failure / affected:** Maximum reports exceed the risk model context window; a provider/client truncates them; one stuck worker prevents fan-in; or a fallback model changes the verdict while the record implies reproducibility. The fund's risk checkpoint is bypassed or never completes.

   **Evidence / confidence:** High for absent bounds; model-specific support is unverified. Fan-out width bounds concurrency, not report size or call duration. A seed does not itself demonstrate deterministic behavior across selected models or gateway routing. The Phase 3 replay claim also omits freezing the stochastic risk result.

   **Correction:** Pin model IDs and record effective model/provider where exposed, prompts, schema/config versions, parameters, responses, and usage. Define per-worker deadlines, retry budget, output-token limits, and a context budget covering every full accepted report plus the proposal and risk output. Have the runner load the immutable snapshot into the prompt; passing only an ID to a tool-less model is not data delivery. Preserve every accepted full report. If the full bundle cannot fit, veto rather than silently summarize it. Deterministic replay begins from recorded model outputs, including risk; fresh inference is a separate experiment. Canonical serialization must also use saved times and stable numeric encodings.

   **Fix check:** Cancelling a Python future does not guarantee termination of an in-flight network call. Enforce transport deadlines and bound the fan-in deadline; late workers cannot alter a sealed cycle. This preserves the full-report requirement rather than replacing it with summaries.

   **Test:** Maximum-size reports, one hung call, late completion, fallback routing, and adversarial report text. **Pass:** the submitted risk input demonstrably contains every accepted report; fixed gates cannot be overridden by text; the cycle terminates predictably; replay of recorded evidence is byte-stable.

10. **Mandate approval, decision signing, and execution signing are conflated.**

   **Plan / classification:** §3 approves a plan hash once for unattended replay; §7 signs weights before the trade list exists; §11 refuses a plan whose hash differs from approval; §3 also borrows graceful `signed=false`. **Missing specification.**

   **Failure / affected:** Fresh sizing changes the plan hash, forcing every cycle to fail; or code compares only a loose policy hash and reuses approval indefinitely. A mutable report ID can point to altered text while the decision signature remains valid. An unsigned fallback can reach live execution or the paid signed-record endpoint.

   **Evidence / confidence:** High. The signed preimage, human approver identity, expiration/revocation, public verification key, report-ID immutability, and binding to the exact execution are not specified.

   **Correction:** Use two explicit objects: a human-authorized mandate containing bounds, wallet, chain, allowed assets, cumulative budget, version, expiry, and revocation state; and a per-cycle execution intent containing exact ordered orders and a fresh mandate validation. If exact-plan approval is intended instead, changing its hash requires approval. Route all system signatures through the sole treasurer authority. Sign content hashes of full reports, snapshot, policy/config, verdict, and proposed intent. Append a separately signed execution outcome linked to the decision; do not rewrite a pre-trade decision to imply it proves fills. Define an asymmetric public-verification format and key-rotation trust path. `signed=false` can be a visible diagnostic, never a signed-product or live-authorization success.

   **Fix check:** A public verification key and a content hash do not prevent replay by themselves; the executor must enforce cycle uniqueness, mandate validity, and cumulative use in durable state. A single writer still needs concurrency control.

   **Test:** Replay approval across cycles/environments, change one report byte, rotate keys, revoke a mandate between planning and submit, and force signer failure. **Pass:** unauthorized execution is refused; historical signatures remain verifiable under the declared trust policy; published results distinguish proposed from executed.

11. **The paid request has no durable purchase-to-delivery-to-settlement mapping.**

   **Plan / classification:** §4 serves the latest cached decision; §7 steps 9–10; §10 probes 6–7 capture payer and successful payment. **Missing specification.**

   **Failure / affected:** The client receives a challenge for one latest record, a new cycle publishes before retry, and it buys another. Or payment settles but the response is lost, prompting another charge. Recording revenue inside the handler can also precede settlement failure. Research buyers and the books disagree about what was purchased.

   **Evidence / confidence:** High for the absent contract; actual replay/refund behavior is unverified. Bankr supplies payment verification and a payer header, but its public documentation does not establish the application's required purchase recovery semantics. [x402 payment security](https://docs.bankr.bot/x402-cloud/security/)

   **Correction:** Resolve latest to an immutable decision ID before purchase. Bind request/purchase, decision ID, payer, price/asset/network, delivery status, and settlement reference. Define recovery of a paid-but-undelivered record and refund authority if recovery is impossible. Validate payer identity only through the platform's authenticated path; test spoofed headers and any direct-origin route. Ingest settled receipts into books separately from handler logs. Keep HTTP payment responses from being shared as unauthenticated cached responses.

   **Fix check:** An application request ID alone cannot stop a payment middleware from charging again; prove provider replay behavior or add a narrow receipt-verified retrieval path. A refund is a new spend and must pass the treasurer. The public page is an explicit requirement: showing the same research there is intentional, so this system sells API delivery rather than exclusive information. Do not “fix” that by removing the public page or claiming the content cannot be scraped.

   **Test:** Drop the response after settlement, replay the same payment, change latest between challenge and retry, spoof the payer header, and fetch via a shared cache. **Pass:** the buyer gets the identified record under the declared charging/recovery policy; no forged payer is trusted; revenue equals reconciled settlements; no accidental extra charge is hidden.

12. **Live access is acknowledged but has no satisfactory phase exit criterion.**

   **Plan / classification:** §4 location gate; §10 execution probe; §12 asks whether an eligible operator exists; Phase 0 exits when every probe has a recorded answer. **Unverified dependency.**

   **Failure / affected:** A documented `403` counts as a completed probe and work proceeds although the required live stock fund cannot trade. Or access works once and expires during unattended operation, preventing exits as well as new positions.

   **Evidence / confidence:** High that the dependency is unresolved; the team's eligibility is unknown. Bankr documents excluded regions and verification expiration after 30 days. A successful quote does not establish execution eligibility. [Bankr location verification](https://docs.bankr.bot/features/trading/tokenized-stocks/)

   **Correction:** Make Phase 0 distinguish pass, fail, and unresolved against capability-specific acceptance criteria. Require a legitimately eligible execution account and a demonstrated small buy-and-sell round trip with the intended permissions. Define access-renewal ownership and paused-operation behavior when it expires. Preserve the Robinhood Chain requirement; a paper demo, a different asset, or relocating a server does not prove it is met.

   **Fix check:** One operator's verification does not prove another account is enabled. Run the probe using the actual execution identity. Surface unknown `403` messages without guessing that every authorization failure has the same remedy.

   **Test:** Use production-shaped permissions, then deliberately revoke/expire authorization. **Pass:** valid account executes both directions; loss of access pauses new attempts, preserves existing holdings and pending orders, and exposes the exact remediation state.

13. **The LLM accounting premise is contradicted by current documentation, and the quota model targets the wrong surface.**

   **Plan / classification:** §4 says credit balance is not programmatically readable and relates Agent API message quotas to fan-out; §8 disables Agent API for the read key and uses `llm.bankr.bot`. **Confirmed contradiction** for credits; **missing specification** for per-surface quotas.

   **Failure / affected:** The runner estimates costs while ignoring available provider reconciliation; fan-out consumes reserved credit and fails mid-cycle; the system throttles around an unrelated Agent API daily quota while exceeding actual wallet/RPC/gateway limits.

   **Evidence / confidence:** High documentation confidence, not measured account access. Current Bankr documentation includes `GET /v1/credits` with effective balance and in-flight usage, and `GET /v1/usage` with token/cost aggregates. [LLM API reference](https://docs.bankr.bot/llm-gateway/api-reference/). The Agent API daily quota applies to `/agent/prompt`; separate general API rate limits exist. [Bankr rate limits](https://docs.bankr.bot/security/developer-api/)

   **Correction:** Probe those endpoints with the intended LLM key. Keep per-call estimates and honesty flags, but reconcile them to available provider totals rather than treating estimates as the only possible evidence. Budget for risk, malformed-output retries, cache token categories, and failed/unknown calls. Maintain rate and concurrency budgets by service, key, and egress IP. A limit probe on one cheap endpoint does not establish another endpoint's behavior. Fail closed on insufficient inference capacity; auto top-up, if enabled, is an additional spend authority that must remain under the mandate.

   **Fix check:** Aggregated usage is not necessarily enough to attribute every cost to a specific analyst; retain request-level evidence and expose unreconciled differences. Credit top-up is not the same event as consumption. An upstream timeout can leave usage cost unknown.

   **Test:** Reconcile a complete cycle containing retries, risk inference, and a dropped response against provider usage; constrain available credit under concurrent calls. **Pass:** no unbounded spend, all estimates are labeled, and differences are retained rather than silently overwritten.

14. **Per-analyst profit attribution has no defined economic meaning.**

   **Plan / classification:** §1 promises which analyst's calls made or lost money; §3 borrows `valid_at`/`invalid_at`; §7 step 9 publishes attribution. **Missing specification.**

   **Failure / affected:** Two analysts recommend the same stock, the aggregator buys one position, and both receive credit for all gains. A vetoed recommendation is reported as earned P&L, or a later revised report replaces the original call before scoring. Users receive a persuasive but false track record.

   **Evidence / confidence:** High. No attribution equation, allocation rule, benchmark, horizon, cost allocation, or counterfactual policy is specified. Two validity timestamps alone also do not record when the system learned a revision.

   **Correction:** Define funded contribution separately from recommendation performance. Persist immutable report versions, effective time and recorded time, aggregation contributions, executed allocations, horizon, benchmark, and cost rules. Allocate actual strategy results once, with an explicit residual for cash, fees, and unassigned effects. Score vetoed/unexecuted calls only as labeled hypothetical results using a specified fill model; never mix them into fund profit.

   **Fix check:** Allocating realized profit is an accounting convention, not proof an analyst caused it. A counterfactual replay introduces assumptions and must not masquerade as an observed trade.

   **Test:** Overlapping recommendations, disagreement, a veto, partial fills, changing weights, and a late report revision. **Pass:** allocated actual P&L plus the residual equals strategy P&L; no gain is counted twice; published historical scores cannot be rewritten by later information.

The end-to-end contract needs the following ownership decisions. These are the concrete missing handoffs behind the findings, not additional feature requests.

| Handoff | Input → output | Identity and units | Authorization | Persistence and source of truth |
|---|---|---|---|---|
| Operator → fund | Funding, configuration, mandate → usable capital and authority | Execution wallet; chain; raw token units; USD limits | Named human approver/admin; bounded treasurer | Mandate/revocation history plus opening-balance evidence; currently unspecified |
| Adapters → snapshot | Chain/RFQ/provider observations → immutable evidence bundle | Chain/address/feed; block/hash; source/fetch times; raw/decimal units | Read-only capabilities | Raw source evidence and normalized snapshot; cache is not the authority |
| Snapshot → analysts | Actual snapshot bytes plus versioned briefs → structured reports | Snapshot hash; analyst/model/version; address-scoped outputs | No trading tools or execution secrets | Runner-owned immutable report store; owner/location currently unspecified |
| Reports → aggregate | Validated structured opinions → weights or no-rebalance | Unique reports; confidence/horizon; cash and asset weights | Deterministic code | Proposal plus config and aggregation provenance; equation unspecified |
| Proposal → risk | Sized candidate trades and all reports → veto/approval | Quote size/age; economic floor; post-trade balances | Fixed gates cannot be overridden by model text | Complete risk inputs/output and gate evidence; exact trade input currently absent |
| Approval → treasurer | Approved intent and mandate → reserved durable orders | Intent/cycle/order IDs; exact payload; stable idempotency key | Sole spend authority; fresh deterministic checks | Authoritative SQL state before external submission |
| Bankr/chain → ledger | Submission outcomes and receipts → reconciled fills/failures | Chain/hash/log/block; raw amounts; confirmation status | Read/reconcile; treasurer owns submission | Receipts and durable order state; HTTP success is insufficient |
| Payment/provider → books | Settlements, refunds, credits, usage → accounting events | Base asset/payee/payer; provider account/request; USD pricing basis | Verified settlements; refund/top-up writes only via treasurer | Complete journal plus independent account reconciliation; adapters missing |
| Ledger → books | Events and closing marks → statements/attribution | Entity, period cutoff, valuation basis, precision, policy version | Pure computation over sealed inputs | Versioned statements, exceptions, and audit evidence |
| Publisher → surfaces → buyer | Committed immutable record → public view/paid delivery | Decision/content ID; purchase ID; signature/key ID; price/network | Publisher writes; surfaces read; payment verifier authenticates buyer | Atomic publication manifest and settlement/delivery reconciliation; handoff unspecified |

The runtime assessment cannot be reduced to the 30-second handler limit.

| Runtime concern | Verified documentation / plan status | Required evidence before relying on it |
|---|---|---|
| Hosting tier and processes | Runner, scheduler, database, and public-page host/tier not specified | Named deployments, actual plan entitlements, persistence and restart model |
| Dependencies and package limits | TypeScript source is bundled by Bankr; 1 MB source cap documented; Python/runtime versions and dependency lockfiles absent | Deploy actual locked packages; distinguish source-size limits from installed/deployed bundle limits |
| Duration and memory | x402: 30 seconds and 256 MB documented | Measure cold/warm maximum-record fetch and signature verification; enforce upstream timeout below handler ceiling |
| Concurrency and connections | Worker width bounded in principle; scheduler overlap, endpoint concurrency and DB pooling unspecified | Concurrent-cycle fencing and bounded connections under the chosen tier; no assumed provider concurrency guarantees |
| Streaming, buffering and payloads | Paid output is a cached record; streaming is not required by this product; payload/buffering limits not established | Explicit maximum record size and actual deployed response test; no inference that gateway SSE implies x402 streaming |
| Background work and termination | Separate cycle schedule is sound; schedule host, frequency guarantees, retries and shutdown behavior unspecified | No work depends on a returned HTTP invocation staying alive; restart reconciles orders and resumes publication safely |
| Filesystem, binaries and sockets | x402 `/tmp` is ephemeral; opt-in persistent capabilities are documented separately | Demonstrate external publication/storage access; verify native dependencies or socket requirements only where actually used |
| Secrets, network and environments | Credential names exist; process isolation, static egress and dev/live separation absent | Worker capability test, allowlisted deployed egress, fail-fast chain/wallet assertions, separate fixture/live data and credentials |

Documentation-supported portions should be retained: mainnet chain ID 4663; the per-token Chainlink multiplier treatment; separate scheduled computation and cached serving; deterministic aggregation; explicit abstention; estimated-cost labeling; and the intended single automated treasurer. Those are coherent choices. The failure is in their unimplemented contracts, not the number of agents. [Robinhood network configuration](https://docs.robinhood.com/chain/connecting/), [Robinhood oracle semantics](https://docs.robinhood.com/chain/oracles-and-price-feeds/)

Repository boundaries are mostly reasonable: pure `core/`, external adapters, and deterministic books need not form a cycle. Keep live reads and storage orchestration out of `core/snapshot.py`; it can merge/hash already-fetched values. However, the report store, fund-wallet observer, payment settlement ingestion, LLM billing reconciliation, publication store, and execution-state owner have no defined implementation. Put deterministic gate logic in one shared location and call it from risk and treasurer; do not maintain two interpretations of the same limits. Model imports are not the same as deployed privileges.

The existing tests prove local properties, not the highest-risk integration seams. Keep them, but correct their claims: two immediate same-key submissions do not prove crash recovery; one known counterfeit does not prove issuer identity; comparing an oracle against GeckoTerminal does not establish multiplier semantics; a one-call LLM latency test does not bound a full risk prompt; and paper/live interface equality does not reproduce re-quotes, eligibility, receipts, or finality. Live probes must capture redacted request/response bodies, timestamps, identities, deployment/package versions, and pass/fail criteria. Mark all results as measured, documented, or inferred. A recorded failure is evidence, not a capability pass.

**Single most likely operational failure:** after live access is established, a swap succeeds but its outcome is not durably recorded; the next cycle sizes from stale holdings and retries or rebalances incorrectly. This is a medium-confidence engineering prediction, not a measured incident. It needs only an ordinary timeout or restart, and the current tests would not catch it. The earlier binary blocker is execution eligibility, which the plan correctly recognizes but has not resolved.
