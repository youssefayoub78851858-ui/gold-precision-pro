"""Transactional paper event lifecycle contract (injected decisions, NOT strategy performance)."""
import json,os,pathlib,sys,tempfile,unittest
sys.path.insert(0,str(pathlib.Path(__file__).resolve().parent/'app'))
import worker
class PaperEventLifecycle(unittest.TestCase):
 def test_entry_exit_restart_deduplication_and_atomic_rollback(self):
  old=os.environ.get('PAPER_DATA_MODE');os.environ['PAPER_DATA_MODE']='recorded_replay'
  try:
   with tempfile.TemporaryDirectory() as tmp:
    path=pathlib.Path(tmp)/'paper.sqlite3';db=worker.connect(path)
    position={'entryBarUTC':'2026-11-10T01:00:00Z','side':'BUY'}
    raw={'fixture':'injected-paper-events-not-market-data'}
    def evaluator(kind):
     def run(raw,now,state):
      if kind=='entry':
       return {'state':{'position':position},'events':[{'type':'PAPER_ENTRY','position':position,'paperOnly':True}]}
      return {'state':{'position':None},'events':[{'type':'PAPER_EXIT','position':position,'paperOnly':True,'netR':1.2}]}
     return run
    try:
     entry=worker.commit_poll(db,raw,1000000,'entry-1',evaluator=evaluator('entry'))
     self.assertEqual([e['type'] for e in entry],['PAPER_ENTRY'])
     self.assertEqual(worker.commit_poll(db,raw,1000000,'entry-1',evaluator=evaluator('entry')),[])
     self.assertEqual(json.loads(db.execute('SELECT json FROM state WHERE id=1').fetchone()[0])['position'],position)
     with self.assertRaises(RuntimeError):
      worker.commit_poll(db,raw,1001000,'crash-1',fail_before_state=True,evaluator=evaluator('exit'))
     self.assertEqual(db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],1)
     db.close();db=worker.connect(path)
     exit_events=worker.commit_poll(db,raw,1002000,'exit-1',evaluator=evaluator('exit'))
     self.assertEqual([e['type'] for e in exit_events],['PAPER_EXIT'])
     self.assertEqual(worker.commit_poll(db,raw,1002000,'exit-1',evaluator=evaluator('exit')),[])
     events=[json.loads(row[0]) for row in db.execute('SELECT json FROM events')]
     self.assertEqual(sum(e['type']=='PAPER_ENTRY' for e in events),1)
     self.assertEqual(sum(e['type']=='PAPER_EXIT' for e in events),1)
     self.assertTrue(all(e['paperOnly'] and e['paperDataMode']=='recorded_replay' for e in events))
     self.assertEqual(db.execute('SELECT COUNT(*) FROM observations').fetchone()[0],2)
     self.assertEqual(db.execute('PRAGMA integrity_check').fetchone()[0],'ok')
    finally:db.close()
  finally:
   if old is None:os.environ.pop('PAPER_DATA_MODE',None)
   else:os.environ['PAPER_DATA_MODE']=old
if __name__=='__main__':unittest.main()
