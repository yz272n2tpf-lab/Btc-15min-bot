#!/usr/bin/env python3
"""
KALSHI BTC15 FRESH OUT-OF-SAMPLE VALIDATOR V1.1.1
==============================================

Purpose
-------
Validate fixed, already-defined rules on settled KXBTC15M contracts that occur
AFTER the old brti_calibration_results.csv dataset.

This is intentionally NOT an optimizer. It does not search thresholds on the
fresh set. It scores four fixed rules:

1) EARLY_P40_NEW
   ask <= 40c
   fair >= 75%
   edge >= 20%
   4-10 minutes left
   abs target gap >= $25

2) EARLY_P45_PROVISIONAL
   ask <= 45c
   fair >= 75%
   edge >= 20%
   4-10 minutes left
   abs target gap >= $25

3) LOCKED_TIER1
   ask <= 45c
   fair >= 75%
   edge >= 8%
   2-10 minutes left
   abs target gap >= $25

4) LOCKED_FINAL_BASELINE
   fair >= 90%
   <= 8 minutes left
   preferred fair side == current target side
   if >6m left: abs target gap >= $75
   if <=6m left: abs target gap >= $50
   dist/range5 >= 1.0

Fresh truth:
- Official Kalshi market.result (yes/no)
- Kalshi market floor_strike / target
- Actual Kalshi 1-minute YES bid/ask candles
- NO ask = 1 - YES bid
- Existing Coinbase 1-minute BTC cache for model features

Model:
- Same target-aware RF + chronological sigmoid calibration used by the
  validated entry/final research.
- RF trained on first 50% of old official dataset.
- Sigmoid calibrated on next 20%.
- Fresh contracts are never used for model fitting.

Outputs
-------
fresh_oos_summary.txt
fresh_oos_early_p40_calls.csv
fresh_oos_early_p45_calls.csv
fresh_oos_locked_tier1_calls.csv
fresh_oos_locked_final_calls.csv
fresh_oos_market_manifest.csv
fresh_oos_candles_cache.csv

Signal-only research. No orders. Does not modify bot.py.
"""

from pathlib import Path
from zoneinfo import ZoneInfo
import re, time, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
import requests
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

CAL = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")
FRESH_CANDLE_CACHE = Path("fresh_oos_candles_cache.csv")
SUMMARY = Path("fresh_oos_summary.txt")
MANIFEST = Path("fresh_oos_market_manifest.csv")

SERIES = "KXBTC15M"
BASE = "https://external-api.kalshi.com/trade-api/v2"
MAX_FRESH_CONTRACTS = 250

FEATURES = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5",
    "dist_per_min_remaining","dist_over_range5",
]

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

RULES = {
    "EARLY_P40_NEW": dict(
        ask_max=.40, fair_min=.75, edge_min=.20,
        min_tl=4., max_tl=10., min_gap=25.,
    ),
    "EARLY_P45_PROVISIONAL": dict(
        ask_max=.45, fair_min=.75, edge_min=.20,
        min_tl=4., max_tl=10., min_gap=25.,
    ),
    "LOCKED_TIER1": dict(
        ask_max=.45, fair_min=.75, edge_min=.08,
        min_tl=2., max_tl=10., min_gap=25.,
    ),
}

def get_json(path, params=None, tries=4):
    last = None
    for attempt in range(tries):
        try:
            r = requests.get(BASE + path, params=params, timeout=20)
            if r.status_code == 429:
                time.sleep(.7 * (attempt+1))
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last = e
            time.sleep(.3 * (attempt+1))
    raise last or RuntimeError(f"GET failed: {path}")

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
    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")
    return close_utc-pd.Timedelta(minutes=15), close_utc

def load_btc():
    d = pd.read_csv(BTC_CACHE)
    ts_col = next(
        (c for c in ["Datetime","datetime","timestamp","Timestamp","time","Time"]
         if c in d.columns),
        d.columns[0],
    )
    d[ts_col] = pd.to_datetime(d[ts_col], errors="coerce", utc=True)
    d = d.dropna(subset=[ts_col]).set_index(ts_col)
    rename = {}
    for want in ["Open","High","Low","Close","Volume"]:
        for c in d.columns:
            if str(c).lower() == want.lower():
                rename[c] = want
                break
    d = d.rename(columns=rename)
    d = d[~d.index.duplicated(keep="last")].sort_index()
    if not {"High","Low","Close"}.issubset(d.columns):
        raise SystemExit("BTC cache missing OHLC columns.")
    return d

def price_at_or_before(data, ts):
    i = data.index.searchsorted(ts, side="right") - 1
    if i < 0:
        return np.nan, pd.NaT
    ti = data.index[i]
    if ts-ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT
    return float(data.iloc[i]["Close"]), ti

def build_snapshot(data, start, target, final_side, elapsed):
    cut = start + pd.Timedelta(minutes=float(elapsed))
    pstart, _ = price_at_or_before(data, start)
    vals = [
        price_at_or_before(data, cut-pd.Timedelta(minutes=m))
        for m in [0,1,2,3,5]
    ]
    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,p2,p3,p5 = [v[0] for v in vals]
    w = data.loc[
        (data.index > cut-pd.Timedelta(minutes=5))
        & (data.index <= cut)
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
    remaining = max(0., 15.-float(elapsed))
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
        "dist_per_min_remaining":float(abs_dist/max(remaining,.25)),
        "dist_over_range5":float(abs_dist/max(range5,1.0)),
        "final_side":int(final_side),
        "flip":int(int(final_side)!=current_side),
    }

def target_from_market(m):
    for key in ["floor_strike","functional_strike","cap_strike"]:
        v = m.get(key)
        try:
            x = float(str(v).replace(",","").replace("$",""))
            if x > 1000:
                return x
        except Exception:
            pass

    text = " ".join(str(m.get(k,"")) for k in [
        "yes_sub_title","subtitle","title","rules_primary"
    ])
    nums = re.findall(r"\$?\s*([0-9]{2,3}(?:,[0-9]{3})+(?:\.\d+)?)", text)
    vals = []
    for s in nums:
        try:
            x = float(s.replace(",",""))
            if x > 1000:
                vals.append(x)
        except Exception:
            pass
    return vals[0] if vals else None

def load_old_calibration():
    cal = pd.read_csv(CAL)
    cal["target_brti"] = pd.to_numeric(cal["target_brti"], errors="coerce")
    cal["final_brti"] = pd.to_numeric(cal["final_brti"], errors="coerce")
    cal = cal.dropna(subset=["target_brti","final_brti"]).copy()
    cal["final_side"] = (cal["final_brti"] >= cal["target_brti"]).astype(int)
    parsed = cal["ticker"].apply(parse_contract_times)
    cal["start"] = [x[0] for x in parsed]
    cal["close"] = [x[1] for x in parsed]
    return cal.dropna(subset=["start","close"]).sort_values("start").reset_index(drop=True)

def fetch_fresh_markets(old_cutoff, btc_max):
    min_settled = int((old_cutoff + pd.Timedelta(seconds=1)).timestamp())
    cursor = None
    rows = []

    for _ in range(5):
        params = {
            "limit":1000,
            "series_ticker":SERIES,
            "status":"settled",
            "min_settled_ts":min_settled,
        }
        if cursor:
            params["cursor"] = cursor
        obj = get_json("/markets", params=params)
        rows.extend(obj.get("markets", []))
        cursor = obj.get("cursor")
        if not cursor:
            break

    out = []
    for m in rows:
        ticker = m.get("ticker")
        if not ticker or not str(ticker).startswith(SERIES):
            continue

        result = str(m.get("result","")).lower()
        if result not in ("yes","no"):
            continue

        target = target_from_market(m)
        if target is None:
            continue

        start, close = parse_contract_times(ticker)
        if pd.isna(start) or pd.isna(close):
            continue
        if close > btc_max + pd.Timedelta(minutes=1):
            continue
        if close <= old_cutoff:
            continue

        out.append({
            "ticker":ticker,
            "target":float(target),
            "final_side":1 if result=="yes" else 0,
            "result":result,
            "start":start,
            "close":close,
            "settlement_value":m.get("settlement_value_dollars"),
        })

    fresh = pd.DataFrame(out).drop_duplicates("ticker")
    fresh = fresh.sort_values("start").reset_index(drop=True)

    if len(fresh) > MAX_FRESH_CONTRACTS:
        # Use the most recent contracts that still fit the local BTC cache.
        fresh = fresh.iloc[-MAX_FRESH_CONTRACTS:].reset_index(drop=True)

    return fresh

def dollar_close(obj):
    if not isinstance(obj, dict):
        return np.nan
    for k in ["close_dollars","close"]:
        v = obj.get(k)
        try:
            if v is not None:
                return float(v)
        except Exception:
            pass
    return np.nan

def fetch_batch_candles(fresh):
    cached = pd.DataFrame()
    if FRESH_CANDLE_CACHE.exists():
        try:
            cached = pd.read_csv(FRESH_CANDLE_CACHE)
            cached["candle_end_utc"] = pd.to_datetime(
                cached["candle_end_utc"], errors="coerce", utc=True
            )
        except Exception:
            cached = pd.DataFrame()

    have = set(cached["contract"]) if not cached.empty else set()
    need = fresh[~fresh["ticker"].isin(have)].copy()

    new_rows = []
    tickers = need["ticker"].tolist()
    for i in range(0, len(tickers), 20):
        chunk = tickers[i:i+20]
        sub = fresh[fresh["ticker"].isin(chunk)]
        start_ts = int(sub["start"].min().timestamp()) - 60
        end_ts = int(sub["close"].max().timestamp()) + 60

        print(
            f"  Kalshi batch candles "
            f"{i+1}-{min(i+len(chunk),len(tickers))}/{len(tickers)}"
        )
        try:
            obj = get_json(
                "/markets/candlesticks",
                params={
                    "market_tickers":",".join(chunk),
                    "start_ts":start_ts,
                    "end_ts":end_ts,
                    "period_interval":1,
                },
            )
            batch_markets = obj.get("markets", [])
        except Exception as batch_exc:
            print(
                "    Batch rejected; falling back to single-market candles:",
                type(batch_exc).__name__,
            )
            batch_markets = []
            for ticker in chunk:
                rr = sub[sub["ticker"] == ticker]
                if rr.empty:
                    continue
                r0 = rr.iloc[0]
                one_start = int(r0["start"].timestamp()) - 60
                one_end = int(r0["close"].timestamp()) + 60
                try:
                    one = get_json(
                        f"/series/{SERIES}/markets/{ticker}/candlesticks",
                        params={
                            "start_ts":one_start,
                            "end_ts":one_end,
                            "period_interval":1,
                        },
                    )
                    batch_markets.append({
                        "market_ticker":ticker,
                        "candlesticks":one.get("candlesticks", []),
                    })
                except Exception as one_exc:
                    print(
                        f"      candle fetch failed for {ticker}: "
                        f"{type(one_exc).__name__}"
                    )
                time.sleep(.06)

        for market in batch_markets:
            ticker = market.get("market_ticker") or market.get("ticker")
            for c in market.get("candlesticks", []):
                ts = pd.to_datetime(
                    c.get("end_period_ts"),
                    unit="s", utc=True, errors="coerce",
                )
                if pd.isna(ts):
                    continue
                ya = dollar_close(c.get("yes_ask", {}))
                yb = dollar_close(c.get("yes_bid", {}))
                no_ask = np.nan if pd.isna(yb) else 1.0-yb
                new_rows.append({
                    "contract":ticker,
                    "candle_end_utc":ts,
                    "yes_ask":ya,
                    "yes_bid":yb,
                    "no_ask":no_ask,
                })
        time.sleep(.10)

    if new_rows:
        new = pd.DataFrame(new_rows)
        candles = pd.concat([cached,new], ignore_index=True)
        candles = candles.drop_duplicates(
            ["contract","candle_end_utc"], keep="last"
        ).sort_values(["contract","candle_end_utc"])
        candles.to_csv(FRESH_CANDLE_CACHE, index=False)
    else:
        candles = cached

    return candles

def train_model(old_cal, btc):
    rows = []
    for _,r in old_cal.iterrows():
        for elapsed in range(1,15):
            s = build_snapshot(
                btc, r["start"], r["target_brti"],
                r["final_side"], elapsed
            )
            if s is not None:
                s["ticker"] = r["ticker"]
                s["start"] = r["start"]
                rows.append(s)

    hist = pd.DataFrame(rows)
    cov = hist.groupby("ticker")["elapsed"].nunique()
    keep = set(cov[cov>=10].index)
    hist = hist[hist["ticker"].isin(keep)].copy()

    contracts = (
        hist[["ticker","start"]]
        .drop_duplicates()
        .sort_values("start")
        .reset_index(drop=True)
    )
    n = len(contracts)
    i1,i2 = int(n*.50),int(n*.70)
    model_c = set(contracts.iloc[:i1]["ticker"])
    calib_c = set(contracts.iloc[i1:i2]["ticker"])

    rf_train = hist[hist["ticker"].isin(model_c)]
    sigmoid_cal = hist[hist["ticker"].isin(calib_c)]

    print(
        f"Training preserved target-aware model: "
        f"{len(model_c)} RF contracts + {len(calib_c)} calibration"
    )
    rf = RandomForestClassifier(
        n_estimators=900,
        max_depth=9,
        min_samples_leaf=12,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    rf.fit(rf_train[FEATURES], rf_train["flip"])

    raw_cal = rf.predict_proba(sigmoid_cal[FEATURES])[:,1]
    sig = LogisticRegression(
        solver="lbfgs", C=1.0, max_iter=1000, random_state=42
    )
    sig.fit(raw_cal.reshape(-1,1), sigmoid_cal["flip"].astype(int))
    return rf,sig

def build_fresh_features(fresh, btc, rf, sig):
    rows = []
    for _,r in fresh.iterrows():
        for elapsed in range(1,15):
            s = build_snapshot(
                btc, r["start"], r["target"],
                r["final_side"], elapsed
            )
            if s is not None:
                s["ticker"] = r["ticker"]
                s["start"] = r["start"]
                s["snapshot_utc"] = (
                    r["start"] + pd.Timedelta(minutes=elapsed)
                )
                rows.append(s)

    x = pd.DataFrame(rows)
    if x.empty:
        raise SystemExit("No fresh BTC features built.")

    raw = rf.predict_proba(x[FEATURES])[:,1]
    flip = sig.predict_proba(raw.reshape(-1,1))[:,1]
    flip = np.clip(flip,.001,.999)

    x["fair_up"] = np.where(x["current_side"]==1,1-flip,flip)
    x["fair_down"] = 1-x["fair_up"]
    x["preferred_side_num"] = np.where(
        x["fair_up"]>=x["fair_down"],1,0
    )
    x["preferred_side"] = np.where(
        x["preferred_side_num"]==1,"UP","DOWN"
    )
    x["preferred_fair"] = np.maximum(x["fair_up"],x["fair_down"])
    return x

def align_prices(features, candles):
    parts = []
    for ticker,g in features.groupby("ticker", sort=False):
        cg = candles[candles["contract"]==ticker].copy()
        if cg.empty:
            continue

        gg = g.copy()
        gg["snapshot_utc"] = (
            pd.to_datetime(gg["snapshot_utc"], utc=True)
            .astype("datetime64[ns, UTC]")
        )
        cg["candle_end_utc"] = (
            pd.to_datetime(cg["candle_end_utc"], utc=True)
            .astype("datetime64[ns, UTC]")
        )

        gg = gg.sort_values("snapshot_utc")
        cg = cg.sort_values("candle_end_utc")

        m = pd.merge_asof(
            gg,
            cg[["candle_end_utc","yes_ask","yes_bid","no_ask"]],
            left_on="snapshot_utc",
            right_on="candle_end_utc",
            direction="backward",
            tolerance=pd.Timedelta(seconds=90),
        )
        parts.append(m)

    if not parts:
        raise SystemExit("No fresh snapshots aligned to Kalshi candles.")

    d = pd.concat(parts, ignore_index=True)
    d["preferred_ask"] = np.where(
        d["preferred_side_num"]==1,
        d["yes_ask"], d["no_ask"]
    )
    d["edge"] = d["preferred_fair"]-d["preferred_ask"]
    d = d[
        d["preferred_ask"].between(.001,.999)
        & d["edge"].notna()
    ].copy()
    return d

def score_entry(frame, p, name):
    mask = (
        (frame["preferred_ask"]<=p["ask_max"])
        & (frame["preferred_fair"]>=p["fair_min"])
        & (frame["edge"]>=p["edge_min"])
        & (frame["remaining"]>=p["min_tl"])
        & (frame["remaining"]<=p["max_tl"])
        & (frame["abs_dist_target"]>=p["min_gap"])
    )
    q = (
        frame[mask]
        .sort_values(["ticker","elapsed"])
        .groupby("ticker",as_index=False)
        .first()
    )
    if q.empty:
        return None,q
    q["correct"] = (
        q["preferred_side_num"].astype(int)
        == q["final_side"].astype(int)
    )
    score = {
        "name":name,
        "calls":len(q),
        "contracts":frame["ticker"].nunique(),
        "coverage":len(q)/max(frame["ticker"].nunique(),1),
        "accuracy":float(q["correct"].mean()),
        "avg_ask":float(q["preferred_ask"].mean()),
        "median_ask":float(q["preferred_ask"].median()),
        "pct_le40":float((q["preferred_ask"]<=.40).mean()),
        "pct_20_40":float(q["preferred_ask"].between(.20,.40).mean()),
        "avg_time_left":float(q["remaining"].mean()),
        "median_time_left":float(q["remaining"].median()),
        "avg_fair":float(q["preferred_fair"].mean()),
    }
    return score,q

def score_final(frame):
    early = frame["remaining"] > 6.0
    required_gap = np.where(early,75.0,50.0)
    mask = (
        (frame["preferred_fair"]>=.90)
        & (frame["remaining"]<=8.0)
        & (frame["abs_dist_target"]>=required_gap)
        & (frame["dist_over_range5"]>=1.0)
        & (frame["preferred_side_num"]==frame["current_side"])
    )
    q = (
        frame[mask]
        .sort_values(["ticker","elapsed"])
        .groupby("ticker",as_index=False)
        .first()
    )
    if q.empty:
        return None,q
    q["correct"] = (
        q["preferred_side_num"].astype(int)
        == q["final_side"].astype(int)
    )
    score = {
        "name":"LOCKED_FINAL_BASELINE",
        "calls":len(q),
        "contracts":frame["ticker"].nunique(),
        "coverage":len(q)/max(frame["ticker"].nunique(),1),
        "accuracy":float(q["correct"].mean()),
        "avg_time_left":float(q["remaining"].mean()),
        "median_time_left":float(q["remaining"].median()),
        "pct_5m_plus":float((q["remaining"]>=5.).mean()),
        "avg_fair":float(q["preferred_fair"].mean()),
    }
    return score,q

def fmt_pct(x):
    return "N/A" if x is None else f"{100*x:.1f}%"

def main():
    if not CAL.exists() or not BTC_CACHE.exists():
        raise SystemExit(
            "Need brti_calibration_results.csv and btc_35d_live_cache.csv "
            "in the project root."
        )

    btc = load_btc()
    old = load_old_calibration()
    old_cutoff = old["close"].max()
    btc_max = btc.index.max()

    print("="*76)
    print("BTC15 FRESH OUT-OF-SAMPLE VALIDATOR V1.1")
    print("="*76)
    print("Old dataset ends:", old_cutoff)
    print("BTC cache ends:", btc_max)
    print("Fetching newer official settled KXBTC15M markets...")

    fresh = fetch_fresh_markets(old_cutoff, btc_max)
    if len(fresh) < 30:
        raise SystemExit(
            f"Only {len(fresh)} fresh usable contracts found. "
            "Need at least 30 for a useful fresh check."
        )

    print(
        f"Fresh contracts: {len(fresh)} | "
        f"{fresh['start'].min()} through {fresh['close'].max()}"
    )
    fresh.to_csv(MANIFEST,index=False)

    candles = fetch_batch_candles(fresh)
    usable_candles = candles[
        candles["contract"].isin(set(fresh["ticker"]))
    ]
    print(
        f"Fresh Kalshi candles: {len(usable_candles):,} | "
        f"{usable_candles['contract'].nunique()} contracts"
    )

    rf,sig = train_model(old,btc)
    features = build_fresh_features(fresh,btc,rf,sig)
    priced = align_prices(features,candles)

    print(
        f"Priced fresh feature set: {len(priced):,} snapshots | "
        f"{priced['ticker'].nunique()} contracts"
    )

    results = []
    for name,p in RULES.items():
        score,calls = score_entry(priced,p,name)
        if score:
            results.append(score)
            calls.to_csv(
                {
                    "EARLY_P40_NEW":"fresh_oos_early_p40_calls.csv",
                    "EARLY_P45_PROVISIONAL":"fresh_oos_early_p45_calls.csv",
                    "LOCKED_TIER1":"fresh_oos_locked_tier1_calls.csv",
                }[name],
                index=False,
            )

    fscore,fcalls = score_final(priced)
    if fscore:
        results.append(fscore)
        fcalls.to_csv("fresh_oos_locked_final_calls.csv",index=False)

    lines = []
    lines.append("="*76)
    lines.append("FRESH OUT-OF-SAMPLE RESULTS")
    lines.append("="*76)
    lines.append(
        f"Fresh contracts available: {priced['ticker'].nunique()}"
    )
    lines.append(
        f"Fresh period: {fresh['start'].min()} -> {fresh['close'].max()}"
    )
    lines.append("")

    for r in results:
        lines.append(r["name"])
        lines.append("-"*60)
        lines.append(
            f"accuracy: {fmt_pct(r['accuracy'])} | "
            f"calls: {r['calls']} | "
            f"coverage: {fmt_pct(r['coverage'])}"
        )
        if "avg_ask" in r:
            lines.append(
                f"avg ask: {100*r['avg_ask']:.1f}c | "
                f"median ask: {100*r['median_ask']:.1f}c | "
                f"<=40c: {fmt_pct(r['pct_le40'])} | "
                f"20-40c: {fmt_pct(r['pct_20_40'])}"
            )
        lines.append(
            f"avg time left: {r['avg_time_left']:.2f}m | "
            f"median: {r['median_time_left']:.2f}m"
        )
        if "pct_5m_plus" in r:
            lines.append(
                f"calls with >=5m left: {fmt_pct(r['pct_5m_plus'])}"
            )
        lines.append("")

    # Fixed acceptance readout for the NEW 40c rule.
    p40 = next(
        (r for r in results if r["name"]=="EARLY_P40_NEW"), None
    )
    lines.append("="*76)
    lines.append("EARLY_P40_NEW ACCEPTANCE CHECK")
    lines.append("="*76)
    if p40 is None:
        lines.append("FAIL: no qualifying fresh calls.")
    else:
        checks = {
            "accuracy >=93%": p40["accuracy"] >= .93,
            "calls >=15": p40["calls"] >= 15,
            "avg ask <=40c": p40["avg_ask"] <= .40,
            "avg time left >=6m": p40["avg_time_left"] >= 6.0,
        }
        for k,v in checks.items():
            lines.append(f"{k}: {'PASS' if v else 'FAIL'}")
        lines.append(
            "OVERALL: "
            + ("PASS" if all(checks.values()) else "NOT READY")
        )

    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Fresh markets occur after the old 663-contract dataset.")
    lines.append("- Official Kalshi result=yes/no is the fresh truth.")
    lines.append("- Actual Kalshi 1-minute bid/ask candles are used.")
    lines.append("- Fresh contracts are not used to train/calibrate the model.")
    lines.append("- Rules are fixed before fresh scoring; no threshold search here.")
    lines.append("- Direct live BRTI authority is a separate live safety gate.")
    lines.append("- No orders; bot.py unchanged.")

    SUMMARY.write_text("\n".join(lines))
    print("\n".join(lines))

if __name__ == "__main__":
    main()
