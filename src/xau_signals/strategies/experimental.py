"""Experimental strategy candidates. Each is deliberately small and explainable.

They share the benchmark's output contract so the engine, gate, replay and
outcome code need no changes. None of these is tuned; parameters are first
guesses written down BEFORE the first backtest (see docs/DESIGN.md).

breakout_retest_v1   Opening-range breakout with a HELD retest.
range_rejection_v1   Fade of the session range edge when the 1h is demonstrably ranging.
benchmark_ext_v1     benchmark_v1 plus an over-extension filter (tests whether a filter
                     earns its complexity; the replay reports how many setups it removes).
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from ..candles import Candle
from ..timeutil import IST, interval_seconds, to_utc
from .base import Evaluation, Setup, SetupState, atr, sma
from .benchmark import BenchmarkV1


def _session_start_utc(as_of: datetime, start: time = time(9, 0)) -> datetime:
    ist = to_utc(as_of).astimezone(IST)
    return datetime.combine(ist.date(), start, IST).astimezone(to_utc(as_of).tzinfo)


class BreakoutRetestV1:
    """Opening range = high/low of the completed 5m candles from 09:00 IST for `range_minutes`.

    After the range is formed: a 5m close beyond the range in either direction is the
    breakout. The setup qualifies on the first later candle that (a) pulls back to within
    `retest_tol_atr` ATR of the broken level without closing back inside the range, and
    (b) closes in the breakout direction. Direction = breakout direction (no 1h filter:
    this candidate tests session structure alone).
    """
    name = "breakout_retest_v1"
    version = "1.0.0"

    def __init__(self, range_minutes: int = 90, atr_period: int = 14, retest_tol_atr: float = 0.3, expiry_bars: int = 6,
                 stale_extension_atr: float = 1.0, invalidation_buffer_atr: float = 0.1, min_range_atr: float = 1.0, **_):
        self.range_minutes = range_minutes
        self.atr_period = atr_period
        self.tol = retest_tol_atr
        self.expiry_bars = expiry_bars
        self.stale_ext = stale_extension_atr
        self.inv_buf = invalidation_buffer_atr
        self.min_range_atr = min_range_atr

    def evaluate(self, *, as_of: datetime, bias_candles: list[Candle], setup_candles: list[Candle]) -> Evaluation:
        as_of = to_utc(as_of)
        s = [c for c in setup_candles if c.ts_close <= as_of]
        ev = Evaluation(as_of=as_of, bias="NONE", state=SetupState.DATA_UNAVAILABLE)
        if len(s) < self.atr_period + 2:
            ev.reasons.append("need more 5m candles")
            return ev
        ev.setup_candle_ts = s[-1].ts_open
        start = _session_start_utc(as_of)
        range_end = start + timedelta(minutes=self.range_minutes)
        rng = [c for c in s if start <= c.ts_open and c.ts_close <= range_end]
        a = atr(s, self.atr_period)[-1]
        if a is None or a <= 0:
            ev.reasons.append("ATR not ready")
            return ev
        ev.metrics["setup_atr"] = a
        if as_of < range_end or not rng:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append(f"opening range forming until {range_end.astimezone(IST):%H:%M} IST")
            return ev
        hi, lo = max(c.high for c in rng), min(c.low for c in rng)
        ev.metrics.update({"range_high": hi, "range_low": lo})
        if hi - lo < self.min_range_atr * a:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append(f"opening range {hi - lo:.2f} too narrow (< {self.min_range_atr} ATR)")
            return ev
        after = [c for c in s if c.ts_open >= range_end]
        # find the first breakout close
        direction, level, bo_idx = None, None, None
        for i, c in enumerate(after):
            if c.close > hi:
                direction, level, bo_idx = "UP", hi, i
                break
            if c.close < lo:
                direction, level, bo_idx = "DOWN", lo, i
                break
        if direction is None:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append(f"no 5m close beyond opening range [{lo:.2f}, {hi:.2f}] yet")
            return ev
        ev.bias = direction
        ev.reasons.append(f"breakout {direction} of opening range at {after[bo_idx].ts_open.astimezone(IST):%H:%M} IST (level {level:.2f})")
        post = after[bo_idx + 1:]
        if not post:
            ev.state = SetupState.SETUP_FORMING
            ev.reasons.append("waiting for a retest candle")
            return ev
        # invalidation: a close back inside the range beyond the level by the buffer kills the idea
        for c in post:
            back_inside = (c.close < level - self.inv_buf * a) if direction == "UP" else (c.close > level + self.inv_buf * a)
            if back_inside:
                ev.state = SetupState.SETUP_INVALIDATED
                ev.reasons.append(f"breakout failed: 5m close back inside the range at {c.ts_open.astimezone(IST):%H:%M} IST")
                return ev
        last = post[-1]
        touched = (last.low <= level + self.tol * a) if direction == "UP" else (last.high >= level - self.tol * a)
        closed_with = last.close > last.open if direction == "UP" else last.close < last.open
        if not touched:
            ev.state = SetupState.SETUP_FORMING
            ev.reasons.append("breakout holding, no retest of the level yet")
            return ev
        if not closed_with:
            ev.state = SetupState.SETUP_FORMING
            ev.reasons.append("retest touched the level but the candle did not close with the breakout")
            return ev
        step = interval_seconds(last.interval)
        trig = last.high if direction == "UP" else last.low
        inval = (level - self.inv_buf * a) if direction == "UP" else (level + self.inv_buf * a)
        setup = Setup(direction, "breakout_held_retest", last.ts_open, trig, min(level, level + (self.tol * a if direction == "UP" else -self.tol * a)),
                      max(level, level + (self.tol * a if direction == "UP" else -self.tol * a)), inval,
                      last.ts_close + timedelta(seconds=step * self.expiry_bars), a, notes=f"opening-range {direction} breakout, retest held")
        ev.setup = setup
        ext = (last.close - trig) if direction == "UP" else (trig - last.close)
        if ext > self.stale_ext * a or as_of > setup.expires_at:
            ev.state = SetupState.SETUP_EXPIRED
            ev.reasons.append("stale or expired")
            return ev
        ev.state = SetupState.SETUP_QUALIFIED
        return ev


class RangeRejectionV1:
    """Fade the edge of the recent range when the 1h chart is demonstrably ranging.

    Ranging (1h): |close - SMA20| <= range_band_atr * ATR(1h) and |SMA slope| <= slope_atr * ATR(1h).
    Range (5m): high/low of the last `lookback_bars` completed 5m candles excluding the last one.
    Setup: the last candle pokes beyond the edge (wick) but closes back inside, with wick >= body.
    Direction is AGAINST the poke. Trigger = close-side extreme of the rejection candle;
    invalidation = the wick extreme +- buffer.
    """
    name = "range_rejection_v1"
    version = "1.0.0"

    def __init__(self, bias_sma: int = 20, bias_lookback_slope: int = 3, atr_period: int = 14, range_band_atr: float = 0.75,
                 slope_atr: float = 0.25, lookback_bars: int = 36, expiry_bars: int = 6, stale_extension_atr: float = 1.0,
                 invalidation_buffer_atr: float = 0.1, **_):
        self.bias_sma, self.slope_n, self.atr_period = bias_sma, bias_lookback_slope, atr_period
        self.band, self.slope_atr, self.lookback = range_band_atr, slope_atr, lookback_bars
        self.expiry_bars, self.stale_ext, self.inv_buf = expiry_bars, stale_extension_atr, invalidation_buffer_atr

    def evaluate(self, *, as_of: datetime, bias_candles: list[Candle], setup_candles: list[Candle]) -> Evaluation:
        as_of = to_utc(as_of)
        b = [c for c in bias_candles if c.ts_close <= as_of]
        s = [c for c in setup_candles if c.ts_close <= as_of]
        ev = Evaluation(as_of=as_of, bias="NONE", state=SetupState.DATA_UNAVAILABLE)
        if len(b) < self.bias_sma + self.slope_n + 1 or len(s) < max(self.lookback + 2, self.atr_period + 2):
            ev.reasons.append("need more candles")
            return ev
        ev.bias_candle_ts, ev.setup_candle_ts = b[-1].ts_open, s[-1].ts_open
        closes = [c.close for c in b]
        sm = sma(closes, self.bias_sma)
        a1 = atr(b, self.atr_period)[-1]
        if sm[-1] is None or sm[-1 - self.slope_n] is None or not a1:
            ev.reasons.append("1h indicators not ready")
            return ev
        dist = abs(closes[-1] - sm[-1])
        slope = abs(sm[-1] - sm[-1 - self.slope_n])
        ev.metrics.update({"bias_dist_atr": dist / a1, "bias_slope_atr": slope / a1})
        if dist > self.band * a1 or slope > self.slope_atr * a1:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append(f"1h not ranging (dist {dist / a1:.2f} ATR, slope {slope / a1:.2f} ATR)")
            return ev
        a = atr(s, self.atr_period)[-1]
        if not a:
            ev.reasons.append("5m ATR not ready")
            return ev
        prior = s[-1 - self.lookback:-1]
        hi, lo = max(c.high for c in prior), min(c.low for c in prior)
        last = s[-1]
        ev.metrics.update({"range_high": hi, "range_low": lo, "setup_atr": a})
        wick_up, wick_dn = last.high - max(last.open, last.close), min(last.open, last.close) - last.low
        direction = None
        if last.high > hi and last.close < hi and wick_up >= last.body:
            direction, extreme, trig, label = "DOWN", last.high, min(last.open, last.close), "upper"
        elif last.low < lo and last.close > lo and wick_dn >= last.body:
            direction, extreme, trig, label = "UP", last.low, max(last.open, last.close), "lower"
        if direction is None:
            inside = lo <= last.close <= hi
            ev.state = SetupState.NO_SETUP if inside else SetupState.SETUP_FORMING
            ev.reasons.append("ranging 1h; no rejection at the 5m range edge on the last candle" if inside else "price outside the range without rejection")
            return ev
        ev.bias = direction
        step = interval_seconds(last.interval)
        inval = extreme + self.inv_buf * a if direction == "DOWN" else extreme - self.inv_buf * a
        setup = Setup(direction, "range_edge_rejection", last.ts_open, trig, min(trig, extreme), max(trig, extreme), inval,
                      last.ts_close + timedelta(seconds=step * self.expiry_bars), a, notes=f"rejection at {label} edge of {self.lookback}-bar range")
        ev.setup = setup
        ext = (last.close - trig) if direction == "UP" else (trig - last.close)
        if ext > self.stale_ext * a or as_of > setup.expires_at:
            ev.state = SetupState.SETUP_EXPIRED
            return ev
        ev.state = SetupState.SETUP_QUALIFIED
        ev.reasons.append(f"rejection {direction} at {label} edge {extreme:.2f}; trigger {trig:.2f}, invalidation {inval:.2f}")
        return ev


class BenchmarkExtV1(BenchmarkV1):
    """benchmark_v1 plus a filter: no setup when the 1h close is more than `max_ext_atr` ATR(1h) from its SMA."""
    name = "benchmark_ext_v1"
    version = "1.0.0"

    def __init__(self, max_ext_atr: float = 2.0, **kw):
        super().__init__(**kw)
        self.max_ext = max_ext_atr

    def evaluate(self, *, as_of: datetime, bias_candles: list[Candle], setup_candles: list[Candle]) -> Evaluation:
        ev = super().evaluate(as_of=as_of, bias_candles=bias_candles, setup_candles=setup_candles)
        if ev.state != SetupState.SETUP_QUALIFIED:
            return ev
        b = [c for c in bias_candles if c.ts_close <= to_utc(as_of)]
        a1 = atr(b, self.atr_period)[-1]
        sm = ev.metrics.get("bias_sma")
        if a1 and sm is not None:
            ext = abs(b[-1].close - sm) / a1
            ev.metrics["bias_ext_atr"] = ext
            if ext > self.max_ext:
                ev.state = SetupState.NO_SETUP
                ev.reasons.append(f"filtered: 1h over-extended ({ext:.2f} ATR from SMA > {self.max_ext})")
                ev.setup = None
        return ev
