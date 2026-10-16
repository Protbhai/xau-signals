from datetime import timedelta

from xau_signals.config import Settings
from xau_signals.engine import run_once
from xau_signals.notify.telegram import DeliveryResult, PaperSender
from xau_signals.state import StateStore
from xau_signals.strategies import BenchmarkV1
from xau_signals.strategies.base import SetupState
from xau_signals.tracking import Tracker

from conftest import ist, trending_1h, trending_pullback_5m


def test_benchmark_qualifies_up_pullback():
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=True)
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=True)
    ev = BenchmarkV1().evaluate(as_of=anchor + timedelta(minutes=5, seconds=30), bias_candles=b, setup_candles=s)
    assert ev.bias == "UP" and ev.state == SetupState.SETUP_QUALIFIED
    st = ev.setup
    assert st.direction == "UP" and st.trigger == s[-1].high and st.invalidation < s[-1].low and st.anchor_ts == anchor


def test_benchmark_down_and_no_lookahead():
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=False)
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=False)
    # as_of BEFORE the anchor candle closes: the anchor must not be used (no look-ahead)
    ev_early = BenchmarkV1().evaluate(as_of=anchor + timedelta(minutes=2), bias_candles=b, setup_candles=s)
    assert ev_early.setup_candle_ts == s[-2].ts_open
    ev = BenchmarkV1().evaluate(as_of=anchor + timedelta(minutes=5), bias_candles=b, setup_candles=s)
    assert ev.bias == "DOWN" and ev.state == SetupState.SETUP_QUALIFIED and ev.setup.direction == "DOWN"


def test_benchmark_expired_when_price_ran_away():
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=True)
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=True)
    strat = BenchmarkV1()
    ev = strat.evaluate(as_of=anchor + timedelta(minutes=5), bias_candles=b, setup_candles=s)
    assert ev.state == SetupState.SETUP_QUALIFIED
    # decision time past expiry (6 bars) => expired
    ev2 = strat.evaluate(as_of=anchor + timedelta(minutes=5 + 31), bias_candles=b, setup_candles=s)
    assert ev2.state == SetupState.SETUP_EXPIRED


def test_insufficient_data_is_unavailable_not_neutral():
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=True)[-10:]
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=True)
    ev = BenchmarkV1().evaluate(as_of=anchor + timedelta(minutes=5), bias_candles=b, setup_candles=s)
    assert ev.state == SetupState.DATA_UNAVAILABLE


# ---------------- engine end-to-end with a fake provider ------------------------

class FakeProvider:
    name = "fake"
    price_scope = "synthetic test feed"

    def __init__(self, b, s, fail=False):
        self.b, self.s, self.fail = b, s, fail

    def fetch(self, *, symbol, interval, start=None, end=None, lookback_bars=None):
        if self.fail:
            from xau_signals.providers.base import ProviderError
            raise ProviderError("boom")
        return list(self.b if interval == "1h" else self.s)


class ScriptedSender:
    def __init__(self, results):
        self.results = list(results)
        self.sent = []

    def send(self, text):
        self.sent.append(text)
        return self.results.pop(0)


def _settings(tmp_path, mode="paper", **over):
    raw = {
        "session": {"start": "09:00", "end": "15:00", "max_alerts_per_session": 3, "cooldown_minutes": 20},
        "data": {"provider": "fake", "symbol": "XAUUSD", "bias_interval": "1h", "setup_interval": "5m", "max_candle_age_seconds": 900, "max_unexplained_gap_bars": 1},
        "strategy": {"name": "benchmark_v1", "benchmark_v1": {}},
        "notify": {"failure_alert_after_consecutive_data_failures": 2},
        "state": {"dir": str(tmp_path / "state")},
    }
    for k, v in over.items():
        raw[k].update(v)
    return Settings(raw=raw, root=tmp_path, mode=mode, telegram_token="t" * 40 if mode == "live" else None, telegram_chat_id="1" if mode == "live" else None)


def _env(tmp_path, up=True):
    anchor = ist(2026, 10, 13, 10, 25)
    s = trending_pullback_5m(anchor, up=up)
    b = trending_1h(ist(2026, 10, 13, 9, 0), up=up)
    return anchor, FakeProvider(b, s), StateStore(tmp_path / "state"), Tracker(tmp_path / "track")


def test_paper_mode_consumes_slot_and_never_calls_live_sender(tmp_path):
    anchor, prov, store, tracker = _env(tmp_path)
    settings = _settings(tmp_path, "paper")
    sender = PaperSender()
    now = anchor + timedelta(minutes=5, seconds=20)
    r = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now)
    assert r.alert_action == "paper" and sender.messages and sender.messages[0].startswith("[PAPER")
    assert "UP bias" in sender.messages[0] and "not a broker bid/ask" in sender.messages[0]
    # same check again => duplicate blocked
    r2 = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now + timedelta(minutes=1))
    assert r2.alert_action.startswith("blocked:duplicate")
    st = store.load()
    assert st.session.consumed() == 1 and len(list(tracker.iter_decisions())) == 2


def test_live_mode_reserve_send_record(tmp_path):
    anchor, prov, store, tracker = _env(tmp_path)
    settings = _settings(tmp_path, "live")
    sender = ScriptedSender([DeliveryResult("sent", message_id=9, http_status=200, attempts=1)])
    r = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=anchor + timedelta(minutes=5, seconds=20))
    assert r.alert_action == "sent" and r.delivery.message_id == 9
    st = store.load()
    a = st.session.alerts[0]
    assert a.status == "sent" and a.message_id == 9 and st.session.last_sent_at
    assert "[PAPER" not in sender.sent[0]


def test_live_ambiguous_consumes_slot_and_is_not_resent(tmp_path):
    anchor, prov, store, tracker = _env(tmp_path)
    settings = _settings(tmp_path, "live")
    sender = ScriptedSender([DeliveryResult("ambiguous", error="read timeout", attempts=1), DeliveryResult("sent", message_id=1)])
    now = anchor + timedelta(minutes=5, seconds=20)
    r = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now)
    assert r.alert_action == "ambiguous"
    r2 = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now + timedelta(minutes=1))
    assert r2.alert_action.startswith("blocked:duplicate") and len(sender.sent) == 1


def test_live_failed_does_not_consume_slot(tmp_path):
    anchor, prov, store, tracker = _env(tmp_path)
    settings = _settings(tmp_path, "live")
    sender = ScriptedSender([DeliveryResult("failed", error="401 Unauthorized", http_status=401), DeliveryResult("sent", message_id=3)])
    now = anchor + timedelta(minutes=5, seconds=20)
    r = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now)
    assert r.alert_action == "failed" and store.load().session.consumed() == 0
    r2 = run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now + timedelta(minutes=1))
    assert r2.alert_action == "sent"


def test_outside_session_no_fetch(tmp_path):
    anchor, prov, store, tracker = _env(tmp_path)
    settings = _settings(tmp_path, "paper")
    r = run_once(settings, provider=prov, sender=PaperSender(), store=store, tracker=tracker, now=ist(2026, 10, 13, 16, 0))
    assert not r.fetched and r.state == "SKIPPED"


def test_data_failure_alert_after_threshold(tmp_path):
    anchor, prov, store, tracker = _env(tmp_path)
    prov.fail = True
    settings = _settings(tmp_path, "paper")
    sender = PaperSender()
    now = anchor + timedelta(minutes=5)
    run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now)
    assert not sender.messages
    run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now + timedelta(minutes=5))
    assert len(sender.messages) == 1 and "data unavailable" in sender.messages[0]
    run_once(settings, provider=prov, sender=sender, store=store, tracker=tracker, now=now + timedelta(minutes=10))
    assert len(sender.messages) == 1      # not repeated within the session
    assert store.load().session.consumed() == 0   # failure alerts never consume setup slots
