#!/usr/bin/env python3
"""Tiny supervisor for one-shot scalp research worker. NO ORDERS."""
import json,os,subprocess,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
PORT=int(os.getenv("PORT","8080"));INTERVAL=max(300,int(os.getenv("SCALP_UNARMED_ANALYSIS_INTERVAL_SEC","900")))
LOCK=threading.Lock();STATE={"ok":True,"status":"SUPERVISOR_STARTING","orders":False,"research_only":True,"worker_running":False}
def loop():
 while True:
  with LOCK:STATE["worker_running"]=True;STATE["status"]="ANALYZING"
  try:
   p=subprocess.run(["python","-u","btc15_scalp_unarmed_analysis_once_v1.py"],capture_output=True,text=True,timeout=840,check=True)
   j=json.loads(p.stdout.strip().splitlines()[-1]);j["worker_running"]=False;j["orders"]=False
   with LOCK:STATE.clear();STATE.update(j)
  except Exception as e:
   with LOCK:STATE.update({"ok":False,"status":"WORKER_ERROR","last_error":type(e).__name__,"worker_running":False,"orders":False,"research_only":True})
  time.sleep(INTERVAL)
class H(BaseHTTPRequestHandler):
 def log_message(self,*a):return
 def do_GET(self):
  with LOCK:b=json.dumps(STATE,separators=(",",":")).encode()
  self.send_response(200);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.end_headers();self.wfile.write(b)
 def bad(self):
  self.send_response(405);self.end_headers()
 do_POST=bad;do_PUT=bad;do_PATCH=bad;do_DELETE=bad
def main():
 srv=ThreadingHTTPServer(("0.0.0.0",PORT),H);threading.Thread(target=srv.serve_forever,daemon=True).start();threading.Thread(target=loop,daemon=True).start()
 print("SCALP UNARMED SUPERVISOR V1 | SHORT-LIVED HEAVY WORKER | NO ORDERS",flush=True)
 while True:time.sleep(3600)
if __name__=="__main__":main()
