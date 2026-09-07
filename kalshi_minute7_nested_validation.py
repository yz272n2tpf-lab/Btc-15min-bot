from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI MINUTE-7 NESTED / ROLLING VALIDATION ===")
print("Purpose: test minute-7 failure filters on fresh chronological folds.")
print("Timing: ticker = ET contract CLOSE; contract start = close - 15 minutes.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

cal = pd.read_csv(CAL)
btc = pd.read_csv(BTC)

btc["Datetime"] = pd.to_datetime(btc["Datetime"], utc=True, errors="coerce")
btc = btc.dropna(subset=["Datetime"]).sort_values("Datetime").set_index("Datetime")

for c in ["Open","High","Low","Close","Volume"]:
    if c in btc.columns:
        btc[c] = pd.to_numeric(btc[c], errors="coerce")

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

def parse_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper()
    )
    if not m:
        return pd.NaT, pd.NaT

    yy, mon, dd, hh, mm = m.groups()
    wall = pd.Timestamp(
        year=2000+int(yy),
        month=MONTHS[mon],
        day=int(dd),
        hour=int(hh),
        minute=int(mm),
    )
    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")

    return close_utc - pd.Timedelta(minutes=15), close_utc

pairs = cal["ticker"].map(parse_times)
cal["start"] = [x[0] for x in pairs]
cal["close"] = [x[1] for x in pairs]
cal["target_brti"] = pd.to_numeric(cal["target_brti"], errors="coerce")
cal["final_brti"] = pd.to_numeric(cal["final_brti"], errors="coerce")
cal["y"] = cal["result"].astype(str).str.lower().map({"yes":1,"no":0})

cal = cal.dropna(
    subset=["start","target_brti","final_brti","y"]
).sort_values("start").reset_index(drop=True)

label_ok = (
    (cal["final_brti"] >= cal["target_brti"]).astype(int)
    == cal["y"].astype(int)
)

def px(ts):
    i = btc.index.searchsorted(ts, side="right") - 1
    if i < 0:
        return np.nan, pd.NaT
    ti = btc.index[i]
    if ts - ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT
    return float(btc.iloc[i]["Close"]), ti

def snapshot(r):
    elapsed = 7
    start = r["start"]
    cut = start + pd.Timedelta(minutes=elapsed)
    target = float(r["target_brti"])

    vals = [
        px(start),
        px(cut),
        px(cut-pd.Timedelta(minutes=1)),
        px(cut-pd.Timedelta(minutes=2)),
        px(cut-pd.Timedelta(minutes=3)),
        px(cut-pd.Timedelta(minutes=5)),
    ]
    if any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,pm1,pm2,pm3,pm5 = [v[0] for v in vals]
    used_times = [v[1] for v in vals]

    w = btc.loc[
        (btc.index > cut-pd.Timedelta(minutes=5))
        & (btc.index <= cut)
    ]

    if len(w) < 3:
        return None

    latest = max(used_times + [w.index.max()])
    if latest > cut:
        raise RuntimeError("FUTURE DATA DETECTED")

    closes = w["Close"].dropna()
    if len(closes) < 2:
        return None

    dist = p1 - target

    return {
        "ticker": r["ticker"],
        "start": start,
        "cut": cut,
        "latest": latest,
        "y": int(r["y"]),
        "current_side": int(dist >= 0),
        "dist_target": dist,
        "abs_dist_target": abs(dist),
        "dist_target_pct": dist/target,
        "dist_start": p1-p0,
        "dist_start_pct": (p1-p0)/p0,
        "move1": p1-pm1,
        "move2": p1-pm2,
        "move3": p1-pm3,
        "move5": p1-pm5,
        "range5": float(w["High"].max()-w["Low"].min()),
        "vol5": float(closes.pct_change().std(ddof=0)),
    }

features = [
    "current_side","dist_target","abs_dist_target","dist_target_pct",
    "dist_start","dist_start_pct","move1","move2","move3","move5",
    "range5","vol5"
]

rows = []
for _, r in cal.iterrows():
    s = snapshot(r)
    if s is not None:
        rows.append(s)

df = pd.DataFrame(rows).sort_values("start").reset_index(drop=True)

print(f"Minute-7 snapshots: {len(df)}")
print()

# Predeclared candidate rules only, based on prior descriptive audit.
RULE_NAMES = [
    "base_conf80",
    "mom2_conf80",
    "mom2_conf80_dist40",
    "mom2_conf80_dist60",
    "mom3_conf80_dist60",
    "dist100_conf80",
]

def attach_predictions(model, d):
    d = d.copy()
    d["pred"] = model.predict(d[features])
    d["conf"] = model.predict_proba(d[features]).max(axis=1)
    d["correct"] = d["pred"].to_numpy() == d["y"].to_numpy()
    d["pred_sign"] = np.where(d["pred"] == 1, 1, -1)

    for col in ["move1","move2","move3","move5"]:
        d[f"{col}_aligned"] = np.sign(d[col]) == d["pred_sign"]

    d["momentum_agreement_count"] = d[
        ["move1_aligned","move2_aligned","move3_aligned","move5_aligned"]
    ].sum(axis=1)
    return d

def masks(d):
    base = d["conf"] >= 0.80
    mom2 = d["momentum_agreement_count"] >= 2
    mom3 = d["momentum_agreement_count"] >= 3

    return {
        "base_conf80": base,
        "mom2_conf80": base & mom2,
        "mom2_conf80_dist40": base & mom2 & (d["abs_dist_target"] >= 40),
        "mom2_conf80_dist60": base & mom2 & (d["abs_dist_target"] >= 60),
        "mom3_conf80_dist60": base & mom3 & (d["abs_dist_target"] >= 60),
        "dist100_conf80": base & (d["abs_dist_target"] >= 100),
    }

def score(d, mask):
    q = d[mask]
    if len(q) == 0:
        return np.nan, 0, 0.0
    return float(q["correct"].mean()), len(q), len(q)/len(d)

# Nested chronological folds:
# each outer test fold is unseen;
# preceding data is split into inner-train / inner-select.
outer_folds = [
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 0.90),
    (0.90, 1.00),
]

outer_results = []

for fold_num, (test_a, test_b) in enumerate(outer_folds, start=1):
    test_start = int(len(df)*test_a)
    test_end = int(len(df)*test_b)

    pre = df.iloc[:test_start].copy()
    outer_test = df.iloc[test_start:test_end].copy()

    if len(pre) < 200 or len(outer_test) == 0:
        continue

    inner_split = int(len(pre)*0.80)
    inner_train = pre.iloc[:inner_split].copy()
    inner_select = pre.iloc[inner_split:].copy()

    if inner_train["start"].max() >= inner_select["start"].min():
        raise RuntimeError("INNER CHRONOLOGY FAILURE")
    if inner_select["start"].max() >= outer_test["start"].min():
        raise RuntimeError("OUTER CHRONOLOGY FAILURE")

    selector_model = RandomForestClassifier(
        n_estimators=500,
        max_depth=7,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    selector_model.fit(inner_train[features], inner_train["y"])

    inner_select = attach_predictions(selector_model, inner_select)
    select_masks = masks(inner_select)

    candidates = []
    for name in RULE_NAMES:
        acc, n, cov = score(inner_select, select_masks[name])
        if n >= 15:
            candidates.append((name, acc, n, cov))

    if not candidates:
        chosen = "base_conf80"
    else:
        # Pick highest inner accuracy, then higher coverage.
        candidates.sort(key=lambda x: (x[1], x[3]), reverse=True)
        chosen = candidates[0][0]

    # Refit only on data before outer test.
    final_model = RandomForestClassifier(
        n_estimators=500,
        max_depth=7,
        min_samples_leaf=8,
        class_weight="balanced",
        random_state=42,
        n_jobs=-1,
    )
    final_model.fit(pre[features], pre["y"])

    outer_test = attach_predictions(final_model, outer_test)
    outer_masks = masks(outer_test)

    raw_acc = float(outer_test["correct"].mean())
    gate_acc, gate_n, gate_cov = score(outer_test, outer_masks[chosen])

    outer_results.append({
        "fold": fold_num,
        "test_start_pct": int(test_a*100),
        "test_end_pct": int(test_b*100),
        "chosen_rule": chosen,
        "raw_acc": raw_acc,
        "gate_acc": gate_acc,
        "gate_n": gate_n,
        "gate_cov": gate_cov,
        "test_n": len(outer_test),
    })

    print(f"=== OUTER FOLD {fold_num}: {int(test_a*100)}->{int(test_b*100)}% ===")
    print(f"Inner train: {len(inner_train)} | Inner select: {len(inner_select)} | Outer test: {len(outer_test)}")
    print("Inner selection candidates:")
    for name, acc, n, cov in candidates:
        print(f"{name:24s} | n={n:3d} | coverage={cov:5.1%} | accuracy={acc:.3f}")
    print("CHOSEN RULE:", chosen)
    print(f"Outer raw accuracy: {raw_acc:.3f}")
    print(f"Outer gated accuracy: {gate_acc:.3f} | n={gate_n} | coverage={gate_cov:.1%}")
    print()

res = pd.DataFrame(outer_results)

print("=== ROLLING SUMMARY ===")
print(res.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print()

if len(res):
    total_gate_n = int(res["gate_n"].sum())
    weighted_gate_acc = np.nan
    if total_gate_n > 0:
        # Recompute weighted success count approximately from fold accuracy*n.
        weighted_gate_acc = float(
            (res["gate_acc"] * res["gate_n"]).sum() / total_gate_n
        )

    weighted_raw_acc = float(
        (res["raw_acc"] * res["test_n"]).sum() / res["test_n"].sum()
    )

    print("=== AGGREGATE ===")
    print(f"Weighted raw OOS accuracy: {weighted_raw_acc:.3f}")
    print(f"Nested-gated OOS accuracy: {weighted_gate_acc:.3f}")
    print(f"Nested-gated total calls: {total_gate_n}")
    print(f"Nested-gated overall coverage: {total_gate_n / res['test_n'].sum():.1%}")
    print()

print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Nested chronological separation: PASS")
print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
print("Do not integrate a rule unless nested/rolling OOS performance is stable.")
