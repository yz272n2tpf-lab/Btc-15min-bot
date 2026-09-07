#!/usr/bin/env python3
"""
KALSHI BTC 15-MIN ENTRY TOURNAMENT V3 — HISTORICAL ACTUAL KALSHI PRICES
=======================================================================

Why V3
------
V2 correctly refused to prove an entry rule because live logs produced only
a handful of qualifying entries. V3 eliminates that bottleneck by downloading
Kalshi's own 1-minute historical YES bid/ask candlesticks for the same settled
KXBTC15M contracts used by the target-aware model.

This lets us test cheap-entry rules across ~hundreds of contracts in ONE run.

Integrity
---------
- Actual historical Kalshi YES bid/ask candlesticks, 1-minute interval.
- DOWN/NO ask derived from the complementary YES bid:
      NO ask = 1 - YES bid
- Official settlement labels from brti_calibration_results.csv.
- Same target-aware RF/sigmoid architecture as the working FINAL tournament.
- Chronology:
    50% RF training
    20% probability calibration
    15% ENTRY rule selection
    15% untouched ENTRY holdout
- Winner selected on validation only.
- Holdout is report-only.
- First qualifying entry per contract.
- Signal only. No orders. Does not modify bot.py.

Historical candlestick cache makes retries/resumes fast.
"""

from pathlib import Path
from datetime import datetime, timezone
from zoneinfo import ZoneInfo
import time, base64, re, json, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

CAL = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")
CANDLE_CACHE = Path("kalshi_kxbtc15m_1m_candles_cache.csv")
ALL_RESULTS = Path("entry_tournament_v3_all_results.csv")
SUMMARY = Path("entry_tournament_v3_summary.txt")
HOLDOUT_CALLS = Path("entry_tournament_v3_winner_holdout_calls.csv")
VALIDATION_CALLS = Path("entry_tournament_v3_winner_validation_calls.csv")

SERIES = "KXBTC15M"
HOSTS = [
    "https://api.elections.kalshi.com",
    "https://external-api.kalshi.com",
]

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

FEATURES = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5",
    "dist_per_min_remaining","dist_over_range5",
]

def load_auth():
    kid = Path.home()/".kalshi"/"key_id"
    key = Path.home()/".kalshi"/"private_key.pem"
    if not kid.exists() or not key.exists():
        raise SystemExit("Missing ~/.kalshi credentials. Read-only API access required.")
    key_id = kid.read_text().strip()
    private_key = serialization.load_pem_private_key(key.read_bytes(), password=None)
    return key_id, private_key

KEY_ID, PRIVATE_KEY = load_auth()

def headers(method, path):
    ts = str(int(time.time()*1000))
    msg = ts + method.upper() + path
    sig = PRIVATE_KEY.sign(
        msg.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }

def get_json(path, params=None):
    last = None
    for host in HOSTS:
        for attempt in range(3):
            try:
                r = requests.get(
                    host+path,
                    headers=headers("GET", path),
                    params=params,
                    timeout=15,
                )
                if r.status_code == 429:
                    time.sleep(0.75*(attempt+1))
                    continue
                if r.status_code in (400,404):
                    last = RuntimeError(f"{r.status_code} {r.text[:120]}")
                    break
                r.raise_for_status()
                return r.json()
            except Exception as e:
                last = e
                time.sleep(0.2*(attempt+1))
    raise last or RuntimeError("Kalshi GET failed")

def parse_contract_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper(),
    )
    if not m:
        return pd.NaT, pd.NaT
    yy, mon, dd, hh, mm = m.groups()
    wall = pd.Timestamp(
        year=2000+int(yy), month=MONTHS[mon], day=int(dd),
        hour=int(hh), minute=int(mm),
    )
    close_utc = wall.tz_localize(ZoneInfo("America/New_York")).tz_convert("UTC")
    return close_utc-pd.Timedelta(minutes=15), close_utc

def load_btc():
    try:
        d = pd.read_csv(BTC_CACHE, index_col="Datetime", parse_dates=True)
    except Exception:
        d = pd.read_csv(BTC_CACHE)
        ts_col = next(
            (c for c in ["Datetime","datetime","timestamp","Timestamp","time","Time"]
             if c in d.columns),
            d.columns[0],
        )
        d[ts_col] = pd.to_datetime(d[ts_col], errors="coerce", utc=True)
        d = d.dropna(subset=[ts_col]).set_index(ts_col)

    idx = pd.to_datetime(d.index, errors="coerce", utc=True)
    ok = ~pd.isna(idx)
    d = d.loc[ok].copy()
    d.index = idx[ok]
    rename = {}
    for want in ["Open","High","Low","Close","Volume"]:
        for c in d.columns:
            if str(c).lower() == want.lower():
                rename[c] = want
                break
    d = d.rename(columns=rename)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if not {"High","Low","Close"}.issubset(d.columns):
        raise SystemExit("BTC cache missing required OHLC columns")
    return d

def price_at_or_before(data, ts):
    i = data.index.searchsorted(ts, side="right")-1
    if i < 0:
        return np.nan, pd.NaT
    ti = data.index[i]
    if ts-ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT
    return float(data.iloc[i]["Close"]), ti

def build_snapshot(data, start, target, final_side, elapsed):
    cut = start + pd.Timedelta(minutes=float(elapsed))
    pstart, tstart = price_at_or_before(data, start)
    vals = [price_at_or_before(data, cut-pd.Timedelta(minutes=m))
            for m in [0,1,2,3,5]]
    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None
    p0,p1,p2,p3,p5 = [v[0] for v in vals]
    w = data.loc[
        (data.index > cut-pd.Timedelta(minutes=5)) & (data.index <= cut)
    ]
    if len(w) < 3:
        return None
    closes = w["Close"].dropna()
    if len(closes) < 2:
        return None

    current_side = int(p0 >= target)
    sign = 1.0 if current_side == 1 else -1.0
    dist = p0-target
    abs_dist = abs(dist)
    remaining = max(0.0, 15.0-float(elapsed))
    range5 = float(w["High"].max()-w["Low"].min())

    move1,move2,move3,move5 = p0-p1,p0-p2,p0-p3,p0-p5
    return {
        "elapsed":float(elapsed),
        "remaining":remaining,
        "current_side":current_side,
        "dist_target":float(dist),
        "abs_dist_target":float(abs_dist),
        "dist_target_pct":float(dist/target),
        "move_from_start":float(p0-pstart),
        "move_from_start_pct":float((p0-pstart)/pstart),
        "move1":float(move1),"move2":float(move2),
        "move3":float(move3),"move5":float(move5),
        "support1":float(move1*sign),"support2":float(move2*sign),
        "support3":float(move3*sign),"support5":float(move5*sign),
        "range5":range5,
        "vol5":float(closes.pct_change().std(ddof=0)),
        "dist_per_min_remaining":float(abs_dist/max(remaining,0.25)),
        "dist_over_range5":float(abs_dist/max(range5,1.0)),
        "final_side":int(final_side),
        "flip":int(int(final_side)!=current_side),
    }

def extract_dollar(obj, key="close"):
    if not isinstance(obj, dict):
        return np.nan
    # Historical API may use close or close_dollars.
    for k in [key, f"{key}_dollars"]:
        v = obj.get(k)
        try:
            if v is not None:
                return float(v)
        except Exception:
            pass
    return np.nan

def fetch_candles(ticker, start, close):
    start_ts = int(start.timestamp())
    end_ts = int(close.timestamp())

    paths = [
        f"/trade-api/v2/historical/markets/{ticker}/candlesticks",
        f"/trade-api/v2/series/{SERIES}/markets/{ticker}/candlesticks",
    ]
    params = {
        "start_ts":start_ts,
        "end_ts":end_ts,
        "period_interval":1,
    }
    last = None
    for path in paths:
        try:
            data = get_json(path, params=params)
            candles = data.get("candlesticks", [])
            if candles:
                rows = []
                for c in candles:
                    ts = pd.to_datetime(
                        c.get("end_period_ts"), unit="s", utc=True, errors="coerce"
                    )
                    yes_ask = extract_dollar(c.get("yes_ask", {}))
                    yes_bid = extract_dollar(c.get("yes_bid", {}))
                    if pd.isna(ts):
                        continue
                    no_ask = np.nan if pd.isna(yes_bid) else 1.0-yes_bid
                    rows.append({
                        "contract":ticker,
                        "candle_end_utc":ts,
                        "yes_ask":yes_ask,
                        "yes_bid":yes_bid,
                        "no_ask":no_ask,
                    })
                if rows:
                    return rows
        except Exception as e:
            last = e
    return []

def load_or_fetch_candles(contracts):
    cached = pd.DataFrame()
    if CANDLE_CACHE.exists():
        try:
            cached = pd.read_csv(CANDLE_CACHE)
            cached["candle_end_utc"] = pd.to_datetime(
                cached["candle_end_utc"], errors="coerce", utc=True
            )
        except Exception:
            cached = pd.DataFrame()

    done = set(cached["contract"].astype(str)) if not cached.empty else set()
    all_rows = cached.to_dict("records") if not cached.empty else []

    missing = contracts[~contracts["ticker"].isin(done)].copy()
    print(
        f"Kalshi 1m candle cache: {len(done)} contracts cached | "
        f"{len(missing)} to fetch"
    )

    for n, (_, r) in enumerate(missing.iterrows(), 1):
        rows = fetch_candles(r["ticker"], r["start"], r["close"])
        all_rows.extend(rows)
        if n % 25 == 0 or n == len(missing):
            pd.DataFrame(all_rows).to_csv(CANDLE_CACHE, index=False)
            print(f"  fetched {n}/{len(missing)} new contracts")
        time.sleep(0.04)

    c = pd.DataFrame(all_rows)
    if c.empty:
        raise SystemExit("No Kalshi historical candles retrieved")
    c["candle_end_utc"] = pd.to_datetime(c["candle_end_utc"], errors="coerce", utc=True)
    for col in ["yes_ask","yes_bid","no_ask"]:
        c[col] = pd.to_numeric(c[col], errors="coerce")
    c = c.dropna(subset=["contract","candle_end_utc"])
    c = c.sort_values(["contract","candle_end_utc"]).drop_duplicates(
        ["contract","candle_end_utc"], keep="last"
    )
    c.to_csv(CANDLE_CACHE, index=False)
    return c

def main():
    print("="*78)
    print("ENTRY TOURNAMENT V3 — HISTORICAL ACTUAL KALSHI 1-MIN PRICES")
    print("OFFLINE BATCH — OFFICIAL SETTLEMENT — SIGNAL ONLY — NO ORDERS")
    print("="*78)

    cal = pd.read_csv(CAL)
    need = {"ticker","target_brti","result"}
    if not need.issubset(cal.columns):
        raise SystemExit(f"{CAL} missing {sorted(need-set(cal.columns))}")

    pairs = cal["ticker"].map(parse_contract_times)
    cal["start"] = [p[0] for p in pairs]
    cal["close"] = [p[1] for p in pairs]
    cal["target_brti"] = pd.to_numeric(cal["target_brti"], errors="coerce")
    cal["final_side"] = cal["result"].astype(str).str.lower().map({"yes":1,"no":0})
    cal = cal.dropna(
        subset=["ticker","start","close","target_brti","final_side"]
    ).sort_values("start").drop_duplicates("ticker", keep="last").reset_index(drop=True)

    btc = load_btc()

    # Historical BTC features first.
    rows = []
    print(f"Building target-aware BTC snapshots: {len(cal)} contracts")
    for i, r in cal.iterrows():
        for elapsed in range(1,15):
            s = build_snapshot(
                btc, r["start"], float(r["target_brti"]),
                int(r["final_side"]), elapsed
            )
            if s is not None:
                s["ticker"] = r["ticker"]
                s["start"] = r["start"]
                s["snapshot_utc"] = r["start"] + pd.Timedelta(minutes=elapsed)
                rows.append(s)
        if (i+1)%100 == 0:
            print(f"  BTC features {i+1}/{len(cal)}")

    hist = pd.DataFrame(rows)
    cov = hist.groupby("ticker")["elapsed"].nunique()
    keep = cov[cov>=10].index
    hist = hist[hist["ticker"].isin(keep)].copy()

    contracts = (
        hist[["ticker","start"]].drop_duplicates().sort_values("start").reset_index(drop=True)
    )
    n = len(contracts)
    if n < 100:
        raise SystemExit(f"Only {n} usable contracts; need >=100")

    i1,i2,i3 = int(n*.50),int(n*.70),int(n*.85)
    model_c = contracts.iloc[:i1]
    calib_c = contracts.iloc[i1:i2]
    valid_c = contracts.iloc[i2:i3]
    hold_c = contracts.iloc[i3:]

    print(
        f"Chronology: model {len(model_c)} | calibration {len(calib_c)} | "
        f"entry validation {len(valid_c)} | untouched holdout {len(hold_c)}"
    )

    rf_train = hist[hist["ticker"].isin(set(model_c["ticker"]))].copy()
    sigmoid_cal = hist[hist["ticker"].isin(set(calib_c["ticker"]))].copy()

    rf = RandomForestClassifier(
        n_estimators=900,max_depth=9,min_samples_leaf=12,
        class_weight="balanced",random_state=42,n_jobs=-1,
    )
    print("Training target-aware fair model once...")
    rf.fit(rf_train[FEATURES], rf_train["flip"])

    raw_cal = rf.predict_proba(sigmoid_cal[FEATURES])[:,1]
    sigmoid = LogisticRegression(
        solver="lbfgs",C=1.0,max_iter=1000,random_state=42
    )
    sigmoid.fit(raw_cal.reshape(-1,1), sigmoid_cal["flip"].astype(int))

    test = hist[hist["ticker"].isin(
        set(valid_c["ticker"])|set(hold_c["ticker"])
    )].copy()
    raw = rf.predict_proba(test[FEATURES])[:,1]
    flip = sigmoid.predict_proba(raw.reshape(-1,1))[:,1]
    flip = np.clip(flip,.001,.999)
    test["fair_up"] = np.where(test["current_side"]==1,1-flip,flip)
    test["fair_down"] = 1-test["fair_up"]
    test["preferred_side_num"] = np.where(test["fair_up"]>=test["fair_down"],1,0)
    test["preferred_side"] = np.where(test["preferred_side_num"]==1,"UP","DOWN")
    test["preferred_fair"] = np.maximum(test["fair_up"],test["fair_down"])

    candle_contracts = cal[cal["ticker"].isin(set(test["ticker"]))][
        ["ticker","start","close"]
    ].copy()
    candles = load_or_fetch_candles(candle_contracts)
    print(
        f"Historical candle cache loaded: "
        f"{candles['contract'].nunique()} contracts | "
        f"{len(candles)} one-minute candles"
    )
    print("Timestamp alignment preflight: normalizing both join keys to datetime64[ns, UTC]")

    # Join each minute snapshot to the nearest candle ending at/before snapshot,
    # max 90 seconds stale.
    merged_parts = []
    for ticker, g in test.groupby("ticker", sort=False):
        cg = candles[candles["contract"]==ticker].sort_values("candle_end_utc").copy()
        if cg.empty:
            continue
        gg = g.sort_values("snapshot_utc").copy()

        # V3.1 alignment fix:
        # pandas merge_asof requires the two datetime keys to have the exact
        # same internal resolution. Historical Kalshi candles can arrive as
        # datetime64[s, UTC] while BTC snapshot timestamps are datetime64[us, UTC].
        # Normalize BOTH explicitly to nanosecond UTC before joining.
        gg["snapshot_utc"] = (
            pd.to_datetime(gg["snapshot_utc"], errors="coerce", utc=True)
            .astype("datetime64[ns, UTC]")
        )
        cg["candle_end_utc"] = (
            pd.to_datetime(cg["candle_end_utc"], errors="coerce", utc=True)
            .astype("datetime64[ns, UTC]")
        )
        gg = gg.dropna(subset=["snapshot_utc"]).sort_values("snapshot_utc")
        cg = cg.dropna(subset=["candle_end_utc"]).sort_values("candle_end_utc")

        m = pd.merge_asof(
            gg,
            cg[["candle_end_utc","yes_ask","yes_bid","no_ask"]],
            left_on="snapshot_utc",
            right_on="candle_end_utc",
            direction="backward",
            tolerance=pd.Timedelta(seconds=90),
        )
        merged_parts.append(m)

    if not merged_parts:
        raise SystemExit("No BTC snapshots aligned to Kalshi candles")

    d = pd.concat(merged_parts, ignore_index=True)
    d["preferred_ask"] = np.where(
        d["preferred_side_num"]==1,d["yes_ask"],d["no_ask"]
    )
    d["edge"] = d["preferred_fair"]-d["preferred_ask"]
    d = d[
        d["preferred_ask"].between(0.001,0.999)
        & d["edge"].notna()
    ].copy()

    # Generic sequence features.
    seq_parts = []
    for ticker, g in d.groupby("ticker", sort=False):
        g = g.sort_values("elapsed").copy()
        prev_side = None
        streak = 0
        prev_fair = np.nan
        prev_edge = np.nan
        streaks=[]
        strengthens=[]
        for _,r in g.iterrows():
            side = r["preferred_side"]
            if side==prev_side:
                streak+=1
            else:
                streak=1
            strengths = bool(
                side==prev_side and pd.notna(prev_fair) and pd.notna(prev_edge)
                and r["preferred_fair"]>=prev_fair and r["edge"]>=prev_edge
            )
            streaks.append(streak)
            strengthens.append(strengths)
            prev_side=side
            prev_fair=r["preferred_fair"]
            prev_edge=r["edge"]
        g["streak"]=streaks
        g["strengthening"]=strengthens
        seq_parts.append(g)
    d = pd.concat(seq_parts, ignore_index=True)

    valid = d[d["ticker"].isin(set(valid_c["ticker"]))].copy()
    hold = d[d["ticker"].isin(set(hold_c["ticker"]))].copy()

    ask_grid=[.25,.30,.35,.40,.45,.50]
    fair_grid=[.60,.65,.70,.75,.80,.85]
    edge_grid=[.08,.10,.12,.15,.20,.25]
    min_tl_grid=[2.,4.,6.,8.,10.]
    max_tl_grid=[10.,12.,14.]
    gap_grid=[0.,25.,50.,75.,100.]
    ratio_grid=[0.,.5,1.]
    persist_grid=[1,2]
    strengthen_grid=[False,True]
    side_agree_grid=[False,True]

    total=(len(ask_grid)*len(fair_grid)*len(edge_grid)*len(min_tl_grid)*
           len(max_tl_grid)*len(gap_grid)*len(ratio_grid)*len(persist_grid)*
           len(strengthen_grid)*len(side_agree_grid))
    print(f"Running ENTRY tournament: {total:,} combinations...")

    def score(frame,p):
        mask=(
            (frame["preferred_ask"]<=p["ask_max"])&
            (frame["preferred_fair"]>=p["fair_min"])&
            (frame["edge"]>=p["edge_min"])&
            (frame["remaining"]>=p["min_tl"])&
            (frame["remaining"]<=p["max_tl"])&
            (frame["abs_dist_target"]>=p["min_gap"])&
            (frame["dist_over_range5"]>=p["min_ratio"])&
            (frame["streak"]>=p["persistence"])
        )
        if p["strengthening"]:
            mask &= frame["strengthening"]
        if p["side_agree"]:
            mask &= frame["preferred_side_num"]==frame["current_side"]

        q=frame[mask].sort_values(["ticker","elapsed"])
        if q.empty:
            return None,pd.DataFrame()
        first=q.groupby("ticker",as_index=False).first()
        first["correct"]=first["preferred_side_num"].astype(int)==first["final_side"].astype(int)
        return {
            **p,
            "calls":len(first),
            "contracts":frame["ticker"].nunique(),
            "coverage":len(first)/max(frame["ticker"].nunique(),1),
            "accuracy":float(first["correct"].mean()),
            "avg_ask":float(first["preferred_ask"].mean()),
            "median_ask":float(first["preferred_ask"].median()),
            "avg_time_left":float(first["remaining"].mean()),
            "median_time_left":float(first["remaining"].median()),
            "avg_fair":float(first["preferred_fair"].mean()),
            "avg_edge":float(first["edge"].mean()),
        },first

    results=[]
    for ask_max in ask_grid:
      for fair_min in fair_grid:
       for edge_min in edge_grid:
        for min_tl in min_tl_grid:
         for max_tl in max_tl_grid:
          if min_tl>max_tl: continue
          for min_gap in gap_grid:
           for min_ratio in ratio_grid:
            for persistence in persist_grid:
             for strengthening in strengthen_grid:
              for side_agree in side_agree_grid:
               p=dict(
                   ask_max=ask_max,fair_min=fair_min,edge_min=edge_min,
                   min_tl=min_tl,max_tl=max_tl,min_gap=min_gap,
                   min_ratio=min_ratio,persistence=persistence,
                   strengthening=strengthening,side_agree=side_agree,
               )
               s,_=score(valid,p)
               if s is not None:
                   results.append(s)

    res=pd.DataFrame(results)
    if res.empty:
        raise SystemExit("No validation entry rules produced calls")

    min_calls=max(8,int(np.ceil(valid_c.shape[0]*.10)))
    eligible=res[res["calls"]>=min_calls].copy()
    if eligible.empty:
        eligible=res[res["calls"]>=5].copy()
    if eligible.empty:
        eligible=res.copy()

    # Accuracy first. Price/timing never compensates for lower accuracy.
    eligible=eligible.sort_values(
        ["accuracy","coverage","avg_time_left","avg_ask","calls"],
        ascending=[False,False,False,True,False]
    ).reset_index(drop=True)
    eligible["validation_rank"]=np.arange(1,len(eligible)+1)
    eligible.to_csv(ALL_RESULTS,index=False)

    keys=[
        "ask_max","fair_min","edge_min","min_tl","max_tl","min_gap",
        "min_ratio","persistence","strengthening","side_agree"
    ]
    winner={k:eligible.iloc[0][k] for k in keys}
    vscore,vcalls=score(valid,winner)
    hscore,hcalls=score(hold,winner)

    if not vcalls.empty: vcalls.to_csv(VALIDATION_CALLS,index=False)
    if not hcalls.empty: hcalls.to_csv(HOLDOUT_CALLS,index=False)

    def pct(x): return "N/A" if x is None or pd.isna(x) else f"{100*x:.1f}%"

    lines=[]
    lines.append("="*78)
    lines.append("ENTRY TOURNAMENT V3 SUMMARY")
    lines.append("="*78)
    lines.append("")
    lines.append("WINNER — SELECTED ON VALIDATION ONLY")
    for k in keys: lines.append(f"{k}: {winner[k]}")
    lines.append("")
    lines.append(
        f"Validation: accuracy {pct(vscore['accuracy'])} | "
        f"calls {vscore['calls']}/{vscore['contracts']} ({pct(vscore['coverage'])}) | "
        f"avg ask {100*vscore['avg_ask']:.1f}c | avg time left {vscore['avg_time_left']:.2f}m"
    )
    lines.append("")
    lines.append("UNTOUCHED HOLDOUT")
    if hscore is None:
        lines.append("Winner produced no holdout calls.")
    else:
        lines.append(
            f"Accuracy {pct(hscore['accuracy'])} | "
            f"calls {hscore['calls']}/{hscore['contracts']} ({pct(hscore['coverage'])}) | "
            f"avg ask {100*hscore['avg_ask']:.1f}c | median ask {100*hscore['median_ask']:.1f}c"
        )
        lines.append(
            f"Avg time left {hscore['avg_time_left']:.2f}m | "
            f"median time left {hscore['median_time_left']:.2f}m | "
            f"avg fair {pct(hscore['avg_fair'])} | avg edge {pct(hscore['avg_edge'])}"
        )
    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Actual Kalshi 1-minute historical YES bid/ask")
    lines.append("- Official settlement labels")
    lines.append("- Chronological 50/20/15/15 split")
    lines.append("- Winner chosen without holdout")
    lines.append("- First qualifying entry per contract")
    lines.append("- No orders; bot.py unchanged")
    lines.append("")
    lines.append("NOTE: Historical Kalshi candles are 1-minute resolution.")
    lines.append("Sub-minute timing must still be smoke-tested live.")
    lines.append("")
    lines.append("FILES WRITTEN")
    lines.append(str(CANDLE_CACHE))
    lines.append(str(ALL_RESULTS))
    lines.append(str(VALIDATION_CALLS))
    lines.append(str(HOLDOUT_CALLS))
    lines.append(str(SUMMARY))

    summary="\n".join(lines)
    SUMMARY.write_text(summary)
    print("\n"+summary)

if __name__=="__main__":
    main()
