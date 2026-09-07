from pathlib import Path
import pandas as pd
import numpy as np
import csv

BASE = Path("kalshi_layer_a_forward_only_results.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== KALSHI STRONG-CONFIRMATION GIVEBACK VALIDATOR ===")
print("Purpose: test whether large post-confirmation giveback predicts eventual failure.")
print()
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

if not BASE.exists():
    raise SystemExit("Missing kalshi_layer_a_forward_only_results.csv")
if not LIVE.exists():
    raise SystemExit("Missing kalshi_live_fair_value_shadow_log.csv")

calls = pd.read_csv(BASE)
calls["call_time"] = pd.to_datetime(calls["call_time"], utc=True, errors="coerce")
calls["correct"] = calls["correct"].astype(str).str.lower().map({"true": True, "false": False})

# Keep Layer A CLEAN calls only.
if "state" in calls.columns:
    calls = calls[calls["state"].astype(str).str.upper().eq("CLEAN")].copy()
elif "layer_a_state" in calls.columns:
    calls = calls[calls["layer_a_state"].astype(str).str.upper().eq("CLEAN")].copy()

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
    keys=["ticker","timestamp","distance","fair","ask","remaining"]
    return sum(any(k in x for k in keys) for x in low) >= 2

rows=[]; header=None
with LIVE.open("r", newline="", encoding="utf-8-sig", errors="replace") as f:
    for row in csv.reader(f):
        if not row: 
            continue
        if headerish(row):
            header=[str(x).strip() for x in row]
            continue
        if header is None:
            continue
        row=row+[""]*max(0,len(header)-len(row))
        rows.append(dict(zip(header,row[:len(header)])))

live=pd.DataFrame(rows)

tc=pick(live.columns,["ticker","contract_ticker","market_ticker"])
ts=pick(live.columns,["timestamp_utc","timestamp","snapshot_time"])
dc=pick(live.columns,["distance_target","distance_from_target","distance"])
fu=pick(live.columns,["fair_up"])
fd=pick(live.columns,["fair_down"])
ua=pick(live.columns,["up_ask"])
da=pick(live.columns,["down_ask"])
rm=pick(live.columns,["remaining_min","time_left","minutes_left"])

for c in [dc,fu,fd,ua,da,rm]:
    if c:
        live[c]=pd.to_numeric(live[c],errors="coerce")
live[ts]=pd.to_datetime(live[ts],utc=True,errors="coerce")
live[tc]=live[tc].astype(str)

def path_for(call):
    ticker=str(call["ticker"])
    side=str(call["call_side"]).upper()
    t0=call["call_time"]
    init_dist=float(call["initial_distance"])
    init_signed=init_dist if side=="UP" else -init_dist
    init_fair=float(call["initial_fair"])

    q=live[(live[tc]==ticker)&(live[ts]>=t0)].sort_values(ts).copy()
    out=[]
    for _,nr in q.iterrows():
        sec=(nr[ts]-t0).total_seconds()
        if sec < 0:
            continue
        signed=float(nr[dc]) if side=="UP" else -float(nr[dc])

        fair=(float(nr[fu]) if side=="UP" and fu and pd.notna(nr[fu]) else
              float(nr[fd]) if side=="DOWN" and fd and pd.notna(nr[fd]) else np.nan)
        ask=(float(nr[ua]) if side=="UP" and ua and pd.notna(nr[ua]) else
             float(nr[da]) if side=="DOWN" and da and pd.notna(nr[da]) else np.nan)

        out.append({
            "sec_from_call":sec,
            "min_from_call":sec/60,
            "timestamp":nr[ts],
            "remaining_min":float(nr[rm]) if rm and pd.notna(nr[rm]) else np.nan,
            "distance_gain":signed-init_signed,
            "fair_gain":fair-init_fair if pd.notna(fair) else np.nan,
            "ask_change":ask-init_fair if pd.notna(ask) else np.nan,
        })
    return pd.DataFrame(out)

def checkpoint(p, minute, tol=.75):
    if p.empty:
        return None
    d=(p["min_from_call"]-minute).abs()
    i=d.idxmin()
    if abs(float(p.loc[i,"min_from_call"])-minute)>tol:
        return None
    return p.loc[i]

records=[]

for _,call in calls.iterrows():
    p=path_for(call)
    if p.empty:
        continue

    c6=checkpoint(p,6)
    if c6 is None:
        continue

    gain6=float(c6["distance_gain"])
    fair6=float(c6["fair_gain"]) if pd.notna(c6["fair_gain"]) else np.nan

    # Strong confirmation definition for research population only.
    strongly_confirmed = (gain6 >= 40) and pd.notna(fair6) and (fair6 >= 0.10)
    if not strongly_confirmed:
        continue

    after6=p[p["min_from_call"]>=float(c6["min_from_call"])].copy()
    if after6.empty:
        continue

    worst_dist=float(after6["distance_gain"].min())
    worst_fair=float(after6["fair_gain"].min()) if after6["fair_gain"].notna().any() else np.nan

    dist_giveback=gain6-worst_dist
    fair_giveback=fair6-worst_fair if pd.notna(fair6) and pd.notna(worst_fair) else np.nan
    pct_dist_giveback=(dist_giveback/gain6) if gain6>0 else np.nan

    # first 50% giveback
    hit50=after6[after6["distance_gain"] <= gain6*0.5]
    first50=float(hit50.iloc[0]["min_from_call"]) if len(hit50) else np.nan

    # first fair gain below +5 points
    hitfair=after6[after6["fair_gain"] < 0.05]
    firstfair=float(hitfair.iloc[0]["min_from_call"]) if len(hitfair) else np.nan

    rec={
        "ticker":str(call["ticker"]),
        "correct":bool(call["correct"]),
        "call_side":str(call["call_side"]).upper(),
        "initial_fair":float(call["initial_fair"]),
        "initial_distance":float(call["initial_distance"]),
        "gain6":gain6,
        "fair6":fair6,
        "worst_distance_gain_after6":worst_dist,
        "worst_fair_gain_after6":worst_fair,
        "distance_giveback":dist_giveback,
        "pct_distance_giveback":pct_dist_giveback,
        "fair_giveback":fair_giveback,
        "first_50pct_giveback_min":first50,
        "first_fair_below_5pt_min":firstfair,
    }

    # later checkpoints
    for minute in [7,8,9,10]:
        cp=checkpoint(p,minute)
        rec[f"{minute}m_distance_gain"]=np.nan if cp is None else float(cp["distance_gain"])
        rec[f"{minute}m_fair_gain"]=np.nan if cp is None or pd.isna(cp["fair_gain"]) else float(cp["fair_gain"])

    records.append(rec)

d=pd.DataFrame(records)

print("Layer A CLEAN strongly-confirmed calls:", len(d))
if len(d)==0:
    raise SystemExit("No strongly-confirmed calls found.")

wins=int(d["correct"].sum())
losses=int((~d["correct"]).sum())
print("Winners:", wins)
print("Losses:", losses)
print("Baseline accuracy:", f"{100*wins/len(d):.1f}%")
print()

# Candidate thresholds for research only.
candidates = [
    ("distance giveback >= $75", d["distance_giveback"] >= 75),
    ("distance giveback >= $100", d["distance_giveback"] >= 100),
    ("distance giveback >= $125", d["distance_giveback"] >= 125),
    ("distance giveback >= 50%", d["pct_distance_giveback"] >= 0.50),
    ("distance giveback >= 75%", d["pct_distance_giveback"] >= 0.75),
    ("fair giveback >= 10pt", d["fair_giveback"] >= 0.10),
    ("fair giveback >= 15pt", d["fair_giveback"] >= 0.15),
    ("fair giveback >= 20pt", d["fair_giveback"] >= 0.20),
    ("50% distance OR fair<+5pt", d["first_50pct_giveback_min"].notna() | d["first_fair_below_5pt_min"].notna()),
]

print("=== GIVEBACK CANDIDATE RESULTS ===")
for name,flag in candidates:
    flagged=d[flag]
    kept=d[~flag]
    caught=int((~flagged["correct"]).sum())
    good_flagged=int(flagged["correct"].sum())
    total_losses=losses
    capture=100*caught/total_losses if total_losses else np.nan
    kept_acc=100*kept["correct"].mean() if len(kept) else np.nan
    false_warn=100*good_flagged/wins if wins else np.nan
    print(
        f"{name:30s} | flagged={len(flagged):3d} | misses_caught={caught}/{total_losses} "
        f"| capture={capture:5.1f}% | good_flagged={good_flagged:3d} "
        f"| false_warn={false_warn:5.1f}% | kept={len(kept):3d} | kept_acc={kept_acc:5.1f}%"
    )

print()
print("=== WINNER VS LOSS SUMMARY ===")
for col in ["gain6","fair6","distance_giveback","pct_distance_giveback","fair_giveback",
            "first_50pct_giveback_min","first_fair_below_5pt_min"]:
    w=pd.to_numeric(d.loc[d.correct,col],errors="coerce").dropna()
    m=pd.to_numeric(d.loc[~d.correct,col],errors="coerce").dropna()
    print(
        f"{col:28s} | winners n={len(w):3d} med={w.median() if len(w) else np.nan:8.3f} "
        f"min={w.min() if len(w) else np.nan:8.3f} max={w.max() if len(w) else np.nan:8.3f} "
        f"| losses={list(m.round(6))}"
    )

print()
print("=== LOSING STRONGLY-CONFIRMED CALLS ===")
lossrows=d[~d.correct].copy()
if len(lossrows):
    print(lossrows.to_string(index=False))
else:
    print("None.")

# chronological last 40%
d = d.sort_values("ticker").reset_index(drop=True)
cut=int(len(d)*0.60)
hold=d.iloc[cut:].copy()
if len(hold):
    hwins=int(hold.correct.sum())
    hloss=int((~hold.correct).sum())
    print()
    print("=== CHRONOLOGICAL HOLDOUT: LAST 40% ===")
    print("Holdout calls:",len(hold),"| baseline accuracy:",f"{100*hold.correct.mean():.1f}%","| losses:",hloss)
    for name,_ in candidates:
        if name=="distance giveback >= $75":
            flag=hold["distance_giveback"]>=75
        elif name=="distance giveback >= $100":
            flag=hold["distance_giveback"]>=100
        elif name=="distance giveback >= $125":
            flag=hold["distance_giveback"]>=125
        elif name=="distance giveback >= 50%":
            flag=hold["pct_distance_giveback"]>=0.50
        elif name=="distance giveback >= 75%":
            flag=hold["pct_distance_giveback"]>=0.75
        elif name=="fair giveback >= 10pt":
            flag=hold["fair_giveback"]>=0.10
        elif name=="fair giveback >= 15pt":
            flag=hold["fair_giveback"]>=0.15
        elif name=="fair giveback >= 20pt":
            flag=hold["fair_giveback"]>=0.20
        else:
            flag=hold["first_50pct_giveback_min"].notna() | hold["first_fair_below_5pt_min"].notna()

        flagged=hold[flag]
        kept=hold[~flag]
        caught=int((~flagged.correct).sum())
        good=int(flagged.correct.sum())
        capture=100*caught/hloss if hloss else np.nan
        kept_acc=100*kept.correct.mean() if len(kept) else np.nan
        print(f"{name:30s} | flagged={len(flagged):2d} | caught={caught}/{hloss} | capture={capture:5.1f}% "
              f"| good_flagged={good:2d} | kept={len(kept):2d} | kept_acc={kept_acc:5.1f}%")

d.to_csv("kalshi_strong_confirmation_giveback_details.csv",index=False)
print()
print("Saved: kalshi_strong_confirmation_giveback_details.csv")
print("=== GIVEBACK VALIDATION COMPLETE ===")
print("Research only. No rule installed.")
