# Capital.com Demo — private price-GET isolation (review only)

The selected candidate is **Capital.com Demo**. The official Capital.com
API documentation states that API keys are **trading-capable**, not genuinely
read-only. Therefore a key must NEVER be put into the general dashboard,
signal engine, browser, public Render service, or a repository file.

## Status

- Code and deterministic mock tests prepared only on
  `review/v2-portable-tests-20261109`.
- `coordinator/capital_demo_private_get_boundary.py` permits ONLY the
  HTTPS Demo `GET /api/v1/prices/{epic}` request shape, with bounded
  fixed query parameters and exact closed-bar window validation.
- It **cannot** log in or create a session, issue POST/PUT/DELETE/order
  calls, or call the live broker host. No live transport is configured.
- Default settings reject ALL provider calls. The private collector must
  later supply an independently reviewed transport and a private archival
  callback. HTTP redirects must be forbidden at the egress layer. A
  network egress allowlist to the Demo host **and only** price route is
  required; Python method restrictions alone do not securely limit the
  privileges of a trading-capable token.
- Activation requires separate, specific approval, verified contractual
  permission for cloud/private research, an eligible and KYC-verified
  Demo account, 2FA/API setup, the broker's genuine Gold epic, and a
  session token obtained outside this module. No keys should be pasted
  into ChatGPT or committed to GitHub. Tokens must be stored in an
  approved isolated secret manager, not the mobile viewer.
- No response counts, receipt times, or synthetic tests can prove
  broker session/DST or execution price basis; independent H1/H4/M15
  parity, DXY/GC rights, costs and prospective net holdout remain open.
- NEVER set the activation environment variables just to pass tests;
  tests use disposable patched values without any remote calls.

## Operational handoff in order

1. Confirm **in writing** broker eligibility for Lebanon, private Render
   research rights, Demo Gold BID/ASK historical/stream basis and timing.
2. Complete account verification/2FA yourself only after permissions
   are confirmed. Use the Capital.com account web portal, not chat.
3. Operator establishes a dedicated network-restricted private
   **Demo-only** session/token service; review logs must redact secrets.
4. Connect only price GETs through an isolated gateway, validate each
   timestamp/price and local first-seen receipt using existing auditors.
5. Admit NO BUY/SELL or auto-paper until independent GC/DXY/news
   coverage, cost model, and untouched after-cost holdout are verified.

Current decision: WAIT. No fees, account or execution authorized.
