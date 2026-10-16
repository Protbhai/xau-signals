# xau-signals

XAU/USD direction-and-entry **notification** system for one trading window,
**09:00–15:00 Asia/Kolkata**, built from scratch. It sends at most three
*conditional* setup observations per session to Telegram; it never trades.

Status: **paper / observation mode**. See `docs/STATUS.md` for what is
operational, experimental and unverified, and `docs/ARCHITECTURE.md` for the
design. Research reports are in `docs/research/`.

## Quick start (local, Windows PowerShell or Git Bash)

```bash
python -m venv .venv && .venv/Scripts/python -m pip install -e ".[dev]"
.venv/Scripts/python -m pytest
.venv/Scripts/python -m xau_signals run --force      # one paper check now
```

Secrets are read from the environment only (`.env.example`). Nothing here
prints or stores them.
