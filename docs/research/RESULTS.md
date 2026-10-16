# Backtest / replay results (16 Oct 2026)

All runs use the real engine, gate, cap (3/day), dedup and 20-minute cooldown via `replay.py`.
Decisions use only candles completed by the decision time. Parameters are the ones fixed in
`docs/DESIGN.md` before any result was read; nothing was tuned between runs. Raw outputs:
`docs/research/results/*.json` (every alert with its outcome). Analysis: `research/analyze.py`.

**What the numbers are:** reference-price excursions measured from the trigger level of alerts
that triggered (a later 5m close beyond the trigger before the 30-minute expiry). They are **not**
trade results: no fill, spread, slippage or exit rule is assumed. "fav" = close at the horizon is
on the favourable side of the trigger. Cost sensitivity subtracts a fixed 1.2 USD round trip
(0.6 per side; retail XAU/USD spread range, **unverified** for any broker).

## Series and windows

| tag | series | price type | window | session days |
|---|---|---|---|---|
| dev | Binance XAUUSDT perp 5m/1h (from 1m) | perp, ~$7 over spot | 2025-12-11 → 2026-08-31 | 188 |
| validation | same | same | 2026-09-01 → 2026-10-16 (untouched until dev was written up) | 34 |
| crosscheck | Yahoo GC=F 5m/1h | COMEX futures, ~$20 over spot | 2026-08-10 → 2026-10-16 | 50 |

Validation and crosscheck overlap in calendar time: they are one period seen on two price
series, not two independent periods. Dukascopy spot could not be downloaded (connection
throttling / HTTP 503 on 16 Oct); it remains the intended spot robustness check.

## Development window (188 days, lag 0 and 2 min identical; lag 7 min in brackets)

| strategy | qualified | sent (/day) | 0-alert days | blocked cap / cooldown | triggered | inval. before trigger | expired | to 15:00 fav : adv | median move USD (after 1.2 cost) | med MFE / MAE |
|---|---|---|---|---|---|---|---|---|---|---|
| benchmark_v1 | 1552 | 486 (2.59) [484] | 11 | 833 / 233 | 295 (61%) | 154 (32%) | 37 | 158 : 134 (54%) | +2.72 (+1.52) [+2.11] | 14.1 / 10.6 |
| breakout_retest_v1 | 161 | 110 (0.59) | 103 | 1 / 50 | 58 (53%) | 45 (41%) | 7 | 27 : 31 (47%) | −1.08 (−2.28) | 11.9 / 14.3 |
| range_rejection_v1 | 129 | 101 (0.54) | 129 | 8 / 20 | 71 (70%) | 27 (27%) | 3 | 36 : 33 (51%) | +0.47 (−0.73) | 9.7 / 6.5 |
| benchmark_ext_v1 | 1120 | 388 (2.06) | 38 | 545 / 187 | 241 (62%) | 120 (31%) | 27 | 135 : 103 (57%) | +2.54 (+1.34) | 12.3 / 9.0 |

Shorter horizons for the benchmark: +30m fav 182:113 (62%), +60m 179:116 (61%), +120m 161:134 (55%).
Range rejection: +30m 44:25 (62%) decaying to 51% by 15:00; UP fades 40% vs DOWN fades 67%.

Things the table hides (from `analyze.py`):
- **The cap selects by arrival time, not quality.** benchmark_v1 hits the 3-alert cap on 147 of
  188 days; 63% of its alerts fall in 09:00–10:59 IST. Alert rank (1st/2nd/3rd of the day) makes
  no difference to outcome (53–55% fav), so the early bias is harmless but means a good setup at
  13:00 is usually never sent.
- **The structural invalidation is hit after trigger in 71% of benchmark setups** before 15:00.
  It is one 5m candle's range below the entry; as an observed level it is honest, as a stop it
  is tight. The message states it as "invalid if", never as a stop.
- The extension filter (`benchmark_ext_v1`) removes 28% of qualified setups and improves the
  favourable share by 3 points and MAE by ~15%; the gain is within sample noise.
- `breakout_retest_v1` has a design flaw found by the replay: one failed breakout marks the
  rest of the day invalidated (6,328 of 13,480 checks), so a second breakout is never seen.
  It is kept as a documented negative result, not fixed and re-run (that would be tuning).

## Validation window (34 days, untouched) and cross-check

| strategy | window | sent (/day) | triggered | to 15:00 fav | median move USD (after 1.2) | positive after cost | inval. hit after trigger |
|---|---|---|---|---|---|---|---|
| benchmark_v1 | validation | 88 (2.59) | 54 (61%) | 37:15 (71%) | +6.86 (+5.66) | 65% | 67% |
| benchmark_v1 | crosscheck (futures) | 130 (2.60) | 83 (64%) | 54:27 (67%) | +4.90 | – | – |
| benchmark_ext_v1 | validation | 78 (2.29) | 48 (62%) | 31:15 (67%) | +6.86 (+5.66) | 61% | 69% |
| benchmark_ext_v1 | crosscheck | 119 (2.38) | 77 (65%) | 49:26 (65%) | +5.80 | – | – |
| breakout_retest_v1 | validation | 23 (0.68) | 16 (70%) | 12:4 (75%) | +3.06 (+1.86) | 69% | 75% |
| breakout_retest_v1 | crosscheck | 44 (0.88) | 29 (66%) | 19:9 (66%) | +3.90 | – | – |
| range_rejection_v1 | validation | 19 (0.56) | 10 (53%) | 5:5 (50%) | −5.10 (−6.30) | 40% | 90% |
| range_rejection_v1 | crosscheck | 29 (0.58) | 18 (62%) | 9:9 (50%) | −4.45 | – | – |

Sept–Oct 2026 was a strong gold uptrend (both UP and DOWN benchmark alerts were ~70% fav, so it
is not only long bias), and 52 triggered setups is a small sample: the validation figures are
better than dev and should be read as "not contradicted", not "confirmed".

## Decision

- **Production candidate: `benchmark_v1`** (preserved baseline). It is the only candidate whose
  sign and trigger rate are consistent across dev, validation and the futures cross-check, and it
  produces the 2–3 alerts/day the brief asks for without forcing them (11 zero-alert days in 188).
- `benchmark_ext_v1`: no benefit shown that justifies the extra rule; shelved, kept in the registry.
- `range_rejection_v1`: rejected (negative out of sample; its 30-minute edge does not survive to 15:00).
- `breakout_retest_v1`: rejected as built (sign flips between windows; day-killing invalidation).

## Limits of this evidence

1. Backtest series ≠ live series (perp vs Twelve Data spot). Rules are ATR-relative, but the
   paper phase on the live series is the real test.
2. One year of data, dominated by a rising gold market. No bear-regime sample.
3. Scheduler lag was modelled (0/2/7 min), not measured; the probe workflow measures it.
4. Costs are a sensitivity line, not a measurement.
5. Three horizons per setup on the same price path are correlated, not independent evidence;
   the within-session (to 15:00 IST) column is the one that matches the user's sitting.
