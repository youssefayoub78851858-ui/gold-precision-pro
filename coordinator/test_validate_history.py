import datetime,unittest
from validate_history import validate
def history():
 start=datetime.datetime(2026,9,1,tzinfo=datetime.timezone.utc)
 return {'source':'synthetic-unit-test-not-real','symbol':'XAU/USD','frames':{
 f:[{'datetime':(start+datetime.timedelta(minutes=m*i)).isoformat().replace('+00:00','Z'),
 'open':4100,'high':4102,'low':4098,'close':4101} for i in range(64)]
 for f,m in [('15min',15),('1h',60),('4h',240)]}}
class HistoryGate(unittest.TestCase):
 def test_valid_shape(self):self.assertEqual(validate(history())['status'],'VALID')
 def test_missing_provenance(self):
  d=history();d.pop('source')
  with self.assertRaises(ValueError):validate(d)
 def test_duplicate_timestamp(self):
  d=history();d['frames']['15min'][2]['datetime']=d['frames']['15min'][1]['datetime']
  with self.assertRaises(ValueError):validate(d)
 def test_bad_ohlc(self):
  d=history();d['frames']['1h'][3]['low']=5000
  with self.assertRaises(ValueError):validate(d)
 def test_incorrect_symbol(self):
  d=history();d['symbol']='EUR/USD'
  with self.assertRaises(ValueError):validate(d)
 def test_gap_is_reported_not_hidden(self):
  d=history()
  for i in range(10,64):
   t=datetime.datetime.fromisoformat(d['frames']['15min'][i]['datetime'].replace('Z','+00:00'))
   d['frames']['15min'][i]['datetime']=(t+datetime.timedelta(minutes=15)).isoformat().replace('+00:00','Z')
  self.assertEqual(validate(d)['gapCounts']['15min'],1)
 def test_misaligned_time(self):
  d=history();d['frames']['4h'][4]['datetime']='2026-09-01T16:01:00Z'
  with self.assertRaises(ValueError):validate(d)
if __name__=='__main__':unittest.main()
