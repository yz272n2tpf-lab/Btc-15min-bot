from pathlib import Path
import pandas as pd
import numpy as np
import csv
import re

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

TARGETS = [
    "KXBTC15M-26AUG250945-45",
    "KXBTC15M-26AUG270615-15",
]

print("=== KALSHI DISTANCE SOURCE AUDIT ===")
print("Purpose: identify exactly which logged fields produce stored_distance.")
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

def headerish(row):
    low=[str(x).lower() for x in row]
    keys=["ticker","timestamp","distance","fair","ask","remaining","price","target","strike"]
    return sum(any(k in x for k in keys) for x in low) >= 2

rows=[]; header=None
with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
    for line_no,row in enumerate(csv.reader(f),1):
        if not row:
            continue
        if headerish(row):
            header=[str(x).strip() for x in row]
            continue
        if header is None:
            continue
        row=row+[""]*max(0,len(header)-len(row))
        rec=dict(zip(header,row[:len(header)]))
        rec["_source_line"]=line_no
        rows.append(rec)

df=pd.DataFrame(rows)

print("=== CSV COLUMNS FOUND ===")
for i,c in enumerate(df.columns):
    print(f"{i:02d}: {c}")
print()

def pick(cols, names):
    for n in names:
        for c in cols:
            if str(c).lower() == n.lower():
                return c
    for n in names:
        for c in cols:
            if n.lower() in str(c).lower():
                return c
    return None

ticker_col=pick(df.columns,["ticker","contract_ticker","market_ticker"])
time_col=pick(df.columns,["timestamp_utc","timestamp","snapshot_time"])
dist_col=pick(df.columns,["distance_target","distance_from_target","distance"])

if ticker_col is None:
    raise SystemExit("Could not find ticker column.")
if dist_col is None:
    raise SystemExit("Could not find distance column.")

df[ticker_col]=df[ticker_col].astype(str)
if time_col:
    df[time_col]=pd.to_datetime(df[time_col],utc=True,errors="coerce")
df[dist_col]=pd.to_numeric(df[dist_col],errors="coerce")

# Convert all plausible columns to numeric copies.
ignore={ticker_col,time_col,"_source_line"}
numeric={}
for c in df.columns:
    if c in ignore:
        continue
    s=pd.to_numeric(df[c],errors="coerce")
    if s.notna().sum() >= 5:
        numeric[c]=s

print("=== NAME-BASED PRICE/TARGET CANDIDATES ===")
keywords=("btc","price","spot","underlying","target","strike","reference","start","threshold","floor","cap","value")
named=[c for c in numeric if any(k in c.lower() for k in keywords)]
if named:
    for c in named:
        vals=numeric[c].dropna()
        print(f"{c:35s} n={len(vals):5d} median={vals.median():12.4f} min={vals.min():12.4f} max={vals.max():12.4f}")
else:
    print("None found by name.")
print()

audit_rows=[]

for ticker in TARGETS:
    q=df[df[ticker_col]==ticker].copy()
    if q.empty:
        print("TARGET NOT FOUND:",ticker)
        continue

    if time_col:
        q=q.sort_values(time_col)

    print("="*100)
    print("TICKER:",ticker,"| rows:",len(q))

    # Numeric columns with BTC-like magnitudes for this ticker.
    btc_like=[]
    for c,s in numeric.items():
        vals=pd.to_numeric(q[c],errors="coerce").dropna()
        if len(vals) < max(3, int(len(q)*0.25)):
            continue
        med=float(vals.median())
        # Broad BTC-ish range.
        if 1000 <= abs(med) <= 250000:
            btc_like.append(c)

    print("BTC-MAGNITUDE CANDIDATES:", btc_like if btc_like else "NONE")

    # Find any pair A-B that reproduces stored distance.
    pair_scores=[]
    for a in btc_like:
        av=pd.to_numeric(q[a],errors="coerce")
        for b in btc_like:
            if a==b:
                continue
            bv=pd.to_numeric(q[b],errors="coerce")
            dv=pd.to_numeric(q[dist_col],errors="coerce")
            mask=av.notna() & bv.notna() & dv.notna()
            if mask.sum() < 3:
                continue
            err=((av[mask]-bv[mask])-dv[mask]).abs()
            pair_scores.append({
                "ticker":ticker,
                "a":a,
                "b":b,
                "n":int(mask.sum()),
                "median_abs_error":float(err.median()),
                "max_abs_error":float(err.max()),
            })

    pair_scores=sorted(pair_scores,key=lambda x:(x["median_abs_error"],x["max_abs_error"]))
    print()
    print("=== BEST A - B = STORED_DISTANCE MATCHES ===")
    if pair_scores:
        for r in pair_scores[:10]:
            print(
                f"{r['a']} - {r['b']} | n={r['n']} | "
                f"median_err=${r['median_abs_error']:.6f} | max_err=${r['max_abs_error']:.6f}"
            )
    else:
        print("No usable BTC-magnitude pairs found.")

    # Look for near-constant BTC-like field: likely target/strike.
    print()
    print("=== POSSIBLE FIXED TARGET / STRIKE FIELDS ===")
    candidates=[]
    for c in btc_like:
        vals=pd.to_numeric(q[c],errors="coerce").dropna()
        if len(vals)<3:
            continue
        spread=float(vals.max()-vals.min())
        nunique=int(vals.round(6).nunique())
        candidates.append((spread,nunique,c,float(vals.iloc[0]),float(vals.median())))
    for spread,nunique,c,first,med in sorted(candidates)[:10]:
        print(f"{c:35s} spread=${spread:10.4f} unique={nunique:3d} first={first:12.4f} median={med:12.4f}")

    # If only one BTC-like live price exists, infer target = price - distance
    # and see whether inferred target is stable.
    print()
    print("=== INFERRED TARGET TESTS: candidate_price - stored_distance ===")
    for c in btc_like:
        pv=pd.to_numeric(q[c],errors="coerce")
        dv=pd.to_numeric(q[dist_col],errors="coerce")
        mask=pv.notna() & dv.notna()
        if mask.sum()<3:
            continue
        inferred=pv[mask]-dv[mask]
        spread=float(inferred.max()-inferred.min())
        print(
            f"using {c:35s} | n={mask.sum():3d} | inferred_target median={inferred.median():12.4f} "
            f"| spread=${spread:.6f} | unique={inferred.round(4).nunique()}"
        )

    # Save last rows with all numeric candidates + core fields.
    keep=[ticker_col]
    if time_col: keep.append(time_col)
    keep.append(dist_col)
    keep += [c for c in btc_like if c not in keep]
    keep.append("_source_line")
    tail=q[keep].tail(15).copy()
    tail.insert(0,"audit_target",ticker)
    audit_rows.append(tail)

    print()
    print("=== LAST 15 RAW NUMERIC PRICE-LIKE ROWS ===")
    print(tail.to_string(index=False))
    print()

if audit_rows:
    out=pd.concat(audit_rows,ignore_index=True)
    out.to_csv("kalshi_distance_source_audit_details.csv",index=False)

print("Saved: kalshi_distance_source_audit_details.csv")
print("=== DISTANCE SOURCE AUDIT COMPLETE ===")
print("Research only. No rule installed.")
