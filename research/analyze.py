"""Read a compare.py result file and report what the summary table hides.

  python research/analyze.py docs/research/results/<file>.json [strategy]

- alerts by IST hour of the decision (does the cap push everything into the open?)
- outcomes by rank of the alert within its day (1st/2nd/3rd): is "first come" worse?
- within-session (to 15:00 IST) close move in ATR and in USD, with cost sensitivity:
  a fixed round-trip cost of 0.6 and 1.2 USD (0.3 / 0.6 per side; retail XAU spread range,
  UNVERIFIED for any specific broker) subtracted from the median and mean close move
- invalidation-after-trigger rate, i.e. how often the structural stop would have been hit
- direction split (UP vs DOWN) outcomes
Nothing here is a profit figure: moves are reference-price excursions from the trigger level.
"""
from __future__ import annotations

import json
import statistics
import sys
from collections import Counter, defaultdict
from datetime import datetime
from pathlib import Path

from zoneinfo import ZoneInfo

IST = ZoneInfo("Asia/Kolkata")


def pct(a, b):
    return f"{100 * a / b:.0f}%" if b else "n/a"


def analyze(path: str, only: str | None = None):
    d = json.loads(Path(path).read_text(encoding="utf-8"))
    print(f"{d['series']} {d['start']}..{d['end']} delay={d['config']['delay_minutes']}")
    for name, r in d["results"].items():
        if only and name != only:
            continue
        alerts = r["alerts"]
        print(f"\n== {name}: {len(alerts)} alerts")
        if not alerts:
            continue
        by_hour = Counter(a["decision_ist"][:2] for a in alerts)
        print("  by IST hour:", dict(sorted(by_hour.items())))
        by_dir = Counter(a["direction"] for a in alerts)
        print("  direction:", dict(by_dir))

        def sess_move(a):
            if not a["outcome"]["triggered_at"]:
                return None
            for e in a["outcome"]["excursions"]:
                if e["horizon"] == "to_15:00_IST" and e["complete"] and e["close_move"] is not None:
                    return e["close_move"], e["close_move"] / a["atr"], e["mfe"], e["mae"]
            return None

        ranks = defaultdict(list)
        day_counter = Counter()
        for a in alerts:
            day_counter[a["day"]] += 1
            ranks[day_counter[a["day"]]].append(a)
        for rk in sorted(ranks):
            xs = ranks[rk]
            trig = [a for a in xs if a["outcome"]["triggered_at"]]
            mv = [sess_move(a) for a in xs]
            mv = [m for m in mv if m]
            fav = sum(1 for m in mv if m[0] > 0)
            print(f"  rank {rk}: n={len(xs)} triggered={pct(len(trig), len(xs))} invalidated-before={pct(sum(1 for a in xs if a['outcome']['invalidated_before_trigger_at']), len(xs))} "
                  f"to15:00 fav={pct(fav, len(mv))} medMove={statistics.median(m[0] for m in mv) if mv else 'n/a':.2f} "
                  f"medMove/ATR={statistics.median(m[1] for m in mv) if mv else 0:.2f}")

        mv = [sess_move(a) for a in alerts]
        mv = [m for m in mv if m]
        if mv:
            moves = [m[0] for m in mv]
            med, mean = statistics.median(moves), statistics.mean(moves)
            print(f"  to15:00 USD move: n={len(moves)} median={med:.2f} mean={mean:.2f} | after 0.6 cost: {med - 0.6:.2f}/{mean - 0.6:.2f} | after 1.2 cost: {med - 1.2:.2f}/{mean - 1.2:.2f}")
            print(f"  share positive after 1.2 cost: {pct(sum(1 for x in moves if x - 1.2 > 0), len(moves))}")
            print(f"  median MFE {statistics.median(m[2] for m in mv):.2f}  median MAE {statistics.median(m[3] for m in mv):.2f}  (USD from trigger)")
        trig = [a for a in alerts if a["outcome"]["triggered_at"]]
        inv_after = sum(1 for a in trig if a["outcome"]["invalidated_after_trigger_at"])
        print(f"  triggered {len(trig)}/{len(alerts)}; structural invalidation hit after trigger: {pct(inv_after, len(trig))}")
        for dr in ("UP", "DOWN"):
            xs = [a for a in alerts if a["direction"] == dr]
            m2 = [sess_move(a) for a in xs]
            m2 = [m for m in m2 if m]
            if m2:
                print(f"  {dr}: n={len(xs)} to15:00 fav={pct(sum(1 for m in m2 if m[0] > 0), len(m2))} medMove={statistics.median(m[0] for m in m2):.2f}")


if __name__ == "__main__":
    analyze(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else None)
