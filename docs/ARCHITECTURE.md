# Architecture

```
 scheduler(s)  ──►  GitHub Actions job (ubuntu, Python 3.12)
   cron-job.org ping (primary)          │
   GitHub cron (backup)                 ▼
                           xau_signals.engine.run_once
                           ├─ providers/*     fetch 1h + 5m candles          (Twelve Data | Yahoo | Binance | CSV)
                           ├─ candles.validate finite, ordered, deduped, completed, gaps classified, freshness
                           ├─ strategies/*    bias + setup → Evaluation(state, Setup)
                           ├─ notify/gate     session window · cap 3 · dedup · cooldown · freshness recheck
                           ├─ notify/telegram reserve → send → record (sent | ambiguous | failed)
                           ├─ state.json      atomic write under a lock; one effective run per 5-min slot
                           └─ data/tracking/  decisions.jsonl · deliveries.jsonl · outcomes.jsonl
                           state + tracking committed back to the repo after every run
```

## Stack and tradeoffs

- **Python 3.12+, standard library + `requests`.** Chosen because the research toolkit (replay,
  resampling, comparison) and the production engine are the *same code*; the backtest exercises
  the real gate, cap and dedup. Cost: it cannot run on Cloudflare Workers Free (JS/TS; Python
  Workers' 10 ms CPU fit is unverified). If GitHub's scheduler proves too unreliable even with
  an external pinger, the documented upgrade path is a TypeScript port of `engine` + `gate` +
  `benchmark` for Workers, verified against golden decision files produced by the Python replay.
- **GitHub Actions + external pinger.** Free, no card, secrets as repo secrets, state persisted by
  committing back. Measured dispatch-to-run lag: ~97 s (one sample; the probe workflow keeps
  measuring). GitHub's own cron is documented as best-effort and is the backup trigger only.
  Budget: private repos get 2,000 minutes/month, billed per started minute; ~76 session runs a
  weekday ≈ 1,700 min/month, so CI stays manual and the probe is time-boxed.
- **State in the repo.** Simple, inspectable, versioned, free. Two pushes racing is handled by
  the `concurrency` group plus the engine's slot check; a lost push loses at most one run's record,
  never an alert decision (the reservation is written before the send).
- **No database, no server, no broker connection.**

## Data (decision, 16 Oct 2026)

| role | source | why |
|---|---|---|
| live | **Twelve Data `XAU/USD`** (free key) | only real-time *spot* series reachable from US-hosted free runners (probe: HTTP 401 without key = reachable). Unverified until a key exists: free-plan access to XAU/USD and candle stamping. |
| live fallback | Yahoo `GC=F` | keyless but COMEX futures, ~10 min late, unofficial, and the runner got HTTP 429 to a bare request |
| research | Binance `XAUUSDT` perp 1m → 5m/1h, 2025-12-11 → now | keyless, real time, deep; **HTTP 451 (geo-blocked) from US runners**, so it cannot be the live source |
| research cross-check | Dukascopy spot BID 1m | real spot; connection-level throttling blocked the download on 16 Oct (retry later, slowly) |

Consequence: the backtest series (Binance perp) is **not** the live series (Twelve Data spot).
Both track the same market within a $5–25 basis, and every rule is expressed in ATR-relative
terms, but this is a known gap: paper-mode forward tracking on the live series is the check.

## Time

Internals are UTC-aware `datetime`s. The session, the alert cap and every user-facing string are
IST (`Asia/Kolkata`, no DST). Gold closures are computed in `America/New_York` (daily 17:00–18:00
break, Fri 17:00 → Sun 18:00 weekend) plus `config/closures.json` for full-day closures.

## Modes

`XAU_MODE=paper` (default): everything runs, the gate consumes slots exactly as live, the message
is recorded and, if Telegram is configured, sent with a `[PAPER — would have sent]` prefix.
`XAU_MODE=live`: setup alerts go out as-is. Failure alerts (data down ≥ 3 checks in a session) go
out in both modes when Telegram is configured.

## Files

- `src/xau_signals/` engine, providers, strategies, notify, state, tracking, replay, cli
- `config/default.toml` all parameters; `config/closures.json` full-day closures
- `research/` fetch_history.py, compare.py; `docs/research/` reports and result JSONs
- `state/state.json` live state; `data/tracking/*.jsonl` forward record
- `.github/workflows/run.yml` production; `probe.yml` infrastructure measurement (time-boxed)
