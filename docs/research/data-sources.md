# XAU/USD candle data sources: verified probe report

Probe window: **Fri 16 Oct 2026, 16:26:32 to 16:33:56 UTC** (`date -u` run before each batch; local clock checked against Binance `serverTime`, off by under 1 s).
Gold was trading at probe time (Friday mid-session). All requests used `curl -s --max-time 20`. No accounts were created and no API keys were used.

Price at about 16:28 UTC, to show how far apart the series are:
Swissquote spot mid 4165.8 · gold-api.com 4167.9 · Binance PAXGUSDT 4165.1 · Binance XAUUSDT perp 4172.8 · Yahoo GC=F 4187.6 (10 min delayed).
**Futures run about $21 above spot, and the Binance perp runs about $7 above spot.**

## Summary table

| Source | No key? | Instrument / price type | Intervals (verified) | History measured | Freshness at probe | Candle timestamp | Last candle | Limits / ToS |
|---|---|---|---|---|---|---|---|---|
| **Yahoo chart v8 `GC=F`** | Yes | COMEX gold **futures**, continuous front month, last trade, USD | 1m, 5m, 1h, 1d (15m untested) | 1m: 7d per call, `period1` 29 days back worked. 5m `range=60d`: 2026-08-07 → now. 1h 60d: same. 1d 2y: 2024-10-16 → now | **~10 min delayed** (`regularMarketTime` 16:16:30 at 16:26:32) | Epoch seconds = bar **open**, UTC-aligned (:00/:05). 1d bars stamped 04:00 UTC (midnight New York) | Forming. A **synthetic extra row** at `regularMarketTime` (O=H=L=C, vol 0) is appended and must be dropped | Unofficial and undocumented. Can break or block without notice. Yahoo ToS ≠ licensed data |
| Yahoo `XAUUSD=X` | n/a | n/a | **HTTP 404 "No data found, symbol may be delisted"** | none | n/a | n/a | n/a | Dead |
| **Binance USDⓈ-M `XAUUSDT` perp** (`fapi/v1/klines`) | Yes | Gold-referenced **perpetual futures** (USDT), last trade | 1m, 5m, 1h tested | **1m from 2025-12-11 08:05 UTC** (first kline) → now | **Real time** (16:25 bar forming at 16:29:07) | `[openTime ms, O,H,L,C, vol, closeTime ms, ...]`, so the label is the **open** time; closeTime = open + interval − 1 ms | Forming. Complete when `closeTime < now` | Official documented public API. Trades **24/7**: weekend bars are flat and synthetic (Sat 10 Oct 12:00 1h range was $0.15). About +$7 premium to spot |
| Binance spot `PAXGUSDT` | Yes | Paxos tokenised gold (1 token = 1 oz), last trade | 5m tested | not measured | Real time | Same as above | Forming | Official API. Thin: 34–439 trades per 5m, so wicks are noisy. Trades 24/7 |
| **Dukascopy datafeed** (`.bi5`) | Yes | Dukascopy Bank **spot XAU/USD**, separate BID and ASK files (bank quotes, not exchange) | 1m candles per day file (`BID_candles_min_1.bi5`); hourly tick files | 1 day decoded (2026-10-15, 1440 rows). Depth not measured | Today's 15:00 hour tick file existed at 16:31 (so an hour file appears ≤ ~30 min after the hour) | Seconds offset from day start UTC = bar **open** | Day files are only final after the day ends | Free but **rate-limits hard**: 1 timeout, 1 reset and 1 HTTP 429 in about 5 requests. Not an API, and redistribution terms unclear |
| Swissquote public BBO | Yes | Swissquote broker **spot bid/ask**, 3 platforms × spread profiles | **Snapshot only, no candles** | none | `ts` 16:28:17 UTC (seconds old) | n/a | n/a | Undocumented public endpoint |
| gold-api.com `/price/XAU` | Yes | "Real-time" spot reference, vendor sources unnamed | Snapshot verified. History/OHLC per docs | not tested | `updatedAt` 16:28:08Z | n/a | n/a | Docs: real-time unlimited. **History/OHLC 10 req/hour free**, minute/hour aggregation listed under Premium ($10/mo) |
| Stooq | **Blocked** | spot XAUUSD (per site) | none returned | none | n/a | n/a | n/a | All of `i=d`, `i=5` and `i=60` returned a **JS proof-of-work bot check** (HTML, HTTP 200). Solving it would be bot-bypass, so not done. Reports say an API key obtained via CAPTCHA has been required since early 2026 |
| Twelve Data | Key needed | `XAU/USD` spot (vendor-aggregated) | per docs: 1min…1day | not tested | not tested | not tested | not tested | Free Basic: **8 credits/min, 800/day** (pricing page). Commodities are listed only from the Grow tier, but XAU/USD is the commodity **"trial symbol"**, so free access is likely but **unverified** |
| Alpha Vantage | Key needed | `FX_INTRADAY` is marked **Premium**. `GOLD_SILVER_HISTORY` is daily/weekly/monthly (third-party summary) | none intraday free | n/a | n/a | n/a | n/a | Free: **25 requests/day**. Not usable for intraday |
| Finnhub | Key needed | `OANDA:XAU_USD` forex candles | n/a | n/a | n/a | n/a | n/a | Unkeyed: 401. Free-plan access to forex candles **not confirmed** in docs. Treat as unverified or likely paid |
| Massive (ex-Polygon) `C:XAUUSD` | Key needed | forex aggregates (BBO-derived) | n/a | n/a | n/a | n/a | n/a | Unkeyed: 401. Free Basic per secondary sources: 5 calls/min, end-of-day, 2y. Forex minute flat files "Not included" on Basic. **Not useful free** |
| FCS API | Key needed | forex/commodity | n/a | n/a | n/a | n/a | n/a | Free: 500 credits/month, 3/min, **60-minute cache delay**, 1y history, 300 candles per call |
| GoldAPI.io | Key needed | spot | n/a | n/a | n/a | n/a | n/a | Unkeyed: 403 "No API Key provided". Free limits **could not be read** (page did not render) |
| metals.dev | Key needed | spot | n/a | n/a | n/a | n/a | n/a | Free: **100 requests/month**, 60 s delay. Unusable for 5-min polling |
| metals.live | Dead | n/a | n/a | n/a | n/a | n/a | n/a | Connection timed out twice (20 s) |
| OANDA v20 | Account token | broker bid/ask/mid | n/a | n/a | n/a | n/a | n/a | Unkeyed: 401. Needs a free practice account plus token (not created) |

## Notes per source

**Yahoo GC=F (verified)**
- Meta: `currency USD`, `exchangeName CMX`, `instrumentType FUTURE`, `exchangeTimezoneName America/New_York`, `gmtoffset -14400`. `validRanges` lists 1d … max.
- This is the **futures front month**, not spot. Expect a $15–30 contango basis and a **price jump at contract roll**. Which contract GC=F maps to was not verified.
- **Delay:** COMEX data is about 10 minutes behind. With a 5-min cadence, the newest *completed* 5m bar is 10–15 minutes old.
- **Completed-bar rule:** drop the last row if `ts % interval != 0`. That row is the synthetic `regularMarketTime` row. Then the remaining last bar is complete only if `ts + interval <= regularMarketTime`.
- **Nulls:** Yahoo pads the 04:00→03:59 UTC "day" grid with `null` OHLC rows.
  - 5m/5d: 49 null bars, mostly 21:00–21:55 every day (the CME break).
  - 1m/7d: 1761 nulls, including Fri 21:00 → Sun 22:09 around the weekend, plus 2 to 10-minute null runs mid-session (e.g. Fri 16 Oct 14:10–14:19).
  - 1d/2y: null bars on US holidays (2025-05-26, 2025-06-19).
- 1d volume repeated exactly on 10-14 and 10-15 (191279). Treat Yahoo volume as unreliable.
- **Friday close:** the last real 1m bar on Fri 9 Oct was 20:59 UTC. It is present.
- Rate limit: not documented. 7 requests total caused no problems.

**Binance XAUUSDT (verified)**
- The 5m klines carry ~1,200–4,100 contracts and ~4,000–8,000 trades per bar, so liquidity is good during the week.
- First kline was 2025-12-11. A press release says TradFi gold perps launched 5 Jan 2026. That conflict is unresolved: possibly an earlier listing under the same symbol.
- Per the press release, off-hours the price index is frozen and the mark price is EWMA-smoothed. **Weekend bars are not a gold market.** Filter them, and expect a gap or jump at Sunday reopen.
- Max `limit` 1500 per call (secondary source). Weight tiers are unverified. Read the `X-MBX-USED-WEIGHT` response header.
- Not tested: whether the endpoint is reachable from the production server's network or region.

**Dukascopy (one file decoded)**
- `https://datafeed.dukascopy.com/datafeed/XAUUSD/YYYY/MM-1/DD/BID_candles_min_1.bi5`. **The month is 0-based.**
- LZMA-compressed. Each record is 24 bytes, big-endian `>5If`: time offset (s), open, close, low, high (all ×0.001), then volume.
- The 2026-10-15 file had 1440 rows, including 60 flat zero-volume filled bars at 21:00–21:59 UTC. Missing minutes are forward-filled, not omitted, so the `vol==0` filter matters.
- Python: `dukascopy-python` 4.0.1 (Apr 2025; tick/minute/hour, BID/ASK), `tickterial`, `tick-vault`, and the older `duka`. JS: `dukascopy-node` (not checked).
- History depth was not measured. "Back to the mid-2000s" is commonly claimed but **unverified**.
- Must be throttled: stay at least a few seconds between files and use one connection.

## Market hours seen in the data (EDT season)

- **Daily break:** 21:00–22:00 UTC, seen in Yahoo nulls and in Dukascopy flat zero-volume bars.
- **Weekend:** last bar Fri 20:59 UTC; reopen Sun 22:00 UTC. In Yahoo 1m, the first non-null bar on Sun 11 Oct was 22:10.
- **Inference, not observed:** after US DST ends on Sun 1 Nov 2026, the break and weekend edges move one hour later, to 22:00–23:00 UTC with the Friday close at 22:00.
- The 03:30–09:30 UTC alert window falls entirely inside the Mon–Fri session. There is no break in it.

## Samples (trimmed)

Yahoo `GC=F` 5m, probe at 16:26:32 UTC:
```
{"symbol":"GC=F","currency":"USD","exchangeName":"CMX","instrumentType":"FUTURE",
 "exchangeTimezoneName":"America/New_York","gmtoffset":-14400,
 "regularMarketTime":1792167390,"regularMarketPrice":4187.6,"dataGranularity":"5m","range":"5d"}
timestamp[-3:] [1792167000, 1792167300, 1792167390]   # 16:10, 16:15 (forming), 16:16:30 synthetic
open  [4185.5, 4189.6, 4187.6]
high  [4190.9, 4190.9, 4187.6]
low   [4185.1, 4186.9, 4187.6]
close [4189.8, 4187.5, 4187.6]
volume [1935, 235, 0]
```
Yahoo `XAUUSD=X`: `{"chart":{"result":null,"error":{"code":"Not Found","description":"No data found, symbol may be delisted"}}}`

Binance `fapi/v1/klines?symbol=XAUUSDT&interval=5m&limit=3`, probe at 16:29:07 UTC:
```
[[1792167300000,"4176.65","4177.88","4171.68","4173.07","2356.524",1792167599999,...,7854,...],
 [1792167600000,"4173.08","4174.97","4169.66","4174.45","4133.125",1792167899999,...,7951,...],
 [1792167900000,"4174.45","4175.22","4171.96","4172.84","1231.762",1792168199999,...,4178,...]]   # 16:25 bar, forming
earliest 1m: [1765440300000,"4217.00","4300.00","4100.00","4235.00",...]   # 2025-12-11 08:05 UTC
```
Swissquote BBO (first platform), ts 16:28:17.561 UTC:
```
[{"topo":{"platform":"SwissquoteCapitalMarkets","server":"Live7"},"spreadProfilePrices":[
  {"spreadProfile":"premium","bidSpread":25.40,"askSpread":25.40,"bid":4165.436,"ask":4166.094}, ...],
  "ts":1792168097561}, ...]
```
Dukascopy `XAUUSD/2026/09/15/BID_candles_min_1.bi5` (16,791 bytes → 1440 records):
```
00:00 O 4111.725 H 4113.965 L 4111.315 C 4112.395 vol 0.0364
20:59 O 4170.695 H 4171.685 L 4170.465 C 4171.185 vol 0.0253
21:00 O 4171.185 H 4171.185 L 4171.185 C 4171.185 vol 0.0     # daily break, filled
```
Stooq (all three URLs): HTML `This site requires JavaScript to verify your browser` with a SHA-256 proof-of-work script.

## Recommendation

**(a) Live polling, 5-min cadence, 03:30–09:30 UTC**
1. **Binance `XAUUSDT` perp klines.** Verified keyless, real time, official API, and the closed-bar flag is clean (`closeTime < now`). Caveat: it is a perp about $7 over spot. Ignore weekend bars.
2. **Twelve Data `XAU/USD` 5min**, if a free signup is acceptable. It is a true spot series, and 72 calls per 6-hour window fits easily in 8/min and 800/day. **Unverified:** that XAU/USD is served on the Basic key, and how its candles are stamped.
3. **Yahoo `GC=F`.** Works keyless but is 10 min delayed, futures-priced, and unofficial. Use only as a fallback.

Add-on for any choice: a Swissquote BBO snapshot each poll gives a real spot bid/ask to quote in the alert text and to monitor the basis. This is snapshot only, so it cannot build OHLC at a 5-min cadence.

**(b) Historical backtest, 1m/5m/15m/1h**
1. **Dukascopy BID (and ASK) 1m candles.** Spot, UTC, free, deep. Resample to 5m/15m/1h yourself. Download once, slowly, and cache locally.
2. **Binance `XAUUSDT` 1m** from 2025-12-11 (about 10 months). This is the **same series as live option (a)1**, which avoids a backtest/live price mismatch. That is the strongest reason to pair them.
3. **Yahoo `GC=F`**: 1m about 30 days, 5m/1h about 70 days measured. Futures with roll jumps, so use only for cross-checks.

**(c) Fallback:** Yahoo `GC=F` for candles (subtract the measured basis, allow for the 10-min lag), plus gold-api.com or Swissquote for a spot sanity price. If Binance is unreachable from the server, Twelve Data becomes primary.

**Key design rule:** backtest and live on the same series, or express signals in relative terms (percent moves, indicators). Spot (Dukascopy) vs perp (Binance) vs futures (Yahoo) differ by $7–25 at any moment.

**Unverified items:**
- Twelve Data free access to XAU/USD and its timestamp convention.
- Finnhub, GoldAPI.io and Massive free-tier details.
- Yahoo 15m depth, 1h beyond 70 days, and which contract GC=F maps to.
- Dukascopy history depth and same-day minute-file availability (the probe got a 429).
- Binance weight tiers, the cause of the Dec 2025 first kline, and reachability from the production host.
- Post-DST hours, which are inferred.
