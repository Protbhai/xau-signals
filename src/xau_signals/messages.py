"""Telegram message text. Concise, IST, with scope and conditionality stated."""
from __future__ import annotations

from datetime import datetime

from .strategies.base import Evaluation, Setup
from .timeutil import candle_close_time, fmt_ist, to_ist


def _hm(dt: datetime) -> str:
    return to_ist(dt).strftime("%H:%M")


def setup_alert(ev: Evaluation, setup: Setup, *, now: datetime, price_scope: str, n_sent: int, cap: int,
                setup_interval: str, stale_ext_atr: float, strategy_tag: str) -> str:
    arrow = "⬆" if setup.direction == "UP" else "⬇"
    side = "above" if setup.direction == "UP" else "below"
    inv_side = "below" if setup.direction == "UP" else "above"
    a_close = candle_close_time(setup.anchor_ts, setup_interval)
    lines = [
        f"<b>XAU/USD {arrow} {setup.direction} bias</b> — {setup.setup_type.replace('_', ' ')}",
        f"Entry if: {setup_interval} close {side} <b>{setup.trigger:.2f}</b> (zone {setup.zone_low:.2f}–{setup.zone_high:.2f})",
        f"Invalid if: {setup_interval} close {inv_side} <b>{setup.invalidation:.2f}</b>",
        f"Checked {fmt_ist(now)} · setup candle {_hm(setup.anchor_ts)}–{_hm(a_close)} IST",
        f"Expires {_hm(setup.expires_at)} IST, or if price runs &gt;{stale_ext_atr:g} ATR (≈{stale_ext_atr * setup.atr:.2f}) past the trigger",
        f"Ref: {price_scope} — not a broker bid/ask",
        f"Conditional observation, not a confirmed entry. Alert {n_sent}/{cap} · {strategy_tag}",
    ]
    return "\n".join(lines)


def failure_alert(kind: str, detail: str, *, now: datetime) -> str:
    return f"<b>XAU/USD system: {kind}</b>\n{detail}\nAt {fmt_ist(now)}. No setup alerts can be judged until this clears."


def paper_prefix(text: str) -> str:
    return "[PAPER — would have sent]\n" + text
