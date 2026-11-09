"""One paid-in-credits usage query. Never prints a key or a provider request URL."""
import argparse,datetime,json,os,pathlib,sqlite3,time,urllib.request,urllib.error,urllib.parse,uuid
UTC=datetime.timezone.utc
class UsageBlocked(RuntimeError):pass
def reserve(path,now):
 # Same account ledger and same pre-I/O conservative accounting as the existing broker.
 with sqlite3.connect('file:'+str(pathlib.Path(path).resolve())+'?mode=rw',uri=True,timeout=10) as db:
  db.execute('BEGIN IMMEDIATE')
  last=db.execute('SELECT MAX(ms) FROM calls').fetchone()[0]
  if last is not None and now<last:raise UsageBlocked('Clock rollback')
  minute=db.execute("SELECT COALESCE(SUM(weight),0) FROM calls WHERE ms>? AND kind!='seed'",(now-60000,)).fetchone()[0]
  daily=db.execute('SELECT COALESCE(SUM(weight),0) FROM calls WHERE day=?',(now//86400000,)).fetchone()[0]
  cooldown=db.execute('SELECT MAX(until_ms) FROM cooldown').fetchone()[0]
  if minute>=7 or daily>=720 or cooldown and cooldown>now:raise UsageBlocked('Usage probe blocked by shared quota/cooldown')
  db.execute('INSERT INTO calls VALUES(?,?,?,?,?)',('usage-'+uuid.uuid4().hex,now,now//86400000,1,'usage'))
def probe(ledger=None):
 key=os.environ.get('TWELVE_DATA_API_KEY')
 if not key:raise UsageBlocked('Provider secret missing')
 if ledger:reserve(ledger,int(time.time()*1000))
 url='https://api.twelvedata.com/api_usage?'+urllib.parse.urlencode({'apikey':key,'timezone':'UTC'})
 try:
  with urllib.request.urlopen(url,timeout=7) as response:raw=json.loads(response.read(100000))
 except urllib.error.HTTPError as error:
  if ledger and error.code==429:
   retry=error.headers.get('Retry-After','60');delay=max(60,int(retry) if retry.isdigit() else 60)
   with sqlite3.connect(ledger) as db:db.execute('INSERT OR REPLACE INTO cooldown VALUES(?,?)',('*',int(time.time()*1000)+delay*1000))
  raise UsageBlocked('Usage query failed; no key or URL logged, no credit refunded') from None
 except Exception:raise UsageBlocked('Usage query failed; no key or URL logged, no credit refunded') from None
 for f in ['current_usage','plan_limit','daily_usage','plan_daily_limit']:
  if type(raw.get(f))!=int or raw[f]<0:raise UsageBlocked('Unrecognized usage schema; stop for review')
 if raw['plan_limit']!=8 or raw['plan_daily_limit']!=800:raise UsageBlocked('Account limits differ from approved Basic assumptions')
 now=datetime.datetime.now(UTC)
 try:
  stamp=datetime.datetime.fromisoformat(raw['timestamp'].replace('Z','+00:00'))
  if stamp.tzinfo is None:stamp=stamp.replace(tzinfo=UTC)
 except Exception:raise UsageBlocked('Invalid provider usage timestamp') from None
 if not 0<=(now-stamp).total_seconds()<=60 or stamp.date()!=now.date():raise UsageBlocked('Usage observation stale/future/wrong UTC day')
 result={k:raw[k] for k in ['current_usage','plan_limit','daily_usage','plan_daily_limit']};result['observedUTC']=now.isoformat();result['serverTimestampUTC']=stamp.isoformat();result['queryCreditCost']=1
 if ledger:
  with sqlite3.connect(ledger) as db:total=db.execute('SELECT COALESCE(SUM(weight),0) FROM calls WHERE day=?',(int(time.time()*1000)//86400000,)).fetchone()[0]
  result['ledgerDailyReserved']=total;result['unexpectedAccountUsage']=raw['daily_usage']>total
  if result['unexpectedAccountUsage']:
   (pathlib.Path(ledger).parent/'PAUSE_LIVE').touch()
 return result
if __name__=='__main__':
 p=argparse.ArgumentParser();p.add_argument('--ledger',required=True);a=p.parse_args()
 if os.environ.get('USAGE_CHECK_APPROVED')!='1':raise SystemExit('Usage check not approved')
 try:print(json.dumps(probe(a.ledger),indent=2))
 except UsageBlocked as e:raise SystemExit(str(e))
