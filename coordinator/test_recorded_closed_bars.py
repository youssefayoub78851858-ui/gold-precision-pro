"""Deterministic closed-bar paper replay with persistence and restart; no external data."""
import datetime,json,pathlib,tempfile,unittest
from app import worker
UTC=datetime.timezone.utc
def millis(s):return int(datetime.datetime.fromisoformat(s.replace('Z','+00:00')).timestamp()*1000)
def fixture(now):
 result={}
 for frame,minutes in [('15min',15),('1h',60),('4h',240)]:
  last=(now//(minutes*60000))*(minutes*60000)-minutes*60000
  rows=[]
  for i in range(80):
   t=last-(79-i)*minutes*60000
   price=4100+i*.1
   rows.append({'datetime':datetime.datetime.fromtimestamp(t/1000,UTC).isoformat().replace('+00:00','Z'),'open':price,'high':price+2,'low':price-2,'close':price+.2})
  result[frame]={'symbol':'XAU/USD','interval':frame,'values':rows}
 return result
class RecordedClosedBars(unittest.TestCase):
 def test_persisted_replay_and_duplicate_poll_are_idempotent(self):
  now=millis('2026-11-10T04:00:05Z')
  with tempfile.TemporaryDirectory() as d:
   db=worker.connect(pathlib.Path(d)/'paper.sqlite3')
   raw=fixture(now)
   try:
    first=worker.commit_poll(db,raw,now,poll_id='replay-slot-1')
    self.assertTrue(first)
    self.assertTrue(all(e.get('paperOnly') for e in first))
    self.assertEqual(worker.commit_poll(db,raw,now,poll_id='replay-slot-1'),[])
    before=db.execute('SELECT COUNT(*) FROM events').fetchone()[0]
    self.assertEqual(db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],1)
    db.close()
    db=worker.connect(pathlib.Path(d)/'paper.sqlite3')
    self.assertEqual(worker.commit_poll(db,raw,now,poll_id='replay-slot-1'),[])
    self.assertEqual(db.execute('SELECT COUNT(*) FROM events').fetchone()[0],before)
    self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
   finally:db.close()
if __name__=='__main__':unittest.main()
