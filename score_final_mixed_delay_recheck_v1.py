
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")
AUDIT = Path("union_coverage_gap_audit_v1_contracts.csv")

OUT = Path("final_mixed_delay_recheck_v1_results.csv")
OUT_CALLS = Path("final_mixed_delay_recheck_v1_calls.csv")

DELAYS = [0, 15, 30, 45, 60]

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def num(df,c):
    if c not in df.columns:
        df[c] = np.nan
    df[c] = pd.to_numeric(df[c],errors="coerce")

def fmt_pct(x):
    return "NA" if pd.isna(x) else f"{x:.1f}%"

print("="*86)
print("FINAL MIXED DELAY / RECHECK AUDIT V1")
print("="*86)

if not UNIFIED.exists():
    raise SystemExit("ERROR: unified log missing")
if not AUDIT.exists():
    raise SystemExit("ERROR: union coverage audit missing")

u = pd.read_csv(UNIFIED)
a = pd.read_csv(AUDIT)

u["timestamp_utc"] = pd.to_datetime(
    u["timestamp_utc"],errors="coerce",utc=True
)

for c in [
    "minutes_left","seconds_left","preferred_fair","abs_btc_gap",
    "dist_over_range5","brti_age_seconds","brti_gap_to_target",
    "side_ask","side_bid"
]:
    num(u,c)

u["brti_ready_b"] = u.get(
    "brti_ready",pd.Series(False,index=u.index)
).map(truthy)

a["final_call_b"] = a["final_call"].map(truthy)
a["final_correct_b"] = a["final_correct"].map(truthy)

final_contracts = a.loc[a["final_call_b"],"contract"].astype(str).tolist()
print(f"FINAL CONTRACTS IN SAME SAMPLE: {len(final_contracts)}")

# Reconstruct exact frozen FINAL gate on side-aligned rows.
f = u[
    u["contract"].astype(str).isin(final_contracts)
    & u["preferred_fair_side"].isin(["UP","DOWN"])
    & (u["side"] == u["preferred_fair_side"])
].copy()

f["required_gap"] = np.where(
    f["minutes_left"] > 6.0,
    75.0,
    50.0
)

f["final_gate"] = (
    f["minutes_left"].between(0.0,8.0,inclusive="both")
    & (f["preferred_fair"] >= 0.90)
    & (f["abs_btc_gap"] >= f["required_gap"])
    & (f["dist_over_range5"] >= 1.0)
    & (f["preferred_fair_side"] == f["current_target_side"])
    & f["brti_ready_b"]
    & (f["brti_age_seconds"] <= 5.0)
    & (f["brti_gap_to_target"].abs() > 11.0)
    & (f["brti_side"] == f["preferred_fair_side"])
)

# Attach official side from prior same-contract audit.
official = dict(zip(
    a["contract"].astype(str),
    a["official_side"].astype(str)
))

# First exact gate-qualifying row per contract.
first_rows = (
    f[f["final_gate"]]
    .sort_values(["contract","timestamp_utc"])
    .groupby("contract",as_index=False)
    .head(1)
    .copy()
)

if first_rows.empty:
    raise SystemExit("ERROR: no reconstructed FINAL calls found")

first_rows["official_side"] = first_rows["contract"].astype(str).map(official)
first_rows["base_correct"] = (
    first_rows["preferred_fair_side"] == first_rows["official_side"]
)
first_rows["base_mixed"] = (
    first_rows["reversal_state"].fillna("").astype(str).str.upper() == "MIXED"
)

print(
    f"RECONSTRUCTED BASE FINAL: "
    f"{int(first_rows['base_correct'].sum())}/{len(first_rows)} = "
    f"{first_rows['base_correct'].mean()*100:.1f}%"
)
print(
    f"BASE MIXED CALLS: {int(first_rows['base_mixed'].sum())}"
)
print("-"*86)

results = []
call_rows = []

for delay in DELAYS:
    kept = []
    removed = 0
    delayed_count = 0

    for _, base in first_rows.iterrows():
        contract = str(base["contract"])
        base_ts = base["timestamp_utc"]
        base_side = str(base["preferred_fair_side"])
        base_mixed = bool(base["base_mixed"])

        # Non-MIXED calls pass through untouched for delay > 0.
        if delay > 0 and not base_mixed:
            chosen = base.copy()
            chosen["delay_seconds"] = 0
            chosen["recheck_reason"] = "NON_MIXED_KEEP"
            kept.append(chosen)
            continue

        if delay == 0:
            chosen = base.copy()
            chosen["delay_seconds"] = 0
            chosen["recheck_reason"] = (
                "BASE_MIXED" if base_mixed else "BASE_NON_MIXED"
            )
            kept.append(chosen)
            continue

        # For MIXED base calls: wait at least N seconds, then take the
        # first row where the original frozen FINAL gate STILL holds and
        # reversal state is no longer MIXED.
        cf = f[
            (f["contract"].astype(str) == contract)
            & (f["preferred_fair_side"] == base_side)
            & (f["timestamp_utc"] >= base_ts + pd.Timedelta(seconds=delay))
            & f["final_gate"]
            & (
                f["reversal_state"].fillna("").astype(str).str.upper()
                != "MIXED"
            )
        ].copy()

        if cf.empty:
            removed += 1
            continue

        chosen = cf.sort_values("timestamp_utc").iloc[0].copy()
        chosen["delay_seconds"] = (
            chosen["timestamp_utc"] - base_ts
        ).total_seconds()
        chosen["recheck_reason"] = "MIXED_DELAY_CLEAR"
        chosen["official_side"] = official.get(contract)
        chosen["base_correct"] = (
            chosen["preferred_fair_side"] == chosen["official_side"]
        )
        kept.append(chosen)
        delayed_count += 1

    if kept:
        k = pd.DataFrame(kept)
        k["correct"] = (
            k["preferred_fair_side"] == k["official_side"]
        )
        accuracy = 100*k["correct"].mean()
        avg_time = k["minutes_left"].mean()
        median_time = k["minutes_left"].median()
        avg_delay = k["delay_seconds"].mean()
        mixed_survived = int(
            (k["recheck_reason"]=="MIXED_DELAY_CLEAR").sum()
        )
        calls = len(k)
        wrong = int((~k["correct"]).sum())
    else:
        accuracy = np.nan
        avg_time = np.nan
        median_time = np.nan
        avg_delay = np.nan
        mixed_survived = 0
        calls = 0
        wrong = 0

    coverage_retained = 100*calls/len(first_rows)

    results.append({
        "delay_seconds":delay,
        "calls":calls,
        "accuracy":accuracy,
        "wrong_calls":wrong,
        "coverage_retained_pct":coverage_retained,
        "avg_time_left":avg_time,
        "median_time_left":median_time,
        "avg_actual_delay_seconds":avg_delay,
        "mixed_calls_survived":mixed_survived,
        "mixed_calls_removed":removed,
    })

    if kept:
        kk = pd.DataFrame(kept).copy()
        kk["scenario_delay_seconds"] = delay
        call_rows.append(kk)

    print(
        f"DELAY {delay:>2}s | "
        f"{calls} calls | "
        f"accuracy {fmt_pct(accuracy)} | "
        f"retained {coverage_retained:.1f}% | "
        f"avg {avg_time:.2f}m left | "
        f"MIXED survived {mixed_survived} | removed {removed}"
    )

res = pd.DataFrame(results)

# Identify best accuracy scenario with at least 80% of calls retained.
eligible = res[res["coverage_retained_pct"] >= 80.0].copy()

print("-"*86)

if len(eligible):
    best = eligible.sort_values(
        ["accuracy","coverage_retained_pct","avg_time_left"],
        ascending=[False,False,False]
    ).iloc[0]

    print("BEST >=80% COVERAGE-RETENTION SCENARIO:")
    print(
        f"  delay {int(best['delay_seconds'])}s | "
        f"{best['accuracy']:.1f}% | "
        f"{int(best['calls'])} calls | "
        f"{best['coverage_retained_pct']:.1f}% retained | "
        f"avg {best['avg_time_left']:.2f}m left"
    )
else:
    best = None
    print("NO DELAY SCENARIO RETAINED >=80% OF FINAL CALLS.")

# Show what happened specifically to the original MIXED calls.
print("-"*86)
print("ORIGINAL MIXED CALL FATES:")

mixed_base = first_rows[first_rows["base_mixed"]].copy()

for _, b in mixed_base.iterrows():
    contract = str(b["contract"])
    status = []
    for delay in [15,30,45,60]:
        cf = f[
            (f["contract"].astype(str)==contract)
            & (f["preferred_fair_side"]==b["preferred_fair_side"])
            & (f["timestamp_utc"]>=b["timestamp_utc"]+pd.Timedelta(seconds=delay))
            & f["final_gate"]
            & (
                f["reversal_state"].fillna("").astype(str).str.upper()
                !="MIXED"
            )
        ].sort_values("timestamp_utc")

        if cf.empty:
            status.append(f"{delay}s:NO CALL")
        else:
            rr = cf.iloc[0]
            correct = (
                rr["preferred_fair_side"] == official.get(contract)
            )
            status.append(
                f"{delay}s:{'WIN' if correct else 'LOSS'}@"
                f"{rr['minutes_left']:.2f}m"
            )

    print(
        f"{contract} | base "
        f"{'WIN' if b['base_correct'] else 'LOSS'} | "
        + " | ".join(status)
    )

res.to_csv(OUT,index=False)

if call_rows:
    pd.concat(call_rows,ignore_index=True).to_csv(
        OUT_CALLS,index=False
    )

print("="*86)

if best is not None:
    base = res[res["delay_seconds"]==0].iloc[0]
    acc_gain = best["accuracy"] - base["accuracy"]
    cov_loss = 100.0 - best["coverage_retained_pct"]

    if (
        best["delay_seconds"] > 0
        and best["accuracy"] >= 95.0
        and best["coverage_retained_pct"] >= 85.0
        and best["avg_time_left"] >= 4.0
    ):
        print("SCREEN RESULT: PROMISING MIXED DELAY/RECHECK GUARDRAIL")
        print(
            f"Accuracy gain {acc_gain:+.1f} points with "
            f"{cov_loss:.1f}% of FINAL calls removed."
        )
        print("NEXT: validate on broader historical/fresh FINAL data before any install.")
    else:
        print("SCREEN RESULT: NO MIXED DELAY RULE IS STRONG ENOUGH YET")
        print("Keep frozen FINAL unchanged.")
        print(
            f"Best scenario changed accuracy by {acc_gain:+.1f} points "
            f"and removed {cov_loss:.1f}% of FINAL calls."
        )
else:
    print("SCREEN RESULT: NO VIABLE MIXED DELAY RULE.")
    print("Keep frozen FINAL unchanged.")

print(f"Saved summary: {OUT}")
print(f"Saved calls: {OUT_CALLS}")
print("="*86)
