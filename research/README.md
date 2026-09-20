# `research/` — what was read before anything was written

Seven discovery reports and one findings page. All of it was produced **before** the
fund was built, and the plan was rewritten twice because of what it said.

```
   seven repositories read           →   findings.md          →   the plan
   (what other people already did)       (what we measured)       (what we will do)
```

| Report | What it examined | What this project took from it |
|---|---|---|
| `bankr-skills.md` | BankrBot's published skills | the wallet, quote and swap endpoints, and the documented shapes the probes then checked. It is where the tokenized-stock location gate was first read, as documentation |
| `bankr-claude.md` | Bankr's Claude plugins | how an agent is expected to reach the wallet, and the shape of the key permissions |
| `agent-os.md` | AgentOS | the chain's public RPC and explorer, and the practice of pinning addresses rather than trusting a name |
| `openclaude.md` | an existing Bankr integration | the claim that credit balance is not programmatically readable — which probe 0.6 disproved, and the plan was corrected |
| `x402-cli-example.md` | Bankr's x402 example | how a paid endpoint is wired, and that settlement is an on-chain event rather than an HTTP status |
| `miroshark.md` | an existing trading system | a portability audit: which parts of an existing fund could be reused, and which assumptions did not survive contact with this chain |
| `aero-stock-lp.md` | tokenized-stock liquidity | where the stocks actually trade, and why the venue's quote and a pool's depth are different questions |

## `findings.md` — the page the rest of the build trusts

Five thousand lines of what the probes measured, each marked **measured**,
**documented** or **inferred**, with **unresolved** a valid outcome. Nothing in this
repository claims a fact that is not in here with its evidence.

It is written to a stricter standard than the plan it corrects, because several plan
claims turned out to be wrong: tokenized-stock execution is genuinely gated (a real
403, with the body quoted), the credit balance *is* readable, a swap is a sponsored
4337 operation rather than an ordinary transaction, and 6 bps of a sale went unexplained
by the logs — three times now, to the wei.

If a number in this repository surprises you, search `findings.md` for it. Either it is
there with how it was measured, or it should not have been stated.
