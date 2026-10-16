"""Faithful port of the OLD project's technical rules (xauusd-telegram-monitor, public repo,
read 17 Oct 2026) so they can be replayed on the same footing as the new candidates.

Two variants exist in that code base:

old_session_v1  = setup_strategy.assess(): inside 09:00-15:00 IST, direction = context_direction(5m)
                  == context_direction(15m) (EMA20 above/below and slope over 3 bars); structure =
                  technical_evidence(5m, 15m): reference range = bars [-9:-3], breakout bar, retest bar,
                  follow bar with higher low / lower high; pattern must start in the session; then a 1m
                  confirmation: 1m bar closed after the 5m close, no touch of the invalidation since the
                  retest, |1m close - 5m close| <= 0.5 ATR, 1m range <= 3 ATR, continuation (higher low and
                  close above the previous 1m high, above invalidation). Entry = that 1m close
                  (IMMEDIATE). Its own cap was 3/day with a 30-minute cooldown.
old_cloud_v1    = multi_timeframe_evidence(5m, 15m, 1h, 4h): same 5m/15m structure, 1h EMA20 context must
                  agree, 4h EMA20 context must not oppose. No 1m step, no session-start rule. Entry = the
                  follow bar's close (IMMEDIATE). The cloud variant had no cap; the replay applies the
                  shared gate so counts are comparable, and reports uncapped qualified setups too.

NOT portable: the old project's `confirmed_bias()` also required a verified news surprise, a verified
market reaction, acceptable spread and no imminent release. No historical data exists for those, so the
replay assumes those gates OPEN. That is the old design's best case; in production it never fired.
Indicator definitions below copy the old code exactly (EMA seeded with the first value; ATR = simple mean
of the last 14 true ranges over the bars before the pattern).
"""
from __future__ import annotations

from datetime import datetime, time, timedelta

from ..candles import Candle
from ..timeutil import IST, to_utc
from .base import Evaluation, Setup, SetupState


def _ema_old(values: list[float], period: int) -> list[float]:
    result = [values[0]]
    alpha = 2 / (period + 1)
    for v in values[1:]:
        result.append(alpha * v + (1 - alpha) * result[-1])
    return result


def _context_direction(rows: list[Candle]) -> str:
    if len(rows) < 30:
        return "UNVERIFIED"
    closes = [c.close for c in rows]
    avg = _ema_old(closes, 20)
    if closes[-1] > avg[-1] and avg[-1] > avg[-4]:
        return "BUY"
    if closes[-1] < avg[-1] and avg[-1] < avg[-4]:
        return "SELL"
    return "NEUTRAL"


def _atr_old(history: list[Candle]) -> float:
    tr = [max(b.high - b.low, abs(b.high - a.close), abs(b.low - a.close)) for a, b in zip(history, history[1:])]
    return sum(tr[-14:]) / 14 if len(tr) >= 14 else 0.0


def _technical_evidence(five: list[Candle], fifteen: list[Candle]) -> tuple[str, str, float | None, float]:
    """Returns (direction BUY/SELL/NEUTRAL, reason, invalidation, atr)."""
    if len(five) < 30 or len(fifteen) < 30:
        return "NEUTRAL", "Insufficient completed candles.", None, 0.0
    reference = five[-9:-3]
    breakout, retest, follow = five[-3:]
    high = max(b.high for b in reference)
    low = min(b.low for b in reference)
    atr = _atr_old(five[:-3])
    if atr <= 0:
        return "NEUTRAL", "Volatility cannot be verified.", None, 0.0
    if any(b.high - b.low > 3 * atr for b in five[-3:]):
        return "NEUTRAL", "Reaction too volatile.", None, atr
    if high - low < atr:
        return "NEUTRAL", "Reference range too narrow.", None, atr
    buffer = 0.1 * atr
    c15 = [b.close for b in fifteen]
    trend = _ema_old(c15, 20)
    bull15 = c15[-1] > trend[-1] and trend[-1] > trend[-4]
    bear15 = c15[-1] < trend[-1] and trend[-1] < trend[-4]
    bull5 = (breakout.close > high + buffer and high - buffer <= retest.low <= high + 0.25 * atr and retest.close > high
             and follow.low > retest.low and follow.close > max(breakout.close, retest.high) and follow.close - high <= 1.5 * atr)
    bear5 = (breakout.close < low - buffer and low - 0.25 * atr <= retest.high <= low + buffer and retest.close < low
             and follow.high < retest.high and follow.close < min(breakout.close, retest.low) and low - follow.close <= 1.5 * atr)
    if bull15 and bull5:
        return "BUY", "15m trend agrees with 5m breakout, held retest, higher low", retest.low, atr
    if bear15 and bear5:
        return "SELL", "15m trend agrees with 5m breakdown, failed reclaim, lower high", retest.high, atr
    return "NEUTRAL", "No aligned 15m trend and completed 5m retest confirmation.", None, atr


class OldMonitorSessionV1:
    name = "old_session_v1"
    version = "port-1.0"

    def __init__(self, **_):
        pass

    def evaluate(self, *, as_of: datetime, bias_candles: list[Candle], setup_candles: list[Candle], aux=None) -> Evaluation:
        as_of = to_utc(as_of)
        aux = aux or {}
        five = [c for c in setup_candles if c.ts_close <= as_of]
        fifteen = [c for c in aux.get("15m", []) if c.ts_close <= as_of]
        one = [c for c in aux.get("1m", []) if c.ts_close <= as_of]
        ev = Evaluation(as_of=as_of, bias="NONE", state=SetupState.DATA_UNAVAILABLE)
        if len(five) < 30 or len(fifteen) < 30:
            ev.reasons.append("need 30 completed 5m and 15m candles")
            return ev
        ev.setup_candle_ts = five[-1].ts_open
        d5, d15 = _context_direction(five), _context_direction(fifteen)
        if d5 not in ("BUY", "SELL") or d5 != d15:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append(f"DIRECTION_NOT_ALIGNED 5m={d5} 15m={d15}")
            return ev
        direction = "UP" if d5 == "BUY" else "DOWN"
        ev.bias = direction
        sdir, reason, inval, atr = _technical_evidence(five, fifteen)
        if sdir != d5 or inval is None:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append("DIRECTION_ONLY: " + reason)
            return ev
        start = datetime.combine(as_of.astimezone(IST).date(), time(9, 0), IST).astimezone(as_of.tzinfo)
        if five[-3].ts_open < start:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append("PATTERN_STARTED_BEFORE_SESSION")
            return ev
        ev.reasons.append("ENTRY_PENDING: " + reason)
        ev.state = SetupState.SETUP_FORMING
        if not one:
            ev.reasons.append("ENTRY_DATA_UNAVAILABLE (no 1m)")
            return ev
        close5 = five[-1].ts_close
        if one[-1].ts_close <= close5:
            return ev
        prev, last = one[-2], one[-1]
        observed = [b for b in one if b.ts_open >= five[-1].ts_open]
        if (direction == "UP" and any(b.low <= inval for b in observed)) or (direction == "DOWN" and any(b.high >= inval for b in observed)):
            ev.state = SetupState.SETUP_INVALIDATED
            ev.reasons.append("STRUCTURE_INVALIDATED on 1m")
            return ev
        if abs(last.close - five[-1].close) > 0.5 * atr:
            ev.reasons.append("ENTRY_EXTENDED")
            return ev
        if last.high - last.low > 3 * atr:
            ev.reasons.append("ENTRY_SPIKE")
            return ev
        cont = (last.low > prev.low and last.close > prev.high and last.close > inval) if direction == "UP" else \
               (last.high < prev.high and last.close < prev.low and last.close < inval)
        if not cont:
            ev.reasons.append("waiting for 1m continuation")
            return ev
        level = max(b.high for b in five[-9:-3]) if direction == "UP" else min(b.low for b in five[-9:-3])
        setup = Setup(direction, "old_break_retest_1m", five[-3].ts_open, last.close, min(level, last.close), max(level, last.close),
                      inval, five[-1].ts_close + timedelta(minutes=5), atr,
                      notes="old project rules; entry at the confirming 1m close", entry_mode="immediate")
        ev.setup = setup
        ev.state = SetupState.SETUP_QUALIFIED
        ev.reasons.append(f"TECHNICAL_SETUP_CANDIDATE at 1m close {last.close:.2f}, invalidation {inval:.2f}")
        return ev


class OldMonitorCloudV1:
    name = "old_cloud_v1"
    version = "port-1.0"

    def __init__(self, **_):
        pass

    def evaluate(self, *, as_of: datetime, bias_candles: list[Candle], setup_candles: list[Candle], aux=None) -> Evaluation:
        as_of = to_utc(as_of)
        aux = aux or {}
        five = [c for c in setup_candles if c.ts_close <= as_of]
        fifteen = [c for c in aux.get("15m", []) if c.ts_close <= as_of]
        hourly = [c for c in bias_candles if c.ts_close <= as_of]
        four = [c for c in aux.get("4h", []) if c.ts_close <= as_of]
        ev = Evaluation(as_of=as_of, bias="NONE", state=SetupState.DATA_UNAVAILABLE)
        if len(five) < 30 or len(fifteen) < 30:
            ev.reasons.append("need 30 completed 5m and 15m candles")
            return ev
        ev.setup_candle_ts = five[-1].ts_open
        sdir, reason, inval, atr = _technical_evidence(five, fifteen)
        hd, bd = _context_direction(hourly), _context_direction(four)
        if "UNVERIFIED" in (hd, bd):
            ev.reasons.append("Hourly or four-hour context unverified.")
            return ev
        if sdir == "NEUTRAL" or inval is None:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append(reason)
            return ev
        direction = "UP" if sdir == "BUY" else "DOWN"
        ev.bias = direction
        if hd != sdir:
            ev.state = SetupState.NO_SETUP
            ev.reasons.append("Hourly context does not support the 5m/15m setup.")
            return ev
        if bd not in (sdir, "NEUTRAL"):
            ev.state = SetupState.NO_SETUP
            ev.reasons.append("4h trend opposes.")
            return ev
        follow = five[-1]
        level = max(b.high for b in five[-9:-3]) if direction == "UP" else min(b.low for b in five[-9:-3])
        setup = Setup(direction, "old_break_retest_mtf", five[-3].ts_open, follow.close, min(level, follow.close), max(level, follow.close),
                      inval, follow.ts_close + timedelta(minutes=5), atr,
                      notes="old project cloud rules; entry at the follow bar close", entry_mode="immediate")
        ev.setup = setup
        ev.state = SetupState.SETUP_QUALIFIED
        ev.reasons.append(reason + " Hourly agrees; 4h not opposing.")
        return ev
