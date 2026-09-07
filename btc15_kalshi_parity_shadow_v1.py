#!/usr/bin/env python3
"""
BTC15 KALSHI/BRTI PARITY SHADOW V3 — LOW MEMORY

Same parity validation as before, but it reads only a bounded tail of the
growing Railway CSVs instead of loading the full files every poll.

READ-ONLY. NO CORE LOGIC CHANGES. NO TRADING THRESHOLD CHANGES. NO ORDERS.
"""
from pathlib import Path
from datetime import datetime, timezone
import base64, csv, math, os, sys, time

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
TAIL_BYTES_UNIFIED = 192 * 1024
TAIL_BYTES_BRTI = 96 * 1024

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
    try: return float(str(x).strip())
    except Exception: return math.nan

def prob(x):
    v = num(x)
    if math.isfinite(v) and abs(v) > 1.5:
        v /= 100.0
    return v

def side(x):
    s = str(x or "").strip().upper()
    if s in {"UP","YES","Y","HIGHER","ABOVE","TRUE","1"}: return "UP"
    if s in {"DOWN","NO","N","LOWER","BELOW","FALSE","0"}: return "DOWN"
    return ""

def first(r, names):
    for k in names:
        if k in r and str(r.get(k,"")).strip() != "":
            return r.get(k)
    return ""

def tail_csv_rows(path, max_bytes):
    if not path.exists() or path.stat().st_size <= 0:
        return []
    with path.open("rb") as f:
        header_b = f.readline()
        if not header_b:
            return []
        header = next(csv.reader([header_b.decode("utf-8-sig", errors="ignore").rstrip("\r\n")]), [])
        if not header:
            return []
        header_end = f.tell()
        size = path.stat().st_size
        start = max(header_end, size - max_bytes)
        f.seek(start)
        if start > header_end:
            f.readline()
        data = f.read()
    rows = []
    for line in data.decode("utf-8", errors="ignore").splitlines():
        if not line.strip():
            continue
        try:
            vals = next(csv.reader([line]))
        except Exception:
            continue
        if len(vals) < len(header):
            vals += [""] * (len(header) - len(vals))
        rows.append(dict(zip(header, vals[:len(header)])))
    return rows

def load_private_key():
    kid = os.getenv("KALSHI_KEY_ID","").strip()
    b64 = os.getenv("KALSHI_PRIVATE_KEY_B64","").strip()
    if kid and b64:
        return kid, serialization.load_pem_private_key(base64.b64decode(b64), password=None)
    kid_path = Path.home()/".kalshi"/"key_id"
    key_path = Path.home()/".kalshi"/"private_key.pem"
    if kid_path.exists() and key_path.exists():
        return kid_path.read_text().strip(), serialization.load_pem_private_key(key_path.read_bytes(), password=None)
    raise RuntimeError("Kalshi read-only credentials not available")

KEY_ID = None
PRIVATE_KEY = None

def auth_headers(method, path):
    global KEY_ID, PRIVATE_KEY
    if KEY_ID is None or PRIVATE_KEY is None:
        KEY_ID, PRIVATE_KEY = load_private_key()
    ts = str(int(time.time()*1000))
    sig = PRIVATE_KEY.sign(
        (ts + method.upper() + path).encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
        "Accept": "application/json",
        "User-Agent": "BTC15-parity-lowmem/3.0",
    }

def kalshi_get(path, params=None):
    r = requests.get(BASE + path, headers=auth_headers("GET", path), params=params, timeout=10)
    r.raise_for_status()
    return r.json()

def active_market():
    obj = kalshi_get(MARKETS_PATH, {"status":"open","series_ticker":"KXBTC15M","limit":1000})
    now = now_utc()
    active = []
    for m in obj.get("markets", []):
        t = str(m.get("ticker",""))
        op, cl = parse_dt(m.get("open_time")), parse_dt(m.get("close_time"))
        if t.startswith("KXBTC15M") and op and cl and op <= now < cl:
            active.append((cl,m))
    if not active:
        return None
    active.sort(key=lambda z:z[0])
    return active[0][1]

def direct_brti_payload():
    obj = kalshi_get(BRTI_PATH, {"id":"BRTI","maxResolution":"PER_SECOND"})
    data = obj.get("data", obj) if isinstance(obj, dict) else {}
    payload = data.get("payload") if isinstance(data, dict) else None
    if not isinstance(payload, list):
        return []
    out = []
    for item in payload:
        try:
            out.append((
                datetime.fromtimestamp(int(item["time"])/1000.0, tz=timezone.utc),
                float(item["value"])
            ))
        except Exception:
            pass
    return out

def market_target(m):
    for k in ["floor_strike","cap_strike","strike","target","settlement_value"]:
        v = num(m.get(k))
        if math.isfinite(v):
            return v
    return math.nan

def qv(m, sd, level):
    if sd=="UP" and level=="bid": keys=["yes_bid_dollars","yes_bid"]
    elif sd=="UP": keys=["yes_ask_dollars","yes_ask"]
    elif level=="bid": keys=["no_bid_dollars","no_bid"]
    else: keys=["no_ask_dollars","no_ask"]
    v = num(first(m, keys))
    if math.isfinite(v) and v > 1.5:
        v /= 100.0
    return v

def latest_unified_snapshot():
    rows = tail_csv_rows(UNIFIED, TAIL_BYTES_UNIFIED)
    timed = []
    for r in rows:
        t = parse_dt(r.get("timestamp_utc"))
        c = str(r.get("contract","")).strip()
        if t and c:
            timed.append((t,c,r))
    if not timed:
        return None
    latest_t, latest_c, latest_r = max(timed, key=lambda x:x[0])
    near = [r for t,c,r in timed if c == latest_c and abs((t-latest_t).total_seconds()) <= SNAPSHOT_JOIN_TOLERANCE_SEC]
    snap = dict(latest_r)
    for r in near:
        sd = side(r.get("side"))
        bid, ask = first(r,["side_bid"]), first(r,["side_ask"])
        if sd=="UP":
            if str(bid).strip(): snap["up_bid"] = bid
            if str(ask).strip(): snap["up_ask"] = ask
        elif sd=="DOWN":
            if str(bid).strip(): snap["down_bid"] = bid
            if str(ask).strip(): snap["down_ask"] = ask
    snap["_source_timestamp"] = latest_t
    snap["_snapshot_rows"] = len(near)
    return snap

def nearest_api_brti(payload, source_ts):
    if not payload or source_ts is None:
        return math.nan, math.nan
    t,val = min(payload, key=lambda z: abs((z[0]-source_ts).total_seconds()))
    return val, abs((t-source_ts).total_seconds())

def nearest_logged_brti(source_ts, api_target):
    rows = tail_csv_rows(BRTI_LOG, TAIL_BYTES_BRTI)
    if not rows or source_ts is None:
        return math.nan, "", math.nan, math.nan
    time_names = ["timestamp_utc","source_timestamp_utc","time_utc","timestamp","observed_utc","collector_timestamp_utc"]
    value_names = ["brti_value","brti_price","direct_brti","direct_brti_value","value","price","benchmark_value"]
    gap_names = ["brti_gap","gap","distance","target_gap"]
    side_names = ["brti_side","side","benchmark_side"]

    cand = []
    for r in rows:
        t = parse_dt(first(r,time_names))
        if t:
            cand.append((abs((t-source_ts).total_seconds()),r))
    if not cand:
        return math.nan, "", math.nan, math.nan
    d,r = min(cand, key=lambda z:z[0])
    val = num(first(r,value_names))
    gap = num(first(r,gap_names))
    sd = side(first(r,side_names))
    if not math.isfinite(val) and math.isfinite(gap) and math.isfinite(api_target):
        val = api_target + gap
    if not math.isfinite(gap) and math.isfinite(val) and math.isfinite(api_target):
        gap = val - api_target
    if not sd and math.isfinite(gap):
        sd = "UP" if gap >= 0 else "DOWN"
    return val, sd, gap, d

def append(rec):
    new = not OUT.exists()
    with OUT.open("a", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS)
        if new: w.writeheader()
        w.writerow({k:rec.get(k,"") for k in FIELDS})

def fd(a,b):
    return abs(a-b) if math.isfinite(a) and math.isfinite(b) else math.nan

def audit():
    m = active_market()
    if m is None:
        print("PARITY WAIT | no active contract", flush=True); return

    r = latest_unified_snapshot()
    if r is None:
        print("PARITY WAIT | unified tail empty", flush=True); return

    now = now_utc()
    st = r["_source_timestamp"]
    uc = str(r.get("contract","")).strip()
    ac = str(m.get("ticker","")).strip()
    age = (now-st).total_seconds()

    close = parse_dt(m.get("close_time"))
    rem = num(first(r,["seconds_left"]))
    if not math.isfinite(rem):
        ml = num(first(r,["minutes_left"]))
        rem = ml*60 if math.isfinite(ml) else math.nan
    api_rem = (close-st).total_seconds() if close else math.nan
    clock_delta = fd(rem,api_rem)

    target = market_target(m)
    btc, gap = num(first(r,["btc_price"])), num(first(r,["btc_gap"]))
    logged_target = btc-gap if math.isfinite(btc) and math.isfinite(gap) else math.nan
    target_delta = fd(logged_target,target)

    lupb,lupa = prob(first(r,["up_bid","yes_bid"])),prob(first(r,["up_ask","yes_ask"]))
    ldnb,ldna = prob(first(r,["down_bid","no_bid"])),prob(first(r,["down_ask","no_ask"]))
    aupb,aupa,adnb,adna = qv(m,"UP","bid"),qv(m,"UP","ask"),qv(m,"DOWN","bid"),qv(m,"DOWN","ask")
    qds = [fd(lupb,aupb),fd(lupa,aupa),fd(ldnb,adnb),fd(ldna,adna)]
    qds = [x for x in qds if math.isfinite(x)]
    qmax = max(qds) if qds else math.nan
    qsc = age <= QUOTE_MAX_AGE_SEC and len(qds)>=2

    api_brti, api_td = nearest_api_brti(direct_brti_payload(),st)
    bot_brti, bot_side, bot_gap, bot_td = nearest_logged_brti(st,target)
    tds = [x for x in [api_td,bot_td] if math.isfinite(x)]
    btd = max(tds) if tds else math.nan
    api_side = "UP" if math.isfinite(api_brti) and math.isfinite(target) and api_brti>=target else ("DOWN" if math.isfinite(api_brti) and math.isfinite(target) else "")
    bdelta = fd(bot_brti,api_brti)

    contract_ok = (uc==ac)
    clock_ok = math.isfinite(clock_delta) and clock_delta <= CLOCK_TOLERANCE_SEC
    target_ok = math.isfinite(target_delta) and target_delta <= TARGET_TOLERANCE_DOLLARS
    quote_ok = qsc and math.isfinite(qmax) and qmax <= QUOTE_TOLERANCE
    brti_ok = (
        math.isfinite(btd) and btd <= BRTI_TIME_TOLERANCE_SEC
        and math.isfinite(bdelta) and bdelta <= BRTI_VALUE_TOLERANCE_DOLLARS
        and bot_side in {"UP","DOWN"} and bot_side == api_side
    )
    scorable = age <= SOURCE_MAX_AGE_SEC and contract_ok and qsc and math.isfinite(bdelta) and math.isfinite(btd)
    status = "PASS" if scorable and clock_ok and target_ok and quote_ok and brti_ok else ("FAIL" if scorable else "WAIT")

    notes=[]
    if not contract_ok: notes.append("CONTRACT")
    if scorable and not clock_ok: notes.append("CLOCK")
    if scorable and not target_ok: notes.append("TARGET")
    if qsc and not quote_ok: notes.append("QUOTES")
    if scorable and not brti_ok: notes.append("BRTI")
    if not qsc: notes.append("QUOTE_STALE")
    if not scorable: notes.append("NOT_SCORABLE")

    append({
        "audit_timestamp_utc":now.isoformat(),
        "source_timestamp_utc":st.isoformat(),
        "source_age_sec":round(age,3),
        "unified_contract":uc,"api_contract":ac,"contract_match":contract_ok,
        "logged_remaining_sec":rem,"api_remaining_at_source_sec":api_rem,
        "clock_delta_sec":clock_delta,"clock_match":clock_ok,
        "logged_target_inferred":logged_target,"api_target":target,
        "target_delta":target_delta,"target_match":target_ok,
        "logged_up_bid":lupb,"api_up_bid":aupb,"logged_up_ask":lupa,"api_up_ask":aupa,
        "logged_down_bid":ldnb,"api_down_bid":adnb,"logged_down_ask":ldna,"api_down_ask":adna,
        "quote_max_delta":qmax,"quote_scorable":qsc,"quote_match":quote_ok,
        "logged_brti_gap":bot_gap,"logged_brti_side":bot_side,"logged_brti_value_inferred":bot_brti,
        "api_brti_value_near_source":api_brti,"api_brti_side_near_source":api_side,
        "brti_time_delta_sec":btd,"brti_value_delta":bdelta,"brti_match":brti_ok,
        "row_scorable":scorable,"overall_status":status,"notes":"|".join(notes),
    })

    qtxt = f"{qmax*100:.1f}c" if math.isfinite(qmax) else "N/A"
    btxt = f"${bdelta:.2f}" if math.isfinite(bdelta) else "N/A"
    print(
        f"PARITY {status} | {ac} | age {age:.1f}s | clock Δ{clock_delta:.1f}s | "
        f"target Δ${target_delta:.2f} | quotes Δ{qtxt} | BRTI Δ{btxt} @ {btd:.1f}s"
        + (f" | {'|'.join(notes)}" if notes else ""),
        flush=True
    )

def main():
    if "--self-test" in sys.argv:
        s = latest_unified_snapshot()
        print("PARITY LOW-MEM SELF-TEST")
        if s:
            vals=[prob(first(s,["up_bid"])),prob(first(s,["up_ask"])),prob(first(s,["down_bid"])),prob(first(s,["down_ask"]))]
            print("Reconstructed quotes:", sum(math.isfinite(x) for x in vals), "/ 4")
            if sum(math.isfinite(x) for x in vals) < 2:
                raise SystemExit("SELF-TEST FAIL")
        print("SELF-TEST: PASS")
        return 0

    print("BTC15 KALSHI/BRTI PARITY SHADOW V3 LOW-MEM: STARTING", flush=True)
    print("Bounded CSV tails only. NO ORDERS.", flush=True)
    while True:
        try: audit()
        except KeyboardInterrupt: break
        except Exception as e: print(f"PARITY WARNING | {type(e).__name__}: {e}", flush=True)
        time.sleep(POLL_SECONDS)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
