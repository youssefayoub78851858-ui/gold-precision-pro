# Research-only runtime readiness

`supervise.py` owns the local broker, API, and paper worker and exits non-zero
after a child failure or missing/stale worker heartbeat. It does not provision
or restart infrastructure. `research_watchdog.py` is a decision-only contract
for an external host health check; it reports `RESTART_REQUIRED` but never
starts a process. The host must be configured to restart the service on a
non-zero exit and to preserve the configured data directory between restarts.

Before any continuous run is authorized, configure a private persistent data
volume for SQLite, filesystem permissions for secrets, HTTPS ingress, a strong
broker token, a single active supervisor instance, and an external check that
reads the heartbeat and enforces the `paper_only` guard. Verify restart limits,
disk capacity, SQLite backup/restore, clock synchronization, and operator pause
procedures. Do not expose market data or derived feed content to other users.

Current tests use injected time and synthetic fixtures only. They do not launch
the supervisor, create a service, poll a provider, send notifications, or prove
that a host's restart configuration works. Live-source activation remains
blocked until source entitlements, cloud processing/storage rights, data
quality, and deployment approval are verified.
