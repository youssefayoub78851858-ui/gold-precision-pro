import concurrent.futures
import json
import pathlib
import sqlite3
import tempfile
import unittest
from ultimate_paper import PaperAccount, timestamp, iso


def bar(time, o=100, h=101, l=99, c=100):
    return dict(datetime=time, open=o, high=h, low=l, close=c)


def signal(side='BUY', stop=95, target=110):
    return dict(signal='WAIT', executable=False, researchCandidate=side, risk={'ok': True}, tradePlan=dict(stop=stop, target=target))


class PaperLifecycle(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = pathlib.Path(self.temp.name) / 'account.sqlite3'
        self.account = PaperAccount(self.path)

    def tearDown(self):
        self.account.close()
        self.temp.cleanup()

    def decide(self, value, report=None):
        snapshot = {'asOfUTC': iso(timestamp(value['datetime']) + 900000)}
        return self.account.step(value, snapshot, evaluator=lambda _: report or signal())

    def test_next_bar_entry_target_costs_restart_and_duplicate(self):
        b = bar('2026-11-10T12:00:00Z')
        self.decide(b)
        self.assertFalse(self.account.summary()['position'])
        self.account.close()
        self.account = PaperAccount(self.path)
        self.account.step(bar('2026-11-10T12:15:00Z'))
        p = self.account.summary()['position'][0]
        self.assertAlmostEqual(p['entry'], 100.5)
        self.assertLessEqual(p['risk'], 50)
        exit_bar = bar('2026-11-10T12:30:00Z', h=111)
        self.account.step(exit_bar)
        trade = self.account.summary()['trades'][0]
        self.assertEqual(trade['reason'], 'TARGET')
        self.assertAlmostEqual(trade['exit'], 109.9)
        self.assertAlmostEqual(trade['net'], (109.9-100.5)*trade['lots']*100-7*trade['lots'])
        self.assertAlmostEqual(self.account.summary()['account']['balance'], 10000+trade['net'])
        self.assertTrue(self.account.step(exit_bar)['duplicate'])
        with self.assertRaises(ValueError):
            self.account.step({**exit_bar, 'close': 100.1})

    def test_sell_bid_ask_and_stop_first(self):
        self.decide(bar('2026-11-10T12:00:00Z'), signal('SELL', 105, 90))
        self.account.step(bar('2026-11-10T12:15:00Z', h=106, l=89))
        trade = self.account.summary()['trades'][0]
        self.assertAlmostEqual(trade['entry'], 99.9)
        self.assertAlmostEqual(trade['exit'], 105.1)
        self.assertEqual(trade['reason'], 'STOP_FIRST')
        self.assertLess(trade['net'], 0)

    def test_gap_stop_and_missing_entry_bar(self):
        self.decide(bar('2026-11-10T12:00:00Z'))
        self.account.step(bar('2026-11-10T12:15:00Z'))
        self.account.step(bar('2026-11-10T13:00:00Z', o=90, h=91, l=89, c=90))
        trade = self.account.summary()['trades'][0]
        self.assertEqual(trade['reason'], 'GAP_STOP')
        self.assertAlmostEqual(trade['exit'], 89.9)
        self.decide(bar('2026-11-10T13:15:00Z'))
        self.account.step(bar('2026-11-10T14:00:00Z'))
        self.assertFalse(self.account.summary()['pending'])
        self.assertFalse(self.account.summary()['position'])

    def test_conflicts_kill_and_rollback(self):
        self.decide(bar('2026-11-10T12:00:00Z'))
        self.decide(bar('2026-11-10T12:15:00Z'), signal('SELL',105,90))
        self.assertEqual(len(self.account.summary()['position']), 1)
        self.assertFalse(self.account.summary()['pending'])
        before = self.account.summary()
        with self.assertRaises(ValueError):
            self.decide(bar('2026-11-10T12:30:00Z', l=90), {'signal':'BUY', 'executable':True})
        self.assertEqual(before, self.account.summary())
        self.account.kill()
        self.account.step(bar('2026-11-10T12:30:00Z', l=90))
        self.decide(bar('2026-11-10T12:45:00Z'))
        self.account.step(bar('2026-11-10T13:00:00Z'))
        self.assertFalse(self.account.summary()['position'])

    def test_daily_ceiling_and_reset(self):
        self.decide(bar('2026-11-10T12:00:00Z'))
        self.account.step(bar('2026-11-10T12:15:00Z'))
        self.account.step(bar('2026-11-10T12:30:00Z', o=50,h=51,l=49,c=50))
        self.assertGreater(self.account.loss(timestamp('2026-11-10T13:00:00Z')), 200)
        self.decide(bar('2026-11-10T13:00:00Z'))
        self.account.step(bar('2026-11-10T13:15:00Z'))
        self.assertFalse(self.account.summary()['position'])
        self.assertEqual(self.account.loss(timestamp('2026-11-11T00:00:00Z')), 0)
        self.decide(bar('2026-11-10T23:45:00Z'))
        self.account.step(bar('2026-11-11T00:00:00Z'))
        self.assertEqual(len(self.account.summary()['position']),1)

    def test_concurrent_duplicate_and_immutable_config(self):
        self.decide(bar('2026-11-10T12:00:00Z'))
        def poll(_):
            a = PaperAccount(self.path)
            try:
                return a.step(bar('2026-11-10T12:15:00Z'))
            finally:
                a.close()
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(poll, range(2)))
        self.assertEqual(sum(bool(r.get('duplicate')) for r in results), 1)
        self.assertEqual(len(self.account.summary()['position']),1)
        with self.assertRaises(ValueError):
            PaperAccount(self.path, {'initialBalance': 20000})

    def test_real_ultimate_evaluator_uses_persisted_account_risk(self):
        observations = json.loads((pathlib.Path(__file__).parent / 'fixtures/ultimate-paper-synthetic.json').read_text())
        # Untrusted caller account values cannot replace the database balance or ceilings.
        observations[0]['snapshot']['risk'].update(equity=1e12, riskFraction=.99)
        for observation in observations:
            self.account.step(**observation)
        summary = self.account.summary()
        self.assertEqual(len(summary['trades']), 1)
        self.assertLessEqual(summary['trades'][0]['risk'], 50)
        self.assertIn('SYNTHETIC', summary['dataOrigin'])
        self.account.close()
        self.account = PaperAccount(self.path)
        for observation in observations:
            self.assertTrue(self.account.step(**observation)['duplicate'])
        self.assertEqual(summary, self.account.summary())

    def test_gap_target_is_known_before_intrabar_stop(self):
        self.decide(bar('2026-11-10T12:00:00Z'))
        self.account.step(bar('2026-11-10T12:15:00Z'))
        self.account.step(bar('2026-11-10T12:30:00Z', o=112, h=113, l=90, c=100))
        trade = self.account.summary()['trades'][0]
        self.assertEqual(trade['reason'], 'GAP_TARGET')
        self.assertAlmostEqual(trade['exit'],109.9)
