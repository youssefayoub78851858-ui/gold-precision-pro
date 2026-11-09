"""Offline integration: the V2 API must fail closed if its broker is unavailable.
No market-data keys, network providers, or trading orders are used.
"""
import contextlib,json,os,subprocess,time,unittest,urllib.error,urllib.request
from pathlib import Path

ROOT=Path(__file__).resolve().parent
PORT=3139
class V2ApiIntegration(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  env={**os.environ,'PORT':str(PORT),'MARKET_DATA_BROKER_URL':'http://127.0.0.1:9','BROKER_TOKEN':'offline-test-token-0123456789-strong'}
  env.pop('TWELVE_DATA_API_KEY',None)
  cls.process=subprocess.Popen(['node',str(ROOT/'service/server.js')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  for _ in range(50):
   if cls.process.poll() is not None:raise RuntimeError('V2 API exited during startup')
   try:
    urllib.request.urlopen(f'http://127.0.0.1:{PORT}/health',timeout=.2).close()
    return
   except (OSError,urllib.error.URLError):time.sleep(.1)
  cls.process.terminate()
  raise RuntimeError('V2 API readiness timeout')
 @classmethod
 def tearDownClass(cls):
  cls.process.terminate()
  try:cls.process.wait(timeout=3)
  except subprocess.TimeoutExpired:cls.process.kill()
 def request(self,path):
  try:
   with urllib.request.urlopen(f'http://127.0.0.1:{PORT}'+path,timeout=15) as r:
    return r.status,json.load(r)
  except urllib.error.HTTPError as e:
   return e.code,json.load(e)
 def test_health_is_paper_only(self):
  code,body=self.request('/health')
  self.assertEqual(code,200)
  self.assertEqual(body['trading'],'disabled')
  self.assertEqual(body['signalEngine'],'Gold Precision Pro V2')
 def test_invalid_interval_is_rejected(self):
  code,_=self.request('/api/candles?interval=invalid')
  self.assertEqual(code,400)
 def test_unavailable_broker_does_not_create_signal(self):
  code,body=self.request('/api/analyze')
  self.assertEqual(code,502)
  self.assertNotIn('signal',body)
 def test_unavailable_broker_cannot_supply_candles(self):
  code,body=self.request('/api/candles?interval=15min')
  self.assertEqual(code,502)
  self.assertNotIn('values',body)
if __name__=='__main__':unittest.main()
