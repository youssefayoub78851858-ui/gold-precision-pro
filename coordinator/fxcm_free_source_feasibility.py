"""Free FXCM ForexConnect feasibility GATE for the current review container.

No FXCM credentials, account, provider network, subscriptions, SDK imports,
deployment or trading. This is a finite evidence inventory, not a live test.

Evidence:
- https://github.com/fxcm/ForexConnectAPI (Linux, TSII demo, EULA)
- https://www.fxcm.com/markets/algorithmic-trading/compare-api/ (demo, free)
- https://forex-connect-api-docs.fxcorporate.com/Python/get_history_py
  (history is account-specific)
- https://pypi.org/project/forexconnect/1.6.5/
- https://pypi.org/project/forexconnect/ (binary wheels verified 2026-11-13)
A current signed supported SDK, OS/runtime entitlement, secure read-only
credential or gateway and actual XAUUSD parity still require external proof.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PROVIDER = "FXCM_FOREXCONNECT"
SUPPORTED_PUBLIC_LINUX_PYTHON_ABIS = ("cp35", "cp36", "cp37")
SOURCES = {
    "officialSdk": "https://github.com/fxcm/ForexConnectAPI",
    "officialCompare": "https://www.fxcm.com/markets/algorithmic-trading/compare-api/",
    "officialHistoryDocs": "https://forex-connect-api-docs.fxcorporate.com/Python/get_history_py",
    "pyPiLegacyWheel": "https://pypi.org/project/forexconnect/1.6.5/",
    "pyPiProject": "https://pypi.org/project/forexconnect/",
}
REQUIRED_DOCKER_MARKERS = ("FROM node:24-bookworm-slim", "python3")


def _python_abi(version):
    if (not isinstance(version, tuple) or len(version) != 2 or
            any(isinstance(x, bool) or not isinstance(x, int) or x < 0 or x > 99
                for x in version)):
        raise ValueError("Python version must be (major, minor) integers")
    return f"cp{version[0]}{version[1]}"


def assess_fxcm_free_source(root=ROOT, *, python_version=None):
    """Proof-inventory only: never authorize vendor login or research signals."""
    version = (sys.version_info.major, sys.version_info.minor) if python_version is None else python_version
    abi = _python_abi(version)
    try:
        docker_text = (Path(root) / "coordinator" / "Dockerfile").read_text(encoding="utf-8")
        container_shape = all(marker in docker_text for marker in REQUIRED_DOCKER_MARKERS)
    except (OSError, UnicodeError):
        container_shape = False

    compatible_public_wheel = abi in SUPPORTED_PUBLIC_LINUX_PYTHON_ABIS
    reasons = [
        "FXCM_DEMO_XAUUSD_HISTORY_AND_LIVE_ENTITLEMENT_NOT_TESTED",
        "FXCM_PYTHON_3_11_OR_ALTERNATIVE_SUPPORTED_LINUX_SDK_NOT_PROVEN" if not compatible_public_wheel
        else "FXCM_LEGACY_PYTHON_3_7_RUNTIME_ISOLATION_NOT_TESTED",
        "FXCM_CLOUD_LICENCE_AND_EULA_DETAILS_NEED_CONFIRMATION",
        "FXCM_ACCOUNT_READ_ONLY_CREDENTIAL_OR_ORDER_PROHIBITION_NOT_VERIFIED",
        "FXCM_LIVE_BID_ASK_TO_HISTORY_PARITY_AND_UTC_NOT_TESTED",
        "FXCM_DEMO_LONG_RUNNING_SESSION_AND_RECONNECT_NOT_TESTED",
        "FXCM_NO_LIVE_API_CALL_OR_PROVIDER_PAYMENT_AUTHORIZED",
    ]
    if not container_shape:
        reasons.insert(0, "CURRENT_REVIEW_DOCKERFILE_NOT_VERIFIED")

    return {
        "mode": "OFFLINE_FXCM_PRE_SUBSCRIPTION_FEASIBILITY",
        "provider": PROVIDER,
        "decision": "NO_GO_UNTIL_PROVEN",
        "signal": "WAIT",
        "executable": False,
        "researchEligible": False,
        "readyForPaper": False,
        "readyForTrading": False,
        "sourceRequestsMade": 0,
        "vendorLogins": 0,
        "secretReads": 0,
        "payments": 0,
        "currentPythonABI": abi,
        "officialPublicLinuxWheelABIs": list(SUPPORTED_PUBLIC_LINUX_PYTHON_ABIS),
        "publishedLinuxWheelMatchesCurrentPython": compatible_public_wheel,
        "reviewDockerShapeVerified": container_shape,
        "officialClaims": {
            "demoAccountOptionDocumented": True,
            "linuxSdkSupportDocumented": True,
            "xauusdHistoricalCoverageListed": True,
            "historyApiIsAccountSpecific": True,
            "sdkCanCreateTradesThereforeNeedsIsolation": True,
        },
        "unverifiedLiveConditions": {
            "xauusdOnOurDemoAccount": False,
            "historicalBidAndAskSample": False,
            "streamingBidAndAskSample": False,
            "sameFeedAndSessionParity": False,
            "modernLinuxRuntimeSuccessfullyTested": False,
            "safeReadOnlyAuthentication": False,
            "privateRenderLicenseAndRetentionFullyVerified": False,
            "independentMarketSessionClock": False,
        },
        "blockingReasons": reasons,
        "documentation": SOURCES,
        "nextAction": (
            "Ask FXCM whether supported Linux/Java or modern Python read-only "
            "adapter runs on Debian Bookworm with cloud private demo; request "
            "concrete XAUUSD M15/H1/H4 BID/ASK sample and exact licence terms."
        ),
        "note": "No proof of a working free connection or trading strategy.",
    }


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output")
    args = parser.parse_args()
    body = json.dumps(assess_fxcm_free_source(), ensure_ascii=False, indent=2) + "\n"
    if args.output:
        p = Path(args.output)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
    else:
        print(body, end="")


if __name__ == "__main__":
    main()
