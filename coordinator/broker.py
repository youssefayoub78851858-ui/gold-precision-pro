"""Development shared XAU/USD gateway. Every API-key consumer must use this ledger.
No provider credentials are required for the mocked tests. Never logs credentials.
"""
import datetime,json,pathlib,sqlite3,threading,time,uuid,urllib.request,urllib.error,os,hmac
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse,parse_qs,urlencode
from zoneinfo import ZoneInfo
DUR={'15min':900000,'1h':3600000,'4h':14400000}
class Blocked(Exception):
 def __init__(self,reason,retry_ms):self.reason=reason;self.retry_ms=retry_ms;super().__init__(reason)
def stamp(c):
 value=datetime.datetime.fromisoformat(c['datetime'].replace(' ','T').replace('Z','+00:00'))
 if value.tzinfo is not None and value.utcoffset()!=datetime.timedelta(0):raise ValueError('UTC candle timestamps required')
 return int(value.replace(tzinfo=datetime.timezone.utc).timestamp()*1000)
def market_open(ms):
 n=datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).astimezone(ZoneInfo('America/New_York'))
 return n.weekday()!=5 and not(n.weekday()==6 and n.hour<18) and not(n.weekday()==4 and n.hour>=17) and n.hour!=17
class Broker:
 def __init__(self,path,provider,clock=lambda:int(time.time()*1000),initial_daily_usage=0):
  if not isinstance(initial_daily_usage,int) or not 0<=initial_daily_usage<=800:raise ValueError('Initial quota usage must be a verified number between 0 and 800')
  self.path=str(path);self.provider=provider;self.clock=clock;self.lock=threading.RLock();self.session_open=market_open
  with self.db() as d:
   d.executescript('''CREATE TABLE IF NOT EXISTS calls(id TEXT PRIMARY KEY,ms INTEGER,day INTEGER,weight INTEGER,kind TEXT);
   CREATE INDEX IF NOT EXISTS call_time ON calls(ms);
   CREATE TABLE IF NOT EXISTS cache(key TEXT PRIMARY KEY,json TEXT,expires INTEGER);
   CREATE TABLE IF NOT EXISTS leases(key TEXT PRIMARY KEY,until_ms INTEGER,token TEXT);
   CREATE TABLE IF NOT EXISTS cooldown(key TEXT PRIMARY KEY,until_ms INTEGER);
   CREATE TABLE IF NOT EXISTS meta(key TEXT PRIMARY KEY,value INTEGER);''')
   if not d.execute("SELECT 1 FROM meta WHERE key='initialized'").fetchone():
    now=self.clock();d.execute("INSERT INTO meta VALUES('initialized',?)",(now,))
    if initial_daily_usage:d.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('initial-usage',now//86400000*86400000,now//86400000,initial_daily_usage,'seed'))
 def db(self):
  d=sqlite3.connect(self.path,timeout=15);d.execute('PRAGMA journal_mode=WAL');d.execute('PRAGMA synchronous=FULL');return d
 def get(self,frame,outputsize=2000,end=None,kind='live'):
  if frame not in DUR or outputsize not in [500,2000] or end not in [None,'2026-08-31','2026-09-30']:raise ValueError('Unsupported request')
  if kind not in ['live','history']:raise ValueError('Unsupported consumer class')
  # Both live/analyze and candle/history endpoints share the same native 2000-bar fetch.
  key=frame+':'+(end or 'latest');now=self.clock();token=uuid.uuid4().hex
  with self.lock:
   with self.db() as d:
    d.execute('BEGIN IMMEDIATE')
    now=self.clock()
    last=d.execute('SELECT MAX(ms) FROM calls').fetchone()[0]
    if last is not None and now<last:raise Blocked('CLOCK_ROLLBACK',last)
    cache=d.execute('SELECT json,expires FROM cache WHERE key=?',(key,)).fetchone()
    if not end and not self.session_open(now) and not self.session_open(now-90000):
     if cache:return {**self.slice(json.loads(cache[0]),outputsize,True),'marketClosed':True}
     raise Blocked('MARKET_CLOSED_NO_FETCH',now+900000)
    if cache and cache[1]>now:return self.slice(json.loads(cache[0]),outputsize,True)
    cool=d.execute('SELECT until_ms FROM cooldown WHERE key IN (?,?) ORDER BY until_ms DESC LIMIT 1',(key,'*')).fetchone()
    if cool and cool[0]>now:raise Blocked('UPSTREAM_COOLDOWN',cool[0])
    lease=d.execute('SELECT until_ms FROM leases WHERE key=?',(key,)).fetchone()
    if lease and lease[0]>now:raise Blocked('FETCH_IN_FLIGHT',lease[0])
    used_min=d.execute("SELECT COALESCE(SUM(weight),0) FROM calls WHERE ms>? AND kind!='seed'",(now-60000,)).fetchone()[0]
    if used_min>=7:
     first=d.execute("SELECT MIN(ms) FROM calls WHERE ms>? AND kind!='seed'",(now-60000,)).fetchone()[0];raise Blocked('MINUTE_SAFETY_LIMIT',first+60001)
    used_day=d.execute('SELECT COALESCE(SUM(weight),0) FROM calls WHERE day=?',(now//86400000,)).fetchone()[0]
    if used_day>=720:raise Blocked('DAILY_SAFETY_LIMIT',(now//86400000+1)*86400000)
    # Reserve live capacity: at most 200 non-live/history calls per UTC day.
    if kind=='history' and d.execute("SELECT COALESCE(SUM(weight),0) FROM calls WHERE day=? AND kind='history'",(now//86400000,)).fetchone()[0]>=200:raise Blocked('HISTORY_BUDGET_LIMIT',(now//86400000+1)*86400000)
    d.execute('INSERT OR REPLACE INTO leases VALUES(?,?,?)',(key,now+15000,token))
    d.execute('INSERT INTO calls VALUES(?,?,?,?,?)',(token,now,now//86400000,1,kind))
    # Commit before network I/O. A crash never refunds a possibly spent credit.
   try:
    value=self.provider(frame,2000,end)
    self.validate(value,frame,self.clock())
    observed=self.clock();expires=observed+86400000*365 if end else (observed//DUR[frame]+1)*DUR[frame]
    if not end:
     closed=[stamp(c)+DUR[frame] for c in value['values'] if stamp(c)+DUR[frame]<=observed]
     if not closed or max(closed)!=(observed//DUR[frame])*DUR[frame]:raise Blocked('CANDLE_NOT_CLOSED_OR_PUBLISHED',observed+20000)
    with self.db() as d:
     lease=d.execute('SELECT token FROM leases WHERE key=?',(key,)).fetchone()
     if not lease or lease[0]!=token:raise Blocked('LEASE_LOST',observed+1000)
     d.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(key,json.dumps(value,separators=(',',':')),expires));d.execute('DELETE FROM leases WHERE key=?',(key,))
    return self.slice(value,outputsize,False)
   except BaseException as exc:
    until=exc.retry_ms if isinstance(exc,Blocked) else self.clock()+20000
    with self.db() as d:
     d.execute('INSERT OR REPLACE INTO cooldown VALUES(?,?)',('*' if isinstance(exc,Blocked) and exc.reason=='PROVIDER_429' else key,until));d.execute('DELETE FROM leases WHERE key=? AND token=?',(key,token))
    raise
 @staticmethod
 def slice(value,size,hit):
  # Provider values are newest first; keep precisely the caller's requested history depth.
  return {**value,'values':value['values'][:size],'broker':{'cacheHit':hit,'nativeFrames':True}}
 @staticmethod
 def validate(value,frame,now):
  import math
  if value.get('status')=='error' or not isinstance(value.get('values'),list) or not value['values']:raise ValueError('Provider returned no data')
  if value.get('meta',{}).get('interval',frame)!=frame:raise ValueError('Wrong frame')
  times=[]
  for c in value['values']:
   t=stamp(c);v=[float(c[k]) for k in ['open','high','low','close']]
   if t>now or not all(math.isfinite(x) and x>0 for x in v) or not v[2]<=min(v[0],v[3])<=max(v[0],v[3])<=v[1]:raise ValueError('Invalid OHLC/time')
   times.append(t)
  if len(set(times))!=len(times) or times!=sorted(times,reverse=True):raise ValueError('Duplicate or unordered candles')
def live_provider(frame,size,end):
 key=os.environ.get('TWELVE_DATA_API_KEY')
 if not key:raise RuntimeError('Provider key is not configured')
 query={'symbol':'XAU/USD','interval':frame,'outputsize':size,'timezone':'UTC','apikey':key}
 if end:query['end_date']=end
 try:
  with urllib.request.urlopen('https://api.twelvedata.com/time_series?'+urlencode(query),timeout=7) as response:return json.loads(response.read(5000000))
 except urllib.error.HTTPError as e:
  if e.code==429:
   retry=e.headers.get('Retry-After','60');seconds=int(retry) if retry.isdigit() else 60
   raise Blocked('PROVIDER_429',int(time.time()*1000)+max(60,seconds)*1000) from None
  raise RuntimeError('Provider request failed') from None
def serve(broker,port=3110,host='127.0.0.1',token=None):
 if not token or len(token)<32:raise ValueError('A strong internal bearer token is required')
 class Handler(BaseHTTPRequestHandler):
  def log_message(self,*_):pass
  def do_GET(self):
   supplied=self.headers.get('Authorization','')
   if not hmac.compare_digest(supplied.encode('utf-8'),('Bearer '+token).encode('utf-8')):
    self.send_response(401);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"error":"Unauthorized"}');return
   p=urlparse(self.path);q=parse_qs(p.query)
   try:
    if p.path=='/health':
     body=b'{"status":"online","paperOnly":true}';self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(body);return
    if p.path!='/time_series':raise ValueError('Unsupported path')
    result=broker.get(q.get('interval',['15min'])[0],int(q.get('outputsize',['2000'])[0]),q.get('end_date',[None])[0],'history' if q.get('end_date') else 'live')
    body=json.dumps(result).encode();self.send_response(200)
   except Blocked as e:
    body=json.dumps({'status':'error','message':e.reason,'retryAtMS':e.retry_ms}).encode();self.send_response(429 if 'LIMIT' in e.reason else 503);self.send_header('Retry-After',str(max(1,(e.retry_ms-broker.clock()+999)//1000)))
   except Exception:
    body=b'{"status":"error","message":"Data unavailable"}';self.send_response(503)
   self.send_header('Content-Type','application/json');self.end_headers()
   try:self.wfile.write(body)
   except BrokenPipeError:pass # caller timed out; the committed quota reservation stays spent
 return ThreadingHTTPServer((host,port),Handler)
if __name__=='__main__':
 if os.environ.get('ALL_KEY_CONSUMERS_ROUTED')!='1' or 'INITIAL_DAILY_USAGE' not in os.environ:raise SystemExit('Refusing provider access: all consumers must first be routed through the shared ledger')
 path=pathlib.Path(os.environ.get('QUOTA_DB','/tmp/gold-shared-quota.sqlite3'))
 broker=Broker(path,live_provider,initial_daily_usage=int(os.environ['INITIAL_DAILY_USAGE']))
 # After ALL old consumers have stopped/rerouted, drain unknown calls from the last minute.
 with broker.db() as d:d.execute('INSERT OR REPLACE INTO cooldown VALUES(?,?)',('*',broker.clock()+60000))
 serve(broker,int(os.environ.get('BROKER_PORT','3110')),os.environ.get('BROKER_BIND','127.0.0.1'),os.environ.get('BROKER_TOKEN')).serve_forever()
