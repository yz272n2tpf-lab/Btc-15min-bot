#!/usr/bin/env python3
"""
BTC15 direct-BRTI Flip Risk model study V1.

READ ONLY | RESEARCH ONLY | NO SIGNAL CHANGES | NO ORDERS

Implements exactly the methodology frozen in:
- BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_FREEZE_20260915.md
- BTC15_DIRECT_BRTI_FLIP_RISK_MODEL_FREEZE_ADDENDUM_V1.md

PASS can authorize only a future read-only shadow collector.
"""
from __future__ import annotations

import json
import math
import time
import urllib.request
from dataclasses import dataclass
from typing import Iterable

import numpy as np
import pandas as pd
from scipy.stats import spearmanr
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import brier_score_loss
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler

TAPE = "kalshi_direct_brti_parity_v1.csv"
LIVE = "https://external-api.kalshi.com/trade-api/v2/markets/"
HIST = "https://external-api.kalshi.com/trade-api/v2/historical/markets/"
TARGET_REMAINING_MINUTES = (9,8,7,6,5,4,3,2,1)
SNAP_TOL_SEC = 7.5
LAG_TOL_SEC = 7.5
WINDOW_SEC = 300.0
MIN_WINDOW_SAMPLES = 50
MAX_WINDOW_GAP_SEC = 8.0
FEATURES = [
    "remaining_min",
    "current_side_sign",
    "signed_dist_target_pct",
    "abs_dist_target_pct",
    "dist_per_min_remaining_pct",
    "aligned_move_1m_pct",
    "aligned_move_2m_pct",
    "aligned_move_3m_pct",
    "aligned_move_5m_pct",
    "brti_range_5m_pct",
    "brti_vol_5m",
    "dist_over_range_5m",
]
BINS = [(0,.05),(.05,.10),(.10,.20),(.20,.30),(.30,.40),(.40,.50),(.50,.60),(.60,.70),(.70,.80),(.80,.90),(.90,.95),(.95,1.001)]
BLOCKS = [
    (1, slice(0,40), slice(40,50), slice(50,65)),
    (2, slice(0,55), slice(55,65), slice(65,80)),
    (3, slice(0,70), slice(70,80), slice(80,94)),
]


def _bool_series(s: pd.Series) -> pd.Series:
    return s.astype(str).str.lower().isin(["true","1","yes"])


def load_tape(path: str = TAPE) -> pd.DataFrame:
    df = pd.read_csv(path)
    required = {
        "timestamp_utc","contract","target","seconds_left","direct_brti",
        "brti_age_seconds","direct_brti_ready",
    }
    missing = required - set(df.columns)
    if missing:
        raise RuntimeError(f"missing tape columns: {sorted(missing)}")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    for c in ["target","seconds_left","direct_brti","brti_age_seconds"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df["ready_bool"] = _bool_series(df["direct_brti_ready"])
    df = df.dropna(subset=["timestamp_utc","contract","target","seconds_left"]).copy()
    return df.sort_values(["contract","timestamp_utc"]).reset_index(drop=True)


def contract_inventory(df: pd.DataFrame) -> pd.DataFrame:
    rows=[]
    for contract,g in df.groupby("contract", sort=False):
        g=g.sort_values("timestamp_utc")
        ts=g["timestamp_utc"]
        d=ts.diff().dt.total_seconds().dropna()
        d=d[(d>0)&np.isfinite(d)]
        first=float(g["seconds_left"].max())
        span=float((ts.max()-ts.min()).total_seconds()) if len(ts)>=2 else 0.0
        p95=float(d.quantile(.95)) if len(d) else float("nan")
        ready_rate=float(g["ready_bool"].mean())
        targets=g["target"].dropna().to_numpy(dtype=float)
        target_consistent=bool(len(targets) and np.nanmax(targets)-np.nanmin(targets) <= 1e-6)
        usable=bool(first>=600 and span>=300 and math.isfinite(p95) and p95<=8 and ready_rate>=.95 and target_consistent)
        rows.append({
            "contract":str(contract),"first_ts":ts.min(),"first_left":first,
            "span":span,"p95_gap":p95,"ready_rate":ready_rate,
            "target_consistent":target_consistent,"usable":usable,
        })
    return pd.DataFrame(rows).sort_values("first_ts").reset_index(drop=True)


def _public_json(url: str):
    req=urllib.request.Request(url,headers={"User-Agent":"Mozilla/5.0","Accept":"application/json"})
    with urllib.request.urlopen(req,timeout=20) as r:
        return json.loads(r.read().decode("utf-8"))


def fetch_official_truth(tickers: Iterable[str]) -> dict[str,str]:
    out={}
    for i,t in enumerate(tickers,1):
        market=None
        for base in (LIVE,HIST):
            try:
                p=_public_json(base+t)
                m=p.get("market",p) if isinstance(p,dict) else None
                if isinstance(m,dict) and m.get("ticker"):
                    market=m;break
            except Exception:
                pass
        if market is None:
            raise RuntimeError(f"official truth fetch failed: {t}")
        result=str(market.get("result") or "").lower().strip()
        status=str(market.get("status") or "").lower().strip()
        side="UP" if result=="yes" else ("DOWN" if result=="no" else None)
        if status!="finalized" or side is None:
            raise RuntimeError(f"official truth not finalized: {t} status={status} result={result}")
        out[t]=side
        if i%20==0:
            print(f"OFFICIAL TRUTH | {i}/{len(list(tickers)) if hasattr(tickers,'__len__') else '?'} fetched",flush=True)
        time.sleep(.05)
    return out


def _lag_price(g: pd.DataFrame, snap_ts: pd.Timestamp, lag_sec: float) -> float | None:
    requested=snap_ts-pd.Timedelta(seconds=lag_sec)
    q=g[(g["timestamp_utc"]<=requested) & g["direct_brti"].notna()]
    if q.empty:return None
    r=q.iloc[-1]
    stale=(requested-r["timestamp_utc"]).total_seconds()
    if stale< -1e-9 or stale>LAG_TOL_SEC+1e-9:return None
    v=float(r["direct_brti"])
    return v if math.isfinite(v) and v>0 else None


def feature_snapshot(g: pd.DataFrame, target_remaining_min: int, official_side: str) -> dict | None:
    target_sec=target_remaining_min*60.0
    q=g.copy()
    q["snap_abs_diff"]=(q["seconds_left"]-target_sec).abs()
    q=q[q["snap_abs_diff"]<=SNAP_TOL_SEC+1e-12]
    if q.empty:return None
    q=q.sort_values(["snap_abs_diff","timestamp_utc"],ascending=[True,True])
    r=q.iloc[0]
    if not bool(r["ready_bool"]):return None
    age=float(r["brti_age_seconds"]) if pd.notna(r["brti_age_seconds"]) else float("inf")
    if not math.isfinite(age) or age>5.0:return None
    cur=float(r["direct_brti"]) if pd.notna(r["direct_brti"]) else float("nan")
    target=float(r["target"])
    if not math.isfinite(cur) or cur<=0 or not math.isfinite(target) or target<=0:return None
    if abs(cur-target)<=1e-12:return None
    side_sign=1.0 if cur>target else -1.0
    current_side="UP" if side_sign>0 else "DOWN"
    snap_ts=r["timestamp_utc"]
    hist=g[(g["timestamp_utc"]>=snap_ts-pd.Timedelta(seconds=WINDOW_SEC)) & (g["timestamp_utc"]<=snap_ts) & g["direct_brti"].notna()].copy().sort_values("timestamp_utc")
    if len(hist)<MIN_WINDOW_SAMPLES:return None
    gaps=hist["timestamp_utc"].diff().dt.total_seconds().dropna()
    if len(gaps) and float(gaps.max())>MAX_WINDOW_GAP_SEC+1e-12:return None
    prices=hist["direct_brti"].to_numpy(dtype=float)
    if not np.isfinite(prices).all() or np.any(prices<=0):return None
    lag_prices={}
    for m in (1,2,3,5):
        p=_lag_price(g,snap_ts,m*60.0)
        if p is None:return None
        lag_prices[m]=p
    aligned={m:((cur/lag_prices[m])-1.0)*side_sign for m in lag_prices}
    range_d=float(np.max(prices)-np.min(prices))
    returns=pd.Series(prices).pct_change().dropna().to_numpy(dtype=float)
    if len(returns)<2:return None
    vol=float(np.std(returns,ddof=1))
    remaining=float(r["seconds_left"])/60.0
    if remaining<=0:return None
    signed_dist=(cur-target)/target
    abs_dist=abs(signed_dist)
    out={
        "contract":str(r["contract"]),"snapshot_ts":snap_ts,
        "target_remaining_min":int(target_remaining_min),
        "remaining_min":remaining,
        "current_side":current_side,
        "current_side_sign":side_sign,
        "signed_dist_target_pct":signed_dist,
        "abs_dist_target_pct":abs_dist,
        "dist_per_min_remaining_pct":abs_dist/remaining,
        "aligned_move_1m_pct":aligned[1],
        "aligned_move_2m_pct":aligned[2],
        "aligned_move_3m_pct":aligned[3],
        "aligned_move_5m_pct":aligned[5],
        "brti_range_5m_pct":range_d/cur,
        "brti_vol_5m":vol,
        "dist_over_range_5m":abs(cur-target)/max(range_d,1e-6),
        "official_side":official_side,
        "flip":int(current_side!=official_side),
    }
    if not all(math.isfinite(float(out[c])) for c in FEATURES):return None
    return out


def build_dataset(df: pd.DataFrame, ordered_contracts: list[str], truth: dict[str,str]) -> tuple[pd.DataFrame,dict]:
    rows=[];excluded={"no_snapshot":0}
    by={c:g.sort_values("timestamp_utc").copy() for c,g in df.groupby("contract")}
    for c in ordered_contracts:
        g=by[c];side=truth[c]
        for minute in TARGET_REMAINING_MINUTES:
            row=feature_snapshot(g,minute,side)
            if row is None:excluded["no_snapshot"]+=1
            else:rows.append(row)
    return pd.DataFrame(rows),excluded


def _base_model() -> Pipeline:
    return Pipeline([
        ("scale",StandardScaler()),
        ("model",LogisticRegression(C=1.0,penalty="l2",solver="lbfgs",max_iter=2000)),
    ])


def _calibrator() -> LogisticRegression:
    return LogisticRegression(C=1.0,penalty="l2",solver="lbfgs",max_iter=2000)


def _logit(p: np.ndarray) -> np.ndarray:
    p=np.clip(np.asarray(p,dtype=float),1e-6,1-1e-6)
    return np.clip(np.log(p/(1-p)),-12,12)


def run_walkforward(ds: pd.DataFrame, ordered_contracts: list[str]) -> tuple[pd.DataFrame,list[dict],dict]:
    out=[];metrics=[];integrity={"block_disjoint":True,"block_chronological":True}
    for block,train_sl,cal_sl,test_sl in BLOCKS:
        tr=ordered_contracts[train_sl];ca=ordered_contracts[cal_sl];te=ordered_contracts[test_sl]
        if set(tr)&set(ca) or set(tr)&set(te) or set(ca)&set(te):integrity["block_disjoint"]=False
        # Contract ordering itself is chronological by first tape timestamp.
        if not (max([ordered_contracts.index(x) for x in tr]) < min([ordered_contracts.index(x) for x in ca]) < min([ordered_contracts.index(x) for x in te])):integrity["block_chronological"]=False
        train=ds[ds.contract.isin(tr)].copy();cal=ds[ds.contract.isin(ca)].copy();test=ds[ds.contract.isin(te)].copy()
        if min(len(train),len(cal),len(test))==0:raise RuntimeError(f"empty block partition {block}")
        if train.flip.nunique()<2 or cal.flip.nunique()<2:raise RuntimeError(f"single-class train/cal block {block}")
        base=_base_model();base.fit(train[FEATURES],train.flip)
        pcal=base.predict_proba(cal[FEATURES])[:,1]
        calibrator=_calibrator();calibrator.fit(_logit(pcal).reshape(-1,1),cal.flip)
        praw=base.predict_proba(test[FEATURES])[:,1]
        pfit=calibrator.predict_proba(_logit(praw).reshape(-1,1))[:,1]
        prior=float(train.flip.mean());pnull=np.full(len(test),prior)
        tmp=test.copy();tmp["block"]=block;tmp["raw_flip_prob"]=praw;tmp["flip_prob"]=pfit;tmp["null_flip_prob"]=pnull;out.append(tmp)
        metrics.append({
            "block":block,"train_contracts":len(tr),"cal_contracts":len(ca),"test_contracts":len(te),
            "train_snapshots":len(train),"cal_snapshots":len(cal),"test_snapshots":len(test),
            "raw_brier":float(brier_score_loss(test.flip,praw)),
            "cal_brier":float(brier_score_loss(test.flip,pfit)),
            "null_brier":float(brier_score_loss(test.flip,pnull)),
            "training_prior":prior,
        })
    return pd.concat(out,ignore_index=True),metrics,integrity


def score_gate(oos: pd.DataFrame, block_metrics: list[dict], integrity: dict) -> dict:
    raw=float(brier_score_loss(oos.flip,oos.raw_flip_prob));cal=float(brier_score_loss(oos.flip,oos.flip_prob));null=float(brier_score_loss(oos.flip,oos.null_flip_prob));skill=1-cal/null if null>0 else float("nan")
    blocks_improve=sum(m["cal_brier"]<=m["raw_brier"]+1e-12 for m in block_metrics)
    rel=[]
    for lo,hi in BINS:
        q=oos[(oos.flip_prob>=lo)&(oos.flip_prob<hi)]
        if len(q)>=20:
            stated=float(q.flip_prob.mean());actual=float(q.flip.mean());rel.append({"lo":lo,"hi":min(hi,1.0),"n":len(q),"stated":stated,"actual":actual,"err":abs(stated-actual)})
    ece=sum(r["n"]*r["err"] for r in rel)/sum(r["n"] for r in rel) if rel else float("nan")
    max30=max([r["err"] for r in rel if r["n"]>=30],default=float("nan"))
    if len(rel)>=3:
        rho=float(spearmanr([r["stated"] for r in rel],[r["actual"] for r in rel]).statistic)
    else:rho=float("nan")
    stay=oos[(1-oos.flip_prob)>=.90]
    stay_actual=float((1-stay.flip).mean()) if len(stay) else float("nan")
    time_rows=[];time_ok=True
    for minute in TARGET_REMAINING_MINUTES:
        q=oos[oos.target_remaining_min==minute]
        if len(q)>=20:
            stated=float(q.flip_prob.mean());actual=float(q.flip.mean());err=abs(stated-actual);time_rows.append({"minute":minute,"n":len(q),"stated":stated,"actual":actual,"err":err});time_ok &= err<=.15+1e-12
    sample_ok=oos.contract.nunique()>=40 and len(oos)>=250
    rel_ok=bool(rel) and ece<=.05+1e-12 and math.isfinite(max30) and max30<=.10+1e-12 and len(rel)>=3 and math.isfinite(rho) and rho>=.80-1e-12
    stay_ok=len(stay)>=30 and stay.contract.nunique()>=8 and stay_actual>=.90-1e-12
    brier_ok=cal<=raw+1e-12 and blocks_improve>=2 and math.isfinite(skill) and skill>=.05-1e-12
    passed=bool(all(integrity.values()) and sample_ok and brier_ok and rel_ok and stay_ok and time_ok)
    return {"passed":passed,"raw_brier":raw,"cal_brier":cal,"null_brier":null,"brier_skill":skill,"blocks_improve":blocks_improve,"reliability":rel,"ece":ece,"max_bin_error_n30":max30,"spearman":rho,"stay90_n":len(stay),"stay90_contracts":stay.contract.nunique(),"stay90_actual":stay_actual,"time_rows":time_rows,"time_ok":bool(time_ok),"sample_ok":sample_ok,"integrity":integrity}


def main() -> int:
    print("=== BTC15 DIRECT BRTI FLIP RISK MODEL V1 ===",flush=True)
    print("FROZEN BEFORE FIT | OFFICIAL TRUTH ONLY | NO START FEATURE | NO ORDERS",flush=True)
    df=load_tape();inv=contract_inventory(df);usable=inv[inv.usable].copy().sort_values("first_ts");ordered=usable.contract.astype(str).tolist()
    print(f"Tape rows={len(df)} contracts={inv.contract.nunique()} usable={len(ordered)}")
    if len(ordered)!=94:raise RuntimeError(f"frozen usable-contract count drift: {len(ordered)} != 94")
    truth=fetch_official_truth(ordered)
    if len(truth)!=94:raise RuntimeError("official truth coverage drift")
    ds,excluded=build_dataset(df,ordered,truth)
    print(f"Feature snapshots={len(ds)} contracts_with_snapshots={ds.contract.nunique()} excluded_grid_points={excluded['no_snapshot']}")
    oos,block_metrics,integrity=run_walkforward(ds,ordered)
    gate=score_gate(oos,block_metrics,integrity)
    print("\n=== WALK-FORWARD BLOCKS ===")
    for m in block_metrics:
        print(f"Block {m['block']} | train/cal/test contracts={m['train_contracts']}/{m['cal_contracts']}/{m['test_contracts']} | snapshots={m['train_snapshots']}/{m['cal_snapshots']}/{m['test_snapshots']} | raw={m['raw_brier']:.6f} cal={m['cal_brier']:.6f} null={m['null_brier']:.6f} | improve={m['cal_brier']<=m['raw_brier']+1e-12}")
    print("\n=== AGGREGATE OOS ===")
    print(f"oos_contracts={oos.contract.nunique()} oos_snapshots={len(oos)}")
    print(f"raw_brier={gate['raw_brier']:.6f} calibrated_brier={gate['cal_brier']:.6f} null_brier={gate['null_brier']:.6f} brier_skill={gate['brier_skill']:.6f}")
    print(f"blocks_tie_or_improve={gate['blocks_improve']}/3")
    print("\n=== RELIABILITY ===")
    for r in gate['reliability']:
        print(f"flip {r['lo']:.0%}-{r['hi']:.0%} | n={r['n']} | stated={r['stated']:.4f} actual={r['actual']:.4f} error={r['err']:.4f}")
    print(f"weighted_abs_cal_error={gate['ece']:.6f}")
    print(f"max_bin_error_n30={gate['max_bin_error_n30']:.6f}")
    print(f"reliability_spearman={gate['spearman']:.6f}")
    print("\n=== STAY >=90% ===")
    print(f"n={gate['stay90_n']} contracts={gate['stay90_contracts']} actual_stay={gate['stay90_actual']:.6f}")
    print("\n=== TIME BUCKETS ===")
    for r in gate['time_rows']:
        print(f"{r['minute']}m left | n={r['n']} stated_flip={r['stated']:.4f} actual_flip={r['actual']:.4f} error={r['err']:.4f} pass={r['err']<=.15+1e-12}")
    print("\n=== INTEGRITY ===")
    for k,v in gate['integrity'].items():print(f"{k}={v}")
    print(f"sample_ok={gate['sample_ok']} time_ok={gate['time_ok']}")
    status="HISTORICAL_DIRECT_BRTI_PASS_SHADOW_ONLY" if gate['passed'] else "HISTORICAL_DIRECT_BRTI_FAIL"
    print("\n=== DECISION ===")
    print("DIRECT_BRTI_FLIP_RISK_STATUS="+status)
    print("PASS="+str(gate['passed']))
    print("AUTHORITY="+("FREEZE_FRESH_FORWARD_SHADOW_SAMPLE_ONLY" if gate['passed'] else "DO_NOT_TUNE_SAME_OOS_COHORT"))
    print("NUMERIC_FLIP_RISK_USER_FACING_ALLOWED=False")
    print("PRODUCTION_CHANGED=False | SIGNAL_THRESHOLDS_CHANGED=False | ORDERS=False")
    return 0 if gate['passed'] else 2


if __name__=="__main__":
    raise SystemExit(main())
