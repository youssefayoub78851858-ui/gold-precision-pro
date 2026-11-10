"""Fabricated unit records stay in temporary directories; never market performance."""
import hashlib
import json
import pathlib
import tempfile
import unittest
from ultimate_connectors import EvidenceIndex, validate_records
from ultimate_import import load_bundle, load_prices
from ultimate_coverage import LAYERS, absence_research
from import_fred_recorded import convert


def record(**changes):
    return dict(mode='recorded', source='FABRICATED UNIT INPUT ONLY', instrument='DXY',
                entitlementVerified=True, observedUTC='2026-09-01T12:00:00Z',
                availableUTC='2026-09-01T12:01:00Z', previous=100, value=99, **changes)


class RecordedIntake(unittest.TestCase):
    def test_duplicate_conflict_arrival_and_lookahead(self):
        row = record()
        for rows in [[row,row],[row,{**row,'value':98}], [row,{**row,'observedUTC':'2026-09-01T11:59:00Z','availableUTC':'2026-09-01T12:02:00Z'}]]:
            with self.assertRaises(ValueError):
                EvidenceIndex({'DXY':rows})
        index = EvidenceIndex({'DXY':[row]})
        self.assertEqual(index.snapshot('2026-09-01T12:00:59Z'),{})
        self.assertEqual(index.snapshot('2026-09-01T12:01:00Z')['DXY'],row)
        with self.assertRaises(ValueError):
            validate_records({'UNKNOWN':[]})

    def test_bundle_digest_rights_and_path(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            export=root/'test-only.json'
            export.write_text(json.dumps({'DXY':[record()]}))
            manifest=dict(schemaVersion=1,kind='recorded-evidence',file=export.name,
                          sha256=hashlib.sha256(export.read_bytes()).hexdigest(), origin='FABRICATED UNIT TEST',
                          retrievedUTC='2026-09-02T00:00:00Z',timestampConvention='UTC_OBSERVATION_AND_FIRST_AVAILABILITY',
                          rights={'status':'UNVERIFIED'})
            path=root/'manifest.json'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'QUARANTINED'):
                load_bundle(path)
            manifest['rights']={'status':'VERIFIED_INTERNAL_RESEARCH','evidenceReference':'UNIT TEST ATTESTATION ONLY'}
            path.write_text(json.dumps(manifest))
            records,report=load_bundle(path)
            self.assertEqual(len(records['DXY']),1)
            self.assertFalse(report['independentlyAuthenticated'])
            export.write_text(export.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'SHA256'):
                load_bundle(path)
            manifest['file']='../outside.json'
            path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'sibling'):
                load_bundle(path)

    def test_news_cannot_claim_future_completeness(self):
        row=dict(mode='recorded',source='FABRICATED UNIT INPUT',instrument='GOLD_USD_NEWS',
                 entitlementVerified=True,observedUTC='2026-09-01T12:00:00Z',availableUTC='2026-09-01T12:00:00Z',
                 events=[],coverageStartUTC='2026-09-01T11:00:00Z',coverageEndUTC='2026-09-01T13:00:00Z')
        with self.assertRaisesRegex(ValueError,'future headline'):
            validate_records({'headlines':[row]})
        row['coverageEndUTC']=row['availableUTC']
        self.assertEqual(validate_records({'headlines':[row]})['headlines'][0],row)

    def test_local_fred_missing_dates_and_first_availability(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            csv=root/'unit.csv';csv.write_text('observation_date,DGS2\n2026-09-01,4.0\n2026-09-02,.\n2026-09-03,4.1\n')
            meta=dict(sha256=hashlib.sha256(csv.read_bytes()).hexdigest(),series='DGS2',
                      rightsStatus='PUBLIC_DOMAIN_CITATION_REQUESTED',sourceReference='FABRICATED UNIT DATA',observations={})
            sidecar=root/'timing.json';sidecar.write_text(json.dumps(meta))
            with self.assertRaisesRegex(ValueError,'availability'):
                convert(csv,sidecar)
            for date in ('2026-09-01','2026-09-03'):
                meta['observations'][date]=dict(observedUTC=date+'T19:00:00Z',availableUTC=date+'T20:30:00Z',evidenceReference='FABRICATED UNIT RECEIPT')
            sidecar.write_text(json.dumps(meta))
            records,report=convert(csv,sidecar)
            self.assertEqual(report['missingDates'],['2026-09-02'])
            self.assertEqual(len(records['US02Y']),1)
            self.assertEqual(records['US02Y'][0]['previous'],4.0)
            self.assertFalse(report['intradayUsable'])

    def test_price_merge_duplicates_rejected_and_absence_only_removes(self):
        price=pathlib.Path(__file__).parent.parent/'research/recorded/2026-09-bid.json'
        with self.assertRaises(ValueError):
            load_prices([price,price])
        empty={'ready':{name:False for name in LAYERS}}
        full={'ready':{name:True for name in LAYERS}}
        result=absence_research([empty,full])
        self.assertFalse(result['executable'])
        self.assertFalse(result['tradesEvaluated'])
        for experiment in result['experiments']:
            self.assertEqual(experiment['additionalBlockedObservations'],1)
            self.assertEqual(experiment['completeCoverageAfterRemoval'],0)
            self.assertTrue(experiment['executionProhibited'])
            self.assertIsNone(experiment['marginalPerformanceEffect'])

    def test_future_holdout_excludes_old_data_and_freeze_tampering(self):
        from ultimate_forward_plan import validate_plan, new_observation_eligible
        path=pathlib.Path(__file__).parent.parent/'research/ultimate-prospective-plan.json'
        plan=validate_plan(path)
        self.assertFalse(new_observation_eligible(plan,'2026-10-30T12:00:00Z','2026-11-12T12:00:00Z'))
        self.assertTrue(new_observation_eligible(plan,'2026-11-12T12:00:00Z','2026-11-12T12:00:01Z'))
        self.assertFalse(new_observation_eligible(plan,'2026-11-12T12:00:00Z','2026-11-12T11:59:59Z'))
        with tempfile.TemporaryDirectory() as directory:
            altered=dict(plan)
            altered['strategySHA256']={**plan['strategySHA256'],'coordinator/v3_ultimate.js':'0'*64}
            file=pathlib.Path(directory)/'tampered.json';file.write_text(json.dumps(altered))
            with self.assertRaisesRegex(ValueError,'freeze mismatch'):
                validate_plan(file)

    def test_absence_report_cannot_be_used_as_paper_decision(self):
        from ultimate_paper import PaperAccount
        report=absence_research([{'ready':{name:False for name in LAYERS}}])
        with tempfile.TemporaryDirectory() as directory:
            account=PaperAccount(pathlib.Path(directory)/'paper.sqlite3')
            try:
                with self.assertRaisesRegex(ValueError,'non-executable research'):
                    account.step({'datetime':'2026-09-01T12:00:00Z','open':100,'high':101,'low':99,'close':100},
                                 {'asOfUTC':'2026-09-01T12:15:00Z'},evaluator=lambda _:report)
                self.assertFalse(account.summary()['position'])
                self.assertFalse(account.summary()['trades'])
                self.assertEqual(account.db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],0)
            finally:
                account.close()
