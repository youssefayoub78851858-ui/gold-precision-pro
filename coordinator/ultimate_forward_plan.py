"""Offline preregistration validator. No collection or trading entry point."""
import hashlib
import json
import pathlib
from ultimate_paper import timestamp


def validate_plan(path):
    path = pathlib.Path(path)
    plan = json.loads(path.read_text())
    root = pathlib.Path(__file__).resolve().parent.parent
    if plan['status'] != 'DRAFT_BLOCKED' or plan['networkEnabled'] or plan['executionEnabled'] or plan['providerRequestBudget'] != 0:
        raise ValueError('This preregistration must remain inactive')
    if timestamp(plan['earliestCaptureUTC']) <= timestamp(plan['freezeNotBeforeUTC']):
        raise ValueError('Future observations must follow strategy freeze')
    for name, expected in plan['strategySHA256'].items():
        file = (root / name).resolve()
        if not file.is_relative_to(root) or hashlib.sha256(file.read_bytes()).hexdigest() != expected:
            raise ValueError('Strategy freeze mismatch: '+name)
    return plan


def new_observation_eligible(plan, observed_utc, first_available_utc):
    observed, available = timestamp(observed_utc), timestamp(first_available_utc)
    return timestamp(plan['earliestCaptureUTC']) <= observed <= available


if __name__ == '__main__':
    import sys
    plan = validate_plan(sys.argv[1])
    print(json.dumps({'status':plan['status'],'freezeVerified':True,'networkEnabled':False,'executionEnabled':False}))
