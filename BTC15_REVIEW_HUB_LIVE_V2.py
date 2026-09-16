#!/usr/bin/env python3
"""BTC15 frozen review hub V2 — FINAL, EARLY, handoff, excursion.
READ ONLY | SIGNAL ONLY | MANUAL EXECUTION | NO ORDERS
"""
from __future__ import annotations
import json,os
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from typing import Any
from urllib.parse import urlparse
import requests
import BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1 as final_review
import BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1 as early_review
import BTC15_HANDOFF_V1_FROZEN_REVIEW_REPORT_V1 as handoff_review
import BTC15_EARLY_EXCURSION_V1_FROZEN_REVIEW_REPORT_V1 as excursion_review
VERSION="BTC15_REVIEW_HUB_LIVE_V2";PORT=int(os.environ.get("PORT","8080"));TIMEOUT=4.0
FINAL_URL=os.environ.get("BTC15_FINAL_V4_STATE_URL","https://final-forward-scorecard-v1-production.up.railway.app/state")
EARLY_URL=os.environ.get("BTC15_EARLY_V1_STATE_URL","https://early-forward-scorecard-v1-production.up.railway.app/state")
HANDOFF_URL=os.environ.get("BTC15_HANDOFF_V1_STATE_URL","http://early-final-handoff-v1.railway.internal:8080/state")
EXCURSION_URL=os.environ.get("BTC15_EXCURSION_V1_STATE_URL","http://early-excursion-forward-v1.railway.internal:8080/state")
def _get(url):
    r=requests.get(url,timeout=TIMEOUT,headers={"Cache-Control":"no-cache","User-Agent":VERSION});r.raise_for_status();d=r.json()
    if not isinstance(d,dict):raise ValueError(f"non-object upstream:{url}")
    return d
def build_hub(final_payload,early_payload,handoff_payload,excursion_payload):
    f=final_review.build_report(final_payload);e=early_review.build_report(early_payload);h=handoff_review.build_report(handoff_payload);x=excursion_review.build_report(excursion_payload); ok=all(q["integrity"]["pass"] for q in (f,e,h,x))
    return {"ok":ok,"version":VERSION,"final":f,"early":e,"handoff":h,"excursion":x,"review_ready":{"final":f["frozen_gate"]["manual_review_ready"],"early":e["frozen_gate"]["manual_review_ready"],"handoff":h["frozen_gate"]["manual_review_ready"],"excursion":x["frozen_gate"]["manual_review_ready"]},"system":{"union_coverage":h["common_universe"]["any_signal_coverage"],"union_coverage_certified":h["common_universe"]["union_coverage_certified"],"union_source":"HANDOFF_COMMON_UNIVERSE_ONLY","blended_accuracy":None},"numeric_flip_risk":None,"auto_promote_allowed":False,"threshold_retune_allowed":False,"manual_execution_only":True,"orders":False}
def collect_live():return build_hub(_get(FINAL_URL),_get(EARLY_URL),_get(HANDOFF_URL),_get(EXCURSION_URL))
def render_text(z):return "=== BTC15 FROZEN REVIEW HUB V2 ===\n"+f"Hub integrity: {'PASS' if z['ok'] else 'FAIL'}\n\n"+final_review.render_text(z["final"])+"\n"+early_review.render_text(z["early"])+"\n"+handoff_review.render_text(z["handoff"])+"\n"+excursion_review.render_text(z["excursion"])+"\nSystem union source: HANDOFF COMMON UNIVERSE ONLY\nNo blended accuracy · numeric Flip Risk hidden · no auto-promotion · no orders\n"
class Handler(BaseHTTPRequestHandler):
    server_version="BTC15ReviewHubV2/1.0"
    def log_message(self,fmt,*args):print("BTC15_REVIEW_HUB_V2_HTTP | "+(fmt%args),flush=True)
    def _json(self,code,obj):
        b=json.dumps(obj,separators=(",",":"),default=str).encode();self.send_response(code);self.send_header("Content-Type","application/json");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.send_header("X-Content-Type-Options","nosniff");self.end_headers();self.wfile.write(b)
    def _text(self,code,text):
        b=text.encode();self.send_response(code);self.send_header("Content-Type","text/plain; charset=utf-8");self.send_header("Content-Length",str(len(b)));self.send_header("Cache-Control","no-store");self.end_headers();self.wfile.write(b)
    def do_GET(self):
        path=urlparse(self.path).path
        try:
            z=collect_live();code=200 if z["ok"] else 503
            if path=="/health":return self._json(code,{"ok":z["ok"],"version":VERSION,"review_ready":z["review_ready"],"integrity":{k:z[k]["integrity"] for k in ("final","early","handoff","excursion")},"orders":False})
            if path in {"/review","/reviews"}:return self._json(code,z)
            if path=="/review.txt":return self._text(code,render_text(z))
            for p,k in (("/final","final"),("/early","early"),("/handoff","handoff"),("/excursion","excursion")):
                if path==p:return self._json(200 if z[k]["integrity"]["pass"] else 503,z[k])
            return self._json(404,{"ok":False,"orders":False,"error":"not_found"})
        except Exception as exc:return self._json(503,{"ok":False,"version":VERSION,"fail_closed":True,"error":f"{type(exc).__name__}:{exc}","orders":False})
    def _reject(self):return self._json(405,{"ok":False,"error":"read_only_review_hub","orders":False})
    do_POST=do_PUT=do_PATCH=do_DELETE=_reject
def main():
    z=collect_live();print(f"{VERSION} START | integrity={z['ok']} | FINAL={z['final']['status']} | EARLY={z['early']['status']} | HANDOFF={z['handoff']['status']} | EXCURSION={z['excursion']['status']} | READ ONLY | NO ORDERS",flush=True);print(render_text(z),flush=True);ThreadingHTTPServer(("0.0.0.0",PORT),Handler).serve_forever();return 0
if __name__=="__main__":raise SystemExit(main())
