
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")
AUDIT = Path("union_coverage_gap_audit_v1_contracts.csv")
OUT = Path("final_mixed_45s_union_impact_v1.csv")

DELAY = 45

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def num(df,c):
    if c not in df.columns:
        df[c] = np.nan
    df[c] = pd.to_numeric(df[c], errors="coerce")

print("="*86)
print("FINAL MIXED 45s RECHECK — UNION COVERAGE IMPACT V1")
print("="*86)

if not UNIFIED.exists():
    raise SystemExit("ERROR: unified log missing")
if not AUDIT.exists():
    raise SystemExit("ERROR: union audit contract file missing")

u = pd.read_csv(UNIFIED)
a = pd.read_csv(AUDIT)

u["timestamp_utc"] = pd.to_datetime(
    u["timestamp_utc"], errors="coerce", utc=True
)

for c in [
    "minutes_left","preferred_fair","abs_btc_gap",
    "dist_over_range5","brti_age_seconds","brti_gap_to_target"
]:
    num(u,c)

u["brti_ready_b"] = u.get(
    "brti_ready", pd.Series(False,index=u.index)
).map(truthy)
u["reversal_state"] = u.get(
    "reversal_state", pd.Series("",index=u.index)
).fillna("").astype(str).str.upper()

# Reconstruct frozen FINAL gate.
fr = u[
    u["preferred_fair_side"].isin(["UP","DOWN"])
    & (u["side"] == u["preferred_fair_side"])
].copy()

fr["required_gap"] = np.where(
    fr["minutes_left"] > 6.0, 75.0, 50.0
)

fr["final_ready"] = (
    fr["minutes_left"].between(0.0,8.0,inclusive="both")
    & (fr["preferred_fair"] >= .90)
    & (fr["abs_btc_gap"] >= fr["required_gap"])
    & (fr["dist_over_range5"] >= 1.0)
    & (fr["preferred_fair_side"] == fr["current_target_side"])
    & fr["brti_ready_b"]
    & (fr["brti_age_seconds"] <= 5.0)
    & (fr["brti_gap_to_target"].abs() > 11.0)
    & (fr["brti_side"] == fr["preferred_fair_side"])
)

ready = fr[fr["final_ready"]].copy().sort_values(
    ["contract","timestamp_utc"]
)
first = ready.groupby("contract",as_index=False).head(1).copy()

# Normalize union audit booleans.
for c in ["final_call","final_correct","scalp_signal","union_actionable"]:
    a[c+"_b"] = a[c].map(truthy)

meta = a.set_index("contract").to_dict("index")

rows = []

for _,r in first.iterrows():
    contract = str(r["contract"])
    side = str(r["preferred_fair_side"])
    original_ts = r["timestamp_utc"]
    original_left = float(r["minutes_left"])
    original_state = str(r["reversal_state"])

    official = meta.get(contract,{}).get("official_side")
    scalp = bool(meta.get(contract,{}).get("scalp_signal_b",False))

    keep = True
    guarded_ts = original_ts
    guarded_left = original_left
    guarded_state = original_state
    status = "UNCHANGED_NON_MIXED"

    if original_state == "MIXED":
        deadline = original_ts + pd.Timedelta(seconds=DELAY)

        cand = ready[
            (ready["contract"].astype(str) == contract)
            & (ready["preferred_fair_side"] == side)
            & (ready["timestamp_utc"] > original_ts)
            & (ready["timestamp_utc"] <= deadline)
            & (ready["reversal_state"] != "MIXED")
        ].copy()

        if cand.empty:
            keep = False
            guarded_ts = pd.NaT
            guarded_left = np.nan
            guarded_state = ""
            status = "SUPPRESSED_MIXED_NO_CLEAR"
        else:
            rr = cand.sort_values("timestamp_utc").iloc[0]
            guarded_ts = rr["timestamp_utc"]
            guarded_left = float(rr["minutes_left"])
            guarded_state = str(rr["reversal_state"])
            status = "RECOVERED_AFTER_45S_CLEAR"

    correct = bool(side == official) if keep else np.nan

    rows.append({
        "contract":contract,
        "official_side":official,
        "final_side":side,
        "original_state":original_state,
        "original_time_left":original_left,
        "guarded_final_call":keep,
        "guarded_time_left":guarded_left,
        "guarded_state":guarded_state,
        "guarded_correct":correct,
        "status":status,
        "scalp_signal":scalp,
        "guarded_union_actionable":bool(keep or scalp),
    })

# Add contracts that had no FINAL at baseline so union denominator remains complete.
seen = {r["contract"] for r in rows}
for _,r in a.iterrows():
    contract = str(r["contract"])
    if contract in seen:
        continue
    scalp = bool(r["scalp_signal_b"])
    rows.append({
        "contract":contract,
        "official_side":r.get("official_side"),
        "final_side":None,
        "original_state":None,
        "original_time_left":np.nan,
        "guarded_final_call":False,
        "guarded_time_left":np.nan,
        "guarded_state":None,
        "guarded_correct":np.nan,
        "status":"NO_BASE_FINAL",
        "scalp_signal":scalp,
        "guarded_union_actionable":scalp,
    })

x = pd.DataFrame(rows)

baseline_final = a[a["final_call_b"]].copy()
baseline_final_n = len(baseline_final)
baseline_final_correct = int(baseline_final["final_correct_b"].sum())

guard = x[x["guarded_final_call"]].copy()
guard_n = len(guard)
guard_correct = int(
    guard["guarded_correct"].fillna(False).astype(bool).sum()
)

baseline_union_n = int(a["union_actionable_b"].sum())
guard_union_n = int(x["guarded_union_actionable"].sum())
n = len(a)

supp = x[x["status"]=="SUPPRESSED_MIXED_NO_CLEAR"].copy()
supp_n = len(supp)
supp_scalp = int(supp["scalp_signal"].sum())
supp_still_union = supp_scalp
supp_lost_union = supp_n - supp_still_union

print("FINAL COMPARISON")
print(
    f"BASE FINAL:  {baseline_final_correct}/{baseline_final_n} = "
    f"{baseline_final_correct/baseline_final_n*100:.1f}% | "
    f"coverage {baseline_final_n}/{n} = {baseline_final_n/n*100:.1f}%"
)
print(
    f"45s GUARDED: {guard_correct}/{guard_n} = "
    f"{guard_correct/guard_n*100:.1f}% | "
    f"coverage {guard_n}/{n} = {guard_n/n*100:.1f}% | "
    f"avg {guard['guarded_time_left'].mean():.2f}m left"
)

print("-"*86)
print("SUPPRESSED MIXED CALLS")
print(f"SUPPRESSED: {supp_n}")
print(f"ALREADY COVERED BY PRIMARY SCALP: {supp_still_union}")
print(f"ACTUAL UNION COVERAGE LOST: {supp_lost_union}")

if supp_n:
    for _,r in supp.iterrows():
        print(
            f"  {r['contract']} | final {r['final_side']} | "
            f"settled {r['official_side']} | "
            f"{'SCALP COVERS' if r['scalp_signal'] else 'BECOMES GAP'}"
        )

print("-"*86)
print("UNION ACTIONABLE COVERAGE")
print(
    f"BASE UNION:  {baseline_union_n}/{n} = "
    f"{baseline_union_n/n*100:.1f}%"
)
print(
    f"45s UNION:   {guard_union_n}/{n} = "
    f"{guard_union_n/n*100:.1f}%"
)
print(
    f"UNION CHANGE: {guard_union_n-baseline_union_n:+d} contracts | "
    f"{(guard_union_n-baseline_union_n)/n*100:+.1f} percentage points"
)

# Timing cost only among delayed-and-recovered calls.
recovered = x[x["status"]=="RECOVERED_AFTER_45S_CLEAR"].copy()
if len(recovered):
    timing_cost = (
        recovered["original_time_left"] - recovered["guarded_time_left"]
    )
    print("-"*86)
    print("RECOVERED MIXED TIMING COST")
    print(f"RECOVERED: {len(recovered)}")
    print(f"AVG DELAY COST: {timing_cost.mean()*60:.1f} seconds")
    print(f"MAX DELAY COST: {timing_cost.max()*60:.1f} seconds")

x.to_csv(OUT,index=False)

print("="*86)

if (
    guard_n >= 20
    and guard_correct == guard_n
    and guard_union_n >= baseline_union_n - 1
):
    print("AUDIT RESULT: 45s MIXED RECHECK IS A STRONG SHADOW CANDIDATE")
    print("NEXT: forward-test BASE FINAL and GUARDED FINAL side-by-side.")
    print("DO NOT replace frozen FINAL yet.")
elif (
    guard_n >= 20
    and guard_correct/guard_n >= .95
    and guard_union_n >= baseline_union_n - 2
):
    print("AUDIT RESULT: 45s MIXED RECHECK IS PROMISING, WITH A COVERAGE COST")
    print("NEXT: shadow-test before any FINAL change.")
else:
    print("AUDIT RESULT: COVERAGE COST IS TOO HIGH OR ACCURACY GAIN TOO WEAK")
    print("Keep frozen FINAL unchanged.")

print(f"Saved detail: {OUT}")
print("="*86)
