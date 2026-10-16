"""Persistent state: a JSON document written atomically under a lock.

Alert accounting lives here. A setup alert goes through three states so that a
crash anywhere leaves us at-most-once:
    reserve  -> the slot is written as "inflight" BEFORE the Telegram call
    sent     -> Telegram returned ok=true with a message_id
    ambiguous-> the call timed out or failed after bytes may have been sent;
                the slot stays consumed and the setup is never re-sent
A reservation found "inflight" on the next run (process died mid-send) is
converted to "ambiguous".
"""
from __future__ import annotations

import json
import os
import time
import uuid
from contextlib import contextmanager
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any, Iterator

from .timeutil import UTC, now_utc

SCHEMA_VERSION = 1


class StateLockError(RuntimeError):
    pass


@dataclass
class AlertRecord:
    setup_id: str
    status: str                 # inflight | sent | ambiguous | failed
    reserved_at: str
    direction: str
    setup_type: str
    message_id: int | None = None
    sent_at: str | None = None
    error: str | None = None


@dataclass
class SessionState:
    session_date: str                         # IST date "YYYY-MM-DD"
    alerts: list[AlertRecord] = field(default_factory=list)
    seen_setup_ids: list[str] = field(default_factory=list)   # observed (any state) this session, for dedup of forming notes
    last_sent_at: str | None = None
    consecutive_data_failures: int = 0
    failure_alert_sent_for: list[str] = field(default_factory=list)

    def consumed(self) -> int:
        return sum(1 for a in self.alerts if a.status in ("inflight", "sent", "ambiguous"))


@dataclass
class State:
    schema: int = SCHEMA_VERSION
    run_id: str = ""
    updated_at: str = ""
    session: SessionState | None = None
    runs: list[dict[str, Any]] = field(default_factory=list)   # last N run summaries (cadence measurement)
    extra: dict[str, Any] = field(default_factory=dict)


def _to_dict(st: State) -> dict[str, Any]:
    return asdict(st)


def _from_dict(d: dict[str, Any]) -> State:
    sess = d.get("session")
    session = None
    if sess:
        session = SessionState(
            session_date=sess["session_date"],
            alerts=[AlertRecord(**a) for a in sess.get("alerts", [])],
            seen_setup_ids=list(sess.get("seen_setup_ids", [])),
            last_sent_at=sess.get("last_sent_at"),
            consecutive_data_failures=int(sess.get("consecutive_data_failures", 0)),
            failure_alert_sent_for=list(sess.get("failure_alert_sent_for", [])),
        )
    return State(
        schema=int(d.get("schema", SCHEMA_VERSION)),
        run_id=d.get("run_id", ""),
        updated_at=d.get("updated_at", ""),
        session=session,
        runs=list(d.get("runs", [])),
        extra=dict(d.get("extra", {})),
    )


class StateStore:
    def __init__(self, directory: str | Path, name: str = "state.json", lock_stale_seconds: int = 240):
        self.dir = Path(directory)
        self.dir.mkdir(parents=True, exist_ok=True)
        self.path = self.dir / name
        self.lock_path = self.dir / (name + ".lock")
        self.lock_stale_seconds = lock_stale_seconds

    # ---- locking -----------------------------------------------------------
    @contextmanager
    def lock(self, wait_seconds: float = 10.0) -> Iterator[None]:
        deadline = time.monotonic() + wait_seconds
        fd = None
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, f"{os.getpid()} {now_utc().isoformat()}".encode())
                break
            except FileExistsError:
                try:
                    age = time.time() - self.lock_path.stat().st_mtime
                except FileNotFoundError:
                    continue
                if age > self.lock_stale_seconds:
                    self.lock_path.unlink(missing_ok=True)   # stale lock from a dead process
                    continue
                if time.monotonic() > deadline:
                    raise StateLockError(f"state locked by another run for {int(age)}s")
                time.sleep(0.2)
        try:
            yield
        finally:
            if fd is not None:
                os.close(fd)
            self.lock_path.unlink(missing_ok=True)

    # ---- load / save -------------------------------------------------------
    def load(self) -> State:
        if not self.path.exists():
            return State()
        with open(self.path, "r", encoding="utf-8") as f:
            return _from_dict(json.load(f))

    def save(self, st: State) -> None:
        st.updated_at = now_utc().isoformat()
        tmp = self.path.with_suffix(self.path.suffix + f".tmp-{uuid.uuid4().hex[:8]}")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(_to_dict(st), f, indent=1, sort_keys=True)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp, self.path)   # atomic on POSIX and on Windows (same volume)

    # ---- session helpers ---------------------------------------------------
    @staticmethod
    def ensure_session(st: State, session_date: date) -> SessionState:
        sd = session_date.isoformat()
        if st.session is None or st.session.session_date != sd:
            st.session = SessionState(session_date=sd)     # daily reset keyed on the IST session date
        # A previous process died between reserve and result: the slot stays consumed.
        for a in st.session.alerts:
            if a.status == "inflight":
                a.status = "ambiguous"
                a.error = (a.error or "") + " | found inflight at next run (process died mid-send)"
        return st.session

    @staticmethod
    def record_run(st: State, summary: dict[str, Any], keep: int = 400) -> None:
        st.runs.append(summary)
        if len(st.runs) > keep:
            del st.runs[: len(st.runs) - keep]


def iso(dt: datetime) -> str:
    return dt.astimezone(UTC).isoformat()
