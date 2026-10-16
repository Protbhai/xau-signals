# Status (16 Oct 2026, 22:30 IST)

## Operational (built and tested)

- Engine: fetch → validate → evaluate → gate → deliver → record. 51 automated tests pass
  (data integrity, session boundaries, 3-alert cap, dedup, cooldown, freshness, slot dedup,
  at-most-once delivery, failure alert, strategies, outcomes, replay).
- Providers: Binance (research), Yahoo GC=F (fallback), Twelve Data (live; key not yet set),
  CSV (research), Dukascopy downloader (research; blocked today).
- Replay backtester and comparison/analysis scripts; results in `docs/research/`.
- Private repo `Protbhai/xau-signals`; production workflow `run.yml` in **paper** mode; probe
  workflow measuring scheduler lag and reachability (time-boxed, every 15 min).
- Local paper check ran end-to-end against live Binance data (NO_SETUP at 22:21 IST, outside
  the session, as expected).

## Experimental

- Strategy choice: `benchmark_v1` on the evidence in `docs/research/RESULTS.md`. No tuning done.
- Forward tracking exists (`decisions.jsonl`, `deliveries.jsonl`, `outcomes.jsonl`) but has no
  live-series data yet.

## Unverified / open

- Twelve Data free plan: does it serve XAU/USD 5min/1h, and how are candles stamped? Needs the
  owner's free key. Until then every production run records `DATA_UNAVAILABLE`.
- Real scheduler cadence on GitHub (probe running; first dispatch-to-run lag 97 s) and the
  external pinger path (needs the owner's cron-job.org setup).
- Telegram delivery on the owner's phone (needs bot token + chat id as repo secrets).
- Spot robustness check on Dukascopy (download throttled/503 on 16 Oct; retry slowly).
- Holiday calendar in `config/closures.json` (research report pending; two dates placeholder).
- Costs (spread/slippage) for the owner's broker: unverified; sensitivity only.

## Not ready for live alerts

Code tests pass, but strategy validity on the live series, data freshness in production and
delivery reliability are all unmeasured. Promotion criteria: `docs/DESIGN.md`.
