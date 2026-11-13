# FXCM ForexConnect Linux static ABI audit — 2026-11-13

The official FXCM Linux archive (7,324,536 bytes) was downloaded and its
structure confirmed in the preceding CI run, including 47 library-like paths
and three Java JAR entries. The observed SHA-256 is pinned in the new static
ABI audit to prevent unnoticed archive substitution.

New GitHub Actions job uses the *node:24-bookworm-slim* base image family that
the private coordinator uses. It installs only Python 3 and binutils in an
ephemeral CI container, downloads the public FXCM GitHub archive, and
examines ELF binaries using **readelf**, which parses binary structures but
does not load/execute the provider SDK. It compares referenced SONAMEs to
other archive library names and the base image's installed library inventory.
It records the required GLIBC version and the base version, plus missing
shared libraries, in an artifact.

This is not a proof of runtime compatibility or an authorization to load
the SDK, log into FXCM or process actual XAU/USD data. Exact dynamic
linker behavior, Java binding, read-only account, EULA, current cloud
rights, live vs historical parity and accurate session timestamps remain
gated. The research signal stays WAIT; no trade execution or paper orders.

No production changes, provider credentials, provider market-data
requests, costs, new paid services or cloud deployment.
