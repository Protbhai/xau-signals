"""Strategy interface. A strategy sees only completed candles up to decision time."""
from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Protocol

from ..candles import Candle


class SetupState(str, Enum):
    DATA_UNAVAILABLE = "DATA_UNAVAILABLE"   # no usable candles
    DATA_STALE = "DATA_STALE"               # candles exist but are too old to act on
    NO_SETUP = "NO_SETUP"                   # evidence present, no qualifying opportunity
    SETUP_FORMING = "SETUP_FORMING"         # conditions partly met; nothing to act on yet
    SETUP_QUALIFIED = "SETUP_QUALIFIED"     # conditional entry can be stated
    SETUP_INVALIDATED = "SETUP_INVALIDATED" # structure broke
    SETUP_EXPIRED = "SETUP_EXPIRED"         # too old / price already extended


@dataclass(frozen=True)
class Setup:
    direction: str            # "UP" | "DOWN"
    setup_type: str           # e.g. "pullback_continuation"
    anchor_ts: datetime       # open time of the candle that defined the setup (UTC)
    trigger: float            # conditional entry trigger level
    zone_low: float           # reference zone
    zone_high: float
    invalidation: float       # observed structural invalidation level
    expires_at: datetime      # UTC; after this the setup is EXPIRED if untriggered
    atr: float                # setup-interval ATR at anchor, for extension checks
    notes: str = ""

    @property
    def setup_id(self) -> str:
        # Same direction+type anchored on the same candle => same setup (dedup key).
        key = f"{self.direction}|{self.setup_type}|{self.anchor_ts.isoformat()}"
        return hashlib.sha1(key.encode()).hexdigest()[:12]


@dataclass
class Evaluation:
    as_of: datetime                   # decision time (UTC)
    bias: str                         # "UP" | "DOWN" | "NONE"
    state: SetupState
    setup: Setup | None = None
    bias_candle_ts: datetime | None = None
    setup_candle_ts: datetime | None = None
    reasons: list[str] = field(default_factory=list)
    metrics: dict[str, float] = field(default_factory=dict)


class Strategy(Protocol):
    name: str
    version: str

    def evaluate(self, *, as_of: datetime, bias_candles: list[Candle], setup_candles: list[Candle]) -> Evaluation: ...


# ---- small indicator helpers (pure python; no look-ahead by construction) -----

def sma(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    s = 0.0
    for i, v in enumerate(values):
        s += v
        if i >= n:
            s -= values[i - n]
        if i >= n - 1:
            out[i] = s / n
    return out


def ema(values: list[float], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    if len(values) < n:
        return out
    k = 2.0 / (n + 1)
    seed = sum(values[:n]) / n
    out[n - 1] = seed
    prev = seed
    for i in range(n, len(values)):
        prev = values[i] * k + prev * (1 - k)
        out[i] = prev
    return out


def atr(candles: list[Candle], n: int) -> list[float | None]:
    out: list[float | None] = [None] * len(candles)
    if len(candles) < n + 1:
        return out
    trs: list[float] = []
    for i, c in enumerate(candles):
        if i == 0:
            trs.append(c.high - c.low)
        else:
            pc = candles[i - 1].close
            trs.append(max(c.high - c.low, abs(c.high - pc), abs(c.low - pc)))
    # Wilder smoothing
    first = sum(trs[1:n + 1]) / n
    out[n] = first
    prev = first
    for i in range(n + 1, len(candles)):
        prev = (prev * (n - 1) + trs[i]) / n
        out[i] = prev
    return out
