"""Download research history to data/raw (never committed).

  python research/fetch_history.py binance   -> XAUUSDT 1m since 2025-12-11, then 5m/1h resampled
  python research/fetch_history.py dukascopy START END  -> spot BID 1m for the date range (slow, throttled)
  python research/fetch_history.py yahoo     -> GC=F 5m/1h, ~60 days, cross-check only
"""
from __future__ import annotations

import sys
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_signals import market_hours  # noqa: E402
from xau_signals.providers.csvfile import write_csv  # noqa: E402
from xau_signals.resample import resample  # noqa: E402
from xau_signals.timeutil import UTC  # noqa: E402

market_hours.load_closures(ROOT / "config" / "closures.json")
RAW = ROOT / "data" / "raw"


def binance():
    from xau_signals.providers.binance import BinanceProvider
    p = BinanceProvider(throttle_seconds=0.4)
    start = datetime(2025, 12, 11, tzinfo=UTC)
    cs = p.fetch(symbol="XAUUSDT", interval="1m", start=start)
    cs = [c for c in cs if c.complete]
    write_csv(RAW / "binance_XAUUSDT_1m.csv", cs)
    print("1m", len(cs), cs[0].ts_open, cs[-1].ts_open)
    for iv in ("5m", "15m", "1h"):
        bars, partial = resample(cs, iv)
        write_csv(RAW / f"binance_XAUUSDT_{iv}.csv", bars)
        print(iv, len(bars), "partial", partial)


def dukascopy(start: str, end: str):
    from xau_signals.providers.dukascopy import download_range
    s, e = date.fromisoformat(start), date.fromisoformat(end)
    cs = download_range(s, e, pause=4.0, cache_dir=RAW / "dukascopy")
    write_csv(RAW / "dukascopy_XAUUSD_bid_1m.csv", cs)
    print("1m", len(cs))
    for iv in ("5m", "15m", "1h"):
        bars, partial = resample(cs, iv)
        write_csv(RAW / f"dukascopy_XAUUSD_bid_{iv}.csv", bars)
        print(iv, len(bars), "partial", partial)


def yahoo():
    from xau_signals.providers.yahoo import YahooProvider
    p = YahooProvider()
    for iv in ("5m", "1h"):
        cs = [c for c in p.fetch(symbol="GC=F", interval=iv) if c.complete]
        write_csv(RAW / f"yahoo_GCF_{iv}.csv", cs)
        print(iv, len(cs), cs[0].ts_open if cs else None, cs[-1].ts_open if cs else None)


if __name__ == "__main__":
    cmd = sys.argv[1]
    if cmd == "binance":
        binance()
    elif cmd == "dukascopy":
        dukascopy(sys.argv[2], sys.argv[3])
    elif cmd == "yahoo":
        yahoo()
    else:
        raise SystemExit(__doc__)
