"""Yahoo Finance chart v8 for GC=F (COMEX gold futures, front month, last trade).

UNOFFICIAL and undocumented; ~10 minutes delayed; appends a synthetic row at
regularMarketTime (dropped here); pads closed hours with nulls (dropped here).
Verified 16 Oct 2026 (docs/research/data-sources.md). Fallback source only.
"""
from __future__ import annotations

from datetime import datetime, timedelta

import requests

from ..candles import Candle
from ..timeutil import from_epoch, interval_seconds, now_utc, to_utc
from .base import ProviderError

BASE = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) xau-signals/0.1"
_RANGE_FOR = {"1m": "7d", "5m": "60d", "15m": "60d", "1h": "60d", "1d": "2y"}


class YahooProvider:
    name = "yahoo"
    price_scope = "COMEX GC front-month futures, last trade (Yahoo, unofficial, ~10 min delayed; ~$20 over spot) — not spot"

    def __init__(self, session: requests.Session | None = None, timeout: float = 15):
        self._http = session or requests.Session()
        self._timeout = timeout

    def fetch(self, *, symbol: str, interval: str, start: datetime | None = None, end: datetime | None = None, lookback_bars: int | None = None) -> list[Candle]:
        params = {"interval": interval, "includePrePost": "false"}
        if start or end:
            now = now_utc()
            params["period1"] = int(to_utc(start or (now - timedelta(days=5))).timestamp())
            params["period2"] = int(to_utc(end or now).timestamp())
        else:
            params["range"] = _RANGE_FOR.get(interval, "5d") if lookback_bars is None else ("5d" if interval in ("1m", "5m", "15m") else "60d")
        try:
            r = self._http.get(BASE.format(symbol=requests.utils.quote(symbol)), params=params, timeout=self._timeout, headers={"User-Agent": UA})
        except requests.RequestException as e:
            raise ProviderError(f"yahoo request failed: {e.__class__.__name__}") from e
        if r.status_code != 200:
            raise ProviderError(f"yahoo HTTP {r.status_code}: {r.text[:120]}")
        body = r.json()
        res = (body.get("chart") or {}).get("result")
        if not res:
            raise ProviderError(f"yahoo error: {str((body.get('chart') or {}).get('error'))[:160]}")
        res = res[0]
        meta = res.get("meta", {})
        if meta.get("symbol") != symbol:
            raise ProviderError(f"yahoo returned symbol {meta.get('symbol')!r}, asked {symbol!r}")
        rmt = meta.get("regularMarketTime")
        rmt_dt = from_epoch(rmt) if rmt else now_utc()
        step = interval_seconds(interval)
        ts_list = res.get("timestamp") or []
        q = (res.get("indicators") or {}).get("quote") or [{}]
        q = q[0]
        out: list[Candle] = []
        for i, t in enumerate(ts_list):
            if t % step != 0:
                continue   # synthetic regularMarketTime row
            o, h, l, c = (q.get(k, [None])[i] if i < len(q.get(k, [])) else None for k in ("open", "high", "low", "close"))
            if None in (o, h, l, c):
                continue   # null padding during closed hours
            v = q.get("volume", [None])[i] if i < len(q.get("volume", [])) else None
            ts = from_epoch(t)
            complete = ts + timedelta(seconds=step) <= rmt_dt
            out.append(Candle(ts, float(o), float(h), float(l), float(c), float(v) if v is not None else None, interval, symbol, "yahoo", complete))
        if lookback_bars:
            out = out[-lookback_bars:]
        return out
