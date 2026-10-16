"""Forward-outcome measurement for a setup, using only candles AFTER the decision.

Reported per setup:
  triggered_at        first candle (after anchor) whose close crosses the trigger before expiry; None if never
  invalidated_at      first candle whose close crosses the invalidation (before trigger) ; None if never
  expired             no trigger by expires_at
  mfe/mae at horizons measured from the trigger level (not from a fill), in price units and in ATR,
                      at +30m, +60m, +120m after trigger, and at session end (15:00 IST same session date);
                      and separately "after_session" (+120m if it crosses 15:00) so in-sitting results are not
                      conflated with later moves.
  unavailable         candles missing for a horizon -> that horizon is None, never guessed.
These are reference-price excursions. They are NOT trade profits: no fill, spread, slippage or exit rule is assumed.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timedelta

from .candles import Candle
from .session import SessionSpec, session_bounds, session_date
from .strategies.base import Setup
from .timeutil import to_utc

HORIZONS_MIN = (30, 60, 120)


@dataclass
class Excursion:
    horizon: str
    n_candles: int
    mfe: float | None          # max favourable excursion from trigger, price units (>=0)
    mae: float | None          # max adverse excursion from trigger, price units (>=0)
    close_move: float | None   # signed move of last close vs trigger, favourable positive
    complete: bool             # horizon fully covered by candles


@dataclass
class Outcome:
    setup_id: str
    direction: str
    trigger: float
    invalidation: float
    atr: float
    triggered_at: str | None = None
    invalidated_before_trigger_at: str | None = None
    invalidated_after_trigger_at: str | None = None
    expired: bool = False
    data_unavailable: bool = False
    excursions: list[Excursion] = field(default_factory=list)
    within_session_end: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


def _fav(direction: str, price: float, ref: float) -> float:
    return (price - ref) if direction == "UP" else (ref - price)


def _excursion(direction: str, trigger: float, candles: list[Candle], label: str, complete: bool) -> Excursion:
    if not candles:
        return Excursion(label, 0, None, None, None, False)
    if direction == "UP":
        mfe = max(c.high for c in candles) - trigger
        mae = trigger - min(c.low for c in candles)
    else:
        mfe = trigger - min(c.low for c in candles)
        mae = max(c.high for c in candles) - trigger
    return Excursion(label, len(candles), max(mfe, 0.0), max(mae, 0.0), _fav(direction, candles[-1].close, trigger), complete)


def evaluate_outcome(setup: Setup, later: list[Candle], *, spec: SessionSpec = SessionSpec()) -> Outcome:
    """`later` = completed setup-interval candles with ts_open > setup.anchor_ts, ascending."""
    out = Outcome(setup.setup_id, setup.direction, setup.trigger, setup.invalidation, setup.atr)
    later = sorted([c for c in later if c.ts_open > setup.anchor_ts], key=lambda c: c.ts_open)
    if not later:
        out.data_unavailable = True
        return out
    up = setup.direction == "UP"
    trig_i = None
    for i, c in enumerate(later):
        if c.ts_open >= setup.expires_at:
            break
        inval = (c.close < setup.invalidation) if up else (c.close > setup.invalidation)
        trig = (c.close > setup.trigger) if up else (c.close < setup.trigger)
        if inval and trig_i is None:
            out.invalidated_before_trigger_at = c.ts_open.isoformat()
            return out
        if trig:
            trig_i = i
            out.triggered_at = c.ts_open.isoformat()
            break
    if trig_i is None:
        # untriggered: expired only if we actually have candles reaching the expiry
        out.expired = later[-1].ts_close >= setup.expires_at
        out.data_unavailable = not out.expired
        return out

    t0 = later[trig_i].ts_close
    after = later[trig_i + 1:]
    for c in after:
        inval = (c.close < setup.invalidation) if up else (c.close > setup.invalidation)
        if inval:
            out.invalidated_after_trigger_at = c.ts_open.isoformat()
            break
    step = (later[1].ts_open - later[0].ts_open) if len(later) > 1 else timedelta(minutes=5)
    for m in HORIZONS_MIN:
        end = t0 + timedelta(minutes=m)
        win = [c for c in after if c.ts_close <= end]
        complete = bool(win) and win[-1].ts_close >= end - step
        out.excursions.append(_excursion(setup.direction, setup.trigger, win, f"+{m}m", complete))
    _, sess_end = session_bounds(session_date(setup.anchor_ts), spec)
    out.within_session_end = sess_end.isoformat()
    win = [c for c in after if c.ts_close <= sess_end]
    complete = bool(win) and win[-1].ts_close >= sess_end - step
    out.excursions.append(_excursion(setup.direction, setup.trigger, win, "to_15:00_IST", complete))
    return out
