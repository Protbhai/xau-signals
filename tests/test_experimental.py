from datetime import timedelta

from xau_signals.candles import Candle
from xau_signals.strategies import BenchmarkExtV1, BreakoutRetestV1, RangeRejectionV1, make
from xau_signals.strategies.base import SetupState

from conftest import ist, trending_1h, trending_pullback_5m


def _bars(start, specs):
    """specs: list of (open, high, low, close) -> 5m candles from start."""
    out, t = [], start
    for o, h, l, c in specs:
        out.append(Candle(t, o, h, l, c, 1.0, "5m", "XAUUSD", "test"))
        t += timedelta(minutes=5)
    return out


def test_registry_builds_all():
    for n in ("benchmark_v1", "breakout_retest_v1", "range_rejection_v1", "benchmark_ext_v1"):
        assert make(n, {}).name == n


def test_breakout_retest_qualifies_after_held_retest():
    start = ist(2026, 10, 13, 9, 0)
    # 18 range bars (90 min) oscillating 2650-2660, then breakout above 2660, then retest that holds
    rng = [(2655, 2660, 2650, 2655 + (1 if i % 2 else -1)) for i in range(18)]
    bo = [(2656, 2663, 2655, 2662.5)]                   # close above 2660
    hold = [(2662.5, 2663.5, 2660.3, 2662.9)]           # retest: low within tol of 2660, closes up
    s = _bars(start, rng + bo + hold)
    # ATR needs 15 bars: fine (20 bars). Decision right after the retest candle closes.
    as_of = s[-1].ts_close + timedelta(seconds=10)
    ev = BreakoutRetestV1(min_range_atr=0.5).evaluate(as_of=as_of, bias_candles=[], setup_candles=s)
    assert ev.state == SetupState.SETUP_QUALIFIED and ev.setup.direction == "UP"
    assert ev.setup.trigger == 2663.5 and ev.setup.invalidation < 2660
    # Before the range is complete: NO_SETUP with a forming-range reason
    ev0 = BreakoutRetestV1().evaluate(as_of=start + timedelta(minutes=70), bias_candles=[], setup_candles=s[:14])
    assert ev0.state in (SetupState.NO_SETUP, SetupState.DATA_UNAVAILABLE)


def test_breakout_invalidated_by_close_back_inside():
    start = ist(2026, 10, 13, 9, 0)
    rng = [(2655, 2660, 2650, 2655 + (1 if i % 2 else -1)) for i in range(18)]
    bo = [(2656, 2663, 2655, 2662.5)]
    fail = [(2662.5, 2662.8, 2655, 2656)]               # closes well back inside
    s = _bars(start, rng + bo + fail)
    ev = BreakoutRetestV1(min_range_atr=0.5).evaluate(as_of=s[-1].ts_close + timedelta(seconds=10), bias_candles=[], setup_candles=s)
    assert ev.state == SetupState.SETUP_INVALIDATED


def test_range_rejection_qualifies_on_wick_rejection():
    start = ist(2026, 10, 13, 9, 0)
    # flat 1h: closes around 2655 with tiny slope => ranging
    b = [Candle(start - timedelta(hours=40 - i), 2655, 2657, 2653, 2655 + 0.2 * ((i % 3) - 1), 1, "1h", "XAUUSD", "test") for i in range(40)]
    flat = [(2655, 2658, 2652, 2655 + (0.5 if i % 2 else -0.5)) for i in range(40)]
    reject = [(2656, 2661.5, 2655.5, 2656.2)]             # pokes above 2658, closes back inside, big upper wick
    s = _bars(start, flat + reject)
    ev = RangeRejectionV1().evaluate(as_of=s[-1].ts_close + timedelta(seconds=10), bias_candles=b, setup_candles=s)
    assert ev.state == SetupState.SETUP_QUALIFIED and ev.setup.direction == "DOWN"
    assert ev.setup.invalidation > 2661.5 and ev.setup.trigger == 2656


def test_range_rejection_refuses_when_1h_trending():
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=True)
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=True)
    ev = RangeRejectionV1().evaluate(as_of=anchor + timedelta(minutes=5), bias_candles=b, setup_candles=s)
    assert ev.state == SetupState.NO_SETUP and "not ranging" in " ".join(ev.reasons)


def test_benchmark_ext_filters_overextended():
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=True)
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=True)
    base = BenchmarkExtV1(max_ext_atr=100).evaluate(as_of=anchor + timedelta(minutes=5), bias_candles=b, setup_candles=s)
    assert base.state == SetupState.SETUP_QUALIFIED
    strict = BenchmarkExtV1(max_ext_atr=0.01).evaluate(as_of=anchor + timedelta(minutes=5), bias_candles=b, setup_candles=s)
    assert strict.state == SetupState.NO_SETUP and strict.setup is None and "filtered" in " ".join(strict.reasons)
