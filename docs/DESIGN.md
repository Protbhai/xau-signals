# Design notes and pre-registration

Written **before** the first backtest result was read (16 Oct 2026, ~17:05 UTC), so that
parameters and success criteria are on record and cannot drift to fit the sample.

## What the system is

A *conditional observation* service. Every 5 minutes inside 09:00–15:00 IST it asks:

1. **Direction** – from the 1h chart (completed candles only).
2. **Setup** – from the 5m chart: is a defined structure present right now?
3. **Entry condition** – a level the user watches on their own 1-minute chart. The system
   does not time the 1m entry; the free scheduler's jitter (1–3 min measured on dispatch,
   unbounded on GitHub cron) makes any claim of a timed 1m entry dishonest.
4. **Invalidation** – an observed structural level, not a money-based stop.
5. **Freshness** – the newest completed 5m candle must have closed within 15 minutes of the
   check (`max_candle_age_seconds = 900`), rechecked immediately before delivery; and the
   price must not already be more than 1 ATR past the trigger (`stale_extension_atr`).

States are explicit: `DATA_UNAVAILABLE`, `DATA_STALE`, `NO_SETUP`, `SETUP_FORMING`,
`SETUP_QUALIFIED`, `SETUP_INVALIDATED`, `SETUP_EXPIRED`. Unavailable evidence is never
reported as "neutral market".

## Why 1h bias + 5m setup for a 6-hour window

The window is 03:30–09:30 UTC: late Asia into the pre-London hours, after Shanghai/Tokyo
open and before London/US flows. One 6-hour window holds six 1h candles: enough for a
1h trend read to matter, too few for a daily-chart rule to change inside the sitting. The
5m chart gives 72 decision points, which fits a 5-minute check cadence exactly. 1m candles
are not used for decisions at all: a free scheduler cannot act on them in time.

## Candidates (all parameters fixed here; none tuned)

| id | idea | direction | setup | trigger | invalidation |
|---|---|---|---|---|---|
| `benchmark_v1` | trend-pullback continuation (the preserved baseline) | 1h close vs rising/falling SMA20 (slope over 3 bars) | 5m candle touches EMA20 (±0.25 ATR14) and closes with the bias | that candle's high/low | that candle's low/high ∓ 0.1 ATR |
| `breakout_retest_v1` | opening-range breakout with a held retest | direction of the first 5m close beyond the 09:00–10:30 IST range (range ≥ 1 ATR) | later candle retests the level (±0.3 ATR) and closes with the breakout; a close back inside kills it | retest candle's high/low | the broken level ∓ 0.1 ATR |
| `range_rejection_v1` | fade the range edge when 1h is demonstrably ranging | against the poke | 1h: \|close−SMA20\| ≤ 0.75 ATR and \|slope\| ≤ 0.25 ATR; 5m: wick beyond the 36-bar range, close back inside, wick ≥ body | close-side extreme of the rejection candle | wick extreme ± 0.1 ATR |
| `benchmark_ext_v1` | benchmark + over-extension filter | as benchmark | as benchmark, but skipped when the 1h close is > 2 ATR(1h) from SMA20 | as benchmark | as benchmark |

Common: expiry 6 bars (30 min) after the anchor candle closes; stale if price is > 1 ATR past
the trigger at decision time.

## Alert policy

- **Cap 3 per IST session date**, counted on this system's setup alerts only (paper and live
  alike, so paper measures the real cadence). Failure alerts never count.
- **Dedup**: `setup_id = sha1(direction | setup_type | anchor candle open time)`. The same
  structure seen on later checks is the same setup and is never re-sent.
- **Cooldown 20 minutes** after a sent alert. Justification: a 5m structure needs several
  candles to form a new, distinct anchor; 20 min (4 bars) plus the 30-min expiry means
  consecutive alerts are about different structures, and three alerts cannot bunch into one
  40-minute burst at the open. It is a design choice, not an optimised number; the replay
  reports how many qualified setups it blocks.
- **At-most-once delivery**: a slot is reserved in state before the Telegram call; `sent`
  only on HTTP 200 + `ok:true` + `message_id`; timeouts after send are `ambiguous` and
  are never retried (no idempotency key exists in the Bot API). Exactly-once is not claimed.
- **One effective run per 5-minute slot**, so two schedulers can fire without double work.
- Outside 09:00–15:00 IST the job fetches nothing (except a 15-minute pre-session warm-up).

## Evaluation plan (fixed before results)

- Development window: Binance XAUUSDT 5m/1h, 2025-12-11 → 2026-08-31.
- Validation window (untouched until the dev read-out is written): 2026-09-01 → 2026-10-16.
- Robustness: the same code on Dukascopy spot BID 5m/1h (different price series, same market)
  for whatever range the throttled download yields.
- Scheduler delay modelled at 0 and 2 minutes. Live measurement replaces the model later.
- Reported per strategy: session days, checks, distinct qualified setups, alerts sent,
  alerts/day, zero-alert days, gate blocks by reason (cap / cooldown / duplicate / stale),
  trigger rate, invalidation-before-trigger rate, expiry rate, unavailable, and for triggered
  setups the favourable/adverse/flat count and median close move, MFE, MAE at +30m, +60m,
  +120m and **to 15:00 IST** (within-sitting), in price units and later in ATR.
- **Not reported as profit**: these are reference-price excursions from the trigger level with
  no fill, spread, slippage or exit rule. Spread/slippage are *unverified*; a sensitivity line
  subtracts a fixed cost of 0.3 and 0.6 USD per side (typical retail XAU/USD spread range,
  unverified for the user's broker) from the median close move.

### Promotion criteria for live Telegram setup alerts (paper → live)

All of the following over at least **15 paper session days** on the production host:

1. Cadence: ≥ 90% of 5-minute slots inside the session produced a run; median lag ≤ 3 min,
   95th percentile ≤ 6 min, measured from `state.json` run records.
2. Data: ≤ 2 `DATA_UNAVAILABLE`/`DATA_STALE` checks per session on median; no unexplained gaps
   inside the session on more than 1 day in 5.
3. Delivery: every paper alert would have passed the gate; test messages to Telegram return
   `ok:true` in ≥ 99% of attempts over the period.
4. Strategy: the chosen candidate's validation-window figures are not materially worse than
   its development-window figures (trigger rate within 10 points, favourable:adverse ratio
   not inverted), and forward paper outcomes over the 15 days do not contradict them.
5. Messages read correctly on the phone: IST times, scope line, cap counter, no HTML leaks.

Promotion is a one-variable change (`XAU_MODE=live`) with rollback by setting it back to
`paper`; the strategy version string is in every message.
