# EODHD private snapshot recovery observer (review only)

A new persistent, strictly offline observer counts **separate** safe status
observations at least 30 seconds apart, separated by no more than 120 seconds.
After 3 it may report OBSERVATION_REPEATED_UNVERIFIED; this is **not**
licensed market-data verification. It does not validate the origin of a
private snapshot, open trades, create a paper account or send alerts.

If the source disappears, goes stale, is malformed, or changes its research
contract, the status immediately becomes SOURCE_ABSENT / SOURCE_INTERRUPTED /
SOURCE_REJECTED, and the counter resets. Repeated polls of the exact same
timestamp do not increment, and UTC clock rollback is rejected. Restart
reuses a 0700-folder SQLite database rather than forgetting previous state.

A compact recovery summary is nested inside existing authenticated audit
status. The public review proxy allowlists it and removes any prices, keys,
and account fields before the mobile UI displays it.

Tests include simulated missing -> three synthetic private-file updates ->
stale -> restart, plus no-network/invalid data. These fixtures are NOT live
EODHD, and sourceVerified/paperOrdersAllowed are always false.
No paid subscription, provider access, broker orders, or production changes.
