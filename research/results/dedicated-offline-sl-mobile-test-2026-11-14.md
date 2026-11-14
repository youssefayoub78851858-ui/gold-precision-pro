# Stop Loss dedicated offline mobile test (2026-11-14)

The user successfully verified TP3 from an Android handset on the review demo.
Stop-loss closure had not yet been verified on that handset. A new isolated
button in `/paper-terminal` exercises the actual existing paper `open()`,
`advance()` and `close()` in synthetic-only fixtures: BUY STOP, SELL STOP,
and BUY STOP_FIRST_BOTH_TOUCHED with adverse price gap. The test computes
actual fee-adjusted net results, demonstrates stop-first conservatism,
and cannot mutate the user's browser-local current three-trade journal.
No market request, account change, FXCM credentials, paid feed or real order.
Always WAIT, executable:false. The ordinary real-data engine remains disabled.
The current branch is for research only and requires user approval before
Render redeployment. Latest published review demo remains on prior commit.

CI: `node test_paper_terminal_core.js` and
`node test_paper_terminal_ui.js` within existing offline workflow.
