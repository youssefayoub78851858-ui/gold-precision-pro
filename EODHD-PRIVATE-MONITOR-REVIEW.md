# EODHD private review monitor — offline only

This is a non-executable status monitor between the saved EODHD private snapshot
and the existing local SQLite alert/notification journals. It is deliberately
separate from the current synthetic-only research monitor runner.

Run **one poll** with explicit paths (never autostarts, no provider connection):

    python coordinator/eodhd_review_monitor.py \
      --snapshot-directory /private/review \
      --alert-db /private/review/research-alerts.sqlite3 \
      --notification-db /private/review/research-notices.sqlite3

- If there is no private snapshot, returns WAIT with NOT_CONNECTED.
- If stale, world-readable, symlinked, corrupt, or bad Bid/Ask geometry, records
  a blocking status. Alerts are deduplicated across polls and process restart.
- A fresh file is NOT entitlement or market-session verification. The review
  bridge runs with **no source authorization, no independent calendar/clock
  evidence, and no engine opt-in**, so it never evaluates or trades.
- Reports counts and reason codes, NEVER bid/ask, token, quotes or account data.
- Notifications are local dry-run previews only, no external email/push.
- No persistent 24/7 polling or live-source monitoring has been enabled.
- The broker, paper account and protected production services are untouched.
- This feature is a preliminary check, not a claim that data quality, historical
  warmup, license, trading strategy or real profitability have been validated.

GitHub Actions runs its offline regressions in the one-click review suite.
