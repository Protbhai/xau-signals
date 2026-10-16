from datetime import date, datetime, timedelta

from xau_signals import market_hours
from xau_signals.session import SessionSpec, in_session, is_trading_session_day, next_session_start, session_bounds, session_date
from xau_signals.timeutil import IST, NY, UTC

from conftest import ist


def test_session_boundaries_inclusive_exclusive():
    assert in_session(ist(2026, 10, 13, 9, 0))
    assert in_session(ist(2026, 10, 13, 14, 59))
    assert not in_session(ist(2026, 10, 13, 15, 0))
    assert not in_session(ist(2026, 10, 13, 8, 59))


def test_session_date_is_ist_date():
    # 20:30 UTC on 13 Oct is 02:00 IST on 14 Oct
    assert session_date(datetime(2026, 10, 13, 20, 30, tzinfo=UTC)) == date(2026, 10, 14)


def test_session_bounds_utc():
    s, e = session_bounds(date(2026, 10, 13))
    assert s == datetime(2026, 10, 13, 3, 30, tzinfo=UTC) and e == datetime(2026, 10, 13, 9, 30, tzinfo=UTC)


def test_market_closed_weekend_and_break():
    # Saturday 12:00 IST
    assert market_hours.is_closed(ist(2026, 10, 10, 12, 0))
    # Friday 17:30 New York (after weekly close)
    assert market_hours.is_closed(datetime(2026, 10, 9, 17, 30, tzinfo=NY))
    # Sunday 17:59 NY closed, 18:00 NY open
    assert market_hours.is_closed(datetime(2026, 10, 11, 17, 59, tzinfo=NY))
    assert not market_hours.is_closed(datetime(2026, 10, 11, 18, 0, tzinfo=NY))
    # Tuesday daily break
    assert market_hours.is_closed(datetime(2026, 10, 13, 17, 30, tzinfo=NY))
    assert not market_hours.is_closed(datetime(2026, 10, 13, 16, 59, tzinfo=NY))
    # Listed closure
    assert market_hours.is_closed(datetime(2026, 12, 25, 12, 0, tzinfo=UTC))


def test_ist_session_never_hits_daily_break():
    # 09:00-15:00 IST = 03:30-09:30 UTC = 23:30-05:30 NY: open on weekdays
    for d in (13, 14, 15, 16):
        assert is_trading_session_day(date(2026, 10, d))
    assert not is_trading_session_day(date(2026, 10, 10))   # Saturday
    assert not is_trading_session_day(date(2026, 10, 11))   # Sunday: opens 18:00 NY = 03:30 IST Monday
    assert not is_trading_session_day(date(2026, 12, 25))


def test_next_session_start_skips_weekend():
    nxt = next_session_start(ist(2026, 10, 16, 16, 0))       # Friday afternoon
    assert nxt == session_bounds(date(2026, 10, 19))[0]      # Monday


def test_custom_spec():
    spec = SessionSpec.from_strings("10:00", "12:00")
    assert in_session(ist(2026, 10, 13, 10, 0), spec) and not in_session(ist(2026, 10, 13, 12, 0), spec)
