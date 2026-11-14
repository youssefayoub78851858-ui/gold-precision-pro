"""Standby is the default; LIVE requires separate operator approval and handoff gates."""
import hmac,json,os,signal,threading,sys
import datetime
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
pause_path=os.path.join(os.environ.get('DATA_DIR','/var/data/gold-live'),'PAUSE_LIVE')
mode='standby' if os.path.exists(pause_path) else os.environ.get('CUTOVER_MODE','standby')
if mode=='live':
 os.execv(sys.executable,[sys.executable,os.path.join(os.path.dirname(__file__),'supervise.py')])
if mode!='standby':raise SystemExit('Unknown CUTOVER_MODE')
token=os.environ.get('BROKER_TOKEN','')
if len(token)<32:raise SystemExit('Strong internal token required')
from eodhd_private_readiness import read_private_status
from eodhd_review_monitor import poll_private_review
from private_review_watchdog import read_audit_state,run_until_stopped
from paper_admission_gate import assess_paper_gate
from fxcm_mobile_readiness import read_fxcm_review_status
from private_eodhd_worker import launch_review_worker,stop_review_worker
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*_):pass
 def do_GET(self):
  if self.path=='/api/v3/monitor/dashboard':
   page=os.path.join(os.path.dirname(__file__),'private_mobile_dashboard.html')
   with open(page,'rb') as f:data=f.read()
   self.send_response(200);self.send_header('Content-Type','text/html; charset=utf-8')
   self.send_header('Cache-Control','no-store')
   self.send_header('Content-Security-Policy',"default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'; connect-src 'self'; base-uri 'none'; frame-ancestors 'none'; form-action 'none'")
   self.send_header('X-Content-Type-Options','nosniff')
   self.send_header('Referrer-Policy','no-referrer')
   self.end_headers();self.wfile.write(data);return
  authenticated=hmac.compare_digest(self.headers.get('Authorization','').encode(),('Bearer '+token).encode())
  health=authenticated and self.path=='/health'
  feed_ready=authenticated and self.path=='/api/v3/eodhd/readiness'
  monitor_ready=authenticated and self.path=='/api/v3/monitor/status'
  viewer_secret=os.environ.get('MONITOR_READONLY_TOKEN','')
  viewer_authorized=(self.path=='/api/v3/monitor/status'
    and len(viewer_secret)>=32 and not hmac.compare_digest(viewer_secret,token)
    and hmac.compare_digest(self.headers.get('X-Monitor-Viewer','').encode(),viewer_secret.encode()))
  status=401 if not (authenticated or viewer_authorized) else 200 if health or feed_ready or monitor_ready or viewer_authorized else 503
  body={'status':'standby','providerAccess':False,'paperRunning':False} if health else {'status':'error','message':'Unauthorized' if not authenticated else 'Coordinator awaiting approved cutover'}
  if authenticated and self.path=='/api/v3/research':body={'engine':'V3','signal':'WAIT','executable':False,'dataStatus':'STANDBY','reason':'Coordinator in standby; provider access disabled'}
  if feed_ready:body=read_private_status(os.environ.get('DATA_DIR','/var/data/gold-live'))
  if monitor_ready or viewer_authorized:
   now=datetime.datetime.now(datetime.timezone.utc)
   body=poll_private_review(audit_root,now)
   body['audit']=read_audit_state(audit_root,now,enabled=audit_enabled)
   body['paperGate']=assess_paper_gate(body,body['audit'])
   body['fxcmReview']=read_fxcm_review_status()
  data=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
audit_root=os.environ.get('DATA_DIR','/var/data/gold-live')
audit_enabled=os.environ.get('PRIVATE_REVIEW_AUDIT_ENABLED')=='1'
audit_stop=threading.Event()
server=ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('BROKER_PORT','3110'))),Handler)
if audit_enabled:
 threading.Thread(target=run_until_stopped,args=(audit_root,audit_stop),
                  daemon=True,name='private-review-audit').start()
# Explicitly disabled unless private review worker, source rights, connection and
# credentials are approved. Never auto-connect because a token already exists.
try:
 eodhd_worker=launch_review_worker(audit_root,mode=mode)
except (OSError,ValueError) as error:
 eodhd_worker=None
 print('EODHD private review worker blocked by local preflight',flush=True)
def shutdown(*_):
 audit_stop.set()
 threading.Thread(target=server.shutdown,daemon=True).start()
signal.signal(signal.SIGTERM,shutdown)
try:server.serve_forever()
finally:
 audit_stop.set()
 stop_review_worker(eodhd_worker)
 server.server_close()
