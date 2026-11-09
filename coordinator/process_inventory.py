"""Never emits command lines, arguments or environment values."""
import os,pathlib
def monitors():
 result=[]
 for proc in pathlib.Path('/proc').iterdir():
  if not proc.name.isdigit():continue
  try:
   args=(proc/'cmdline').read_bytes().split(b'\0')
   if len(args)<2 or not pathlib.Path(args[0].decode()).name.startswith('python'):continue
   script=pathlib.Path(args[1].decode());name=script.name
   if name not in ['monitor.py','worker.py','supervise.py']:continue
   if not (str(script).startswith('/workspace/gold-') or str(script).startswith(str(pathlib.Path(__file__).parent)+'/')):continue
   state=(proc/'stat').read_text().split(') ')[1].split()[0]
   if state=='Z':continue
   result.append({'pid':int(proc.name),'script':str(script),'state':state})
  except (OSError,ValueError,UnicodeError):continue
 return result
def refuse_competing():
 # A starting broker may have exactly its own supervisor, but no existing paper worker.
 parent=os.getppid();others=[p for p in monitors() if p['pid']!=parent]
 if others:raise RuntimeError('Existing paper monitor or stack must be stopped and checkpointed before live handoff')
 return True
if __name__=='__main__':
 import json
 print(json.dumps({'activeMonitors':monitors(),'continuousMonitoringAssumed':False},indent=2))
