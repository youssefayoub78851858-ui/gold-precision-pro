"""Offline chronological evaluation. Same BID/cost/account simulator for V2 and Ultimate.
Fixed parameters: training/validation windows are diagnostics, never optimization.
"""
import argparse
import hashlib
import json
import pathlib
import random
import statistics
import subprocess
import tempfile
from ultimate_paper import PaperAccount, DEFAULTS, timestamp, iso, BAR_MS
from ultimate_connectors import load_export, EvidenceIndex
from validate_history import validate


def verify_dataset(path):
    path = pathlib.Path(path)
    manifest = json.loads(path.with_name('manifest.json').read_text())
    item = next((d for d in manifest['datasets'] if d['file'] == path.name), None)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if not item or digest != item['sha256'] or item.get('priceConvention') != 'BID':
        raise ValueError('Unverified recorded file digest or price convention')
    doc = json.loads(path.read_text())
    validate(doc)
    if any(word in doc['source'].lower() for word in ('synthetic', 'fabricated', 'mock')):
        raise ValueError('Synthetic source is not historical evidence')
    return doc, item


def generate(document, config, evidence=None, diagnostics=False):
    risk = {k: config[k] for k in ('riskFraction', 'dailyLossFraction', 'valuePerPoint', 'lotStep', 'minLot', 'maxLot', 'commissionPerLot', 'slippage')}
    risk.update(equity=config['initialBalance'], dailyLoss=0, killSwitch=False, activeTrades=0)
    prepared = {}
    if evidence:
        index = EvidenceIndex(evidence)
        for bar in document['frames']['15min']:
            as_of = iso(timestamp(bar['datetime']) + BAR_MS)
            prepared[as_of] = index.snapshot(as_of)
    data = dict(frames=document['frames'], evidence=prepared, spread=config['spread'], risk=risk, diagnostics=diagnostics)
    result = subprocess.run(['node', str(pathlib.Path(__file__).with_name('ultimate_signals.js'))], input=json.dumps(data), text=True, capture_output=True, check=True)
    return json.loads(result.stdout)


def metrics(summary):
    trades = summary['trades']
    net = [t['net'] for t in trades]
    peak = balance = summary['config']['initialBalance']
    max_dd = 0
    for value in net:
        balance += value
        peak = max(peak, balance)
        max_dd = max(max_dd, peak - balance)
    # IID bootstrap is exploratory; serial dependence and low counts invalidate inference.
    ci = None
    if len(net) >= 30:
        rng = random.Random(20261110)
        means = sorted(statistics.mean(rng.choices(net, k=len(net))) for _ in range(1000))
        ci = [means[24], means[974]]
    losses = -sum(n for n in net if n < 0)
    return dict(trades=len(net), netPnL=sum(net), expectancyR=statistics.mean(t['net']/t['risk'] for t in trades) if trades else None, expectancy=statistics.mean(net) if net else None,
                profitFactor=sum(n for n in net if n > 0) / losses if losses else None,
                winRate=sum(n > 0 for n in net) / len(net) if net else None,
                maxClosedBalanceDrawdown=max_dd, bootstrapMean95=ci,
                openAtEnd=len(summary['position']), pendingAtEnd=len(summary['pending']),
                inference='INSUFFICIENT' if len(net) < 30 else 'EXPLORATORY_IID_ONLY')


def simulate(bars, decisions, engine, config, start, end):
    with tempfile.TemporaryDirectory() as directory:
        account = PaperAccount(pathlib.Path(directory) / 'paper.sqlite3', config)
        try:
            for bar, decision in zip(bars, decisions, strict=True):
                opened = timestamp(bar['datetime'])
                if not start <= opened < end:
                    continue
                raw = decision[engine]
                if engine == 'v2':
                    report = dict(signal='WAIT', executable=False, researchCandidate=raw['signal'] if raw['signal'] in ('BUY', 'SELL') else 'NONE', risk={'ok': True}, tradePlan={'stop': raw.get('stop'), 'target': raw.get('target')})
                else:
                    report = raw
                account.step({**bar, 'dataOrigin': 'RECORDED_BID_ARTIFACT'}, {'asOfUTC': iso(opened + BAR_MS)}, evaluator=lambda _, r=report: r)
            return metrics(account.summary())
        finally:
            account.close()


def run(paths, evidence_file=None):
    docs, provenance = [], []
    for path in paths:
        doc, origin = verify_dataset(path)
        docs.append(doc)
        provenance.append(origin)
    frames = {f: sorted([b for d in docs for b in d['frames'][f]], key=lambda b: timestamp(b['datetime'])) for f in ('15min', '1h', '4h')}
    document = dict(source='; '.join(d['source'] for d in docs), symbol='XAU/USD', frames=frames)
    validate(document)
    evidence = load_export(evidence_file) if evidence_file else {}
    bars = frames['15min']
    start, finish = timestamp(bars[0]['datetime']), timestamp(bars[-1]['datetime']) + BAR_MS
    # Fixed elapsed-calendar boundaries set before reading outcomes.
    span = finish - start
    cut1, cut2 = start + span * 50 // 100, start + span * 75 // 100
    windows = [('train', start, cut1), ('validation', cut1, cut2), ('test', cut2, finish)]
    folds = []
    week = 7 * 86400000
    cursor = start + 21 * 86400000
    while cursor + week <= finish:
        folds.append(('walk_forward_' + str(len(folds) + 1), cursor, cursor + week))
        cursor += week
    scenarios = []
    for label, spread, slippage, commission in [('base', .4, .1, 7), ('stress', .8, .3, 10)]:
        config = {**DEFAULTS, 'spread': spread, 'slippage': slippage, 'commissionPerLot': commission}
        decisions = generate(document, config, evidence)
        results = []
        for name, begin, end in windows + folds:
            result = {engine: simulate(bars, decisions, engine, config, begin, end) for engine in ('v2', 'ultimate')}
            results.append(dict(window=name, startUTC=iso(begin), endUTC=iso(end), trainingStartUTC=iso(start) if name.startswith('walk_forward') else None, trainingEndUTC=iso(begin) if name.startswith('walk_forward') else None, optimizationApplied=False, **result))
        reasons = {}
        for decision in decisions:
            for reason in decision['ultimate']['monitoring']['blocked']:
                reasons[reason] = reasons.get(reason, 0) + 1
        scenarios.append(dict(name=label, costs=config, windows=results, ultimateBlockedCounts=reasons))
    return dict(mode='RECORDED_BID_RESEARCH', executable=False, statisticallyValidated=False,
                provenance=provenance, evidenceLayersProvided=list(evidence), scenarios=scenarios,
                walkForwardPolicy='Fixed parameters, expanding history, weekly forward evaluation after 21 days; no fitting or selection. Each window resets account and purges pending/open positions at boundaries; warmup uses past bars only.',
                limitations=['BID OHLC, modeled constant ASK spread; no true intrabar sequence, variable spread or latency', 'Stop-first on ambiguous candles; gap stops fill at adverse open; targets capped at limit then adverse slippage', 'No forced liquidation at window end: open/pending counts disclosed and unrealized PnL excluded', 'IID bootstrap exploratory only; no dependence-adjusted statistical proof', 'September/October were previously researched: these are chronological OOS diagnostics, not untouched holdouts', 'Without recorded cross-market/news/trade-side evidence, Ultimate remains blocked; zero trades is not success'])


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('datasets', nargs='+')
    parser.add_argument('--evidence')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    result = run(args.datasets, args.evidence)
    pathlib.Path(args.output).write_text(json.dumps(result, indent=2, allow_nan=False) + '\n')
