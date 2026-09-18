#!/usr/bin/env python3
"""Disk-backed private incremental evidence adapter V2.
Infrastructure only | READ ONLY | NO ORDERS.
Avoids retaining the complete source export in Python heap.
"""
from __future__ import annotations
import gc,hashlib,json,os,tempfile,threading,time
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import parse_qs,urlparse
import requests

PORT=int(os.environ.get("PORT","8080"))
SOURCE_URL=os.environ.get("SCALP_PATH_EXPORT_URL","http://scalp-move-shadow-v1.railway.internal:8080/research/path-export").strip()
TOKEN=(os.environ.get("SCALP_PATH_EXPORT_TOKEN","") or os.environ.get("PATH_EXPORT_TOKEN","")).strip()
POLL=max(30,int(os.environ.get("SCALP_INCREMENTAL_POLL_SEC","60")))
DATA=os.environ.get("SCALP_INCREMENTAL_FILE","/tmp/scalp_path_export.csv")
LOCK=threading.Lock()
STATE={"ok":False,"status":"STARTING","orders":False,"read_only":True}

def auth():
    h={"Cache-Control":"no-cache"}
    if TOKEN:h["Authorization"]="Bearer "+TOKEN
    return h

def refresh():
    # Stream canonical private export to disk; memory stays bounded by requests chunk size.
    fd,tmp=tempfile.mkstemp(prefix="scalp_path_",suffix=".tmp",dir=os.path.dirname(DATA) or "/tmp")
    os.close(fd); sha=hashlib.sha256(); n=0
    try:
        with requests.get(SOURCE_URL,headers=auth(),timeout=90,stream=True) as r:
            r.raise_for_status()
            with open(tmp,"wb") as f:
                for chunk in r.iter_content(chunk_size=1024*1024):
                    if chunk: f.write(chunk);sha.update(chunk);n+=len(chunk)
        # Trim incomplete tail if any.
        with open(tmp,"rb+") as f:
            if n:
                f.seek(max(0,n-65536));tail=f.read();pos=tail.rfind(bytes([10]))
                if pos<0: raise ValueError("no complete newline in tail")
                end=max(0,n-65536)+pos+1
                if end<n:f.truncate(end);n=end
        # Rehash exact committed bytes if truncated.
        h=hashlib.sha256();rows=-1
        with open(tmp,"rb") as f:
            head=f.read(4096)
            if b"record_type" not in head:raise ValueError("unexpected export")
            f.seek(0);rows=0
            for chunk in iter(lambda:f.read(1024*1024),b""):
                h.update(chunk);rows+=chunk.count(bytes([10]))
        os.replace(tmp,DATA)
        st={"ok":True,"status":"READY","bytes":n,"rows":max(0,rows-1),"sha256":h.hexdigest(),"updated":time.time(),"orders":False,"read_only":True}
        with LOCK:STATE.clear();STATE.update(st)
        print("SCALP_INCREMENTAL_DISK | "+json.dumps(st,separators=(",",":")),flush=True)
        for name in ("tail","head","chunk"):
            if name in locals(): del locals()[name]
        gc.collect()
    finally:
        if os.path.exists(tmp):
            try:os.unlink(tmp)
            except OSError:pass

def worker():
    while True:
        try:refresh()
        except Exception as exc:
            with LOCK:STATE.update({"ok":False,"status":"ERROR_RETRYING","error":f"{type(exc).__name__}:{exc}","orders":False})
        time.sleep(POLL)

class H(BaseHTTPRequestHandler):
    def log_message(self,*a):return
    def j(self,code,obj):
        raw=json.dumps(obj,separators=(",",":")).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(raw)));self.end_headers();self.wfile.write(raw)
    def do_GET(self):
        u=urlparse(self.path)
        if u.path=="/health":
            with LOCK:x=dict(STATE)
            return self.j(200,x)
        if u.path=="/research/path-manifest":
            with LOCK:x=dict(STATE)
            return self.j(200 if x.get("ok") else 503,x)
        if u.path=="/research/path-delta":
            q=parse_qs(u.query);start=int(q.get("offset",["0"])[0]);cap=min(4*1024*1024,max(1,int(q.get("max_bytes",[str(4*1024*1024)])[0])))
            with LOCK:meta=dict(STATE)
            size=int(meta.get("bytes",0))
            if start<0 or start>size:return self.j(409,{"ok":False,"error":"invalid_offset","size":size,"orders":False})
            with open(DATA,"rb") as f:
                f.seek(start);chunk=f.read(cap)
                if start+len(chunk)<size:
                    p=chunk.rfind(bytes([10]));chunk=b"" if p<0 else chunk[:p+1]
            end=start+len(chunk);self.send_response(200);self.send_header("Content-Type","application/octet-stream");self.send_header("Content-Length",str(len(chunk)));self.send_header("X-Start-Offset",str(start));self.send_header("X-End-Offset",str(end));self.send_header("X-Chunk-SHA256",hashlib.sha256(chunk).hexdigest());self.send_header("X-Source-Size",str(size));self.send_header("X-Source-SHA256",str(meta.get("sha256","")));self.end_headers();self.wfile.write(chunk);return
        return self.j(404,{"ok":False,"orders":False})
    def do_POST(self):return self.j(405,{"ok":False,"orders":False,"error":"read_only"})
    do_PUT=do_POST;do_PATCH=do_POST;do_DELETE=do_POST

if __name__=="__main__":
    threading.Thread(target=worker,daemon=True).start()
    ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
