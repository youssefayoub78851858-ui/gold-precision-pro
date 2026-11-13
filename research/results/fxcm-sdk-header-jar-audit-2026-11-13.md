# FXCM C++ header / Java jar metadata check (2026-11-13)

The previous CI commit cc669bb6 passed: static ELF readelf inventory
of official FXCM ForexConnect Linux 1.6.5 SDK showed 19 ELF shared
libraries, no missing referenced SONAMEs in the Debian Bookworm base
and max GLIBC_2.14 requirement against libc 2.36. This only proves
static dependencies are plausible, not that the SDK loads or functions.

This additional isolated job retrieves the exact same publicly available
archive with pinned SHA-256, reads the archive's source header entries
and Java JAR class metadata, and tries C++17 syntax-only compilation
of a public header. No link step, no SDK loading, no Java class execution,
no FXCM account, market request, order, subscription, deployment or key.

Results are recorded to fxcm-sdk-header-jar-audit JSON artifact.
A "PASSED" compile does not mean live integration or a license is
available. A "BLOCKED" compile should show a concrete compiler diagnostic.
Before real XAUUSD access, current FXCM API/EULA cloud permissions,
read-only access and price/timeframe/UTC data must be proved in writing.
Keep WAIT and all trading paths disabled.
