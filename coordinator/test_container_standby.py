"""CI real Docker build and isolated standby/restart smoke. No provider key or network at runtime."""
import json,os,pathlib,secrets,subprocess,tempfile,time
ROOT=pathlib.Path(__file__).resolve().parent

def main():
 tag='gold-v3-standby:ci';cid=None
 subprocess.run(['docker','build','-f',str(ROOT/'Dockerfile'),'-t',tag,str(ROOT)],check=True)
 with tempfile.TemporaryDirectory() as d:
  tmp=pathlib.Path(d);data=tmp/'data';data.mkdir();(data/'gold-live').mkdir();envfile=tmp/'runtime.env';envfile.write_text('CUTOVER_MODE=standby\nDATA_DIR=/var/data/gold-live\nBROKER_PORT=3110\nBROKER_TOKEN='+secrets.token_urlsafe(40)+'\n');envfile.chmod(0o600)
  def start():
   return subprocess.check_output(['docker','run','-d','--network=none','--memory=512m','--cpus=0.5','--env-file',str(envfile),'--mount','type=bind,src='+str(data)+',dst=/var/data',tag],text=True).strip()
  def execute(code):return subprocess.check_output(['docker','exec','-i',cid,'python3','-'],input=code,text=True)
  probe='''import os,json,urllib.request,urllib.error
base='http://127.0.0.1:3110'
t=os.environ['BROKER_TOKEN']
def get(path):
 r=urllib.request.Request(base+path,headers={'Authorization':'Bearer '+t})
 try:
  with urllib.request.urlopen(r,timeout=2) as q:return q.status,json.load(q)
 except urllib.error.HTTPError as e:return e.code,json.load(e)
code,health=get('/health');assert code==200 and health=={'status':'standby','providerAccess':False,'paperRunning':False}
code,v3=get('/api/v3/research');assert code==503 and v3['signal']=='WAIT' and v3['dataStatus']=='STANDBY'
code,feed=get('/api/v3/eodhd/readiness');assert code==200 and feed['status']=='NOT_CONNECTED' and feed['signal']=='WAIT' and feed['executable'] is False and feed['providerAccess'] is False
assert feed['closedBarCounts']=={'M15':0,'H1':0,'H4':0} and feed['priceVisible'] is False
assert 'TWELVE_DATA_API_KEY' not in os.environ
import pathlib
assert not list(pathlib.Path('/var/data').rglob('*.sqlite3'))
for p in pathlib.Path('/proc').glob('[0-9]*/cmdline'):
 try:cmd=p.read_bytes()
 except OSError:continue
 assert not any(x in cmd for x in [b'broker_process.py',b'worker.py',b'supervise.py']),cmd
'''
  try:
   cid=start()
   for _ in range(40):
    try:execute(probe);break
    except subprocess.CalledProcessError:time.sleep(.25)
   else:raise RuntimeError('Standby readiness failed')
   host=json.loads(subprocess.check_output(['docker','inspect',cid],text=True))[0]['HostConfig'];assert host['Memory']==536870912 and host['NanoCpus']==500000000 and host['NetworkMode']=='none'
   # Test module loading from actual copied image filesystem without starting live API or worker.
   subprocess.run(['docker','exec',cid,'node','-e',"require('/app/v3_trade_plan'); console.log('PASS V3 dependency closure inside built image')"],check=True)
   execute("from pathlib import Path\np=Path('/var/data/gold-live');p.mkdir(exist_ok=True);(p/'standby-persistence-check').write_text('ok')")
   subprocess.run(['docker','restart',cid],check=True,stdout=subprocess.DEVNULL)
   for _ in range(40):
    try:execute(probe);break
    except subprocess.CalledProcessError:time.sleep(.25)
   else:raise RuntimeError('Restart readiness failed')
   execute("from pathlib import Path\nassert Path('/var/data/gold-live/standby-persistence-check').read_text()=='ok'")
   print('PASS actual Docker image; V3 imports; standby; provider disabled; no worker; 512MB/0.5CPU; bind-volume survives restart')
  finally:
   if cid:subprocess.run(['docker','rm','-f',cid],check=False,stdout=subprocess.DEVNULL)
if __name__=='__main__':main()
