"""Read-only SQLite observer. First-seen latency is an upper bound, never exact commit time."""
import argparse,datetime,fcntl,json,pathlib,signal,sqlite3,threading,time
STOP=threading.Event()
def utc():return datetime.datetime.now(datetime.timezone.utc).isoformat()
def main():
 p=argparse.ArgumentParser();p.add_argument('--db',required=True);p.add_argument('--output',required=True);a=p.parse_args()
 out=pathlib.Path(a.output);out.parent.mkdir(parents=True,exist_ok=True)
 with out.with_suffix('.lock').open('a') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  cursor=None;last_poll=None
  with out.open('a',buffering=1) as log:
   while not STOP.is_set():
    try:
     with sqlite3.connect('file:'+str(pathlib.Path(a.db).resolve())+'?mode=ro',uri=True,timeout=2) as db:
      db.execute('PRAGMA query_only=ON')
      if cursor is None:
       cursor=db.execute('SELECT COALESCE(MAX(rowid),0) FROM events').fetchone()[0]
       log.write(json.dumps({'type':'OBSERVER_START','UTC':utc(),'baselineEventRow':cursor,'measurement':'Existing events excluded from fresh latency metrics; restarts produce observation gaps'})+'\n')
      rows=db.execute('SELECT e.rowid,e.id,e.json,o.observed_ms FROM events e JOIN observations o ON o.id=e.observation_id WHERE e.rowid>? ORDER BY e.rowid',(cursor,)).fetchall()
     seen=utc();seen_ms=datetime.datetime.fromisoformat(seen).timestamp()*1000
     for rowid,eid,raw,received in rows:
      event=json.loads(raw);record={'eventID':eid,'row':rowid,'firstSeenUTC':seen,'previousPollUTC':last_poll,'inputObservedMS':received,'event':event,'measurement':'DB first-seen upper bound; includes observer poll delay; not exact transaction commit timestamp'}
      if event.get('type')=='SIGNAL' and event.get('candleCloseUTC'):
       closed=datetime.datetime.fromisoformat(event['candleCloseUTC'].replace('Z','+00:00')).timestamp()*1000
       record['closeToDBFirstSeenSeconds']=(seen_ms-closed)/1000;record['inputToDBFirstSeenSeconds']=(seen_ms-received)/1000
      log.write(json.dumps(record)+'\n');cursor=rowid
     last_poll=seen
    except (sqlite3.Error,OSError,ValueError):
     # Producer audit is independent; never create or repair the paper database here.
     pass
    STOP.wait(1)
if __name__=='__main__':
 for s in [signal.SIGINT,signal.SIGTERM]:signal.signal(s,lambda *_:STOP.set())
 main()
