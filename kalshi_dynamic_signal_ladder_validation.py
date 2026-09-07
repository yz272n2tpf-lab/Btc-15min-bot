from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI DYNAMIC SIGNAL-LADDER VALIDATION ===")
print("Purpose: validate EARLY -> STRONG -> FINAL LOCK behavior on every 15m contract.")
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
        "elapsed": elapsed,
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

elapsed_list = [5,7,9,11]
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

print(f"Contracts with complete 5/7/9/11 snapshots: {len(contracts)}")
print()

# Final 30% is untouched chronological validation.
blocks = [(0.70,0.80),(0.80,0.90),(0.90,1.00)]
all_blocks = []

for block_num, (a,b) in enumerate(blocks, start=1):
    train_end = int(len(contracts)*a)
    test_end = int(len(contracts)*b)

    train_tickers = contracts.iloc[:train_end]["ticker"]
    test_tickers = contracts.iloc[train_end:test_end]["ticker"]

    train_contracts = contracts[contracts["ticker"].isin(train_tickers)]
    test_contracts = contracts[contracts["ticker"].isin(test_tickers)]

    if train_contracts["start"].max() >= test_contracts["start"].min():
        raise RuntimeError("CHRONOLOGY FAILURE")

    pred_frames = {}

    for elapsed in elapsed_list:
        train = long[
            (long["ticker"].isin(train_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        test = long[
            (long["ticker"].isin(test_tickers))
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

        test["pred"] = model.predict(test[features])
        test["conf"] = model.predict_proba(test[features]).max(axis=1)

        pred_frames[elapsed] = test[
            ["ticker","y","pred","conf","current_side","abs_dist_target"]
        ].copy()

    merged = pred_frames[5].rename(columns={
        "pred":"pred_5",
        "conf":"conf_5",
        "current_side":"side_5",
        "abs_dist_target":"dist_5",
    })

    for elapsed in [7,9,11]:
        tmp = pred_frames[elapsed].rename(columns={
            "pred":f"pred_{elapsed}",
            "conf":f"conf_{elapsed}",
            "current_side":f"side_{elapsed}",
            "abs_dist_target":f"dist_{elapsed}",
        })
        merged = merged.merge(
            tmp[[
                "ticker",f"pred_{elapsed}",f"conf_{elapsed}",
                f"side_{elapsed}",f"dist_{elapsed}"
            ]],
            on="ticker",
            how="inner"
        )

    merged["block"] = block_num

    # Every contract always has a raw directional call.
    merged["raw_call"] = merged["pred_5"]

    # Signal ladder:
    # EARLY = minute 5 model direction, always shown.
    # STRONG = minute 7+ if confidence and direction support improve.
    # HIGH-CONFIDENCE = minute 9 if 7&9 agree and both >=85%.
    # FINAL LOCK = minute 11 validated conditions.
    merged["early_call"] = merged["pred_5"]

    merged["strong_7"] = (
        (merged["conf_7"] >= 0.80)
        & (merged["pred_7"] == merged["side_7"])
    )

    merged["strong_9"] = (
        (merged["conf_9"] >= 0.80)
        & (merged["pred_9"] == merged["side_9"])
    )

    merged["high_conf_9"] = (
        (merged["pred_7"] == merged["pred_9"])
        & (merged["conf_7"] >= 0.85)
        & (merged["conf_9"] >= 0.85)
    )

    merged["final_lock_11"] = (
        (
            (merged["pred_9"] == merged["pred_11"])
            & (merged["conf_9"] >= 0.85)
            & (merged["conf_11"] >= 0.85)
        )
        |
        (merged["conf_11"] >= 0.90)
    )

    # Ladder status at the latest checkpoint.
    merged["final_status"] = "EARLY LEAN"
    merged.loc[merged["strong_7"], "final_status"] = "STRONG"
    merged.loc[merged["strong_9"], "final_status"] = "STRONG"
    merged.loc[merged["high_conf_9"], "final_status"] = "HIGH CONFIDENCE"
    merged.loc[merged["final_lock_11"], "final_status"] = "FINAL LOCK"

    # Direction associated with highest attained stage.
    merged["ladder_pred"] = merged["pred_5"]
    merged.loc[merged["strong_7"], "ladder_pred"] = merged["pred_7"]
    merged.loc[merged["strong_9"], "ladder_pred"] = merged["pred_9"]
    merged.loc[merged["high_conf_9"], "ladder_pred"] = merged["pred_9"]
    merged.loc[merged["final_lock_11"], "ladder_pred"] = merged["pred_11"]

    all_blocks.append(merged)

    print(f"=== UNTOUCHED BLOCK {block_num}: {int(a*100)}->{int(b*100)}% ===")
    print(f"Train={len(train_tickers)} | Test={len(test_tickers)}")

    for label, mask, pred_col in [
        ("EARLY minute-5 raw call", pd.Series(True, index=merged.index), "pred_5"),
        ("STRONG by minute 7", merged["strong_7"], "pred_7"),
        ("STRONG by minute 9", merged["strong_9"], "pred_9"),
        ("HIGH CONFIDENCE at minute 9", merged["high_conf_9"], "pred_9"),
        ("FINAL LOCK at minute 11", merged["final_lock_11"], "pred_11"),
    ]:
        q = merged[mask]
        if len(q):
            acc = (q[pred_col] == q["y"]).mean()
            print(
                f"{label:30s} | n={len(q):3d} | "
                f"coverage={len(q)/len(merged):5.1%} | accuracy={acc:.3f}"
            )

    print()

agg = pd.concat(all_blocks, ignore_index=True)

print("=== AGGREGATE LADDER RESULTS ===")

for label, mask, pred_col in [
    ("EARLY minute-5 raw call", pd.Series(True, index=agg.index), "pred_5"),
    ("STRONG by minute 7", agg["strong_7"], "pred_7"),
    ("STRONG by minute 9", agg["strong_9"], "pred_9"),
    ("HIGH CONFIDENCE at minute 9", agg["high_conf_9"], "pred_9"),
    ("FINAL LOCK at minute 11", agg["final_lock_11"], "pred_11"),
]:
    q = agg[mask]
    if len(q):
        acc = (q[pred_col] == q["y"]).mean()
        print(
            f"{label:30s} | n={len(q):3d} | "
            f"coverage={len(q)/len(agg):5.1%} | accuracy={acc:.3f}"
        )

print()
print("=== FINAL STATUS DISTRIBUTION ===")

for status in ["EARLY LEAN","STRONG","HIGH CONFIDENCE","FINAL LOCK"]:
    q = agg[agg["final_status"] == status]
    if len(q):
        acc = (q["ladder_pred"] == q["y"]).mean()
        print(
            f"{status:18s} | n={len(q):3d} | "
            f"share={len(q)/len(agg):5.1%} | accuracy={acc:.3f}"
        )

print()
print("=== EVERY-CONTRACT REQUIREMENT ===")
print(f"Untouched contracts evaluated: {len(agg)}")
print(f"Contracts with raw UP/DOWN call: {agg['raw_call'].notna().sum()}")
print(
    "Every untouched contract has a raw call:",
    "YES" if agg["raw_call"].notna().all() else "NO"
)

print()
print("=== DIRECTION CHANGE / RECOVERY ===")

for a,b in [(5,7),(7,9),(9,11),(5,11)]:
    changed = agg[f"pred_{a}"] != agg[f"pred_{b}"]
    print(
        f"Direction changed {a}->{b}: "
        f"{changed.mean():.1%} ({changed.sum()}/{len(agg)})"
    )

wrong5 = agg[agg["pred_5"] != agg["y"]]
if len(wrong5):
    recovered11 = wrong5["pred_11"] == wrong5["y"]
    print(
        f"Wrong at minute 5 but correct at minute 11: "
        f"{recovered11.mean():.1%} ({recovered11.sum()}/{len(wrong5)})"
    )

print()
print("=== FINAL-LOCK STABILITY BY BLOCK ===")

for block in sorted(agg["block"].unique()):
    z = agg[agg["block"] == block]
    q = z[z["final_lock_11"]]
    if len(q):
        acc = (q["pred_11"] == q["y"]).mean()
        print(
            f"Block {block}: n={len(q):3d} | "
            f"coverage={len(q)/len(z):5.1%} | accuracy={acc:.3f}"
        )

print()
print("=== HARD CHECKS ===")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological holdouts: PASS")
print("Every-contract raw direction: PASS" if agg["raw_call"].notna().all() else "FAIL")

print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
print("Use this result to decide the exact live EARLY / STRONG / HIGH-CONFIDENCE / FINAL-LOCK ladder.")
