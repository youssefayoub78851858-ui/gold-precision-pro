# Databento DBN decoder fixtures

These three binary files are copied from Databento's official `dbn` repository
at immutable source revision `a77693030595b8f29f6b4c58e63b1b1a9d899b3f`,
`tests/data/`. Their SHA-256 values, sizes, schemas, and decoded record counts
are pinned in `manifest.json`. The upstream repository declares Apache-2.0 and
its license is included beside the copied files; no separate per-file license
was found.

They decode to symbol `ESH1` (not XAUUSD or GC). Treat them only as software
decoder fixtures. They do not prove GC coverage, market-data rights, book
continuity, or strategy performance. Adapter results remain test-only,
`researchEligible: false`, `signal: WAIT`, and `executable: false`.
