# Status (16 Oct 2026, 22:55 IST)

## Operational (built and tested)

- Engine: fetch → validate → evaluate → gate → deliver → record. 51 automated tests pass
  (data integrity, session boundaries, 3-alert cap, dedup, cooldown, freshness, slot dedup,
  at-most-once delivery, failure alert, strategies, outcomes, replay).
- Providers: Twelve Data XAU/USD (live, VERIFIED from GitHub 16 Oct 17:19Z: real-time 5m/1h, open-time UTC
  stamps, no volume, 5000 bars/call), Binance (research), Yahoo GC=F (fallback), CSV (research),
  Dukascopy downloader (research; blocked today).
- Telegram delivery VERIFIED from GitHub (notify-test: ok=true, message_id 3). Secrets set: bot token,
  chat id, Twelve Data key. XAU_MODE=paper.
- Forced production run from GitHub with real data: fetch -> validate (fresh) -> NO_SETUP, state committed.
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

- Real scheduler cadence: GitHub cron fired 0 times in its first 56 min (probe continues over the
  weekend). The cron-job.org pinger is configured and VERIFIED (dispatch 17:35:32Z -> run start 17:35:45Z,
  13 s). Owner to confirm its schedule is restricted to Mon-Fri 03:15-09:40 UTC (minutes budget).
- Telegram: owner confirmed the test message arrived on the phone (16 Oct 22:49 IST).
- Spot robustness check on Dukascopy (download throttled/503 on 16 Oct; retry slowly).
- Holiday calendar in `config/closures.json` (research report pending; two dates placeholder).
- Costs (spread/slippage) for the owner's broker: unverified; sensitivity only.

## Not ready for live alerts

Code tests pass and the pipeline is proven once end to end. Strategy validity on the live series
(paper period), scheduler cadence and delivery reliability over time are still unmeasured. Promotion criteria: `docs/DESIGN.md`.

## Incident 16 Oct 23:50 IST (evening pipeline test)

First paper alert (DOWN pullback, trigger 4163.53) was delivered to Telegram, but the run's
`state.json`/tracking commit was lost: the external pinger (running round the clock, unrestricted)
had committed `state.json` seconds earlier, `git pull --rebase` conflicted and the retry loop could
not recover. Effect: the alert record (and a 23:45 "forming" decision) vanished from the repo, which
breaks at-most-once accounting if a setup were still live. No duplicate was sent (the setup expired
at 00:20 IST and the session date rolled). Fixes pushed: (1) a skipped run never consumes the 5-minute
slot; (2) persist step keeps this run's `state.json` on conflict, merges append-only logs by union,
and fails the job loudly if the push still fails. Residual risk: two *effective* runs in one slot on
different runners can still race; the GitHub concurrency group serialises jobs, and the pinger's
schedule must be restricted to the session window. Verify on the next double-trigger slot.
