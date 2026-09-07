from pathlib import Path
import pandas as pd
import numpy as np
import csv

LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OFFICIAL = Path("kalshi_official_settlement_check.csv")

TARGETS = [
    "KXBTC15M-26AUG250945-45",
    "KXBTC15M-26AUG270615-15",
]

print("=== KALSHI SETTLEMENT ALIGNMENT AUDIT ===")
print("Purpose: verify ticker/target/countdown/distance remain aligned through settlement.")
print("Targets:")
for t in TARGETS:
    print(" -", t)
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")
if not OFFICIAL.exists():
    raise SystemExit("Missing kalshi_official_settlement_check.csv")

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

def headerish(row):
    low=[str(x).lower() for x in row]
    keys=["ticker","timestamp","distance","fair","target","remaining","btc"]
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

live=pd.DataFrame(rows)

tc=pick(live.columns,["ticker","contract_ticker","market_ticker"])
ts=pick(live.columns,["timestamp_utc","timestamp","snapshot_time"])
rm=pick(live.columns,["remaining_min","time_left","minutes_left"])
btc=pick(live.columns,["btc_price","bitcoin_price","underlying_price","spot_price"])
target=pick(live.columns,["target_price","strike","contract_target","start_price"])
dist=pick(live.columns,["distance_target","distance_from_target","distance"])
ps=pick(live.columns,["preferred_side","current_target_side"])
status=pick(live.columns,["signal_status","status"])
fu=pick(live.columns,["fair_up"])
fd=pick(live.columns,["fair_down"])
ua=pick(live.columns,["up_ask"])
da=pick(live.columns,["down_ask"])

for c in [rm,btc,target,dist,fu,fd,ua,da]:
    if c:
        live[c]=pd.to_numeric(live[c],errors="coerce")
live[ts]=pd.to_datetime(live[ts],utc=True,errors="coerce")
live[tc]=live[tc].astype(str)

official=pd.read_csv(OFFICIAL)
ot=pick(official.columns,["ticker","contract_ticker","market_ticker"])
ores=pick(official.columns,["result","official_result","winner","settlement_result"])
ost=pick(official.columns,["status","market_status"])
osett=pick(official.columns,["settlement_time","settled_at","expiration_time","close_time"])

if osett:
    official[osett]=pd.to_datetime(official[osett],utc=True,errors="coerce")

def expected_side_from_distance(x):
    if pd.isna(x): return ""
    if x>0: return "UP"
    if x<0: return "DOWN"
    return "TIE"

audit_rows=[]

for ticker in TARGETS:
    print()
    print("="*90)
    print("TICKER:",ticker)

    oq=official[official[ot].astype(str)==ticker]
    if len(oq):
        o=oq.iloc[-1]
        print("OFFICIAL RESULT:", o[ores] if ores else "unknown",
              "| STATUS:", o[ost] if ost else "unknown",
              "| SETTLEMENT:", o[osett] if osett else "unknown")
    else:
        print("OFFICIAL RESULT: NOT FOUND")

    q=live[live[tc]==ticker].copy().sort_values(ts)
    print("LIVE SNAPSHOTS:",len(q))

    if q.empty:
        continue

    # show last 15 snapshots to focus on settlement alignment
    tail=q.tail(15).copy()

    for _,r in tail.iterrows():
        derived=None
        if btc and target and pd.notna(r[btc]) and pd.notna(r[target]):
            derived=float(r[btc])-float(r[target])

        stored=float(r[dist]) if dist and pd.notna(r[dist]) else np.nan
        mismatch=np.nan
        if derived is not None and pd.notna(stored):
            mismatch=stored-derived

        row={
            "ticker":ticker,
            "timestamp":r[ts],
            "remaining_min":float(r[rm]) if rm and pd.notna(r[rm]) else np.nan,
            "btc_price":float(r[btc]) if btc and pd.notna(r[btc]) else np.nan,
            "target_price":float(r[target]) if target and pd.notna(r[target]) else np.nan,
            "stored_distance":stored,
            "derived_btc_minus_target":derived if derived is not None else np.nan,
            "distance_mismatch":mismatch,
            "stored_distance_side":expected_side_from_distance(stored),
            "derived_side":expected_side_from_distance(derived) if derived is not None else "",
            "preferred_side":r[ps] if ps else "",
            "signal_status":r[status] if status else "",
            "fair_up":float(r[fu]) if fu and pd.notna(r[fu]) else np.nan,
            "fair_down":float(r[fd]) if fd and pd.notna(r[fd]) else np.nan,
            "up_ask":float(r[ua]) if ua and pd.notna(r[ua]) else np.nan,
            "down_ask":float(r[da]) if da and pd.notna(r[da]) else np.nan,
            "source_line":r["_source_line"],
        }
        audit_rows.append(row)

    show=pd.DataFrame(audit_rows)
    show=show[show["ticker"]==ticker]

    print()
    print("=== LAST SNAPSHOTS ===")
    print(show.to_string(index=False))

    # checks
    print()
    print("=== ALIGNMENT CHECKS ===")
    if target:
        vals=q[target].dropna().unique()
        print("Distinct target prices in ticker:",len(vals), list(np.round(vals,6))[:10])
    else:
        print("Target column not found.")

    if rm:
        rr=q[rm].dropna()
        if len(rr)>=2:
            diffs=rr.diff().dropna()
            non_decreasing=int((diffs>=0).sum())
            print("Countdown non-decreasing steps:",non_decreasing,
                  "(should normally be 0 except duplicate/restart edge cases)")
        print("Final remaining_min:", rr.iloc[-1] if len(rr) else np.nan)

    if btc and target and dist:
        tmp=q[[btc,target,dist]].dropna().copy()
        if len(tmp):
            err=(tmp[dist]-(tmp[btc]-tmp[target])).abs()
            print("Max |stored distance - (BTC-target)|:",float(err.max()))
            print("Median mismatch:",float(err.median()))
            print("Rows with mismatch > $1:",int((err>1).sum()),"/",len(err))

    # compare final sign to official result
    if len(oq) and dist:
        result=str(oq.iloc[-1][ores]).upper() if ores else ""
        final=q.dropna(subset=[dist]).iloc[-1] if q[dist].notna().any() else None
        if final is not None:
            final_side=expected_side_from_distance(float(final[dist]))
            print("Final stored-distance side:",final_side,"| official:",result)
            print("SIGN AGREEMENT:", final_side==result)

out=pd.DataFrame(audit_rows)
out.to_csv("kalshi_settlement_alignment_audit_details.csv",index=False)

print()
print("Saved: kalshi_settlement_alignment_audit_details.csv")
print("=== SETTLEMENT ALIGNMENT AUDIT COMPLETE ===")
print("Research only. No rule installed.")
