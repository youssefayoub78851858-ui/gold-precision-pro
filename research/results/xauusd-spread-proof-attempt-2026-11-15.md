# Attempted empirical proof: XAUUSD spread widening / mid-only breakout filter

Audit date: 2026-11-15. Branch:
`review/v2-portable-tests-20261109`.

## What was actually checked
- `research/recorded/manifest.json` and the SHA-256 verified local
  `2026-09-bid.json` and `2026-10-bid.json`.
- September: **2448 M15** BID observations.
- October: **2436 M15** BID observations.
- Total **4884 M15 BID** and **zero historical ASK or MID
  observations in these archives**.
- Source field cites Dukascopy via dukascopy-node, but the manifest itself
  explicitly disclaims independent source authenticity. A matching SHA digest
  proves bytes unchanged since manifest creation, not vendor provenance.
- Stored H1/H4 are aggregate BID bars, not synchronized bid/ask evidence.
- `coordinator/xauusd_spread_noise_guard.js` works on *synthetic*
  normalized BID/ASK/MID fixtures; CI verifies its fail-closed behavior.
  These assertions are **not measured trading wins**.
- Broker-variable historical spread, actual broker slippage/commission,
  historical ask-side stop fills, verified session gaps, independent
  licensed market origin, and untouched forward holdout remain unavailable.

## Conclusion
**NOT PROVEN / WAIT**. From BID candles alone, ASK-BID at the M15
close cannot be reconstructed. No valid paired baseline-versus-filter
trade outcome, false breakout reduction, profit increase or win-rate
delta may be calculated or claimed. Do not backfill ASK as
`BID + 0.40`, derive it from MID, relabel Binance perpetual
quotes as spot/GC, or use successful code tests as empirical trading
evidence.

The new executable-free
`coordinator/xauusd_spread_proof_readiness.js` reads only
the local existing archive and reports counts, integrity and blockers;
`coordinator/test_xauusd_spread_proof_readiness.js` tests original files,
tampering and mislabelled basis. It never initiates a data request,
broker action, subscription, deployment or price signal.

## Evidence needed before a real test
1. Synchronized timestamped XAU/USD BID/ASK quote histories **with
   legally documented cloud algorithmic research and internal-display
   rights**. Document the first-availability receipts.
2. Reconcile historical bars, live BBO, broker schedule and DST
   without filling gaps or using incomplete candles.
3. Freeze baseline candidates, exact filter rules and realistic
   broker commissions/slippage before opening the holdout window.
4. Compute the same frozen candidate universe and after-cost outcomes
   before and after the filter, preserving decisions available as-of.
   Include win rate, mean net R, drawdown, suppressed opportunities,
   sample size, uncertainty and a truly independent future replication.
5. Continue WAIT/paper-disabled until those conditions are met.
