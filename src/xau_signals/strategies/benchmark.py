"""benchmark_v1: the preserved, deliberately simple baseline.

Bias (1h, completed candles only): close above a rising SMA(20) => UP; below a
falling SMA(20) => DOWN; otherwise NONE.
Setup (5m): a pullback to the EMA(20) in the bias direction, i.e. the last
completed 5m candle touched the EMA (within touch_tolerance_atr * ATR) and closed
back in the bias direction. Then:
  trigger       = that candle's high (UP) / low (DOWN)
  zone          = [EMA - tol*ATR, EMA + tol*ATR]
  invalidation  = that candle's low (UP) / high (DOWN) +- invalidation_buffer_atr*ATR
  expiry        = expiry_bars * 5 minutes after the candle closes
Stale rule: if the latest close is already beyond trigger by more than
stale_extension_atr * ATR, the move has left; state EXPIRED, nothing to send.
This file is frozen as the benchmark. Experiments live in other modules.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from ..candles import Candle
from ..timeutil import interval_seconds, to_utc
from .base import Evaluation, Setup, SetupState, atr, ema, sma


class BenchmarkV1:
    name = "benchmark_v1"
    version = "1.0.0"

    def __init__(self, bias_sma: int = 20, bias_lookback_slope: int = 3, setup_ema: int = 20, atr_period: int = 14,
                 touch_tolerance_atr: float = 0.25, expiry_bars: int = 6, stale_extension_atr: float = 1.0,
                 invalidation_buffer_atr: float = 0.1, **_ignored):
        self.bias_sma = bias_sma
        self.bias_lookback_slope = bias_lookback_slope
        self.setup_ema = setup_ema
        self.atr_period = atr_period
        self.touch_tol = touch_tolerance_atr
        self.expiry_bars = expiry_bars
        self.stale_ext = stale_extension_atr
        self.inv_buf = invalidation_buffer_atr

    # -- bias ------------------------------------------------------------------
    def bias(self, bias_candles: list[Candle]) -> tuple[str, list[str], dict[str, float]]:
        reasons: list[str] = []
        closes = [c.close for c in bias_candles]
        s = sma(closes, self.bias_sma)
        n = len(closes)
        if n < self.bias_sma + self.bias_lookback_slope or s[-1] is None or s[-1 - self.bias_lookback_slope] is None:
            reasons.append(f"bias: need {self.bias_sma + self.bias_lookback_slope} 1h candles, have {n}")
            return "NONE", reasons, {}
        last, prev = s[-1], s[-1 - self.bias_lookback_slope]
        m = {"bias_close": closes[-1], "bias_sma": last, "bias_sma_slope": last - prev}
        if closes[-1] > last and last > prev:
            reasons.append(f"bias UP: 1h close {closes[-1]:.2f} > rising SMA{self.bias_sma} {last:.2f}")
            return "UP", reasons, m
        if closes[-1] < last and last < prev:
            reasons.append(f"bias DOWN: 1h close {closes[-1]:.2f} < falling SMA{self.bias_sma} {last:.2f}")
            return "DOWN", reasons, m
        reasons.append(f"bias NONE: close {closes[-1]:.2f} vs SMA {last:.2f} (slope {last - prev:+.2f})")
        return "NONE", reasons, m

    # -- evaluate ----------------------------------------------------------------
    def evaluate(self, *, as_of: datetime, bias_candles: list[Candle], setup_candles: list[Candle]) -> Evaluation:
        as_of = to_utc(as_of)
        # Only candles completed by as_of may be used (guards replay against look-ahead).
        bias_candles = [c for c in bias_candles if c.ts_close <= as_of]
        setup_candles = [c for c in setup_candles if c.ts_close <= as_of]
        ev = Evaluation(as_of=as_of, bias="NONE", state=SetupState.DATA_UNAVAILABLE)
        if not bias_candles or not setup_candles:
            ev.reasons.append("no completed candles for bias or setup interval")
            return ev
        ev.bias_candle_ts = bias_candles[-1].ts_open
        ev.setup_candle_ts = setup_candles[-1].ts_open

        bias, reasons, metrics = self.bias(bias_candles)
        ev.bias, ev.reasons, ev.metrics = bias, reasons, metrics

        need = max(self.setup_ema, self.atr_period + 1) + 1
        if len(setup_candles) < need:
            ev.state = SetupState.DATA_UNAVAILABLE
            ev.reasons.append(f"setup: need {need} 5m candles, have {len(setup_candles)}")
            return ev
        if bias == "NONE":
            ev.state = SetupState.NO_SETUP
            return ev

        closes = [c.close for c in setup_candles]
        e = ema(closes, self.setup_ema)
        a = atr(setup_candles, self.atr_period)
        last = setup_candles[-1]
        e_last, a_last = e[-1], a[-1]
        if e_last is None or a_last is None or a_last <= 0:
            ev.state = SetupState.DATA_UNAVAILABLE
            ev.reasons.append("setup: indicators not ready")
            return ev
        tol = self.touch_tol * a_last
        ev.metrics.update({"setup_ema": e_last, "setup_atr": a_last, "last_close": last.close})

        touched = (last.low <= e_last + tol) if bias == "UP" else (last.high >= e_last - tol)
        closed_with_bias = last.close > last.open if bias == "UP" else last.close < last.open
        on_right_side = last.close > e_last if bias == "UP" else last.close < e_last

        if not touched:
            # price away from the mean in bias direction: nothing to do yet
            ev.state = SetupState.NO_SETUP
            ev.reasons.append(f"setup: no pullback to EMA{self.setup_ema} ({e_last:.2f}) on last 5m candle")
            return ev
        if touched and not (closed_with_bias and on_right_side):
            ev.state = SetupState.SETUP_FORMING
            ev.reasons.append("setup forming: pullback touched EMA but candle did not close back with the bias")
            return ev

        step = interval_seconds(last.interval)
        if bias == "UP":
            trigger, inval = last.high, last.low - self.inv_buf * a_last
        else:
            trigger, inval = last.low, last.high + self.inv_buf * a_last
        setup = Setup(
            direction=bias,
            setup_type="pullback_continuation",
            anchor_ts=last.ts_open,
            trigger=trigger,
            zone_low=e_last - tol,
            zone_high=e_last + tol,
            invalidation=inval,
            expires_at=last.ts_close + timedelta(seconds=step * self.expiry_bars),
            atr=a_last,
            notes=f"5m pullback to EMA{self.setup_ema} closed {('up' if bias == 'UP' else 'down')}",
        )
        ev.setup = setup
        # stale check against the latest known close
        ext = (last.close - trigger) if bias == "UP" else (trigger - last.close)
        if ext > self.stale_ext * a_last:
            ev.state = SetupState.SETUP_EXPIRED
            ev.reasons.append(f"stale: price already {ext:.2f} beyond trigger (> {self.stale_ext} ATR)")
            return ev
        if as_of > setup.expires_at:
            ev.state = SetupState.SETUP_EXPIRED
            ev.reasons.append("expired: decision time is past the setup expiry")
            return ev
        ev.state = SetupState.SETUP_QUALIFIED
        ev.reasons.append(f"qualified: trigger {trigger:.2f}, invalidation {inval:.2f}, expires {setup.expires_at.isoformat()}")
        return ev
