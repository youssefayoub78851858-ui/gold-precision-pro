"""Data coverage and gate audit on recorded local archives; never creates paper orders."""
import argparse
from collections import Counter
import json
import pathlib
from ultimate_import import load_prices, load_bundle
from ultimate_connectors import EvidenceIndex
from ultimate_walkforward import generate
from ultimate_paper import DEFAULTS

LAYERS = ('XAUUSD', 'DXY', 'US02Y', 'US10Y', 'GC', 'calendar', 'headlines', 'orderFlow')


def percent(count, total):
    return round(100 * count / total, 4) if total else None


def absence_research(rows):
    """Only removes ready bits. No substitution, relaxing gates, trades or signals."""
    baseline = sum(all(row['ready'][name] for name in LAYERS) for row in rows)
    result = []
    for removed in LAYERS:
        after = 0  # the mandatory removed layer is false for every observation
        result.append(dict(removedLayer=removed, availableObservationsLost=sum(r['ready'][removed] for r in rows),
                           completeCoverageAfterRemoval=after, additionalBlockedObservations=baseline-after,
                           marginalPerformanceEffect=None,
                           interpretation='NOT_IDENTIFIABLE_MISSING_BASELINE_EVIDENCE' if baseline == 0 else 'MANDATORY_DATA_GATE_VETO',
                           executionProhibited=True))
    return dict(kind='NON_EXECUTABLE_DATA_ABLATION', executable=False, executionProhibited=True,
                tradesEvaluated=False, baselineCompleteObservations=baseline,
                note='Removing absent layers cannot estimate economic effects. No layer is bypassed and no candidate/entry/return is generated.', experiments=result)


def audit(paths, bundle=None):
    document, price_report = load_prices(paths)
    records, evidence_report = load_bundle(bundle) if bundle else ({}, {'status':'NO_LOCAL_EVIDENCE_BUNDLE'})
    decisions = generate(document, DEFAULTS, records, diagnostics=True)
    index = EvidenceIndex(records)
    rows, reasons = [], {name: Counter() for name in LAYERS}
    ready_counts, blocked_counts, patterns = Counter(), Counter(), Counter()
    directional = 0
    directional_cases = []
    for item in decisions:
        decision = item['ultimate']
        price_ok = all(status['ok'] for status in decision['priceFrames'].values())
        ready = {'XAUUSD': price_ok}
        for name in LAYERS[1:]:
            ready[name] = decision['layers'][name]['status'] == 'READY'
            if not ready[name]:
                reasons[name][decision['layers'][name]['reason']] += 1
            elif decision['layers'][name].get('blocked'):
                reasons[name]['HIGH_IMPACT_EVENT_VETO_DESPITE_AVAILABLE_DATA'] += 1
        for frame, status in decision['priceFrames'].items():
            if not status['ok']:
                reasons['XAUUSD'][frame+': '+status['reason']] += 1
        ready_counts.update(name for name in LAYERS if ready[name])
        blocked_counts.update(decision['monitoring']['blocked'])
        patterns[' | '.join(decision['monitoring']['blocked']) or 'NONE'] += 1
        directional += decision['technicalCandidate'] in ('BUY','SELL')
        if decision['technicalCandidate'] in ('BUY','SELL'):
            directional_cases.append(dict(asOfUTC=item['asOfUTC'], technicalLabel=decision['technicalCandidate'], executable=False, risk=decision['risk'], blockers=decision['monitoring']['blocked']))
        chosen = index.snapshot(item['asOfUTC'])
        observed = [row['observedUTC'] for row in chosen.values()]
        from ultimate_paper import timestamp
        # For complete external data only: do not report a perfect skew for missing feeds.
        skew = (max(map(timestamp,observed))-min(map(timestamp,observed)))/1000 if len(observed)==7 and all(ready[n] for n in LAYERS[1:]) else None
        rows.append(dict(asOfUTC=item['asOfUTC'], ready=ready,
                         completeExternalObservedSkewSeconds=skew, blockers=decision['monitoring']['blocked']))
    total = len(rows)
    complete = sum(all(r['ready'].values()) for r in rows)
    group_ready = {'XAUUSD':ready_counts['XAUUSD'], 'DXY':ready_counts['DXY'], 'US02Y':ready_counts['US02Y'], 'US10Y':ready_counts['US10Y'], 'GC':ready_counts['GC'],
                   'news':sum(r['ready']['calendar'] and r['ready']['headlines'] for r in rows), 'OrderFlow':ready_counts['orderFlow']}
    coverage = {name:dict(readyObservations=ready_counts[name], requiredObservations=total,
                          coveragePct=percent(ready_counts[name], total), failureReasons=dict(reasons[name])) for name in LAYERS}
    report = dict(kind='RECORDED_DATA_GATE_AUDIT', executable=False, statisticallyValidated=False,
                  denominator=dict(observedM15Decisions=total, note='Decision instants from existing M15 bars, not an exchange-session completeness claim'),
                  prices=price_report, externalEvidence=evidence_report, layerCoverage=coverage,
                  sourceGroupCoverage={name:dict(ready=count, coveragePct=percent(count,total)) for name,count in group_ready.items()},
                  meanRequiredLayerCoveragePct=percent(sum(ready_counts.values()),total*len(LAYERS)),
                  completeRequiredDataObservations=complete, completeRequiredDataCoveragePct=percent(complete,total),
                  technicalDirectionalObservations=directional, directionalResearchCases=directional_cases,
                  allActualGatesClear=sum(not r['blockers'] for r in rows), gateBlockCounts=dict(blocked_counts),
                  blockerPatterns=[dict(count=count, gates=gates) for gates,count in patterns.most_common()],
                  rightsAssessment='XAU archive public redistribution/internal entitlement not established; data-validity percentages do not confer rights',
                  findings=['Each absent external layer is an independent mandatory blocker; removing only one cannot unlock Ultimate',
                            'Daily FRED series and delayed ICE/CME quotes cannot satisfy five-minute intraday freshness by relabeling retrieval time',
                            'Calendar scheduled-event coverage is not comprehensive real-time headline coverage; future unknown news cannot be declared covered',
                            'The unchanged plus-30-minute headline coverage requirement conflicts with genuine past-only headline availability; intake rejects future completeness attestations rather than bypassing this gate'],
                  absenceResearch=absence_research(rows))
    return report, rows


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('datasets',nargs='+')
    parser.add_argument('--bundle')
    parser.add_argument('--output',required=True)
    parser.add_argument('--absence-output')
    args = parser.parse_args()
    report, _ = audit(args.datasets,args.bundle)
    pathlib.Path(args.output).write_text(json.dumps(report,indent=2,allow_nan=False)+'\n')
    if args.absence_output:
        pathlib.Path(args.absence_output).write_text(json.dumps(report['absenceResearch'],indent=2,allow_nan=False)+'\n')
