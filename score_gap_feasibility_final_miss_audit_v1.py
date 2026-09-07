
import warnings, math
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")
AUDIT = Path("union_coverage_gap_audit_v1_contracts.csv")

OUT_GAPS = Path("gap_feasibility_v1_details.csv")
OUT_MISSES = Path("final_miss_audit_v1_details.csv")

HORIZON = 180
ROI_TARGETS = [0.18, 0.25]
ROI_STOP = 0.18
ASK_MAX = 0.50
MIN_MOVE_C = 4

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def num(df,c):
    if c not in df.columns:
        df[c] = np.nan
    df[c] = pd.to_numeric(df[c],errors="coerce")

def roi_delta(entry, roi):
    return max(
        MIN_MOVE_C/100.0,
        math.ceil(float(entry)*float(roi)*100 - 1e-12)/100.0
    )

print("="*86)
print("GAP FEASIBILITY + FINAL MISS AUDIT V1")
print("="*86)

if not UNIFIED.exists():
    raise SystemExit("ERROR: unified log missing")
if not AUDIT.exists():
    raise SystemExit(
        "ERROR: union_coverage_gap_audit_v1_contracts.csv missing. "
        "Run the union audit first."
    )

u = pd.read_csv(UNIFIED)
a = pd.read_csv(AUDIT)

u["timestamp_utc"] = pd.to_datetime(
    u["timestamp_utc"],errors="coerce",utc=True
)

for c in [
    "minutes_left","side_ask","side_bid","side_fair","side_edge",
    "preferred_fair","preferred_edge","abs_btc_gap","btc_gap",
    "dist_over_range5","brti_age_seconds","brti_gap_to_target",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
]:
    num(u,c)

u["brti_ready_b"] = u.get(
    "brti_ready", pd.Series(False,index=u.index)
).map(truthy)
u["brti_agrees_b"] = u.get(
    "brti_agrees_side", pd.Series(False,index=u.index)
).map(truthy)

# ------------------------------------------------------------------
# PART A: THEORETICAL / FEASIBILITY AUDIT ON THE FIVE UNION GAPS
# ------------------------------------------------------------------

a["union_actionable"] = a["union_actionable"].map(truthy)
gaps = a[~a["union_actionable"]].copy()

print(f"UNION GAPS TO AUDIT: {len(gaps)}")
print("-"*86)

gap_rows = []

for _, gr in gaps.iterrows():
    contract = str(gr["contract"])
    cu = u[u["contract"].astype(str)==contract].copy()
    cu = cu[
        cu["minutes_left"].between(2.0,10.0,inclusive="both")
        & (cu["side_ask"]<=ASK_MAX)
        & cu["side_bid"].notna()
    ].sort_values(["side","timestamp_utc"])

    best_by_roi = {}

    for target_roi in ROI_TARGETS:
        best = None

        for side, gs in cu.groupby("side",sort=False):
            gs = gs.sort_values("timestamp_utc").reset_index(drop=True)
            ts = gs["timestamp_utc"].tolist()
            asks = gs["side_ask"].astype(float).to_numpy()
            bids = gs["side_bid"].astype(float).to_numpy()

            for i in range(len(gs)):
                entry = asks[i]
                if not np.isfinite(entry):
                    continue

                target_delta = roi_delta(entry,target_roi)
                stop_delta = roi_delta(entry,ROI_STOP)
                t0 = ts[i]

                first_target = None
                first_stop = None
                max_bid = bids[i]

                for j in range(i,len(gs)):
                    dt = (ts[j]-t0).total_seconds()
                    if dt < 0:
                        continue
                    if dt > HORIZON:
                        break

                    bid = bids[j]
                    if not np.isfinite(bid):
                        continue

                    max_bid = max(max_bid,bid)

                    if (
                        first_target is None
                        and bid >= entry + target_delta
                    ):
                        first_target = dt

                    if (
                        first_stop is None
                        and bid <= entry - stop_delta
                    ):
                        first_stop = dt

                    if first_target is not None or first_stop is not None:
                        if (
                            first_target is not None
                            and (
                                first_stop is None
                                or first_target <= first_stop
                            )
                        ):
                            break
                        if (
                            first_stop is not None
                            and (
                                first_target is None
                                or first_stop < first_target
                            )
                        ):
                            break

                win = (
                    first_target is not None
                    and (
                        first_stop is None
                        or first_target <= first_stop
                    )
                )

                max_roi = (
                    (max_bid-entry)/entry
                    if entry>0 and np.isfinite(max_bid)
                    else np.nan
                )

                candidate = {
                    "contract":contract,
                    "gap_type":gr.get("gap_type",""),
                    "target_roi":target_roi,
                    "side":side,
                    "timestamp_utc":ts[i],
                    "minutes_left":float(gs.iloc[i]["minutes_left"]),
                    "entry_ask":entry,
                    "target_delta_c":target_delta*100,
                    "stop_delta_c":stop_delta*100,
                    "win_before_stop":bool(win),
                    "seconds_to_target":first_target,
                    "seconds_to_stop":first_stop,
                    "max_roi_pct":max_roi*100 if np.isfinite(max_roi) else np.nan,
                    "reversal_state":gs.iloc[i].get("reversal_state",""),
                    "brti_side":gs.iloc[i].get("brti_side",""),
                    "brti_agrees_side":gs.iloc[i].get("brti_agrees_side",""),
                    "lag15":gs.iloc[i].get("kalshi_lag_15s",""),
                    "lag30":gs.iloc[i].get("kalshi_lag_30s",""),
                }

                if best is None:
                    best = candidate
                else:
                    # Prefer a true win, then earlier timing, then cheaper entry,
                    # then larger max ROI.
                    score_new = (
                        int(candidate["win_before_stop"]),
                        candidate["minutes_left"],
                        -candidate["entry_ask"],
                        candidate["max_roi_pct"]
                        if np.isfinite(candidate["max_roi_pct"]) else -999
                    )
                    score_old = (
                        int(best["win_before_stop"]),
                        best["minutes_left"],
                        -best["entry_ask"],
                        best["max_roi_pct"]
                        if np.isfinite(best["max_roi_pct"]) else -999
                    )
                    if score_new > score_old:
                        best = candidate

        best_by_roi[target_roi] = best
        if best is not None:
            gap_rows.append(best)

    b18 = best_by_roi.get(0.18)
    b25 = best_by_roi.get(0.25)

    def brief(b):
        if b is None:
            return "NONE"
        return (
            f"{'YES' if b['win_before_stop'] else 'NO'} | "
            f"{b['side']} {b['entry_ask']*100:.0f}c | "
            f"{b['minutes_left']:.2f}m left | "
            f"target +{b['target_delta_c']:.0f}c"
        )

    print(f"{contract} | {gr.get('gap_type','')}")
    print(f"  18% ROI opportunity: {brief(b18)}")
    print(f"  25% ROI opportunity: {brief(b25)}")

gap_df = pd.DataFrame(gap_rows)
gap_df.to_csv(OUT_GAPS,index=False)

if len(gaps):
    per_contract_18 = (
        gap_df[gap_df["target_roi"]==0.18]
        .groupby("contract")["win_before_stop"]
        .max()
    )
    feasible18 = int(per_contract_18.sum()) if len(per_contract_18) else 0
else:
    feasible18 = 0

print("-"*86)
print(
    f"18% ROI FEASIBLE UNION GAPS: "
    f"{feasible18}/{len(gaps)}"
)

# ------------------------------------------------------------------
# PART B: AUDIT THE TWO FINAL MISSES ON THIS SAME 41-CONTRACT SAMPLE
# ------------------------------------------------------------------

a["final_call"] = a["final_call"].map(truthy)
a["final_correct"] = a["final_correct"].map(truthy)

misses = a[
    a["final_call"] & ~a["final_correct"]
].copy()

print("="*86)
print(f"FINAL MISSES ON SAME-CONTRACT SAMPLE: {len(misses)}")
print("-"*86)

miss_rows=[]

for _, mr in misses.iterrows():
    contract=str(mr["contract"])
    side=str(mr["final_side"])
    call_left=float(mr["final_time_left"])

    cu=u[
        (u["contract"].astype(str)==contract)
        & (u["side"].astype(str)==side)
    ].copy()

    if cu.empty:
        print(f"{contract}: no matching unified row")
        continue

    # Nearest row by minutes-left.
    cu["_delta_left"]=(cu["minutes_left"]-call_left).abs()
    row=cu.sort_values("_delta_left").iloc[0]

    detail={
        "contract":contract,
        "official_side":mr.get("official_side",""),
        "final_side":side,
        "final_time_left":call_left,
        "side_ask":row.get("side_ask",np.nan),
        "side_fair":row.get("side_fair",np.nan),
        "preferred_fair":row.get("preferred_fair",np.nan),
        "preferred_edge":row.get("preferred_edge",np.nan),
        "abs_btc_gap":row.get("abs_btc_gap",np.nan),
        "dist_over_range5":row.get("dist_over_range5",np.nan),
        "brti_side":row.get("brti_side",""),
        "brti_gap_to_target":row.get("brti_gap_to_target",np.nan),
        "brti_age_seconds":row.get("brti_age_seconds",np.nan),
        "brti_agrees_side":row.get("brti_agrees_side",""),
        "reversal_state":row.get("reversal_state",""),
        "btc_move_15s_side":row.get("btc_move_15s_side",np.nan),
        "btc_move_30s_side":row.get("btc_move_30s_side",np.nan),
        "ask_move_15s":row.get("ask_move_15s",np.nan),
        "ask_move_30s":row.get("ask_move_30s",np.nan),
        "fair_move_15s":row.get("fair_move_15s",np.nan),
        "fair_move_30s":row.get("fair_move_30s",np.nan),
    }
    miss_rows.append(detail)

    fair = detail["preferred_fair"]
    gap = detail["abs_btc_gap"]
    dor = detail["dist_over_range5"]
    brti_gap = detail["brti_gap_to_target"]

    print(
        f"{contract} | called {side} | settled {detail['official_side']} | "
        f"{call_left:.2f}m left"
    )
    print(
        f"  fair "
        f"{'NA' if pd.isna(fair) else f'{fair*100:.1f}%'} | "
        f"BTC gap "
        f"{'NA' if pd.isna(gap) else f'${gap:.0f}'} | "
        f"dist/range "
        f"{'NA' if pd.isna(dor) else f'{dor:.2f}'}"
    )
    print(
        f"  BRTI side {detail['brti_side']} | "
        f"BRTI gap "
        f"{'NA' if pd.isna(brti_gap) else f'${brti_gap:.0f}'} | "
        f"reversal {detail['reversal_state']}"
    )

miss_df=pd.DataFrame(miss_rows)
miss_df.to_csv(OUT_MISSES,index=False)

print("="*86)

if len(gaps) and feasible18 >= 3:
    print("DIRECTION: MOST UNION GAPS CONTAIN 18%+ TEMPORARY-MOVE OPPORTUNITY.")
    print("NEXT PATH SHOULD BE A TARGETED CHOP/REVERSAL SCALP DETECTOR.")
elif len(gaps) and feasible18 >= 1:
    print("DIRECTION: SOME UNION GAPS ARE TRADEABLE, SOME MAY BE TRUE PASS.")
    print("BUILD ONLY THE SPECIFIC REVERSAL REGIME THAT SHOWS FEASIBILITY.")
else:
    print("DIRECTION: THESE UNION GAPS SHOW LITTLE 18% SCALP FEASIBILITY.")
    print("DO NOT FORCE COVERAGE; TRUE PASS MAY BE APPROPRIATE.")

if len(misses):
    print(
        "FINAL MISS AUDIT SAVED. "
        "Inspect these before final Kalshi-app parity / production lock."
    )

print(f"Saved gap details: {OUT_GAPS}")
print(f"Saved final miss details: {OUT_MISSES}")
print("="*86)
