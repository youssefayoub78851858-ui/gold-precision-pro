"""Standby is the default; LIVE requires separate operator approval and handoff gates."""
import hmac,json,os,signal,threading,sys
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
pause_path=os.path.join(os.environ.get('DATA_DIR','/var/data/gold-live'),'PAUSE_LIVE')
mode='standby' if os.path.exists(pause_path) else os.environ.get('CUTOVER_MODE','standby')
if mode=='live':
 os.execv(sys.executable,[sys.executable,os.path.join(os.path.dirname(__file__),'supervise.py')])
if mode!='standby':raise SystemExit('Unknown CUTOVER_MODE')
token=os.environ.get('BROKER_TOKEN','')
if len(token)<32:raise SystemExit('Strong internal token required')
from eodhd_private_readiness import read_private_status
class Handler(BaseHTTPRequestHandler):
 def log_message(self,*_):pass
 def do_GET(self):
  authenticated=hmac.compare_digest(self.headers.get('Authorization','').encode(),('Bearer '+token).encode())
  health=authenticated and self.path=='/health'
  feed_ready=authenticated and self.path=='/api/v3/eodhd/readiness'
  status=401 if not authenticated else 200 if health or feed_ready else 503
  body={'status':'standby','providerAccess':False,'paperRunning':False} if health else {'status':'error','message':'Unauthorized' if not authenticated else 'Coordinator awaiting approved cutover'}
  if authenticated and self.path=='/api/v3/research':body={'engine':'V3','signal':'WAIT','executable':False,'dataStatus':'STANDBY','reason':'Coordinator in standby; provider access disabled'}
  if feed_ready:body=read_private_status(os.environ.get('DATA_DIR','/var/data/gold-live'))
  data=json.dumps(body).encode();self.send_response(status);self.send_header('Content-Type','application/json');self.send_header('Cache-Control','no-store');self.end_headers();self.wfile.write(data)
server=ThreadingHTTPServer(('0.0.0.0',int(os.environ.get('BROKER_PORT','3110'))),Handler)
signal.signal(signal.SIGTERM,lambda *_:threading.Thread(target=server.shutdown,daemon=True).start())
try:server.serve_forever()
finally:server.server_close()
