# EODHD → research pipeline staging, no data activation

This review branch contains a disabled WebSocket producer and an offline Python bridge.
The producer writes separate BID / ASK / MID closed-bar frames to a private snapshot;
the analysis bridge uses **BID**, not MID, when explicitly authorized for research.

No network or paid subscription is used in these tests. The bridge denies all
research by default; it does **not** trust `sessionVerified` or warmup flags from
a snapshot. Independent market-session opens, historical coverage, a verified UTC
clock, the provider rights policy, and separate macro/news/order-flow evidence
are required before a research-only evaluation is called.

Technical caveat: 50 complete H4 bars require at least 800 M15 bars even in a
perfectly continuous session. Snapshot storage was raised from 320 to 2048
M15 bars; a restart, weekly market closure or missing tick still resets the
in-memory stream. **This is not a replacement for a licensed historical
warmup/import and persisted catch-up**. No session calendar is invented.

The validator compares separately timestamped BID/ASK/MID frames, verifies
non-crossing quotes and MID open/close provenance, and checks freshness.
Independent UTC expected opens are passed into the existing intake gate.
If all future external evidence is independently available, the bridge can call
the already existing V3/r2 research-only pipeline; results are always WAIT
and executable:false. That prospective code path is tested with a **mocked**
engine and synthetic fixture, not real vendor data.

The private readiness endpoint remains in standby, no signal transport or
paper executor is enabled. No new API key, Render deployment, CUTOVER_MODE
change, paid requests or actual MT5 trade. Main/backup/production untouched.

Offline tests:
- python -m unittest -v test_eodhd_research_bridge
- python -m unittest -v test_eodhd_private_readiness
- node test_eodhd_ws_bridge.js

Aggregation safety: H1/H4 BID, ASK and MID values must exactly match
complete aligned M15 source groups; injected or conflicting higher-frame bars
are quarantined before V3/r2 invocation.
