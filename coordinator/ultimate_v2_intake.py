"""Local-only v2 evidence bundle validation. Legacy intake remains unchanged."""
import argparse
import csv
import hashlib
import json
import pathlib
import subprocess
from ultimate_connectors import utc


def load_bundle(path):
    path = pathlib.Path(path).resolve()
    manifest = json.loads(path.read_text())
    if manifest.get('schemaVersion') != 2 or manifest.get('kind') != 'ultimate-v2-recorded-evidence':
        raise ValueError('Expected independent Ultimate v2 bundle')
    file = (path.parent / manifest['file']).resolve()
    if file.parent != path.parent:
        raise ValueError('Evidence export must be a sibling of manifest')
    if hashlib.sha256(file.read_bytes()).hexdigest() != manifest.get('sha256'):
        raise ValueError('Evidence SHA256 mismatch')
    if not manifest.get('origin') or not manifest.get('availabilityReceiptReference'):
        raise ValueError('Origin and first-availability receipt required')
    utc(manifest['retrievedUTC'])
    rights = manifest.get('rights', {})
    if rights.get('status') != 'VERIFIED_INTERNAL_RESEARCH' or rights.get('algorithmicResearchAuthorized') is not True or not rights.get('evidenceReference'):
        raise ValueError('QUARANTINED: algorithmic research rights not established')
    if file.suffix == '.json':
        records = json.loads(file.read_text())
    else:
        records = {}
        with file.open(newline='') as stream:
            for row in csv.DictReader(stream):
                records.setdefault(row['layer'], []).append(json.loads(row['payload']))
    if not isinstance(records, dict) or any(not isinstance(rows,list) for rows in records.values()):
        raise ValueError('Expected evidence layer arrays')
    if any(not isinstance(row,dict) or row.get('mode') != 'recorded' for rows in records.values() for row in rows):
        raise ValueError('Recorded bundles cannot contain synthetic evidence')
    validator = pathlib.Path(__file__).with_name('ultimate_v2_contracts.js')
    result = subprocess.run(['node', str(validator)], input=json.dumps(records), capture_output=True, text=True, check=False)
    if result.returncode:
        raise ValueError('Invalid v2 contract: '+(result.stdout or result.stderr))
    for rows in records.values():
        if any(utc(row['availableUTC']) > utc(manifest['retrievedUTC']) or (row['role']=='DAILY_CONTEXT' and utc(row['releaseScheduleAvailableUTC'])>utc(manifest['retrievedUTC'])) for row in rows):
            raise ValueError('A captured bundle cannot contain later arrival receipts')
    return records, dict(contractVersion=2, sha256=manifest['sha256'], origin=manifest['origin'],
                         counts={name:len(rows) for name,rows in records.items()},
                         rightsStatus='LOCALLY_ATTESTED_NOT_INDEPENDENTLY_VERIFIED',
                         networkEnabled=False, note='No export automation or vendor entitlement is inferred from a file')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('manifest')
    args = parser.parse_args()
    _, report = load_bundle(args.manifest)
    print(json.dumps(report,indent=2))
