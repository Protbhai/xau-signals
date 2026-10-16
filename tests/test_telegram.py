import json

import requests

from xau_signals.notify.telegram import TelegramSender


class _Resp:
    def __init__(self, status, body=None, raw=None):
        self.status_code = status
        self._body = body
        self._raw = raw

    def json(self):
        if self._raw is not None:
            raise ValueError("not json")
        return self._body


class _Session:
    def __init__(self, script):
        self.script = list(script)
        self.calls = 0

    def post(self, url, json=None, timeout=None):
        self.calls += 1
        item = self.script.pop(0)
        if isinstance(item, Exception):
            raise item
        return item


def _sender(script, retries=2):
    return TelegramSender("123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA", "42", timeout_seconds=1, max_retries=retries, session=_Session(script))


def test_success_requires_ok_true_and_message_id():
    r = _sender([_Resp(200, {"ok": True, "result": {"message_id": 77}})]).send("hi")
    assert r.sent and r.message_id == 77 and r.attempts == 1


def test_200_without_ok_is_failed_not_sent():
    r = _sender([_Resp(200, {"ok": False, "description": "weird"})]).send("hi")
    assert r.status == "failed"


def test_read_timeout_is_ambiguous_and_not_retried():
    s = _sender([requests.exceptions.ReadTimeout(), _Resp(200, {"ok": True, "result": {"message_id": 1}})])
    r = s.send("hi")
    assert r.status == "ambiguous" and r.attempts == 1


def test_connect_timeout_retries_then_succeeds(monkeypatch):
    monkeypatch.setattr("time.sleep", lambda s: None)
    r = _sender([requests.exceptions.ConnectTimeout(), _Resp(200, {"ok": True, "result": {"message_id": 5}})]).send("hi")
    assert r.sent and r.attempts == 2


def test_429_respects_retry_after_then_5xx_then_fail(monkeypatch):
    waits = []
    monkeypatch.setattr("time.sleep", lambda s: waits.append(s))
    r = _sender([_Resp(429, {"ok": False, "parameters": {"retry_after": 3}}), _Resp(502, raw=True), _Resp(503, raw=True)]).send("hi")
    assert r.status == "failed" and r.attempts == 3 and waits[0] == 3


def test_4xx_is_definitive_failure_no_retry():
    r = _sender([_Resp(401, {"ok": False, "description": "Unauthorized"})]).send("hi")
    assert r.status == "failed" and r.attempts == 1 and "Unauthorized" in r.error


def test_error_text_never_contains_token(caplog):
    from xau_signals.log import redact
    assert "123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA" not in redact("url https://api.telegram.org/bot123456789:AAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAAA/sendMessage failed")
