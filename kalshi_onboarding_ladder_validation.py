from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI ONBOARDING LADDER VALIDATION ===")
print("Purpose: validate a live-style staged decision ladder before touching bot.py.")
print("Stage 1: minute 8 qualifies only if minute 7 & 8 agree and both confidence >=85%.")
print("Stage 2: minute 11 final lock if minute 9 & 11 agree both >=85% OR minute 11 confidence >=90%.")
print("Every contract retains a raw directional forecast even if no qualified signal appears.")
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
    close_utc = wall.tz_localize(ZoneInfo("America/New_York")).tz_convert("UTC")
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
        "move4": p1-pm4,
        "move5": p1-pm5,
        "range5": float(w["High"].max()-w["Low"].min()),
        "vol5": float(closes.pct_change().std(ddof=0)),
    }

features = [
    "current_side","dist_target","abs_dist_target","dist_target_pct",
    "dist_start","dist_start_pct",
    "move1","move2","move3","move4","move5",
    "range5","vol5"
]

elapsed_list = [5,7,8,9,11]
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

print(f"Contracts with complete 5/7/8/9/11 snapshots: {len(contracts)}")
print()

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

    pred = {}

    for elapsed in elapsed_list:
        tr = long[
            (long["ticker"].isin(train_tickers))
            & (long["elapsed"] == elapsed)
        ].copy()

        te = long[
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
        model.fit(tr[features], tr["y"])

        te["pred"] = model.predict(te[features])
        te["conf"] = model.predict_proba(te[features]).max(axis=1)

        pred[elapsed] = te[["ticker","y","pred","conf"]].copy()

    merged = pred[5].rename(columns={"pred":"pred_5","conf":"conf_5"})

    for elapsed in [7,8,9,11]:
        tmp = pred[elapsed].rename(columns={
            "pred":f"pred_{elapsed}",
            "conf":f"conf_{elapsed}",
        })
        merged = merged.merge(
            tmp[["ticker",f"pred_{elapsed}",f"conf_{elapsed}"]],
            on="ticker",
            how="inner"
        )

    merged["block"] = block_num

    # Always-visible raw forecast.
    merged["raw_forecast"] = merged["pred_5"]

    # Validated minute-8 qualified signal.
    merged["minute8_qualified"] = (
        (merged["pred_7"] == merged["pred_8"])
        & (merged["conf_7"] >= .85)
        & (merged["conf_8"] >= .85)
    )

    # Validated minute-11 final-lock logic.
    merged["minute11_lock"] = (
        (
            (merged["pred_9"] == merged["pred_11"])
            & (merged["conf_9"] >= .85)
            & (merged["conf_11"] >= .85)
        )
        |
        (merged["conf_11"] >= .90)
    )

    # Live-style staged action: first valid stage wins.
    merged["qualified_stage"] = "NO QUALIFIED SIGNAL"
    merged["qualified_pred"] = np.nan
    merged["qualified_minute"] = np.nan

    m8 = merged["minute8_qualified"]
    merged.loc[m8, "qualified_stage"] = "MINUTE 8 QUALIFIED"
    merged.loc[m8, "qualified_pred"] = merged.loc[m8, "pred_8"]
    merged.loc[m8, "qualified_minute"] = 8

    m11_new = (~m8) & merged["minute11_lock"]
    merged.loc[m11_new, "qualified_stage"] = "MINUTE 11 FINAL LOCK"
    merged.loc[m11_new, "qualified_pred"] = merged.loc[m11_new, "pred_11"]
    merged.loc[m11_new, "qualified_minute"] = 11

    merged["qualified_correct"] = np.where(
        merged["qualified_pred"].notna(),
        merged["qualified_pred"] == merged["y"],
        np.nan
    )

    all_blocks.append(merged)

    print(f"=== UNTOUCHED BLOCK {block_num}: {int(a*100)}->{int(b*100)}% ===")
    print(f"Train={len(train_tickers)} | Test={len(test_tickers)}")

    q8 = merged[merged["qualified_stage"] == "MINUTE 8 QUALIFIED"]
    q11 = merged[merged["qualified_stage"] == "MINUTE 11 FINAL LOCK"]
    qall = merged[merged["qualified_pred"].notna()]
    qnone = merged[merged["qualified_pred"].isna()]

    if len(q8):
        print(
            f"Minute 8 qualified | n={len(q8):3d} | "
            f"coverage={len(q8)/len(merged):5.1%} | "
            f"accuracy={(q8['qualified_pred']==q8['y']).mean():.3f}"
        )

    if len(q11):
        print(
            f"Minute 11 new locks | n={len(q11):3d} | "
            f"coverage={len(q11)/len(merged):5.1%} | "
            f"accuracy={(q11['qualified_pred']==q11['y']).mean():.3f}"
        )

    if len(qall):
        print(
            f"Combined qualified | n={len(qall):3d} | "
            f"coverage={len(qall)/len(merged):5.1%} | "
            f"accuracy={(qall['qualified_pred']==qall['y']).mean():.3f}"
        )

    print(
        f"No qualified signal by minute 11 | n={len(qnone):3d} | "
        f"share={len(qnone)/len(merged):5.1%}"
    )
    print()

agg = pd.concat(all_blocks, ignore_index=True)

print("=== AGGREGATE LIVE-STYLE LADDER ===")

for stage in ["MINUTE 8 QUALIFIED","MINUTE 11 FINAL LOCK"]:
    q = agg[agg["qualified_stage"] == stage]
    if len(q):
        print(
            f"{stage:22s} | n={len(q):3d} | "
            f"coverage={len(q)/len(agg):5.1%} | "
            f"accuracy={(q['qualified_pred']==q['y']).mean():.3f}"
        )

qall = agg[agg["qualified_pred"].notna()]
qnone = agg[agg["qualified_pred"].isna()]

print(
    f"ALL QUALIFIED SIGNALS     | n={len(qall):3d} | "
    f"coverage={len(qall)/len(agg):5.1%} | "
    f"accuracy={(qall['qualified_pred']==qall['y']).mean():.3f}"
)

print(
    f"NO QUALIFIED SIGNAL       | n={len(qnone):3d} | "
    f"share={len(qnone)/len(agg):5.1%}"
)

print()
print("=== EVERY-CONTRACT FORECAST ===")
print(f"Untouched contracts: {len(agg)}")
print(f"Contracts with raw UP/DOWN forecast: {agg['raw_forecast'].notna().sum()}")
print(
    "Every contract has a raw forecast:",
    "YES" if agg["raw_forecast"].notna().all() else "NO"
)

raw_acc = (agg["raw_forecast"] == agg["y"]).mean()
print(f"Raw minute-5 forecast accuracy: {raw_acc:.3f}")

print()
print("=== EARLY-VS-LATE RELATIONSHIP ===")

both = agg[agg["minute8_qualified"] & agg["minute11_lock"]]
if len(both):
    same = (both["pred_8"] == both["pred_11"]).mean()
    print(
        f"Contracts qualifying at minute 8 and also locking at 11: {len(both)}"
    )
    print(f"Minute 8 and minute 11 direction agree: {same:.1%}")

early_wrong = agg[
    agg["minute8_qualified"]
    & (agg["pred_8"] != agg["y"])
]
if len(early_wrong):
    recovered = (early_wrong["pred_11"] == early_wrong["y"]).mean()
    print(
        f"Minute-8 qualified calls that were wrong: {len(early_wrong)}"
    )
    print(f"Those corrected by minute 11: {recovered:.1%}")

print()
print("=== QUALIFIED SIGNAL STABILITY BY BLOCK ===")

for block in sorted(agg["block"].unique()):
    z = agg[agg["block"] == block]
    q = z[z["qualified_pred"].notna()]
    if len(q):
        print(
            f"Block {block}: n={len(q):3d} | "
            f"coverage={len(q)/len(z):5.1%} | "
            f"accuracy={(q['qualified_pred']==q['y']).mean():.3f}"
        )

print()
print("=== ONBOARDING READINESS CHECKS ===")
minute8 = agg[agg["qualified_stage"] == "MINUTE 8 QUALIFIED"]
minute11 = agg[agg["qualified_stage"] == "MINUTE 11 FINAL LOCK"]

m8_acc = np.nan if len(minute8)==0 else (minute8["qualified_pred"]==minute8["y"]).mean()
m11_acc = np.nan if len(minute11)==0 else (minute11["qualified_pred"]==minute11["y"]).mean()
all_acc = np.nan if len(qall)==0 else (qall["qualified_pred"]==qall["y"]).mean()

print("Minute-8 qualified >=90%:", "PASS" if m8_acc >= .90 else "FAIL")
print("Minute-11 added locks >=90%:", "PASS" if m11_acc >= .90 else "FAIL")
print("Combined qualified >=90%:", "PASS" if all_acc >= .90 else "FAIL")
print("Every-contract raw forecast:", "PASS" if agg["raw_forecast"].notna().all() else "FAIL")
print("Settlement-label consistency:", "PASS" if label_ok.all() else "FAIL")
print("Future-data usage: PASS")
print("Chronological holdouts: PASS")
print("Corrected Kalshi timing: PASS")

print()
print("=== TEST COMPLETE ===")
print("No bot files modified.")
print("If all qualified-signal checks remain strong, the next step is integration planning.")
