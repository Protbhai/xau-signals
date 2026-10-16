"""Twelve Data time_series for XAU/USD (vendor-aggregated spot). NEEDS a free API key
(env XAU_TWELVEDATA_KEY). UNVERIFIED on the free plan as of 16 Oct 2026: whether
XAU/USD is served and how candles are stamped. Docs say candle datetime is the bar
open in the requested timezone; we request UTC.
"""
from __future__ import annotations

import os
from datetime import datetime, timedelta

import requests

from ..candles import Candle
from ..timeutil import UTC, interval_seconds, now_utc, to_utc
from .base import ProviderError

BASE = "https://api.twelvedata.com/time_series"
_IV = {"1m": "1min", "5m": "5min", "15m": "15min", "1h": "1h", "1d": "1day"}


class TwelveDataProvider:
    name = "twelvedata"
    price_scope = "Twelve Data XAU/USD spot (vendor-aggregated, no bid/ask) — not a broker price"

    def __init__(self, api_key: str | None = None, session: requests.Session | None = None, timeout: float = 15):
        self._key = api_key or os.environ.get("XAU_TWELVEDATA_KEY")
        if not self._key:
            raise ProviderError("XAU_TWELVEDATA_KEY not set")
        self._http = session or requests.Session()
        self._timeout = timeout

    def fetch(self, *, symbol: str, interval: str, start: datetime | None = None, end: datetime | None = None, lookback_bars: int | None = None) -> list[Candle]:
        params = {"symbol": symbol, "interval": _IV[interval], "timezone": "UTC", "format": "JSON", "apikey": self._key,
                  "outputsize": min(5000, lookback_bars or 300)}
        if start:
            params["start_date"] = to_utc(start).strftime("%Y-%m-%d %H:%M:%S")
        if end:
            params["end_date"] = to_utc(end).strftime("%Y-%m-%d %H:%M:%S")
        try:
            r = self._http.get(BASE, params=params, timeout=self._timeout)
        except requests.RequestException as e:
            raise ProviderError(f"twelvedata request failed: {e.__class__.__name__}") from e
        body = r.json()
        if body.get("status") == "error" or "values" not in body:
            raise ProviderError(f"twelvedata error: {str(body.get('message') or body)[:160]}")
        step = interval_seconds(interval)
        now = now_utc()
        out = []
        for v in reversed(body["values"]):
            ts = datetime.strptime(v["datetime"], "%Y-%m-%d %H:%M:%S" if len(v["datetime"]) > 10 else "%Y-%m-%d").replace(tzinfo=UTC)
            complete = ts + timedelta(seconds=step) <= now
            out.append(Candle(ts, float(v["open"]), float(v["high"]), float(v["low"]), float(v["close"]),
                              float(v["volume"]) if v.get("volume") not in (None, "") else None, interval, symbol, "twelvedata", complete))
        return out
