#!/usr/bin/env python3
"""Read-only full-contract monitor for production V8.1 SCALP output."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json, math, os, time
from urllib.request import urlopen

URL=os.environ["V81_LADDERS_URL"]
SAMPLE_S=float(os.environ.get("V81_MONITOR_SAMPLE_S","1.0"))
TIMEOUT_S=float(os.environ.get("V81_MONITOR_TIMEOUT_S","0.8"))
WINDOW_S=900

def iso(ts):
    return datetime.fromtimestamp(ts,tz=timezone.utc).isoformat()

def fetch():
    with urlopen(URL,timeout=TIMEOUT_S) as r:
        raw=r.read(524289)
    if len(raw)>524288: raise ValueError("OVERSIZE_RESPONSE")
    v=json.loads(raw)
    if not isinstance(v,dict): raise ValueError("NOT_OBJECT")
    return v

now=time.time()
start=(math.floor(now/WINDOW_S)+1)*WINDOW_S
end=start+WINDOW_S
print("V81_PRODUCT_MONITOR_PLAN | "+json.dumps({
    "url":URL,"sample_s":SAMPLE_S,"window_start_utc":iso(start),
    "window_end_utc":iso(end),"signal_only":True,"orders":False
},separators=(",",":")),flush=True)

last=0.0
while time.time()<start:
    t=time.time()
    try:
        v=fetch()
        if t-last>=20:
            print("V81_PRODUCT_WARMUP | "+json.dumps({
                "at_utc":iso(t),"status":v.get("status"),"reason":v.get("reason"),
                "guidance":v.get("guidance"),"contract":v.get("contract"),
                "origin":bool(v.get("origin")),"event":v.get("event"),
                "diagnostics":v.get("diagnostics"),"confirmation_counts":v.get("confirmation_counts")
            },separators=(",",":")),flush=True); last=t
    except Exception as exc:
        if t-last>=20:
            print("V81_PRODUCT_WARMUP_ERROR | "+json.dumps({
                "at_utc":iso(t),"type":type(exc).__name__
            },separators=(",",":")),flush=True); last=t
    time.sleep(min(.75,max(.05,start-time.time())))

samples=transport_errors=unavailable=identity_bad=0
signals=exits=origin_samples=0
status_counts=Counter()
reason_counts=Counter()
guidance_counts=Counter()
diag_reason_counts=Counter()
diag_side_reason_counts=Counter()
ready_confirming_samples=0
max_confirm_up=max_confirm_down=0
handoff_bad=0
event_ids=set()
prev_status=None
status_transitions=0
last_progress=0.0

while time.time()<end:
    cycle=time.monotonic(); wall=time.time()
    try:
        v=fetch(); samples+=1
        status=str(v.get("status","MISSING")); status_counts[status]+=1
        if prev_status is not None and status!=prev_status: status_transitions+=1
        prev_status=status

        ident=v.get("official_identity") or {}
        if wall>=start+3 and abs(float(ident.get("official_open",-1))-start)>1e-6:
            identity_bad+=1

        reason=str(v.get("reason",""))
        if reason: reason_counts[reason]+=1

        guidance=str(v.get("guidance",""))
        if guidance: guidance_counts[guidance]+=1

        if status=="UNAVAILABLE":
            unavailable+=1

        if v.get("origin"):
            origin_samples+=1

        event=v.get("event")
        if event=="SCALP_SIGNAL":
            signals+=1
        elif event=="SCALP_EXIT":
            exits+=1
        if event:
            oid=(v.get("origin") or {}).get("origin_id")
            event_ids.add((event,oid,v.get("published_ts")))

        for d in v.get("diagnostics") or []:
            if not isinstance(d,dict): continue
            dr=str(d.get("reason","UNKNOWN"))
            side=str(d.get("side","?"))
            diag_reason_counts[dr]+=1
            diag_side_reason_counts[side+":"+dr]+=1
            if dr=="READY_CONFIRMING": ready_confirming_samples+=1

        cc=v.get("confirmation_counts") or {}
        try: max_confirm_up=max(max_confirm_up,int(cc.get("UP",0)))
        except Exception: pass
        try: max_confirm_down=max(max_confirm_down,int(cc.get("DOWN",0)))
        except Exception: pass

        h=v.get("handoff") or {}
        if h and (h.get("failed") or h.get("pressure") or h.get("drops",0)):
            handoff_bad+=1

        if wall-last_progress>=60:
            print("V81_PRODUCT_PROGRESS | "+json.dumps({
                "at_utc":iso(wall),"samples":samples,"unavailable":unavailable,
                "status_counts":dict(status_counts),"guidance_counts":dict(guidance_counts),
                "signals":signals,"exits":exits,"origin_samples":origin_samples,
                "diag_reasons":dict(diag_reason_counts),
                "max_confirm_up":max_confirm_up,"max_confirm_down":max_confirm_down,
                "handoff_bad":handoff_bad
            },separators=(",",":")),flush=True); last_progress=wall
    except Exception:
        transport_errors+=1

    elapsed=time.monotonic()-cycle
    time.sleep(max(0.0,SAMPLE_S-elapsed))

result={
    "schema":"BTC15_V81_PRODUCT_MONITOR_V1",
    "window_start_utc":iso(start),"window_end_utc":iso(end),"duration_s":WINDOW_S,
    "samples":samples,"transport_errors":transport_errors,
    "unavailable":unavailable,"status_counts":dict(status_counts),
    "status_transitions":status_transitions,"identity_bad":identity_bad,
    "guidance_counts":dict(guidance_counts),"signals":signals,"exits":exits,
    "unique_events":len(event_ids),"origin_samples":origin_samples,
    "diagnostic_reasons":dict(diag_reason_counts),
    "diagnostic_side_reasons":dict(diag_side_reason_counts),
    "ready_confirming_samples":ready_confirming_samples,
    "max_confirm_up":max_confirm_up,"max_confirm_down":max_confirm_down,
    "handoff_bad":handoff_bad,"reason_counts":dict(reason_counts),
    "signal_only":True,"orders":False
}
print("V81_PRODUCT_RESULT | "+json.dumps(result,separators=(",",":")),flush=True)
while True: time.sleep(3600)
