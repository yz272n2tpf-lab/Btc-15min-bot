
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")
AUDIT = Path("union_coverage_gap_audit_v1_contracts.csv")
OUT = Path("final_45s_reconciliation_v1.csv")

DELAY = 45

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def num(df,c):
    if c not in df.columns:
        df[c] = np.nan
    df[c] = pd.to_numeric(df[c], errors="coerce")

print("="*92)
print("FINAL 45s MIXED RECHECK — RECONCILIATION V1")
print("SOURCE OF TRUTH: THE 27 BASELINE FINAL CALLS FROM UNION AUDIT")
print("="*92)

if not UNIFIED.exists():
    raise SystemExit("ERROR: unified log missing")
if not AUDIT.exists():
    raise SystemExit("ERROR: union audit missing")

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

a["final_call_b"] = a["final_call"].map(truthy)
a["final_correct_b"] = a["final_correct"].map(truthy)
a["scalp_signal_b"] = a["scalp_signal"].map(truthy)
a["union_actionable_b"] = a["union_actionable"].map(truthy)

base = a[a["final_call_b"]].copy()

print(
    f"BASELINE FROM UNION AUDIT: "
    f"{int(base['final_correct_b'].sum())}/{len(base)} = "
    f"{base['final_correct_b'].mean()*100:.1f}%"
)

# Reconstruct frozen FINAL-ready rows once.
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

rows = []

for _,b in base.iterrows():
    contract = str(b["contract"])
    side = str(b["final_side"])
    official = str(b["official_side"])
    base_left = float(b["final_time_left"])
    scalp = bool(b["scalp_signal_b"])

    # Anchor to the exact baseline call stored by union audit:
    # same contract, same side, nearest minutes-left among frozen-ready rows.
    cand0 = ready[
        (ready["contract"].astype(str) == contract)
        & (ready["preferred_fair_side"].astype(str) == side)
    ].copy()

    if cand0.empty:
        rows.append({
            "contract":contract,"official_side":official,"final_side":side,
            "baseline_correct":bool(b["final_correct_b"]),
            "baseline_time_left":base_left,
            "anchor_found":False,
            "anchor_time_left":np.nan,"anchor_delta_seconds":np.nan,
            "anchor_reversal":"",
            "guarded_call":False,"guarded_correct":np.nan,
            "guarded_time_left":np.nan,"guarded_reversal":"",
            "guard_status":"NO_READY_ANCHOR",
            "scalp_signal":scalp
        })
        continue

    cand0["_left_delta"] = (cand0["minutes_left"] - base_left).abs()
    r0 = cand0.sort_values(
        ["_left_delta","timestamp_utc"]
    ).iloc[0]

    anchor_ts = r0["timestamp_utc"]
    anchor_left = float(r0["minutes_left"])
    anchor_state = str(r0["reversal_state"])
    delta_sec = abs(anchor_left-base_left)*60.0

    guarded_call = True
    guarded_correct = (side == official)
    guarded_left = anchor_left
    guarded_state = anchor_state
    status = "UNCHANGED_NON_MIXED"

    if anchor_state == "MIXED":
        deadline = anchor_ts + pd.Timedelta(seconds=DELAY)
        rc = ready[
            (ready["contract"].astype(str) == contract)
            & (ready["preferred_fair_side"].astype(str) == side)
            & (ready["timestamp_utc"] > anchor_ts)
            & (ready["timestamp_utc"] <= deadline)
            & (ready["reversal_state"] != "MIXED")
        ].copy()

        if rc.empty:
            guarded_call = False
            guarded_correct = np.nan
            guarded_left = np.nan
            guarded_state = ""
            status = "SUPPRESSED_MIXED_NO_CLEAR"
        else:
            rr = rc.sort_values("timestamp_utc").iloc[0]
            guarded_left = float(rr["minutes_left"])
            guarded_state = str(rr["reversal_state"])
            guarded_correct = (side == official)
            status = "RECOVERED_AFTER_CLEAR"

    rows.append({
        "contract":contract,
        "official_side":official,
        "final_side":side,
        "baseline_correct":bool(b["final_correct_b"]),
        "baseline_time_left":base_left,
        "anchor_found":True,
        "anchor_time_left":anchor_left,
        "anchor_delta_seconds":delta_sec,
        "anchor_reversal":anchor_state,
        "guarded_call":guarded_call,
        "guarded_correct":guarded_correct,
        "guarded_time_left":guarded_left,
        "guarded_reversal":guarded_state,
        "guard_status":status,
        "scalp_signal":scalp,
    })

x = pd.DataFrame(rows)

print("-"*92)
print("ANCHOR CHECK")
print(
    f"Exact/near baseline anchors found: "
    f"{int(x['anchor_found'].sum())}/{len(x)}"
)
if x["anchor_found"].any():
    print(
        f"Max baseline-vs-anchor timing difference: "
        f"{x.loc[x['anchor_found'],'anchor_delta_seconds'].max():.1f}s"
    )

print("-"*92)
print("MIXED BASELINE CALLS — CONTRACT BY CONTRACT")

mx = x[x["anchor_reversal"]=="MIXED"].copy()
for _,r in mx.iterrows():
    if r["guarded_call"]:
        fate = (
            f"CALL {r['final_side']} @ {r['guarded_time_left']:.2f}m | "
            f"{'WIN' if bool(r['guarded_correct']) else 'LOSS'} | "
            f"cleared to {r['guarded_reversal']}"
        )
    else:
        fate = "NO CALL WITHIN 45s"

    print(
        f"{r['contract']} | base "
        f"{'WIN' if r['baseline_correct'] else 'LOSS'} "
        f"@ {r['baseline_time_left']:.2f}m | {fate} | "
        f"{'SCALP COVERS' if r['scalp_signal'] else 'NO SCALP'}"
    )

guard = x[x["guarded_call"]].copy()
guard_correct = int(
    guard["guarded_correct"].fillna(False).astype(bool).sum()
)

# Union after guard: start from baseline audit and replace final availability.
guard_map = dict(zip(x["contract"],x["guarded_call"]))
guarded_union = []
for _,r in a.iterrows():
    contract = str(r["contract"])
    final_after = bool(guard_map.get(contract, False))
    scalp = bool(r["scalp_signal_b"])
    guarded_union.append(final_after or scalp)

guarded_union_n = int(sum(guarded_union))
base_union_n = int(a["union_actionable_b"].sum())
n = len(a)

supp = x[x["guard_status"]=="SUPPRESSED_MIXED_NO_CLEAR"].copy()
supp_scalp = int(supp["scalp_signal"].sum()) if len(supp) else 0

print("-"*92)
print("RECONCILED 45s RESULT")
print(
    f"FINAL: {guard_correct}/{len(guard)} = "
    f"{guard_correct/len(guard)*100:.1f}% | "
    f"{len(guard)}/{n} contracts = {len(guard)/n*100:.1f}% coverage"
)
print(
    f"SUPPRESSED MIXED: {len(supp)} | "
    f"scalp rescues {supp_scalp} | "
    f"true union losses {len(supp)-supp_scalp}"
)
print(
    f"UNION: {guarded_union_n}/{n} = "
    f"{guarded_union_n/n*100:.1f}% "
    f"(baseline {base_union_n}/{n} = {base_union_n/n*100:.1f}%)"
)

# Directly explain the two known baseline losses.
losses = x[~x["baseline_correct"]].copy()
print("-"*92)
print("BASELINE FINAL LOSSES UNDER 45s POLICY")
for _,r in losses.iterrows():
    print(
        f"{r['contract']} | base {r['final_side']} vs settled "
        f"{r['official_side']} | anchor state {r['anchor_reversal']} | "
        f"{r['guard_status']}"
        + (
            f" -> {'WIN' if bool(r['guarded_correct']) else 'LOSS'}"
            if r["guarded_call"] else ""
        )
    )

x.to_csv(OUT,index=False)

print("="*92)

if (
    len(guard) >= 20
    and guard_correct == len(guard)
    and guarded_union_n >= base_union_n-1
):
    print("RECONCILIATION RESULT: 45s POLICY IS A STRONG SHADOW CANDIDATE")
    print("NEXT: forward shadow BASE FINAL vs 45s GUARDED FINAL.")
elif (
    len(guard) >= 20
    and guard_correct/len(guard) >= .95
    and guarded_union_n >= base_union_n-2
):
    print("RECONCILIATION RESULT: PROMISING, BUT WITH MEASURABLE COVERAGE COST")
    print("Do not alter frozen FINAL; shadow-test only if worth the tradeoff.")
else:
    print("RECONCILIATION RESULT: 45s POLICY DOES NOT JUSTIFY A FINAL CHANGE")
    print("Keep frozen FINAL unchanged.")

print(f"Saved detail: {OUT}")
print("="*92)
