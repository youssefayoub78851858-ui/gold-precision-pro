"""Build consistent H1/H4 from actual M15 candles; reject partial groups."""
import collections,datetime,json,pathlib,sys
from validate_history import validate
def rebuild(doc):
 validate(doc)
 base=doc['frames']['15min']
 out={'15min':base}
 for name,minutes in [('1h',60),('4h',240)]:
  grouped=collections.defaultdict(list)
  for c in base:
   t=datetime.datetime.fromisoformat(c['datetime'].replace('Z','+00:00'))
   start=t.replace(hour=(t.hour//(minutes//60))*(minutes//60),minute=0,second=0,microsecond=0) if minutes>=60 else t
   grouped[start].append(c)
  rows=[]
  for start,items in sorted(grouped.items()):
   times=[datetime.datetime.fromisoformat(c['datetime'].replace('Z','+00:00')) for c in items]
   expected=[start+datetime.timedelta(minutes=15*i) for i in range(minutes//15)]
   if times!=expected:continue
   rows.append({'datetime':start.isoformat().replace('+00:00','Z'),'open':items[0]['open'],'high':max(c['high'] for c in items),'low':min(c['low'] for c in items),'close':items[-1]['close']})
  out[name]=rows
 result={'source':doc['source']+'; H1/H4 rebuilt from complete M15 groups only','symbol':doc['symbol'],'frames':out}
 validate(result)
 return result
if __name__=='__main__':
 source=json.loads(pathlib.Path(sys.argv[1]).read_text())
 output=rebuild(source)
 pathlib.Path(sys.argv[2]).write_text(json.dumps(output))
 print(json.dumps({'originalCounts':{k:len(v) for k,v in source['frames'].items()},'normalizedCounts':{k:len(v) for k,v in output['frames'].items()},'rule':'H1/H4 only complete M15 groups; no synthetic weekend candles'},indent=2))
