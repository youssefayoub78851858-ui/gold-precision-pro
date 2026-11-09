"""Persistent close-aligned transport scheduler; frozen strategy and paper core unchanged."""
import datetime,json,pathlib,sqlite3,time,shutil
from zoneinfo import ZoneInfo
ROOT=pathlib.Path(__file__).parent
CFG=json.loads((ROOT/'scheduler.json').read_text())
def open_market(ms):
 n=datetime.datetime.fromtimestamp(ms/1000,datetime.timezone.utc).astimezone(ZoneInfo('America/New_York'))
 return n.weekday()!=5 and not(n.weekday()==6 and n.hour<18) and not(n.weekday()==4 and n.hour>=17) and n.hour!=17
def init(db):
 db.executescript('''CREATE TABLE IF NOT EXISTS poll_attempts(slot INTEGER,attempt INTEGER,utc_day TEXT,credits INTEGER,status TEXT,PRIMARY KEY(slot,attempt));
 CREATE TABLE IF NOT EXISTS completed_slots(slot INTEGER PRIMARY KEY,status TEXT);
 CREATE TABLE IF NOT EXISTS retry_hints(slot INTEGER PRIMARY KEY,next_ms INTEGER);''')
def reserve(db,now):
 """Reserve before I/O, so a crash can overcount but cannot undercount the local allowance."""
 seconds=now/1000;slot=int(seconds//CFG['slotSeconds'])*CFG['slotSeconds'];age=seconds-slot
 day=datetime.datetime.fromtimestamp(seconds,datetime.timezone.utc).date().isoformat()
 db.execute('BEGIN IMMEDIATE')
 try:
  if db.execute('SELECT 1 FROM completed_slots WHERE slot=?',(slot,)).fetchone():db.commit();return {'action':'WAIT','reason':'SLOT_COMPLETE'}
  if not open_market(now) and not open_market(slot*1000-60000):
   db.execute('INSERT INTO completed_slots VALUES(?,?)',(slot,'MARKET_CLOSED'));db.commit();return {'action':'STATUS','reason':'MARKET_CLOSED','slot':slot}
  if age>CFG['maximumObservationDelaySeconds']:
   db.execute('INSERT INTO completed_slots VALUES(?,?)',(slot,'WINDOW_MISSED'));db.commit();return {'action':'STATUS','reason':'WINDOW_MISSED_NO_BACKFILL','slot':slot}
  count=db.execute('SELECT COUNT(*) FROM poll_attempts WHERE slot=?',(slot,)).fetchone()[0]
  if count>=len(CFG['attemptOffsetsSeconds']):
   db.execute('INSERT INTO completed_slots VALUES(?,?)',(slot,'RETRIES_EXHAUSTED'));db.commit();return {'action':'STATUS','reason':'RETRIES_EXHAUSTED','slot':slot}
  due=slot+CFG['attemptOffsetsSeconds'][count]
  hint=db.execute('SELECT next_ms FROM retry_hints WHERE slot=?',(slot,)).fetchone()
  if hint:due=max(due,hint[0]/1000)
  if seconds<due:db.commit();return {'action':'WAIT','reason':'NOT_DUE','next_ms':int(due*1000)}
  used=db.execute('SELECT COALESCE(SUM(credits),0) FROM poll_attempts WHERE utc_day=?',(day,)).fetchone()[0]
  if used+CFG['reservedCreditsPerAttempt']>CFG['maximumReservedCreditsPerUTCDay']:
   db.execute('INSERT INTO completed_slots VALUES(?,?)',(slot,'LOCAL_QUOTA_LIMIT'));db.commit();return {'action':'STATUS','reason':'LOCAL_QUOTA_LIMIT','slot':slot}
  db.execute('INSERT INTO poll_attempts VALUES(?,?,?,?,?)',(slot,count,day,CFG['reservedCreditsPerAttempt'],'RESERVED'))
  db.commit();return {'action':'FETCH','slot':slot,'attempt':count,'poll_id':f'close-{slot}-{count}','reservedCreditsToday':used+CFG['reservedCreditsPerAttempt']}
 except BaseException:db.rollback();raise
def defer(db,slot,next_ms):
 with db:db.execute('INSERT OR REPLACE INTO retry_hints VALUES(?,?)',(slot,int(next_ms)))
def finish(db,reservation,ready):
 db.execute('BEGIN IMMEDIATE')
 try:
  db.execute('UPDATE poll_attempts SET status=? WHERE slot=? AND attempt=?',('READY' if ready else 'RETRY',reservation['slot'],reservation['attempt']))
  if ready:db.execute('INSERT OR IGNORE INTO completed_slots VALUES(?,?)',(reservation['slot'],'READY'))
  db.commit()
 except BaseException:db.rollback();raise
def storage_ok(directory):
 path=pathlib.Path(directory)/'monitor.sqlite3';size=path.stat().st_size if path.exists() else 0
 # Atomic backup replacement needs current DB + old backup + new temporary backup.
 free=shutil.disk_usage(directory).free
 return size<CFG['maximumDatabaseBytes'] and free>size+CFG['minimumFreeBytes']
def input_ready(raw,now):
 # Share exactly the JS admission contract; no second set of age constants.
 import subprocess
 try:
  p=subprocess.run(['node',str(ROOT.parent/'timing-cli.js')],input=json.dumps({'raw':raw,'now':now}),text=True,capture_output=True,timeout=10,check=True)
  return json.loads(p.stdout)['accepted'] is True
 except (ValueError,OSError,subprocess.SubprocessError):return False
