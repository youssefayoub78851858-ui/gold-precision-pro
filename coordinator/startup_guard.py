"""Fail-closed handoff and durable restart admission. Never changes routing or approval flags."""
import datetime,hashlib,json,os,pathlib,sqlite3
from handoff_guard import check
UTC=datetime.timezone.utc
class NotReady(RuntimeError):pass
def route_digest(m):
 # Operator-attested routing is checked on every startup. This is not a remote audit.
 keys=['accountInventoryComplete','allAccountConsumersRouted','consumers','publishedServiceMustRemainUnchanged']
 return hashlib.sha256(json.dumps({k:m.get(k) for k in keys},sort_keys=True).encode()).hexdigest()
def authorize(m,data,key_present,now):
 data=pathlib.Path(data);receipt=data/'handoff-receipt.json';dbpath=data/'quota.sqlite3'
 if receipt.exists():
  record=json.loads(receipt.read_text())
  if record['routeDigest']!=route_digest(m):raise NotReady('ROUTING_CHANGED_REQUIRES_NEW_VERIFIED_HANDOFF')
  if not key_present:raise NotReady('PROVIDER_KEY_NOT_AVAILABLE_HERE')
  if not m.get('accountInventoryComplete') or not m.get('allAccountConsumersRouted'):raise NotReady('SHARED_HANDOFF_UNCONFIRMED')
  if not dbpath.exists():raise NotReady('QUOTA_LEDGER_MISSING_DO_NOT_RESEED')
  with sqlite3.connect('file:'+str(dbpath.resolve())+'?mode=ro',uri=True) as db:
   if db.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise NotReady('QUOTA_LEDGER_CORRUPT')
   initialized=db.execute("SELECT value FROM meta WHERE key='initialized'").fetchone()
   if not initialized or record['initializedMS']!=initialized[0]:raise NotReady('QUOTA_LEDGER_IDENTITY_CHANGED')
   last=db.execute('SELECT MAX(ms) FROM calls').fetchone()[0]
   if last is not None and last>int(now.timestamp()*1000):raise NotReady('QUOTA_CLOCK_ROLLBACK')
  return {'mode':'RESUME_EXISTING_LEDGER','initialDailyUsage':record['initialDailyUsage'],'routeDigest':record['routeDigest']}
 result=check(m,key_present,now)
 if result['blockingReasons']:raise NotReady(','.join(result['blockingReasons']))
 if dbpath.exists():raise NotReady('UNATTESTED_EXISTING_LEDGER_REQUIRES_MANUAL_RECONCILIATION')
 return {'mode':'FIRST_HANDOFF','initialDailyUsage':m['providerUsage']['dailyUsed']+m['providerUsage']['postMeasurementCallsReserved'],'routeDigest':route_digest(m)}
def seal_after_initialize(auth,data):
 if auth['mode']!='FIRST_HANDOFF':return
 data=pathlib.Path(data);p=data/'handoff-receipt.json'
 with sqlite3.connect(data/'quota.sqlite3') as db:
  initialized=db.execute("SELECT value FROM meta WHERE key='initialized'").fetchone()[0]
 record={**auth,'initializedMS':initialized,'note':'Operator routing attestation plus persistent ledger; does not detect external consumers or backup rollback'}
 temp=data/'handoff-receipt.tmp';fd=os.open(temp,os.O_WRONLY|os.O_CREAT|os.O_TRUNC,0o600)
 with os.fdopen(fd,'w') as out:json.dump(record,out);out.flush();os.fsync(out.fileno())
 os.replace(temp,p)
