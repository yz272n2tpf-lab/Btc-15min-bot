#!/usr/bin/env python3
"""
BTC15 combined dashboard state bridge V3.

READ ONLY | SIGNAL ONLY | NO ORDERS

Uses the actual nested protected-main dashboard schema discovered by the
key-only schema probe. Exposes /state and /combined-state and emits a read-only
1-second live observer. Protected EARLY/FINAL outputs are adapted, not rebuilt.
Generalized SCALP stays freshness + contract fail-closed.
"""
from __future__ import annotations

import json
import runpy
import threading
import time
from http.server import ThreadingHTTPServer
from typing import Any, Mapping
from urllib.parse import urlparse

import requests

import scalp_path_export_bridge_v1 as base
import scalp_integration_state_bridge_v4 as scalp_v4
from btc15_cross_service_payload_v4 import compose_cross_service_payload

MAIN_STATE_URL = "https://btc-15min-bot-production.up.railway.app/dashboard_state.json"
VERSION = "BTC15_COMBINED_STATE_BRIDGE_V3"
POLL_SEC = 1.0
HEARTBEAT_SEC = 30.0


def unwrap_main_state(obj: Any) -> Mapping[str, Any]:
    if not isinstance(obj, Mapping):
        raise ValueError("main dashboard state is not a JSON object")
    if obj.get("contract"):
        return obj
    for key in ("state", "data"):
        nested = obj.get(key)
        if isinstance(nested, Mapping) and nested.get("contract"):
            return nested
    raise ValueError("main dashboard state has no contract")


def fetch_main_state() -> Mapping[str, Any]:
    r=requests.get(MAIN_STATE_URL,timeout=3.0,headers={"Cache-Control":"no-cache"})
    r.raise_for_status()
    return unwrap_main_state(r.json())


def build_combined_state(main_state: Mapping[str, Any],rows,*,now=None) -> dict:
    scalp=scalp_v4.build_state(rows,now=now)
    combined=compose_cross_service_payload(main_state,scalp).to_dict()
    combined["version"]=VERSION
    combined["scalp_bridge_version"]=scalp.get("version")
    combined["manual_execution_only"]=True
    combined["order_action"]=None
    combined["numeric_flip_risk_validated"]=False
    combined["orders"]=False
    return combined


def _json_response(handler,code,obj):
    raw=json.dumps(obj,separators=(",",":")).encode()
    handler.send_response(code)
    handler.send_header("Content-Type","application/json")
    handler.send_header("Content-Length",str(len(raw)))
    handler.send_header("Cache-Control","no-store")
    handler.send_header("Access-Control-Allow-Origin","*")
    handler.end_headers()
    handler.wfile.write(raw)


class Handler(scalp_v4.Handler):
    def do_GET(self):
        if urlparse(self.path).path=="/combined-state":
            try:
                main=fetch_main_state()
                rows,_=base.read_rows()
                x=build_combined_state(main,rows)
                x["ok"]=True
                return _json_response(self,200,x)
            except Exception as exc:
                return _json_response(self,503,{
                    "ok":False,"version":VERSION,
                    "error":f"{type(exc).__name__}: {exc}",
                    "fail_closed":True,"manual_execution_only":True,
                    "order_action":None,"numeric_flip_risk_validated":False,
                    "orders":False,
                })
        return super().do_GET()


def start_server():
    srv=ThreadingHTTPServer(("0.0.0.0",base.PORT),Handler)
    t=threading.Thread(target=srv.serve_forever,name="btc15-combined-state-v3-http",daemon=True)
    t.start()
    print(
        f"BTC15 COMBINED STATE BRIDGE V3 START | port {base.PORT} | "
        "NESTED MAIN SCHEMA | FRESHNESS + CONTRACT FAIL-CLOSED | READ ONLY | NO ORDERS",
        flush=True,
    )
    return srv,t


def _f(v,digits=1,suffix=""):
    try:return f"{float(v):.{digits}f}{suffix}"
    except Exception:return "—"


def observer_loop():
    last=None
    last_hb=0.0
    while True:
        try:
            main=fetch_main_state()
            rows,_=base.read_rows()
            x=build_combined_state(main,rows)
            sig=(
                x.get("contract"),x.get("early",{}).get("state"),
                x.get("final",{}).get("state"),x.get("scalp",{}).get("state"),
                x.get("headline"),tuple(x.get("context_labels") or ()),
                x.get("scalp_management_message"),x.get("scalp_contract_aligned"),
                x.get("scalp_source_fresh"),x.get("scalp_block_reason"),
            )
            now=time.time()
            if sig!=last or now-last_hb>=HEARTBEAT_SEC:
                paths=",".join(x.get("actionable_paths") or ()) or "-"
                labels=",".join(x.get("context_labels") or ()) or "-"
                print(
                    "COMBINED_BRIDGE_V3 | "
                    f"contract={x.get('contract')} | left={_f(x.get('canonical_seconds_left'),1,'s')} | "
                    f"EARLY={x.get('early',{}).get('state')} | FINAL={x.get('final',{}).get('state')} | "
                    f"SCALP={x.get('scalp',{}).get('state')} | headline={x.get('headline')} | "
                    f"paths={paths} | labels={labels} | sync={x.get('scalp_contract_aligned')} | "
                    f"fresh={x.get('scalp_source_fresh')} | age={_f(x.get('scalp_source_age_sec'),1,'s')} | "
                    f"timer_delta={_f(x.get('scalp_timer_delta_sec'),1,'s')} | "
                    f"block={x.get('scalp_block_reason') or '-'} | "
                    f"management={x.get('scalp_management_message')} | NO ORDERS",
                    flush=True,
                )
                last=sig;last_hb=now
        except Exception as exc:
            print(
                f"COMBINED_BRIDGE_V3 WARNING | {type(exc).__name__}: {exc} | FAIL CLOSED | NO ORDERS",
                flush=True,
            )
        time.sleep(POLL_SEC)


def main():
    if not base.COLLECTOR.exists():raise SystemExit(f"collector missing: {base.COLLECTOR}")
    start_server()
    threading.Thread(target=observer_loop,name="btc15-combined-observer-v3",daemon=True).start()
    runpy.run_path(str(base.COLLECTOR),run_name="__main__")
    return 0


if __name__=="__main__":raise SystemExit(main())
