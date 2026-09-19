#!/usr/bin/env python3
"""Single-owner BRTI WebSocket gateway V1. Read-only. SIGNAL ONLY. NO ORDERS."""
import asyncio,base64,json,math,os,threading,time,uuid
from collections import deque
from decimal import Decimal
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
import websockets
from cryptography.hazmat.primitives import hashes,serialization
from cryptography.hazmat.primitives.asymmetric import padding

WS="wss://external-api-ws.kalshi.com/trade-api/ws/v2"; PATH="/trade-api/ws/v2"
MAX_AGE_MS=5000; RING=deque(maxlen=3600); LOCK=threading.Lock()
STATE={"ready":False,"reason":"BOOTING","connected":False,"epoch":None,"sequence":0,"latest":None,"reconnects":0,"bad":0,"dup":0,"ooo":0,"orders":False,"signal_only":True}

KEY=os.environ["KALSHI_KEY_ID"].strip(); PRIV=serialization.load_pem_private_key(base64.b64decode(os.environ["KALSHI_PRIVATE_KEY_B64"].strip()),password=None)
def hdr():
 t=str(int(time.time()*1000));sig=PRIV.sign((t+"GET"+PATH).encode(),padding.PSS(mgf=padding.MGF1(hashes.SHA256()),salt_length=padding.PSS.DIGEST_LENGTH),hashes.SHA256())
 return {"KALSHI-ACCESS-KEY":KEY,"KALSHI-ACCESS-SIGNATURE":base64.b64encode(sig).decode(),"KALSHI-ACCESS-TIMESTAMP":t}
def snap():
 with LOCK:
  x=dict(STATE); latest=None if STATE["latest"] is None else dict(STATE["latest"])
 now=int(time.time()*1000);age=None if latest is None else now-latest["source_ts_ms"]
 x["latest"]=latest;x["source_age_ms"]=age
 x["ready"]=bool(x["connected"] and latest and age is not None and 0<=age<=MAX_AGE_MS and x["reason"]=="PRIMARY_OK")
 x["server_ts_ms"]=now;x["retained_ticks"]=len(RING);return x
def fail(reason):
 with LOCK: STATE["ready"]=False;STATE["connected"]=False;STATE["reason"]=reason
async def owner():
 backoff=1
 while True:
  epoch=str(uuid.uuid4())
  try:
   fail("CONNECTING")
   async with websockets.connect(WS,additional_headers=hdr(),ping_interval=20,ping_timeout=20,max_queue=4096) as ws:
    with LOCK: STATE["connected"]=True;STATE["epoch"]=epoch
    await ws.send(json.dumps({"id":1,"cmd":"subscribe","params":{"channels":["cfbenchmarks_value"],"index_ids":["BRTI"]}}))
    backoff=1
    while True:
     raw=await asyncio.wait_for(ws.recv(),timeout=15);recv=int(time.time()*1000);x=json.loads(raw)
     if x.get("type")=="error":raise RuntimeError("upstream_error")
     if x.get("type")!="cfbenchmarks_value":continue
     m=x.get("msg",{});d=json.loads(m.get("data","{}"))
     try: ts=int(d["time"]);v=Decimal(str(d["value"]))
     except Exception:
      with LOCK:STATE["bad"]+=1
      fail("INVALID_DATA");continue
     if m.get("index_id")!="BRTI" or d.get("id")!="BRTI" or not v.is_finite() or v<=0 or ts>recv+1000:
      with LOCK:STATE["bad"]+=1
      fail("INVALID_DATA");continue
     with LOCK:
      prev=STATE["latest"]
      if prev and ts==prev["source_ts_ms"]:STATE["dup"]+=1;continue
      if prev and ts<prev["source_ts_ms"]:STATE["ooo"]+=1;continue
      STATE["sequence"]+=1
      obs={"schema_version":1,"index_id":"BRTI","value":str(v),"source_ts_ms":ts,"receive_ts_ms":recv,"owner_epoch":epoch,"sequence":STATE["sequence"],"orders":False,"signal_only":True}
      RING.append(obs);STATE["latest"]=obs;STATE["reason"]="PRIMARY_OK";STATE["ready"]=True
  except Exception as exc:
   fail("UPSTREAM_DISCONNECTED")
   with LOCK:STATE["reconnects"]+=1
   print("BRTI_GATEWAY DISCONNECTED | %s | retry=%ss | WAIT | NO ORDERS"%(type(exc).__name__,backoff),flush=True)
   await asyncio.sleep(backoff);backoff=min(30,backoff*2)
class H(BaseHTTPRequestHandler):
 def sendj(self,code,obj):
  b=json.dumps(obj,separators=(",",":")).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Cache-Control","no-store");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def do_GET(self):
  path=self.path.split("?",1)[0]
  if path=="/health":return self.sendj(200,{"alive":True,"orders":False})
  if path=="/state":
   s=snap();return self.sendj(200,s)
  if path=="/ready":
   s=snap();return self.sendj(200 if s["ready"] else 503,s)
  if path=="/ticks":
   with LOCK:a=list(RING)
   return self.sendj(200,{"ticks":a,"orders":False,"signal_only":True})
  return self.sendj(404,{"error":"not_found"})
 def log_message(self,*a):pass
def main():
 threading.Thread(target=lambda:asyncio.run(owner()),daemon=True,name="brti-ws-owner").start()
 port=int(os.getenv("PORT","8080"));print("BRTI WS GATEWAY V1 START | ONE OWNER | 1H RING | FAIL CLOSED | NO ORDERS",flush=True)
 def heartbeat():
  while True:
   time.sleep(30);x=snap();print("BRTI_GATEWAY HEARTBEAT | ready=%s | reason=%s | age_ms=%s | seq=%s | retained=%s | epoch=%s | reconnects=%s | dup=%s | ooo=%s | bad=%s | NO ORDERS"%(x["ready"],x["reason"],x["source_age_ms"],x["sequence"],x["retained_ticks"],x["epoch"],x["reconnects"],x["dup"],x["ooo"],x["bad"]),flush=True)
 threading.Thread(target=heartbeat,daemon=True,name="brti-gateway-heartbeat").start()
 def consumer_proof():
  import subprocess,sys
  time.sleep(65)
  while True:
   p=subprocess.run([sys.executable,"-u","btc15_brti_gateway_loopback_proof_v1.py"],capture_output=True,text=True,timeout=5)
   print((p.stdout.strip() or ("BRTI_CONSUMER_LOOPBACK | pass=False | rc=%s | NO ORDERS"%p.returncode)),flush=True)
   time.sleep(60)
 threading.Thread(target=consumer_proof,daemon=True,name="brti-consumer-loopback-proof").start()
 def parity_shadow_proof():
  import subprocess,sys
  time.sleep(75)
  p=subprocess.run([sys.executable,"-u","test_btc15_kalshi_parity_shadow_gateway_v1_static.py"],capture_output=True,text=True,timeout=10)
  print((p.stdout.strip() or ("BRTI_PARITY_GATEWAY_SHADOW_STATIC_FAIL | rc=%s | NO ORDERS"%p.returncode)),flush=True)
 threading.Thread(target=parity_shadow_proof,daemon=True,name="brti-parity-shadow-static-proof").start()
 ThreadingHTTPServer(("0.0.0.0",port),H).serve_forever()
if __name__=="__main__":main()

