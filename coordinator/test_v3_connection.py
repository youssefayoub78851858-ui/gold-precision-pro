"""Offline transport/admission tests, not strategy-profitability evidence."""
import copy,datetime,json,os,pathlib,secrets,socket,subprocess,tempfile,threading,time,unittest,urllib.request,urllib.error
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs
ROOT=pathlib.Path(__file__).resolve().parent
NOW=1794301205000 # 2026-11-10T09:00:05Z, market open
TOKEN=secrets.token_urlsafe(40)
def port():
 with socket.socket() as s:s.bind(('127.0.0.1',0));return s.getsockname()[1]
def fixture():
 result={}
 for f,m in [('15min',15),('1h',60),('4h',240)]:
  end=NOW//(m*60000)*(m*60000);rows=[]
  for i in range(150):
   t=end-i*m*60000;p=4100+i*.1
   rows.append({'datetime':datetime.datetime.fromtimestamp(t/1000,datetime.timezone.utc).isoformat(),'open':p,'high':p+2,'low':p-2,'close':p+.1})
  result[f]={'symbol':'XAU/USD','meta':{'interval':f},'values':rows}
 return result
class Connection(unittest.TestCase):
 @classmethod
 def setUpClass(cls):
  cls.calls=0;cls.raw=fixture();cls.upstream=200
  class Handler(BaseHTTPRequestHandler):
   def log_message(self,*_):pass
   def do_GET(self):
    if self.headers.get('Authorization')!='Bearer '+TOKEN:self.send_response(401);self.end_headers();return
    cls.calls+=1;frame=parse_qs(urlparse(self.path).query)['interval'][0]
    self.send_response(cls.upstream);self.end_headers();self.wfile.write(json.dumps(cls.raw[frame]).encode())
  cls.broker=ThreadingHTTPServer(('127.0.0.1',0),Handler);cls.thread=threading.Thread(target=cls.broker.serve_forever,daemon=True);cls.thread.start()
  cls.tmp=tempfile.TemporaryDirectory();cls.preload=pathlib.Path(cls.tmp.name)/'clock.cjs';cls.preload.write_text('const D=Date,t=Number(process.env.TEST_NOW);global.Date=class extends D{constructor(...a){super(...(a.length?a:[t]))}static now(){return t}}')
 @classmethod
 def tearDownClass(cls):cls.broker.shutdown();cls.broker.server_close();cls.tmp.cleanup()
 def setUp(self):self.__class__.raw=fixture();self.__class__.upstream=200
 def request(self,path,now=NOW):
  ap=port();env={k:v for k,v in os.environ.items() if k not in ['TWELVE_DATA_API_KEY','NODE_OPTIONS']};env.update(PORT=str(ap),BROKER_TOKEN=TOKEN,MARKET_DATA_BROKER_URL=f'http://127.0.0.1:{self.broker.server_port}',NODE_OPTIONS='--require='+str(self.preload),TEST_NOW=str(now))
  p=subprocess.Popen(['node',str(ROOT.parent/'server.js')],env=env,stdout=subprocess.DEVNULL,stderr=subprocess.PIPE)
  try:
   for _ in range(100):
    try:urllib.request.urlopen(f'http://127.0.0.1:{ap}/health',timeout=.2).close();break
    except OSError:time.sleep(.03)
   try:
    with urllib.request.urlopen(f'http://127.0.0.1:{ap}'+path,timeout=5) as r:return r.status,json.load(r)
   except urllib.error.HTTPError as e:return e.code,json.load(e)
  finally:p.terminate();p.communicate(timeout=5)
 def test_public_route_reaches_v3_with_closed_native_frames(self):
  code,x=self.request('/api/v3/research');self.assertEqual(code,200);self.assertEqual(x['engine'],'V3');self.assertEqual(x['dataStatus'],'FRESH');self.assertEqual(x['signal'],'WAIT');self.assertFalse(x['executable']);self.assertEqual(x['candles']['15min']['ageAfterCloseSeconds'],5)
 def test_late_window_wait(self):
  _,x=self.request('/api/v3/research',NOW+90000);self.assertEqual(x['dataStatus'],'STALE');self.assertEqual(x['reason'],'MISSED_OBSERVATION_WINDOW')
 def test_missing_latest_h4_wait(self):
  self.raw['4h']['values'].pop(1);_,x=self.request('/api/v3/research');self.assertEqual(x['dataStatus'],'STALE');self.assertEqual(x['blockedFrame'],'4h')
 def test_forming_candles_not_used(self):
  _,a=self.request('/api/v3/research')
  for pack in self.raw.values():pack['values'][0].update(open=1,high=2,low=.5,close=1)
  _,b=self.request('/api/v3/research');self.assertEqual(a,b)
 def test_bad_ohlc_unavailable(self):
  self.raw['1h']['values'][1]['high']=1;code,x=self.request('/api/v3/research');self.assertEqual(code,503);self.assertEqual(x['dataStatus'],'UNAVAILABLE');self.assertEqual(x['signal'],'WAIT')
 def test_duplicate_timestamps_unavailable(self):
  self.raw['15min']['values'][1]=copy.deepcopy(self.raw['15min']['values'][0]);code,x=self.request('/api/v3/research');self.assertEqual(code,503);self.assertFalse(x['executable'])
 def test_older_h4_off_grid_not_labelled_fresh(self):
  c=self.raw['4h']['values'][3];t=datetime.datetime.fromisoformat(c['datetime']);c['datetime']=(t+datetime.timedelta(hours=1)).isoformat()
  code,x=self.request('/api/v3/research');self.assertEqual(code,200);self.assertEqual(x['dataStatus'],'INVALID');self.assertEqual(x['signal'],'WAIT')
 def test_wrong_interval_unavailable(self):
  self.raw['4h']['meta']['interval']='1h';code,x=self.request('/api/v3/research');self.assertEqual(code,503)
 def test_broker_failure_wait(self):
  self.__class__.upstream=503;code,x=self.request('/api/v3/research');self.assertEqual(code,503);self.assertEqual(x['signal'],'WAIT');self.assertIn('reason',x)
 def test_closed_market_does_not_fetch(self):
  before=self.calls;_,x=self.request('/api/v3/research',1794657605000);self.assertEqual(x['dataStatus'],'MARKET_CLOSED');self.assertEqual(self.calls,before)
 def test_docker_copies_v3_dependency_closure(self):
  import shlex
  included=set()
  for line in (ROOT/'Dockerfile').read_text().splitlines():
   if line.startswith('COPY '):included.update(shlex.split(line)[1:-1])
  for name in ['v3_trade_plan.js','v3_multitimeframe.js','v3_market_structure.js']:self.assertIn(name,included);self.assertTrue((ROOT/name).is_file())
if __name__=='__main__':unittest.main()
