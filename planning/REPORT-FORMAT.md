# The analyst report (unit 2.1, a stop)

**Status: four hand-written examples, awaiting the operator.** No schema, no
brief and no code exists for this yet. 2.2 and 2.3 are built from whatever is
approved here.

**The capture.** Every example is written against the committed capture
`66852293-253315c0e691`, snapshot
`253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c`, built
Saturday 19 September at 06:04Z. That is inside the weekend closed session. Every
stock's mark is its feed's last round from Friday. The venue and GeckoTerminal
keep trading, and five tradeable names carry closed-session divergence
findings. **The reports are written for that weekend, not an imagined trading
day.** Every number comes from the capture and cites where.

**How to read them.** Each report is a short note:
- a first line the machine reads;
- a paragraph of what the analyst sees;
- then a few calls. Each call has one machine line, a sentence or two of
  reasoning, the figures behind it, and what would prove it wrong.

The decisions behind that shape follow the four reports.

**Agent addresses.** The price-integrity report carries its real agent address,
from the account made at 2.0. The other three accounts do not exist yet
(`research/findings.md` §2.0), so their first line shows `0x…`.

---

## 1. price-trend

*Direction vocabulary: buy, hold or sell. Its question, "where is this price
going", has a direction.*

```
REPORT price-trend 0x… 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The market went nowhere this month: SPY ended the 30 days where it began
(762.21 → 761.55, [SPY timeline 2026-08-20, SPY mark.price_usd]). The trends
worth following are in single names. Chips and Meta are up hard, Amazon is
drifting lower, and Nvidia is stuck. Every price here is Friday's close. The
feeds are frozen for the weekend, and nothing below uses a weekend price.

I passed on MSTR and COIN. Much of their month came in Friday's session alone
(MSTR +16% on the day, COIN +12%: [MSTR timeline 2026-09-17, MSTR timeline
2026-09-18, COIN timeline 2026-09-17, COIN timeline 2026-09-18]). A trend read
off one day's spike is a guess.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc buy medium
The strongest trend on the list. It closed Friday at its 30-day high, 23% above
its 3 September low, and it held two pullbacks on the way up.
- 559.42, Friday's close and the 30-day high [mark.price_usd]
- 454.99, the low on 3 September [timeline 2026-09-03]
- +9.0% in the last two sessions, from 513.31 [timeline 2026-09-16]
Wrong if: it closes back below 513.31, Wednesday's close.

CALL META 0xc0d6457c16cc70d6790dd43521c899c87ce02f35 buy medium
Up 22% in the month in a steady run of higher highs, with a smaller daily swing
than AMD (1.9% against 3.0%). Friday gave back 2.3% from Thursday's high. That
is a pause, not a break.
- 544.71 → 666.76 over 30 days [timeline 2026-08-20, mark.price_usd]
- 682.43, Thursday's close and the high [timeline 2026-09-17]
- 644.00, the last pullback low, on 10 September [timeline 2026-09-10]
Wrong if: it closes below 644.00.

CALL INTC 0xc72b96e0e48ecd4dc75e1e45396e26300bc39681 buy low
Up 12% since Tuesday and 18% in the month. It swings about 3.7% a day, so the
trend is real and the conviction is not.
- 97.22 → 109.05 since Tuesday's close [timeline 2026-09-15, mark.price_usd]
- 92.42 a month ago [timeline 2026-08-20]
Wrong if: it closes below 100.91, Wednesday's close.

CALL NVDA 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec hold low
Nvidia has gone nowhere for a month. It sits in a 208–230 range, about
two-thirds of the way up, after bouncing 5% off 211.92 this week. The chip rally
is happening in AMD and Intel, not here. I would neither add nor cut until it
leaves the range.
- 222.45, Friday's close [mark.price_usd]
- 207.91 low on 24 August, 230.24 high on 4 September [timeline 2026-08-24,
  timeline 2026-09-04]
- +2.6% over 30 days [timeline 2026-08-20]
Wrong if: it closes above 230.24, a breakout and a buy, or below 207.91, where
the range breaks and it becomes a sell.

CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 sell low
Lower highs all month: 266.08, then 259.03, then 257.13, then a low of 245.74
on Wednesday. Friday's bounce to 253.86 did not reach the last high.
- 266.08 on 28 August and 257.13 on 11 September [timeline 2026-08-28,
  timeline 2026-09-11]
- 245.74 on 16 September [timeline 2026-09-16]
- 253.86, Friday's close [mark.price_usd]
Wrong if: it closes above 257.13, ending the run of lower highs.
```

---

## 2. cross-asset-macro

*Direction vocabulary. Its question, "what does the way these assets move
together favour", ends in add, keep or cut for an asset. Most weeks the honest
answer is very few calls.*

```
REPORT cross-asset-macro 0x… 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

The index is flat and the stocks are not moving together. SPY ended the 30 days
where it began and QQQ rose 1.4% [SPY timeline, QQQ timeline]. Across the 18
tradeable stocks, daily returns correlate only 0.22 on average [timeline, all
18]. Two pairs are the exception: MSTR and COIN move as one (0.87), and so do
AMD and INTC (0.78). Oil runs the other way. USO rose 14.5% while its daily
moves correlated −0.37 with SPY. Treasury bills paid about 2.9% a year (SGOV
100.88 → 101.11 in 29 days, [SGOV timeline 2026-08-20, SGOV mark.price_usd]).
There are no new closes since Friday, so nothing here changes over the weekend.

Two calls, and no call on anything else. A flat, loosely correlated market says
it is not moving as one. It does not say which way it goes next, and twenty
daily returns are too few to call a regime.

CALL USO 0xa30fa36db767ad9ed3f7a60fc79526fb4d56d344 buy low
The one tradeable asset that moves against stocks. Holding some makes the book
depend less on the equity tape. That is the reason for the call, not a view on
oil.
- −0.37, its correlation with SPY's daily returns over 30 days [timeline, SPY
  timeline]
- +14.5% over 30 days, 134.97 → 154.54 [timeline 2026-08-20, mark.price_usd]
- 4.3% below its 15 September high of 161.41 [timeline 2026-09-15]
Wrong if: its correlation with SPY turns positive, because then it no longer
diversifies.

CALL COIN 0x6330d8c3178a418788df01a47479c0ce7ccf450b hold medium
COIN and MSTR are the same bet. If the fund buys MSTR, it already owns COIN's
move, and buying COIN as well doubles it. Hold, don't add.
- 0.87, COIN–MSTR correlation of daily returns [timeline, MSTR timeline]
- COIN +12.6% and MSTR +35.9% over 30 days: the same bet, and MSTR carries more
  of it [timeline 2026-08-20, MSTR timeline 2026-08-20]
Wrong if: the two stop moving together, with the correlation below 0.5 on a
later snapshot.
```
