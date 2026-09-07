from pathlib import Path
import re
import numpy as np
import pandas as pd
from zoneinfo import ZoneInfo
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== CORRECTED KALSHI SETTLEMENT WALK-FORWARD TEST ===")
print("Timing rule: ticker timestamp = CONTRACT CLOSE in America/New_York time.")
print("Contract start = ticker close minus 15 minutes.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not CAL.exists():
    raise SystemExit("ERROR: brti_calibration_results.csv not found.")
if not BTC.exists():
    raise SystemExit("ERROR: btc_35d_live_cache.csv not found.")

cal = pd.read_csv(CAL)
btc = pd.read_csv(BTC)

required_cal = {"ticker", "target_brti", "final_brti", "result"}
missing = required_cal - set(cal.columns)
if missing:
    raise SystemExit(f"ERROR: calibration file missing columns: {sorted(missing)}")

if "Datetime" not in btc.columns:
    raise SystemExit("ERROR: BTC cache missing Datetime column.")

btc["Datetime"] = pd.to_datetime(btc["Datetime"], utc=True, errors="coerce")
btc = btc.dropna(subset=["Datetime"]).sort_values("Datetime").set_index("Datetime")

for c in ["Open", "High", "Low", "Close", "Volume"]:
    if c in btc.columns:
        btc[c] = pd.to_numeric(btc[c], errors="coerce")

MONTHS = {
    "JAN": 1, "FEB": 2, "MAR": 3, "APR": 4,
    "MAY": 5, "JUN": 6, "JUL": 7, "AUG": 8,
    "SEP": 9, "OCT": 10, "NOV": 11, "DEC": 12,
}

def parse_contract_times(ticker):
    """
    Example:
    KXBTC15M-26AUG221545-45

    Proven convention:
    2026-08-22 15:45 is CONTRACT CLOSE in America/New_York time.
    """
    s = str(ticker).upper().strip()
    m = re.search(r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-", s)
    if not m:
        return pd.NaT, pd.NaT

    yy, mon, dd, hh, mm = m.groups()
    if mon not in MONTHS:
        return pd.NaT, pd.NaT

    try:
        wall = pd.Timestamp(
            year=2000 + int(yy),
            month=MONTHS[mon],
            day=int(dd),
            hour=int(hh),
            minute=int(mm),
        )
        close_et = wall.tz_localize(ZoneInfo("America/New_York"))
        close_utc = close_et.tz_convert("UTC")
        start_utc = close_utc - pd.Timedelta(minutes=15)
        return start_utc, close_utc
    except Exception:
        return pd.NaT, pd.NaT

times = cal["ticker"].map(parse_contract_times)
cal["start_time"] = [x[0] for x in times]
cal["close_time"] = [x[1] for x in times]

cal["target_brti"] = pd.to_numeric(cal["target_brti"], errors="coerce")
cal["final_brti"] = pd.to_numeric(cal["final_brti"], errors="coerce")
cal["y"] = cal["result"].astype(str).str.lower().map({"yes": 1, "no": 0})
cal = cal.dropna(subset=["start_time", "close_time", "target_brti", "final_brti", "y"])
cal = cal.sort_values("start_time").reset_index(drop=True)

label_check = (
    (cal["final_brti"] >= cal["target_brti"]).astype(int)
    == cal["y"].astype(int)
)

print("Usable settled contracts:", len(cal))
print("YES:", int((cal["y"] == 1).sum()))
print("NO:", int((cal["y"] == 0).sum()))
print(
    "Settlement label sanity:",
    f"{label_check.mean():.3%}",
    f"({int(label_check.sum())}/{len(label_check)})",
)
print()

def get_close_at_or_before(ts, tolerance_minutes=2):
    if len(btc) == 0:
        return np.nan
    pos = btc.index.searchsorted(ts, side="right") - 1
    if pos < 0:
        return np.nan
    idx = btc.index[pos]
    if ts - idx > pd.Timedelta(minutes=tolerance_minutes):
        return np.nan
    return float(btc.iloc[pos]["Close"])

def make_snapshot(row, elapsed):
    start = row["start_time"]
    target = float(row["target_brti"])

    t = start + pd.Timedelta(minutes=elapsed)
    p0 = get_close_at_or_before(start)
    p1 = get_close_at_or_before(t)
    p_1 = get_close_at_or_before(t - pd.Timedelta(minutes=1))
    p_3 = get_close_at_or_before(t - pd.Timedelta(minutes=3))
    p_5 = get_close_at_or_before(t - pd.Timedelta(minutes=5))

    vals = [p0, p1, p_1, p_3, p_5]
    if any(pd.isna(v) for v in vals):
        return None

    w = btc.loc[
        (btc.index > t - pd.Timedelta(minutes=5))
        & (btc.index <= t)
    ]
    if len(w) < 3:
        return None

    high5 = pd.to_numeric(w["High"], errors="coerce").max()
    low5 = pd.to_numeric(w["Low"], errors="coerce").min()
    close5 = pd.to_numeric(w["Close"], errors="coerce")

    if pd.isna(high5) or pd.isna(low5) or close5.isna().all():
        return None

    dist_target = p1 - target
    dist_start = p1 - p0

    return {
        "ticker": row["ticker"],
        "start_time": start,
        "elapsed": elapsed,
        "y": int(row["y"]),
        "current_side": 1 if dist_target >= 0 else 0,
        "dist_target_dollars": dist_target,
        "dist_target_pct": dist_target / target,
        "abs_dist_target": abs(dist_target),
        "dist_start_dollars": dist_start,
        "dist_start_pct": dist_start / p0,
        "move_1m": p1 - p_1,
        "move_3m": p1 - p_3,
        "move_5m": p1 - p_5,
        "range_5m": float(high5 - low5),
        "vol_5m": float(
            close5.pct_change().std(ddof=0)
            if len(close5) > 1 else 0.0
        ),
    }

elapsed_points = [1, 3, 5, 7, 9, 11]
all_results = []

for elapsed in elapsed_points:
    rows = []
    for _, r in cal.iterrows():
        snap = make_snapshot(r, elapsed)
        if snap is not None:
            rows.append(snap)

    df = pd.DataFrame(rows).sort_values("start_time").reset_index(drop=True)

    print(f"=== ELAPSED MINUTE {elapsed} ===")
    print("Snapshots:", len(df))

    if len(df) < 120:
        print("Too few aligned snapshots for reliable walk-forward test.")
        print()
        continue

    baseline_acc = accuracy_score(df["y"], df["current_side"])
    print(f"Current-side-vs-target baseline accuracy: {baseline_acc:.3f}")

    feature_cols = [
        "current_side",
        "dist_target_dollars",
        "dist_target_pct",
        "abs_dist_target",
        "dist_start_dollars",
        "dist_start_pct",
        "move_1m",
        "move_3m",
        "move_5m",
        "range_5m",
        "vol_5m",
    ]

    fold_starts = [0.50, 0.60, 0.70, 0.80, 0.90]
    fold_ends   = [0.60, 0.70, 0.80, 0.90, 1.00]

    fold_correct = 0
    fold_total = 0

    conf_stats = {
        0.60: [0, 0],
        0.65: [0, 0],
        0.70: [0, 0],
        0.75: [0, 0],
        0.80: [0, 0],
    }

    for a, b in zip(fold_starts, fold_ends):
        train_end = int(len(df) * a)
        test_end = int(len(df) * b)

        train = df.iloc[:train_end]
        test = df.iloc[train_end:test_end]

        if len(train) < 100 or len(test) == 0:
            continue

        X_train = train[feature_cols]
        y_train = train["y"]
        X_test = test[feature_cols]
        y_test = test["y"].to_numpy()

        model = RandomForestClassifier(
            n_estimators=400,
            max_depth=7,
            min_samples_leaf=8,
            class_weight="balanced",
            random_state=42,
            n_jobs=-1,
        )
        model.fit(X_train, y_train)

        pred = model.predict(X_test)
        proba = model.predict_proba(X_test)
        conf = proba.max(axis=1)

        correct = pred == y_test

        fold_correct += int(correct.sum())
        fold_total += len(test)

        for threshold in conf_stats:
            mask = conf >= threshold
            if mask.any():
                conf_stats[threshold][0] += int(correct[mask].sum())
                conf_stats[threshold][1] += int(mask.sum())

        print(
            f"Fold {int(a*100)}->{int(b*100)}% | "
            f"train {len(train)} | test {len(test)} | "
            f"accuracy {accuracy_score(y_test, pred):.3f} | "
            f"70%+ coverage {(conf >= 0.70).mean():.1%}"
        )

    wf_acc = fold_correct / fold_total if fold_total else np.nan

    print("WALK-FORWARD TOTAL:")
    print(f"Accuracy: {wf_acc:.3f}" if not pd.isna(wf_acc) else "Accuracy: N/A")

    threshold_results = {}
    for threshold, (correct_n, total_n) in conf_stats.items():
        if total_n:
            acc = correct_n / total_n
            cov = total_n / fold_total
            print(
                f"{int(threshold*100)}%+ confidence: "
                f"accuracy {acc:.3f} | coverage {cov:.1%} | n={total_n}"
            )
        else:
            acc = np.nan
            cov = 0.0
            print(f"{int(threshold*100)}%+ confidence: none")

        threshold_results[threshold] = (acc, cov, total_n)

    hc70 = threshold_results[0.70]

    all_results.append({
        "elapsed": elapsed,
        "snapshots": len(df),
        "baseline_acc": baseline_acc,
        "walkforward_acc": wf_acc,
        "conf70_acc": hc70[0],
        "conf70_coverage": hc70[1],
        "conf70_n": hc70[2],
    })

    print()

print("=== SUMMARY ===")
if not all_results:
    print("No elapsed point had enough data.")
else:
    summary = pd.DataFrame(all_results)
    print(
        summary.to_string(
            index=False,
            float_format=lambda x: f"{x:.3f}",
        )
    )

print()
print("=== CORRECTED TEST COMPLETE ===")
print("No bot files modified.")
print("Use this result only after confirming timing correction materially changes alignment.")
