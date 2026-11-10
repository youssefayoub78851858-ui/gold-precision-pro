import copy
import json
import pathlib
import tempfile
import unittest
from ultimate_paper import DEFAULTS, timestamp
from ultimate_walkforward import generate, verify_dataset, simulate, metrics


class RecordedResearch(unittest.TestCase):
    def test_recorded_digest_and_ohlc(self):
        root = pathlib.Path(__file__).parent.parent / 'research/recorded'
        for path in root.glob('*-bid.json'):
            doc, provenance = verify_dataset(path)
            self.assertGreater(len(doc['frames']['15min']),2000)
            self.assertEqual(provenance['priceConvention'],'BID')
        with tempfile.TemporaryDirectory() as temp:
            original = root / '2026-09-bid.json'
            path = pathlib.Path(temp) / original.name
            path.write_text(original.read_text()+' ')
            path.with_name('manifest.json').write_text((root/'manifest.json').read_text())
            with self.assertRaises(ValueError):
                verify_dataset(path)

    def test_future_bar_mutation_cannot_change_prefix(self):
        fixture=json.loads((pathlib.Path(__file__).parent/'fixtures/ultimate-synthetic.json').read_text())
        frames={k:fixture['frames'][v] for k,v in [('15min','M15'),('1h','H1'),('4h','H4')]}
        document={'frames':frames}
        before=generate(document,DEFAULTS)
        changed=copy.deepcopy(document)
        changed['frames']['15min'][-1].update(open=100, high=110,low=90,close=109)
        after=generate(changed,DEFAULTS)
        self.assertEqual(before[:-1],after[:-1])
        # Both engines must disclose zero sample expectancy instead of inventing success.
        for engine in ('v2','ultimate'):
            result=simulate(frames['15min'],before,engine,DEFAULTS,timestamp(frames['15min'][0]['datetime']),timestamp(before[-1]['asOfUTC']))
            self.assertEqual(result['trades'],0)
            self.assertIsNone(result['expectancy'])
            self.assertEqual(result['inference'],'INSUFFICIENT')
