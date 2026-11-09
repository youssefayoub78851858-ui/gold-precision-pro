"""Own one local stack; restart by the host after a failed child. Never creates resources."""
import argparse,fcntl,json,os,pathlib,secrets,signal,subprocess,sys,threading,time,urllib.request
ROOT=pathlib.Path(__file__).parent;STOP=threading.Event()
def child_environment(name,base):
 child=dict(base)
 if name!='broker':child.pop('TWELVE_DATA_API_KEY',None)
 # Recorded input may reach ONLY a broker explicitly started in recorded-replay mode.
 if name!='broker' or child.get('PAPER_DATA_MODE')!='recorded_replay':child.pop('REPLAY_SNAPSHOT',None)
 return child
def main():
 started=time.monotonic()
 parser=argparse.ArgumentParser();parser.add_argument('--replay');parser.add_argument('--smoke',action='store_true');args=parser.parse_args()
 data=pathlib.Path(os.environ.get('DATA_DIR',ROOT/'runtime'));data.mkdir(parents=True,exist_ok=True)
 token=os.environ.get('BROKER_TOKEN') or (secrets.token_urlsafe(32) if args.replay else None)
 if not token or len(token)<32:raise RuntimeError('Configure a strong broker token via secrets')
 env={**os.environ,'DATA_DIR':str(data),'BROKER_TOKEN':token,'BROKER_PORT':os.environ.get('BROKER_PORT','3110'),'PORT':os.environ.get('LOCAL_API_PORT','3111'),'PYTHONUNBUFFERED':'1'}
 env['MARKET_DATA_BROKER_URL']='http://127.0.0.1:'+env['BROKER_PORT'];env['CANDLES_URL']='http://127.0.0.1:'+env['PORT']+'/api/candles'
 env['PAPER_DATA_MODE']='recorded_replay' if args.replay else 'readonly_live'
 if args.replay:env['REPLAY_SNAPSHOT']=str(pathlib.Path(args.replay).resolve());env.pop('TWELVE_DATA_API_KEY',None)
 children={};logs=[];exit_code=0
 def emit(kind,**values):
  with (data/'supervisor-events.jsonl').open('a') as out:out.write(json.dumps({'type':kind,'observedMS':int(time.time()*1000),'recordedReplay':bool(args.replay),**values})+'\n')
 def start(name,cmd):
  out=(data/(name+'.log')).open('a');logs.append(out);children[name]=subprocess.Popen(cmd,env=child_environment(name,env),stdin=subprocess.DEVNULL,stdout=out,stderr=subprocess.STDOUT)
 def wait_ready(url,auth=False):
  until=time.monotonic()+15
  while time.monotonic()<until and not STOP.is_set():
   if any(p.poll() is not None for p in children.values()):raise RuntimeError('Child exited during startup')
   try:
    request=urllib.request.Request(url,headers={'Authorization':'Bearer '+token} if auth else {})
    with urllib.request.urlopen(request,timeout=1) as response:
     if response.status==200:return
   except OSError:pass
   STOP.wait(.1)
  raise RuntimeError('Readiness timeout')
 with (data/'stack.lock').open('w') as lock:
  fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
  try:
   emit('STACK_START');start('broker',[sys.executable,str(ROOT/'broker_process.py')]);wait_ready(env['MARKET_DATA_BROKER_URL']+'/health',True)
   start('api',['node',str(ROOT/'service/server.js')]);wait_ready('http://127.0.0.1:'+env['PORT']+'/health')
   command=[sys.executable,str(ROOT/'app/worker.py')]+(['--once'] if args.smoke else [])
   start('paper',command)
   if os.environ.get('LIVE_ACCEPTANCE_RECORDING')=='1':start('acceptance',[sys.executable,str(ROOT/'acceptance_watch.py'),'--db',str(data/'monitor.sqlite3'),'--output',str(data/'live-acceptance.jsonl')])
   while not STOP.is_set():
    if (data/'PAUSE_LIVE').exists():emit('OPERATOR_PAUSE');break
    codes={name:p.poll() for name,p in children.items()}
    if args.smoke and codes.get('paper')==0:emit('SMOKE_COMPLETE');break
    failed=[name for name,code in codes.items() if code is not None]
    if failed:emit('CHILD_EXIT',children=failed,codes={name:codes[name] for name in failed});exit_code=1;break
    heartbeat=data/'heartbeat.json'
    if heartbeat.exists() and time.monotonic()-started>120 and time.time()-heartbeat.stat().st_mtime>120:emit('HEARTBEAT_STALE');exit_code=1;break
    if not args.smoke and not heartbeat.exists() and time.monotonic()-started>120:emit('HEARTBEAT_MISSING');exit_code=1;break
    temp=data/'stack-health.tmp';temp.write_text(json.dumps({'observedMS':int(time.time()*1000),'processesAlive':list(children),'paperOnly':True}));os.replace(temp,data/'stack-health.json')
    STOP.wait(.2)
  except BaseException as exc:emit('STACK_ERROR',errorType=type(exc).__name__);exit_code=1
  finally:
   for p in reversed(list(children.values())):
    if p.poll() is None:p.terminate()
   deadline=time.monotonic()+25
   for p in children.values():
    try:p.wait(timeout=max(.1,deadline-time.monotonic()))
    except subprocess.TimeoutExpired:p.kill();p.wait()
   for out in logs:out.close()
   emit('STACK_STOP',exitCode=exit_code)
 return exit_code
if __name__=='__main__':
 for sig in [signal.SIGTERM,signal.SIGINT]:signal.signal(sig,lambda *_:STOP.set())
 started=time.monotonic();raise SystemExit(main())
