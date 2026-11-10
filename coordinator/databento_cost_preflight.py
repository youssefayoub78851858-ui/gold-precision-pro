"""Inspect an already-saved quote locally. Never requests metadata, data, trials or billing."""
import argparse
from decimal import Decimal
import json
import pathlib
from recorded_utils import ns


def amount(value):
    if isinstance(value,bool):raise ValueError('Invalid money amount')
    result=Decimal(str(value))
    if not result.is_finite() or result<0:raise ValueError('Nonnegative finite USD amounts required')
    return result


def assess(quote):
    required=('dataset','schema','symbols','startUTC','endUTC','quotedUTC','evidenceReference')
    if any(not quote.get(k) for k in required):raise ValueError('Exact request and saved quote receipt required')
    if quote['dataset']!='GLBX.MDP3' or quote['schema']!='trades' or quote.get('currency')!='USD':raise ValueError('Expected GC trades USD quote')
    import re
    if not isinstance(quote['symbols'],list) or any(not re.fullmatch(r'GC[FGHJKMNQUVXZ]\d{1,4}',s) for s in quote['symbols']):raise ValueError('Dated GC symbols required')
    if not ns(quote['startUTC'])<ns(quote['endUTC'])<=ns(quote['quotedUTC'])-86400*10**9:
        raise ValueError('Historical T+1 interval required; no recent/live request')
    keys=('estimatedDataUSD','licenseUSD','otherFeesUSD','taxUSD','eligibleCreditsUSD')
    missing=[k for k in keys if quote.get(k) is None]
    total=None
    values={k:amount(quote[k]) for k in keys if quote.get(k) is not None}
    if not missing:
        total=max(Decimal(0),values['estimatedDataUSD']-values['eligibleCreditsUSD'])+values['licenseUSD']+values['otherFeesUSD']+values['taxUSD']
    return dict(kind='LOCAL_QUOTE_REVIEW',exactRequest={k:quote[k] for k in required},currency='USD',missingCostComponents=missing,
                estimatedCashUSD=str(total) if total is not None else None,actualBilledUSD=None,
                quotedDataCostUSD=str(amount(quote['estimatedDataUSD'])) if quote.get('estimatedDataUSD') is not None else None,
                approvedToSpend=False,spendingCapUSD='0',networkEnabled=False,
                note='Estimate is not a bill or authorization; actual metered bytes may differ. Credits/account eligibility and source-specific licensing need confirmation. No API was called.')


if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('saved_quote')
    args=parser.parse_args();print(json.dumps(assess(json.loads(pathlib.Path(args.saved_quote).read_text())),indent=2))
