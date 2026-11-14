# Public FXCM readiness card — Review Demo, 2026-11-14

The last GitHub Actions run 43582738431 passed all jobs, including private
phone/dashboard tests and isolated coordinator image startup/restart.

Render discovery: the public demo `gold-precision-v3-review-demo` uses root
`server.js` / `ultimate.html` and has autoDeploy disabled. The private
coordinator runs a separate Docker image and is not publicly browsable; both
were deployed at f18f1a63, not latest review branch. Production is separate.

This change adds to **public review demo only** a fixed, no-credentials,
no-price FXCM readiness endpoint and a phone-friendly card that queries the
endpoint **only on button press**, preserving WAIT. It does not attempt to
read the private coordinator or its token. It gives honest unresolved
blockers and zero connected candle counts, not mock FXCM quote data.

The private coordinator's more detailed monitor panel is unchanged by this
public demo change. No live FXCM SDK/market requests, paid services, trading,
main/backup/fix branch updates or automatic production cutover.
