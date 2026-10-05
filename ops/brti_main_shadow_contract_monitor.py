#!/usr/bin/env python3
"""Read-only full-window monitor for 1s BRTI owner + exact MAIN shadow."""
from __future__ import annotations
from collections import Counter
from datetime import datetime, timezone
import json, math, os, time
from urllib.request import urlopen

OWNER_URL=os.environ["BRTI_SHADOW_STATE_URL"]
MAIN_URL=os.environ["BTC15_MAIN_SHADOW_LADDERS_URL"]
SAMPLE_S=float(os.environ.get("BTC15_SHADOW_SAMPLE_S","0.25"))
TIMEOUT_S=float(os.environ.get("BTC15_SHADOW_TIMEOUT_S","0.8"))
WINDOW_S=900

def iso(ts):
    return datetime.fromtimestamp(ts,tz=timezone.utc).isoformat()

def fetch(url):
    with urlopen(url,timeout=TIMEOUT_S) as r:
        raw=r.read(524289)
    if len(raw)>524288: raise ValueError("OVERSIZE_RESPONSE")
    v=json.loads(raw)
    if not isinstance(v,dict): raise ValueError("NOT_OBJECT")
    return v

now=time.time()
start=(math.floor(now/WINDOW_S)+1)*WINDOW_S
end=start+WINDOW_S
print("BTC15_1S_SHADOW_PLAN | "+json.dumps({
    "owner_url":OWNER_URL,"main_url":MAIN_URL,"sample_s":SAMPLE_S,
    "window_start_utc":iso(start),"window_end_utc":iso(end),
    "signal_only":True,"orders":False},separators=(",",":")),flush=True)

# Warmup until the exact next 15-minute boundary.
last=0.0
while time.time()<start:
    t=time.time()
    try:
        o=fetch(OWNER_URL); m=fetch(MAIN_URL)
        if t-last>=20:
            print("BTC15_1S_SHADOW_WARMUP | "+json.dumps({
                "at_utc":iso(t),"owner_status":o.get("status"),
                "owner_clean":o.get("clean_for_qualification"),"owner_age_ms":o.get("age_ms"),
                "main_status":m.get("status"),"main_reason":m.get("reason"),
                "main_contract":(m.get("official_identity") or {}).get("contract")
            },separators=(",",":")),flush=True); last=t
    except Exception as exc:
        if t-last>=20:
            print("BTC15_1S_SHADOW_WARMUP_ERROR | "+json.dumps({
                "at_utc":iso(t),"type":type(exc).__name__},separators=(",",":")),flush=True); last=t
    time.sleep(min(0.75,max(0.05,start-time.time())))

owner_ages=[]
owner_samples=owner_transport=owner_clean_false=owner_status_bad=owner_age_over5=0
owner_source_rollbacks=owner_seq_rollbacks=owner_config_mismatch=0
owner_max_source_gap_ms=0.0
owner_last_source=owner_last_seq=None
owner_first_counters=owner_last_counters=None

main_samples=main_transport=main_unavailable=main_pub_rollbacks=0
main_wrong_identity_after_3s=0
main_first_expected_ms=None
main_last_pub=None
main_prev_available=None
main_transitions=0
main_unavail_start=None
main_longest_unavail_ms=0.0
main_reasons=Counter()
main_revalidated=0
main_max_reval_brti_age_s=0.0
main_max_reval_btc_age_s=0.0
main_max_reval_quote_age_s=0.0
last_progress=0.0

while time.time()<end:
    cycle=time.monotonic(); wall=time.time()

    # Owner sample
    try:
        o=fetch(OWNER_URL); owner_samples+=1
        required=("status","clean_for_qualification","age_ms","sequence","source_ts_ms",
                  "poll_interval_ms","max_qualification_age_ms","upstream_attempts",
                  "upstream_ok","upstream_errors","http_429")
        if any(k not in o for k in required): raise ValueError("OWNER_SCHEMA")
        age=float(o["age_ms"]); owner_ages.append(age)
        if o["clean_for_qualification"] is not True: owner_clean_false+=1
        if o["status"]!="PRIMARY_OK": owner_status_bad+=1
        if age>5000.0: owner_age_over5+=1
        if abs(float(o["poll_interval_ms"])-1000.0)>1e-6 or abs(float(o["max_qualification_age_ms"])-5000.0)>1e-6:
            owner_config_mismatch+=1
        src=int(o["source_ts_ms"]); seq=int(o["sequence"])
        if owner_last_source is not None:
            if src<owner_last_source: owner_source_rollbacks+=1
            elif src>owner_last_source: owner_max_source_gap_ms=max(owner_max_source_gap_ms,src-owner_last_source)
        if owner_last_seq is not None and seq<owner_last_seq: owner_seq_rollbacks+=1
        owner_last_source,owner_last_seq=src,seq
        c={k:int(o[k]) for k in ("upstream_attempts","upstream_ok","upstream_errors","http_429")}
        if owner_first_counters is None: owner_first_counters=c
        owner_last_counters=c
    except Exception:
        owner_transport+=1

    # MAIN sample
    try:
        m=fetch(MAIN_URL); main_samples+=1
        available=m.get("status") in ("PASS","AVAILABLE")
        if main_prev_available is not None and available!=main_prev_available: main_transitions+=1
        main_prev_available=available
        if not available:
            main_unavailable+=1
            main_reasons[str(m.get("reason","UNKNOWN"))]+=1
            if main_unavail_start is None: main_unavail_start=wall
        else:
            if main_unavail_start is not None:
                main_longest_unavail_ms=max(main_longest_unavail_ms,(wall-main_unavail_start)*1000.0)
                main_unavail_start=None
            ident=m.get("official_identity") or {}
            if wall>=start+3 and abs(float(ident.get("official_open",-1))-start)>1e-6:
                main_wrong_identity_after_3s+=1
            elif abs(float(ident.get("official_open",-1))-start)<=1e-6 and main_first_expected_ms is None:
                main_first_expected_ms=max(0.0,(wall-start)*1000.0)
            pub=m.get("published_ts")
            if isinstance(pub,(int,float)):
                if main_last_pub is not None and pub<main_last_pub: main_pub_rollbacks+=1
                main_last_pub=pub
            p=m.get("presentation_revalidation")
            if isinstance(p,dict) and isinstance(p.get("source"),dict):
                s=p["source"]; served=float(m["served_ts"])
                main_revalidated+=1
                main_max_reval_brti_age_s=max(main_max_reval_brti_age_s,served-float(s["brti"]))
                main_max_reval_btc_age_s=max(main_max_reval_btc_age_s,served-float(s["btc"]))
                main_max_reval_quote_age_s=max(main_max_reval_quote_age_s,served-float(s["quote"]))
    except Exception:
        main_transport+=1
        if main_unavail_start is None: main_unavail_start=wall

    if wall-last_progress>=60:
        print("BTC15_1S_SHADOW_PROGRESS | "+json.dumps({
            "at_utc":iso(wall),"owner_samples":owner_samples,
            "owner_max_age_ms":max(owner_ages) if owner_ages else None,
            "owner_clean_false":owner_clean_false,"owner_429":None if owner_last_counters is None else owner_last_counters["http_429"],
            "main_samples":main_samples,"main_unavailable":main_unavailable,
            "main_transitions":main_transitions,"main_reasons":dict(main_reasons),
            "main_first_expected_ms":main_first_expected_ms
        },separators=(",",":")),flush=True); last_progress=wall

    elapsed=time.monotonic()-cycle
    time.sleep(max(0.0,SAMPLE_S-elapsed))

if main_unavail_start is not None:
    main_longest_unavail_ms=max(main_longest_unavail_ms,(end-main_unavail_start)*1000.0)

def delta(k):
    if owner_first_counters is None or owner_last_counters is None: return None
    return owner_last_counters[k]-owner_first_counters[k]

owner_p99=None
if owner_ages:
    a=sorted(owner_ages); owner_p99=a[min(len(a)-1,int(math.ceil(.99*len(a)))-1)]

passed=all([
    owner_samples>=2000, main_samples>=2000,
    owner_transport==0, owner_clean_false==0, owner_status_bad==0, owner_age_over5==0,
    owner_source_rollbacks==0, owner_seq_rollbacks==0, owner_config_mismatch==0,
    delta("upstream_errors")==0, delta("http_429")==0,
    max(owner_ages)<=5000.0 if owner_ages else False,
    main_transport==0, main_unavailable==0, main_transitions==0,
    main_pub_rollbacks==0, main_wrong_identity_after_3s==0,
    main_first_expected_ms is not None and main_first_expected_ms<=3000.0,
])

result={
    "schema":"BTC15_1S_BRTI_MAIN_SHADOW_CONTRACT_V1",
    "status":"PASS" if passed else "FAIL",
    "window_start_utc":iso(start),"window_end_utc":iso(end),"duration_s":WINDOW_S,
    "owner":{"samples":owner_samples,"transport_errors":owner_transport,
        "clean_false":owner_clean_false,"status_not_ok":owner_status_bad,
        "age_over_5s":owner_age_over5,"max_age_ms":max(owner_ages) if owner_ages else None,
        "p99_age_ms":owner_p99,"max_source_gap_ms":owner_max_source_gap_ms,
        "source_rollbacks":owner_source_rollbacks,"sequence_rollbacks":owner_seq_rollbacks,
        "config_mismatch":owner_config_mismatch,"upstream_attempts_delta":delta("upstream_attempts"),
        "upstream_ok_delta":delta("upstream_ok"),"upstream_errors_delta":delta("upstream_errors"),
        "http_429_delta":delta("http_429")},
    "main":{"samples":main_samples,"transport_errors":main_transport,
        "unavailable":main_unavailable,"availability_transitions":main_transitions,
        "longest_unavailable_ms":main_longest_unavail_ms,"reasons":dict(main_reasons),
        "published_rollbacks":main_pub_rollbacks,"wrong_identity_after_3s":main_wrong_identity_after_3s,
        "first_expected_identity_ms":main_first_expected_ms,"revalidated_samples":main_revalidated,
        "max_revalidation_brti_age_s":main_max_reval_brti_age_s,
        "max_revalidation_btc_age_s":main_max_reval_btc_age_s,
        "max_revalidation_quote_age_s":main_max_reval_quote_age_s},
    "signal_only":True,"orders":False,
}
print("BTC15_1S_SHADOW_RESULT | "+json.dumps(result,separators=(",",":")),flush=True)
while True: time.sleep(3600)
