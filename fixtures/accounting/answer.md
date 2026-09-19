# The known answer (unit 4.11)

`events.json` is a constructed list of events: they did not happen. This file works
out, by hand, what a ledger that tells economic truth must say about them, and
`expected.json` carries the same figures as data. `tests/test_accounting.py` holds
`core/ledger.py` to them, to the last digit.

**It was derived without running the ledger.** Each figure below comes from the event
list and the rules as `core/ledger.py`'s table states them, in exact rationals. The
only rounding any rule names is the basis a partial disposal removes, half-even to
10⁻³⁰ of a dollar; it happens once here, at the withdrawal, and is marked where it
does.

**The rules used**

- A holding's cost is its **average cost**. A disposal removes basis in proportion to
  the units it gives: `basis × units given ÷ units held`.
- A fill's **value is its cash leg** at that leg's recorded mark: what a buy paid, or
  what a sale received. The asset acquired takes that value as its basis.
- **Realised** is each disposal's proceeds less the basis it removed.
- A **fee** is a cost at its own mark, and is never part of any position's basis.
  Paying it uses up the asset it was paid in, at that asset's average cost.
- A **transfer** is capital, not income: in adds its worth to what was put in, out
  takes away the basis it carries.
- **Inference** is an expense beside the books: it moves no holding and is in no NAV.
- Marks for the final valuation are the committed capture's,
  `fixtures/snapshots/67364057-c06abd9e89f0`: **USDG 0.99992279**, **ETH
  2637.20423511**, **GME 22.55175**.

---

## The paper book

| # | Event | Working |
|---|---|---|
| 0 | Opening 200 USDG @ 0.99995 | basis and **opened** = 200 × 0.99995 = **199.99** |
| 1 | Buy 2 GME, gave 45 USDG @ 0.99995 | value = 45 × 0.99995 = 44.99775. USDG basis removed = 199.99 × 45⁄200 = 44.99775, so realised += 0. USDG: 155 units, basis 154.99225. GME: 2 units, basis 44.99775 |
| 2 | Buy 2 GME, gave 62 USDG @ 0.99990 | value = 62 × 0.99990 = 61.99380. USDG basis removed = 154.99225 × 62⁄155 = 61.99690, so realised += 61.99380 − 61.99690 = **−0.00310** (USDG's own mark fell). USDG: 93 units, basis 92.99535. GME: 4 units, basis 106.99155 — average cost 26.7478875 |
| 3 | Sell 1 GME (a quarter), got 23 USDG @ 0.99992 | value = 23 × 0.99992 = 22.99816. GME basis removed = 106.99155 × 1⁄4 = 26.7478875, so realised += 22.99816 − 26.7478875 = **−3.7497275**. GME: 3 units, basis 80.2436625. USDG: 116 units, basis 115.99351 |

**Held:** 3 GME, 116 USDG. **Opened** 199.99. **Realised** −0.00310 + −3.7497275 =
**−3.7528275**. **Costs** 0. **Expenses** 0.

At the capture's marks:

| | units | × mark | value | basis | unrealised |
|---|---|---|---|---|---|
| GME | 3 | 22.55175 | 67.65525 | 80.2436625 | −12.5884125 |
| USDG | 116 | 0.99992279 | 115.99104364 | 115.99351 | −0.00246636 |
| **NAV** | | | **183.64629364** | | **−12.59087886** |

**The identity:** 199.99 + (−3.7528275) + (−12.59087886) − 0 = **183.64629364** = NAV.

---

## The real book

| # | Event | Working |
|---|---|---|
| 4 | Opening 0.00046 ETH @ 2600 | basis and opened = **1.196** |
| 5 | Opening 0.078742 USDG @ 0.99995 | basis and opened = **0.0787380629** |
| 6 | **Transfer in** 5 USDG @ 0.99995 | 4.99975 added to **opened** — a contribution, so realised does not move. USDG: 5.078742 units, basis 5.0784880629 |
| 7 | Live fill: gave 0.0002 ETH, got 0.52 USDG @ 0.99992 | value = the cash leg = 0.52 × 0.99992 = 0.5199584. ETH basis removed = 1.196 × 2⁄4.6 = 0.52, so realised += **−0.0000416**. ETH: 0.00026 units, basis 0.676. USDG: 5.598742 units, basis 5.5984464629 |
| 8 | Fee: 0.000003 ETH @ 2637 (gas on that swap) | cost = **0.007911**. ETH basis removed = 0.676 × 3⁄260 = 0.0078, so realised += 0.000111. ETH: 0.000257 units, basis 0.6682 |
| 9 | Fee: 0.000004 ETH @ 2637 (**gas on a transaction that reverted**) | cost = **0.010548**, and there is no fill: nothing was bought or sold. ETH basis removed = 0.6682 × 4⁄257 = 0.0104, so realised += 0.000148. ETH: 0.000253 units, basis 0.6578 |
| 10 | **Transfer out** 2 USDG @ 0.99992 | basis removed = 5.5984464629 × 2⁄5.598742 = 1.99989442731956571672707904740029…, the one share here that does not divide, rounded half-even to 10⁻³⁰: **1.9998944273195657167270790474**. It comes off **opened**, not off realised: a withdrawal is not a loss. USDG: 3.598742 units, basis 3.5985520355804342832729209526 |
| 11 | Inference 0.099454 (risk) | expense, no holding moves |
| 12 | Inference 0.260564 (price-trend) | expense, no holding moves |

**Opened** = 1.196 + 0.0787380629 + 4.99975 − 1.9998944273195657167270790474 =
**4.2745936355804342832729209526**.
**Realised** = −0.0000416 + 0.000111 + 0.000148 = **0.0002174**.
**Costs** = 0.007911 + 0.010548 = **0.018459**. **Expenses** = 0.099454 + 0.260564 =
**0.360018**, beside the NAV and in no book's value.

At the capture's marks:

| | units | × mark | value | basis | unrealised |
|---|---|---|---|---|---|
| ETH | 0.000253 | 2637.20423511 | 0.66721267148283 | 0.6578 | 0.00941267148283 |
| USDG | 3.598742 | 0.99992279 | 3.59846414113018 | 3.5985520355804342832729209526 | −0.0000878944502542832729209526 |
| **NAV** | | | **4.26567681261301** | | **0.0093247770325757167270790474** |

**The identity:** 4.2745936355804342832729209526 + 0.0002174 +
0.0093247770325757167270790474 − 0.018459 = **4.26567681261301** = NAV.

The two books are never added. 183.64629364 and 4.26567681261301 are two figures, and
the fund has no third.

---

## What this fixture does not contain, and why

The journal keeps four kinds of event, and 4.11 added a fifth, the transfer. Of the
events the operator named, these are still not expressible:

- **Settled revenue.** An x402 sale that settles is income, not capital, so it cannot
  be a transfer in without becoming a contribution. It needs an event of its own and a
  line in the identity. The evidence it would rest on — `PaymentSettled` — is unit
  7.2's, and the line is 6.1's. **The ledger needs it, not this fixture.**
- **Revenue that has not settled.** It is not an event at all, and must not become
  one: nothing is booked from an HTTP status, and revenue is evidenced by settlement
  (PLAN §2 invariant 9). An unsettled sale leaves the books unchanged, which is what
  this fixture shows by having no event for it. 6.2 surfaces it as an exception.
- **LLM credits bought.** The credits are bought inside each agent's own Bankr
  account, not from the fund's execution wallet, so neither book sees the purchase.
  What the books see is consumption, which is here twice, as an expense. Whether the
  operator's credit spend becomes the fund's cost is 6.3's question.
- **Persisting a transfer.** `store/schema.sql` accepts four kinds, and a transfer is
  the fifth: the journal cannot keep one yet. That is 4.6's full version, and the
  store was outside this unit's paths.
