# Deployment, operation and rollback

Everything below is free. Nothing here needs a card, a broker, or a paid plan.

## 0. What already exists

- Private repo `github.com/Protbhai/xau-signals` with the code, `run.yml` (production) and
  `probe.yml` (measurement). Default mode is **paper**.

## 1. Manual steps for the owner (one time)

1. **Telegram bot**: in Telegram, talk to `@BotFather` → `/newbot` → copy the token. Send the
   new bot one message, then open `https://api.telegram.org/bot<TOKEN>/getUpdates` in a browser
   and read `chat.id`. Do not paste the token anywhere except the GitHub secret below.
2. **Twelve Data free key**: sign up at twelvedata.com (free Basic plan, no card). Copy the key.
   This is a data account, not a financial account; no trading permissions are involved.
3. **GitHub secrets** (repo → Settings → Secrets and variables → Actions → *Secrets*):
   `XAU_TELEGRAM_BOT_TOKEN`, `XAU_TELEGRAM_CHAT_ID`, `XAU_TWELVEDATA_KEY`.
   *Variables*: `XAU_MODE` = `paper` (leave until promotion), optional `XAU_PROVIDER`.
4. **External pinger (primary trigger)**: create a free account at cron-job.org. Create a
   fine-grained GitHub personal access token scoped to this one repo with *Actions: read and
   write* only, and store it **only** in the cron-job.org job header
   `Authorization: Bearer <token>`. Job: `POST https://api.github.com/repos/Protbhai/xau-signals/actions/workflows/run.yml/dispatches`
   body `{"ref":"main"}`, header `Accept: application/vnd.github+json`, every 5 minutes,
   03:15–09:40 UTC, Mon–Fri. (Tradeoff: a third party holds a narrowly scoped token. Without it,
   GitHub's own cron is the only trigger and is best-effort.)
5. Run `notify-test` once from the Actions tab (workflow_dispatch of a tiny job) or locally with
   the secrets in the environment: `python -m xau_signals notify-test`. Confirm the message
   arrives on the phone.

## 2. First deployment (paper)

Already live in paper mode once step 3 is done; until then every run records
`DATA_UNAVAILABLE` (no key) and sends nothing. Watch:
- `state/state.json` → `runs[]` (lag per slot), `session.alerts`.
- `data/tracking/decisions.jsonl` and `deliveries.jsonl`.
- Actions tab → run durations (minutes budget).

## 3. Promotion to live

Criteria are in `docs/DESIGN.md`. Promotion = set variable `XAU_MODE=live`. One variable, one
change. Record the date, strategy name@version and the config commit hash in `docs/STATUS.md`.

## 4. Rollback

- Stop alerts: set `XAU_MODE=paper` (next run obeys) or disable the `run` workflow
  (Actions → run → ⋯ → Disable workflow) for an immediate stop.
- Roll back code: `git revert <commit>` on `main`; the next run uses it. State files are
  forward-compatible (`schema` field); never hand-edit `state.json` during a session.
- Roll back a strategy: `[strategy] name` in `config/default.toml` back to `benchmark_v1`.
  Every alert carries `name@version`, so the forward record stays attributable.

## 5. Operations

- **Minutes budget**: ~76 runs/weekday × 1 billed minute. Check *Settings → Billing* monthly.
  If it tightens: make the repo public (code and state become public; secrets stay secret) or
  port the runner to Cloudflare Workers (see ARCHITECTURE.md).
- **Duplicate triggers** (pinger + cron in the same 5-minute slot): the second is a no-op by
  design (`DUPLICATE_SLOT` in `runs[]`).
- **Data outage**: after 3 consecutive failed checks inside the session one failure message is
  sent (both modes); nothing else until the next session.
- **Secrets**: never in files, logs (redacted) or messages. Rotate by replacing the GitHub secret.
- **Weekend / holidays**: no fetches outside the session; `config/closures.json` lists full-day
  closures (see `docs/research/market-hours.md` for the verified calendar).

## 6. Local run

```bash
.venv/Scripts/python -m xau_signals run --force          # one check now (paper unless env says live)
.venv/Scripts/python -m xau_signals status
.venv/Scripts/python -m xau_signals replay --bias-csv data/raw/binance_XAUUSDT_1h.csv --setup-csv data/raw/binance_XAUUSDT_5m.csv --symbol XAUUSDT --delay 2
```
