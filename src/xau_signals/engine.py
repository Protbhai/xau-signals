"""One check run: fetch -> validate -> evaluate -> gate -> deliver -> record.

The same function serves paper mode, live mode and replay (via injected provider,
sender, store and clock), so the backtest exercises the real cap/dedup/gate code.
"""
from __future__ import annotations

import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Any

from . import market_hours, messages
from .candles import CandleValidationError, validate
from .config import Settings
from .log import redact
from .notify import gate
from .notify.telegram import DeliveryResult, PaperSender, Sender
from .providers.base import Provider, ProviderError
from .session import SessionSpec, in_session, session_date
from .state import AlertRecord, StateStore, iso
from .strategies import make as make_strategy
from .strategies.base import Evaluation, SetupState
from .timeutil import interval_seconds, now_utc, to_utc
from .tracking import Tracker

log = logging.getLogger("xau.engine")


@dataclass
class RunSummary:
    run_id: str
    started_at: datetime
    in_session: bool
    fetched: bool
    state: str
    bias: str
    alert_action: str                 # none | blocked:<reason> | sent | ambiguous | failed | paper
    delivery: DeliveryResult | None = None
    validation: dict[str, str] = field(default_factory=dict)
    notes: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        d = {"run_id": self.run_id, "started_at": iso(self.started_at), "in_session": self.in_session, "fetched": self.fetched,
             "state": self.state, "bias": self.bias, "alert_action": self.alert_action, "validation": self.validation, "notes": self.notes}
        if self.delivery:
            d["delivery"] = {"status": self.delivery.status, "message_id": self.delivery.message_id, "http": self.delivery.http_status,
                             "error": redact(self.delivery.error or "") or None, "attempts": self.delivery.attempts, "elapsed_s": round(self.delivery.elapsed_seconds, 2)}
        return d


def _lookback_bars(strategy_params: dict[str, Any]) -> tuple[int, int]:
    bias_need = int(strategy_params.get("bias_sma", 20)) + int(strategy_params.get("bias_lookback_slope", 3)) + 10
    setup_need = max(int(strategy_params.get("setup_ema", 20)), int(strategy_params.get("atr_period", 14)) + 1) + 40
    return bias_need, setup_need


def run_once(
    settings: Settings,
    *,
    provider: Provider,
    sender: Sender | None,
    store: StateStore,
    tracker: Tracker,
    now: datetime | None = None,
    force_fetch: bool = False,
    strategy=None,
) -> RunSummary:
    injected_clock = now is not None          # replay/tests inject time; live runs use a fresh clock at the gate
    now = to_utc(now or now_utc())
    run_id = uuid.uuid4().hex[:10]
    spec = SessionSpec.from_strings(settings.get("session", "start", "09:00"), settings.get("session", "end", "15:00"))
    cap = int(settings.get("session", "max_alerts_per_session", 3))
    cooldown = timedelta(minutes=int(settings.get("session", "cooldown_minutes", 20)))
    sname = settings.get("strategy", "name", "benchmark_v1")
    sparams = settings.raw.get("strategy", {}).get(sname, {})
    strat = strategy or make_strategy(sname, sparams)
    symbol = settings.raw["data"].get("symbols", {}).get(provider.name) or settings.get("data", "symbol")
    bias_iv = settings.get("data", "bias_interval", "1h")
    setup_iv = settings.get("data", "setup_interval", "5m")
    max_age = float(settings.get("data", "max_candle_age_seconds", 900))
    max_gap = int(settings.get("data", "max_unexplained_gap_bars", 1))
    fail_after = int(settings.get("notify", "failure_alert_after_consecutive_data_failures", 3))

    sd = session_date(now)
    insess = in_session(now, spec)
    summary = RunSummary(run_id, now, insess, False, "SKIPPED", "NONE", "none")

    with store.lock():
        st = store.load()
        st.run_id = run_id
        sess = store.ensure_session(st, sd)

        # Duplicate-trigger protection: two schedulers (GitHub cron + an external pinger) may both fire for
        # the same 5-minute slot. The second one records itself and does nothing else.
        slot_sec = int(settings.get("session", "slot_seconds", 300))
        slot = int(now.timestamp()) // slot_sec * slot_sec
        if not force_fetch and st.extra.get("last_slot") == slot:
            summary.state = "DUPLICATE_SLOT"
            summary.notes.append(f"slot {slot} already handled by run {st.extra.get('last_slot_run')}")
            StateStore.record_run(st, summary.to_dict())
            store.save(st)
            return summary
        st.extra["last_slot"], st.extra["last_slot_run"] = slot, run_id
        st.extra["last_slot_lag_s"] = int(now.timestamp()) - slot

        # Pre-session warm-up: fetch from 15 min before the window so the first in-session check has fresh data.
        pre = to_utc(datetime.combine(sd, spec.start, __import__("xau_signals.timeutil", fromlist=["IST"]).IST)) - timedelta(minutes=15)
        should_fetch = force_fetch or insess or (pre <= now < pre + timedelta(minutes=15))
        if not should_fetch or market_hours.is_closed(now):
            summary.notes.append("outside session window (or market closed): no fetch, record only")
            StateStore.record_run(st, summary.to_dict())
            store.save(st)
            return summary

        # ---- fetch + validate --------------------------------------------------
        bias_need, setup_need = _lookback_bars(sparams)
        ev: Evaluation
        try:
            raw_b = provider.fetch(symbol=symbol, interval=bias_iv, lookback_bars=bias_need)
            raw_s = provider.fetch(symbol=symbol, interval=setup_iv, lookback_bars=setup_need)
            summary.fetched = True
            b, rep_b = validate(raw_b, symbol=symbol, interval=bias_iv, now=now, max_age_seconds=max_age * 4 + interval_seconds(bias_iv), max_unexplained_gap_bars=max_gap)
            s, rep_s = validate(raw_s, symbol=symbol, interval=setup_iv, now=now, max_age_seconds=max_age, max_unexplained_gap_bars=max_gap)
            summary.validation = {bias_iv: rep_b.summary(), setup_iv: rep_s.summary()}
            data_fresh = bool(rep_s.fresh) and bool(rep_b.fresh)
            data_ok = rep_b.ok and rep_s.ok and bool(b) and bool(s)
        except (ProviderError, CandleValidationError, OSError, ValueError) as e:
            data_ok, data_fresh, b, s = False, False, [], []
            summary.notes.append(f"fetch/validate error: {redact(str(e))[:300]}")

        if not data_ok or not data_fresh:
            sess.consecutive_data_failures += 1
            ev = Evaluation(as_of=now, bias="NONE", state=SetupState.DATA_UNAVAILABLE if not data_ok else SetupState.DATA_STALE,
                            reasons=[summary.validation.get(setup_iv, ""), *summary.notes])
            summary.state, summary.bias = ev.state.value, "NONE"
            tracker.record_decision(ev, run_id=run_id, mode=settings.mode, strategy=f"{strat.name}@{strat.version}")
            if insess and sess.consecutive_data_failures >= fail_after and "data" not in sess.failure_alert_sent_for and sender is not None:
                text = messages.failure_alert("data unavailable or stale", f"{sess.consecutive_data_failures} consecutive checks failed. " + " | ".join(ev.reasons)[:400], now=now)
                res = sender.send(text)
                tracker.record_delivery({"run_id": run_id, "kind": "failure", "at": now, **res.__dict__})
                if res.status in ("sent", "ambiguous"):
                    sess.failure_alert_sent_for.append("data")
                summary.notes.append(f"failure alert: {res.status}")
            StateStore.record_run(st, summary.to_dict())
            store.save(st)
            return summary

        sess.consecutive_data_failures = 0

        # ---- evaluate ----------------------------------------------------------
        ev = strat.evaluate(as_of=now, bias_candles=b, setup_candles=s)
        summary.state, summary.bias = ev.state.value, ev.bias
        tracker.record_decision(ev, run_id=run_id, mode=settings.mode, strategy=f"{strat.name}@{strat.version}",
                                extra={"price_scope": provider.price_scope})

        if ev.state != SetupState.SETUP_QUALIFIED or ev.setup is None:
            StateStore.record_run(st, summary.to_dict())
            store.save(st)
            return summary

        setup = ev.setup
        if setup.setup_id not in sess.seen_setup_ids:
            sess.seen_setup_ids.append(setup.setup_id)

        # ---- gate (recheck session + freshness right before delivery) -------------
        now2 = now if injected_clock else to_utc(now_utc())   # recheck session + freshness against the clock right before sending
        g = gate.check(now=now2, sess=sess, setup_id=setup.setup_id, spec=spec, max_alerts=cap, cooldown=cooldown, data_fresh=data_fresh)
        if not g.allowed:
            summary.alert_action = f"blocked:{g.reason}"
            StateStore.record_run(st, summary.to_dict())
            store.save(st)
            return summary

        n_sent = sess.consumed() + 1
        text = messages.setup_alert(ev, setup, now=now2, price_scope=provider.price_scope, n_sent=n_sent, cap=cap,
                                    setup_interval=setup_iv, stale_ext_atr=float(sparams.get("stale_extension_atr", 1.0)),
                                    strategy_tag=f"{strat.name}@{strat.version}")
        if settings.mode != "live" or sender is None or isinstance(sender, PaperSender):
            # Paper: consume the slot exactly as live would, so the cap/cooldown behave identically.
            rec = AlertRecord(setup.setup_id, "sent", iso(now2), setup.direction, setup.setup_type, message_id=None, sent_at=iso(now2), error="paper")
            sess.alerts.append(rec)
            sess.last_sent_at = iso(now2)
            summary.alert_action = "paper"
            if sender is not None:
                sender.send(messages.paper_prefix(text))
            tracker.record_delivery({"run_id": run_id, "kind": "setup", "mode": settings.mode, "setup_id": setup.setup_id, "at": now2, "status": "paper", "text": text})
            StateStore.record_run(st, summary.to_dict())
            store.save(st)
            return summary

        # Live: reserve -> save -> send -> save
        rec = AlertRecord(setup.setup_id, "inflight", iso(now2), setup.direction, setup.setup_type)
        sess.alerts.append(rec)
        store.save(st)
        res = sender.send(text)
        rec.status = res.status if res.status in ("sent", "ambiguous", "failed") else "failed"
        rec.message_id = res.message_id
        rec.error = redact(res.error or "") or None
        if res.status == "sent":
            rec.sent_at = iso(now_utc())
            sess.last_sent_at = rec.sent_at
        elif res.status == "ambiguous":
            sess.last_sent_at = iso(now_utc())     # treat as possibly delivered: cooldown still applies
        summary.alert_action = res.status
        summary.delivery = res
        tracker.record_delivery({"run_id": run_id, "kind": "setup", "mode": settings.mode, "setup_id": setup.setup_id, "at": now2,
                                 "status": res.status, "message_id": res.message_id, "http": res.http_status, "error": rec.error,
                                 "attempts": res.attempts, "elapsed_s": round(res.elapsed_seconds, 2), "text": text})
        if res.status == "failed":
            log.error("setup alert delivery failed: %s", rec.error)
        StateStore.record_run(st, summary.to_dict())
        store.save(st)
        return summary
