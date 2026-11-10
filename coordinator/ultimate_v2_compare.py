"""Re-evaluate archived prices under frozen v1 and independent v2. No new holdout claim."""
import argparse
import hashlib
import json
import pathlib
import subprocess
from ultimate_import import load_prices
from ultimate_paper import DEFAULTS
from ultimate_v2_intake import load_bundle


def compare(paths, bundle=None):
    doc, price_report = load_prices(paths)
    records, receipt = load_bundle(bundle) if bundle else ({}, {'status':'NO_V2_EVIDENCE_BUNDLE'})
    c = DEFAULTS
    risk = {k:c[k] for k in ('riskFraction','dailyLossFraction','valuePerPoint','lotStep','minLot','maxLot','commissionPerLot','slippage')}
    risk.update(equity=c['initialBalance'],dailyLoss=0,activeTrades=0,killSwitch=False)
    payload=dict(frames=doc['frames'],records=records,spread=c['spread'],risk=risk)
    result=subprocess.run(['node',str(pathlib.Path(__file__).with_name('ultimate_v2_replay.js'))],input=json.dumps(payload),text=True,capture_output=True,check=True)
    report=json.loads(result.stdout)
    report['priceProvenance']=price_report
    report['externalEvidence']=receipt
    report['costAssumptions']=c
    report['modelSHA256']={name:hashlib.sha256(pathlib.Path(__file__).with_name(name).read_bytes()).hexdigest() for name in ('v3_ultimate.js','ultimate_v2.js','ultimate_v2_contracts.js','ultimate_v2_replay.js')}
    return report


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('datasets',nargs='+')
    parser.add_argument('--bundle')
    parser.add_argument('--output',required=True)
    args=parser.parse_args()
    pathlib.Path(args.output).write_text(json.dumps(compare(args.datasets,args.bundle),indent=2,allow_nan=False)+'\n')
