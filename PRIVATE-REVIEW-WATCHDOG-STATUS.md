# Private review watchdog: activation stage, NOT licensed data

An offline-only periodic observer is available in the private standby
coordinator with \`PRIVATE_REVIEW_AUDIT_ENABLED=1\`. When the environment
variable is absent it is OFF. It makes ZERO provider network requests,
never triggers a research signal, paper account, broker, or push/email.

When enabled, the loop reads the existing private snapshot every 60 s, writes
deduplicated alert and notification transitions to a \`0700\` private directory
on the Render persistent disk and records last heartbeat. It survives restarts
without duplicating unchanged events. If EODHD is not connected, it records
only the blocked source state (WAIT).

The authenticated \`/api/v3/monitor/status\` includes an optional sanitized
\`audit\` object: AUDIT_OK/STALE/DISABLED, last UTC heartbeat, active reason
codes, last local notification code. The existing public review proxy validates
and strips this data; the mobile page renders it using textContent (no raw
prices, account information, or provider keys).

GitHub Actions tests no-network Docker run with observer OFF and ON including
restart and recovery. A passing CI alone does not prove sustained uptime,
market-data availability, profitability or readiness for paper positions.
Switching on the research-only loop in private Render requires deployment
of the reviewed code and explicit operator approval. Production remains
untouched and EODHD, MT5 orders, and external notifications stay OFF.
