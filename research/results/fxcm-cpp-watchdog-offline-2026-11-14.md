# FXCM native C++ fixture process watchdog — 2026-11-14

Source: coordinator/fxcm_cpp_offline_supervisor.py
Tests: coordinator/test_fxcm_cpp_offline_supervisor.py

One more useful preparation step before any FXCM EULA/account entitlement:
the synthetic C++ fixture is now supervised as an isolated child process,
rather than assumed to produce a perfect JSON message instantly.

- SHA-256 of the *locally built test binary* is checked before launching.
- Only explicitly named synthetic fixture modes are permitted.
- No shell, no environment variables copied from connected accounts,
  no stdin, no stderr output stored and no FXCM SDK loaded or called.
- The process has a hard timeout and a capped stdout budget. A stuck or
  oversized process is killed and converted into a WAIT status.
- Non-zero exits, malformed JSON, wrong digest and unknown live flags
  likewise fail closed. Output is metadata only, never Bid/Ask prices.
- Even a valid synthetic C++ packet still passes to the existing
  FXCM standby -> common research gate with license/access disabled.

This supervisor is not wired into a deployed service and is deliberately
restricted to a synthetic fixture binary. It does not provide a general
network sandbox for arbitrary binaries or prove native FXCM SDK runtime
behavior. A real licensed adapter would require a separately reviewed
service/process design, OS/network restrictions, verified permissions and
live market data acceptance. No real trades, no subscription, no Render
deployment, no changes to production branches.
