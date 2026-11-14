# FXCM offline C++ -> existing research integration (2026-11-14)

The prior review commit 5d2ea314 passes GitHub Actions. Next step tests
the cross-language path end-to-end without pretending a market connection.

The new C++17 emitter is deliberately an **original deterministic
synthetic-only fixture generator**: no FXCM SDK/header/import, no account,
network, broker session, data rights or order functions. Its CLI supports
only named offline fixture scenarios; --connect-live is rejected.
It outputs three-timeframe synthetic Bid and Ask candles, explicitly tagged
SYNTHETIC_CPP_OFFLINE_TEST_ONLY, including test variants for crossed prices,
stale candles, missing H1, forming M15 and gaps.

The Python test compiles and executes ONLY this self-contained fixture
program, sends JSON to the *existing* fxcm_native_pipeline_bridge, then
asserts the shared xauusd_research_pipeline never receives price bars
or calls the V3, Ultimate R2, paper or order engines. Even forged EULA,
BUY signals and source-approval booleans cannot unlock research.

This is not a native FXCM SDK run. The *real* C++ producer still needs
current vendor EULA and cloud rights, credential/order isolation, verified
clock/session semantics, genuine broker Bid/Ask history and live parity.
No Render deployments, provider requests, subscriptions, trades or bills.
