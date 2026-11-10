"""Offline replay with transactional content-addressed audit storage. No network or fills."""
import argparse
import hashlib
import json
import pathlib
import sqlite3
import subprocess


def replay(fixture, database):
    parsed = json.loads(pathlib.Path(fixture).read_bytes())
    canonical = json.dumps(parsed, sort_keys=True, separators=(',', ':')).encode()
    identity = hashlib.sha256(canonical).hexdigest()
    result = subprocess.run(['node', str(pathlib.Path(__file__).with_name('v3_ultimate.js')), str(fixture)], check=True, capture_output=True, text=True)
    report = json.loads(result.stdout)
    assert report['executable'] is False and report['signal'] == 'WAIT'
    with sqlite3.connect(database) as db:
        db.execute('CREATE TABLE IF NOT EXISTS ultimate_audit (id TEXT PRIMARY KEY, as_of TEXT NOT NULL, input_json TEXT NOT NULL, report_json TEXT NOT NULL)')
        db.execute('INSERT OR IGNORE INTO ultimate_audit VALUES (?,?,?,?)', (identity, report['asOfUTC'], canonical.decode(), json.dumps(report, sort_keys=True)))
    return {'observationID': identity, 'report': report}


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('fixture')
    parser.add_argument('--database', required=True, help='Local SQLite audit file')
    args = parser.parse_args()
    print(json.dumps(replay(args.fixture, args.database), indent=2))
