"""Metadata-only gate for the pending CFI Lebanon read-only source inquiry."""


def readiness():
    return {
        'vendor': 'CFI Lebanon MT5',
        'status': 'AWAITING_OFFICIAL_CFI_CONFIRMATION',
        'instrumentConfirmed': False,
        'readOnlyApiConfirmed': False,
        'closedM15H1H4Confirmed': False,
        'renderCloudUseConfirmed': False,
        'costAndTermsConfirmed': False,
        'enabled': False,
        'networkRequests': 0,
        'signal': 'WAIT',
        'executable': False,
    }
