"""Fair comparison of strategy candidates on one data series.

  python research/compare.py <series> <start> <end> [--delay 2] [--strategies a,b] [--tag dev]

series: binance | dukascopy | yahoo  (files in data/raw written by fetch_history.py)
Writes docs/research/results/<tag>_<series>_<start>_<end>_d<delay>.json and prints a table.
Every run is recorded; nothing is cherry-picked. Parameters come from config/default.toml
and are NOT changed between dev and validation runs.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from xau_signals import market_hours  # noqa: E402
from xau_signals.config import load_settings  # noqa: E402
from xau_signals.providers.csvfile import read_csv  # noqa: E402
from xau_signals.replay import ReplayConfig, replay  # noqa: E402
from xau_signals.strategies import REGISTRY, make  # noqa: E402

FILES = {
    "binance": ("binance_XAUUSDT_{iv}.csv", "XAUUSDT"),
    "dukascopy": ("dukascopy_XAUUSD_bid_{iv}.csv", "XAUUSD"),
    "yahoo": ("yahoo_GCF_{iv}.csv", "GC=F"),
}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("series")
    ap.add_argument("start")
    ap.add_argument("end")
    ap.add_argument("--delay", type=float, default=0.0)
    ap.add_argument("--cadence", type=int, default=5)
    ap.add_argument("--strategies", default=",".join(REGISTRY))
    ap.add_argument("--tag", default="dev")
    ap.add_argument("--cooldown", type=int, default=None, help="override cooldown minutes")
    ap.add_argument("--aux", default="15m,1m,4h", help="extra series to load if files exist")
    a = ap.parse_args()

    market_hours.load_closures(ROOT / "config" / "closures.json")
    settings = load_settings(root=ROOT)
    pattern, symbol = FILES[a.series]
    raw = ROOT / "data" / "raw"
    b = read_csv(raw / pattern.format(iv="1h"), symbol=symbol, interval="1h", source=a.series)
    s = read_csv(raw / pattern.format(iv="5m"), symbol=symbol, interval="5m", source=a.series)
    start, end = date.fromisoformat(a.start), date.fromisoformat(a.end)
    cfg = ReplayConfig(cadence_minutes=a.cadence, delay_minutes=a.delay,
                       max_alerts=int(settings.get("session", "max_alerts_per_session", 3)),
                       cooldown_minutes=a.cooldown if a.cooldown is not None else int(settings.get("session", "cooldown_minutes", 20)))
    aux = {}
    for iv in [x for x in a.aux.split(",") if x]:
        f = raw / pattern.format(iv=iv)
        if f.exists():
            aux[iv] = read_csv(f, symbol=symbol, interval=iv, source=a.series)
        elif iv == "4h":
            from xau_signals.resample import resample
            aux["4h"], _ = resample(b, "4h")
        elif iv == "15m":
            from xau_signals.resample import resample
            aux["15m"], _ = resample(s, "15m")
    print("aux series:", {k: len(v) for k, v in aux.items()}, flush=True)
    results = {}
    for name in a.strategies.split(","):
        t0 = time.time()
        strat = make(name, settings.raw.get("strategy", {}).get(name, {}))
        res = replay(strat, b, s, cfg=cfg, start=start, end=end, aux=aux)
        summ = res.summary()
        summ["seconds"] = round(time.time() - t0, 1)
        results[name] = {"summary": summ, "alerts": res.alerts}
        o = summ["outcomes"]
        h = o["to_15:00_IST"]
        print(f"{name:22s} days={summ['session_days']:4d} checks={summ['checks']:6d} qualified={summ['distinct_qualified_setups']:4d} "
              f"sent={summ['alerts_sent']:4d} ({summ['alerts_per_day_mean']}/day, 0-days={summ['days_with_0_alerts']}) "
              f"trig={o['triggered']} invB={o['invalidated_before_trigger']} exp={o['expired_untriggered']} unav={o['unavailable']} "
              f"| +15m fav={o['+15m'].get('favourable',0)}/{o['+15m'].get('n',0)} | to15:00 n={h.get('n',0)} fav={h.get('favourable',0)} adv={h.get('adverse',0)} medMove={h.get('median_close_move')} "
              f"medMFE={h.get('median_mfe')} medMAE={h.get('median_mae')} | {summ['seconds']}s", flush=True)
    out = ROOT / "docs" / "research" / "results" / f"{a.tag}_{a.series}_{a.start}_{a.end}_d{a.delay:g}_cd{cfg.cooldown_minutes}.json"
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"series": a.series, "start": a.start, "end": a.end, "config": cfg.__dict__ | {"spec": str(cfg.spec)},
                               "params": settings.raw.get("strategy"), "results": results}, indent=1, default=str), encoding="utf-8")
    print("wrote", out)


if __name__ == "__main__":
    main()
