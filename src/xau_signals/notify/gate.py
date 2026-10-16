"""The alert gate: session window, daily cap, dedup, cooldown, freshness recheck.

Everything a setup alert must pass immediately before delivery lives here, so
the same code runs in paper mode, live mode and the replay backtest.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from ..session import SessionSpec, in_session, session_date
from ..state import SessionState
from ..timeutil import to_utc


@dataclass(frozen=True)
class GateDecision:
    allowed: bool
    reason: str      # "ok" or why it was blocked


def check(
    *,
    now: datetime,
    sess: SessionState,
    setup_id: str,
    spec: SessionSpec,
    max_alerts: int,
    cooldown: timedelta,
    data_fresh: bool,
) -> GateDecision:
    now = to_utc(now)
    if sess.session_date != session_date(now).isoformat():
        return GateDecision(False, "state session_date mismatch (daily reset not applied)")
    if not in_session(now, spec):
        return GateDecision(False, "outside 09:00-15:00 IST")
    if not data_fresh:
        return GateDecision(False, "data not fresh at send time")
    if any(a.setup_id == setup_id and a.status in ("inflight", "sent", "ambiguous") for a in sess.alerts):
        return GateDecision(False, "duplicate: this setup was already alerted this session")
    if sess.consumed() >= max_alerts:
        return GateDecision(False, f"daily cap reached ({max_alerts})")
    if sess.last_sent_at:
        last = datetime.fromisoformat(sess.last_sent_at)
        if now - last < cooldown:
            left = int((cooldown - (now - last)).total_seconds() // 60) + 1
            return GateDecision(False, f"cooldown: {left} min left")
    return GateDecision(True, "ok")
