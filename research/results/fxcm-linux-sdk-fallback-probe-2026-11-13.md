# FXCM Linux SDK fallback availability check — 2026-11-13

FCLite Node and browser packages returned HTTP 404 from the documented
MyGet @gehtsoft scope registry during isolated GitHub Linux npm installs.
These failures do **not** prove the vendor discontinued packages: they may
require a different current URL or authorization. Do not automatically use
third-party mirrors or undocumented brokers.

Independent fallback: FXCM's verified official GitHub repository contains
ForexConnectAPI-1.6.5-Linux-x86_64.tar.gz (~7.3 MB). A read-only CI probe
downloads this public archive, verifies compressed tar integrity, computes
SHA-256, and inventories contained file names. It does not extract, load,
execute, or install code, log into FXCM, access price data, or modify
Docker/prod settings. Outcome JSON artifact:
fxcm-forexconnect-linux-archive-probe.

A successful archive metadata probe only confirms that the SDK distribution
is accessible, **not** that it can run on modern Debian Bookworm or that its
Java/C++ bindings handle read-only XAU/USD on our Demo account.
Legacy SDK EULA, cloud rights, read-only order isolation, native libraries,
XAUUSD session/UTC and BID/ASK parity must be proven independently.
No real trading, paid API or new subscriptions.

FXCM official source: https://github.com/fxcm/ForexConnectAPI
