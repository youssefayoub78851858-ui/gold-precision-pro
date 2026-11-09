import datetime,json,pathlib,tempfile,unittest,sqlite3
import reduced,worker
UTC=datetime.timezone.utc
def ms(value):return int(datetime.datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()*1000)
class ReducedSchedule(unittest.TestCase):
 def setUp(self):self.tmp=tempfile.TemporaryDirectory();self.path=pathlib.Path(self.tmp.name)/'monitor.sqlite3';self.db=worker.connect(self.path);reduced.init(self.db)
 def tearDown(self):self.db.close();self.tmp.cleanup()
 def test_close_alignment_and_retry_offsets(self):
  start=ms('2026-11-09T01:00:00Z');self.assertEqual(reduced.reserve(self.db,start+4000)['action'],'WAIT')
  a=reduced.reserve(self.db,start+5000);self.assertEqual(a['attempt'],0);reduced.finish(self.db,a,False)
  self.assertEqual(reduced.reserve(self.db,start+24000)['action'],'WAIT')
  b=reduced.reserve(self.db,start+25000);self.assertEqual(b['attempt'],1);reduced.finish(self.db,b,False)
  c=reduced.reserve(self.db,start+65000);self.assertEqual(c['attempt'],2);reduced.finish(self.db,c,True)
  self.assertEqual(reduced.reserve(self.db,start+66000)['reason'],'SLOT_COMPLETE')
 def test_no_backfill_after_90_seconds(self):
  self.assertEqual(reduced.reserve(self.db,ms('2026-11-09T01:01:31Z'))['reason'],'WINDOW_MISSED_NO_BACKFILL')
  self.assertEqual(self.db.execute('SELECT COUNT(*) FROM poll_attempts').fetchone()[0],0)
 def test_reserved_credits_survive_restart_and_crash(self):
  start=ms('2026-11-09T01:00:00Z');a=reduced.reserve(self.db,start+5000);self.db.close();self.db=worker.connect(self.path);reduced.init(self.db)
  b=reduced.reserve(self.db,start+25000);self.assertEqual(b['attempt'],1);self.assertEqual(b['reservedCreditsToday'],6)
 def test_daily_quota_is_persistent_and_never_exceeds_400(self):
  self.db.execute('INSERT INTO poll_attempts VALUES(0,0,?,?,?)',('2026-11-09',399,'RESERVED'))
  self.assertEqual(reduced.reserve(self.db,ms('2026-11-09T01:00:05Z'))['reason'],'LOCAL_QUOTA_LIMIT')
  self.assertEqual(reduced.reserve(self.db,ms('2026-11-10T01:00:05Z'))['reservedCreditsToday'],3)
 def test_closed_market_has_no_data_requests(self):
  a=reduced.reserve(self.db,ms('2026-11-08T15:00:05Z'));self.assertEqual(a['reason'],'MARKET_CLOSED');self.assertEqual(self.db.execute('SELECT COUNT(*) FROM poll_attempts').fetchone()[0],0)
 def test_stale_m15_and_higher_frame_must_retry(self):
  def row(t):return {'datetime':t}
  now=ms('2026-11-09T04:00:05Z');raw={'15min':{'values':[row('2026-11-09T03:45:00Z')]},'1h':{'values':[row('2026-11-09T03:00:00Z')]},'4h':{'values':[row('2026-11-09T00:00:00Z')]}}
  self.assertTrue(reduced.input_ready(raw,now));raw['1h']['values']=[row('2026-11-09T02:00:00Z')];self.assertFalse(reduced.input_ready(raw,now))
 def test_full_day_one_success_per_slot_requires_288_credits(self):
  start=ms('2026-11-10T00:00:05Z');used=0
  # Abstract 24h open day, bypass session check only in this arithmetic test.
  original=reduced.open_market;reduced.open_market=lambda _:True
  try:
   for i in range(96):
    a=reduced.reserve(self.db,start+i*900000);self.assertEqual(a['action'],'FETCH');used+=3;reduced.finish(self.db,a,True)
  finally:reduced.open_market=original
  self.assertEqual(used,288)
 def test_retries_exhausted_does_not_fetch_a_fourth_time(self):
  start=ms('2026-11-09T01:00:00Z')
  for delta in [5000,25000,65000]:reduced.finish(self.db,reduced.reserve(self.db,start+delta),False)
  self.assertEqual(reduced.reserve(self.db,start+70000)['reason'],'RETRIES_EXHAUSTED')
 def test_final_bar_at_market_close_is_observed(self):
  self.assertEqual(reduced.reserve(self.db,ms('2026-11-09T22:00:05Z'))['action'],'FETCH')
 def test_shared_quota_retry_hint_is_respected_inside_90_second_window(self):
  start=ms('2026-11-09T01:00:00Z');a=reduced.reserve(self.db,start+5000);reduced.finish(self.db,a,False)
  reduced.defer(self.db,a['slot'],start+65124)
  self.assertEqual(reduced.reserve(self.db,start+65000)['action'],'WAIT')
  self.assertEqual(reduced.reserve(self.db,start+65124)['action'],'FETCH')
 @unittest.skipUnless(pathlib.Path('/workspace/gold-v2-audit/frames.json').exists(), "External audit frames are unavailable; integration replay must run with the original fixture")
 def test_frozen_sell_entry_exit_and_restart_are_persisted_once(self):
  # Replay transport fixture only: shifted old prices; never logged as live or holdout results.
  original=json.loads(pathlib.Path('/workspace/gold-v2-audit/frames.json').read_text());shift=14*86400000
  def raw_at(now):
   raw={}
   for f,rows in original.items():
    shifted=[]
    for c in rows:
     t=ms(c['datetime'].replace(' ','T')+('Z' if not c['datetime'].endswith('Z') else ''))+shift
     if t<=now:shifted.append({**c,'datetime':datetime.datetime.fromtimestamp(t/1000,UTC).isoformat().replace('+00:00','Z')})
    raw[f]={'symbol':'XAU/USD','interval':f,'values':shifted}
   return raw
  start=ms('2026-11-10T00:00:05Z');a=reduced.reserve(self.db,start)
  events=worker.commit_poll(self.db,raw_at(start),start,a['poll_id']);reduced.finish(self.db,a,True)
  self.assertTrue(any(e['type']=='PAPER_ENTRY' and e['position']['side']=='SELL' for e in events))
  self.db.close();self.db=worker.connect(self.path);reduced.init(self.db)
  self.assertEqual(reduced.reserve(self.db,start+1000)['reason'],'SLOT_COMPLETE')
  for i in range(1,49):
   now=start+i*900000;a=reduced.reserve(self.db,now)
   if a['action']!='FETCH':continue
   events=worker.commit_poll(self.db,raw_at(now),now,a['poll_id']);reduced.finish(self.db,a,True)
   if any(e['type']=='PAPER_EXIT' for e in events):break
  records=[json.loads(r[0]) for r in self.db.execute('SELECT json FROM events')]
  self.assertEqual(sum(e['type']=='PAPER_ENTRY' for e in records),1);self.assertEqual(sum(e['type']=='PAPER_EXIT' for e in records),1)
  exit=next(e for e in records if e['type']=='PAPER_EXIT');self.assertAlmostEqual(exit['roundTripPriceCost'],.67);self.assertTrue('netR' in exit)
if __name__=='__main__':unittest.main()
