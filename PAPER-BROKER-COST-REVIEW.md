# XAU/USD broker-cost and paper risk preflight (review only)

New \`coordinator/paper_cost_preflight.py\` contains pure **offline**
unit-tested arithmetic for labelled \`SYNTHETIC_TEST_ONLY\` scenarios.
All 12 cost/risk parameters must be explicitly supplied, including
contract ounces per lot, lot size, spread in USD/oz, entry/exit adverse
slippage, *round-trip* commission per lot, stop distance, target net USD,
equity, risk fraction, daily loss fraction and used daily loss.

Spread is counted **once** in a complete round trip; slippage counts twice
(entry + exit), and commission is exactly the supplied **round-trip**
assumption. The model estimates cost, target movement and stop-risk against
a 0.5% per-idea and 2% daily-research risk ceiling. It makes **no network**
calls and can never authorize or create a paper/real position.

The example in the unit test is deliberately synthetic: 0.01 hypothetical
lots of 100 hypothetical ounces/lot, $0.40/oz spread, $0.10/oz adverse
slippage per leg, $7 per lot round-trip fee, $50 hypothetical equity and
$5 target net. **None** of these assumptions is a verified broker quote,
contract specification, actual CFI price, a recommendation or a profit
forecast. The scenario is rejected by its 0.5% budget.

Live private status now adds a \`costReadiness\` block to the paper gate.
The mobile review proxy exposes **only** fixed BLOCKED/WAIT reason codes
and the fact the calculator module exists. It never exposes hypothetical
numbers, raw prices, account values, or vendor credentials.

Still required: authenticated broker symbol specifications (contract size,
min/step lots, pip/tick value), actual spread at the intended execution
venue, valid fee schedule, separately tested slippage/market-hour policy,
confirmed collateral and the true per-idea/daily risk budget. A real,
licensed market feed and explicit paper-only approval remain separate
prerequisites. No payment, live provider calls, MT5 trade, or public
production update is performed.
