"""Capital.com Demo *proposed* outbound proxy policy; OFFLINE ONLY.

Pure policy evaluation: accepts only the narrow intended prices GET shape,
never uses credentials, sockets, provider data, or Render configuration.
A passing simulated rule-set is NOT proof of deployed network isolation.

The separate real egress boundary must enforce HTTP method AND path after
TLS termination, prevent CONNECT tunnels/bypass, and keep trading-capable
tokens in an isolated non-public process. Host/IP firewalls alone cannot
inspect HTTPS methods or paths.
"""
from __future__ import annotations

from urllib.parse import parse_qsl, urlsplit
from capital_demo_offline_adapter import DEMO_BASE_URL, RESOLUTIONS, _valid_epic
from capital_demo_https_transport import _validate

MODE = "CAPITAL_DEMO_PROPOSED_EGRESS_CONTRACT_OFFLINE_V1"
GATEWAY_POLICY = {
    "defaultDeny": True,
    "upstreamScheme": "https",
    "upstreamAuthority": urlsplit(DEMO_BASE_URL).netloc,
    "allowedMethods": ["GET"],
    "pathPolicy": "EXACT_DEMO_PRICES_EPIC_ONLY",
    "allowedQueryFieldsInOrder": ["resolution", "from", "to", "max"],
    "requireBrokerTlsCertificateHostnameValidation": True,
    "rejectRedirects": True,
    "rejectNon2xx": True,
    "denyHttpConnectTunnels": True,
    "denyWebsocketUpgrade": True,
    "denyArbitraryForwardProxy": True,
    "forbidTradingHost": True,
    "requireTokenHolderToBeSeparatePrivateProcess": True,
    "denyTokenAccessFromPublicUiOrResearchWorkers": True,
    "denyDirectEgressBypassingGateway": True,
    "enforceHttpPathAfterTlsTermination": True,
}

def _safe(reason):
    return {
        "mode": MODE, "status": "BLOCKED",
        "reason": reason,
        "simulatedPriceGetShapeAllowed": False,
        "proposedGatewayProfileMatchesRequirements": False,
        "actualProxyInstalledAndEnforcing": False,
        "realNetworkIsolationVerified": False,
        "credentialsIsolatedOnHost": False,
        "providerTermsVerified": False,
        "sourceRightsApproved": False,
        "providerRequestsMade": 0,
        "brokerOrdersSent": 0,
        "signal": "WAIT", "executable": False,
        "paperOrdersAllowed": False, "liveOrdersAllowed": False,
    }


def inspect_proposed_profile(proposed):
    """Compare a proposed, non-secret design against the exact contract.

    This is a CONFIGURATION SHAPE exercise, NOT a verified deploy audit.
    A supplied dict can always lie and is never trusted as external proof.
    """
    if type(proposed) is not dict or proposed != GATEWAY_POLICY:
        return _safe("PROPOSED_POLICY_MISSING_OR_DIVERGENT")
    return {
        **_safe("PROPOSED_DESIGN_ONLY_REQUIRES_INDEPENDENT_EGRESS_ATTESTATION"),
        "status": "SIMULATED_DESIGN_CONTRACT_MATCH_ONLY",
        "proposedGatewayProfileMatchesRequirements": True,
    }


def inspect_intended_request(method, url, header_names, *,
                             redirect_attempted=False,
                             effective_url=None):
    """Evaluate the request intended for a future proxy, never send it.

    Exact fixed headers' *names* are checked; never accept token values.
    Calling this cannot authorize a future provider request or orders.
    """
    rejected = _safe("NON_PRICE_ROUTE_OR_MUTATING_METHOD_REJECTED")
    if (type(method) is not str or type(url) is not str or
            type(header_names) not in (tuple, list) or
            len(header_names) != 2 or
            set(header_names) != {"CST", "X-SECURITY-TOKEN"} or
            redirect_attempted is not False or
            (effective_url is not None and effective_url != url)):
        return rejected
    try:
        u = urlsplit(url)
        q = parse_qsl(u.query, strict_parsing=True, keep_blank_values=True)
        if (u.scheme != "https" or u.netloc != GATEWAY_POLICY["upstreamAuthority"]
                or u.username is not None or u.password is not None
                or u.fragment or
                not u.path.startswith("/api/v1/prices/") or
                not _valid_epic(u.path.removeprefix("/api/v1/prices/")) or
                [k for k, _ in q] != GATEWAY_POLICY["allowedQueryFieldsInOrder"] or
                dict(q)["resolution"] not in {v[0] for v in RESOLUTIONS.values()}):
            return rejected
        # Reuse the actual request-validation contract, not a parallel
        # homegrown syntax that could silently become more permissive.
        _validate(method, url, {
            "CST": "S" * 32, "X-SECURITY-TOKEN": "T" * 32
        })
    except (TypeError, ValueError, KeyError, OverflowError, AttributeError):
        return rejected
    return {
        **_safe("SIMULATED_ALLOWLIST_MATCH_NOT_A_PERMISSION_TO_CONNECT"),
        "status": "SIMULATED_PRICE_GET_SHAPE_ONLY",
        "simulatedPriceGetShapeAllowed": True,
    }


if __name__ == "__main__":
    raise SystemExit("OFFLINE_ONLY_NO_PROXY_OR_PROVIDER_CONNECTION")
