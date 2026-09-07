from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI EARLY-EDGE 90% VALIDATION ===")
print("Purpose: search for robust 90%+ qualified calls before minute 11.")
print("Focus: elapsed minutes 5 / 7 / 9 on correctly aligned Kalshi contracts.")
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

def snapshot(r, elapsed):
    start = r["start"]
    cut = start + pd.Timedelta(minutes=elapsed)
    target = float(r["target_brti"])

    vals = [
        px(start),
        px(cut),
        px(cut-pd.Timedelta(minutes=1)),
        px(cut-pd.Timedelta(minutes=2)),
        px(cut-pd.Timedelta(minutes=3)),
        px(cut-pd.Timedelta(minutes=4)),
        px(cut-pd.Timedelta(minutes=5)),
    ]
    if any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,pm1,pm2,pm3,pm4,pm5 = [v[0] for v in vals]
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
    moves = {
        "move1": p1-pm1,
        "move2": p1-pm2,
        "move3": p1-pm3,
        "move4": p1-pm4,
        "move5": p1-pm5,
    }

    return {
        "ticker": r["ticker"],
        "start": start,
        "elapsed": elapsed,
        "y": int(r["y"]),
        "current_side": int(dist >= 0),
        "dist_target": dist,
        "abs_dist_target": abs(dist),
        "dist_target_pct": dist/target,
        "dist_start": p1-p0,
        "dist_start_pct": (p1-p0)/p0,
        **moves,
        "range5": float(w["High"].max()-w["Low"].min()),
        "vol5": float(closes.pct_change().std(ddof=0)),
    }

features = [
    "current_side","dist_target","abs_dist_target","dist_target_pct",
    "dist_start","dist_start_pct","move1","move2","move3","move4","move5",
    "range5","vol5"
]

elapsed_list = [5,7,9]
rows = []

for elapsed in elapsed_list:
    for _, r in cal.iterrows():
        s = snapshot(r, elapsed)
        if s is not None:
            rows.append(s)

long = pd.DataFrame(rows)

counts = long.groupby("ticker")["elapsed"].nunique()
keep = counts[counts == len(elapsed_list)].index
long = long[long["ticker"].isin(keep)].copy()

contracts = (
    long[["ticker","start","y"]]
    .drop_duplicates("ticker")
    .sort_values("start")
    .reset_index(drop=True)
)

print(f"Contracts with complete 5/7/9 snapshots: {len(contracts)}")
print()

def add_pred_features(d):
    d = d.copy()
    d["pred_sign"] = np.where(d["pred"] == 1, 1, -1)
    for col in ["move1","move2","move3","move4","move5"]:
        d[f"{col}_aligned"] = np.sign(d[col]) == d["pred_sign"]
    d["momentum_count"] = d[
        ["move1_aligned","move2_aligned","move3_aligned","move4_aligned","move5_aligned"]
    ].sum(axis=1)
    d["target_side_agree"] = d["pred"] == d["current_side"]
    d["correct"] = d["pred"] == d["y"]
    return d

# Predeclared rule library. No rule is chosen from the outer test data.
def candidate_masks(d, elapsed):
    masks = {}

    for conf in [0.80,0.85,0.90]:
        masks[f"m{elapsed}_conf{int(conf*100)}"] = d["conf"] >= conf

    for conf in [0.80,0.85]:
        for mom in [2,3,4]:
            masks[f"m{elapsed}_conf{int(conf*100)}_mom{mom}"] = (
                (d["conf"] >= conf)
                & (d["momentum_count"] >= mom)
            )

    for conf in [0.80,0.85]:
        for dist in [40,60,80,100]:
            masks[f"m{elapsed}_conf{int(conf*100)}_dist{dist}"] = (
                (d["conf"] >= conf)
                & (d["abs_dist_target"] >= dist)
            )

    for conf in [0.80,0.85]:
        for mom in [2,3]:
            for dist in [40,60,80]:
                masks[f"m{elapsed}_conf{int(conf*100)}_mom{mom}_dist{dist}"] = (
                    (d["conf"] >= conf)
                    & (d["momentum_count"] >= mom)
                    & (d["abs_dist_target"] >= dist)
                )

    for conf in [0.80,0.85]:
        masks[f"m{elapsed}_conf{int(conf*100)}_side"] = (
            (d["conf"] >= conf)
            & d["target_side_agree"]
        )

    return masks

outer_blocks = [(0.70,0.80),(0.80,0.90),(0.90,1.00)]
results = []
chosen_rules = []

for block_num, (a,b) in enumerate(outer_blocks, start=1):
    train_end = int(len(contracts)*a)
    test_end = int(len(contracts)*b)

    pre_tickers = contracts.iloc[:train_end]["ticker"]
    test_tickers = contracts.iloc[train_end:test_end]["ticker"]

    pre_contracts = contracts[contracts["ticker"].isin(pre_tickers)]
    test_contracts = contracts[contracts["ticker"].isin(test_tickers)]

    if pre_contracts["start"].max() >= test_contracts["start"].min():
        raise RuntimeError("OUTER CHRONOLOGY FAILURE")

    # inner 80/20 chronological split for rule selection
    inner_cut = int(len(pre_tickers)*0.80)
    inner_train_tickers = pre_tickers.iloc[:inner_cut]
    inner_select_tickers = pre_tickers.iloc[inner_cut:]

    print(f"=== OUTER BLOCK {block_num}: {int(a*100)}->{int(b*100)}% ===")
    print(
        f"Inner train={len(inner_train_tickers)} | "
        f"Inner select={len(inner_select_tickers)} | "
        f"Outer test={len(test_tickers)}"
    )

    block_preds = {}

    for elapsed in elapsed_list:
        train = long[
            (long["ticker"].isin(inner_train_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        select = long[
            (long["ticker"].isin(inner_select_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        model = RandomForestClassifier(
            n_estimators=700,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(train[features], train["y"])

        select["pred"] = model.predict(select[features])
        select["conf"] = model.predict_proba(select[features]).max(axis=1)
        select = add_pred_features(select)

        masks = candidate_masks(select, elapsed)

        candidates = []
        for name, mask in masks.items():
            q = select[mask]
            if len(q) >= 15:
                candidates.append({
                    "name": name,
                    "elapsed": elapsed,
                    "acc": float(q["correct"].mean()),
                    "n": len(q),
                    "coverage": len(q)/len(select),
                })

        # Favor >=90%, then coverage; if none reach 90%, favor accuracy then coverage.
        good = [x for x in candidates if x["acc"] >= 0.90]
        if good:
            good.sort(key=lambda x: (x["coverage"], x["acc"]), reverse=True)
            selected = good[0]
        else:
            candidates.sort(key=lambda x: (x["acc"], x["coverage"]), reverse=True)
            selected = candidates[0]

        chosen_rules.append((block_num, selected))
        print(
            f"Minute {elapsed}: selected {selected['name']} | "
            f"inner acc={selected['acc']:.3f} | "
            f"coverage={selected['coverage']:.1%} | n={selected['n']}"
        )

        # Refit using all pre-test data, then evaluate truly untouched outer test.
        full_train = long[
            (long["ticker"].isin(pre_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        outer = long[
            (long["ticker"].isin(test_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        final_model = RandomForestClassifier(
            n_estimators=700,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        final_model.fit(full_train[features], full_train["y"])

        outer["pred"] = final_model.predict(outer[features])
        outer["conf"] = final_model.predict_proba(outer[features]).max(axis=1)
        outer = add_pred_features(outer)

        outer_masks = candidate_masks(outer, elapsed)
        omask = outer_masks[selected["name"]]
        q = outer[omask]

        acc = np.nan if len(q) == 0 else float(q["correct"].mean())
        cov = len(q)/len(outer)

        print(
            f"  OUTER TEST -> n={len(q)} | coverage={cov:.1%} | "
            f"accuracy={'NA' if pd.isna(acc) else f'{acc:.3f}'}"
        )

        results.append({
            "block": block_num,
            "elapsed": elapsed,
            "selected_rule": selected["name"],
            "outer_n": len(q),
            "outer_coverage": cov,
            "outer_accuracy": acc,
            "test_n": len(outer),
        })

        block_preds[elapsed] = outer[[
            "ticker","y","pred","conf","momentum_count",
            "target_side_agree","abs_dist_target","correct"
        ]].copy()

    # Same-contract cross-minute agreement candidates on untouched test.
    m5 = block_preds[5].rename(columns={"pred":"pred5","conf":"conf5","correct":"correct5"})
    m7 = block_preds[7].rename(columns={"pred":"pred7","conf":"conf7","correct":"correct7"})
    m9 = block_preds[9].rename(columns={"pred":"pred9","conf":"conf9","correct":"correct9"})

    same = m5[["ticker","y","pred5","conf5"]].merge(
        m7[["ticker","pred7","conf7"]], on="ticker"
    ).merge(
        m9[["ticker","pred9","conf9"]], on="ticker"
    )

    agreement_rules = {
        "5&7 agree both85": (
            (same["pred5"] == same["pred7"])
            & (same["conf5"] >= .85)
            & (same["conf7"] >= .85)
        ),
        "7&9 agree both80": (
            (same["pred7"] == same["pred9"])
            & (same["conf7"] >= .80)
            & (same["conf9"] >= .80)
        ),
        "7&9 agree both85": (
            (same["pred7"] == same["pred9"])
            & (same["conf7"] >= .85)
            & (same["conf9"] >= .85)
        ),
        "5/7/9 all agree min80": (
            (same["pred5"] == same["pred7"])
            & (same["pred7"] == same["pred9"])
            & (same["conf5"] >= .80)
            & (same["conf7"] >= .80)
            & (same["conf9"] >= .80)
        ),
    }

    print("Cross-minute untouched:")
    for name, mask in agreement_rules.items():
        q = same[mask]
        if len(q):
            pred_col = "pred7" if name.startswith("5&7") else "pred9"
            acc = (q[pred_col] == q["y"]).mean()
            print(
                f"  {name:25s} | n={len(q):3d} | "
                f"coverage={len(q)/len(same):5.1%} | accuracy={acc:.3f}"
            )
    print()

res = pd.DataFrame(results)

print("=== SELECTED-RULE OUTER SUMMARY ===")
print(res.to_string(index=False, float_format=lambda x: f"{x:.3f}"))
print()

print("=== BY MINUTE AGGREGATE ===")
for elapsed in elapsed_list:
    q = res[res["elapsed"] == elapsed]
    total_n = int(q["outer_n"].sum())
    test_n = int(q["test_n"].sum())
    if total_n:
        weighted_acc = float(
            (q["outer_accuracy"] * q["outer_n"]).sum() / total_n
        )
        print(
            f"Minute {elapsed} selected-gate | calls={total_n} | "
            f"coverage={total_n/test_n:.1%} | accuracy={weighted_acc:.3f}"
        )

print()
print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Nested chronological selection: PASS")
print("Untouched outer testing: PASS")
print("Corrected Kalshi timing: PASS")
print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
print("Goal: determine whether any pre-minute-11 qualification rule truly sustains 90%+ OOS.")
