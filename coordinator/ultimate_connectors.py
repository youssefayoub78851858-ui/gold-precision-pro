"""Prepared offline adapters for vendor exports. No HTTP clients, SDKs or credentials.
Live transport is intentionally absent; planning never sends requests.
"""
import bisect
import csv
import datetime as dt
import json
import math
import pathlib

SPECS = {
    'DXY': {'vendor': 'ICE export', 'instrument': 'DXY', 'licenseRequired': True},
    'US02Y': {'vendor': 'FRED export', 'instrument': 'DGS2', 'licenseRequired': False, 'requestTemplate': {'method':'GET', 'endpoint':'https://api.stlouisfed.org/fred/series/observations', 'parameters':{'series_id':'DGS2', 'file_type':'json'}, 'credentialName':'FRED_API_KEY'}},
    'US10Y': {'vendor': 'FRED export', 'instrument': 'DGS10', 'licenseRequired': False, 'requestTemplate': {'method':'GET', 'endpoint':'https://api.stlouisfed.org/fred/series/observations', 'parameters':{'series_id':'DGS10', 'file_type':'json'}, 'credentialName':'FRED_API_KEY'}},
    'GC': {'vendor': 'CME export', 'instrument': 'GC', 'licenseRequired': True},
    'calendar': {'vendor': 'Economic calendar export', 'instrument': 'USD_EVENTS', 'licenseRequired': True},
    'headlines': {'vendor': 'Licensed news export', 'instrument': 'GOLD_USD_NEWS', 'licenseRequired': True},
    'orderFlow': {'vendor': 'Licensed exchange trade export', 'instrument': 'GC_TRADES', 'licenseRequired': True},
}


def plan():
    return {name: {**spec, 'enabled': False, 'networkImplemented': False,
                   'credentialConfigured': False, 'requestsSent': 0,
                   'status': 'EXPORT_ONLY', 'note': 'FRED daily values are delayed context, not fresh intraday confirmation' if name.startswith('US') else 'Vendor entitlement must be verified before any future transport'} for name, spec in SPECS.items()}


def utc(value):
    t = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
    if t.tzinfo is None or t.utcoffset() != dt.timedelta(0):
        raise ValueError('UTC timestamp required')
    return t


def validate(name, row):
    if name not in SPECS or row.get('mode') != 'recorded' or not row.get('source', '').strip():
        raise ValueError('Recorded source and known layer required')
    if row.get('instrument') != SPECS[name]['instrument']:
        raise ValueError('Wrong instrument')
    observed, available = utc(row['observedUTC']), utc(row['availableUTC'])
    if available < observed:
        raise ValueError('Evidence cannot arrive before observation')
    if SPECS[name]['licenseRequired'] and row.get('entitlementVerified') is not True:
        raise ValueError('Export entitlement unverified')
    if name in ('DXY', 'US02Y', 'US10Y', 'GC'):
        if not all(isinstance(row.get(k), (int, float)) and not isinstance(row[k], bool) and math.isfinite(row[k]) and row[k] > 0 for k in ('previous', 'value')):
            raise ValueError('Invalid numeric reference')
    elif name in ('calendar', 'headlines'):
        if not isinstance(row.get('events'), list):
            raise ValueError('Events required')
        for event in row['events']:
            if utc(event['publishedUTC']) > available or event.get('impact') not in ('low', 'medium', 'high'):
                raise ValueError('Unknown or future publication')
            utc(event['timeUTC'])
        if name == 'headlines' and any(utc(e['timeUTC']) > available for e in row['events']):
            raise ValueError('Future headline')
        start, end = utc(row['coverageStartUTC']), utc(row['coverageEndUTC'])
        if start > end:
            raise ValueError('Reversed event coverage interval')
        if name == 'headlines' and end > available:
            raise ValueError('Cannot attest future headline coverage')
    else:
        if row.get('kind') != 'trades' or row.get('licensed') is not True:
            raise ValueError('Trade sides and licensing required')
        if not all(isinstance(row.get(k), (int, float)) and not isinstance(row[k], bool) and math.isfinite(row[k]) and row[k] >= 0 for k in ('buyVolume', 'sellVolume')) or row['buyVolume'] + row['sellVolume'] <= 0:
            raise ValueError('Invalid trade volumes')
    return row


def validate_records(records):
    if not isinstance(records, dict) or any(name not in SPECS for name in records):
        raise ValueError('Expected known evidence layer mapping')
    for name, rows in records.items():
        if not isinstance(rows, list):
            raise ValueError('Layer rows must be a list')
        previous = None
        seen = set()
        for row in rows:
            if not isinstance(row, dict):
                raise ValueError('Evidence row must be an object')
            validate(name, row)
            key = (utc(row['observedUTC']), utc(row['availableUTC']))
            if key in seen or (previous is not None and (key[1] <= previous[1] or key[0] < previous[0])):
                raise ValueError('Duplicate or reversed evidence arrival')
            seen.add(key)
            previous = key
    return records


class EvidenceIndex:
    def __init__(self, records):
        validate_records(records)
        self.records = records
        self.times = {name: [utc(row['availableUTC']) for row in rows] for name, rows in records.items()}

    def snapshot(self, as_of):
        result, cutoff = {}, utc(as_of)
        for name, rows in self.records.items():
            index = bisect.bisect_right(self.times[name], cutoff) - 1
            if index >= 0:
                result[name] = rows[index]
        return result


def snapshot(records, as_of):
    return EvidenceIndex(records).snapshot(as_of)


def load_export(path):
    path = pathlib.Path(path)
    if path.suffix == '.json':
        records = json.loads(path.read_text())
    else:
        records = {}
        # CSV has layer,payload columns; payload is canonical vendor-normalized JSON.
        with path.open(newline='') as file:
            for row in csv.DictReader(file):
                records.setdefault(row['layer'], []).append(json.loads(row['payload']))
    snapshot(records, '1970-01-01T00:00:00Z')  # validates every row without making it available
    return records


if __name__ == '__main__':
    print(json.dumps(plan(), indent=2))
