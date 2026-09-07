#!/usr/bin/env python3
"""
BTC15 FINAL POSITION-PROTECTION SHADOW V4 — LOW MEMORY

Same prospective FINAL-trajectory collection as V3, but only a bounded tail
of the unified CSV is read each poll. This prevents the shadow collector from
loading the entire growing dataset into RAM.

READ-ONLY. NO CORE LOGIC CHANGES. NO ORDERS.
"""
from pathlib import Path
from datetime import datetime, timezone
import csv, json, math, sys, time

DATA_ROOT = Path("/data") if Path("/data").exists() else Path(".")
SOURCE = DATA_ROOT / "kalshi_subminute_unified_v1_1.csv"
OUT = DATA_ROOT / "kalshi_final_position_protection_shadow_v3.csv"
STATE = DATA_ROOT / "kalshi_final_position_protection_shadow_v3_state.json"

POLL_SECONDS = 3
TAIL_BYTES = 256 * 1024

FAIR_MIN = 0.90
MAX_MINUTES_LEFT = 8.0
GAP_EARLY = 75.0
GAP_LATE = 50.0
DIST_RANGE_MIN = 1.0

FIELDS = [
    "collector_timestamp_utc","source_timestamp_utc","contract","record_type",
    "final_side","current_preferred_side","final_trigger_fair","current_fair",
    "fair_change_from_trigger","minutes_left","btc_price","btc_gap",
    "signed_gap_for_final_side","trigger_signed_gap","signed_gap_change_from_trigger",
    "dist_over_range5","brti_ready","brti_side","brti_gap","reversal_state",
    "up_bid","up_ask","down_bid","down_ask","final_side_bid",
    "trigger_final_side_bid","bid_change_from_trigger","current_target_side","notes"
]

def utcnow():
    return datetime.now(timezone.utc)

def parse_dt(x):
    try:
        d = datetime.fromisoformat(str(x).strip().replace("Z","+00:00"))
        if d.tzinfo is None: d=d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None

def num(x):
    try:return float(str(x).strip())
    except Exception:return math.nan

def prob(x):
    v=num(x)
    if math.isfinite(v) and abs(v)>1.5:v/=100.0
    return v

def side(x):
    s=str(x or "").strip().upper()
    if s in {"UP","YES","Y","HIGHER","ABOVE","TRUE","1"}:return "UP"
    if s in {"DOWN","NO","N","LOWER","BELOW","FALSE","0"}:return "DOWN"
    return ""

def truthy(x):
    return str(x or "").strip().lower() in {"1","true","yes","y"}

def first(r,names):
    for k in names:
        if k in r and str(r.get(k,"")).strip()!="":
            return r.get(k)
    return ""

def tail_csv_rows(path,max_bytes):
    if not path.exists() or path.stat().st_size<=0:return []
    with path.open("rb") as f:
        hb=f.readline()
        if not hb:return []
        h=next(csv.reader([hb.decode("utf-8-sig",errors="ignore").rstrip("\r\n")]),[])
        he=f.tell(); size=path.stat().st_size; start=max(he,size-max_bytes)
        f.seek(start)
        if start>he:f.readline()
        data=f.read()
    out=[]
    for line in data.decode("utf-8",errors="ignore").splitlines():
        if not line.strip():continue
        try:v=next(csv.reader([line]))
        except Exception:continue
        if len(v)<len(h):v+=[""]*(len(h)-len(v))
        out.append(dict(zip(h,v[:len(h)])))
    return out

def preferred_side(r):
    ps=side(first(r,["preferred_side","preferred_fair_side","fair_preferred_side"]))
    if ps:return ps
    rs=side(r.get("side"))
    sf=prob(r.get("side_fair")); pf=prob(r.get("preferred_fair"))
    if truthy(r.get("preferred_side_match")):return rs
    if rs and math.isfinite(sf) and math.isfinite(pf) and abs(sf-pf)<1e-7:return rs
    return ""

def preferred_row(r):
    ps=preferred_side(r); rs=side(r.get("side"))
    return bool(ps and (not rs or rs==ps))

def side_bid(r,sd):
    v=prob(first(r,["up_bid","yes_bid"] if sd=="UP" else ["down_bid","no_bid"]))
    if math.isfinite(v):return v
    if side(r.get("side"))==sd:return prob(r.get("side_bid"))
    return math.nan

def quote(r,sd,level):
    names = (
        ["up_bid","yes_bid"] if sd=="UP" and level=="bid" else
        ["up_ask","yes_ask"] if sd=="UP" else
        ["down_bid","no_bid"] if level=="bid" else
        ["down_ask","no_ask"]
    )
    v=prob(first(r,names))
    if math.isfinite(v):return v
    if side(r.get("side"))==sd:
        return prob(r.get("side_bid" if level=="bid" else "side_ask"))
    return math.nan

def load_state():
    base={"started_utc":utcnow().isoformat(),"last_source_utc":"","active":None}
    if not STATE.exists():return base
    try:
        x=json.loads(STATE.read_text(encoding="utf-8"))
        base.update(x); return base
    except Exception:return base

def save_state(s):
    tmp=STATE.with_suffix(".tmp")
    tmp.write_text(json.dumps(s,indent=2,sort_keys=True),encoding="utf-8")
    tmp.replace(STATE)

def append(rec):
    new=not OUT.exists()
    with OUT.open("a",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=FIELDS)
        if new:w.writeheader()
        w.writerow({k:rec.get(k,"") for k in FIELDS})

def qualifies_final(r):
    ps=preferred_side(r)
    fair=prob(r.get("preferred_fair"))
    ml=num(r.get("minutes_left"))
    gap=num(r.get("btc_gap"))
    ratio=num(r.get("dist_over_range5"))
    target=side(r.get("current_target_side"))
    ready=truthy(first(r,["brti_ready","ready"]))
    bs=side(r.get("brti_side"))
    need=GAP_EARLY if math.isfinite(ml) and ml>6 else GAP_LATE
    return (
        ps and math.isfinite(fair) and fair>=FAIR_MIN
        and math.isfinite(ml) and ml<=MAX_MINUTES_LEFT
        and math.isfinite(gap) and abs(gap)>=need
        and math.isfinite(ratio) and ratio>=DIST_RANGE_MIN
        and target==ps and ready and bs==ps
    )

def record(r,typ,active):
    fs=active["final_side"]
    pf=prob(r.get("preferred_fair")); ml=num(r.get("minutes_left"))
    btc=num(r.get("btc_price")); gap=num(r.get("btc_gap"))
    ratio=num(r.get("dist_over_range5")); bg=num(r.get("brti_gap"))
    fb=side_bid(r,fs)
    sg=gap if fs=="UP" else (-gap if math.isfinite(gap) else math.nan)
    fairchg=pf-float(active["trigger_fair"]) if math.isfinite(pf) else math.nan
    gapchg=sg-float(active["trigger_signed_gap"]) if math.isfinite(sg) else math.nan
    tb=float(active["trigger_bid"])
    bidchg=fb-tb if math.isfinite(fb) and math.isfinite(tb) else math.nan
    return {
        "collector_timestamp_utc":utcnow().isoformat(),
        "source_timestamp_utc":r.get("timestamp_utc",""),
        "contract":str(r.get("contract","")).strip(),"record_type":typ,
        "final_side":fs,"current_preferred_side":preferred_side(r),
        "final_trigger_fair":active["trigger_fair"],"current_fair":pf if math.isfinite(pf) else "",
        "fair_change_from_trigger":fairchg if math.isfinite(fairchg) else "",
        "minutes_left":ml if math.isfinite(ml) else "","btc_price":btc if math.isfinite(btc) else "",
        "btc_gap":gap if math.isfinite(gap) else "","signed_gap_for_final_side":sg if math.isfinite(sg) else "",
        "trigger_signed_gap":active["trigger_signed_gap"],
        "signed_gap_change_from_trigger":gapchg if math.isfinite(gapchg) else "",
        "dist_over_range5":ratio if math.isfinite(ratio) else "",
        "brti_ready":truthy(first(r,["brti_ready","ready"])),"brti_side":side(r.get("brti_side")),
        "brti_gap":bg if math.isfinite(bg) else "","reversal_state":first(r,["reversal_state","reversal"]),
        "up_bid":quote(r,"UP","bid"),"up_ask":quote(r,"UP","ask"),
        "down_bid":quote(r,"DOWN","bid"),"down_ask":quote(r,"DOWN","ask"),
        "final_side_bid":fb if math.isfinite(fb) else "",
        "trigger_final_side_bid":tb if math.isfinite(tb) else "",
        "bid_change_from_trigger":bidchg if math.isfinite(bidchg) else "",
        "current_target_side":side(r.get("current_target_side")),
        "notes":"RAW_PROTECTION_TELEMETRY_ONLY",
    }

def main():
    if "--self-test" in sys.argv:
        rows=tail_csv_rows(SOURCE,TAIL_BYTES)
        print("POSITION PROTECTION LOW-MEM SELF-TEST")
        print("Tail rows visible:",len(rows))
        print("SELF-TEST: PASS")
        return 0

    state=load_state()
    started=parse_dt(state.get("started_utc")) or utcnow()
    last=parse_dt(state.get("last_source_utc"))
    active=state.get("active")

    print("BTC15 FINAL POSITION-PROTECTION SHADOW V4 LOW-MEM: STARTING",flush=True)
    print("Bounded CSV tail only. Existing bot unchanged. NO ORDERS.",flush=True)

    while True:
        try:
            rows=tail_csv_rows(SOURCE,TAIL_BYTES)
            batch=[]
            for r in rows:
                t=parse_dt(r.get("timestamp_utc"))
                if not t or t<started:continue
                if last is not None and t<=last:continue
                if not preferred_row(r):continue
                batch.append((t,r))
            if not batch:
                time.sleep(POLL_SECONDS); continue
            batch.sort(key=lambda z:z[0])

            for t,r in batch:
                c=str(r.get("contract","")).strip()
                if not c:continue
                if active and c!=active.get("contract"):
                    print(f"POSITION-PROTECTION ROLLOVER | finished {active.get('contract')}",flush=True)
                    active=None
                if active is None and qualifies_final(r):
                    ps=preferred_side(r); pf=prob(r.get("preferred_fair")); gap=num(r.get("btc_gap"))
                    sg=gap if ps=="UP" else -gap
                    bid=side_bid(r,ps)
                    active={
                        "contract":c,"final_side":ps,"trigger_utc":t.isoformat(),
                        "trigger_fair":float(pf),"trigger_signed_gap":float(sg),
                        "trigger_bid":float(bid) if math.isfinite(bid) else math.nan
                    }
                    append(record(r,"FINAL_TRIGGER",active))
                    print(f"POSITION-PROTECTION FINAL_TRIGGER | {c} | {ps}",flush=True)
                elif active and c==active.get("contract"):
                    append(record(r,"POST_FINAL",active))

            last=max(t for t,_ in batch)
            save_state({"started_utc":started.isoformat(),"last_source_utc":last.isoformat(),"active":active})
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"POSITION-PROTECTION WARNING | {type(e).__name__}: {e}",flush=True)
        time.sleep(POLL_SECONDS)
    return 0

if __name__=="__main__":
    raise SystemExit(main())
