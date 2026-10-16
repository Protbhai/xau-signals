# Old project rules vs new benchmark: same data, same replay, no look-ahead (17 Oct 2026)

The old project's technical rules (`xauusd-telegram-monitor`, public repo) were ported line for
line into `strategies/old_monitor.py` and run through the same replay as the new candidates:
decisions see only candles completed by the check time; the same cap (3/day) and the OLD
project's own 30-minute cooldown apply to every strategy; outcomes come from later candles only.
Result files: `docs/research/results/oldvsnew-*.json` (every alert, every outcome).

**What could not be ported:** the old `confirmed_bias()` also demanded a verified news surprise in
the same direction, a verified market reaction, acceptable spread and no imminent release. No
historical dataset holds the first three (consensus figures are not free historically, and the
surprise→gold-direction rule was never written), so the replay treats those gates as OPEN. That is
the old design's *best case*. In production it has never emitted a direction.

**Accuracy** below = share of entered setups whose close is on the favourable side of the entry,
at the old design's own horizon (+15 min) and at the end of the sitting (15:00 IST). Moves are
reference-price excursions in USD from the entry/trigger level; not profits.

## Results

| strategy | window | alerts (/day) | zero-alert days | +15m favourable | to 15:00 favourable | median move to 15:00 (USD) | invalidation hit after entry |
|---|---|---|---|---|---|---|---|
| **old_session_v1** (5m+15m trend, break/retest/follow, 1m confirm) | dev 188 d, lag 2 | 5 (0.03) | 183 | 2/5 | 2/5 (40%) | −4.82 | 3/5 |
| | dev, lag 0 | 0 | 188 | – | – | – | – |
| | validation 34 d, lag 0/2/4 | 0 | 34 | – | – | – | – |
| **old_cloud_v1** (5m+15m structure, 1h agrees, 4h not opposing) | dev 188 d | 24 (0.13) | 166 | 10/24 (42%) | 11/24 (46%) | −1.37 | 15/24 |
| | validation 34 d | 5 (0.15) | 29 | 4/5 | 1/5 (20%) | −2.61 | – |
| | crosscheck futures 50 d | 5 (0.10) | 45 | 3/5 | 2/5 (40%) | −1.50 | – |
| **benchmark_v1** (new: 1h SMA20 trend, 5m EMA20 pullback, conditional trigger) | dev 188 d | 475 (2.53) | 11 | 178/289 (62%) | 160/286 (56%) | +3.32 | ~70% (tight level) |
| | validation 34 d | 85 (2.50) | 1 | 39/56 (70%) | 39/54 (72%) | +5.98 | 67% |
| | crosscheck futures 50 d | 126 (2.52) | 3 | 56/85 (66%) | 57/83 (69%) | +5.80 | – |

Benchmark figures here use the 30-minute cooldown for parity; with its deployed 20-minute cooldown
the numbers are within a point or two (see RESULTS.md).

## Why the old rules almost never fire

`old_session_v1` requires, at one check, all of: 5m EMA20 trend and 15m EMA20 trend in the same
direction (both above/below and sloping over 3 bars); a 6-bar reference range at least 1 ATR wide;
a breakout bar closing beyond it by 0.1 ATR; a retest bar whose extreme sits in a 0.35-ATR band and
closes beyond the level; a follow bar with a higher low (lower high) closing beyond both earlier bars
but no more than 1.5 ATR past the level; the pattern begun after 09:00 IST; and then a 1-minute bar,
closed after the 5m close, that makes a higher low above the previous 1m high, within 0.5 ATR of the
5m close, with no touch of the invalidation since the retest. Each condition is sensible; their
product occurs about once a month in this data (49 "entry pending" moments in 13,480 checks, 5
confirmations). The pattern also only confirms if the check lands 1–4 minutes after a 5m close: at
exact 5-minute boundaries no 1m bar has closed yet, so with a punctual scheduler it is structurally
zero. With the news/spread/reaction gates added back, the production count is zero by construction.

`old_cloud_v1` fires more (0.13/day) because it drops the 5m-trend, session-start and 1m steps, but
it enters at the close of the *third* bar of a breakout-retest-continuation sequence, i.e. up to
1.5 ATR into the move. Buying the extension is why its +15m accuracy is a coin flip (42%), its
to-15:00 median is negative, and its structural invalidation (the retest extreme) is hit after
entry in 62% of cases.

## Why the new benchmark does better on this evidence

It waits for a pullback *inside* an established 1h trend and states a conditional trigger (the
pullback bar's high/low), so entry is near the mean rather than at the extension, and a setup that
runs away is marked stale instead of chased. It fires 2.5 times a day, so the 3-alert cap is used,
and its favourable share stays above 50% in all three windows with positive medians. Its weak
spots are real: the cap selects by arrival time, and its invalidation level is tight.

## What this does and does not prove

- Sample sizes for the old rules are 5, 24, 5 and 5 alerts. They do not prove the old design
  "loses"; they prove it hardly ever speaks, and that when it does, this sample shows no edge.
- The validation period (Sep–Oct 2026) was a strong gold uptrend; both designs are long-biased
  there. The futures cross-check is the same period on another price series, not an independent one.
- The benchmark's edge is modest: ~0.5 ATR median favourable move before any cost, with a 1.2 USD
  round trip taken as a sensitivity, not a measurement.
- Neither replay used the live series (Twelve Data spot); paper mode from Monday is the check.
