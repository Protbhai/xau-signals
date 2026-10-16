"""Provider interface. Adapters return raw Candle lists; validation happens in candles.validate."""
from __future__ import annotations

from datetime import datetime
from typing import Protocol


class ProviderError(RuntimeError):
    pass


class Provider(Protocol):
    name: str
    price_scope: str      # human text for the alert, e.g. "COMEX GC front-month futures, last price (Yahoo, unofficial)"

    def fetch(self, *, symbol: str, interval: str, start: datetime | None = None, end: datetime | None = None, lookback_bars: int | None = None) -> list:
        """Return candles (possibly including a forming last one, flagged complete=False)."""
        ...
