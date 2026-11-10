"""Strict local recorded-data intake. No network transport, filling or timestamp inference."""
import argparse
import hashlib
import json
import pathlib
import statistics
from ultimate_connectors import SPECS, load_export, utc, EvidenceIndex
from ultimate_paper import timestamp
from ultimate_walkforward import verify_dataset



def load_bundle(manifest_path):
    """Manifest pins an existing normalized export and its local legal-use evidence.
    Unknown rights are quarantined: no records are returned for replay.
    """
    path = pathlib.Path(manifest_path).resolve()
    manifest = json.loads(path.read_text())
    if manifest.get('schemaVersion') != 1 or manifest.get('kind') != 'recorded-evidence':
        raise ValueError('Expected recorded evidence bundle v1')
    file = (path.parent / manifest['file']).resolve()
    if file.parent != path.parent:
        raise ValueError('Export must be a direct sibling of manifest')
    actual = hashlib.sha256(file.read_bytes()).hexdigest()
    if actual != manifest.get('sha256'):
        raise ValueError('Recorded export SHA256 mismatch')
    for key in ('origin', 'retrievedUTC', 'timestampConvention', 'rights'):
        if not manifest.get(key):
            raise ValueError(f'Missing manifest {key}')
    utc(manifest['retrievedUTC'])
    if manifest['timestampConvention'] != 'UTC_OBSERVATION_AND_FIRST_AVAILABILITY':
        raise ValueError('Cannot infer availability from date-only observations')
    rights = manifest['rights']
    if rights.get('status') != 'VERIFIED_INTERNAL_RESEARCH' or not rights.get('evidenceReference'):
        raise ValueError('QUARANTINED: internal research rights evidence required')
    records = load_export(file)
    EvidenceIndex(records)  # rejects duplicates and unordered arrivals
    counts = {name: len(rows) for name, rows in records.items()}
    summary = {}
    for name, rows in records.items():
        gaps = [(utc(b['availableUTC'])-utc(a['availableUTC'])).total_seconds() for a,b in zip(rows, rows[1:])]
        delays = [(utc(row['availableUTC'])-utc(row['observedUTC'])).total_seconds() for row in rows]
        summary[name] = dict(count=len(rows), firstObservedUTC=rows[0]['observedUTC'] if rows else None,
                             lastObservedUTC=rows[-1]['observedUTC'] if rows else None,
                             firstAvailableUTC=rows[0]['availableUTC'] if rows else None,
                             lastAvailableUTC=rows[-1]['availableUTC'] if rows else None,
                             arrivalGapsOverFiveMinutes=sum(gap>300 for gap in gaps),
                             largestArrivalGapSeconds=max(gaps,default=None),
                             maxDeliveryLagSeconds=max(delays,default=None),
                             medianDeliveryLagSeconds=statistics.median(delays) if delays else None,
                             duplicateRows=0, inferredTimestamps=0, filledRows=0)
    return records, dict(sha256=actual, counts=counts, arrivals=summary,
                        manifest=manifest, independentlyAuthenticated=False,
                        note='Hash and local rights attestation do not independently authenticate provider origin; long gaps are reported without filling')


def load_prices(paths):
    documents, origins = [], []
    for path in paths:
        document, origin = verify_dataset(path)
        documents.append(document)
        origins.append(origin)
    frames = {}
    from validate_history import validate
    for name in ('15min', '1h', '4h'):
        rows = [row for document in documents for row in document['frames'][name]]
        frames[name] = sorted(rows, key=lambda row: timestamp(row['datetime']))
    document = dict(source='; '.join(d['source'] for d in documents), symbol='XAU/USD', frames=frames)
    validation = validate(document)  # includes duplicate/overlap/UTC/alignment checks
    coverage = {}
    for name, minutes in [('15min',15),('1h',60),('4h',240)]:
        rows = frames[name]
        expected = (timestamp(rows[-1]['datetime'])-timestamp(rows[0]['datetime']))//(minutes*60000)+1
        coverage[name] = dict(rows=len(rows), calendarGridSlots=expected,
                              absentCalendarSlots=expected-len(rows),
                              note='Calendar grid includes weekends/holidays; absence is not classified as a market-session defect without a session calendar')
    return document, dict(provenance=origins, validation=validation, gridCoverage=coverage,
                          rightsStatus='UNVERIFIED_FOR_PUBLIC_REDISTRIBUTION',
                          usage='Existing local archive inspection only; confirm source-specific internal-use and redistribution rights before new capture or distribution')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    parser.add_argument('--output', required=True)
    args = parser.parse_args()
    records, report = load_bundle(args.manifest)
    pathlib.Path(args.output).write_text(json.dumps(report, indent=2)+'\n')
