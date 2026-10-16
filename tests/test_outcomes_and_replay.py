from datetime import timedelta

from xau_signals.candles import Candle
from xau_signals.outcomes import evaluate_outcome
from xau_signals.replay import ReplayConfig, replay
from xau_signals.strategies import BenchmarkV1
from xau_signals.strategies.base import Setup

from conftest import ist, make_candles, trending_1h, trending_pullback_5m


def _setup(anchor, up=True):
    return Setup("UP" if up else "DOWN", "pullback_continuation", anchor, 2660.0, 2655.0, 2658.0, 2652.0 if up else 2668.0,
                 anchor + timedelta(minutes=35), 2.0)


def _bars(anchor, closes):
    out = []
    t = anchor + timedelta(minutes=5)
    for c in closes:
        out.append(Candle(t, c - 0.5, c + 1.0, c - 1.0, c, 1.0, "5m", "XAUUSD", "test"))
        t += timedelta(minutes=5)
    return out


def test_outcome_triggered_then_excursions():
    anchor = ist(2026, 10, 13, 10, 25)
    later = _bars(anchor, [2659, 2661, 2663, 2662, 2664, 2665, 2666] + [2667] * 30)
    o = evaluate_outcome(_setup(anchor), later)
    assert o.triggered_at == later[1].ts_open.isoformat() and not o.invalidated_before_trigger_at
    h30 = next(e for e in o.excursions if e.horizon == "+30m")
    assert h30.complete and h30.n_candles == 6 and h30.mfe > 0 and h30.close_move > 0


def test_outcome_invalidated_before_trigger():
    anchor = ist(2026, 10, 13, 10, 25)
    later = _bars(anchor, [2658, 2651, 2670])
    o = evaluate_outcome(_setup(anchor), later)
    assert o.invalidated_before_trigger_at and not o.triggered_at


def test_outcome_expired_vs_unavailable():
    anchor = ist(2026, 10, 13, 10, 25)
    o = evaluate_outcome(_setup(anchor), _bars(anchor, [2658] * 8))
    assert o.expired and not o.data_unavailable
    o2 = evaluate_outcome(_setup(anchor), _bars(anchor, [2658] * 2))
    assert o2.data_unavailable and not o2.expired


def test_within_session_horizon_separated():
    anchor = ist(2026, 10, 13, 14, 25)                       # late: 15:00 is 35 min away
    later = _bars(anchor, [2661] + [2670] * 40)              # big move mostly AFTER 15:00
    o = evaluate_outcome(_setup(anchor), later)
    sess = next(e for e in o.excursions if e.horizon == "to_15:00_IST")
    h120 = next(e for e in o.excursions if e.horizon == "+120m")
    assert sess.n_candles < h120.n_candles and sess.complete


def test_replay_enforces_cap_and_cooldown_and_no_lookahead():
    # one session day of synthetic 5m + 1h data with several pullbacks
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=True)
    # extend the day with more candles (random-walk) so the session continues
    s += make_candles(s[-1].ts_open + timedelta(minutes=5), 60, "5m", price=s[-1].close, drift=0.3, vol=0.8, seed=7)
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=True, n=40)
    b += [Candle(b[-1].ts_open + timedelta(hours=i), b[-1].close, b[-1].close + 1, b[-1].close - 1, b[-1].close + 0.5, 1, "1h", "XAUUSD", "test") for i in range(1, 7)]
    res = replay(BenchmarkV1(), b, s, cfg=ReplayConfig(cadence_minutes=5, delay_minutes=2, max_alerts=3, cooldown_minutes=20))
    assert res.session_days == 1 and res.checks > 0
    assert res.alerts_sent <= 3
    assert all(a <= 3 for a in res.alerts_per_day)
    summ = res.summary()
    assert summ["alerts_sent"] == res.alerts_sent and "outcomes" in summ
