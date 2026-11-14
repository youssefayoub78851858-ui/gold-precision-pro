# FXCM native standby bridge to existing research pipeline (2026-11-14)

This update does NOT create a second trading strategy or enable an SDK.
It reuses coordinator/fxcm_native_offline_boundary.js to structurally audit
a proposed native C++ bridge packet, then invokes the *existing*
xauusd_research_pipeline.run_research_pipeline with strictly metadata
and an intentionally closed, provider-pinned SourcePolicy.

No candles, synthetic assumed session calendar, unverified Bid/Ask fills,
user-supplied rights flags, approval booleans, or broker login can reach
V3, Ultimate R2, diagnostics or paper execution. Audit output exposes
counts/reasons only (no prices), and status always remains WAIT,
researchEligible:false, executable:false.

This is an integration guard/diagnostic, not actual FXCM market data.
External blockers: EULA and private cloud rights, read-only demo
isolation, FXCM source timestamps, session calendar, live/historical
Bid/Ask parity and actual service availability. No vendor network
access, subscription, account session, Render deploy or order.
