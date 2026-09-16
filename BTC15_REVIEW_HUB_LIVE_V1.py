#!/usr/bin/env python3
"""BTC15 frozen review hub V1.

READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS

Aggregates independently fail-closed FINAL V4 and EARLY V1 review packets.
It never mixes their denominators and never creates a blended accuracy metric.
"""
from __future__ import annotations
import json, os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
import requests
import BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1 as final_review
import BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1 as early_review

VERSION="BTC15_REVIEW_HUB_LIVE_V1"
PORT=int(os.environ.get("PORT","8080"))
FINAL_URL=os.environ.get("BTC15_FINAL_V4_STATE_URL","https://final-forward-scorecard-v1-production.up.railway.app/state")
EARLY_URL=os.environ.get("BTC15_EARLY_V1_STATE_URL","https://early-forward-scorecard-v1-production.up.railway.app/state")
TIMEOUT=4.0

def _get(url:str)->dict[str,Any]:
    r=requests.get(url,timeout=TIMEOUT,headers={"Cache-Control":"no-cache","User-Agent":VERSION}); r.raise_for_status(); d=r.json()
    if not isinstance(d,dict): raise ValueError("upstream state is not an object")
    return d

def build_hub(final_payload:dict[str,Any],early_payload:dict[str,Any])->dict[str,Any]:
    f=final_review.build_report(final_payload); e=early_review.build_report(early_payload)
    return {"ok":bool(f["integrity"]["pass"] and e["integrity"]["pass"]),"version":VERSION,"final":f,"early":e,"review_ready":{"final":bool(f["frozen_gate"]["manual_review_ready"]),"early":bool(e["frozen_gate"]["manual_review_ready"])},"blended_accuracy":None,"union_coverage":None,"auto_promote_allowed":False,"threshold_retune_allowed":False,"numeric_flip_risk_validated":False,"manual_execution_only":True,"orders":False}

def collect_live()->dict[str,Any]: return build_hub(_get(FINAL_URL),_get(EARLY_URL))

def render_text(h:dict[str,Any])->str:
    return "=== BTC15 FROZEN REVIEW HUB ===\n"+f"Hub integrity: {'PASS' if h['ok'] else 'FAIL'}\n\n"+final_review.render_text(h["final"])+"\n"+early_review.render_text(h["early"])+"\nNo blended accuracy · no union claim · no auto-promotion · no orders\n"

class Handler(BaseHTTPRequestHandler):
    server_version="BTC15ReviewHubV1/1.0"
    def log_message(self,fmt,*args): print("BTC15_REVIEW_HUB_HTTP | "+(fmt%args),flush=True)
    def _json(self,code,obj):
        raw=json.dumps(obj,separators=(",",":"),default=str).encode(); self.send_response(code); self.send_header("Content-Type","application/json"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.send_header("X-Content-Type-Options","nosniff"); self.end_headers(); self.wfile.write(raw)
    def _text(self,code,text):
        raw=text.encode(); self.send_response(code); self.send_header("Content-Type","text/plain; charset=utf-8"); self.send_header("Content-Length",str(len(raw))); self.send_header("Cache-Control","no-store"); self.end_headers(); self.wfile.write(raw)
    def do_GET(self):
        path=urlparse(self.path).path
        try:
            h=collect_live(); code=200 if h["ok"] else 503
            if path=="/health": return self._json(code,{"ok":h["ok"],"version":VERSION,"final_integrity":h["final"]["integrity"],"early_integrity":h["early"]["integrity"],"review_ready":h["review_ready"],"orders":False})
            if path in {"/review","/reviews"}: return self._json(code,h)
            if path=="/review.txt": return self._text(code,render_text(h))
            if path=="/final": return self._json(200 if h["final"]["integrity"]["pass"] else 503,h["final"])
            if path=="/early": return self._json(200 if h["early"]["integrity"]["pass"] else 503,h["early"])
            return self._json(404,{"ok":False,"orders":False,"error":"not_found"})
        except Exception as exc: return self._json(503,{"ok":False,"version":VERSION,"fail_closed":True,"error":f"{type(exc).__name__}:{exc}","orders":False})
    def _reject(self): return self._json(405,{"ok":False,"error":"read_only_review_hub","orders":False})
    do_POST=do_PUT=do_PATCH=do_DELETE=_reject

def main():
    h=collect_live(); print(f"{VERSION} START | hub_integrity={h['ok']} | final={h['final']['status']} | early={h['early']['status']} | READ ONLY | NO ORDERS",flush=True); print(render_text(h),flush=True); ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever()
    return 0
if __name__=="__main__": raise SystemExit(main())
