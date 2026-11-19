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

## Actual running-build verification — 19 November 2026 (read-only)

- Render private coordinator `gold-precision-coordinator` is still LIVE at
  `b01574f221cb550b9ead70b6c8de17e0b1a61c8f`, with auto-deploy disabled.
  Its deployed `biquote_private_forward_vault.py` has **NO**
  `firstObservedClosedUTC` implementation. Its deployed
  `biquote_seven_day_review.py` has **NO** first-seen-coverage logging.
- The later first-seen receipt implementation and point-in-time V3 audit are
  review-branch **CODE ONLY**. Passing GitHub Actions does NOT imply those
  changes ran on the owner-only disk or that existing market bars have local
  first-seen records.
- Read-only Render logs at 2026-11-19 11:00 UTC showed closed
  M15=136 (latest contiguous 48), H1=34 (contiguous 12), H4=8
  (contiguous 8), 736 sparse BID/ASK quote samples; unclassified missing
  slots M15=4, H1=1. These are **persisted counts, not independently
  authenticated archive receipts**. This evidence cannot establish a
  point-in-time signal, broker data rights or fills.
- The running archive is expected to be a legacy no-first-seen archive;
  the exact vault bytes were **NOT** accessed or inspected through Render.
  On a future controlled transition, ALL historical un-timestamped candles
  remain UNKNOWN forever. Only candles newly appended AFTER authorized
  deployment can carry local receipt evidence.
- The offline mixed legacy/new migration regression
  `test_deployed_legacy_to_future_receipts_keeps_old_bars_unknown`
  checks that hypothetical forward upgrade does not fabricate historical
  timestamps or open paper/live trading. This is **not** a real Render
  migration, backup or restore test.

**Decision:** preserve the collector process and its fixed consent window;
no deploy, restart, new poller, new subscription or actual execution.

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

## Isolated local restore rehearsal (offline only)

The new `biquote_collector_restore_rehearsal.py` accepts an existing, owner-only
backup, verifies its signed payload, restores it to a disposable private
scratch directory, reloads all sealed candles and receipts, compares bytes,
and destroys the scratch copy. It emits **counts only**, never prices, quote
secrets, paths or a signal. It does not access the Render private disk.

Passing locally is NOT evidence that Render has an independent offsite backup
or that a real disaster recovery operation succeeded. The coordinator should
stay deployed on its prior build while the seven-day capture is active.

## Render persistent-disk snapshots (19 November 2026 documentation check)

Render documents **one automatic disk snapshot per 24 hours**, encrypted
at rest, available for **seven days**. They are *platform disaster recovery*
points. Restoring one **overwrites the entire current disk** and removes any
newer accumulated market records; there is no per-file snapshot restore.

Documentation: https://render.com/docs/disks

The GitHub/Render integration in this workflow has **not verified any
specific snapshot** for the collector disk, and exposes no list-snapshots
or independent file-export action. Do not claim this is an audited, offsite
backup of the signed BiQuote vault. The owner can inspect snapshots in
Render Dashboard -> coordinator service -> Disk, without restoring them.

The offline `biquote_render_snapshot_preflight.py` accepts only
operator-supplied snapshot listing metadata. It strips snapshot keys from
output, never authenticates listing provenance, and always vetoes restore,
deploy and orders. A fresh listed snapshot does **not** prove that the
signed vault is recoverable. Keep the live collector untouched while the
seven-day recording is active.

## Dormant second seven-day capture option (not authorized or activated)

The first approved collector window ends on **2026-11-25T00:00:00Z**.
At that time the existing code stops; pushing code or restarting later
will NOT collect more bars under the old window by itself.

A *dormant* second fixed 7-day interval is now supported (25 November to
2 December 2026). It requires an explicit NEW, owner-reviewed permission
and the exact new anchor. The opt-in variables are
`GPP_BIQUOTE_NEXT_7DAY_APPROVAL` and
`GPP_BIQUOTE_NEXT_7DAY_START_UTC`.
Neither has been set or approved in Render. It is strictly read-only,
no trade signals, no live orders, no paid data. It can never auto-roll
into a third interval. An actual controlled deploy must also be separately
authorized after the current recording is finished and backed up.

The old default start and authorization remain unchanged. No extra
collector or API polling process is launched by this GitHub change.
