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

---

## 3. execution-quality

*Condition vocabulary: proceed or caution. Its question, "what does trading
this cost", has no direction. Asked for buy, hold or sell, the one recorded
execution-quality report returned `NO_CALL` on all 35 assets (LESSONS
2026-09-19).*

```
REPORT execution-quality 0x… 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

At $25 every tradeable name is cheap to trade. There is no fee anywhere, and
price impact is 21 bps at most, on COIN [quote.fee_bps, quote.swap_impact_bps,
all 20]. Three things matter more than impact this weekend.

First, every quote accepts a fill up to 5% worse than the price it shows
[quote.slippage_bps = 500, all 20]. That bound is about 24 times the worst
impact measured. A trade sent with it would accept losing 5% where the venue is
showing 0.2%.

Second, the venue quotes all weekend at prices that have moved, while every
mark is Friday's. A buy fills at the venue's price and is booked at the mark.
Wherever the two differ, the position starts with a gain or loss that is not
real.

Third, the quotes were 0 to 20 seconds old when the snapshot was built
[quote.age_s]. By the time a plan is made from them they will be older than the
60 seconds the fund allows, so the plan has to quote again.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution high
A buy pays 1.3% more than the price it would be booked at, eight times its
impact. It is the only name where the weekend gap works against a buyer by more
than a quarter of a point.
- venue 154.66 against mark 152.64 [quote.venue_price_usd, mark.price_usd]
- impact 16 bps [quote.swap_impact_bps]
Wrong if: the venue's price comes back to within 0.2% of the mark, as it is for
most names.

CALL NVDA 0xd0601ce157db5bdc3162bbac2a2c8af5320d9eec proceed high
Among the cheapest names to trade: 9 bps of impact, the venue within 0.2% of the
mark, and one of the three deepest corroborating markets.
- impact 9 bps [quote.swap_impact_bps]
- venue 222.05 against mark 222.45 [quote.venue_price_usd, mark.price_usd]
- $50.85M of 24-hour volume [corroboration.volume_24h_usd]
Wrong if: impact at $25 rises above 25 bps.

CALL SPY 0x117cc2133c37b721f49de2a7a74833232b3b4c0c proceed high
No measurable impact, and the venue within 0.13% of the mark.
- impact 0 bps [quote.swap_impact_bps]
- venue 762.52 against mark 761.55 [quote.venue_price_usd, mark.price_usd]
Wrong if: impact at $25 rises above 25 bps.
```

---

## 4. price-integrity

*Condition vocabulary. Its question, "does this price hold up today", has no
direction. It compares three sources the snapshot already carries and no other
seat compares: the Chainlink mark, GeckoTerminal, and the venue's price inside
the $25 quote. It exists because of the weekend. When the market is shut, this
is the question that matters most.*

```
REPORT price-integrity 0x42a9bd235aedd68e9f2881710577105cb46e3d27 253315c0e691c42a39a851092bb1b866dc6f605861a07fc21bb0da8027e8721c

Every stock's mark is its feed's last round before the weekend close, and none
will move until Monday 00:00Z [mark.updated_at, all 20]. Five tradeable names
now differ from GeckoTerminal by more than 100 bps [findings]. The venue's own
price is a third opinion, and it settles which side is wrong:
- for AMD and MSTR it agrees with GeckoTerminal. The market moved after the feed
  stopped, so the mark is stale;
- for AMZN, GOOGL and SGOV it agrees with the mark. GeckoTerminal is the odd one
  out.

The other fifteen agree to within about 1%.

CALL MSTR 0xec262a75e413fafd0df80480274532c79d42da09 caution high
The mark is stale. Both other prices sit above it, and they agree with each
other.
- mark 152.64, set Friday 23:41Z [mark.price_usd, mark.updated_at]
- GeckoTerminal 155.50 (+1.9%) on $4.42M of volume [corroboration.price_usd,
  corroboration.volume_24h_usd]
- venue 154.66 (+1.3%) [quote.venue_price_usd]
Wrong if: Monday's first round lands near 152.6, which would mean both other
prices were wrong.

CALL AMD 0x86923f96303d656e4aa86d9d42d1e57ad2023fdc caution medium
The same pattern, the other way. Both other prices are about 1% below a mark set
at 19:57Z on Friday. Medium, not high, because GeckoTerminal's volume is barely
over the $1M the fund requires of a corroborator.
- mark 559.42 [mark.price_usd]
- GeckoTerminal 553.56 (−1.0%) on $1.06M [corroboration.price_usd,
  corroboration.volume_24h_usd]
- venue 551.91 (−1.3%) [quote.venue_price_usd]
Wrong if: Monday's first round lands near 559.

CALL AMZN 0x12f190a9f9d7d37a250758b26824b97ce941bf54 proceed medium
The flagged divergence is GeckoTerminal's, not the mark's. GeckoTerminal is 4.7%
above the mark, while the venue, which would fill the trade, is within 0.23% of
it. A 4.7% move over one weekend with the venue unmoved is a bad pool reading,
not a stale feed.
- mark 253.86 [mark.price_usd]
- GeckoTerminal 265.83 (+4.7%) on $2.10M [corroboration.price_usd,
  corroboration.volume_24h_usd]
- venue 253.28 (−0.23%) [quote.venue_price_usd]
Wrong if: Monday's first round lands near 265.

CALL GOOGL 0x2e0847e8910a9732eb3fb1bb4b70a580adad4fe3 proceed medium
The same shape as AMZN, smaller. GeckoTerminal is 1.3% above, and the venue is
within 0.12%.
- mark 350.47, GeckoTerminal 355.17, venue 350.04 [mark.price_usd,
  corroboration.price_usd, quote.venue_price_usd]
Wrong if: Monday's first round lands near 355.

CALL SGOV 0x92fd66527192e3e61d4ddd13322aa222de86f9b5 proceed high
A 0–3 month Treasury fund that has not moved more than 0.05% on any day this
month has not fallen 1.2% over a weekend. GeckoTerminal's price is wrong, and
the venue agrees with the mark.
- iShares 0-3 Month Treasury Bond [asset.name]
- largest daily move in 30 closes: 0.05% [timeline]
- mark 101.11, GeckoTerminal 99.86 (−1.2%), venue 100.88 (−0.22%)
  [mark.price_usd, corroboration.price_usd, quote.venue_price_usd]
Wrong if: Monday's first round lands near 99.9.
```
