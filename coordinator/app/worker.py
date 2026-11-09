"""Single-writer, transactional paper worker. Only outbound HTTP GET; no broker SDK."""
import argparse,datetime,fcntl,gzip,hashlib,json,os,pathlib,signal,sqlite3,subprocess,threading,time,urllib.request,uuid
import reduced
import urllib.error
ROOT=pathlib.Path(__file__).parent
CONFIG=json.loads((ROOT/'config.json').read_text())
STOP=threading.Event()
def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'))
def checksum(blob):return hashlib.sha256(blob).hexdigest()
def verify():
    manifest=json.loads((ROOT/'package-manifest.json').read_text())
    for name,digest in manifest['files'].items():
        if checksum((ROOT/name).read_bytes())!=digest:raise RuntimeError('Frozen file mismatch: '+name)
    return checksum((ROOT/'config.json').read_bytes())
def connect(path):
    db=sqlite3.connect(path,timeout=5,isolation_level=None)
    db.execute('PRAGMA journal_mode=WAL');db.execute('PRAGMA synchronous=FULL');db.execute('PRAGMA foreign_keys=ON')
    db.executescript('''
    CREATE TABLE IF NOT EXISTS metadata(key TEXT PRIMARY KEY,value TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS state(id INTEGER PRIMARY KEY CHECK(id=1),json TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS snapshots(sha TEXT PRIMARY KEY,gzip BLOB NOT NULL);
    CREATE TABLE IF NOT EXISTS observations(id TEXT PRIMARY KEY,observed_ms INTEGER NOT NULL,snapshot_sha TEXT REFERENCES snapshots(sha),status TEXT NOT NULL);
    CREATE TABLE IF NOT EXISTS events(id TEXT PRIMARY KEY,observation_id TEXT NOT NULL REFERENCES observations(id),json TEXT NOT NULL);
    INSERT OR IGNORE INTO state VALUES(1,'{}');
    ''')
    # Review execution policy has a separate identity from the frozen strategy/config.
    policy=checksum((ROOT.parent/'timing.js').read_bytes()+(ROOT/'paper-core.js').read_bytes()+(ROOT/'reduced.py').read_bytes())
    prior=db.execute("SELECT value FROM metadata WHERE key='reviewTimingPolicySha256'").fetchone()
    if prior and prior[0]!=policy:raise RuntimeError('Different review timing policy; separate database required')
    if not prior and db.execute('SELECT COUNT(*) FROM observations').fetchone()[0]:raise RuntimeError('Refusing original observations without review policy identity')
    db.execute("INSERT OR IGNORE INTO metadata VALUES('reviewTimingPolicySha256',?)",(policy,))
    mode=os.environ.get('PAPER_DATA_MODE','readonly_live')
    previous_mode=db.execute("SELECT value FROM metadata WHERE key='paperDataMode'").fetchone()
    if previous_mode and previous_mode[0]!=mode:raise RuntimeError('Refusing to mix recorded replay and live paper state')
    db.execute("INSERT OR IGNORE INTO metadata VALUES('paperDataMode',?)",(mode,))
    config_hash=verify();old=db.execute("SELECT value FROM metadata WHERE key='configSha256'").fetchone()
    if old and old[0]!=config_hash:raise RuntimeError('Database belongs to a different frozen configuration')
    db.execute("INSERT OR IGNORE INTO metadata VALUES('configSha256',?)",(config_hash,))
    return db
def evaluate(raw,now,state):
    result=subprocess.run(['node',str(ROOT/'evaluate.js')],input=canonical({'raw':raw,'now':now,'state':state}),text=True,capture_output=True,timeout=15,check=True)
    return json.loads(result.stdout)
def commit_poll(db,raw,now,poll_id=None,fail_before_state=False,evaluator=evaluate):
    verify();poll_id=poll_id or str(uuid.uuid4());blob=canonical(raw).encode();sha=checksum(blob)
    db.execute('BEGIN IMMEDIATE')
    try:
        if db.execute('SELECT 1 FROM observations WHERE id=?',(poll_id,)).fetchone():db.rollback();return []
        state=json.loads(db.execute('SELECT json FROM state WHERE id=1').fetchone()[0])
        previous=db.execute('SELECT MAX(observed_ms) FROM observations').fetchone()[0]
        if previous is not None and now<previous:raise RuntimeError('Clock moved backwards; refusing stale observation')
        result=evaluator(raw,now,state)
        last_good=db.execute('SELECT MAX(observed_ms) FROM observations WHERE status="PROCESSED"').fetchone()[0]
        if last_good is not None and now-last_good>990000:
            result['events'].insert(0,{'type':'MONITOR_GAP','paperOnly':True,'observedAtUTC':datetime.datetime.fromtimestamp(now/1000,datetime.timezone.utc).isoformat(),'secondsSincePreviousPoll':(now-last_good)/1000,'reason':'Observation gap; no missed signal or entry backfilled. Exceeds expected M15 observation interval; may include closed-market time.'})
        db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(sha,gzip.compress(blob)))
        db.execute('INSERT INTO observations VALUES(?,?,?,?)',(poll_id,now,sha,'PROCESSED'))
        for index,event in enumerate(result['events']):
            event.update(snapshotSha256=sha,observationId=poll_id,paperDataMode=os.environ.get('PAPER_DATA_MODE','readonly_live'))
            kind=event['type']
            if kind=='SIGNAL':identity={'type':kind,'candle':event['candleOpenUTC']}
            elif kind in ['PAPER_ENTRY','PAPER_EXIT']:identity={'type':kind,'entry':event['position']['entryBarUTC'],'side':event['position']['side']}
            else:identity={'poll':poll_id,'index':index}
            db.execute('INSERT INTO events VALUES(?,?,?)',(checksum(canonical(identity).encode()),poll_id,canonical(event)))
        if fail_before_state:raise RuntimeError('Injected crash before state commit')
        db.execute('UPDATE state SET json=? WHERE id=1',(canonical(result['state']),))
        db.commit();return result['events']
    except BaseException:db.rollback();raise
def record_error(db,kind):
    now=int(time.time()*1000);poll=str(uuid.uuid4())
    event={'type':'POLL_ERROR','signal':'WAIT','errorType':kind,'paperOnly':True,'observedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat(),'reason':'No decision or entry inferred from failed poll'}
    db.execute('BEGIN IMMEDIATE')
    try:
        db.execute('INSERT INTO observations VALUES(?,?,NULL,?)',(poll,now,'ERROR'))
        db.execute('INSERT INTO events VALUES(?,?,?)',(poll,poll,canonical(event)));db.commit()
    except BaseException:db.rollback();raise
def record_status(db,reason,slot):
    oid=f'status-{slot}-{reason}';now=int(time.time()*1000)
    event={'type':'STATUS','signal':'WAIT','reason':reason,'paperOnly':True,'observedAtUTC':datetime.datetime.now(datetime.timezone.utc).isoformat()}
    db.execute('BEGIN IMMEDIATE')
    try:
        if not db.execute('SELECT 1 FROM observations WHERE id=?',(oid,)).fetchone():
            db.execute('INSERT INTO observations VALUES(?,?,NULL,?)',(oid,now,'SCHEDULER'))
            db.execute('INSERT INTO events VALUES(?,?,?)',(oid,oid,canonical(event)))
        db.commit()
    except BaseException:db.rollback();raise
def fetch_raw():
    raw={}
    for frame in ['15min','1h','4h']:
        if STOP.is_set():raise InterruptedError('Shutdown requested')
        request=urllib.request.Request(os.environ.get('CANDLES_URL','http://127.0.0.1:3111/api/candles')+'?interval='+frame,headers={'User-Agent':'GoldV2PaperMonitor/1.0'})
        with urllib.request.urlopen(request,timeout=7) as response:
            blob=response.read(5_000_001)
            if len(blob)>5_000_000:raise ValueError('Response too large')
        raw[frame]=json.loads(blob)
    return raw
def backup(db,directory):
    target=directory/'latest-backup.sqlite3';tmp=directory/'backup.tmp'
    with sqlite3.connect(tmp) as dest:db.backup(dest)
    with sqlite3.connect(tmp) as dest:
        if dest.execute('PRAGMA integrity_check').fetchone()[0]!='ok':raise RuntimeError('Backup integrity failed')
    os.replace(tmp,target)
def import_legacy(db,source):
    """Run only after stopping the old watcher; preserve its state and entire audit log."""
    if db.execute('SELECT COUNT(*) FROM observations').fetchone()[0]:raise RuntimeError('Import requires an empty database')
    source=pathlib.Path(source);state=json.loads((source/'state.json').read_text())
    events=[json.loads(line) for line in (source/'events.jsonl').read_text().splitlines() if line.strip()]
    db.execute('BEGIN IMMEDIATE')
    try:
        for i,event in enumerate(events):
            oid='legacy-'+str(i);sha=None;snapshot=event.get('snapshotPath')
            if snapshot and pathlib.Path(snapshot).exists():
                blob=pathlib.Path(snapshot).read_bytes();sha=checksum(blob)
                expected=event.get('snapshotSha256')
                if expected and sha!=expected:raise RuntimeError('Legacy snapshot hash mismatch')
                db.execute('INSERT OR IGNORE INTO snapshots VALUES(?,?)',(sha,gzip.compress(blob)))
            observed=int(datetime.datetime.fromisoformat(event['observedAtUTC'].replace('Z','+00:00')).timestamp()*1000)
            db.execute('INSERT INTO observations VALUES(?,?,?,?)',(oid,observed,sha,'LEGACY'))
            db.execute('INSERT INTO events VALUES(?,?,?)',(oid,oid,canonical(event)))
        db.execute('UPDATE state SET json=? WHERE id=1',(canonical(state),));db.commit()
    except BaseException:db.rollback();raise
def health(db,directory):
    latest=db.execute('SELECT MAX(observed_ms) FROM observations WHERE status="PROCESSED"').fetchone()[0]
    state=json.loads(db.execute('SELECT json FROM state').fetchone()[0]);now=int(time.time()*1000)
    obj={'checked_ms':now,'last_processed_ms':latest,'observation_age_seconds':None if latest is None else (now-latest)/1000,'state':state,'paperOnly':True}
    temp=directory/'heartbeat.tmp';temp.write_text(canonical(obj));os.replace(temp,directory/'heartbeat.json');return obj
def main():
    parser=argparse.ArgumentParser();parser.add_argument('--once',action='store_true');parser.add_argument('--fixture');parser.add_argument('--export',action='store_true');parser.add_argument('--backup',action='store_true');parser.add_argument('--healthcheck',action='store_true');parser.add_argument('--import-legacy');args=parser.parse_args()
    directory=pathlib.Path(os.environ.get('DATA_DIR','/var/data/gold-v2'));directory.mkdir(parents=True,exist_ok=True)
    if args.healthcheck:
        obj=json.loads((directory/'heartbeat.json').read_text());age=time.time()-obj['checked_ms']/1000
        raise SystemExit(0 if age<180 else 1)
    with (directory/'worker.lock').open('w') as lock:
        fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB);db=connect(directory/'monitor.sqlite3')
        try:
            if args.import_legacy:import_legacy(db,args.import_legacy);backup(db,directory);return
            if args.export:
                for row in db.execute('SELECT json FROM events ORDER BY rowid'):print(row[0])
                return
            if args.backup:backup(db,directory);return
            reduced.init(db);last_backup=0
            while not STOP.is_set():
                now=int(time.time()*1000)
                if not args.once and not args.fixture:
                    if now>=int(datetime.datetime.fromisoformat(CONFIG['prospectiveEndUTC'].replace('Z','+00:00')).timestamp()*1000):
                        while not STOP.wait(60):health(db,directory)
                        break
                    if not reduced.storage_ok(directory):
                        record_status(db,'STORAGE_SAFETY_LIMIT',int(now//900000)*900);health(db,directory);STOP.wait(60);continue
                    reservation=reduced.reserve(db,now)
                    if reservation['action']!='FETCH':
                        if reservation['action']=='STATUS':record_status(db,reservation['reason'],reservation['slot'])
                        health(db,directory);STOP.wait(1);continue
                else:reservation=None
                try:
                    raw=json.loads(pathlib.Path(args.fixture).read_text()) if args.fixture else fetch_raw()
                    observed=int(time.time()*1000)
                    events=commit_poll(db,raw,observed,reservation['poll_id'] if reservation else None)
                    if reservation:
                        state=json.loads(db.execute('SELECT json FROM state WHERE id=1').fetchone()[0])
                        ready=(reduced.input_ready(raw,observed) or any(e.get('reason')=='MARKET_CLOSED' for e in events)) and not state.get('pending') and not any(e['type']=='DATA_ERROR' for e in events)
                        reduced.finish(db,reservation,ready)
                    print(canonical({'events':[{'type':e['type'],'signal':e.get('signal'),'reason':e.get('reason')} for e in events]}),flush=True)
                    if time.time()-last_backup>=86400:backup(db,directory);last_backup=time.time()
                except InterruptedError:
                    if STOP.is_set():break
                    raise
                except (OSError,ValueError,subprocess.SubprocessError) as exc:
                    if reservation and isinstance(exc,urllib.error.HTTPError):
                        try:
                            retry=json.loads(exc.read()).get('retryAtMS')
                            if isinstance(retry,(int,float)):reduced.defer(db,reservation['slot'],retry)
                        except (ValueError,OSError):pass
                    record_error(db,type(exc).__name__);print(canonical({'errorType':type(exc).__name__,'signal':'WAIT'}),flush=True)
                    if reservation:reduced.finish(db,reservation,False)
                health(db,directory)
                if args.once or args.fixture:break
                if time.time()>=datetime.datetime.fromisoformat(CONFIG['prospectiveEndUTC'].replace('Z','+00:00')).timestamp():
                    print('Prospective window ended; archive retained; polling stopped.',flush=True)
                    # Remain idle to avoid platform restarts repeatedly polling past the window.
                    while not STOP.wait(60):health(db,directory)
                    break
                STOP.wait(1)
        finally:
            db.execute('PRAGMA wal_checkpoint(TRUNCATE)');db.close()
if __name__=='__main__':
    for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda *_:STOP.set())
    main()
