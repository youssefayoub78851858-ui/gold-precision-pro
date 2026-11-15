# Paired holdout intraday timestamp safety and chronological stability

Review branch only. The frozen V3 engine remains unchanged.

The existing pairwise audit had point-in-time upper bounds but could
accept a very stale GC/DXY/order-flow source observation. This change
rejects an observation older than 5 minutes at the candidate decision
or a cross-source DXY/GC/order-flow observation skew exceeding 60
seconds. Daily Treasury and economic-calendar observations are
intentionally not forced into a 60-second intraday window.

The new `ultimate_pairwise_stability.js` splits the SAME predeclared,
hash-locked candidate universe into chronological halves and reports
baseline and shadow-filter net-R differences after the existing spread,
slippage and commission assumptions. The halves are NOT independent
out-of-sample trials and no claim of benefit, significance, accuracy or
live source authorization is allowed. Small samples are flagged.
No broker/network/vendor calls, subscriptions, Render deploys or real
trades. Any missing input is rejected; the frozen V3 decision stays WAIT.
