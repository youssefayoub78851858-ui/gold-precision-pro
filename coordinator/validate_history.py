"""Validate real historical XAU/USD candles before any V2 performance claim.
Usage: python coordinator/validate_history.py history.json
Expected JSON: {"source":"provider or broker export","symbol":"XAU/USD",
"frames":{"15min":[...],"1h":[...],"4h":[...]}}
Each candle has datetime (UTC ISO), open, high, low, close.
No provider calls or secrets.
"""
import datetime,json,math,pathlib,sys
DURATIONS={'15min':15,'1h':60,'4h':240}
def validate(document):
 if not isinstance(document,dict):raise ValueError('Expected JSON object')
 if not isinstance(document.get('source'),str) or not document['source'].strip():
  raise ValueError('Missing data provenance source')
 if document.get('symbol') not in ('XAU/USD','XAUUSD'):
  raise ValueError('Unexpected instrument')
 frames=document.get('frames')
 if not isinstance(frames,dict):raise ValueError('Missing frames')
 report={}
 gaps={}
 for frame,minutes in DURATIONS.items():
  candles=frames.get(frame)
  if not isinstance(candles,list) or len(candles)<60:
   raise ValueError(f'{frame}: at least 60 candles required')
  previous=None
  gaps[frame]=0
  for i,c in enumerate(candles):
   if not isinstance(c,dict):raise ValueError(f'{frame}[{i}]: invalid candle')
   try:
    stamp=datetime.datetime.fromisoformat(c['datetime'].replace('Z','+00:00'))
    if stamp.tzinfo is None or stamp.utcoffset()!=datetime.timedelta(0):
     raise ValueError('timestamp must be UTC')
    values=[float(c[k]) for k in ('open','high','low','close')]
   except (KeyError,TypeError,ValueError,AttributeError) as e:
    raise ValueError(f'{frame}[{i}]: invalid timestamp or OHLC: {e}') from e
   o,h,l,close=values
   if not all(math.isfinite(v) and v>0 for v in values) or l>h or not l<=o<=h or not l<=close<=h:
    raise ValueError(f'{frame}[{i}]: invalid price range')
   if (int(stamp.timestamp())//60)%minutes!=0 or stamp.second or stamp.microsecond:
    raise ValueError(f'{frame}[{i}]: misaligned UTC open')
   if previous is not None and stamp<=previous:
    raise ValueError(f'{frame}[{i}]: duplicate or unsorted time')
   if previous is not None:
    delta=(stamp-previous).total_seconds()
    if delta<minutes*60:raise ValueError(f'{frame}[{i}]: overlapping bars')
    if delta>minutes*60:gaps[frame]+=1
   previous=stamp
  report[frame]={'count':len(candles),'lastOpenUTC':previous.isoformat()}
 return {'status':'VALID','symbol':document['symbol'],'source':document['source'],'frames':report,'gapCounts':gaps,'note':'Validity does not prove completeness, source authenticity or profitability'}
if __name__=='__main__':
 try:print(json.dumps(validate(json.loads(pathlib.Path(sys.argv[1]).read_text())),indent=2))
 except (ValueError,IndexError,OSError,json.JSONDecodeError) as e:
  print(f'INVALID HISTORY: {e}',file=sys.stderr);sys.exit(1)
