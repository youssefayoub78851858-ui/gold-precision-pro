# FXCM native SDK -> private research intake contract (offline preparation)

Prepared after the official FXCM Linux archive passed static ABI, C++ compile
and symbol link checks. This module does not load or call the provider SDK.

Source: coordinator/fxcm_native_offline_boundary.js
Candidate future producer schema: an in-memory JSON object with:
- provider = FXCM
- source = FOREXCONNECT_NATIVE_CPP
- instrument = XAU/USD
- receivedUTC = strictly UTC ISO 8601 timestamp
- frames = {M15, H1, H4}, each an ordered list of CLOSED candle objects.
- each candle = {openTime, bid:{open,high,low,close}, ask:{open,high,low,close}}.

These fields are a proposed internal hand-off schema; they have NOT been
shown to be the native output format of FXCM. The future licensed C++ adapter
would have to convert real native records and independently verify their
clock basis, session dates, provenance and entitlements.

The validator rejects incorrect source identity, forming candles, UTC
misalignment, duplicate or out-of-order timestamps, crossed Bid/Ask
and divergent M15 versus H1/H4 OHLC aggregates. It reports any apparent
gaps as unverified until a separately validated FXCM session calendar exists.

The output never contains candles. It always says WAIT, executable:false,
researchEligible:false, paperOrdersAllowed:false, sdkLoaded:false,
sourceRequestsMade:0 and no price/output transport to an engine.
Caller-side claims to hold a signed EULA, data entitlement or signal
authorization do not override these gates.

16 CI scenarios are pure synthetic records; no API keys, SDK usage,
FXCM login, real broker market-data request, paid subscription,
paper trading, real trading, deployment or production change.
