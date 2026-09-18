#!/usr/bin/env python3
"""Read-only incremental adapter for the existing scalp path export.
DEPLOY_TRIGGER_20260918: source-branch deployment handshake.
DEPLOY_TRIGGER_TOKEN_REF: apply Railway reference variable.
Infrastructure only. Does not change producer, strategy, cutoffs, or orders.
"""
from __future__ import annotations
import hashlib, json, os, threading, time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse
import requests

PORT=int(os.environ.get("PORT","8080"))
SOURCE_URL=os.environ.get("SCALP_PATH_EXPORT_URL","http://scalp-move-shadow-v1.railway.internal:8080/research/path-export").strip()
TOKEN=os.environ.get("SCALP_PATH_EXPORT_TOKEN","").strip()
# Private Railway traffic is already isolated; when no adapter token is injected,
# authenticate to the existing producer with the producer-compatible internal header only if available.
INTERNAL_TOKEN=os.environ.get("PATH_EXPORT_TOKEN","").strip()
POLL=max(15,int(os.environ.get("SCALP_INCREMENTAL_POLL_SEC","30")))
LOCK=threading.Lock()
STATE={"ok":False,"status":"STARTING","orders":False,"read_only":True}
BODY=b""
GEN=""
SOURCE_PREFIX_SHA=""

def fetch():
    h={"Cache-Control":"no-cache"}
    tok=TOKEN or INTERNAL_TOKEN
    if tok: h["Authorization"]="Bearer "+tok
    r=requests.get(SOURCE_URL,headers=h,timeout=45); r.raise_for_status()
    raw=r.content
    if not raw or b"record_type" not in raw[:4096]: raise ValueError("unexpected export")
    # Expose only complete newline-terminated bytes.
    end=raw.rfind(bytes([10]))
    if end<0: raise ValueError("no complete rows")
    body=raw[:end+1]
    return body

def cycle():
    global BODY,GEN,SOURCE_PREFIX_SHA
    raw=fetch()
    sha=hashlib.sha256(raw).hexdigest()\n    SOURCE_PREFIX_SHA=sha
    header=raw.splitlines()[0]
    gen=hashlib.sha256(header).hexdigest()
    rows=max(0,raw.count(bytes([10]))-1)
    with LOCK:
        BODY=raw; GEN=gen
        STATE.update({"ok":True,"status":"READY","bytes":len(raw),"rows":rows,
                      "sha256":sha,"generation":gen,"updated":time.time(),
                      "orders":False,"read_only":True})
    print(f"SCALP_INCREMENTAL | bytes={len(raw)} rows={rows} sha={sha} | READ ONLY | NO ORDERS",flush=True)

def worker():
    while True:
        try: cycle()
        except Exception as exc:
            with LOCK: STATE.update({"ok":False,"status":"ERROR_RETRYING","error":f"{type(exc).__name__}:{exc}","orders":False})
        time.sleep(POLL)

class H(BaseHTTPRequestHandler):
    def log_message(self,*a): return
    def sendj(self,code,obj):
        raw=json.dumps(obj,separators=(",",":")).encode(); self.send_response(code)
        self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(raw)))
        self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=="/health":
            with LOCK: x=dict(STATE)
            return self.sendj(200,x)
        if u.path=="/research/path-manifest":
            with LOCK: x=dict(STATE)
            return self.sendj(200 if x.get("ok") else 503,x)
        if u.path=="/research/path-delta":
            q=parse_qs(u.query); start=int(q.get("offset",["0"])[0]); cap=min(4*1024*1024,max(1,int(q.get("max_bytes",[str(4*1024*1024)])[0])))
            with LOCK: raw=BODY; gen=GEN
            if start<0 or start>len(raw): return self.sendj(409,{"ok":False,"error":"invalid_offset","generation":gen,"size":len(raw),"orders":False})
            stop=min(len(raw),start+cap)
            if stop<len(raw):
                nl=raw.rfind(bytes([10]),start,stop+1); stop=start if nl<start else nl+1
            chunk=raw[start:stop]
            self.send_response(200); self.send_header("Content-Type","application/octet-stream")
            self.send_header("Content-Length",str(len(chunk))); self.send_header("X-Generation",gen)
            self.send_header("X-Start-Offset",str(start)); self.send_header("X-End-Offset",str(stop))
            self.send_header("X-Chunk-SHA256",hashlib.sha256(chunk).hexdigest()); self.send_header("X-Source-Size",str(len(raw)))
            self.end_headers(); self.wfile.write(chunk); return
        return self.sendj(404,{"ok":False,"orders":False,"error":"not_found"})
    def do_POST(self): return self.sendj(405,{"ok":False,"orders":False,"error":"read_only"})
    do_PUT=do_POST; do_PATCH=do_POST; do_DELETE=do_POST

if __name__=="__main__":
    threading.Thread(target=worker,daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
