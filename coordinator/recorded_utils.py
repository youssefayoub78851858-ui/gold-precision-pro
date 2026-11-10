"""Pure local receipt helpers; exact nanoseconds, no HTTP or credential handling."""
import calendar
import datetime as dt
import hashlib
import json
import pathlib
import re
import subprocess


def ns(value, encoding='ISO8601_NS'):
    if encoding == 'UNIX_NS':
        if isinstance(value, bool) or not re.fullmatch(r'[0-9]+', str(value)):
            raise ValueError('Exact integer nanoseconds required; floats/guessed units forbidden')
        result = int(value)
        if not 0 <= result < 2**64-1:
            raise ValueError('Invalid or undefined nanoseconds')
        return result
    match = re.fullmatch(r'(\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2})(?:\.(\d{1,9}))?(?:Z|\+00:00)', str(value))
    if not match:
        raise ValueError('Explicit UTC ISO timestamp required')
    stamp = dt.datetime.strptime(match[1], '%Y-%m-%dT%H:%M:%S')
    return calendar.timegm(stamp.timetuple())*10**9 + int((match[2] or '').ljust(9,'0'))


def iso_ns(value):
    seconds, fraction = divmod(value, 10**9)
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+f'.{fraction:09d}Z'


def iso_ms(value, ceil=False):
    millis = (value+999999)//1000000 if ceil else value//1000000
    seconds, fraction = divmod(millis, 1000)
    return dt.datetime.fromtimestamp(seconds, dt.timezone.utc).strftime('%Y-%m-%dT%H:%M:%S')+f'.{fraction:03d}Z'


def pinned_file(manifest_path, kind):
    path = pathlib.Path(manifest_path).resolve()
    m = json.loads(path.read_text())
    if m.get('kind') != kind or m.get('manifestVersion') != 1:
        raise ValueError('Unsupported local manifest')
    file = (path.parent/m['file']).resolve()
    if file.parent != path.parent:
        raise ValueError('Input must be a direct sibling of manifest')
    raw = file.read_bytes()
    if hashlib.sha256(raw).hexdigest() != m.get('sha256'):
        raise ValueError('Source SHA256 mismatch')
    return m, raw


def rights(m):
    r = m.get('rights',{})
    if r.get('status') != 'VERIFIED_INTERNAL_RESEARCH' or r.get('algorithmicResearchAuthorized') is not True or not r.get('evidenceReference'):
        raise ValueError('QUARANTINED: source-specific private algorithmic research rights required')
    return r


def validate_v2(records):
    result = subprocess.run(['node',str(pathlib.Path(__file__).with_name('ultimate_v2_contracts.js'))],
                            input=json.dumps(records),text=True,capture_output=True)
    if result.returncode:
        raise ValueError('Existing protection contract rejected export: '+(result.stdout or result.stderr))
