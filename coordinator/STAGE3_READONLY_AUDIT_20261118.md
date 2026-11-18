# Gold Precision Pro Ultimate — Stage 3 review-only evidence
**18 November 2026 (UTC) — branch `review/v2-portable-tests-20261109` only**

## Confirmed deployment evidence at 09:55–10:12 UTC
- Coordinator Render private service `gold-precision-coordinator` and Android demo `gold-precision-v3-review-demo` deployed commit `97c15bdc254dfece9c2c94c795caf892edccef47` live.
- Sealed vault reopened at 09:55:32 UTC with M15=39, H1=9, H4=2, quote observations=41, capacity headroom.
- At 10:12:02 UTC the same private observer recorded its 10th saved **snapshot since that restart**, 0 rejected snapshots, all 40 GET attempts HTTP-complete. Each sample still had `UNCLASSIFIED_M15_COVERAGE_GAP` and `geometryChecksOk=false`.
- The saved-snapshot count is **not** the number of new closed candles. A stronger metadata-only event was added in Stage 3 to report actual new closed bars, continuity and unclassified gaps only when a new closed bar is persisted.

## New Stage 3 protections
1. `ultimate_batch_acceptance.py` now rejects inconsistent claimed frozen V3 evaluation unless >=21 **contiguous closed bars** exist in each timeframe AND both H1/H4 contain at least one fully covered, mismatch-free M15 comparison.
2. `review_monitor_proxy.js` separately validates Stage 3 booleans, counters, status codes, and prior archive information before showing it on Android; it never forwards raw OHLC or BID/ASK.
3. `private-monitor.html` presents Stage 3 `WAIT` state, number of warmed frames, H4 remaining to 21, independent rights/session/context blockers. No entries, stop losses or order activation.
4. `biquote_seven_day_review.py` emits `BIQUOTE_STAGE3_CLOSED_BAR_PROGRESS` **only after new closed candles**; fields are normalized counts, unclassified gap slots/pairs and an explicit no-trading veto. On bad sealed metadata the event is `BIQUOTE_STAGE3_METADATA_UNAVAILABLE` and never leaks raw private prices, credentials, untrusted path or exception string.
5. Synthetic-only and adversarial offline tests cover fabricated V3 readiness, corrupted metadata, cross-frame disagreements, mobile safety and no provider calls. Passing CI never constitutes independent market qualification.

## Remaining real-world blockers
- BiQuote permits private personal archival subject to its terms, but the specific upstream MT5 broker identity/market-data entitlement and DST/holiday/session calendar are not independently established.
- A generic 22:00–23:00 UTC daily break reference cannot **automatically classify** the actual observed M15 gaps or prove all closed H4 bars represent complete 16-M15 groups.
- Forward H4 warmup needs 21 contiguous closed bars (84 wall-clock hours in a continuously trading market; longer with breaks). Earlier timestamps cannot be retroactively relabeled as prospective.
- Macro feeds, DXY, US02Y, US10Y, GC trades/MBP-10/MBO order flow, execution-cost basis and forward net profitability remain independently unverified.
- Capital.com Demo has a pre-existing, strictly offline BID/ASK parser/fixtures for historical M15/H1/H4. No keys requested or endpoint enabled; demo and live keys share **trading capability**. Cloud/private storage rights remain unconfirmed. See `research/results/capital-demo-staging-2026-11-16.md`.
- GC Order Flow and CME permissions are a separate potential charge, not included in a free XAUUSD quote source.

**Invariants: `signal=WAIT`, `executable=false`, `paperOrdersAllowed=false`, no real order or paid provider connection. No production deploy or `main`/`backup-v1` edits.**
