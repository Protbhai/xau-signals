"""Replay backtest: run the real engine over history at a simulated check cadence.

No look-ahead: at each decision time `t` the strategy receives only candles whose
close time <= t (enforced again inside the strategy). The scheduler jitter is
modelled explicitly: checks happen at every `cadence` minutes plus `delay`
minutes (e.g. 5 + 7 = a GitHub-Actions-like lag). Outcomes use later candles and
are reported separately for within-session (to 15:00 IST) and fixed horizons.
"""
from __future__ import annotations

import statistics
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Any

from .candles import Candle, validate
from .notify import gate
from .outcomes import Outcome, evaluate_outcome
from .session import SessionSpec, is_trading_session_day, session_bounds
from .state import AlertRecord, SessionState
from .strategies.base import SetupState, Strategy
from .timeutil import IST, to_utc


@dataclass
class ReplayConfig:
    cadence_minutes: int = 5
    delay_minutes: float = 0.0          # scheduler lag applied to every check
    max_alerts: int = 3
    cooldown_minutes: int = 20
    spec: SessionSpec = field(default_factory=SessionSpec)
    stale_ext_atr: float = 1.0


@dataclass
class ReplayResult:
    strategy: str
    config: ReplayConfig
    session_days: int = 0
    checks: int = 0
    states: dict[str, int] = field(default_factory=dict)
    qualified_seen: int = 0            # distinct qualified setup_ids observed
    alerts_sent: int = 0
    blocked: dict[str, int] = field(default_factory=dict)
    alerts_per_day: list[int] = field(default_factory=list)
    outcomes: list[Outcome] = field(default_factory=list)
    alerts: list[dict[str, Any]] = field(default_factory=list)

    def summary(self) -> dict[str, Any]:
        n = len(self.outcomes)
        trig = [o for o in self.outcomes if o.triggered_at]
        inv_b = sum(1 for o in self.outcomes if o.invalidated_before_trigger_at)
        inv_a = sum(1 for o in trig if o.invalidated_after_trigger_at)
        exp = sum(1 for o in self.outcomes if o.expired)
        unav = sum(1 for o in self.outcomes if o.data_unavailable)

        def hz(label: str) -> dict[str, Any]:
            ex = [e for o in trig for e in o.excursions if e.horizon == label and e.complete]
            if not ex:
                return {"n": 0}
            fav = sum(1 for e in ex if (e.close_move or 0) > 0)
            adv = sum(1 for e in ex if (e.close_move or 0) < 0)
            flat = len(ex) - fav - adv
            atrs = {o.setup_id: o.atr for o in trig}
            return {"n": len(ex), "favourable": fav, "adverse": adv, "flat": flat,
                    "median_close_move": round(statistics.median(e.close_move for e in ex), 2),
                    "median_mfe": round(statistics.median(e.mfe for e in ex), 2),
                    "median_mae": round(statistics.median(e.mae for e in ex), 2),
                    "incomplete": sum(1 for o in trig for e in o.excursions if e.horizon == label and not e.complete)}

        return {
            "strategy": self.strategy,
            "cadence_min": self.config.cadence_minutes, "delay_min": self.config.delay_minutes,
            "session_days": self.session_days, "checks": self.checks, "states": self.states,
            "distinct_qualified_setups": self.qualified_seen, "alerts_sent": self.alerts_sent,
            "alerts_per_day_mean": round(statistics.mean(self.alerts_per_day), 2) if self.alerts_per_day else 0,
            "days_with_0_alerts": sum(1 for a in self.alerts_per_day if a == 0),
            "days_with_3_alerts": sum(1 for a in self.alerts_per_day if a >= 3),
            "blocked": self.blocked,
            "outcomes": {"n": n, "triggered": len(trig), "invalidated_before_trigger": inv_b, "expired_untriggered": exp,
                         "unavailable": unav, "invalidated_after_trigger": inv_a,
                         "+15m": hz("+15m"), "+30m": hz("+30m"), "+60m": hz("+60m"), "+120m": hz("+120m"), "to_15:00_IST": hz("to_15:00_IST")},
        }


def _decision_times(d: date, cfg: ReplayConfig) -> list[datetime]:
    start, end = session_bounds(d, cfg.spec)
    t = start
    out = []
    while t < end:
        out.append(t + timedelta(minutes=cfg.delay_minutes))
        t += timedelta(minutes=cfg.cadence_minutes)
    return [x for x in out if x < end]   # a delayed check that lands after 15:00 is not a session check


def replay(strategy: Strategy, bias_candles: list[Candle], setup_candles: list[Candle], *, cfg: ReplayConfig,
           start: date | None = None, end: date | None = None, bias_lookback: int = 60, setup_lookback: int = 150,
           aux: dict[str, list[Candle]] | None = None, aux_lookback: int = 400) -> ReplayResult:
    """aux: extra completed-candle series (e.g. {"15m": [...], "1m": [...], "4h": [...]}) sliced by close time <= t."""
    res = ReplayResult(strategy=f"{strategy.name}@{strategy.version}", config=cfg)
    setup_candles = sorted(setup_candles, key=lambda c: c.ts_open)
    bias_candles = sorted(bias_candles, key=lambda c: c.ts_open)
    aux = {k: sorted(v, key=lambda c: c.ts_open) for k, v in (aux or {}).items()}
    aux_i = {k: 0 for k in aux}
    if not setup_candles:
        return res
    d0 = start or setup_candles[0].ts_open.astimezone(IST).date()
    d1 = end or setup_candles[-1].ts_open.astimezone(IST).date()
    d = d0
    bi = si = 0
    while d <= d1:
        if not is_trading_session_day(d, cfg.spec):
            d += timedelta(days=1)
            continue
        sess = SessionState(session_date=d.isoformat())
        day_alerts = 0
        day_had_data = False
        for t in _decision_times(d, cfg):
            # advance pointers: candles completed by t
            while bi < len(bias_candles) and bias_candles[bi].ts_close <= t:
                bi += 1
            while si < len(setup_candles) and setup_candles[si].ts_close <= t:
                si += 1
            b = bias_candles[max(0, bi - bias_lookback):bi]
            s = setup_candles[max(0, si - setup_lookback):si]
            if not s:
                continue
            aux_now = {}
            for k, series in aux.items():
                j = aux_i[k]
                while j < len(series) and series[j].ts_close <= t:
                    j += 1
                aux_i[k] = j
                aux_now[k] = series[max(0, j - aux_lookback):j]
            day_had_data = True
            res.checks += 1
            _, rep = validate(s, symbol=s[-1].symbol, interval=s[-1].interval, now=t, max_age_seconds=900, max_unexplained_gap_bars=1)
            fresh = bool(rep.fresh)
            ev = strategy.evaluate(as_of=t, bias_candles=b, setup_candles=s, aux=aux_now)
            res.states[ev.state.value] = res.states.get(ev.state.value, 0) + 1
            if ev.state != SetupState.SETUP_QUALIFIED or ev.setup is None:
                continue
            sid = ev.setup.setup_id
            if sid not in sess.seen_setup_ids:
                sess.seen_setup_ids.append(sid)
                res.qualified_seen += 1
            g = gate.check(now=t, sess=sess, setup_id=sid, spec=cfg.spec, max_alerts=cfg.max_alerts,
                           cooldown=timedelta(minutes=cfg.cooldown_minutes), data_fresh=fresh)
            if not g.allowed:
                key = g.reason.split(":")[0]
                res.blocked[key] = res.blocked.get(key, 0) + 1
                continue
            sess.alerts.append(AlertRecord(sid, "sent", t.isoformat(), ev.setup.direction, ev.setup.setup_type, sent_at=t.isoformat()))
            sess.last_sent_at = t.isoformat()
            res.alerts_sent += 1
            day_alerts += 1
            later = [c for c in setup_candles if c.ts_open > ev.setup.anchor_ts and c.ts_open < to_utc(datetime.combine(d, cfg.spec.end, IST)) + timedelta(hours=3)]
            oc = evaluate_outcome(ev.setup, later, spec=cfg.spec)
            res.outcomes.append(oc)
            res.alerts.append({"day": d.isoformat(), "decision_ist": t.astimezone(IST).strftime("%H:%M"), "direction": ev.setup.direction, "entry_mode": ev.setup.entry_mode,
                               "trigger": ev.setup.trigger, "invalidation": ev.setup.invalidation, "atr": round(ev.setup.atr, 2),
                               "alert_age_min": round((t - ev.setup.anchor_ts).total_seconds() / 60 - 5, 1),
                               "outcome": oc.to_dict()})
        if day_had_data:
            res.session_days += 1
            res.alerts_per_day.append(day_alerts)
        d += timedelta(days=1)
    return res
