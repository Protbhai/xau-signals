import json
import os
import threading
import time
from datetime import date, timedelta

import pytest

from xau_signals.notify import gate
from xau_signals.session import SessionSpec
from xau_signals.state import AlertRecord, SessionState, State, StateLockError, StateStore

from conftest import ist


def test_state_roundtrip_and_daily_reset(tmp_path):
    store = StateStore(tmp_path)
    st = store.load()
    sess = store.ensure_session(st, date(2026, 10, 13))
    sess.alerts.append(AlertRecord("abc", "sent", "x", "UP", "pullback_continuation", message_id=5, sent_at="y"))
    store.save(st)
    st2 = store.load()
    assert st2.session.alerts[0].message_id == 5 and st2.session.session_date == "2026-10-13"
    # new IST date => fresh session, cap resets
    sess3 = store.ensure_session(st2, date(2026, 10, 14))
    assert sess3.alerts == [] and sess3.consumed() == 0


def test_inflight_becomes_ambiguous_on_next_run(tmp_path):
    store = StateStore(tmp_path)
    st = store.load()
    sess = store.ensure_session(st, date(2026, 10, 13))
    sess.alerts.append(AlertRecord("abc", "inflight", "x", "UP", "t"))
    store.save(st)
    st2 = store.load()
    sess2 = store.ensure_session(st2, date(2026, 10, 13))
    assert sess2.alerts[0].status == "ambiguous" and sess2.consumed() == 1


def test_atomic_save_leaves_no_partial_file(tmp_path):
    store = StateStore(tmp_path)
    st = State()
    store.save(st)
    assert json.loads(store.path.read_text())["schema"] == 1
    assert not list(tmp_path.glob("*.tmp-*"))


def test_lock_blocks_concurrent_and_clears_stale(tmp_path):
    store = StateStore(tmp_path, lock_stale_seconds=1)
    with store.lock():
        with pytest.raises(StateLockError):
            with StateStore(tmp_path, lock_stale_seconds=1000).lock(wait_seconds=0.5):
                pass
    # stale lock left by a dead process
    store.lock_path.write_text("dead")
    old = time.time() - 10
    os.utime(store.lock_path, (old, old))
    with store.lock(wait_seconds=0.5):
        pass
    assert not store.lock_path.exists()


def _sess(day="2026-10-13"):
    return SessionState(session_date=day)


def test_gate_cap_dedup_cooldown_session():
    spec = SessionSpec()
    cd = timedelta(minutes=20)
    now = ist(2026, 10, 13, 10, 0)
    sess = _sess()
    ok = gate.check(now=now, sess=sess, setup_id="s1", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True)
    assert ok.allowed
    sess.alerts.append(AlertRecord("s1", "sent", now.isoformat(), "UP", "t", sent_at=now.isoformat()))
    sess.last_sent_at = now.isoformat()
    # duplicate
    assert "duplicate" in gate.check(now=now + timedelta(minutes=5), sess=sess, setup_id="s1", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True).reason
    # cooldown
    assert "cooldown" in gate.check(now=now + timedelta(minutes=5), sess=sess, setup_id="s2", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True).reason
    assert gate.check(now=now + timedelta(minutes=20), sess=sess, setup_id="s2", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True).allowed
    # cap: ambiguous and inflight count as consumed
    sess.alerts.append(AlertRecord("s2", "ambiguous", "x", "UP", "t"))
    sess.alerts.append(AlertRecord("s3", "inflight", "x", "UP", "t"))
    sess.last_sent_at = None
    assert "cap" in gate.check(now=now + timedelta(hours=1), sess=sess, setup_id="s4", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True).reason
    # failed does not consume
    sess.alerts[-1].status = "failed"
    assert gate.check(now=now + timedelta(hours=1), sess=sess, setup_id="s4", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True).allowed
    # outside session
    assert "outside" in gate.check(now=ist(2026, 10, 13, 15, 0), sess=sess, setup_id="s9", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True).reason
    # stale data at send time
    assert "fresh" in gate.check(now=now + timedelta(hours=1), sess=sess, setup_id="s9", spec=spec, max_alerts=3, cooldown=cd, data_fresh=False).reason
    # wrong session date in state (reset not applied)
    assert "mismatch" in gate.check(now=ist(2026, 10, 14, 10, 0), sess=sess, setup_id="s9", spec=spec, max_alerts=3, cooldown=cd, data_fresh=True).reason
