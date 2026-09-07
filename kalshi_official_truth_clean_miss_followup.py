from pathlib import Path
import pandas as pd
import numpy as np

DETAILS = Path("kalshi_official_truth_clean_miss_discriminator.csv")
OUT = Path("kalshi_official_truth_clean_miss_followup.csv")

print("=== KALSHI CLEAN-MISS FOLLOW-UP AUDIT ===")
print("Purpose: isolate the remaining CLEAN miss and test narrower combinations.")
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not DETAILS.exists():
    raise SystemExit(f"Missing {DETAILS}")

d = pd.read_csv(DETAILS, low_memory=False)

if "correct" not in d.columns:
    raise SystemExit("Missing correct column.")

d["correct"] = d["correct"].astype(str).str.lower().isin(["true","1","yes"])
miss = d[~d["correct"]].copy()
wins = d[d["correct"]].copy()

print(f"CLEAN calls loaded: {len(d)}")
print(f"Winners: {len(wins)}")
print(f"Misses: {len(miss)}")
print()

# Detect likely metric columns from the first discriminator output.
metric_cols = [c for c in d.columns if any(k in c for k in [
    "worst_distance_drop","worst_fair_drop","distance_gain","fair_gain",
    "ask_change","signed_distance"
])]

print("=== EACH CLEAN MISS PROFILE ===")
base_cols = [c for c in [
    "ticker","call_side","initial_fair_result","remaining_min_result",
    "anchor_signed_distance"
] if c in d.columns]
show_cols = base_cols + [c for c in metric_cols if c in d.columns]
print(miss[show_cols].to_string(index=False))
print()

# Find the miss least extreme versus winners on each metric.
rows = []
for col in metric_cols:
    s = pd.to_numeric(d[col], errors="coerce")
    sw = pd.to_numeric(wins[col], errors="coerce").dropna()
    sm = pd.to_numeric(miss[col], errors="coerce")
    if sw.empty:
        continue
    # percentile rank of each miss relative to winners
    for idx, val in sm.items():
        if pd.isna(val):
            continue
        pct = float((sw <= val).mean())
        rows.append({
            "ticker": miss.loc[idx, "ticker"] if "ticker" in miss.columns else str(idx),
            "metric": col,
            "value": float(val),
            "winner_min": float(sw.min()),
            "winner_median": float(sw.median()),
            "winner_max": float(sw.max()),
            "pct_rank_vs_winners": pct,
        })

ranks = pd.DataFrame(rows)

print("=== MOST DISTINCT MISS/METRIC COMBINATIONS ===")
if not ranks.empty:
    # distance/fair "drop" metrics: larger is generally worse; gain metrics: more negative is worse.
    # Rank by closeness to either tail.
    ranks["tail_extremeness"] = np.maximum(ranks["pct_rank_vs_winners"], 1-ranks["pct_rank_vs_winners"])
    print(ranks.sort_values("tail_extremeness", ascending=False).head(40).to_string(index=False))
print()

# Candidate pair scan across numeric metrics, using winner-derived percentile cutoffs only.
numeric_metrics = []
for c in metric_cols:
    x = pd.to_numeric(d[c], errors="coerce")
    if x.notna().sum() >= max(10, len(d)//2):
        numeric_metrics.append(c)

candidates = []
for c1 in numeric_metrics:
    x1 = pd.to_numeric(d[c1], errors="coerce")
    w1 = pd.to_numeric(wins[c1], errors="coerce").dropna()
    if w1.empty:
        continue
    cuts1 = sorted(set([
        float(w1.quantile(0.05)), float(w1.quantile(0.10)),
        float(w1.quantile(0.90)), float(w1.quantile(0.95))
    ]))
    for cut1 in cuts1:
        for op1 in ["<=", ">="]:
            m1 = x1 <= cut1 if op1 == "<=" else x1 >= cut1

            for c2 in numeric_metrics:
                if c2 <= c1:
                    continue
                x2 = pd.to_numeric(d[c2], errors="coerce")
                w2 = pd.to_numeric(wins[c2], errors="coerce").dropna()
                if w2.empty:
                    continue
                cuts2 = sorted(set([
                    float(w2.quantile(0.05)), float(w2.quantile(0.10)),
                    float(w2.quantile(0.90)), float(w2.quantile(0.95))
                ]))
                for cut2 in cuts2:
                    for op2 in ["<=", ">="]:
                        m2 = x2 <= cut2 if op2 == "<=" else x2 >= cut2
                        mask = m1 & m2
                        flagged = int(mask.sum())
                        misses_caught = int((mask & ~d["correct"]).sum())
                        good_flagged = int((mask & d["correct"]).sum())
                        if misses_caught == 0:
                            continue
                        kept = int((~mask).sum())
                        kept_correct = int(((~mask) & d["correct"]).sum())
                        kept_acc = kept_correct/kept if kept else np.nan
                        candidates.append({
                            "rule": f"{c1} {op1} {cut1:.6g} AND {c2} {op2} {cut2:.6g}",
                            "flagged": flagged,
                            "misses_caught": misses_caught,
                            "total_misses": int((~d["correct"]).sum()),
                            "good_flagged": good_flagged,
                            "kept": kept,
                            "kept_accuracy": kept_acc
                        })

cand = pd.DataFrame(candidates)
if not cand.empty:
    cand["capture"] = cand["misses_caught"] / cand["total_misses"]
    cand = cand.sort_values(
        ["misses_caught","good_flagged","flagged","kept_accuracy"],
        ascending=[False, True, True, False]
    ).reset_index(drop=True)

print("=== TOP NARROW COMBINATION CANDIDATES ===")
if cand.empty:
    print("No usable pair candidates found.")
else:
    print(cand.head(30).to_string(index=False))

# Also identify any miss still not caught by the prior best broad diagnostic:
# 420s fair_drop >= 0.150, if present.
best_col = None
for c in d.columns:
    if c.startswith("420s") and "fair_drop" in c:
        best_col = c
        break

if best_col:
    b = pd.to_numeric(d[best_col], errors="coerce") >= 0.150
    escaped = d[(~d["correct"]) & (~b)].copy()
    print()
    print("=== MISSES ESCAPING 420s FAIR_DROP >= 0.150 ===")
    if escaped.empty:
        print("None.")
    else:
        print(escaped[show_cols].to_string(index=False))

if not cand.empty:
    cand.to_csv(OUT, index=False)
else:
    pd.DataFrame().to_csv(OUT, index=False)

print()
print(f"Saved: {OUT}")
print("=== FOLLOW-UP AUDIT COMPLETE ===")
print("Research only. No rule installed.")
