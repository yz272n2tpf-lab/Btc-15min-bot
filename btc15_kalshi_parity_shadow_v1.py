#!/usr/bin/env python3
"""
BTC15 KALSHI-APP / BRTI PARITY SHADOW V2

Fixes V1's schema mismatch:
- unified log is side-row based, so V2 reconstructs UP/DOWN quotes from
  side + side_bid + side_ask across the newest contract snapshot.
- direct BRTI comparison can fall back to the bot's persistent
  kalshi_direct_brti_parity_v1.csv when BRTI fields are not present
  on the unified row.

READ-ONLY:
- no bot logic edits
- no trading threshold changes
- no orders
"""

from pathlib import Path
from datetime import datetime, timezone
import base64
import csv
import math
import os
import sys
import time

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

DATA_ROOT = Path("/data") if Path("/data").exists() else Path(".")
UNIFIED = DATA_ROOT / "kalshi_subminute_unified_v1_1.csv"
BRTI_LOG = DATA_ROOT / "kalshi_direct_brti_parity_v1.csv"
OUT = DATA_ROOT / "kalshi_app_parity_shadow_v1.csv"

BASE = "https://external-api.kalshi.com"
MARKETS_PATH = "/trade-api/v2/markets"
BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"

POLL_SECONDS = 15

# Plumbing tolerances only; NOT trading thresholds.
SOURCE_MAX_AGE_SEC = 12.0
QUOTE_MAX_AGE_SEC = 6.0
CLOCK_TOLERANCE_SEC = 10.0
TARGET_TOLERANCE_DOLLARS = 1.00
QUOTE_TOLERANCE = 0.06
BRTI_TIME_TOLERANCE_SEC = 6.0
BRTI_VALUE_TOLERANCE_DOLLARS = 2.00
SNAPSHOT_JOIN_TOLERANCE_SEC = 2.0

FIELDS = [
    "audit_timestamp_utc","source_timestamp_utc","source_age_sec",
    "unified_contract","api_contract","contract_match",
    "logged_remaining_sec","api_remaining_at_source_sec","clock_delta_sec","clock_match",
    "logged_target_inferred","api_target","target_delta","target_match",
    "logged_up_bid","api_up_bid","logged_up_ask","api_up_ask",
    "logged_down_bid","api_down_bid","logged_down_ask","api_down_ask",
    "quote_max_delta","quote_scorable","quote_match",
    "logged_brti_gap","logged_brti_side","logged_brti_value_inferred",
    "api_brti_value_near_source","api_brti_side_near_source",
    "brti_time_delta_sec","brti_value_delta","brti_match",
    "row_scorable","overall_status","notes"
]

def now_utc():
    return datetime.now(timezone.utc)

def parse_dt(x):
    try:
        d = datetime.fromisoformat(str(x).strip().replace("Z","+00:00"))
        if d.tzinfo is None:
            d = d.replace(tzinfo=timezone.utc)
        return d.astimezone(timezone.utc)
    except Exception:
        return None

def num(x):
    try:
        return float(str(x).strip())
    except Exception:
        return math.nan

def prob(x):
    v = num(x)
    if math.isfinite(v) and abs(v) > 1.5:
        v /= 100.0
    return v

def side(x):
    s = str(x or "").strip().upper()
    if s in {"UP","YES","Y","HIGHER","ABOVE","TRUE","1"}:
        return "UP"
    if s in {"DOWN","NO","N","LOWER","BELOW","FALSE","0"}:
        return "DOWN"
    return ""

def truthy(x):
    return str(x or "").strip().lower() in {"1","true","yes","y"}

def first(r, names):
    for k in names:
        if k in r and str(r.get(k,"")).strip() != "":
            return r.get(k)
    return ""

def all_rows(path):
    if not path.exists():
        return []
    with path.open(newline="", encoding="utf-8-sig", errors="ignore") as f:
        return list(csv.DictReader(f))

def load_private_key():
    kid = os.getenv("KALSHI_KEY_ID","").strip()
    b64 = os.getenv("KALSHI_PRIVATE_KEY_B64","").strip()
    if kid and b64:
        raw = base64.b64decode(b64)
        key = serialization.load_pem_private_key(raw, password=None)
        return kid, key

    kid_path = Path.home()/".kalshi"/"key_id"
    key_path = Path.home()/".kalshi"/"private_key.pem"
    if kid_path.exists() and key_path.exists():
        kid = kid_path.read_text().strip()
        key = serialization.load_pem_private_key(key_path.read_bytes(), password=None)
        return kid, key

    raise RuntimeError("Kalshi read-only credentials not available")

KEY_ID = None
PRIVATE_KEY = None

def auth_headers(method, path):
    global KEY_ID, PRIVATE_KEY
    if KEY_ID is None or PRIVATE_KEY is None:
        KEY_ID, PRIVATE_KEY = load_private_key()

    ts = str(int(time.time()*1000))
    msg = (ts + method.upper() + path).encode("utf-8")
    sig = PRIVATE_KEY.sign(
        msg,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json",
        "User-Agent": "BTC15-parity-shadow/2.0",
    }

def kalshi_get(path, params=None):
    r = requests.get(
        BASE + path,
        headers=auth_headers("GET", path),
        params=params,
        timeout=10,
    )
    r.raise_for_status()
    return r.json()

def active_market():
    obj = kalshi_get(
        MARKETS_PATH,
        {"status":"open","series_ticker":"KXBTC15M","limit":1000},
    )
    now = now_utc()
    active = []
    for m in obj.get("markets", []):
        ticker = str(m.get("ticker",""))
        if not ticker.startswith("KXBTC15M"):
            continue
        op = parse_dt(m.get("open_time"))
        cl = parse_dt(m.get("close_time"))
        if op and cl and op <= now < cl:
            active.append((cl,m))
    if not active:
        return None
    active.sort(key=lambda z:z[0])
    return active[0][1]

def direct_brti_payload():
    obj = kalshi_get(BRTI_PATH, {"id":"BRTI","maxResolution":"PER_SECOND"})
    data = obj.get("data", obj) if isinstance(obj,dict) else {}
    payload = data.get("payload") if isinstance(data,dict) else None
    if not isinstance(payload,list):
        return []
    out = []
    for item in payload:
        if not isinstance(item,dict):
            continue
        try:
            val = float(item.get("value"))
            t = datetime.fromtimestamp(int(item.get("time"))/1000.0, tz=timezone.utc)
            out.append((t,val))
        except Exception:
            continue
    return out

def market_target(m):
    for k in ["floor_strike","cap_strike","strike","target","settlement_value"]:
        v = num(m.get(k))
        if math.isfinite(v):
            return v
    return math.nan

def qv(m, side_name, level):
    if side_name == "UP" and level == "bid":
        keys = ["yes_bid_dollars","yes_bid"]
    elif side_name == "UP":
        keys = ["yes_ask_dollars","yes_ask"]
    elif side_name == "DOWN" and level == "bid":
        keys = ["no_bid_dollars","no_bid"]
    else:
        keys = ["no_ask_dollars","no_ask"]
    v = num(first(m,keys))
    if math.isfinite(v) and v > 1.5:
        v /= 100.0
    return v

def latest_unified_snapshot():
    """
    Return one synthetic snapshot built from all side-rows near the newest
    timestamp for the newest contract.
    """
    rows = all_rows(UNIFIED)
    timed = []
    for r in rows:
        t = parse_dt(r.get("timestamp_utc"))
        c = str(r.get("contract","")).strip()
        if t and c:
            timed.append((t,c,r))
    if not timed:
        return None

    latest_t, latest_c, latest_r = max(timed, key=lambda x:x[0])
    near = [
        r for t,c,r in timed
        if c == latest_c
        and abs((t-latest_t).total_seconds()) <= SNAPSHOT_JOIN_TOLERANCE_SEC
    ]

    snap = dict(latest_r)

    # First prefer explicit wide columns if they exist.
    for k in ["up_bid","up_ask","down_bid","down_ask","yes_bid","yes_ask","no_bid","no_ask"]:
        for r in reversed(near):
            if str(r.get(k,"")).strip() != "":
                snap[k] = r.get(k)
                break

    # Reconstruct wide quotes from side-row schema.
    for r in near:
        sd = side(r.get("side"))
        bid = first(r,["side_bid"])
        ask = first(r,["side_ask"])
        if sd == "UP":
            if str(bid).strip() != "":
                snap["up_bid"] = bid
            if str(ask).strip() != "":
                snap["up_ask"] = ask
        elif sd == "DOWN":
            if str(bid).strip() != "":
                snap["down_bid"] = bid
            if str(ask).strip() != "":
                snap["down_ask"] = ask

    # Carry BRTI fields from any side-row if present.
    for k in ["brti_gap","brti_side","brti_ready","ready"]:
        if str(snap.get(k,"")).strip() == "":
            for r in reversed(near):
                if str(r.get(k,"")).strip() != "":
                    snap[k] = r.get(k)
                    break

    snap["_source_timestamp"] = latest_t
    snap["_snapshot_rows"] = len(near)
    return snap

def nearest_api_brti(payload, source_ts):
    if not payload or source_ts is None:
        return None, math.nan, math.nan
    t,val = min(payload, key=lambda z: abs((z[0]-source_ts).total_seconds()))
    d = abs((t-source_ts).total_seconds())
    return t,val,d

def nearest_logged_brti(source_ts, api_target, unified_snap):
    """
    Prefer BRTI carried in unified. If absent, adaptively read the bot's
    persistent direct-BRTI parity log.
    Returns (value, side, gap, time_delta).
    """
    ugap = num(first(unified_snap,["brti_gap"]))
    uside = side(first(unified_snap,["brti_side"]))
    if math.isfinite(ugap) and math.isfinite(api_target):
        uval = api_target + ugap
        return uval, (uside or ("UP" if ugap >= 0 else "DOWN")), ugap, 0.0

    rows = all_rows(BRTI_LOG)
    if not rows or source_ts is None:
        return math.nan, "", math.nan, math.nan

    time_names = [
        "timestamp_utc","source_timestamp_utc","time_utc","timestamp",
        "observed_utc","collector_timestamp_utc"
    ]
    value_names = [
        "brti_value","brti_price","direct_brti","direct_brti_value",
        "value","price","benchmark_value"
    ]
    gap_names = ["brti_gap","gap","distance","target_gap"]
    side_names = ["brti_side","side","benchmark_side"]

    candidates = []
    for r in rows:
        t = parse_dt(first(r,time_names))
        if not t:
            continue
        d = abs((t-source_ts).total_seconds())
        candidates.append((d,t,r))
    if not candidates:
        return math.nan, "", math.nan, math.nan

    d,_,r = min(candidates, key=lambda z:z[0])

    val = num(first(r,value_names))
    gap = num(first(r,gap_names))
    sd = side(first(r,side_names))

    if not math.isfinite(val) and math.isfinite(gap) and math.isfinite(api_target):
        val = api_target + gap
    if not math.isfinite(gap) and math.isfinite(val) and math.isfinite(api_target):
        gap = val - api_target
    if not sd and math.isfinite(gap):
        sd = "UP" if gap >= 0 else "DOWN"
    if not sd and math.isfinite(val) and math.isfinite(api_target):
        sd = "UP" if val >= api_target else "DOWN"

    return val, sd, gap, d

def append(rec):
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new:
            w.writeheader()
        w.writerow({k:rec.get(k,"") for k in FIELDS})

def finite_delta(a,b):
    if math.isfinite(a) and math.isfinite(b):
        return abs(a-b)
    return math.nan

contract_stats = {}
last_contract = None

def update_summary(contract, status):
    if not contract:
        return
    st = contract_stats.setdefault(contract, {"rows":0,"scorable":0,"passes":0,"fails":0})
    st["rows"] += 1
    if status in {"PASS","FAIL"}:
        st["scorable"] += 1
        st["passes"] += int(status=="PASS")
        st["fails"] += int(status=="FAIL")

def print_summary(contract):
    st = contract_stats.get(contract)
    if not st:
        return
    rate = (100*st["passes"]/st["scorable"]) if st["scorable"] else 0.0
    print(
        f"PARITY CONTRACT SUMMARY | {contract} | rows {st['rows']} | "
        f"scorable {st['scorable']} | pass {st['passes']} | fail {st['fails']} | "
        f"pass_rate {rate:.1f}%",
        flush=True,
    )

def one_audit():
    global last_contract

    m = active_market()
    if m is None:
        print("PARITY WAIT | no active KXBTC15M contract", flush=True)
        return

    r = latest_unified_snapshot()
    if r is None:
        print("PARITY WAIT | unified log missing/empty", flush=True)
        return

    audit_ts = now_utc()
    source_ts = r.get("_source_timestamp") or parse_dt(r.get("timestamp_utc"))
    unified_contract = str(r.get("contract","")).strip()
    api_contract = str(m.get("ticker","")).strip()

    if last_contract and api_contract != last_contract:
        print_summary(last_contract)
    last_contract = api_contract

    source_age = (audit_ts-source_ts).total_seconds() if source_ts else math.nan
    contract_match = bool(unified_contract and unified_contract == api_contract)

    close_ts = parse_dt(m.get("close_time"))
    logged_remaining = num(first(r,["seconds_left"]))
    if not math.isfinite(logged_remaining):
        ml = num(first(r,["minutes_left"]))
        logged_remaining = ml*60.0 if math.isfinite(ml) else math.nan
    api_remaining_source = (
        (close_ts-source_ts).total_seconds()
        if close_ts and source_ts else math.nan
    )
    clock_delta = finite_delta(logged_remaining, api_remaining_source)
    clock_match = math.isfinite(clock_delta) and clock_delta <= CLOCK_TOLERANCE_SEC

    api_target = market_target(m)
    btc_price = num(first(r,["btc_price"]))
    btc_gap = num(first(r,["btc_gap"]))
    logged_target = (
        btc_price-btc_gap
        if math.isfinite(btc_price) and math.isfinite(btc_gap)
        else math.nan
    )
    target_delta = finite_delta(logged_target, api_target)
    target_match = math.isfinite(target_delta) and target_delta <= TARGET_TOLERANCE_DOLLARS

    lupb = prob(first(r,["up_bid","yes_bid"]))
    lupa = prob(first(r,["up_ask","yes_ask"]))
    ldnb = prob(first(r,["down_bid","no_bid"]))
    ldna = prob(first(r,["down_ask","no_ask"]))

    aupb = qv(m,"UP","bid")
    aupa = qv(m,"UP","ask")
    adnb = qv(m,"DOWN","bid")
    adna = qv(m,"DOWN","ask")

    quote_deltas = [
        finite_delta(lupb,aupb),
        finite_delta(lupa,aupa),
        finite_delta(ldnb,adnb),
        finite_delta(ldna,adna),
    ]
    quote_deltas = [x for x in quote_deltas if math.isfinite(x)]
    quote_max_delta = max(quote_deltas) if quote_deltas else math.nan
    quote_scorable = (
        math.isfinite(source_age)
        and source_age <= QUOTE_MAX_AGE_SEC
        and len(quote_deltas) >= 2
    )
    quote_match = quote_scorable and quote_max_delta <= QUOTE_TOLERANCE

    api_payload = direct_brti_payload()
    _, api_brti, api_brti_time_delta = nearest_api_brti(api_payload,source_ts)
    logged_brti, logged_brti_side, logged_brti_gap, logged_brti_time_delta = (
        nearest_logged_brti(source_ts,api_target,r)
    )
    brti_time_delta = max(
        x for x in [api_brti_time_delta,logged_brti_time_delta]
        if math.isfinite(x)
    ) if any(math.isfinite(x) for x in [api_brti_time_delta,logged_brti_time_delta]) else math.nan

    api_brti_side = (
        "UP" if math.isfinite(api_brti) and math.isfinite(api_target) and api_brti >= api_target
        else ("DOWN" if math.isfinite(api_brti) and math.isfinite(api_target) else "")
    )
    brti_value_delta = finite_delta(logged_brti,api_brti)
    brti_match = (
        math.isfinite(brti_time_delta)
        and brti_time_delta <= BRTI_TIME_TOLERANCE_SEC
        and math.isfinite(brti_value_delta)
        and brti_value_delta <= BRTI_VALUE_TOLERANCE_DOLLARS
        and logged_brti_side in {"UP","DOWN"}
        and logged_brti_side == api_brti_side
    )

    row_scorable = (
        math.isfinite(source_age)
        and source_age <= SOURCE_MAX_AGE_SEC
        and contract_match
        and quote_scorable
        and math.isfinite(brti_time_delta)
        and brti_time_delta <= BRTI_TIME_TOLERANCE_SEC
        and math.isfinite(brti_value_delta)
    )

    if not row_scorable:
        status = "WAIT"
    elif contract_match and clock_match and target_match and quote_match and brti_match:
        status = "PASS"
    else:
        status = "FAIL"

    notes = []
    if not contract_match: notes.append("CONTRACT")
    if row_scorable and not clock_match: notes.append("CLOCK")
    if row_scorable and not target_match: notes.append("TARGET")
    if quote_scorable and not quote_match: notes.append("QUOTES")
    if row_scorable and not brti_match: notes.append("BRTI")
    if not quote_scorable: notes.append("QUOTE_MISSING_OR_STALE")
    if not math.isfinite(logged_brti): notes.append("BOT_BRTI_MISSING")
    if not row_scorable: notes.append("NOT_SCORABLE")

    rec = {
        "audit_timestamp_utc":audit_ts.isoformat(),
        "source_timestamp_utc":source_ts.isoformat() if source_ts else "",
        "source_age_sec":round(source_age,3) if math.isfinite(source_age) else "",
        "unified_contract":unified_contract,
        "api_contract":api_contract,
        "contract_match":contract_match,
        "logged_remaining_sec":round(logged_remaining,3) if math.isfinite(logged_remaining) else "",
        "api_remaining_at_source_sec":round(api_remaining_source,3) if math.isfinite(api_remaining_source) else "",
        "clock_delta_sec":round(clock_delta,3) if math.isfinite(clock_delta) else "",
        "clock_match":clock_match,
        "logged_target_inferred":round(logged_target,4) if math.isfinite(logged_target) else "",
        "api_target":round(api_target,4) if math.isfinite(api_target) else "",
        "target_delta":round(target_delta,4) if math.isfinite(target_delta) else "",
        "target_match":target_match,
        "logged_up_bid":lupb if math.isfinite(lupb) else "",
        "api_up_bid":aupb if math.isfinite(aupb) else "",
        "logged_up_ask":lupa if math.isfinite(lupa) else "",
        "api_up_ask":aupa if math.isfinite(aupa) else "",
        "logged_down_bid":ldnb if math.isfinite(ldnb) else "",
        "api_down_bid":adnb if math.isfinite(adnb) else "",
        "logged_down_ask":ldna if math.isfinite(ldna) else "",
        "api_down_ask":adna if math.isfinite(adna) else "",
        "quote_max_delta":round(quote_max_delta,6) if math.isfinite(quote_max_delta) else "",
        "quote_scorable":quote_scorable,
        "quote_match":quote_match,
        "logged_brti_gap":round(logged_brti_gap,4) if math.isfinite(logged_brti_gap) else "",
        "logged_brti_side":logged_brti_side,
        "logged_brti_value_inferred":round(logged_brti,4) if math.isfinite(logged_brti) else "",
        "api_brti_value_near_source":round(api_brti,4) if math.isfinite(api_brti) else "",
        "api_brti_side_near_source":api_brti_side,
        "brti_time_delta_sec":round(brti_time_delta,3) if math.isfinite(brti_time_delta) else "",
        "brti_value_delta":round(brti_value_delta,4) if math.isfinite(brti_value_delta) else "",
        "brti_match":brti_match,
        "row_scorable":row_scorable,
        "overall_status":status,
        "notes":"|".join(notes),
    }
    append(rec)
    update_summary(api_contract,status)

    qtxt = f"{quote_max_delta*100:.1f}c" if math.isfinite(quote_max_delta) else "N/A"
    btxt = f"${brti_value_delta:.2f}" if math.isfinite(brti_value_delta) else "N/A"
    print(
        f"PARITY {status} | {api_contract} | age {source_age:.1f}s | "
        f"clock Δ{clock_delta:.1f}s | target Δ${target_delta:.2f} | "
        f"quotes Δ{qtxt} | BRTI Δ{btxt} @ "
        f"{brti_time_delta:.1f}s | joined {r.get('_snapshot_rows',0)} row(s)"
        + (f" | {rec['notes']}" if rec["notes"] else ""),
        flush=True,
    )

def self_test():
    snap = latest_unified_snapshot()
    print("KALSHI PARITY SHADOW V2 SELF-TEST")
    if snap is None:
        print("Unified local sample: not present — compile/schema fallback test only.")
    else:
        vals = {
            "up_bid":prob(first(snap,["up_bid","yes_bid"])),
            "up_ask":prob(first(snap,["up_ask","yes_ask"])),
            "down_bid":prob(first(snap,["down_bid","no_bid"])),
            "down_ask":prob(first(snap,["down_ask","no_ask"])),
        }
        n = sum(math.isfinite(v) for v in vals.values())
        print("Newest contract:", snap.get("contract",""))
        print("Joined side rows:", snap.get("_snapshot_rows",0))
        print("Reconstructed quote fields:", n, "/ 4")
        print("Quotes:", vals)
        if n < 2:
            raise SystemExit("SELF-TEST FAIL: could not reconstruct at least two quote fields.")
    print("SELF-TEST: PASS")
    print("No network request made. No orders.")
    return 0

def main():
    if "--self-test" in sys.argv:
        return self_test()

    print("="*84, flush=True)
    print("BTC15 KALSHI-APP / BRTI PARITY SHADOW V2: STARTING", flush=True)
    print(f"Unified source: {UNIFIED}", flush=True)
    print(f"Bot BRTI source: {BRTI_LOG}", flush=True)
    print(f"Output: {OUT}", flush=True)
    print("Fix: side-row quote reconstruction + persistent bot-BRTI fallback", flush=True)
    print("Read-only. Existing bot unchanged. NO ORDERS.", flush=True)
    print("="*84, flush=True)

    while True:
        try:
            one_audit()
        except KeyboardInterrupt:
            if last_contract:
                print_summary(last_contract)
            break
        except Exception as e:
            print(f"PARITY WARNING | {type(e).__name__}: {e}", flush=True)
        time.sleep(POLL_SECONDS)

    return 0

if __name__ == "__main__":
    raise SystemExit(main())
