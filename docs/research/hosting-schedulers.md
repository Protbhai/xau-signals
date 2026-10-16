# Free schedulers for the 5-minute price-check job

Research date: **2026-10-16** (`date -u` = Fri Oct 16 16:26 UTC 2026). Every page below was read on that date. Read-only research; nothing created or deployed.
"UNVERIFIED" = not confirmed on an official page.

Target: weekdays 03:30–09:30 UTC (09:00–15:00 IST) every 5 min (73 slots/day), plus a light pass outside that window. Fetch price API, call Telegram Bot API, keep a few KB of state, secrets as env secrets, laptop off.

---

## Comparison table

| Platform | Free, no card? | Min interval | Fits 5-min window? | Persistence | Main risk |
|---|---|---|---|---|---|
| **Cloudflare Workers Free (JS/TS)** | Free plan is the default; "no card" seen only in a search snippet of a CF marketing page (UNVERIFIED on docs) | 1 min | **Yes** | KV, D1, Durable Objects (all on Free) | 10 ms CPU; occasional cron incidents |
| GitHub Actions `schedule` | Yes (public repo unlimited; private 2,000 min) | 5 min | **No, not right now** | commit-back / cache / artifact / repo variable | Multi-hour delays and dropped runs since 26 Aug 2026 (community reports) |
| GitHub Actions `workflow_dispatch` fired by cron-job.org | Yes | 1 min (cron-job.org) | Yes, if the PAT trade-off is OK | same as above | PAT stored at cron-job.org; private repo minutes are tight |
| cron-job.org (pinger only) | Yes | 1 min | Yes, as a trigger | none | 30 s timeout; off after 25 failures in a row |
| Oracle Always Free VM | **Card required** (verification hold) | real cron | Yes | local disk | Idle VMs reclaimed; capacity errors |
| Google Cloud Scheduler + Cloud Run | **Billing account; Trial needs card** | 1 min (UNVERIFIED) | Yes | Firestore free | 3 free jobs per billing account |
| AWS Lambda + EventBridge Scheduler | No card for most new users | 1 min (UNVERIFIED) | Yes, for 6 months | DynamoDB | Free plan account closes after 6 months |
| Northflank Sandbox | 2 free cron jobs; card status UNVERIFIED | UNVERIFIED | Possibly | 1 free DB | Card possibly needed |
| Val Town Free | Not stated | **15 min** | No | — | — |
| Vercel Hobby | Yes | **Once a day, ±59 min** | No | — | — |
| Netlify scheduled functions | All plans | not stated (examples hourly) | UNVERIFIED | — | 30 s limit |
| Render | Cron jobs are not a free service type; **$1/month minimum** | — | No (not free) | — | — |
| Railway | $5 trial for 30 days, then $1/month credit | UNVERIFIED | Unclear | — | Credit too small / cron unverified |
| Fly.io | **No free tier for new orgs**; card after trial | — | No | — | — |
| PythonAnywhere Free | New free accounts (after 2026-01-15) get **no** scheduled tasks; older free = 1 daily task | daily | No | — | — |
| Replit | Scheduled deployments cost **$2/month base** | — | No (not free) | — | — |
| Deno Deploy | Classic **shut down 20 Jul 2026**; new Deploy cron limits not documented | UNVERIFIED | UNVERIFIED | KV free quota | Public beta, "no uptime guarantees" |
| Koyeb | Pricing page lists no free compute plan (Pro $29) | — | No | — | — |
| Glitch | **Hosting shut down 8 Jul 2025** | — | No | — | — |

---

## 1. GitHub Actions

Sources: [events-that-trigger-workflows](https://docs.github.com/en/actions/reference/workflows-and-actions/events-that-trigger-workflows), [billing](https://docs.github.com/en/billing/concepts/product-billing/github-actions), [runner pricing](https://docs.github.com/en/billing/reference/actions-runner-pricing), [limits](https://docs.github.com/en/actions/reference/limits), [workflow syntax](https://docs.github.com/en/actions/reference/workflows-and-actions/workflow-syntax), [caching](https://docs.github.com/en/actions/reference/workflows-and-actions/dependency-caching), [variables](https://docs.github.com/en/actions/reference/workflows-and-actions/variables), [variables REST](https://docs.github.com/en/rest/actions/variables), [workflows REST](https://docs.github.com/en/rest/actions/workflows), [disable/enable](https://docs.github.com/en/actions/how-tos/manage-workflow-runs/disable-and-enable-workflows). All read 2026-10-16.

- **Free usage:** public repos use standard hosted runners free. GitHub Free private repos get 2,000 min/month. Each job is **rounded up to a whole minute**, so a 20-second job costs 1 minute. Without a payment method, usage is **blocked** once the quota is used up. That is a hard stop, with no charge.
- **Budget check for a private repo:** 73 slots × ~22 weekdays ≈ 1,600 min, plus the off-hours passes, so it is close to 2,000. A **public repo** has no minute problem, but the code and any committed state are public. Secrets stay secret.
- **Interval:** "The shortest interval … is once every 5 minutes." Runs only on the default branch. UTC by default, with an optional IANA `timezone`.
- **Documented caveats:** delays "during periods of high loads"; "High load times include the start of every hour"; "some queued jobs may be dropped." In public repos, scheduled workflows are **auto-disabled after 60 days without repository activity**. Re-enable with `gh workflow enable`. UNVERIFIED: whether the bot's own state commits count as "activity".
- **Real-world status (important):** GitHub Community threads report scheduled runs **4–6+ hours late or not created at all since 2026-08-26**, still happening in October. A `*/5` cron got no runs in 25 minutes. Manual dispatch started in 7–12 s. No staff answer; marked Unanswered. See [#207346](https://github.com/orgs/community/discussions/207346) (last comment 3 Oct 2026), [#210111](https://github.com/orgs/community/discussions/210111) (12 Oct 2026), and [#201738](https://github.com/orgs/community/discussions/201738). These are user reports, not an official statement. Older reports describe 5–30 min delays at the top of the hour. One July 2026 issue shows six `*/5` ticks missing in 30 min ([tamucsa/points#34](https://github.com/tamucsa/points/issues/34)).
- **Concurrency:** `concurrency: group` allows at most 1 running and 1 pending run. A newer pending run replaces an older one.
- **Secrets:** repository secrets. **State options:** (a) commit a small JSON file back with `contents: write`. This is simplest and also creates repo activity. (b) Actions cache: entries can't be changed (each save needs a new key) and are evicted after 7 days unused. (c) A repo variable (48 KB max) updated with `PATCH …/actions/variables/{name}`. Needs a PAT with `repo` scope (classic); UNVERIFIED whether `GITHUB_TOKEN` can do it. (d) Artifacts: 500 MB, awkward to read back.
- **External trigger:** `POST …/workflows/{id}/dispatches` needs the `workflow_dispatch` trigger and a token with `repo` scope (classic PAT). The fine-grained permission is not stated on the page. Returns 200 with the run id.
- **Runner cold start:** no official figure. **UNVERIFIED**; commonly 10–40 s before the first step.

## 2. Cloudflare Workers Free

Sources: [limits](https://developers.cloudflare.com/workers/platform/limits/), [cron triggers](https://developers.cloudflare.com/workers/configuration/cron-triggers/), [scheduled handler](https://developers.cloudflare.com/workers/runtime-apis/handlers/scheduled/), [KV limits](https://developers.cloudflare.com/kv/platform/limits/), [D1 pricing](https://developers.cloudflare.com/d1/platform/pricing/), [DO pricing](https://developers.cloudflare.com/durable-objects/platform/pricing/), [secrets](https://developers.cloudflare.com/workers/configuration/secrets/), [pricing](https://developers.cloudflare.com/workers/platform/pricing/), [Python](https://developers.cloudflare.com/workers/languages/python/), [Python GA blog](https://blog.cloudflare.com/python-workers-ga/). All read 2026-10-16.

- **Limits:** 100,000 requests/day (resets 00:00 UTC). **10 ms CPU** per HTTP request and per Cron Trigger. Time spent waiting on `fetch` is not CPU (per CF docs as quoted by search; the limits page lists only the numbers). **5 Cron Triggers per account.** 50 subrequests per invocation. 128 MB memory. Cron wall time 15 min.
- **Cron:** 5-field syntax, 1-minute granularity, **UTC**. Trap: **weekday numbers are 1–7 with 1 = Sunday**, so write `MON-FRI`, not `1-5`. A trigger change takes up to 15 min to roll out. Runs on "underutilized machines". **No timing SLA or retry is documented.** The handler gets `controller.scheduledTime` (ms) and `controller.cron`.
- **Outbound fetch:** allowed to arbitrary hosts. UNVERIFIED explicitly for the free plan, but fetch is the standard API and there is no free-plan host restriction in the limits.
- **Storage, all on Free:** KV 100k reads/day, **1,000 writes/day**, 1 write/s per key, 1 GB. D1 5M rows read and 100k rows written per day, 5 GB. Durable Objects (SQLite only) 100k requests/day, 100k rows written/day.
- **Secrets:** `wrangler secret put` or the dashboard. No free-plan limit is stated.
- **Python:** **GA since 21 Sep 2026** (blog). It needs the `python_workers` flag and supports `scheduled()` on a `WorkerEntrypoint`. Whether a Python cold start fits within **10 ms CPU on Free is UNVERIFIED**. Use **JS/TS** on Free.
- **Card:** the docs say only "By default, users have access to the Workers Free plan." A "no credit card required" line appeared in a search snippet of a CF marketing page, but I could not confirm it on an official page. **UNVERIFIED.**
- **Reliability:** status-mirror history shows partial Cron-Trigger incidents: 12 Mar 2025 (07:00–13:44 UTC), Feb 2025 (new schedules didn't run), Feb 2026 (24 min), Sep 2026. These come from third-party aggregators (isdown.app); UNVERIFIED on cloudflarestatus.com.

## 3. Oracle Cloud Always Free

[Always Free resources](https://docs.oracle.com/en-us/iaas/Content/FreeTier/freetier_topic-Always_Free_Resources.htm), [sign-up](https://docs.oracle.com/en-us/iaas/Content/GSG/Tasks/signingup_topic-Sign_Up_for_Free_Oracle_Cloud_Promotion.htm), read 2026-10-16.

- **Resources:** A1 Flex up to 2 OCPU / 12 GB, or 2× E2.1.Micro. Home region only.
- **Card required:** "Add payment verification method … Credit Card." Debit cards with a Visa/MC logo and no PIN are accepted. There may be a temporary hold.
- **Idle reclaim:** a VM is "idle" if over 7 days the 95th-percentile CPU is below 20%, network below 20%, and (A1 only) memory below 20%. **This job would look idle.**
- **Capacity:** "out of host capacity" errors are documented.

## 4. Google Cloud

[Free features](https://docs.cloud.google.com/free/docs/free-cloud-features), read 2026-10-16. Cloud Scheduler pricing comes from a search snippet of [cloud.google.com/scheduler/pricing](https://cloud.google.com/scheduler/pricing); a direct fetch returned no body, so it is partly UNVERIFIED.

- **Card:** the Free Trial "must provide a credit card or other payment method". The Free Tier needs a billing account.
- **Cloud Scheduler:** 3 free jobs per billing account, then $0.10 per job per 31 days.
- **Cloud Run:** 2M requests and 180k vCPU-s per month. **Functions:** 2M invocations. **Firestore:** 50k reads and 20k writes per day.

## 5. AWS

[Free plans](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html), [Free Tier FAQ](https://aws.amazon.com/free/free-tier-faqs/), [Lambda pricing](https://aws.amazon.com/lambda/pricing/), [EventBridge pricing](https://aws.amazon.com/eventbridge/pricing/), read 2026-10-16.

- **Card:** "A payment method isn't required to sign up for most new customers." A card may still be asked for to verify identity.
- **Free plan:** $100 credit plus up to $100 more. The plan **ends after 6 months or when credits run out, and the account closes**; data is kept 90 days. To keep running past 6 months you must upgrade to the Paid plan, which needs a card.
- **Allowances:** Lambda 1M requests and 400k GB-s per month. EventBridge Scheduler 14M invocations per month.

## 6. Others

- **Vercel Hobby** ([doc](https://vercel.com/docs/cron-jobs/usage-and-pricing)): once a day only, precision ±59 min. Not usable.
- **Netlify** ([doc](https://docs.netlify.com/build/functions/scheduled-functions/)): all plans, UTC, 30 s limit, published deploys only. A sub-hourly minimum is not stated (UNVERIFIED).
- **Render** ([cron](https://render.com/docs/cronjobs), [free](https://render.com/docs/free)): cron jobs are not a free service type. Minimum charge is $1/month per cron job.
- **Railway** ([trial](https://docs.railway.com/reference/pricing/free-trial)): $5 for 30 days, then $1/month credit. Cron details not on that page (UNVERIFIED).
- **Fly.io** ([pricing](https://docs.fly.io/about/pricing)): "New organizations don't have a free tier." A card is needed after the trial (2 h of machine time or 7 days).
- **PythonAnywhere** ([doc](https://help.pythonanywhere.com/pages/ScheduledTasks/)): tasks only on paid accounts or free accounts created before 2026-01-15; older free accounts get 1 daily task.
- **Glitch** ([blog](https://blog.glitch.com/post/changes-are-coming-to-glitch/)): hosting shut down 8 Jul 2025.
- **Replit** ([pricing](https://docs.replit.com/billing/deployment-pricing)): scheduled deployments have a $2/month base fee.
- **Val Town** ([pricing](https://www.val.town/pricing)): Free plan cron minimum is 15 min, 1 min per run.
- **Deno Deploy** ([cron](https://docs.deno.com/deploy/kv/manual/cron/), [pricing](https://deno.com/deploy/pricing)): Classic was shut down 20 Jul 2026. Classic cron was "at least once", with up to 1 min drift. On the new Deploy, cron is not documented on the pricing page (UNVERIFIED). Free: 1M requests and 10 h active CPU per month.
- **Koyeb** ([pricing](https://www.koyeb.com/pricing)): no free compute plan listed.
- **Northflank** ([pricing](https://northflank.com/pricing)): Sandbox has 2 services, 2 cron jobs, 1 DB, "always-on". Whether a card is required is UNVERIFIED; the FAQ says a card is "only verified".
- **cron-job.org** ([FAQ](https://cron-job.org/en/faq/)): free, 1-min minimum, 30 s timeout, custom headers and POST bodies, last 50 runs in history. Small delays possible at peak. Turned off after more than 25 failures in a row.
- **UptimeRobot** ([pricing](https://uptimerobot.com/pricing/)): free, 50 monitors, 5-min interval, "No credit card required". Meant for hobby/non-profit use; jitter not documented.
- **Healthchecks.io** ([pricing](https://healthchecks.io/pricing/)): free Hobbyist plan, 20 checks. Use it as a **missed-run alarm**, not a trigger.

## 7. Stand-alone state stores (if the host is stateless)

- **Turso** ([pricing](https://turso.tech/pricing)): 5 GB, 10M rows written/month, "no credit card required".
- **Upstash Redis** ([pricing](https://upstash.com/docs/redis/overall/pricing)): 500K commands/month, 250 MB. Card not stated.
- **Neon** ([plans](https://neon.com/docs/introduction/plans)): 1 GB per project; compute sleeps after 5 min (cold start on each run).
- **Supabase** ([billing](https://supabase.com/docs/guides/platform/billing-on-supabase), [pausing](https://supabase.com/docs/guides/platform/free-project-pausing)): 2 free projects, 500 MB. **Paused after 1 week of low activity**; a 5-min job keeps it awake.

---

## (a) Ranked recommendation

1. **Cloudflare Workers Free, JS/TS, one cron `*/5 * * * *`, state in D1 (or KV).** The code decides each tick:
   - weekday 03:30–09:30 UTC: full check;
   - otherwise: a light pass, e.g. only on ticks where `minute == 0` every 1–2 h;
   - a dedupe key per 5-min slot (`YYYYMMDDHHMM`) makes reruns harmless.

   This uses 288 invocations/day, far below 100k. KV writes stay under 1,000/day only if you write about once per tick; that is why D1 is preferred, with a 100k rows/day limit. **Expected jitter (UNVERIFIED, to be measured):** normally seconds, with rare incident gaps of minutes to hours.
2. **Add redundancy:** cron-job.org calls a secret-guarded `/tick` HTTP route on the same Worker, offset by about 2 min. The slot key stops double sends. Add a Healthchecks.io check (5 min period, 10 min grace) that the Worker pings, to alert on gaps.
3. **GitHub Actions, only via `workflow_dispatch` from cron-job.org** (public repo, state committed back). Do not rely on `schedule` while the Aug–Oct 2026 delays continue. Expect about 10–40 s runner start (UNVERIFIED) plus dispatch latency.
4. **Oracle Always Free VM:** precise cron, but needs a card and is at real risk of idle reclaim.
5. **GCP / AWS:** fine technically. They need a card or billing account, or (AWS Free plan) the account closes at 6 months.

## (b) Measurement plan (run 10 weekdays before trusting it)

- **Each tick writes one row:** `slot` (the scheduled time: `controller.scheduledTime`, or for cron-job.org the floored 5-min slot); `trigger` (cron, pinger or gha); `started_at` (`Date.now()`); `lag_ms = started_at − slot`; `price_fetch_ms`; `tg_send_ms` (round-trip of `sendMessage`); `tg_date` (the `date` field in Telegram's response, server time in seconds); `sent` (bool); `error`.
- **Delivery delay:** Telegram's API acknowledgement and `date` measure server acceptance only. Arrival on the phone cannot be measured automatically without a user client, so that part is UNVERIFIED. Do a manual spot-check a few times a day: compare the timestamp in the message text with the phone's received time.
- **Daily summary at 09:35 UTC to Telegram:** expected slots (73), slots seen per trigger, missing slots listed, lag p50/p95/max, duplicates suppressed, Telegram send p50/p95, errors.
- **GitHub comparison, optional:** the same probe, logging `created_at` vs `run_started_at` from the runs API to separate scheduler delay from runner queueing.
- **Pass criteria (suggested):** at least 99% of slots seen with lag ≤ 60 s, and no gap over 10 min.

## (c) What the user must create or authorize manually

1. **Telegram:** create the bot with @BotFather and get `TELEGRAM_BOT_TOKEN`. Send the bot one message, then read `TELEGRAM_CHAT_ID` from `getUpdates`.
2. **Price API:** an account and `PRICE_API_KEY`, if the API needs one.
3. **Cloudflare:** sign up and verify the email. Run `wrangler login` (OAuth consent) or create a scoped API token. Create the D1 database / KV namespace. Run `wrangler secret put` for each secret, typing the values yourself.
4. **cron-job.org:** an account, plus one job to `https://<worker>/tick` with a header such as `X-Tick-Secret`. Generate that secret and store it as a Worker secret too.
5. **Healthchecks.io, optional:** an account and one check URL, stored as a Worker secret.
6. **GitHub, optional fallback:** a repo, repo secrets, and a classic PAT with `repo` scope (or a fine-grained token with Actions write; UNVERIFIED) for the dispatch caller.
7. **Not needed:** a card for options 1–3. Oracle needs a card; GCP needs a billing account.
