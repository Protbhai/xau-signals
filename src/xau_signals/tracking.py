"""Forward performance tracking: append-only JSONL of every decision and every delivery."""
from __future__ import annotations

import json
from dataclasses import asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Iterator

from .strategies.base import Evaluation
from .timeutil import UTC


def _json_default(o: Any):
    if isinstance(o, datetime):
        return o.astimezone(UTC).isoformat()
    if hasattr(o, "value"):
        return o.value
    return str(o)


class Tracker:
    def __init__(self, directory: str | Path):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.decisions = self.dir / "decisions.jsonl"
        self.deliveries = self.dir / "deliveries.jsonl"
        self.outcomes = self.dir / "outcomes.jsonl"

    def _append(self, path: Path, rec: dict[str, Any]) -> None:
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, default=_json_default, sort_keys=True) + "\n")

    def record_decision(self, ev: Evaluation, *, run_id: str, mode: str, strategy: str, extra: dict[str, Any] | None = None) -> None:
        rec = {"run_id": run_id, "mode": mode, "strategy": strategy, "as_of": ev.as_of, "bias": ev.bias, "state": ev.state.value,
               "bias_candle_ts": ev.bias_candle_ts, "setup_candle_ts": ev.setup_candle_ts, "reasons": ev.reasons, "metrics": ev.metrics,
               "setup": (asdict(ev.setup) | {"setup_id": ev.setup.setup_id}) if ev.setup else None}
        if extra:
            rec.update(extra)
        self._append(self.decisions, rec)

    def record_delivery(self, rec: dict[str, Any]) -> None:
        self._append(self.deliveries, rec)

    def record_outcome(self, rec: dict[str, Any]) -> None:
        self._append(self.outcomes, rec)

    def iter_decisions(self) -> Iterator[dict[str, Any]]:
        if not self.decisions.exists():
            return iter(())
        with open(self.decisions, encoding="utf-8") as f:
            return iter([json.loads(line) for line in f if line.strip()])

    def iter_outcomes(self) -> Iterator[dict[str, Any]]:
        if not self.outcomes.exists():
            return iter(())
        with open(self.outcomes, encoding="utf-8") as f:
            return iter([json.loads(line) for line in f if line.strip()])
