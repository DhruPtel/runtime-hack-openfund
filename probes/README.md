# `probes/` — throwaway scripts that measured what the docs got wrong

Twenty-two scripts, written in Phase 0, before any of the fund existed. **Nothing under
`src/` imports anything here.** Each one asked a single question of a live system and
wrote the answer into [`research/findings.md`](../research/findings.md), marked
**measured**, **documented** or **inferred**, with bodies redacted and a timestamp.

They exist because the documentation was wrong about things that would have cost money.

## Three examples of what they found

**The stock path is genuinely closed.** `execute.py` sent one real AAPL order and got
back `403` with the body *"Tokenized stocks (AAPL) are not available in your region"* —
before broadcast, no gas. Documentation had said tokenized-stock trading required
location verification; the probe turned that into evidence, and the whole fund was
rescoped around it: equity orders are sized, quoted and gated for real, and filled on
paper.

**A swap is not an ordinary transaction.** `idempotency.py` spent $0.08 to find out
what a real swap looks like on 4663, and it is a gas-sponsored **ERC-4337 UserOperation
inside a bundler's transaction**. Its first verdict was *wrong* — it checked `tx.from`
against the wallet and the wallet's nonce, and both said "not ours" about a swap that
plainly moved the fund's money. Everything downstream reads the EntryPoint event
instead. The same probe measured that a repeat under the same idempotency key returns
the original result and does not broadcast twice.

**The balance is readable after all.** `credits.py` checked a claim inherited from an
earlier project — that credit balance could not be read programmatically, so all cost
figures must be estimates. It could be read. The plan was corrected. The cost line is
still labelled an estimate, but now for the real reason: the provider attributes spend
per key and day, not per request.

Also here: `keymap.py`, which measures what each API key can actually do rather than
trusting its toggles, and is worth running before any live call; and the `x402_*`
probes, which established that revenue must be booked from an on-chain `PaymentSettled`
event and never from a handler returning 200.

**`probes/out/` is not committed.** The probe outputs stayed local; what they measured
lives in `findings.md`, and the two recordings the tests depend on were copied into
`tests/data/`.
