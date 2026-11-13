# FXCM official Linux SDK C++ symbol link-only evidence

Builds on successful 2026-11-13 static ELF dependencies and C++ header syntax
CI. The next offline check in an isolated Bookworm container:
- Downloads public official FXCM ForexConnect Linux archive, pinned to an
  observed SHA-256 from the earlier successful archive metadata audit.
- Validates tar member names, writes only C++ headers, ELF shared libraries
  and safe same-directory library symlinks into a temporary CI folder.
- Compiles a throwaway C++ object that references
  CO2GTransport::createSession() without calling it.
- Links a throwaway shared object against the vendor libForexConnect using
  g++ and records linker status, warnings and ELF DT_NEEDED metadata.
- Critically: never runs the object, imports or loads FXCM SDK, accesses
  accounts, calls provider market-data API or makes trades.

A linkable symbol alone NEVER authorizes SDK use or cloud integration and
does not prove real functional runtime compatibility. Linking failure must
be diagnosed before attempting runtime code. Written FXCM EULA/cloud
rights, trading-disabled credentials, and actual XAU/USD data-quality
validation remain required before a staged demo connection.
No Render deploy and no payment or production branch change.
