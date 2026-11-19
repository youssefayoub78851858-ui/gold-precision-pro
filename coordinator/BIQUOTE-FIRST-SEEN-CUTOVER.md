# BiQuote first-seen collector upgrade — gate, not deployment

**Branch:** `review/v2-portable-tests-20261109`. **NO live order capability**.

## Decision, 19 November 2026

The private Render coordinator currently owns the only 7-day BiQuote
capture loop, anchored at **2026-11-18T00:00:00Z** and bounded by its
existing consent to **2026-11-25T00:00:00Z**. A manual Render deploy
restarts its process; code tests cannot guarantee that this will not
skip a receipt slot or interrupt H4 continuity.

**Therefore this change is committed but not deployed to that private
collector during the active capture.** No new service, second poller,
paid request, public price path or production deployment is permitted.

## Why the new receipt evidence matters

- Newly appended closed candles get `firstObservedClosedUTC` recorded
  **atomically in the same owner-only SHA-256 sealed vault**.
- Old candles lack that field. Their first-observed timestamps remain
  **unknown forever**, including after restarts or software rollback.
- A local first-seen timestamp is only a collector receipt, not proof of
  licensing, exchange timing, broker session calendar, Bid/Ask history,
  executable spread, order fill, or profitable signals.
- Any research read of `firstObservedClosedUTC` must veto candles that
  were not yet locally received; the current research code remains WAIT.
- No provider credentials or private candle prices enter GitHub/CI logs.

## Pre-deployment checklist

1. **Do not interrupt the active seven-day collector.** Wait until
   the bounded run has actually finished and its final status is
   independently verified; the calendar bound alone is insufficient.
2. Independently confirm a private persistent disk, current collector
   health, exact deployed SHA, and a secure **recoverable disk backup**.
   GitHub commits do not back up Render's private price archive.
3. Verify the existing `review/v2-portable-tests-20261109` branch
   CI runs, Docker image, owner-only disk permission, and that the
   capture approval remains intentionally controlled.
4. Make an explicit operator-reviewed cutover plan. Never enable
   `CUTOVER_MODE=live`, real orders, additional collector processes,
   new fees, or subscriptions.
5. After an authorized controlled deploy, verify only *safe metadata*:
   sealed-vault old counts intact; local first-seen counters only for
   newly appended bars; unknown legacy counts unchanged; ingestion
   progresses without gap-bridging or secrets in logs.
6. Any vault mismatch, missing backup, source-rights uncertainty, or
   new calendar gap remains **WAIT**. Never "repair" history using
   inferred timestamps or fabricate success.

Offline tests:
`test_biquote_private_forward_vault`,
`test_biquote_first_seen_collector_cutover`,
`test_biquote_seven_day_review`. These are synthetic and prove
program logic only; they do **not** attest actual Render backup,
continuous uptime or trade readiness.
