import pandas as pd
from pathlib import Path

marker = pd.to_datetime(Path("kalshi_frozen_3m_guard_start_utc.txt").read_text().strip(), utc=True)
a = pd.read_csv("kalshi_official_truth_layer_a_rescore_details.csv", low_memory=False)
b = pd.read_csv("kalshi_official_truth_late_reversal_precursor_details.csv", low_memory=False)

a["timestamp_utc"] = pd.to_datetime(a["timestamp_utc"], errors="coerce", utc=True)
x = a[(a["timestamp_utc"] >= marker) & a["layer_a_state"].astype(str).str.upper().str.contains("CLEAN", na=False)].copy()

if x["correct"].dtype == bool:
    x["correct_bool"] = x["correct"]
else:
    x["correct_bool"] = x["correct"].astype(str).str.lower().map(
        {"true":True,"1":True,"yes":True,"false":False,"0":False,"no":False}
    )

cols = ["ticker","dist_5p0","dist_4p5","dist_4p0","dist_3p5","dist_3p0",
        "fair_5p0","fair_4p5","fair_4p0","fair_3p5","fair_3p0"]
b = b[[c for c in cols if c in b.columns]].copy()
for c in b.columns:
    if c != "ticker":
        b[c] = pd.to_numeric(b[c], errors="coerce")

x = x.merge(b, on="ticker", how="left")

print("=== CURRENT POST-FREEZE EARLY-WARNING DIAGNOSTIC ===")
print("Diagnostic only. No thresholds changed. No bot.py changes. No orders.")
print("Post-freeze CLEAN calls:", len(x))
print("Winners:", int(x["correct_bool"].sum()))
print("Misses:", int((~x["correct_bool"]).sum()))

print("\n=== FORWARD MISSES ===")
show = [c for c in ["timestamp_utc","ticker","call_side","official_side","initial_fair",
                    "initial_signed_distance","dist_5p0","dist_4p5","dist_4p0","dist_3p5","dist_3p0"] if c in x.columns]
print(x[~x["correct_bool"]][show].sort_values("timestamp_utc").to_string(index=False))

print("\n=== EARLIER CHECKPOINT SCAN ===")
rows = []
for cp in ["5p0","4p5","4p0","3p5","3p0"]:
    c = "dist_" + cp
    if c not in x.columns:
        continue
    for th in [25,50,75,100]:
        u = x[x[c].notna() & x["correct_bool"].notna()].copy()
        f = u[c] <= th
        mt = int((~u["correct_bool"]).sum())
        caught = int((f & ~u["correct_bool"]).sum())
        good = int((f & u["correct_bool"]).sum())
        kept = u[~f]
        acc = 100*kept["correct_bool"].mean() if len(kept) else None
        rows.append([cp.replace("p",".")+"m", th, len(u), int(f.sum()), caught, mt, good, len(kept), None if acc is None else round(acc,1)])
print(pd.DataFrame(rows, columns=["checkpoint","threshold","usable","flagged","caught","misses","good_flagged","kept","kept_acc_pct"]).to_string(index=False))
print("\nDo NOT install a new threshold from this diagnostic alone.")
