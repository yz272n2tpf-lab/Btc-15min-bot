#!/usr/bin/env python3
"""Live read-only host for qualified recovered V11/V13 preview. NO ORDERS."""
from __future__ import annotations
import json,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlparse
import requests
import BTC15_RECOVERED_V11_FINAL_PROBABILITY_V1 as candidate

PORT=int(os.environ.get("PORT","8080"))
MAIN="https://btc-15min-bot-production.up.railway.app"
SCALP="https://scalp-display-bridge-v6-production.up.railway.app"
VERSION="BTC15_RECOVERED_V11_LIVE_HOST_V1"
HTML=b""

def get(url,headers=None):
    r=requests.get(url,timeout=3.0,headers={"Cache-Control":"no-cache",**(headers or {})})
    r.raise_for_status();return r

def load():
    global HTML
    p=candidate.build_dashboard();HTML=p.read_bytes()
    required=(b"BTC15_RECOVERED_V11_FINAL_PROBABILITY_V2",b"BTC15_RECOVERED_V11_INFORMATION_SEAM_V1",b"SIGNAL ONLY")
    if not all(x in HTML for x in required):raise RuntimeError("qualified recovered artifact markers missing")
    return p

class H(BaseHTTPRequestHandler):
    def log_message(self,fmt,*args):print("RECOVERED_LIVE_HTTP | "+fmt%args,flush=True)
    def hdr(self,code,ctype,n=None,nonce=None):
        self.send_response(code);self.send_header("Content-Type",ctype);self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.send_header("Access-Control-Allow-Origin","*")
        if nonce:self.send_header("X-BTC15-Information-Nonce",nonce)
        if n is not None:self.send_header("Content-Length",str(n))
        self.end_headers()
    def js(self,code,obj):
        raw=json.dumps(obj,separators=(",",":")).encode();self.hdr(code,"application/json",len(raw));self.wfile.write(raw)
    def proxy_json(self,url):
        try:
            r=get(url);json.loads(r.content.decode());self.hdr(200,"application/json",len(r.content));self.wfile.write(r.content)
        except Exception as e:self.js(503,{"ok":False,"orders":False,"error":"upstream_unavailable:"+type(e).__name__})
    def do_GET(self):
        path=urlparse(self.path).path
        if path in ("/","/index.html","/BTC_Kalshi_App_Live_v13.html"):
            self.hdr(200,"text/html; charset=utf-8",len(HTML));self.wfile.write(HTML);return
        if path=="/dashboard_state.json":return self.proxy_json(MAIN+"/dashboard_state.json")
        if path=="/combined-state":return self.proxy_json(SCALP+"/combined-state")
        if path in ("/information","/information/identity"):
            nonce=self.headers.get("X-BTC15-Information-Nonce")
            if not nonce:return self.js(400,{"ok":False,"orders":False,"error":"nonce_required"})
            try:
                r=get(MAIN+path,{"X-BTC15-Information-Nonce":nonce})
                if r.headers.get("X-BTC15-Information-Nonce")!=nonce:raise RuntimeError("nonce_mismatch")
                json.loads(r.content.decode());self.hdr(200,"application/json",len(r.content),nonce);self.wfile.write(r.content)
            except Exception as e:self.js(503,{"ok":False,"orders":False,"error":"information_unavailable:"+type(e).__name__})
            return
        if path=="/health":return self.js(200,{"ok":bool(HTML),"version":VERSION,"shadow_only":True,"orders":False,"main_proxy":True,"information_proxy":True,"scalp_proxy":True})
        self.js(404,{"ok":False,"orders":False,"error":"not_found"})
    def reject(self):self.js(405,{"ok":False,"orders":False,"error":"read_only_preview"})
    do_POST=reject;do_PUT=reject;do_PATCH=reject;do_DELETE=reject

def main():
    p=load();print(f"{VERSION} START | {p} | READ ONLY | SIGNAL ONLY | NO ORDERS",flush=True)
    ThreadingHTTPServer(("0.0.0.0",PORT),H).serve_forever()
if __name__=="__main__":main()
