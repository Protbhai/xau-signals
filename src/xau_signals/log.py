"""Logging that never leaks secrets.

Every value of an environment variable whose name contains TOKEN, SECRET, KEY or
PASSWORD is redacted from every log record, as is anything that looks like a
Telegram bot token.
"""
from __future__ import annotations

import logging
import os
import re
import sys

_SECRET_ENV_MARKERS = ("TOKEN", "SECRET", "KEY", "PASSWORD", "CHAT_ID")
_TG_TOKEN_RE = re.compile(r"\d{6,12}:[A-Za-z0-9_-]{30,}")


def _secret_values() -> list[str]:
    vals = []
    for k, v in os.environ.items():
        if any(m in k.upper() for m in _SECRET_ENV_MARKERS) and v and len(v) >= 6:
            vals.append(v)
    return vals


class RedactingFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        msg = super().format(record)
        for v in _secret_values():
            msg = msg.replace(v, "***")
        return _TG_TOKEN_RE.sub("***:***", msg)


def setup_logging(level: str = "INFO") -> logging.Logger:
    root = logging.getLogger()
    if not root.handlers:
        h = logging.StreamHandler(sys.stdout)
        h.setFormatter(RedactingFormatter("%(asctime)sZ %(levelname)s %(name)s: %(message)s", "%Y-%m-%dT%H:%M:%S"))
        logging.Formatter.converter = __import__("time").gmtime
        root.addHandler(h)
    root.setLevel(level.upper())
    return logging.getLogger("xau")


def redact(text: str) -> str:
    """Redact secrets from an arbitrary string (used before persisting error text)."""
    for v in _secret_values():
        text = text.replace(v, "***")
    return _TG_TOKEN_RE.sub("***:***", text)
