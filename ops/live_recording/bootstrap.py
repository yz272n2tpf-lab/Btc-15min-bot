"""Owner-process opt-in. Recorder failure cannot terminate a native process."""
import atexit,json,os,sys
from pathlib import Path
ACTIVE=None;ACTIVE_ADAPTER=None
def start(role):
 global ACTIVE,ACTIVE_ADAPTER
 if os.getenv('BTC15_RECORDING_ENABLED')!='1':return None
 try:
  from .policy import sha,need,attest,validate
  raw=Path(os.environ['BTC15_RECORDING_CONFIG']).read_bytes()
  need(len(raw)<=65536 and sha(raw)==os.environ.get('BTC15_RECORDING_CONFIG_SHA256'),'CONFIG_HASH')
  c=json.loads(raw);validate(c,role)
  receipt=attest(Path(__file__).resolve().parents[2],c,role)
  from .capture import Capture
  from .adapters import install
  ACTIVE=Capture(c,role,attestation=receipt);ACTIVE_ADAPTER=install(ACTIVE)
  atexit.register(ACTIVE.stop,'PROCESS_EXIT')
  return ACTIVE
 except Exception as e:
  print('BTC15 RECORDER DISABLED | '+type(e).__name__+': '+str(e)[:180],file=sys.stderr,flush=True)
  if ACTIVE:
   ACTIVE.failure='BOOTSTRAP_FAILURE';ACTIVE.stop('BOOTSTRAP_FAILURE')
  return None
