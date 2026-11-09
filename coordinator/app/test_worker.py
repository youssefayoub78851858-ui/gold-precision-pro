import unittest,tempfile,pathlib,json,subprocess,os,fcntl,sqlite3
import worker
FIXTURE=pathlib.Path(__file__).resolve().parents[1]/"local-fixture.json"
class Durability(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name);self.db=worker.connect(self.path/'test.sqlite3')
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def counts(self):return [self.db.execute('SELECT COUNT(*) FROM '+t).fetchone()[0] for t in ['observations','events','snapshots']]
 def fake(self,raw,now,state):
  if state.get('seen'):return {'state':state,'events':[]}
  state['seen']=True
  return {'state':state,'events':[{'type':'SIGNAL','signal':'BUY','candleOpenUTC':'2026-11-09T00:00:00Z'},{'type':'PAPER_ENTRY','position':{'entryBarUTC':'2026-11-09T00:15:00Z','side':'BUY'}}]}
 def test_crash_rolls_back_events_and_state_then_retry_once(self):
  with self.assertRaises(RuntimeError):worker.commit_poll(self.db,{},1000,'one',True,self.fake)
  self.assertEqual(self.counts(),[0,0,0]);self.assertEqual(self.db.execute('SELECT json FROM state').fetchone()[0],'{}')
  worker.commit_poll(self.db,{},1000,'one',evaluator=self.fake);self.assertEqual(self.counts(),[1,2,1])
  worker.commit_poll(self.db,{},1000,'one',evaluator=self.fake);self.assertEqual(self.counts(),[1,2,1])
 def test_restart_and_repeat_snapshot_does_not_duplicate_signals(self):
  worker.commit_poll(self.db,{},1000,'one',evaluator=self.fake);self.db.close();self.db=worker.connect(self.path/'test.sqlite3')
  worker.commit_poll(self.db,{},2000,'two',evaluator=self.fake);self.assertEqual(self.counts(),[2,2,1])
 def test_clock_rollback_rejected(self):
  worker.commit_poll(self.db,{},1000,evaluator=self.fake)
  with self.assertRaises(RuntimeError):worker.commit_poll(self.db,{},999,evaluator=self.fake)
 def test_backup_restores_complete_state_and_events(self):
  worker.commit_poll(self.db,{},1000,evaluator=self.fake);worker.backup(self.db,self.path)
  with sqlite3.connect(self.path/'latest-backup.sqlite3') as restored:
   self.assertEqual(restored.execute('PRAGMA integrity_check').fetchone()[0],'ok');self.assertEqual(restored.execute('SELECT COUNT(*) FROM events').fetchone()[0],2);self.assertTrue(json.loads(restored.execute('SELECT json FROM state').fetchone()[0])['seen'])
 def test_lock_rejects_second_process(self):
  with (self.path/'lock').open('w') as lock:
   fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
   result=subprocess.run(['python','-c','import fcntl,sys; f=open(sys.argv[1],"w"); fcntl.flock(f,fcntl.LOCK_EX|fcntl.LOCK_NB)',str(self.path/'lock')],capture_output=True)
   self.assertNotEqual(result.returncode,0)
 @unittest.skipUnless(FIXTURE.exists(), "Recorded local-fixture.json is not included in this checkout; cannot assert replay behavior")
 def test_real_frozen_core_closed_market_and_bad_data_wait(self):
  raw=json.loads(FIXTURE.read_text())
  now=1794142800000 # overwritten below with explicit UTC for readability
  import datetime
  now=int(datetime.datetime(2026,11,8,13,tzinfo=datetime.timezone.utc).timestamp()*1000)
  worker.commit_poll(self.db,raw,now,'closed')
  rows=[json.loads(x[0]) for x in self.db.execute('SELECT json FROM events')]
  self.assertTrue(any(e.get('signal')=='WAIT' and e.get('reason')=='MARKET_CLOSED' for e in rows))
  raw['15min']['values'].append(raw['15min']['values'][0]);worker.commit_poll(self.db,raw,now+1000,'bad')
  last=json.loads(self.db.execute('SELECT json FROM events ORDER BY rowid DESC LIMIT 1').fetchone()[0]);self.assertEqual(last['type'],'DATA_ERROR');self.assertEqual(last['signal'],'WAIT')
 def test_legacy_import_is_atomic_and_cannot_repeat(self):
  source=self.path/'old';source.mkdir();(source/'state.json').write_text('{"totalNetR":2}')
  (source/'events.jsonl').write_text('{"type":"STATUS","signal":"WAIT","observedAtUTC":"2026-11-08T13:00:00Z"}\n')
  worker.import_legacy(self.db,source);self.assertEqual(self.counts(),[1,1,0])
  with self.assertRaises(RuntimeError):worker.import_legacy(self.db,source)
 @unittest.skipUnless(FIXTURE.exists(), "Recorded local-fixture.json is not included in this checkout; cannot assert replay behavior")
 def test_stale_data_on_open_market_cannot_create_entry(self):
  import datetime
  raw=json.loads(FIXTURE.read_text())
  now=int(datetime.datetime(2026,11,9,1,tzinfo=datetime.timezone.utc).timestamp()*1000)
  result=worker.evaluate(raw,now,{})
  self.assertTrue(any(e.get('reason')=='STALE_OR_MISSING_DATA' and e.get('signal')=='WAIT' for e in result['events']))
  self.assertNotIn('position',result['state'])
 @unittest.skipUnless(FIXTURE.exists(), "Recorded local-fixture.json is not included in this checkout; cannot assert replay behavior")
 def test_missing_active_bar_quarantines_position_without_inventing_result(self):
  import datetime
  raw=json.loads(FIXTURE.read_text())
  entry='2026-11-06 20:30:00';raw['15min']['values']=[c for c in raw['15min']['values'] if c['datetime']!=entry]
  state={'position':{'side':'BUY','entry':4060,'stop':3900,'target1':4200,'target2':4300,'entryBarUTC':'2026-11-06T20:30:00.000Z','lastProcessedUTC':None,'target1Touched':False}}
  now=int(datetime.datetime(2026,11,9,1,tzinfo=datetime.timezone.utc).timestamp()*1000)
  result=worker.evaluate(raw,now,state)
  self.assertTrue(result['state']['position']['quarantined']);self.assertTrue(any(e['type']=='POSITION_QUARANTINED' for e in result['events']))
  self.assertFalse(any(e['type']=='PAPER_EXIT' for e in result['events']))
if __name__=='__main__':unittest.main()
