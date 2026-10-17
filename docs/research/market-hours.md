# Gold market hours for a 09:00-15:00 IST desk

Researched 2026-10-16/17 (`date -u` = Fri 16 Oct 2026 16:26 UTC). IST = UTC+5:30, no DST.
**Trader window: 09:00-15:00 IST = 03:30-09:30 UTC.** "Verified" = read on the cited page this session. UNVERIFIED = memory, secondary source, or not yet published.

## DST anchors (verified)
- US: DST ends **1 Nov 2026**, starts **14 Mar 2027**, ends 7 Nov 2027 (NIST rule + 2026 dates) - https://www.nist.gov/pml/time-and-frequency-division/popular-links/daylight-saving-time-dst
- UK: clocks back **25 Oct 2026**, forward **28 Mar 2027**, back 31 Oct 2027 - https://www.gov.uk/when-do-the-clocks-change
- Australia (affects RBA): AEDT until ~4 Apr 2027, from ~3 Oct 2027. UNVERIFIED.

## 1. Spot XAU/USD (OTC)
- OANDA: "Sunday approximately 5 p.m. to Friday 5 p.m. (New York time)". Metals table (GMT, winter basis): Sun-Thu 23:00-22:15 next day, Thu-Fri 23:00-22:00 - https://www.oanda.com/assets/documents/402/Hours_of_Operation_bT4prdz.pdf
- IG: spot gold "11pm Sunday to 10pm Friday (UK time)" - https://www.ig.com/uk/trading-strategies/gold-trading-hours--when-to-trade-gold-200320 . The page shows no spot daily break, only the futures break. A secondary summary of IG's dealing-hours page says 06:00-05:00 HKT, which implies a break at 21:00-22:00 UTC (UNVERIFIED).
- Pepperstone/IC Markets XAUUSD rows: could not be read (UNVERIFIED).

Rule: spot gold follows the **NY 17:00 rollover** and pauses for about 60 minutes (some brokers 15 min to 1 h).

| Period | Weekly open | Daily break | Weekly close |
|---|---|---|---|
| US DST (to 31 Oct 2026; 14 Mar to 6 Nov 2027) | Sun ~22:00 UTC = Mon 03:30 IST | ~21:00-22:00 UTC = 02:30-03:30 IST | Fri ~21:00 UTC = Sat 02:30 IST |
| US standard (1 Nov 2026 to 13 Mar 2027) | Sun ~23:00 UTC = Mon 04:30 IST | ~22:00-23:00 UTC = 03:30-04:30 IST | Fri ~22:00 UTC = Sat 03:30 IST |

The break is **never inside 09:00-15:00 IST**. From 1 Nov 2026, Monday's spot open (~04:30 IST) is about 4.5 h before your desk opens.

## 2. COMEX gold futures (GC), CME Globex (verified)
- "Sunday - Friday 6:00 p.m. - 5:00 p.m. (5:00 p.m. - 4:00 p.m. /CT) with a 60-minute break each day beginning at 5:00 p.m. (4:00 p.m. CT)" - https://www.cmegroup.com/markets/metals/precious/gold.contractSpecs.html
- In UTC: break 21:00-22:00 (CDT) / 22:00-23:00 (CST), the same as spot. GC trades continuously through 03:30-09:30 UTC, Mon-Fri.
- 2026-27 holiday events for GC, from CME's trading-hours service (https://www.cmegroup.com/trading-hours.html, times CT):

| Date | GC status |
|---|---|
| Thu 26 Nov 2026 Thanksgiving | Session for Fri trade date opened Wed 17:00. Halt/pre-open Thu 13:30, reopen 17:00. **Open in your window** |
| Fri 27 Nov 2026 | Early close 13:45 CT |
| Thu 24 Dec 2026 | Early close **12:45 CT** (18:45 UTC). Open in your window |
| **Fri 25 Dec 2026** | **No trading**. Reopens Sun 27 Dec 17:00 CT |
| Thu 31 Dec 2026 | Regular close 16:00 CT |
| **Fri 1 Jan 2027** | **No trading**. Reopens Sun 3 Jan 17:00 CT |
| Mon 18 Jan 2027 MLK / Mon 5 Jul 2027 | Open overnight; halt before the 13:30 CT pre-open. Your window is open |
| **Fri 26 Mar 2027 Good Friday** | **No trading** ("No trading for Friday March 26th trade date"). Reopens Sun 28 Mar 17:00 CT |
| Thu 25 Nov 2027 Thanksgiving | Same pattern as 2026; early close Fri 26 Nov 13:45 CT |
| **Fri 24 Dec 2027** (Christmas observed) | **No trading**. Reopens Sun 26 Dec 17:00 CT |
| Fri 31 Dec 2027 | Regular 16:00 CT close. Reopens Sun 2 Jan 2028 |
| Fri 18 Jun 2027 Juneteenth | Service data look inconsistent. UNVERIFIED |

CME says holiday hours are usually finalised about two weeks before each holiday.

## 3. London / LBMA
- Gold auctions (ICE Benchmark Administration): **10:30 and 15:00 London** - https://www.ice.com/publicdocs/Gold_Holiday_Calendar_2026.pdf
  - BST (to 25 Oct 2026; from 28 Mar 2027): AM 09:30 UTC = **15:00 IST** (the minute your window ends); PM 14:00 UTC = 19:30 IST.
  - GMT: AM 10:30 UTC = 16:00 IST; PM 15:00 UTC = 20:30 IST. Both are outside your window.
- 2026 LBMA gold auction calendar (verified, ICE PDF): no auctions on 1 Jan, 3 Apr, 6 Apr, 4 May, 25 May, 31 Aug, 25 Dec, 28 Dec. **24 Dec and 31 Dec: AM auction runs, PM has no auction.**
- I found no 2027 LBMA calendar. UK bank holidays 2027 (verified, https://www.gov.uk/bank-holidays.json): 1 Jan, 26 Mar, 29 Mar, 3 May, 31 May, 30 Aug, 27 Dec, 28 Dec. On these days the London desks are absent and auctions are normally cancelled; that last point is UNVERIFIED for 2027. Spot still trades, but liquidity is thin from London-open time.

## 4. Window vs global sessions (IST)
| Venue | Local hours | IST |
|---|---|---|
| Tokyo equities (JST, no DST) | 09:00-15:30, lunch 11:30-12:30 (UNVERIFIED) | 05:30-12:00, lunch 08:00-09:00 |
| Singapore (SGT) | 09:00 open | 06:30 |
| SGE spot (Au99.99 etc.) day session, verified https://en.sge.com.cn/eng_trading_ProductsIntroduce | 09:00-15:30 CST; night 20:00-02:30 | **06:30-13:00**; night 17:30-00:00 |
| SGE benchmark (SHAU) | 10:15 / **14:15** CST | 07:45 / **11:45** (inside) |
| SHFE gold (AU), verified https://www.shfe.com.cn/eng/reports/CalendarHolidays/TradingHours/ | 09:00-10:15, 10:30-11:30, 13:30-15:00; night 21:00-02:30 | 06:30-07:45, 08:00-09:00, **11:00-12:30**; night 18:30-00:00 |
| Frankfurt / London 08:00 open | BST/CEST to 25 Oct 2026, from 28 Mar 2027 | London **12:30**, Frankfurt 11:30 |
| Same, in winter | GMT/CET from 25 Oct 2026 | London **13:30**, Frankfurt 12:30 |
| NY / US data | 08:30 ET | 18:00 (EDT) / 19:00 (EST): outside |

Regime: 09:00-11:00 IST is late Asia (SHFE on lunch). 11:00-12:30 IST is the China afternoon plus the 11:45 SGE fix. The London/Europe open at 12:30 IST (summer) or 13:30 IST (winter) is the biggest volume step, so your last 1.5-2.5 h are the most liquid.

## 5. Scheduled events in 03:30-09:30 UTC
**Inside the window**
- **RBA**: decision at 14:30 Sydney, presser 15:30 (verified, https://www.rba.gov.au/media/index.html). AEDT: 03:30 UTC = **09:00 IST**; AEST: 04:30 UTC = 10:00 IST. Dates (https://www.rba.gov.au/schedules-events/board-meeting-schedules.html): 3 Nov and 8 Dec 2026; 9 Feb, 23 Mar, 4 May, 22 Jun, 10 Aug, 28 Sep, 2 Nov and 14 Dec 2027.
- **BoJ**: no fixed release time. Usually around 11:30-13:00 JST = 08:00-09:30 IST, with the presser at 15:30 JST = 12:00 IST. Both times UNVERIFIED. Decision days (https://www.boj.or.jp/en/mopo/mpmsche_minu/index.htm): 30 Oct and 18 Dec 2026; 22 Jan, 18 Mar, 28 Apr, 11 Jun, 22 Jul, 22 Sep, 29 Oct and 17 Dec 2027.
- **RBI**: 10:00 IST (04:30 UTC) on 4 Dec 2026 and 5 Feb 2027. This comes from secondary sources and is UNVERIFIED on rbi.org.in. It mostly moves INR/MCX, not XAU/USD.
- SGE PM fix at 11:45 IST.
- UK ONS releases at 07:00 London (11:30 IST summer / 12:30 IST winter); German data at 08:00 CET; euro-area flash PMIs around 09:00-10:00 CET. All UNVERIFIED (usual practice).

**Outside the window (before 09:00 IST)**
- China NBS PMI 09:30 CST = 01:30 UTC = 07:00 IST (https://www.financecalendar.com/?p=2090, secondary).
- RatingDog (ex-Caixin) PMI 09:45 CST = 07:15 IST.
- China CPI/PPI 09:30 CST; activity/GDP 10:00 CST = 07:30 IST. China trade data around 11:00 CST = 08:30 IST, which varies and is UNVERIFIED.
- Japan data 08:30-08:50 JST = 05:00-05:20 IST.
- SGE AM fix 07:45 IST.

**After the window**
- All US data (12:30/13:30 UTC = 18:00/19:00 IST), FOMC (around 23:30/00:30 IST) and the LBMA PM auction.

## 6. Closed vs thin in your window
- **Fully closed:** both spot and GC are shut, with no session at all.
- **Thin:** markets are open, but a major centre (London, or Japan/China) is on holiday.
- **US-only holidays** (Thanksgiving, MLK and similar) do not thin the 03:30-09:30 UTC window much.
- China holidays (SGE/SHFE closed) remove the Shanghai flow: Golden Week, Spring Festival (6 Feb 2027) and others. The 2027 dates are not published yet: UNVERIFIED.

```json
{
  "window_utc": "03:30-09:30",
  "fully_closed": [
    {"date": "2026-12-25", "reason": "Christmas; GC no trading, spot closed", "source": "https://www.cmegroup.com/trading-hours.html ; https://www.ig.com/en/help-and-support/articles/785235-holiday-and-seasonal-trading-hour-changes-for-2026"},
    {"date": "2027-01-01", "reason": "New Year; GC no trading, spot closed", "source": "https://www.cmegroup.com/trading-hours.html ; https://www.ig.com/en/help-and-support/articles/785235-holiday-and-seasonal-trading-hour-changes-for-2026"},
    {"date": "2027-03-26", "reason": "Good Friday; GC no trading (verified); spot closure UNVERIFIED for 2027 (IG closed metals on Good Friday 2026)", "source": "https://www.cmegroup.com/trading-hours.html"},
    {"date": "2027-12-24", "reason": "Christmas observed; GC no trading (verified); spot closure UNVERIFIED", "source": "https://www.cmegroup.com/trading-hours.html"}
  ],
  "thin_partial": [
    {"date": "2026-11-03", "reason": "Japan Culture Day, Tokyo shut - UNVERIFIED", "source": "UNVERIFIED (jpx.co.jp blocked)"},
    {"date": "2026-11-23", "reason": "Japan Labour Thanksgiving - UNVERIFIED", "source": "UNVERIFIED (jpx.co.jp blocked)"},
    {"date": "2026-12-24", "reason": "Christmas Eve: LBMA AM only, GC early close 12:45 CT (after window)", "source": "https://www.ice.com/publicdocs/Gold_Holiday_Calendar_2026.pdf"},
    {"date": "2026-12-28", "reason": "UK Boxing Day substitute: no LBMA auctions, London absent", "source": "https://www.ice.com/publicdocs/Gold_Holiday_Calendar_2026.pdf"},
    {"date": "2026-12-31", "reason": "New Year's Eve: LBMA AM only; Japan closed (IG notes JPX 29 Dec too)", "source": "https://www.ice.com/publicdocs/Gold_Holiday_Calendar_2026.pdf"},
    {"date": "2027-02-08", "reason": "Spring Festival week (approx 2027-02-05..12), SGE/SHFE closed - dates UNVERIFIED", "source": "UNVERIFIED"},
    {"date": "2027-03-29", "reason": "Easter Monday UK", "source": "https://www.gov.uk/bank-holidays.json"},
    {"date": "2027-05-03", "reason": "UK Early May bank holiday", "source": "https://www.gov.uk/bank-holidays.json"},
    {"date": "2027-05-31", "reason": "UK Spring bank holiday (also US Memorial Day)", "source": "https://www.gov.uk/bank-holidays.json"},
    {"date": "2027-08-30", "reason": "UK Summer bank holiday", "source": "https://www.gov.uk/bank-holidays.json"},
    {"date": "2027-10-01", "reason": "China National Day week (approx 10-01..07), SGE/SHFE closed - UNVERIFIED", "source": "UNVERIFIED"},
    {"date": "2027-12-27", "reason": "UK Christmas substitute day", "source": "https://www.gov.uk/bank-holidays.json"},
    {"date": "2027-12-28", "reason": "UK Boxing Day substitute day", "source": "https://www.gov.uk/bank-holidays.json"},
    {"date": "2027-12-31", "reason": "New Year's Eve; GC regular close; holiday-thin", "source": "https://www.cmegroup.com/trading-hours.html"}
  ]
}
```
Weekends are excluded. Recheck the CME page and broker notices about two weeks before each date.
