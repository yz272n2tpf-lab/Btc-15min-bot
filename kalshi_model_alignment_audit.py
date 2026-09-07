from pathlib import Path
import pandas as pd

CAL = Path("brti_calibration_results.csv")
BTC = Path("btc_35d_live_cache.csv")

print("=== KALSHI MODEL ALIGNMENT AUDIT ===")
print("Purpose: inspect historical settled-contract fields before changing model logic.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if not CAL.exists():
    raise SystemExit("ERROR: brti_calibration_results.csv not found.")

cal = pd.read_csv(CAL)

print("Calibration rows:", len(cal))
print("Calibration columns:", len(cal.columns))
print()
print("=== CALIBRATION COLUMNS ===")
for i, c in enumerate(cal.columns, start=1):
    print(f"{i:02d}. {c}")

print()
print("=== LIKELY KALSHI / TARGET / OUTCOME FIELDS ===")
keywords = (
    "ticker", "target", "strike", "result", "outcome", "settle",
    "brti", "coinbase", "final", "open", "close", "time", "gap", "bias"
)

likely = [
    c for c in cal.columns
    if any(k in c.lower() for k in keywords)
]

if likely:
    for c in likely:
        print("-", c)
else:
    print("None detected automatically.")

print()
print("=== NON-NULL COUNTS FOR LIKELY FIELDS ===")
for c in likely:
    print(f"{c}: {cal[c].notna().sum()}/{len(cal)}")

print()
print("=== SAMPLE SETTLED CONTRACT ROWS ===")
sample_cols = likely[:14] if likely else list(cal.columns[:14])
print(cal[sample_cols].head(8).to_string(index=False))

print()
print("=== VALUE COUNTS FOR POSSIBLE LABEL FIELDS ===")
label_words = ("result", "outcome", "settle", "direction", "yes", "win")
label_cols = [
    c for c in cal.columns
    if any(k in c.lower() for k in label_words)
]

if not label_cols:
    print("No obvious label columns detected.")
else:
    for c in label_cols:
        vals = cal[c].dropna()
        if len(vals) == 0:
            continue
        unique = vals.astype(str).nunique()
        if unique <= 20:
            print(f"\n{c}:")
            print(vals.astype(str).value_counts().head(20).to_string())

print()
print("=== BTC CACHE CHECK ===")
if BTC.exists():
    btc = pd.read_csv(BTC)
    print("BTC rows:", len(btc))
    print("BTC columns:", len(btc.columns))
    print("BTC column names:")
    for i, c in enumerate(btc.columns, start=1):
        print(f"{i:02d}. {c}")
else:
    print("btc_35d_live_cache.csv not found.")

print()
print("=== AUDIT COMPLETE ===")
print("No files modified.")
print("NEXT: use this output to map a true Kalshi-settlement prediction target.")
