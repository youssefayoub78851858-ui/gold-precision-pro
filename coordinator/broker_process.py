import json,os,pathlib,time,signal,threading,fcntl
from broker import Broker,serve,live_provider
root=pathlib.Path(os.environ['DATA_DIR']);root.mkdir(parents=True,exist_ok=True)
# Hold for the process lifetime, before touching quota state or binding a socket.
coordinator_lock=(root/'coordinator.lock').open('a')
try:fcntl.flock(coordinator_lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
except BlockingIOError:raise SystemExit('Coordinator already running for this DATA_DIR')
recorded=os.environ.get('REPLAY_SNAPSHOT')
if recorded:
 raw=json.loads(pathlib.Path(recorded).read_text())
 def provider(*_):raise RuntimeError('Replay provider refuses external fetch')
 b=Broker(root/'quota.sqlite3',provider)
 b.session_open=lambda _:False # Replay serves only recorded snapshots; never invokes a provider.
 # Retain original times/prices. Closed-market data yields WAIT, never a fake live fill.
 with b.db() as db:
  for f,payload in raw.items():
   if f not in ['15min','1h','4h']:continue
   db.execute('INSERT OR REPLACE INTO cache VALUES(?,?,?)',(f+':latest',json.dumps(payload),0))
else:
 if os.environ.get('LIVE_DATA_APPROVED')!='1' or os.environ.get('ALL_KEY_CONSUMERS_ROUTED')!='1':raise SystemExit('Live data disabled until shared-quota handoff is approved')
 if not os.environ.get('TWELVE_DATA_API_KEY'):raise SystemExit('No provider secret configured')
 from process_inventory import refuse_competing
 refuse_competing()
 from startup_guard import authorize,seal_after_initialize
 import datetime
 manifest=json.loads(os.environ['HANDOFF_MANIFEST_JSON']) if os.environ.get('HANDOFF_MANIFEST_JSON') else json.loads(pathlib.Path(os.environ.get('HANDOFF_MANIFEST',pathlib.Path(__file__).parent/'handoff-manifest.json')).read_text())
 if not (root/'handoff-receipt.json').exists() and os.environ.get('FIRST_HANDOFF_USAGE_PROBE_APPROVED')=='1':
  from handoff_guard import check
  static=check(manifest,True,datetime.datetime.now(datetime.timezone.utc))
  usage_reasons={'CURRENT_PROVIDER_USAGE_NOT_VERIFIED','POST_USAGE_MEASUREMENT_REQUESTS_NOT_RESERVED','USAGE_OBSERVATION_TIME_MISSING','USAGE_SNAPSHOT_STALE_FUTURE_OR_WRONG_UTC_DAY'}
  if any(x not in usage_reasons for x in static['blockingReasons']):raise SystemExit('Routing/storage/minute handoff incomplete; usage probe not sent')
  if (root/'quota.sqlite3').exists():raise SystemExit('Unsealed existing quota ledger: reconcile manually; no usage request sent')
  # Durable one-shot reservation prevents deploy restart loops spending usage credits.
  try:
   with (root/'bootstrap-usage-attempt.json').open('x') as attempt:json.dump({'state':'reserved_before_provider_io','UTC':datetime.datetime.now(datetime.timezone.utc).isoformat()},attempt);attempt.flush();os.fsync(attempt.fileno())
  except FileExistsError:raise SystemExit('First handoff attempt already used; preserve/reconcile before explicit retry')
  from usage_probe import probe
  counters=probe()
  manifest['providerUsage']={'dailyUsed':counters['daily_usage'],'postMeasurementCallsReserved':1,'observedUTC':counters['observedUTC']}
  (root/'initial-usage-sanitized.json').write_text(json.dumps(counters,indent=2))
 auth=authorize(manifest,root,True,datetime.datetime.now(datetime.timezone.utc))
 if 'INITIAL_DAILY_USAGE' in os.environ and int(os.environ['INITIAL_DAILY_USAGE'])!=auth['initialDailyUsage']:raise SystemExit('Initial usage differs from verified handoff')
 b=Broker(root/'quota.sqlite3',live_provider,initial_daily_usage=auth['initialDailyUsage'])
 seal_after_initialize(auth,root)
 with b.db() as db:db.execute('INSERT OR REPLACE INTO cooldown VALUES(?,?)',('*',b.clock()+60000))
server=serve(b,int(os.environ['BROKER_PORT']),os.environ.get('BROKER_BIND','127.0.0.1'),os.environ.get('BROKER_TOKEN'))
signal.signal(signal.SIGTERM,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
try:server.serve_forever()
finally:
 server.server_close()
 if 'db' in globals():db.close()
