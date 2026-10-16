from datetime import timedelta

from xau_signals.candles import Candle
from xau_signals.outcomes import evaluate_outcome
from xau_signals.strategies import make
from xau_signals.strategies.base import Setup, SetupState
from xau_signals.strategies.old_monitor import _context_direction, _ema_old, _technical_evidence

from conftest import ist


def _c(t, o, h, l, c, iv="5m"):
    return Candle(t, o, h, l, c, 1.0, iv, "XAUUSD", "test")


def _series(start, specs, iv="5m"):
    step = {"1m": 1, "5m": 5, "15m": 15, "1h": 60}[iv]
    out, t = [], start
    for o, h, l, c in specs:
        out.append(_c(t, o, h, l, c, iv)); t += timedelta(minutes=step)
    return out


def test_old_ema_and_context_match_reference_semantics():
    vals = [1.0, 2.0, 3.0]
    e = _ema_old(vals, 20)
    assert e[0] == 1.0 and abs(e[1] - (2 / 21 * 2.0 + 19 / 21 * 1.0)) < 1e-12
    rows = _series(ist(2026, 10, 13, 9, 0), [(100 + i, 101 + i, 99 + i, 100.5 + i) for i in range(40)])
    assert _context_direction(rows) == "BUY"
    assert _context_direction(rows[:10]) == "UNVERIFIED"


def _bull_pattern(start):
    # 27 bars of mild uptrend with ~2.0 ranges (ATR ~2), reference range wide, then breakout/retest/follow
    base = [(2650 + 0.3 * i, 2651.2 + 0.3 * i, 2649.2 + 0.3 * i, 2650.4 + 0.3 * i) for i in range(27)]
    # reference range (bars -9..-3 of the final 5m list) = last 6 of base: highs up to ~2659.0, lows ~2655.5
    hi = max(b[1] for b in base[-6:])
    atr_guess = 2.0
    breakout = (hi - 0.5, hi + 1.6, hi - 0.8, hi + 1.0)              # close > high + 0.1 atr
    retest = (hi + 0.9, hi + 1.2, hi + 0.1, hi + 0.8)                # low within [hi-0.2, hi+0.5], close > hi
    follow = (hi + 0.8, hi + 1.9, hi + 0.4, hi + 1.7)                # higher low, close > max(breakout c, retest h), within 1.5 atr
    return _series(start, base + [breakout, retest, follow]), hi


def test_technical_evidence_bull_pattern_detected():
    start = ist(2026, 10, 13, 9, 0)
    five, hi = _bull_pattern(start)
    fifteen = _series(start - timedelta(hours=8), [(2600 + i, 2601.5 + i, 2599 + i, 2600.8 + i) for i in range(40)], iv="15m")
    d, reason, inval, atr = _technical_evidence(five, fifteen)
    assert d == "BUY" and inval == five[-2].low and atr > 0


def test_old_session_requires_1m_confirmation_and_is_immediate_entry():
    start = ist(2026, 10, 13, 9, 0)
    five, hi = _bull_pattern(start)
    fifteen = _series(start - timedelta(hours=8), [(2600 + i, 2601.5 + i, 2599 + i, 2600.8 + i) for i in range(40)], iv="15m")
    strat = make("old_session_v1", {})
    t = five[-1].ts_close + timedelta(seconds=30)
    ev = strat.evaluate(as_of=t, bias_candles=[], setup_candles=five, aux={"15m": fifteen, "1m": []})
    assert ev.state == SetupState.SETUP_FORMING and ev.bias == "UP"
    fc = five[-1].close
    one = _series(five[-1].ts_open, [(fc - 0.2, fc + 0.1, fc - 0.4, fc - 0.1)] * 5 + [(fc - 0.1, fc + 0.3, fc - 0.2, fc + 0.2), (fc + 0.2, fc + 0.6, fc - 0.1, fc + 0.5)], iv="1m")
    t2 = one[-1].ts_close + timedelta(seconds=10)
    ev2 = strat.evaluate(as_of=t2, bias_candles=[], setup_candles=five, aux={"15m": fifteen, "1m": one})
    assert ev2.state == SetupState.SETUP_QUALIFIED and ev2.setup.entry_mode == "immediate" and ev2.setup.trigger == one[-1].close


def test_immediate_outcome_counts_as_triggered_at_anchor():
    anchor = ist(2026, 10, 13, 10, 25)
    s = Setup("UP", "x", anchor, 2660.0, 2659, 2660, 2655.0, anchor + timedelta(minutes=10), 2.0, entry_mode="immediate")
    later = _series(anchor + timedelta(minutes=5), [(2660, 2662, 2659.5, 2661.5)] * 8)
    o = evaluate_outcome(s, later)
    assert o.triggered_at == anchor.isoformat() and not o.invalidated_after_trigger_at
    h15 = next(e for e in o.excursions if e.horizon == "+15m")
    assert h15.n_candles == 3 and h15.close_move > 0
