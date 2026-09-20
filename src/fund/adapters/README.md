# `adapters/` — everything that comes from outside

An adapter turns one external surface into a value the rest of the fund can use, and
**records what it heard, including a refusal**. It never decides what the answer means.

| File | What it reads |
|---|---|
| `chain_4663.py` | Robinhood Chain over JSON-RPC: balances, Chainlink feeds, the registry, the block. The largest adapter, because the chain has the most ways to be unhelpful |
| `bankr_quote.py` | Bankr's `/wallet/swap-quote` — a price at a size, read-only |
| `bankr_exec.py` | Bankr's `/wallet/swap` — **the only path in this repository that can spend.** Nothing outside `treasurer/` may import it |
| `bankr_llm.py` | the LLM gateway the analysts and the risk agent call |
| `bankr_usage.py` | what those calls cost, read back from the gateway |
| `gecko.py` | GeckoTerminal, an independent second price |
| `http.py` | one transport: timeouts, retries, backoff, and a refusal that stays a refusal |
| `cache.py` | the recorder that makes a capture replayable |
| `fake_venue.py` | a venue for paper cycles, labelled `FAKE VENUE` in every answer it gives |

**What an adapter must never do:** smooth over a bad answer. If a feed is stale, the
staleness is reported and something downstream refuses; the adapter does not substitute
the last good value. A missing answer is `None`, and `None` blocks.

**One send, never a retry.** `bankr_exec.py` sends a swap once. A timeout is an
*unknown* outcome, not a failure, and the fix is to read the chain — never to send
again under a new key.
