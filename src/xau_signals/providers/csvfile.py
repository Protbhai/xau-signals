"""CSV provider: candles from a file (research, replay, tests).

Format: header `ts_open,open,high,low,close,volume`; ts_open is ISO-8601 with
offset (e.g. 2026-10-01T03:30:00+00:00) or epoch seconds. Rows may be in any
order; validation fixes order and drops duplicates.
"""
from __future__ import annotations

import csv
from datetime import datetime
from pathlib import Path

from ..candles import Candle
from ..timeutil import UTC, from_epoch, to_utc


def read_csv(path: str | Path, *, symbol: str, interval: str, source: str = "csv") -> list[Candle]:
    out: list[Candle] = []
    with open(path, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            raw = row["ts_open"].strip()
            if raw.replace(".", "", 1).isdigit():
                ts = from_epoch(float(raw))
            else:
                dt = datetime.fromisoformat(raw.replace("Z", "+00:00"))
                ts = to_utc(dt if dt.tzinfo else dt.replace(tzinfo=UTC))
            vol = row.get("volume")
            out.append(Candle(ts, float(row["open"]), float(row["high"]), float(row["low"]), float(row["close"]),
                              float(vol) if vol not in (None, "", "nan") else None, interval, symbol, source, True))
    return out


def write_csv(path: str | Path, candles: list[Candle]) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["ts_open", "open", "high", "low", "close", "volume"])
        for c in candles:
            w.writerow([c.ts_open.astimezone(UTC).isoformat(), c.open, c.high, c.low, c.close, "" if c.volume is None else c.volume])


class CsvProvider:
    name = "csv"
    price_scope = "historical CSV (research only)"

    def __init__(self, files: dict[str, str | Path], symbol: str, source: str = "csv"):
        self.files = {k: Path(v) for k, v in files.items()}   # interval -> path
        self.symbol = symbol
        self.source = source
        self._cache: dict[str, list[Candle]] = {}

    def fetch(self, *, symbol: str, interval: str, start: datetime | None = None, end: datetime | None = None, lookback_bars: int | None = None) -> list[Candle]:
        if symbol != self.symbol:
            raise ValueError(f"CsvProvider has {self.symbol}, asked for {symbol}")
        if interval not in self._cache:
            self._cache[interval] = sorted(read_csv(self.files[interval], symbol=symbol, interval=interval, source=self.source), key=lambda c: c.ts_open)
        cs = self._cache[interval]
        if start:
            cs = [c for c in cs if c.ts_open >= to_utc(start)]
        if end:
            cs = [c for c in cs if c.ts_open < to_utc(end)]
        if lookback_bars:
            cs = cs[-lookback_bars:]
        return list(cs)
