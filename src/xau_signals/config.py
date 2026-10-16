"""Configuration: TOML file + environment. Secrets come only from the environment."""
from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class Settings:
    raw: dict[str, Any]
    root: Path
    mode: str = "paper"
    telegram_token: str | None = field(default=None, repr=False)
    telegram_chat_id: str | None = field(default=None, repr=False)

    def __getitem__(self, section: str) -> dict[str, Any]:
        return self.raw[section]

    def get(self, section: str, key: str, default: Any = None) -> Any:
        return self.raw.get(section, {}).get(key, default)

    @property
    def telegram_configured(self) -> bool:
        return bool(self.telegram_token and self.telegram_chat_id)

    def path(self, rel: str) -> Path:
        p = Path(rel)
        return p if p.is_absolute() else self.root / p


def load_settings(config_path: str | os.PathLike | None = None, root: str | os.PathLike | None = None) -> Settings:
    root_p = Path(root) if root else Path(__file__).resolve().parents[2]
    cfg = Path(config_path or os.environ.get("XAU_CONFIG") or (root_p / "config" / "default.toml"))
    if not cfg.is_absolute():
        cfg = root_p / cfg
    with open(cfg, "rb") as f:
        raw = tomllib.load(f)
    mode = os.environ.get("XAU_MODE", "paper").strip().lower()
    if mode not in ("paper", "live"):
        raise ValueError(f"XAU_MODE must be paper or live, got {mode!r}")
    # Test-only overrides of the session window (HH:MM IST). Production leaves these unset.
    for env_key, cfg_key in (("XAU_SESSION_START", "start"), ("XAU_SESSION_END", "end")):
        v = os.environ.get(env_key, "").strip()
        if v:
            if len(v) != 5 or v[2] != ":" or not (v[:2] + v[3:]).isdigit():
                raise ValueError(f"{env_key} must be HH:MM, got {v!r}")
            raw.setdefault("session", {})[cfg_key] = v
    return Settings(
        raw=raw,
        root=root_p,
        mode=mode,
        telegram_token=os.environ.get("XAU_TELEGRAM_BOT_TOKEN") or None,
        telegram_chat_id=os.environ.get("XAU_TELEGRAM_CHAT_ID") or None,
    )
