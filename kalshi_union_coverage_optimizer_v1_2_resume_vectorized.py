#!/usr/bin/env python3
"""
UNION COVERAGE OPTIMIZER V1.2 — RESUME + VECTORIZED SCALP SEARCH
===============================================================

Purpose
-------
Finish the exact coverage-expansion question WITHOUT rebuilding the 663-contract
feature/model pipeline and WITHOUT 360,000 expensive pandas group-bys.

Uses:
- union_optimizer_processed_snapshot_cache.csv from V1.1
- kalshi_kxbtc15m_1m_candles_cache.csv
- brti_calibration_results.csv

Preserves:
- chronological 50/20/15/15 contract split
- locked Tier-1 entry rule
- secondary-entry validation-only selection
- actual ask to enter / future bid to exit
- spread
- stop-before-profit chronology
- untouched holdout as report-only
- signal only / no orders

Scalp parameter grid is the SAME 360,000 combinations.
Only the implementation is changed: NumPy first-hit scoring replaces repeated
pandas groupby/filter work.
"""

from pathlib import Path
from zoneinfo import ZoneInfo
import re, warnings
warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd

CAL = Path("brti_calibration_results.csv")
CACHE = Path("union_optimizer_processed_snapshot_cache.csv")
CANDLES = Path("kalshi_kxbtc15m_1m_candles_cache.csv")

SUMMARY = Path("union_coverage_optimizer_v1_2_summary.txt")
SECONDARY_RESULTS = Path("union_secondary_entry_results_v1_2.csv")
SCALP_RESULTS = Path("union_scalp_results_v1_2.csv")
HOLDOUT_DETAIL = Path("union_coverage_holdout_detail_v1_2.csv")

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

def parse_contract_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper()
    )
    if not m:
        return pd.NaT, pd.NaT
    yy, mon, dd, hh, mm = m.groups()
    wall = pd.Timestamp(
        year=2000+int(yy), month=MONTHS[mon], day=int(dd),
        hour=int(hh), minute=int(mm)
    )
    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")
    return close_utc-pd.Timedelta(minutes=15), close_utc

def pct(x):
    return f"{100*float(x):.1f}%"

def load_cache():
    if not CACHE.exists():
        raise SystemExit(
            f"Missing {CACHE}. V1.1 did not reach the cache-write step."
        )
    d = pd.read_csv(CACHE)
    need = {
        "ticker","snapshot_utc","elapsed","remaining","abs_dist_target",
        "dist_over_range5","preferred_ask","preferred_fair","edge",
        "preferred_side","preferred_side_num","final_side"
    }
    missing = need-set(d.columns)
    if missing:
        raise SystemExit(f"Processed cache missing columns: {sorted(missing)}")

    d["snapshot_utc"] = pd.to_datetime(
        d["snapshot_utc"], errors="coerce", utc=True
    )
    for c in [
        "elapsed","remaining","abs_dist_target","dist_over_range5",
        "preferred_ask","preferred_fair","edge",
        "preferred_side_num","final_side"
    ]:
        d[c] = pd.to_numeric(d[c], errors="coerce")

    d = d.dropna(
        subset=[
            "ticker","snapshot_utc","elapsed","remaining",
            "preferred_ask","preferred_fair","edge",
            "preferred_side_num","final_side"
        ]
    ).copy()
    return d.sort_values(["ticker","elapsed"]).reset_index(drop=True)

def contract_split(d):
    ticks = pd.DataFrame({"ticker": sorted(d["ticker"].unique())})
    pairs = ticks["ticker"].map(parse_contract_times)
    ticks["start"] = [p[0] for p in pairs]
    ticks = ticks.dropna(subset=["start"]).sort_values("start").reset_index(drop=True)
    n = len(ticks)

    # Cache contains validation + holdout only from V1.1. Reconstruct their
    # relative boundary from the original 99 / 100 chronology where possible.
    if n < 20:
        raise SystemExit(f"Too few cached contracts: {n}")

    # Original V1.1 used last 30% of full usable history = validation 15% +
    # holdout 15%, which are almost equal sizes. Split this cached set in half.
    mid = n//2
    valid_ticks = set(ticks.iloc[:mid]["ticker"])
    hold_ticks = set(ticks.iloc[mid:]["ticker"])
    return valid_ticks, hold_ticks

def locked_tier1_mask(d):
    return (
        (d["preferred_ask"] <= .45)
        & (d["preferred_fair"] >= .75)
        & (d["edge"] >= .08)
        & (d["remaining"] >= 2.0)
        & (d["remaining"] <= 10.0)
        & (d["abs_dist_target"] >= 25.0)
    )

def first_contract_rows(frame, mask):
    q = frame[mask].sort_values(["ticker","elapsed"])
    if q.empty:
        return pd.DataFrame()
    return q.groupby("ticker", as_index=False).first()

def score_secondary(frame, p):
    mask = (
        (frame["preferred_ask"] <= p["ask_max"])
        & (frame["preferred_fair"] >= p["fair_min"])
        & (frame["edge"] >= p["edge_min"])
        & (frame["remaining"] >= p["min_tl"])
        & (frame["remaining"] <= p["max_tl"])
        & (frame["abs_dist_target"] >= p["min_gap"])
        & (frame["dist_over_range5"] >= p["min_ratio"])
    )
    first = first_contract_rows(frame, mask)
    if first.empty:
        return None, first
    correct = (
        first["preferred_side_num"].astype(int)
        == first["final_side"].astype(int)
    )
    return {
        **p,
        "calls": len(first),
        "contracts": frame["ticker"].nunique(),
        "coverage": len(first)/max(frame["ticker"].nunique(),1),
        "accuracy": float(correct.mean()),
        "avg_ask": float(first["preferred_ask"].mean()),
        "avg_time_left": float(first["remaining"].mean()),
    }, first

def secondary_tournament(valid_pool):
    ask_grid=[.45,.50,.55,.60]
    fair_grid=[.60,.65,.70,.75]
    edge_grid=[.05,.08,.10,.12]
    min_tl_grid=[2.,4.,6.,8.]
    max_tl_grid=[10.,12.,14.]
    gap_grid=[0.,25.,50.,75.]
    ratio_grid=[0.,.5,1.]

    rows=[]
    for ask_max in ask_grid:
      for fair_min in fair_grid:
       for edge_min in edge_grid:
        for min_tl in min_tl_grid:
         for max_tl in max_tl_grid:
          if min_tl > max_tl:
              continue
          for min_gap in gap_grid:
           for min_ratio in ratio_grid:
            p=dict(
                ask_max=ask_max,fair_min=fair_min,edge_min=edge_min,
                min_tl=min_tl,max_tl=max_tl,min_gap=min_gap,min_ratio=min_ratio
            )
            s,_ = score_secondary(valid_pool,p)
            if s is not None:
                rows.append(s)

    res = pd.DataFrame(rows)
    if res.empty:
        raise SystemExit("No secondary candidates")

    min_calls=max(8,int(np.ceil(valid_pool["ticker"].nunique()*.10)))
    e=res[res["calls"]>=min_calls].copy()
    if e.empty: e=res[res["calls"]>=5].copy()
    if e.empty: e=res.copy()
    e["meets90"]=e["accuracy"]>=.90
    e=e.sort_values(
        ["meets90","accuracy","coverage","avg_time_left","avg_ask"],
        ascending=[False,False,False,False,True]
    ).reset_index(drop=True)
    e["validation_rank"]=np.arange(1,len(e)+1)
    e.to_csv(SECONDARY_RESULTS,index=False)
    keys=["ask_max","fair_min","edge_min","min_tl","max_tl","min_gap","min_ratio"]
    winner={k:e.iloc[0][k] for k in keys}
    return winner, keys

def load_candles():
    c = pd.read_csv(CANDLES)
    c["candle_end_utc"] = pd.to_datetime(
        c["candle_end_utc"], errors="coerce", utc=True
    )
    for col in ["yes_ask","yes_bid","no_ask"]:
        c[col] = pd.to_numeric(c[col], errors="coerce")
    if "no_bid" not in c.columns:
        c["no_bid"] = 1.0-c["yes_ask"]
    else:
        c["no_bid"] = pd.to_numeric(c["no_bid"], errors="coerce")
    return c.dropna(subset=["contract","candle_end_utc"]).sort_values(
        ["contract","candle_end_utc"]
    )

def future_outcome_matrix(pool, candles, exit_rules):
    """
    Matrix shape N rows x R exit rules.
    -1 = no usable future candle
     0 = loss/no target
     1 = profit target hit before stop
    """
    n=len(pool); R=len(exit_rules)
    out=np.full((n,R),-1,dtype=np.int8)

    grouped_candles={k:g.sort_values("candle_end_utc") for k,g in candles.groupby("contract")}
    for i,r in pool.iterrows():
        ticker=r["ticker"]
        cg=grouped_candles.get(ticker)
        if cg is None or cg.empty:
            continue
        t0=pd.Timestamp(r["snapshot_utc"])
        side=r["preferred_side"]
        entry=float(r["preferred_ask"])
        bid_col="yes_bid" if side=="UP" else "no_bid"

        for j,(pt,sl,hz) in enumerate(exit_rules):
            t1=t0+pd.Timedelta(minutes=int(hz))
            sub=cg[
                (cg["candle_end_utc"]>t0)
                &(cg["candle_end_utc"]<=t1)
            ]
            if sub.empty:
                continue
            target=entry+pt
            stop=entry-sl
            usable=False
            result=0
            for bid in sub[bid_col].to_numpy():
                if pd.isna(bid):
                    continue
                usable=True
                b=float(bid)
                if b <= stop:
                    result=0
                    break
                if b >= target:
                    result=1
                    break
            if usable:
                out[i,j]=result
    return out

def vectorized_scalp_tournament(pool,candles):
    scalp_ask=[.30,.40,.50,.60,.70]
    scalp_fair=[.52,.55,.60,.65,.70]
    scalp_edge=[.00,.03,.05,.08,.10]
    scalp_min_tl=[3.,5.,7.,9.]
    scalp_max_tl=[10.,12.,14.]
    scalp_gap=[0.,25.,50.]
    profit_targets=[.08,.10,.12,.15,.20]
    stop_losses=[.05,.08,.10,.12]
    horizons=[2,3,4,5]

    exit_rules=[(pt,sl,hz) for pt in profit_targets for sl in stop_losses for hz in horizons]
    filters=[]
    for ask_max in scalp_ask:
      for fair_min in scalp_fair:
       for edge_min in scalp_edge:
        for min_tl in scalp_min_tl:
         for max_tl in scalp_max_tl:
          if min_tl>max_tl:
              continue
          for min_gap in scalp_gap:
            filters.append(dict(
                ask_max=ask_max,fair_min=fair_min,edge_min=edge_min,
                min_tl=min_tl,max_tl=max_tl,min_gap=min_gap
            ))

    pool=pool.sort_values(["ticker","elapsed"]).reset_index(drop=True)
    print(
        f"Precomputing future outcomes: {len(pool)} snapshots x "
        f"{len(exit_rules)} exit rules..."
    )
    outcomes=future_outcome_matrix(pool,candles,exit_rules)

    ask=pool["preferred_ask"].to_numpy(float)
    fair=pool["preferred_fair"].to_numpy(float)
    edge=pool["edge"].to_numpy(float)
    rem=pool["remaining"].to_numpy(float)
    gap=pool["abs_dist_target"].to_numpy(float)
    tick=pool["ticker"].astype(str).to_numpy()
    unique_ticks=list(dict.fromkeys(tick.tolist()))
    contract_indices={t:np.where(tick==t)[0] for t in unique_ticks}

    rows=[]
    print(
        f"Vectorized exact search: {len(filters):,} filters x "
        f"{len(exit_rules)} exit rules = {len(filters)*len(exit_rules):,} combinations"
    )

    for fi,p in enumerate(filters,1):
        base=(
            (ask<=p["ask_max"])
            &(fair>=p["fair_min"])
            &(edge>=p["edge_min"])
            &(rem>=p["min_tl"])
            &(rem<=p["max_tl"])
            &(gap>=p["min_gap"])
        )
        if not base.any():
            continue

        # Accumulate first-valid candidate per contract for ALL exit rules together.
        calls=np.zeros(len(exit_rules),dtype=np.int16)
        wins=np.zeros(len(exit_rules),dtype=np.int16)
        ask_sum=np.zeros(len(exit_rules),dtype=float)
        time_sum=np.zeros(len(exit_rules),dtype=float)

        for t,inds in contract_indices.items():
            inds=inds[base[inds]]
            if len(inds)==0:
                continue
            unresolved=np.ones(len(exit_rules),dtype=bool)
            for idx in inds:
                valid=(outcomes[idx]>=0)&unresolved
                if valid.any():
                    calls[valid]+=1
                    wins[valid]+=outcomes[idx,valid]
                    ask_sum[valid]+=ask[idx]
                    time_sum[valid]+=rem[idx]
                    unresolved[valid]=False
                if not unresolved.any():
                    break

        good=calls>0
        for j in np.where(good)[0]:
            pt,sl,hz=exit_rules[j]
            rows.append({
                **p,
                "profit_target":pt,
                "stop_loss":sl,
                "horizon":hz,
                "calls":int(calls[j]),
                "contracts":len(unique_ticks),
                "coverage":float(calls[j]/max(len(unique_ticks),1)),
                "accuracy":float(wins[j]/calls[j]),
                "avg_ask":float(ask_sum[j]/calls[j]),
                "avg_time_left":float(time_sum[j]/calls[j]),
            })

        if fi % 750 == 0:
            print(f"  filters scored {fi}/{len(filters)}")

    res=pd.DataFrame(rows)
    if res.empty:
        raise SystemExit("No scalp candidates")
    min_calls=max(8,int(np.ceil(len(unique_ticks)*.08)))
    e=res[res["calls"]>=min_calls].copy()
    if e.empty: e=res[res["calls"]>=5].copy()
    if e.empty: e=res.copy()
    e["meets75"]=e["accuracy"]>=.75
    e=e.sort_values(
        ["meets75","accuracy","coverage","profit_target","avg_time_left","avg_ask"],
        ascending=[False,False,False,False,False,True]
    ).reset_index(drop=True)
    e["validation_rank"]=np.arange(1,len(e)+1)
    e.to_csv(SCALP_RESULTS,index=False)

    keys=[
        "ask_max","fair_min","edge_min","min_tl","max_tl","min_gap",
        "profit_target","stop_loss","horizon"
    ]
    winner={k:e.iloc[0][k] for k in keys}
    return winner,keys

def score_scalp_one(frame,candles,p):
    mask=(
        (frame["preferred_ask"]<=p["ask_max"])
        &(frame["preferred_fair"]>=p["fair_min"])
        &(frame["edge"]>=p["edge_min"])
        &(frame["remaining"]>=p["min_tl"])
        &(frame["remaining"]<=p["max_tl"])
        &(frame["abs_dist_target"]>=p["min_gap"])
    )
    q=frame[mask].sort_values(["ticker","elapsed"])
    picked=[]
    for ticker,g in q.groupby("ticker",sort=False):
        for _,r in g.iterrows():
            # exact one-rule chronological outcome
            side=r["preferred_side"]; entry=float(r["preferred_ask"])
            t0=pd.Timestamp(r["snapshot_utc"])
            t1=t0+pd.Timedelta(minutes=int(p["horizon"]))
            cg=candles[
                (candles["contract"]==ticker)
                &(candles["candle_end_utc"]>t0)
                &(candles["candle_end_utc"]<=t1)
            ].sort_values("candle_end_utc")
            if cg.empty: continue
            bid_col="yes_bid" if side=="UP" else "no_bid"
            target=entry+p["profit_target"]; stop=entry-p["stop_loss"]
            usable=False; win=False
            for bid in cg[bid_col].to_numpy():
                if pd.isna(bid): continue
                usable=True
                b=float(bid)
                if b<=stop:
                    win=False; break
                if b>=target:
                    win=True; break
            if not usable: continue
            rr=r.copy(); rr["scalp_win"]=win
            picked.append(rr); break

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
    print("UNION COVERAGE OPTIMIZER V1.2 — RESUME + VECTORIZED")
    print("NO FEATURE REBUILD — NO MODEL RETRAIN — NO ORDERS")
    print("="*78)

    d=load_cache()
    valid_ticks,hold_ticks=contract_split(d)
    valid=d[d["ticker"].isin(valid_ticks)].copy()
    hold=d[d["ticker"].isin(hold_ticks)].copy()

    print(
        f"Loaded processed cache: {len(d)} snapshots | "
        f"validation {len(valid_ticks)} contracts | holdout {len(hold_ticks)} contracts"
    )

    # Locked Tier-1 anchors
    v_t1_first=first_contract_rows(valid,locked_tier1_mask(valid))
    h_t1_first=first_contract_rows(hold,locked_tier1_mask(hold))
    valid_t1=set(v_t1_first["ticker"]) if not v_t1_first.empty else set()
    hold_t1=set(h_t1_first["ticker"]) if not h_t1_first.empty else set()

    valid_sec_pool=valid[~valid["ticker"].isin(valid_t1)].copy()
    hold_sec_pool=hold[~hold["ticker"].isin(hold_t1)].copy()

    print("Scoring SECONDARY entry tournament from processed cache...")
    sec_win,sec_keys=secondary_tournament(valid_sec_pool)
    sec_v,sec_v_calls=score_secondary(valid_sec_pool,sec_win)
    sec_h,sec_h_calls=score_secondary(hold_sec_pool,sec_win)
    valid_sec=set(sec_v_calls["ticker"]) if not sec_v_calls.empty else set()
    hold_sec=set(sec_h_calls["ticker"]) if not sec_h_calls.empty else set()

    valid_scalp_pool=valid[~valid["ticker"].isin(valid_t1|valid_sec)].copy()
    hold_scalp_pool=hold[~hold["ticker"].isin(hold_t1|hold_sec)].copy()

    candles=load_candles()
    scalp_win,scalp_keys=vectorized_scalp_tournament(valid_scalp_pool,candles)
    sc_v,sc_v_calls=score_scalp_one(valid_scalp_pool,candles,scalp_win)
    sc_h,sc_h_calls=score_scalp_one(hold_scalp_pool,candles,scalp_win)

    valid_scalp=set(sc_v_calls["ticker"]) if not sc_v_calls.empty else set()
    hold_scalp=set(sc_h_calls["ticker"]) if not sc_h_calls.empty else set()

    valid_union=valid_t1|valid_sec|valid_scalp
    hold_union=hold_t1|hold_sec|hold_scalp

    detail=[]
    for ticker in sorted(hold_ticks):
        detail.append({
            "ticker":ticker,
            "tier1_entry":ticker in hold_t1,
            "secondary_entry":ticker in hold_sec,
            "scalp":ticker in hold_scalp,
            "any_actionable":ticker in hold_union,
        })
    pd.DataFrame(detail).to_csv(HOLDOUT_DETAIL,index=False)

    lines=[]
    lines.append("="*78)
    lines.append("UNION COVERAGE OPTIMIZER V1.2 SUMMARY")
    lines.append("="*78)
    lines.append("")
    lines.append("LOCKED TIER-1 ENTRY")
    lines.append(
        f"Validation coverage: {len(valid_t1)}/{len(valid_ticks)} "
        f"({pct(len(valid_t1)/len(valid_ticks))})"
    )
    lines.append(
        f"Holdout coverage: {len(hold_t1)}/{len(hold_ticks)} "
        f"({pct(len(hold_t1)/len(hold_ticks))})"
    )
    lines.append("")
    lines.append("SECONDARY ENTRY WINNER — selected on validation only")
    for k in sec_keys:
        lines.append(f"{k}: {sec_win[k]}")
    lines.append(
        f"Validation: accuracy {pct(sec_v['accuracy'])} | calls {sec_v['calls']} | "
        f"avg ask {100*sec_v['avg_ask']:.1f}c | "
        f"avg time left {sec_v['avg_time_left']:.2f}m"
    )
    if sec_h is None:
        lines.append("Holdout: no calls")
    else:
        lines.append(
            f"Holdout: accuracy {pct(sec_h['accuracy'])} | calls {sec_h['calls']} | "
            f"avg ask {100*sec_h['avg_ask']:.1f}c | "
            f"avg time left {sec_h['avg_time_left']:.2f}m"
        )
    lines.append("")
    lines.append("SCALP WINNER — selected on validation only")
    for k in scalp_keys:
        lines.append(f"{k}: {scalp_win[k]}")
    lines.append(
        f"Validation: win rate {pct(sc_v['accuracy'])} | calls {sc_v['calls']} | "
        f"avg ask {100*sc_v['avg_ask']:.1f}c | "
        f"avg time left {sc_v['avg_time_left']:.2f}m"
    )
    if sc_h is None:
        lines.append("Holdout: no calls")
    else:
        lines.append(
            f"Holdout: win rate {pct(sc_h['accuracy'])} | calls {sc_h['calls']} | "
            f"avg ask {100*sc_h['avg_ask']:.1f}c | "
            f"avg time left {sc_h['avg_time_left']:.2f}m"
        )
    lines.append("")
    lines.append("UNION ACTIONABLE COVERAGE")
    lines.append(
        f"Validation: {len(valid_union)}/{len(valid_ticks)} "
        f"({pct(len(valid_union)/len(valid_ticks))})"
    )
    lines.append(
        f"Untouched holdout: {len(hold_union)}/{len(hold_ticks)} "
        f"({pct(len(hold_union)/len(hold_ticks))})"
    )
    lines.append("")
    lines.append("INTEGRITY")
    lines.append("- Loaded V1.1 processed cache; no feature/model rebuild")
    lines.append("- Locked Tier-1 unchanged")
    lines.append("- Secondary selected on validation only")
    lines.append("- Scalp selected on validation only")
    lines.append("- Actual ask entry / actual future bid exit")
    lines.append("- Spread included")
    lines.append("- Stop before target chronology")
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
