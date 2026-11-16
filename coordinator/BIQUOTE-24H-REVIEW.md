# BiQuote 24-hour read-only review observer — staged, not deployed

**Current status:** CODE-READY / OFFLINE-TESTED (pending GitHub CI) / NO RENDER DEPLOY / NO PROVIDER SUBSCRIPTION.

This worker is a conservative **candidate** for a 24-hour metadata-only trial
on an isolated review environment. Adding it to GitHub does NOT start it or
change the existing Render services or production. Trading is always disabled.

## Actual data evidence preceding this worker

On 16 November 2026 the public BiQuote REST tests confirmed HTTP 200 for
XAUUSD BID/ASK quote plus M15/H1/H4 OHLC. Measured at 18:51:02 UTC, 47/47
complete H1 overlaps and 9/9 complete H4 overlaps agreed on OHLC with M15.
There were 3 partially supported H4 bars near broker session/day/week gaps.
Those bars were not proven invalid and were **not** declared valid market
sessions either. BiQuote's support permits private Render paper research
under its terms but does not guarantee the upstream MT5 broker's rights.

Evidence: GitHub Actions run 43933123761 on the review branch.

## Review worker contract

- Code: `coordinator/biquote_24h_observer.py`. Stdlib Python.
- Fixed 24-hour UTC window, **720 slots every 120 seconds**, each slot makes
  exactly one call to the existing, public-only four-GET BiQuote one-shot
  (quote, M15, H1, H4). **Maximum 2,880 public GET attempts per run**.
- No credentials, broker account, POST, order or transaction code, cron,
  deployment changes or account-access functionality.
- No raw candles or raw BID/ASK prices saved or logged; emitted metadata
  includes sample status, quote-age/spread minima/maxima, HTTP health and
  overlap-gap counters, never a BUY/SELL instruction.
- If restarted, the SAME fixed UTC start time must be provided. A missed
  slot is counted as missed, not reconstructed by rapid catch-up requests.
  After the 24-hour window, the worker exits. There is no recurrence.
- All reports keep `signal=WAIT`, `executable=false`,
  `researchEligible=false`, `paperOrdersAllowed=false`.
- A 120-second REST cadence is **not** tick-stream completeness and cannot
  prove 24/5 availability, historical spread, broker parity or profitability.
  BiQuote may go stale during its regular daily/weekly market closures,
  has no SLA and no historical missed-period backfill.

## Read-only activation instructions for approved Render *review* environment

**Do not deploy by default.** Confirm the exact Render workspace, review
service, its cost/plan, uptime/sleep characteristics, and that it does not
touch the production instance. A free sleeping web service is not a proven
24-hour always-on background worker; do not claim a full 24h result from it.

No future job should start until that environment is independently reviewed.
Once explicitly confirmed and suitable, run exactly one review worker process
with the following command, using an absolute fixed UTC start:

```sh
GPP_BIQUOTE_PUBLIC_24H_REVIEW=APPROVED_READONLY_NO_TRADING \
  python coordinator/biquote_24h_observer.py \
    --start-utc 2026-11-17T00:00:00Z
```

The sample date above is a **non-current example**, not a scheduled run.
Never copy it without choosing an actual appropriate timestamp. Require
an operator to configure one runtime instance and an externally verified
time and cost budget. Run as a dedicated review *background worker*
rather than replacing the application's production/server command.

## Safety validation

`python -m unittest -v test_biquote_24h_observer` uses a fake 24-hour clock.
It proves: 720-slot/2880-request bound, no orders, restart does not
backfill missed slots, expiration makes zero requests, future/non-UTC start
is blocked, broken public requests never become signals, and the CLI
requires explicit read-only approval. The CI job runs **offline only**.

## Evaluation threshold

At the end, report a concrete count of sampled and missed slots, HTTP 200
responses, independently checked stale quotes, cross-frame non-overlap,
number of full H1/H4 comparisons and OHLC disagreements, actual captured
observation-window time, and unavoidable unknowns. No paper or live trading
is authorized by a healthy telemetry report. Do not estimate profitability
from the overlap test.
