"""Import Dukascopy-node CSV OHLC into V2 history JSON. Fail closed on ambiguity."""
import csv,datetime,json,pathlib,sys
FRAMES={'m15':'15min','h1':'1h','h4':'4h'}
def convert(root):
 result={}
 for folder,frame in FRAMES.items():
  files=list((root/folder).rglob('*.csv'))
  if len(files)!=1:raise ValueError(f'{folder}: expected exactly one CSV, got {len(files)}')
  with files[0].open(newline='') as stream:
   reader=csv.DictReader(stream)
   if not reader.fieldnames:raise ValueError(f'{folder}: no CSV header')
   names={x.strip().lower():x for x in reader.fieldnames}
   def col(*candidates):
    for name in candidates:
     if name in names:return names[name]
    raise ValueError(f'{folder}: missing column {candidates}, available={list(names)}')
   time=col('timestamp','datetime','date','time')
   o,h,l,c=[col(n) for n in ('open','high','low','close')]
   bars=[]
   for row in reader:
    raw=row[time].strip()
    if raw.isdigit():
     number=int(raw)
     if number>10**12:number/=1000
     dt=datetime.datetime.fromtimestamp(number,datetime.timezone.utc)
    else:
     dt=datetime.datetime.fromisoformat(raw.replace('Z','+00:00').replace(' ','T'))
     if dt.tzinfo is None:dt=dt.replace(tzinfo=datetime.timezone.utc)
     if dt.utcoffset()!=datetime.timedelta(0):raise ValueError('Non UTC timestamps')
    bars.append({'datetime':dt.isoformat().replace('+00:00','Z'),'open':float(row[o]),'high':float(row[h]),'low':float(row[l]),'close':float(row[c])})
   if not bars:raise ValueError(f'{folder}: empty')
   result[frame]=sorted(bars,key=lambda x:x['datetime'])
 return {'source':'Dukascopy historical XAUUSD BID CSV via dukascopy-node, 2026-09-01 to 2026-10-01','symbol':'XAU/USD','frames':result}
if __name__=='__main__':
 try:
  output=convert(pathlib.Path(sys.argv[1]))
  pathlib.Path(sys.argv[2]).write_text(json.dumps(output))
  print('Imported', {k:len(v) for k,v in output['frames'].items()})
 except (ValueError,IndexError,OSError,KeyError) as e:
  print('IMPORT FAILED:',e,file=sys.stderr);sys.exit(1)
