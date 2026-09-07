from pathlib import Path
import pandas as pd
import numpy as np
import re
import csv

ROOT = Path(".")
OUT = "kalshi_settlement_source_inventory.csv"

KEYWORDS = [
    "brti", "cf benchmark", "cfbench", "benchmark", "settlement",
    "index", "coinbase", "btc_price", "bitcoin_price",
    "underlying", "spot", "reference", "target", "strike"
]

print("=== KALSHI SETTLEMENT-SOURCE AUDIT ===")
print("Purpose: inventory every possible settlement/price source already present in the project.")
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

def norm(s):
    return str(s).strip().lower()

def parse_dt_series(s):
    return pd.to_datetime(s, utc=True, errors="coerce")

records = []

csv_files = sorted(ROOT.glob("*.csv"))
print(f"CSV files found: {len(csv_files)}")
print()

for path in csv_files:
    try:
        df = pd.read_csv(path, low_memory=False)
    except Exception:
        continue

    cols = list(df.columns)
    lower = [norm(c) for c in cols]

    matched_cols = []
    for c, lc in zip(cols, lower):
        if any(k in lc for k in KEYWORDS):
            matched_cols.append(c)

    # timestamp candidates
    ts_cols = [c for c in cols if any(k in norm(c) for k in ["timestamp", "time_utc", "datetime", "created_at"])]
    cadence_sec = np.nan
    cadence_col = ""

    for tc in ts_cols:
        ts = parse_dt_series(df[tc]).dropna().sort_values()
        if len(ts) >= 3:
            diffs = ts.diff().dt.total_seconds().dropna()
            diffs = diffs[diffs > 0]
            if len(diffs):
                med = float(diffs.median())
                if pd.isna(cadence_sec) or med < cadence_sec:
                    cadence_sec = med
                    cadence_col = tc

    if matched_cols:
        print("=" * 95)
        print("FILE:", path.name)
        print("ROWS:", len(df))
        print("MATCHED COLUMNS:", matched_cols)
        if cadence_col:
            print(f"FASTEST MEDIAN CADENCE: {cadence_sec:.3f} sec using {cadence_col}")
        else:
            print("CADENCE: could not determine")

        for c in matched_cols:
            s = pd.to_numeric(df[c], errors="coerce")
            n_num = int(s.notna().sum())
            text_sample = ""
            if n_num == 0:
                vals = df[c].dropna().astype(str).head(3).tolist()
                text_sample = " | sample=" + " ; ".join(vals[:3])
            else:
                vals = s.dropna()
                text_sample = (
                    f" | numeric n={len(vals)}"
                    f" med={vals.median():.6f}"
                    f" min={vals.min():.6f}"
                    f" max={vals.max():.6f}"
                )
            print(f"  - {c}{text_sample}")

            records.append({
                "file": path.name,
                "rows": len(df),
                "column": c,
                "median_cadence_sec": cadence_sec,
                "cadence_timestamp_column": cadence_col,
                "numeric_count": n_num,
            })
        print()

# Search Python source for price/settlement provider references.
print()
print("=== PYTHON SOURCE REFERENCES ===")
source_hits = []
for path in sorted(ROOT.glob("*.py")):
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        continue
    low = text.lower()
    hits = [k for k in KEYWORDS if k in low]
    if hits:
        # Find especially useful provider/feed lines.
        useful = []
        for i, line in enumerate(text.splitlines(), 1):
            ll = line.lower()
            if any(k in ll for k in [
                "coinbase", "brti", "cfbench", "benchmark",
                "settlement", "index", "btc_price", "target"
            ]):
                useful.append((i, line.strip()))
        if useful:
            print("=" * 95)
            print("FILE:", path.name)
            for i, line in useful[:40]:
                print(f"{i:4d}: {line[:180]}")
            if len(useful) > 40:
                print(f"... {len(useful)-40} more matching lines")
            source_hits.append(path.name)

print()
print("=== SPEED SUMMARY ===")
if records:
    inv = pd.DataFrame(records)
    inv.to_csv(OUT, index=False)

    # summarize fastest files
    fsum = (
        inv.groupby("file", dropna=False)
        .agg(
            median_cadence_sec=("median_cadence_sec", "min"),
            matched_columns=("column", "count")
        )
        .reset_index()
        .sort_values("median_cadence_sec", na_position="last")
    )

    print(fsum.head(20).to_string(index=False))

    fast = fsum[fsum["median_cadence_sec"].notna() & (fsum["median_cadence_sec"] <= 5)]
    medium = fsum[fsum["median_cadence_sec"].notna() & (fsum["median_cadence_sec"] <= 30)]

    print()
    print("Files <=5 sec cadence:", len(fast))
    if len(fast):
        print(fast.to_string(index=False))

    print()
    print("Files <=30 sec cadence:", len(medium))
    if len(medium):
        print(medium.to_string(index=False))
else:
    pd.DataFrame().to_csv(OUT, index=False)
    print("No matching settlement/price columns found.")

print()
print("=== INTERPRETATION GUIDE ===")
print("If we find BRTI/CF-Benchmark data: use it for settlement-aware validation.")
print("If we only find Coinbase: next step is adding a benchmark-compatible settlement feed or proxy.")
print("If cadence is ~30-60 sec: it is too sparse to recreate a true 60-sample final-minute average exactly.")
print("If cadence is <=1-5 sec: we may already have enough raw data to model the settlement window much better.")
print()
print(f"Saved: {OUT}")
print("=== SETTLEMENT-SOURCE AUDIT COMPLETE ===")
print("Research only. No rule installed.")
