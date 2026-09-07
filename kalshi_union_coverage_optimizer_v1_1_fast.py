#!/usr/bin/env python3
"""
KALSHI BTC 15-MIN UNION COVERAGE OPTIMIZER V1
=============================================

Purpose
-------
Keep the locked strong tiers intact and expand ACTIONABLE COVERAGE.

Locked anchors:
1) FINAL tournament winner (do not weaken)
2) Tier-1 ENTRY historical-price winner (do not weaken)

This optimizer searches the contracts NOT already covered by Tier-1 ENTRY for:
- Secondary directional value entries
- Short-horizon scalp opportunities using ACTUAL Kalshi 1-minute bid/ask
- Reversal scalps using ACTUAL Kalshi 1-minute bid/ask

Core metric:
UNION ACTIONABLE COVERAGE = % of contracts with >=1 validated opportunity.

Integrity
---------
- Actual Kalshi historical 1-minute YES bid/ask
- Official settlement labels
- Chronological model/calibration/validation/untouched-holdout split
- Locked Tier-1 rule is not tuned
- New rules are selected on validation only
- Untouched holdout is report-only
- Signal-only; no orders
- bot.py unchanged

Scalp realism
-------------
For a candidate entry:
- BUY at the actual ASK
- EXIT at the actual future BID on the same side
- Profit target must be hit BEFORE a stop-loss is hit
- This accounts for spread and avoids using settlement-only correctness
"""

from pathlib import Path
from zoneinfo import ZoneInfo
import re, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression

CAL = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")
CANDLE_CACHE = Path("kalshi_kxbtc15m_1m_candles_cache.csv")

SUMMARY = Path("union_coverage_optimizer_v1_summary.txt")
SECONDARY_RESULTS = Path("union_secondary_entry_results.csv")
SCALP_RESULTS = Path("union_scalp_results.csv")
HOLDOUT_DETAIL = Path("union_coverage_holdout_detail.csv")
PROCESSED_CACHE = Path("union_optimizer_processed_snapshot_cache.csv")

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
    try:
        d = pd.read_csv(BTC_CACHE, index_col="Datetime", parse_dates=True)
    except Exception:
        d = pd.read_csv(BTC_CACHE)
        ts = next(
            (c for c in ["Datetime","datetime","timestamp","Timestamp","time","Time"]
             if c in d.columns), d.columns[0]
        )
        d[ts] = pd.to_datetime(d[ts], errors="coerce", utc=True)
        d = d.dropna(subset=[ts]).set_index(ts)

    idx = pd.to_datetime(d.index, errors="coerce", utc=True)
    ok = ~pd.isna(idx)
    d = d.loc[ok].copy()
    d.index = idx[ok]
    rename={}
    for want in ["Open","High","Low","Close","Volume"]:
        for c in d.columns:
            if str(c).lower()==want.lower():
                rename[c]=want
                break
    d=d.rename(columns=rename)
    d=d[~d.index.duplicated(keep="last")].sort_index()
    return d

def price_at_or_before(data, ts):
    i=data.index.searchsorted(ts,side="right")-1
    if i<0:
        return np.nan,pd.NaT
    ti=data.index[i]
    if ts-ti>pd.Timedelta(minutes=2):
        return np.nan,pd.NaT
    return float(data.iloc[i]["Close"]),ti

def build_snapshot(data,start,target,final_side,elapsed):
    cut=start+pd.Timedelta(minutes=float(elapsed))
    pstart,_=price_at_or_before(data,start)
    vals=[price_at_or_before(data,cut-pd.Timedelta(minutes=m)) for m in [0,1,2,3,5]]
    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None
    p0,p1,p2,p3,p5=[v[0] for v in vals]
    w=data.loc[(data.index>cut-pd.Timedelta(minutes=5))&(data.index<=cut)]
    if len(w)<3:
        return None
    closes=w["Close"].dropna()
    if len(closes)<2:
        return None

    current_side=int(p0>=target)
    sign=1.0 if current_side==1 else -1.0
    dist=p0-target
    abs_dist=abs(dist)
    remaining=max(0.0,15.0-float(elapsed))
    range5=float(w["High"].max()-w["Low"].min())
    move1,move2,move3,move5=p0-p1,p0-p2,p0-p3,p0-p5
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
        "snapshot_utc":cut,
    }

def load_candles():
    c=pd.read_csv(CANDLE_CACHE)
    c["candle_end_utc"]=pd.to_datetime(c["candle_end_utc"],errors="coerce",utc=True)
    for col in ["yes_ask","yes_bid","no_ask"]:
        c[col]=pd.to_numeric(c[col],errors="coerce")
    # derive NO bid from YES ask
    c["no_bid"]=1.0-c["yes_ask"]
    return c.dropna(subset=["contract","candle_end_utc"]).sort_values(
        ["contract","candle_end_utc"]
    )

def add_fair(hist,rf,sigmoid):
    d=hist.copy()
    raw=rf.predict_proba(d[FEATURES])[:,1]
    flip=sigmoid.predict_proba(raw.reshape(-1,1))[:,1]
    flip=np.clip(flip,.001,.999)
    d["fair_up"]=np.where(d["current_side"]==1,1-flip,flip)
    d["fair_down"]=1-d["fair_up"]
    d["preferred_side_num"]=np.where(d["fair_up"]>=d["fair_down"],1,0)
    d["preferred_side"]=np.where(d["preferred_side_num"]==1,"UP","DOWN")
    d["preferred_fair"]=np.maximum(d["fair_up"],d["fair_down"])
    return d

def align_prices(test,candles):
    parts=[]
    for ticker,g in test.groupby("ticker",sort=False):
        cg=candles[candles["contract"]==ticker].copy()
        if cg.empty:
            continue
        gg=g.copy()
        gg["snapshot_utc"]=pd.to_datetime(
            gg["snapshot_utc"],errors="coerce",utc=True
        ).astype("datetime64[ns, UTC]")
        cg["candle_end_utc"]=pd.to_datetime(
            cg["candle_end_utc"],errors="coerce",utc=True
        ).astype("datetime64[ns, UTC]")
        gg=gg.dropna(subset=["snapshot_utc"]).sort_values("snapshot_utc")
        cg=cg.dropna(subset=["candle_end_utc"]).sort_values("candle_end_utc")
        m=pd.merge_asof(
            gg,
            cg[["candle_end_utc","yes_ask","yes_bid","no_ask","no_bid"]],
            left_on="snapshot_utc",right_on="candle_end_utc",
            direction="backward",tolerance=pd.Timedelta(seconds=90),
        )
        parts.append(m)
    if not parts:
        raise SystemExit("No aligned Kalshi price data")
    d=pd.concat(parts,ignore_index=True)
    d["preferred_ask"]=np.where(
        d["preferred_side_num"]==1,d["yes_ask"],d["no_ask"]
    )
    d["preferred_bid"]=np.where(
        d["preferred_side_num"]==1,d["yes_bid"],d["no_bid"]
    )
    d["edge"]=d["preferred_fair"]-d["preferred_ask"]
    return d[d["preferred_ask"].between(.001,.999)].copy()

def locked_tier1_mask(d):
    # Exact V3 Tier-1 winner
    return (
        (d["preferred_ask"]<=.45)
        &(d["preferred_fair"]>=.75)
        &(d["edge"]>=.08)
        &(d["remaining"]>=2.0)
        &(d["remaining"]<=10.0)
        &(d["abs_dist_target"]>=25.0)
    )

def score_secondary(frame,p):
    mask=(
        (frame["preferred_ask"]<=p["ask_max"])
        &(frame["preferred_fair"]>=p["fair_min"])
        &(frame["edge"]>=p["edge_min"])
        &(frame["remaining"]>=p["min_tl"])
        &(frame["remaining"]<=p["max_tl"])
        &(frame["abs_dist_target"]>=p["min_gap"])
        &(frame["dist_over_range5"]>=p["min_ratio"])
    )
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
        "avg_time_left":float(first["remaining"].mean()),
    },first

def future_scalp_outcome(row,candles,profit_target,stop_loss,horizon):
    ticker=row["ticker"]
    side=row["preferred_side"]
    entry=float(row["preferred_ask"])
    t0=pd.Timestamp(row["snapshot_utc"])
    t1=t0+pd.Timedelta(minutes=int(horizon))
    cg=candles[
        (candles["contract"]==ticker)
        &(candles["candle_end_utc"]>t0)
        &(candles["candle_end_utc"]<=t1)
    ].sort_values("candle_end_utc")
    if cg.empty:
        return None
    bid_col="yes_bid" if side=="UP" else "no_bid"
    asks_col="yes_ask" if side=="UP" else "no_ask"

    target=entry+profit_target
    stop=entry-stop_loss
    for _,c in cg.iterrows():
        bid=c[bid_col]
        ask=c[asks_col]
        if pd.isna(bid) or pd.isna(ask):
            continue
        # Stop uses bid too, because that's the executable exit.
        if float(bid)<=stop:
            return False
        if float(bid)>=target:
            return True
    return False

def score_scalp(frame,candles,p):
    mask=(
        (frame["preferred_ask"]<=p["ask_max"])
        &(frame["preferred_fair"]>=p["fair_min"])
        &(frame["edge"]>=p["edge_min"])
        &(frame["remaining"]>=p["min_tl"])
        &(frame["remaining"]<=p["max_tl"])
        &(frame["abs_dist_target"]>=p["min_gap"])
    )
    q=frame[mask].sort_values(["ticker","elapsed"])
    if q.empty:
        return None,pd.DataFrame()

    picked=[]
    for ticker,g in q.groupby("ticker",sort=False):
        for _,r in g.iterrows():
            out=future_scalp_outcome(
                r,candles,p["profit_target"],p["stop_loss"],p["horizon"]
            )
            if out is None:
                continue
            rr=r.copy()
            rr["scalp_win"]=bool(out)
            picked.append(rr)
            break

    if not picked:
        return None,pd.DataFrame()
    first=pd.DataFrame(picked)
    return {
        **p,
        "calls":len(first),
        "contracts":frame["ticker"].nunique(),
        "coverage":len(first)/max(frame["ticker"].nunique(),1),
        "accuracy":float(first["scalp_win"].mean()),
        "avg_ask":float(first["preferred_ask"].mean()),
        "avg_time_left":float(first["remaining"].mean()),
    },first

def main():
    print("="*78)
    print("UNION COVERAGE OPTIMIZER V1.1 FAST")
    print("LOCKED FINAL + LOCKED TIER-1 ENTRY + COVERAGE EXPANSION")
    print("="*78)

    cal=pd.read_csv(CAL)
    pairs=cal["ticker"].map(parse_contract_times)
    cal["start"]=[p[0] for p in pairs]
    cal["close"]=[p[1] for p in pairs]
    cal["target_brti"]=pd.to_numeric(cal["target_brti"],errors="coerce")
    cal["final_side"]=cal["result"].astype(str).str.lower().map({"yes":1,"no":0})
    cal=cal.dropna(subset=["ticker","start","close","target_brti","final_side"]).sort_values(
        "start"
    ).drop_duplicates("ticker",keep="last").reset_index(drop=True)

    btc=load_btc()
    rows=[]
    print(f"Building fair snapshots from {len(cal)} settled contracts...")
    for i,r in cal.iterrows():
        for elapsed in range(1,15):
            s=build_snapshot(
                btc,r["start"],float(r["target_brti"]),int(r["final_side"]),elapsed
            )
            if s is not None:
                s["ticker"]=r["ticker"]
                s["start"]=r["start"]
                rows.append(s)
        if (i+1)%100==0:
            print(f"  features {i+1}/{len(cal)}")

    hist=pd.DataFrame(rows)
    cov=hist.groupby("ticker")["elapsed"].nunique()
    keep=cov[cov>=10].index
    hist=hist[hist["ticker"].isin(keep)].copy()
    contracts=hist[["ticker","start"]].drop_duplicates().sort_values("start").reset_index(drop=True)
    n=len(contracts)
    i1,i2,i3=int(n*.50),int(n*.70),int(n*.85)
    model_c=contracts.iloc[:i1]
    calib_c=contracts.iloc[i1:i2]
    valid_c=contracts.iloc[i2:i3]
    hold_c=contracts.iloc[i3:]

    print(
        f"Chronology: model {len(model_c)} | calibration {len(calib_c)} | "
        f"validation {len(valid_c)} | untouched holdout {len(hold_c)}"
    )

    train=hist[hist["ticker"].isin(set(model_c["ticker"]))].copy()
    calib=hist[hist["ticker"].isin(set(calib_c["ticker"]))].copy()
    rf=RandomForestClassifier(
        n_estimators=900,max_depth=9,min_samples_leaf=12,
        class_weight="balanced",random_state=42,n_jobs=-1
    )
    print("Training target-aware fair model once...")
    rf.fit(train[FEATURES],train["flip"])
    raw=rf.predict_proba(calib[FEATURES])[:,1]
    sig=LogisticRegression(solver="lbfgs",C=1.0,max_iter=1000,random_state=42)
    sig.fit(raw.reshape(-1,1),calib["flip"].astype(int))

    test=hist[hist["ticker"].isin(set(valid_c["ticker"])|set(hold_c["ticker"]))].copy()
    test=add_fair(test,rf,sig)
    candles=load_candles()
    d=align_prices(test,candles)
    try:
        d.to_csv(PROCESSED_CACHE,index=False)
        print(f"Processed snapshot cache written: {PROCESSED_CACHE}")
    except Exception:
        pass

    valid=d[d["ticker"].isin(set(valid_c["ticker"]))].copy()
    hold=d[d["ticker"].isin(set(hold_c["ticker"]))].copy()

    # Locked Tier-1 coverage anchors.
    def tier1_contracts(frame):
        q=frame[locked_tier1_mask(frame)].sort_values(["ticker","elapsed"])
        return set(q.groupby("ticker").first().index)

    valid_t1=tier1_contracts(valid)
    hold_t1=tier1_contracts(hold)

    # Search SECONDARY entry only among contracts not already covered by Tier-1.
    valid_secondary_pool=valid[~valid["ticker"].isin(valid_t1)].copy()
    hold_secondary_pool=hold[~hold["ticker"].isin(hold_t1)].copy()

    ask_grid=[.45,.50,.55,.60]
    fair_grid=[.60,.65,.70,.75]
    edge_grid=[.05,.08,.10,.12]
    min_tl_grid=[2.,4.,6.,8.]
    max_tl_grid=[10.,12.,14.]
    gap_grid=[0.,25.,50.,75.]
    ratio_grid=[0.,.5,1.]

    sec_results=[]
    total=(len(ask_grid)*len(fair_grid)*len(edge_grid)*len(min_tl_grid)*
           len(max_tl_grid)*len(gap_grid)*len(ratio_grid))
    print(f"Testing {total:,} SECONDARY directional-entry combinations...")
    for ask_max in ask_grid:
      for fair_min in fair_grid:
       for edge_min in edge_grid:
        for min_tl in min_tl_grid:
         for max_tl in max_tl_grid:
          if min_tl>max_tl: continue
          for min_gap in gap_grid:
           for min_ratio in ratio_grid:
            p=dict(
                ask_max=ask_max,fair_min=fair_min,edge_min=edge_min,
                min_tl=min_tl,max_tl=max_tl,min_gap=min_gap,min_ratio=min_ratio
            )
            s,_=score_secondary(valid_secondary_pool,p)
            if s is not None:
                sec_results.append(s)

    sec=pd.DataFrame(sec_results)
    if sec.empty:
        raise SystemExit("No secondary-entry candidates")

    min_calls=max(8,int(np.ceil(valid_c.shape[0]*.10)))
    sec_eligible=sec[sec["calls"]>=min_calls].copy()
    if sec_eligible.empty:
        sec_eligible=sec[sec["calls"]>=5].copy()
    if sec_eligible.empty:
        sec_eligible=sec.copy()
    # For coverage expansion, require a strong accuracy floor first.
    # Then maximize coverage/timing/price.
    sec_eligible["meets90"]=sec_eligible["accuracy"]>=.90
    sec_eligible=sec_eligible.sort_values(
        ["meets90","accuracy","coverage","avg_time_left","avg_ask"],
        ascending=[False,False,False,False,True]
    ).reset_index(drop=True)
    sec_eligible["validation_rank"]=np.arange(1,len(sec_eligible)+1)
    sec_eligible.to_csv(SECONDARY_RESULTS,index=False)

    sec_keys=["ask_max","fair_min","edge_min","min_tl","max_tl","min_gap","min_ratio"]
    sec_win={k:sec_eligible.iloc[0][k] for k in sec_keys}
    sec_v,sec_v_calls=score_secondary(valid_secondary_pool,sec_win)
    sec_h,sec_h_calls=score_secondary(hold_secondary_pool,sec_win)

    valid_sec=set(sec_v_calls["ticker"]) if not sec_v_calls.empty else set()
    hold_sec=set(sec_h_calls["ticker"]) if not sec_h_calls.empty else set()

    # SCALP search only on contracts still uncovered after Tier-1 + secondary.
    valid_scalp_pool=valid[
        ~valid["ticker"].isin(valid_t1|valid_sec)
    ].copy()
    hold_scalp_pool=hold[
        ~hold["ticker"].isin(hold_t1|hold_sec)
    ].copy()

    scalp_ask=[.30,.40,.50,.60,.70]
    scalp_fair=[.52,.55,.60,.65,.70]
    scalp_edge=[.00,.03,.05,.08,.10]
    scalp_min_tl=[3.,5.,7.,9.]
    scalp_max_tl=[10.,12.,14.]
    scalp_gap=[0.,25.,50.]
    profit_targets=[.08,.10,.12,.15,.20]
    stop_losses=[.05,.08,.10,.12]
    horizons=[2,3,4,5]

    # FAST EXACT SCALP SEARCH
    # -----------------------
    # The old V1 brute-forced every entry filter x every exit rule and
    # repeatedly rescanned future candles. V1.1 precomputes the outcome of
    # every possible exit rule ONCE for every validation snapshot, then tests
    # all entry-filter combinations against that cached outcome matrix.
    # Same parameter grid, same scoring semantics, far less repeated work.
    print("Precomputing scalp exit outcomes once...")

    exit_rules=[]
    for pt in profit_targets:
      for sl in stop_losses:
       for hz in horizons:
        exit_rules.append((pt,sl,hz))

    pool = valid_scalp_pool.sort_values(["ticker","elapsed"]).copy().reset_index(drop=True)
    outcome_cols=[]

    for j,(pt,sl,hz) in enumerate(exit_rules):
        col=f"_scalp_outcome_{j}"
        vals=[]
        for _,r in pool.iterrows():
            vals.append(
                future_scalp_outcome(
                    r,candles,pt,sl,hz
                )
            )
        pool[col]=vals
        outcome_cols.append(col)

    entry_filters=[]
    for ask_max in scalp_ask:
      for fair_min in scalp_fair:
       for edge_min in scalp_edge:
        for min_tl in scalp_min_tl:
         for max_tl in scalp_max_tl:
          if min_tl>max_tl:
              continue
          for min_gap in scalp_gap:
            entry_filters.append(dict(
                ask_max=ask_max,fair_min=fair_min,edge_min=edge_min,
                min_tl=min_tl,max_tl=max_tl,min_gap=min_gap
            ))

    print(
        f"FAST SCALP SEARCH: {len(entry_filters):,} entry filters x "
        f"{len(exit_rules)} exit rules = "
        f"{len(entry_filters)*len(exit_rules):,} exact combinations"
    )

    scalp_results=[]

    for i,p0 in enumerate(entry_filters,1):
        mask=(
            (pool["preferred_ask"]<=p0["ask_max"])
            &(pool["preferred_fair"]>=p0["fair_min"])
            &(pool["edge"]>=p0["edge_min"])
            &(pool["remaining"]>=p0["min_tl"])
            &(pool["remaining"]<=p0["max_tl"])
            &(pool["abs_dist_target"]>=p0["min_gap"])
        )
        cand=pool[mask]
        if cand.empty:
            continue

        # For each exit rule, choose the FIRST qualifying snapshot per contract
        # that has a valid future outcome under that exit rule.
        for j,(pt,sl,hz) in enumerate(exit_rules):
            col=outcome_cols[j]
            c=cand[cand[col].notna()]
            if c.empty:
                continue
            first=(
                c.sort_values(["ticker","elapsed"])
                 .groupby("ticker",as_index=False)
                 .first()
            )
            if first.empty:
                continue
            wins=first[col].astype(bool)
            scalp_results.append({
                **p0,
                "profit_target":pt,
                "stop_loss":sl,
                "horizon":hz,
                "calls":len(first),
                "contracts":valid_scalp_pool["ticker"].nunique(),
                "coverage":len(first)/max(valid_scalp_pool["ticker"].nunique(),1),
                "accuracy":float(wins.mean()),
                "avg_ask":float(first["preferred_ask"].mean()),
                "avg_time_left":float(first["remaining"].mean()),
            })

        if i % 500 == 0:
            print(f"  scalp entry filters {i}/{len(entry_filters)}")

    scalp=pd.DataFrame(scalp_results)
    if scalp.empty:
        raise SystemExit("No scalp candidates")

    scalp_min_calls=max(8,int(np.ceil(valid_c.shape[0]*.08)))
    scalp_eligible=scalp[scalp["calls"]>=scalp_min_calls].copy()
    if scalp_eligible.empty:
        scalp_eligible=scalp[scalp["calls"]>=5].copy()
    if scalp_eligible.empty:
        scalp_eligible=scalp.copy()

    # Scalp target: prioritize accuracy, then coverage, then return/time.
    scalp_eligible["meets75"]=scalp_eligible["accuracy"]>=.75
    scalp_eligible=scalp_eligible.sort_values(
        ["meets75","accuracy","coverage","profit_target","avg_time_left","avg_ask"],
        ascending=[False,False,False,False,False,True]
    ).reset_index(drop=True)
    scalp_eligible["validation_rank"]=np.arange(1,len(scalp_eligible)+1)
    scalp_eligible.to_csv(SCALP_RESULTS,index=False)

    scalp_keys=[
        "ask_max","fair_min","edge_min","min_tl","max_tl","min_gap",
        "profit_target","stop_loss","horizon"
    ]
    scalp_win={k:scalp_eligible.iloc[0][k] for k in scalp_keys}
    sc_v,sc_v_calls=score_scalp(valid_scalp_pool,candles,scalp_win)
    sc_h,sc_h_calls=score_scalp(hold_scalp_pool,candles,scalp_win)

    valid_scalp=set(sc_v_calls["ticker"]) if not sc_v_calls.empty else set()
    hold_scalp=set(sc_h_calls["ticker"]) if not sc_h_calls.empty else set()

    # Union coverage among actionable entry/scalp paths.
    valid_union=valid_t1|valid_sec|valid_scalp
    hold_union=hold_t1|hold_sec|hold_scalp

    # Holdout detail
    detail=[]
    for ticker in hold_c["ticker"]:
        detail.append({
            "ticker":ticker,
            "tier1_entry":ticker in hold_t1,
            "secondary_entry":ticker in hold_sec,
            "scalp":ticker in hold_scalp,
            "any_actionable":ticker in hold_union,
        })
    pd.DataFrame(detail).to_csv(HOLDOUT_DETAIL,index=False)

    def pct(x): return f"{100*float(x):.1f}%"

    lines=[]
    lines.append("="*78)
    lines.append("UNION COVERAGE OPTIMIZER V1.1 FAST SUMMARY")
    lines.append("="*78)
    lines.append("")
    lines.append("LOCKED TIER-1 ENTRY")
    lines.append(
        f"Validation coverage: {len(valid_t1)}/{len(valid_c)} "
        f"({pct(len(valid_t1)/len(valid_c))})"
    )
    lines.append(
        f"Holdout coverage: {len(hold_t1)}/{len(hold_c)} "
        f"({pct(len(hold_t1)/len(hold_c))})"
    )
    lines.append("")
    lines.append("SECONDARY ENTRY WINNER — selected on validation only")
    for k in sec_keys: lines.append(f"{k}: {sec_win[k]}")
    lines.append(
        f"Validation: accuracy {pct(sec_v['accuracy'])} | "
        f"calls {sec_v['calls']} | avg ask {100*sec_v['avg_ask']:.1f}c | "
        f"avg time left {sec_v['avg_time_left']:.2f}m"
    )
    if sec_h is None:
        lines.append("Holdout: no calls")
    else:
        lines.append(
            f"Holdout: accuracy {pct(sec_h['accuracy'])} | "
            f"calls {sec_h['calls']} | avg ask {100*sec_h['avg_ask']:.1f}c | "
            f"avg time left {sec_h['avg_time_left']:.2f}m"
        )
    lines.append("")
    lines.append("SCALP WINNER — selected on validation only")
    for k in scalp_keys: lines.append(f"{k}: {scalp_win[k]}")
    lines.append(
        f"Validation: win rate {pct(sc_v['accuracy'])} | "
        f"calls {sc_v['calls']} | avg ask {100*sc_v['avg_ask']:.1f}c | "
        f"avg time left {sc_v['avg_time_left']:.2f}m"
    )
    if sc_h is None:
        lines.append("Holdout: no calls")
    else:
        lines.append(
            f"Holdout: win rate {pct(sc_h['accuracy'])} | "
            f"calls {sc_h['calls']} | avg ask {100*sc_h['avg_ask']:.1f}c | "
            f"avg time left {sc_h['avg_time_left']:.2f}m"
        )
    lines.append("")
    lines.append("UNION ACTIONABLE COVERAGE")
    lines.append(
        f"Validation: {len(valid_union)}/{len(valid_c)} "
        f"({pct(len(valid_union)/len(valid_c))})"
    )
    lines.append(
        f"Untouched holdout: {len(hold_union)}/{len(hold_c)} "
        f"({pct(len(hold_union)/len(hold_c))})"
    )
    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Locked Tier-1 rule unchanged")
    lines.append("- Secondary selected on validation only")
    lines.append("- Scalp selected on validation only")
    lines.append("- Actual Kalshi ask for entry; actual future bid for exit")
    lines.append("- Spread included")
    lines.append("- Stop-loss evaluated before profit target")
    lines.append("- Holdout report-only")
    lines.append("- No orders; bot.py unchanged")
    lines.append("")
    lines.append("FILES WRITTEN")
    lines.append(str(SECONDARY_RESULTS))
    lines.append(str(SCALP_RESULTS))
    lines.append(str(HOLDOUT_DETAIL))
    lines.append(str(SUMMARY))

    summary="\n".join(lines)
    SUMMARY.write_text(summary)
    print("\n"+summary)

if __name__=="__main__":
    main()
