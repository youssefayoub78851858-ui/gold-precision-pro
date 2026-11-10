"""New temporal contracts. Fabricated fixture values are unit tests only."""
import hashlib
import json
import pathlib
import subprocess
import tempfile
import unittest
from ultimate_v2_intake import load_bundle

ROOT=pathlib.Path(__file__).resolve().parent.parent


def fixture():
    command="console.log(JSON.stringify(require(process.argv[1]).fixture('recorded')))"
    result=subprocess.run(['node','-e',command,str(ROOT/'coordinator/test_ultimate_v2.js')],check=True,text=True,capture_output=True)
    return json.loads(result.stdout)


class UltimateV2Contracts(unittest.TestCase):
    def test_new_contracts_and_no_execution(self):
        subprocess.run(['node',str(ROOT/'coordinator/test_ultimate_v2.js')],check=True,capture_output=True)

    def test_version_registry_preserves_previous_engine_and_reports(self):
        registry=json.loads((ROOT/'research/ultimate-versions.json').read_text())
        for version in registry['versions']:
            for name,expected in version['filesSHA256'].items():
                self.assertEqual(hashlib.sha256((ROOT/name).read_bytes()).hexdigest(),expected,name)
        self.assertFalse(registry['versions'][1]['automaticPaperSwitch'])
        self.assertFalse(registry['versions'][1]['realTradingEnabled'])

    def test_bundle_rights_digest_schema_and_synthetic_quarantine(self):
        with tempfile.TemporaryDirectory() as directory:
            root=pathlib.Path(directory)
            file=root/'UNIT-ONLY-records.json'
            data=fixture()['feeds'];records={name:[row] for name,row in data.items()}
            file.write_text(json.dumps(records))
            manifest=dict(schemaVersion=2,kind='ultimate-v2-recorded-evidence',file=file.name,
                          sha256=hashlib.sha256(file.read_bytes()).hexdigest(),origin='FABRICATED UNIT TEST ONLY',
                          retrievedUTC='2026-11-10T13:00:00Z',availabilityReceiptReference='UNIT RECEIPT',
                          rights=dict(status='UNVERIFIED'))
            path=root/'manifest.json';path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'QUARANTINED'):
                load_bundle(path)
            manifest['rights']=dict(status='VERIFIED_INTERNAL_RESEARCH',algorithmicResearchAuthorized=True,evidenceReference='UNIT ATTESTATION')
            path.write_text(json.dumps(manifest))
            loaded,report=load_bundle(path)
            self.assertEqual(len(loaded),7)
            self.assertFalse(report['networkEnabled'])
            file.write_text(file.read_text()+' ')
            with self.assertRaisesRegex(ValueError,'SHA256'):
                load_bundle(path)
            records['GC'][0]['mode']='synthetic'
            file.write_text(json.dumps(records));manifest['sha256']=hashlib.sha256(file.read_bytes()).hexdigest();path.write_text(json.dumps(manifest))
            with self.assertRaisesRegex(ValueError,'synthetic'):
                load_bundle(path)

    def test_future_bar_and_future_release_vintage_do_not_change_past(self):
        case=fixture();frames={k:case['frames'][v] for k,v in [('15min','M15'),('1h','H1'),('4h','H4')]}
        payload=dict(frames=frames,records={},spread=case['spread'],risk=case['risk'])
        replay=ROOT/'coordinator/ultimate_v2_replay.js'
        def run(value):
            result=subprocess.run(['node',str(replay)],input=json.dumps(value),text=True,capture_output=True,check=True)
            return json.loads(result.stdout)
        result=run(payload)
        self.assertFalse(result['isIndependentHoldout'])
        self.assertFalse(result['executable'])
        self.assertEqual(result['researchCandidates'],{'v1':0,'v2':0})
        self.assertEqual(result['jointCoveragePct'],0)
        self.assertEqual(result['dataCoverage']['US02Y']['role'],'DAILY_CONTEXT')
        future=fixture()['feeds']['US02Y']
        future.update(availableUTC='2026-11-10T13:00:00Z')
        payload['records']={'US02Y':[future]}
        self.assertEqual(run(payload),result)

        payload['frames']['15min']=payload['frames']['15min'][:-1]
        prefix_result=run(payload)
        payload['frames']['4h'][-1].update(high=600,close=500)
        self.assertEqual(run(payload),prefix_result)
