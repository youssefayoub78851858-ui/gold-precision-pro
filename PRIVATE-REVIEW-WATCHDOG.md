# Review-only periodic watchdog — offline stage

New **private** \`coordinator/private_review_watchdog.py\` is a low-cost periodic
status-only reviewer. It reads existing local EODHD readiness (including missing
feed) and writes deduplicated SQLite alert and notification journals in a
private \`0700\` directory. Read-only summaries include the last heartbeat,
active codes, last WAIT notification code and pause/stale status.

It NEVER connects to EODHD, downloads historical bars, produces BUY/SELL,
sends push/email, enters a paper trade or calls a broker. Test fixtures are
not real market prices. \`WAIT\` and \`executable:false\` are mandatory.

At this commit it is **NOT started by the Render service**, and the UI is not
yet wired to this audit. The next gated step is opt-in startup in the PRIVATE
coordinator standby runtime and authenticated read-only display on mobile;
a real periodic heartbeat must be verified on Render before claiming 24/7.
Production stays untouched and no subscription is purchased.
