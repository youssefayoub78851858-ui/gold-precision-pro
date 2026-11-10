"""Convert LOCAL saved FRED graph CSV with explicit first-availability sidecar.
Never downloads, assumes intraday release times, or copies a daily value to intraday rows.
"""
import argparse
import csv
import hashlib
import io
import json
import math
import pathlib
from ultimate_connectors import validate_records, utc


def convert(csv_path, sidecar_path):
    path = pathlib.Path(csv_path)
    raw = path.read_bytes()
    sidecar = json.loads(pathlib.Path(sidecar_path).read_text())
    if sidecar.get('sha256') != hashlib.sha256(raw).hexdigest():
        raise ValueError('CSV and availability sidecar digest mismatch')
    series = sidecar.get('series')
    layer = {'DGS2':'US02Y', 'DGS10':'US10Y'}.get(series)
    if layer is None or sidecar.get('rightsStatus') != 'PUBLIC_DOMAIN_CITATION_REQUESTED':
        raise ValueError('Only source-attributed public-domain DGS2/DGS10 supported')
    if not sidecar.get('sourceReference'):
        raise ValueError('Official source reference required')
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig')))
    date_field = 'observation_date' if 'observation_date' in (reader.fieldnames or []) else 'DATE'
    records, missing, previous, seen = [], [], None, set()
    last_date = None
    for row in reader:
        date = row[date_field]
        if date in seen or (last_date is not None and date <= last_date):
            raise ValueError('Duplicate or unordered FRED observation date')
        seen.add(date)
        last_date = date
        value = row[series]
        if value in ('', '.'):
            missing.append(date)
            continue
        value = float(value)
        if not math.isfinite(value) or value <= 0:
            raise ValueError('Invalid daily yield')
        timing = sidecar['observations'].get(date)
        if not timing:
            raise ValueError('Explicit observation and first-availability evidence missing')
        observed, available = utc(timing['observedUTC']), utc(timing['availableUTC'])
        if observed.date().isoformat() != date or not timing.get('evidenceReference') or available < observed:
            raise ValueError('Invalid date or availability attestation')
        if previous is not None:
            records.append(dict(mode='recorded', source=sidecar['sourceReference'], instrument=series,
                                observedUTC=timing['observedUTC'], availableUTC=timing['availableUTC'],
                                previous=previous, value=value, observationDate=date,
                                frequency='DAILY', units='PERCENT_PER_ANNUM',
                                availabilityEvidence=timing['evidenceReference']))
        previous = value
    result = {layer:records}
    validate_records(result)
    return result, dict(kind='LOCAL_FRED_DAILY_IMPORT', sourceSHA256=sidecar['sha256'],
                        missingDates=missing, normalizedRows=len(records),
                        intradayUsable=False, note='First nonmissing value is reference only; daily yields are not intraday prices or five-minute confirmations')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('csv')
    parser.add_argument('sidecar')
    parser.add_argument('--output',required=True)
    args = parser.parse_args()
    records, report = convert(args.csv,args.sidecar)
    pathlib.Path(args.output).write_text(json.dumps(records,indent=2)+'\n')
    print(json.dumps(report,indent=2))
