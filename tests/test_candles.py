from datetime import timedelta

import pytest

from xau_signals.candles import Candle, CandleValidationError, validate
from xau_signals.timeutil import UTC

from conftest import ist, make_candles


def test_clean_series_passes():
    start = ist(2026, 10, 13, 9, 0)
    cs = make_candles(start, 50, "5m")
    now = cs[-1].ts_close + timedelta(seconds=30)
    out, rep = validate(cs, symbol="XAUUSD", interval="5m", now=now, max_age_seconds=900)
    assert rep.ok and rep.n_out == 50 and rep.fresh is True and not rep.unexplained_gaps


def test_symbol_mismatch_raises():
    cs = make_candles(ist(2026, 10, 13, 9, 0), 5, "5m", symbol="GC=F")
    with pytest.raises(CandleValidationError):
        validate(cs, symbol="XAUUSD", interval="5m", now=cs[-1].ts_close + timedelta(minutes=1))


def test_nonfinite_and_inverted_dropped():
    cs = make_candles(ist(2026, 10, 13, 9, 0), 5, "5m")
    bad1 = Candle(cs[2].ts_open, float("nan"), 1, 1, 1, None, "5m", "XAUUSD", "test")
    bad2 = Candle(cs[3].ts_open, 2650, 2640, 2660, 2650, None, "5m", "XAUUSD", "test")   # low > high
    cs2 = [cs[0], cs[1], bad1, bad2, cs[4]]
    out, rep = validate(cs2, symbol="XAUUSD", interval="5m", now=cs[4].ts_close + timedelta(minutes=1))
    assert rep.dropped_nonfinite == 2 and rep.n_out == 3


def test_future_and_forming_dropped():
    cs = make_candles(ist(2026, 10, 13, 9, 0), 10, "5m")
    now = cs[-2].ts_close + timedelta(seconds=10)          # last candle still forming; one more is in the future
    future = Candle(cs[-1].ts_open + timedelta(minutes=5), 1, 2, 0.5, 1, None, "5m", "XAUUSD", "test")
    out, rep = validate(cs + [future], symbol="XAUUSD", interval="5m", now=now)
    assert rep.dropped_future == 1 and rep.dropped_forming == 1 and out[-1].ts_open == cs[-2].ts_open


def test_duplicates_and_order():
    cs = make_candles(ist(2026, 10, 13, 9, 0), 6, "5m")
    shuffled = [cs[3], cs[0], cs[1], cs[1], cs[2], cs[5], cs[4]]
    out, rep = validate(shuffled, symbol="XAUUSD", interval="5m", now=cs[-1].ts_close + timedelta(minutes=1))
    assert rep.reordered and rep.dropped_duplicates == 1 and [c.ts_open for c in out] == [c.ts_open for c in cs]


def test_conflicting_duplicate_is_error():
    cs = make_candles(ist(2026, 10, 13, 9, 0), 3, "5m")
    dup = Candle(cs[1].ts_open, cs[1].open, cs[1].high + 5, cs[1].low, cs[1].close, None, "5m", "XAUUSD", "test")
    out, rep = validate(cs + [dup], symbol="XAUUSD", interval="5m", now=cs[-1].ts_close + timedelta(minutes=1))
    assert not rep.ok and any("conflicting" in e for e in rep.errors)


def test_unexplained_gap_flagged_but_weekend_gap_expected():
    # Friday 20:50 NY -> Sunday 18:00 NY is a legitimate closure.
    cs = make_candles(ist(2026, 10, 9, 20, 0), 400, "5m")   # spans a weekend because closed times are skipped
    now = cs[-1].ts_close + timedelta(minutes=1)
    out, rep = validate(cs, symbol="XAUUSD", interval="5m", now=now)
    assert rep.expected_gaps and not rep.unexplained_gaps
    # Now remove 3 candles mid-session: unexplained.
    broken = cs[:100] + cs[103:]
    out, rep = validate(broken, symbol="XAUUSD", interval="5m", now=now, max_unexplained_gap_bars=1)
    assert len(rep.unexplained_gaps) == 1 and rep.unexplained_gaps[0][2] == 3 and not rep.ok


def test_stale_data_not_fresh_when_market_open():
    cs = make_candles(ist(2026, 10, 13, 9, 0), 20, "5m")
    now = cs[-1].ts_close + timedelta(minutes=40)
    out, rep = validate(cs, symbol="XAUUSD", interval="5m", now=now, max_age_seconds=900)
    assert rep.fresh is False


def test_old_data_is_fresh_enough_when_market_closed():
    # Saturday: market closed, last candle is Friday's close; not "stale" in the alarming sense.
    cs = make_candles(ist(2026, 10, 10, 1, 0), 20, "5m")   # Sat 01:00 IST = Fri 15:30 NY, before close
    now = ist(2026, 10, 10, 12, 0)                         # Sat noon IST: closed
    out, rep = validate(cs, symbol="XAUUSD", interval="5m", now=now, max_age_seconds=900)
    assert rep.fresh is True
