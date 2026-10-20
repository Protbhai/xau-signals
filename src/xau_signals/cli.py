"""Command line: run | status | outcomes | replay | fetch | notify-test."""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

from . import market_hours
from .config import Settings, load_settings
from .log import setup_logging
from .notify.telegram import PaperSender, TelegramSender
from .providers.base import ProviderError
from .state import StateStore
from .timeutil import IST, now_utc, to_utc
from .tracking import Tracker


def _provider(settings: Settings):
    import os
    name = os.environ.get("XAU_PROVIDER") or settings.get("data", "provider", "twelvedata")
    if name == "csv":
        from .providers.csvfile import CsvProvider
        files = settings.raw["data"]["csv_files"]
        return CsvProvider({k: settings.path(v) for k, v in files.items()}, symbol=settings.get("data", "symbol"))
    if name == "yahoo":
        from .providers.yahoo import YahooProvider
        return YahooProvider()
    if name == "binance":
        from .providers.binance import BinanceProvider
        return BinanceProvider()
    if name == "twelvedata":
        from .providers.twelvedata import TwelveDataProvider
        return TwelveDataProvider()
    raise SystemExit(f"unknown provider {name!r}")


def _symbol(settings: Settings) -> str:
    import os
    name = os.environ.get("XAU_PROVIDER") or settings.get("data", "provider", "twelvedata")
    return settings.raw["data"].get("symbols", {}).get(name) or settings.get("data", "symbol")


def _sender(settings: Settings, log):
    if settings.telegram_configured:
        return TelegramSender(settings.telegram_token, settings.telegram_chat_id,
                              timeout_seconds=float(settings.get("notify", "telegram_timeout_seconds", 15)),
                              max_retries=int(settings.get("notify", "telegram_max_retries", 2)))
    log.info("telegram not configured: using PaperSender (messages recorded only)")
    return PaperSender()


def cmd_run(args, settings: Settings, log):
    from .engine import run_once
    market_hours.load_closures(settings.path(settings.get("session", "closures_file", "config/closures.json")))
    store = StateStore(settings.path(settings.get("state", "dir", "state")), lock_stale_seconds=int(settings.get("state", "lock_stale_seconds", 240)))
    tracker = Tracker(settings.path("data/tracking"))
    sender = _sender(settings, log)
    now = datetime.fromisoformat(args.now) if args.now else None
    try:
        provider = _provider(settings)
    except ProviderError as e:
        # e.g. no API key configured yet: record the run honestly as DATA_UNAVAILABLE and exit 0 so state persists.
        log.error("provider not usable: %s", e)
        d = {"mode": settings.mode, "state": "DATA_UNAVAILABLE", "alert_action": "none", "notes": [f"provider not usable: {e}"]}
        with store.lock():
            st = store.load()
            StateStore.record_run(st, d | {"started_at": now_utc().isoformat()})
            store.save(st)
        print(json.dumps(d, indent=1))
        return 0
    summary = run_once(settings, provider=provider, sender=sender, store=store, tracker=tracker, now=now, force_fetch=args.force)
    d = summary.to_dict()
    d["mode"] = settings.mode
    if isinstance(sender, PaperSender) and sender.messages:
        d["paper_messages"] = sender.messages
    print(json.dumps(d, indent=1))
    return 0


def cmd_status(args, settings: Settings, log):
    store = StateStore(settings.path(settings.get("state", "dir", "state")))
    st = store.load()
    out = {"updated_at": st.updated_at, "session": st.session.__dict__ if st.session else None, "last_runs": st.runs[-args.n:]}
    print(json.dumps(out, indent=1, default=str))
    return 0


OUTCOME_FETCH_GAP_S = 8


def cmd_outcomes(args, settings: Settings, log):
    """Evaluate forward outcomes for recorded decisions whose expiry has passed and that lack an outcome."""
    from .outcomes import evaluate_outcome
    from .strategies.base import Setup
    market_hours.load_closures(settings.path(settings.get("session", "closures_file", "config/closures.json")))
    tracker = Tracker(settings.path("data/tracking"))
    done = {o["setup_id"] for o in tracker.iter_outcomes()}
    provider = _provider(settings)
    symbol = _symbol(settings)
    iv = settings.get("data", "setup_interval", "5m")
    now = to_utc(now_utc())
    n = 0
    for rec in tracker.iter_decisions():
        s = rec.get("setup")
        if not s or rec.get("state") != "SETUP_QUALIFIED" or s["setup_id"] in done:
            continue
        anchor = datetime.fromisoformat(s["anchor_ts"])
        if now < anchor + timedelta(hours=3):
            continue   # too early to judge within-session + 120m horizons
        setup = Setup(s["direction"], s["setup_type"], anchor, s["trigger"], s["zone_low"], s["zone_high"], s["invalidation"],
                      datetime.fromisoformat(s["expires_at"]), s["atr"], s.get("notes", ""))
        if n:
            time.sleep(OUTCOME_FETCH_GAP_S)   # free Twelve Data plan: 8 credits per minute
        try:
            later = provider.fetch(symbol=symbol, interval=iv, start=anchor, end=anchor + timedelta(hours=9))
        except ProviderError as e:
            if "API credits" not in str(e):
                raise
            print(json.dumps({"outcomes_written": n, "stopped": "rate limit; the rest are measured on the next run"}))
            return 0
        oc = evaluate_outcome(setup, [c for c in later if c.complete])
        tracker.record_outcome({"evaluated_at": now, "decision_run_id": rec.get("run_id"), "mode": rec.get("mode"), **oc.to_dict()})
        done.add(s["setup_id"])
        n += 1
    print(json.dumps({"outcomes_written": n}))
    return 0


def cmd_replay(args, settings: Settings, log):
    from .providers.csvfile import read_csv
    from .replay import ReplayConfig, replay
    from .strategies import make
    market_hours.load_closures(settings.path(settings.get("session", "closures_file", "config/closures.json")))
    symbol = args.symbol or settings.get("data", "symbol")
    b = read_csv(args.bias_csv, symbol=symbol, interval=args.bias_interval)
    s = read_csv(args.setup_csv, symbol=symbol, interval=args.setup_interval)
    params = settings.raw.get("strategy", {}).get(args.strategy, {})
    strat = make(args.strategy, params)
    cfg = ReplayConfig(cadence_minutes=args.cadence, delay_minutes=args.delay, max_alerts=int(settings.get("session", "max_alerts_per_session", 3)),
                       cooldown_minutes=int(settings.get("session", "cooldown_minutes", 20)))
    res = replay(strat, b, s, cfg=cfg)
    out = {"summary": res.summary(), "alerts": res.alerts if args.alerts else len(res.alerts)}
    text = json.dumps(out, indent=1, default=str)
    if args.out:
        Path(args.out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.out).write_text(text, encoding="utf-8")
        print(json.dumps(res.summary(), indent=1))
    else:
        print(text)
    return 0


def cmd_fetch(args, settings: Settings, log):
    from .providers.csvfile import write_csv
    provider = _provider(settings)
    symbol = args.symbol or _symbol(settings)
    start = datetime.fromisoformat(args.start) if args.start else None
    end = datetime.fromisoformat(args.end) if args.end else None
    cs = provider.fetch(symbol=symbol, interval=args.interval, start=start, end=end, lookback_bars=args.bars)
    write_csv(args.out, cs)
    print(json.dumps({"written": len(cs), "first": cs[0].ts_open.isoformat() if cs else None, "last": cs[-1].ts_open.isoformat() if cs else None, "out": args.out}))
    return 0


def cmd_notify_test(args, settings: Settings, log):
    if not settings.telegram_configured:
        print("telegram not configured (XAU_TELEGRAM_BOT_TOKEN / XAU_TELEGRAM_CHAT_ID)")
        return 2
    s = _sender(settings, log)
    r = s.send(f"xau-signals test message at {now_utc().astimezone(IST).strftime('%d %b %H:%M:%S IST')} (mode={settings.mode})")
    print(json.dumps({"status": r.status, "message_id": r.message_id, "http": r.http_status, "error": r.error, "attempts": r.attempts}))
    return 0 if r.sent else 1


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="xau-signals")
    p.add_argument("--config", default=None)
    p.add_argument("--log-level", default="INFO")
    sub = p.add_subparsers(dest="cmd", required=True)

    r = sub.add_parser("run", help="one check (fetch, evaluate, maybe alert)")
    r.add_argument("--now", help="ISO time to evaluate as-of (testing/replay of a single check)")
    r.add_argument("--force", action="store_true", help="fetch even outside the session window")
    r.set_defaults(fn=cmd_run)

    s = sub.add_parser("status")
    s.add_argument("-n", type=int, default=10)
    s.set_defaults(fn=cmd_status)

    o = sub.add_parser("outcomes", help="write forward outcomes for matured decisions")
    o.set_defaults(fn=cmd_outcomes)

    rp = sub.add_parser("replay", help="backtest the engine over CSV history")
    rp.add_argument("--bias-csv", required=True)
    rp.add_argument("--setup-csv", required=True)
    rp.add_argument("--bias-interval", default="1h")
    rp.add_argument("--setup-interval", default="5m")
    rp.add_argument("--symbol", default=None)
    rp.add_argument("--strategy", default="benchmark_v1")
    rp.add_argument("--cadence", type=int, default=5)
    rp.add_argument("--delay", type=float, default=0.0)
    rp.add_argument("--alerts", action="store_true", help="include per-alert rows in the output")
    rp.add_argument("--out", default=None)
    rp.set_defaults(fn=cmd_replay)

    f = sub.add_parser("fetch", help="download candles to CSV (research)")
    f.add_argument("--interval", required=True)
    f.add_argument("--symbol", default=None)
    f.add_argument("--start", default=None)
    f.add_argument("--end", default=None)
    f.add_argument("--bars", type=int, default=None)
    f.add_argument("--out", required=True)
    f.set_defaults(fn=cmd_fetch)

    t = sub.add_parser("notify-test", help="send one test message to Telegram (requires secrets)")
    t.set_defaults(fn=cmd_notify_test)

    args = p.parse_args(argv)
    log = setup_logging(args.log_level)
    settings = load_settings(args.config)
    return int(args.fn(args, settings, log) or 0)


if __name__ == "__main__":
    sys.exit(main())
