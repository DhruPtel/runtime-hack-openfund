# `agents/` — the thinking

Five model calls, each in its own process, none able to spend.

| File | What it is |
|---|---|
| `runner.py` | starts the four analyst seats in parallel, each with its own credential, and collects what comes back |
| `analyst.py` | one seat: build the brief, make one call, validate the reply, retry once if it was malformed |
| `risk.py` | the risk agent: reads every report **in full** plus the sized plan, votes per order and overall |
| `schema.py` | the validator. A report is refused unless every figure it cites is in the snapshot |
| `briefs/` | the prompts, as files. `price-trend`, `cross-asset-macro`, `execution-quality`, `price-integrity`, and `risk.v2.md` |
| `show.py` | print a stored report as it was written |

**The four seats are independent.** Each receives the same snapshot bytes and never
sees another seat's output. They are not a conversation; disagreement is the point, and
the record keeps it.

**A report is evidence or it is refused.** `schema.py` checks every number against the
snapshot it claims to come from. In the rehearsal runs, four of twelve replies were
refused for citing a figure that matched nothing — a fabricated price never becomes a
weight. `NO_CALL` is a valid answer; a seat forced to have a view will invent one.

**The risk agent may veto, never approve.** A failed or unknown gate blocks an order
whatever the model writes. The model can only *add* a refusal. `risk.v2.md` exists
because v1 said "an overall veto vetoes every order" without saying when one is
warranted, and the agent read that as a rule to veto whole plans over a single bad
order; v2 says an overall veto is for a plan unsafe as a whole.

**What they can never do:** hold a key that transacts or signs. The credential table
refuses it, the import graph forbids reaching `treasurer/`, and
`run/isolation.py` measures it live — both analyst keys were refused by the wallet API
with a 403.
