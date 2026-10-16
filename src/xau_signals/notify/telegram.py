"""Telegram delivery with explicit success semantics.

Delivery is claimed ONLY when the Bot API answers HTTP 200 with {"ok": true} and
a message_id. Anything else is "failed" (we know nothing left Telegram's side,
e.g. connection refused before the request was sent, or a 4xx with a clear
description) or "ambiguous" (timeout / connection dropped after sending: the
message may or may not exist). Ambiguous results are never retried for setup
alerts, because the Bot API has no idempotency key; the brief asks for honesty
over duplicates.
Retries: only for 429 (respecting retry_after) and 5xx, up to max_retries.
"""
from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Protocol

import requests

log = logging.getLogger("xau.telegram")


@dataclass
class DeliveryResult:
    status: str                  # sent | failed | ambiguous
    message_id: int | None = None
    http_status: int | None = None
    error: str | None = None
    attempts: int = 0
    elapsed_seconds: float = 0.0

    @property
    def sent(self) -> bool:
        return self.status == "sent"


class Sender(Protocol):
    def send(self, text: str) -> DeliveryResult: ...


class TelegramSender:
    def __init__(self, token: str, chat_id: str, timeout_seconds: float = 15, max_retries: int = 2, session: requests.Session | None = None):
        if not token or not chat_id:
            raise ValueError("telegram token and chat_id are required")
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id
        self._timeout = timeout_seconds
        self._max_retries = max_retries
        self._http = session or requests.Session()

    def send(self, text: str) -> DeliveryResult:
        t0 = time.monotonic()
        payload = {"chat_id": self._chat_id, "text": text, "parse_mode": "HTML", "disable_web_page_preview": True}
        attempts = 0
        last_err = None
        while attempts <= self._max_retries:
            attempts += 1
            try:
                r = self._http.post(self._url, json=payload, timeout=self._timeout)
            except requests.exceptions.ConnectTimeout as e:
                last_err = f"connect timeout: {e.__class__.__name__}"
                # Nothing was sent; a retry is safe.
                time.sleep(min(2 * attempts, 6))
                continue
            except requests.exceptions.ConnectionError as e:
                # Could be refused (nothing sent) or dropped mid-flight (ambiguous). Be honest: ambiguous.
                return DeliveryResult("ambiguous", error=f"connection error: {e.__class__.__name__}", attempts=attempts, elapsed_seconds=time.monotonic() - t0)
            except requests.exceptions.ReadTimeout as e:
                return DeliveryResult("ambiguous", error=f"read timeout after send: {e.__class__.__name__}", attempts=attempts, elapsed_seconds=time.monotonic() - t0)
            except requests.exceptions.RequestException as e:
                return DeliveryResult("failed", error=f"request error: {e.__class__.__name__}", attempts=attempts, elapsed_seconds=time.monotonic() - t0)

            if r.status_code == 200:
                try:
                    data = r.json()
                except ValueError:
                    return DeliveryResult("ambiguous", http_status=200, error="200 but body not JSON", attempts=attempts, elapsed_seconds=time.monotonic() - t0)
                if data.get("ok") is True and isinstance(data.get("result"), dict) and "message_id" in data["result"]:
                    return DeliveryResult("sent", message_id=int(data["result"]["message_id"]), http_status=200, attempts=attempts, elapsed_seconds=time.monotonic() - t0)
                return DeliveryResult("failed", http_status=200, error=f"ok!=true: {str(data)[:200]}", attempts=attempts, elapsed_seconds=time.monotonic() - t0)

            if r.status_code == 429:
                try:
                    wait = float(r.json().get("parameters", {}).get("retry_after", 2))
                except ValueError:
                    wait = 2.0
                last_err = f"429 rate limited, retry_after={wait}"
                if attempts <= self._max_retries:
                    time.sleep(min(wait, 30))
                continue
            if 500 <= r.status_code < 600:
                last_err = f"{r.status_code} server error"
                if attempts <= self._max_retries:
                    time.sleep(min(2 * attempts, 6))
                continue
            # 4xx other than 429: definitive failure (bad token, chat not found, message too long...)
            desc = ""
            try:
                desc = str(r.json().get("description", ""))[:200]
            except ValueError:
                pass
            return DeliveryResult("failed", http_status=r.status_code, error=f"{r.status_code} {desc}", attempts=attempts, elapsed_seconds=time.monotonic() - t0)
        return DeliveryResult("failed", error=last_err or "retries exhausted", attempts=attempts, elapsed_seconds=time.monotonic() - t0)


class PaperSender:
    """Records what would have been sent. Used in paper mode and tests."""
    def __init__(self) -> None:
        self.messages: list[str] = []

    def send(self, text: str) -> DeliveryResult:
        self.messages.append(text)
        return DeliveryResult("sent", message_id=len(self.messages), http_status=200, attempts=1)
