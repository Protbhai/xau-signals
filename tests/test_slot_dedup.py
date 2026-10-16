from datetime import timedelta

from xau_signals.engine import run_once
from xau_signals.notify.telegram import PaperSender
from xau_signals.state import StateStore
from xau_signals.tracking import Tracker

from conftest import ist, trending_1h, trending_pullback_5m
from test_strategy_and_engine import FakeProvider, _settings


def test_second_trigger_in_same_slot_is_noop(tmp_path):
    anchor = ist(2026, 10, 13, 10, 25)
    prov = FakeProvider(trending_1h(ist(2026, 10, 13, 9, 0)), trending_pullback_5m(anchor))
    store, tracker = StateStore(tmp_path / "state"), Tracker(tmp_path / "track")
    settings = _settings(tmp_path, "paper")
    sender = PaperSender()
    t = anchor + timedelta(minutes=5, seconds=20)       # slot 10:30:00-10:34:59 IST
    r1 = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=t)
    r2 = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=t + timedelta(seconds=90))
    assert r1.alert_action == "paper" and r2.state == "DUPLICATE_SLOT" and not r2.fetched
    r3 = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=t + timedelta(minutes=5))
    assert r3.fetched and r3.state != "DUPLICATE_SLOT"
    assert store.load().extra["last_slot_lag_s"] == 20 + 300 - 300  # 10:35:20 -> 20 s into the slot
