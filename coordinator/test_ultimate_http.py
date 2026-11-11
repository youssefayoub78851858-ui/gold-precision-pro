"""Offline-only HTTP acceptance, including request boundaries and review UI."""
import json
import os
import socket
import subprocess
import time
import unittest
import urllib.error
import urllib.request
from pathlib import Path

class UltimateHTTP(unittest.TestCase):
    def test_offline_contract(self):
        with socket.socket() as sock:
            sock.bind(('127.0.0.1', 0))
            port = sock.getsockname()[1]
        env = {**os.environ, 'PORT': str(port), 'DEMO_MODE': 'standby', 'H15_OFFICIAL_RSS_DISABLED': '1', 'OFFICIAL_MACRO_DISABLED': '1', 'GOLD_SPOT_REFERENCE_DISABLED': '1'}
        proc = subprocess.Popen(['node', str(Path(__file__).resolve().parent.parent / 'server.js')], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        base = f'http://127.0.0.1:{port}'
        def request(path, payload=None):
            req = urllib.request.Request(base + path, data=payload, headers={'Content-Type': 'application/json'})
            try:
                with urllib.request.urlopen(req, timeout=5) as response:
                    return response.status, response.read()
            except urllib.error.HTTPError as error:
                return error.code, error.read()
        try:
            for _ in range(100):
                try:
                    request('/health')
                    break
                except OSError:
                    time.sleep(.03)
            self.assertIn(b'Gold Precision Pro Ultimate', request('/ultimate')[1])
            self.assertIn(b'recorded-review-load', request('/ultimate')[1])
            self.assertIn(b'free-context-load', request('/ultimate')[1])
            self.assertIn(b'spot-refresh', request('/ultimate')[1])
            self.assertIn(b'candle-source-check', request('/ultimate')[1])
            cr, raw = request('/api/v3/ultimate/candle-source-readiness')
            self.assertEqual(cr, 200)
            readiness = json.loads(raw)
            self.assertEqual(readiness['mode'], 'CANDLE_SOURCE_FEASIBILITY_ONLY')
            self.assertEqual(readiness['signal'], 'WAIT')
            self.assertFalse(readiness['executable'])
            self.assertFalse(readiness['automaticPollingEnabled'])
            self.assertFalse(readiness['latestConnected'])
            self.assertFalse(readiness['publicOhlcDistributionEnabled'])
            self.assertEqual(readiness['derivedSampleCounts'], {'M15':96,'H1':24,'H4':6})
            self.assertEqual(request('/api/v3/ultimate/candle-source-readiness', b'{}')[0], 405)
            sc, sr = request('/api/v3/ultimate/gold-spot-reference')
            self.assertEqual(sc, 200)
            spot = json.loads(sr)
            self.assertEqual(spot['mode'], 'FREE_XAU_SPOT_REFERENCE')
            self.assertEqual(spot['dataStatus'], 'DISABLED_OFFLINE')
            self.assertIsNone(spot['price'])
            self.assertFalse(spot['executable'])
            self.assertFalse(spot['realOHLC'])
            self.assertFalse(spot['readyForUltimateTrading'])
            self.assertTrue(all(f['closedCandles'] == 0 for f in spot['frames'].values()))
            self.assertEqual(request('/api/v3/ultimate/gold-spot-reference', b'{}')[0], 405)
            self.assertIn(b'macro-refresh', request('/ultimate')[1])
            mc, mr = request('/api/v3/ultimate/official-macro')
            self.assertEqual(mc, 200)
            m = json.loads(mr)
            self.assertEqual(m['mode'], 'OFFICIAL_MACRO_REVIEW')
            self.assertEqual(m['signal'], 'WAIT')
            self.assertFalse(m['executable'])
            self.assertFalse(m['liveData'])
            self.assertEqual(m['calendar'], [])
            self.assertEqual(m['headlines'], [])
            self.assertEqual(request('/api/v3/ultimate/official-macro', b'{}')[0], 405)
            daily_code, daily_raw = request('/api/v3/ultimate/free-context')
            self.assertEqual(daily_code, 200)
            daily = json.loads(daily_raw)
            self.assertEqual(daily['mode'], 'OFFICIAL_RECORDED_DAILY_CONTEXT')
            self.assertEqual(daily['signal'], 'WAIT')
            self.assertFalse(daily['executable'])
            self.assertFalse(daily['readyForFiveMinuteGate'])
            self.assertFalse(daily['readyForUltimateTrading'])
            self.assertFalse(daily['liveData'])
            self.assertFalse(daily['firstAvailabilityVerified'])
            self.assertEqual(daily['providerRequests'], 0)
            self.assertEqual(daily['observedDate'], '2026-11-09')
            self.assertEqual({x['series']:x['latestYieldPct'] for x in daily['rates']}, {'DGS2':4.56, 'DGS10':4.88})
            self.assertEqual(request('/api/v3/ultimate/free-context', b'{}')[0], 405)
            code, payload = request('/api/v3/ultimate/recorded-review')
            self.assertEqual(code, 200)
            report = json.loads(payload)
            self.assertEqual(report['mode'], 'STORED_RECORDED_RESEARCH')
            self.assertEqual(report['signal'], 'WAIT')
            self.assertFalse(report['executable'])
            self.assertFalse(report['liveData'])
            self.assertEqual(report['providerRequests'], 0)
            self.assertEqual(report['countM15'], 4884)
            self.assertEqual(report['priceReady'], 4573)
            self.assertEqual(report['allLayersTogetherPct'], 0)
            self.assertEqual(len(report['missingLayers']), 7)
            self.assertEqual(len(report['researchCases']), 4)
            self.assertEqual(len(report['v2Windows']), 3)
            self.assertEqual(request('/api/v3/ultimate/recorded-review', b'{}')[0], 405)
            self.assertEqual(request('/api/v3/ultimate')[0], 405)
            self.assertEqual(request('/api/v3/ultimate', b'bad')[0], 400)
            status, raw = request('/api/v3/ultimate', json.dumps({'asOfUTC':'2026-11-10T12:00:00Z'}).encode())
            self.assertEqual(status, 200)
            data = json.loads(raw)
            self.assertEqual(data['signal'], 'WAIT')
            self.assertFalse(data['executable'])
            self.assertEqual(data['monitoring']['readyFeeds'], 0)
            self.assertIn(b'ultimate-r2-review', request('/ultimate')[1])
            self.assertIn(b'/api/v3/ultimate/r2', request('/ultimate')[1])
            self.assertEqual(request('/api/v3/ultimate/r2')[0], 405)
            self.assertEqual(request('/api/v3/ultimate/r2', b'bad')[0], 400)
            r2_fixture=Path(__file__).resolve().parent/'fixtures'/'ultimate-synthetic.json'
            status,raw=request('/api/v3/ultimate/r2',r2_fixture.read_bytes())
            self.assertEqual(status,200)
            r2=json.loads(raw)
            self.assertEqual(r2['version'],2)
            self.assertEqual(r2['contractVersion'],'ultimate-context-events-v2')
            self.assertEqual(r2['signal'],'WAIT')
            self.assertFalse(r2['executable'])
            self.assertFalse(r2['networkEnabled'])
            self.assertEqual(r2['legacyComparison']['version'],1)
            self.assertEqual(request('/api/v3/ultimate', b' ' * (1048576 + 1))[0], 413)
            self.assertEqual(request('/api/v3/ultimate/r2', b' ' * (1048576 + 1))[0], 413)
        finally:
            proc.terminate()
            proc.communicate(timeout=5)
