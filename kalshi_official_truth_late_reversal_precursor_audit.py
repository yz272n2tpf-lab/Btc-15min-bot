from pathlib import Path
import csv, math
import pandas as pd
import numpy as np

RESCORE = Path("kalshi_official_truth_layer_a_rescore_details.csv")
LIVE = Path("kalshi_live_fair_value_shadow_log.csv")
OUT = Path("kalshi_official_truth_late_reversal_precursor_audit.csv")
DETAILS = Path("kalshi_official_truth_late_reversal_precursor_details.csv")

print("=== KALSHI LATE-REVERSAL PRECURSOR AUDIT ===")
print("Purpose: find the earliest 3–5 minute warning that precedes the known <=1.5m late flip.")
print("Research only.")
print("No thresholds changed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")

def read_mixed_csv(path):
    try:
        return pd.read_csv(path, low_memory=False)
    except Exception:
        rows = []
        with open(path, "r", encoding="utf-8", errors="replace", newline="") as f:
            reader = csv.reader(f)
            header = next(reader)
            n = len(header)
            for r in reader:
                if len(r) < n:
                    r = r + [""] * (n-len(r))
                elif len(r) > n:
                    r = r[:n]
                rows.append(r)
        return pd.DataFrame(rows, columns=header)

def pick(cols, choices):
    for c in choices:
        if c in cols:
            return c
    return None

if not RESCORE.exists():
    raise SystemExit(f"Missing {RESCORE}")
if not LIVE.exists():
    raise SystemExit(f"Missing {LIVE}")

r = pd.read_csv(RESCORE, low_memory=False)
live = read_mixed_csv(LIVE)

# --- rescore columns ---
rticker = pick(r.columns, ["ticker","contract","market_ticker"])
rcorrect = pick(r.columns, ["correct","is_correct"])
rstate = pick(r.columns, ["layer_a_state","state","warning_state"])
rcallside = pick(r.columns, ["call_side","preferred_side"])
rtime = pick(r.columns, ["call_time","timestamp","ts"])
rfair = pick(r.columns, ["fair_pref_num","initial_fair","fair_preferred"])
rinitdist = pick(r.columns, ["initial_signed_distance","initial_distance","distance_target"])

need = [rticker, rcorrect, rstate]
if any(x is None for x in need):
    raise SystemExit("Could not identify required columns in rescore file.")

# Normalize CLEAN only
rr = r.copy()
rr[rcorrect] = rr[rcorrect].astype(str).str.lower().map(
    {"true":True,"false":False,"1":True,"0":False,"yes":True,"no":False}
).fillna(rr[rcorrect] if rr[rcorrect].dtype==bool else False)

if rstate:
    clean = rr[rr[rstate].astype(str).str.upper().str.contains("CLEAN", na=False)].copy()
else:
    clean = rr.copy()

print(f"\nCLEAN calls loaded: {len(clean)}")
print(f"Winners: {int(clean[rcorrect].sum())}")
print(f"Misses: {int((~clean[rcorrect]).sum())}")

# --- live columns ---
lticker = pick(live.columns, ["ticker","contract","market_ticker"])
lts = pick(live.columns, ["timestamp_utc","timestamp","time","datetime"])
lrem = pick(live.columns, ["remaining_min","time_left_min","remaining"])
ldist = pick(live.columns, ["distance_target","distance_from_target","distance","target_distance"])
lps = pick(live.columns, ["preferred_side","current_target_side","current_side"])
lfup = pick(live.columns, ["fair_up"])
lfdn = pick(live.columns, ["fair_down"])
lfpref = pick(live.columns, ["fair_preferred"])
luask = pick(live.columns, ["up_ask"])
ldask = pick(live.columns, ["down_ask"])
lpask = pick(live.columns, ["preferred_ask"])
lstatus = pick(live.columns, ["signal_status","status"])

if lticker is None or lts is None or lrem is None or ldist is None:
    raise SystemExit("Could not identify ticker/time/remaining/distance columns in live log.")

live[lts] = pd.to_datetime(live[lts], errors="coerce", utc=True)
live[lrem] = pd.to_numeric(live[lrem], errors="coerce")
live[ldist] = pd.to_numeric(live[ldist], errors="coerce")
for c in [lfup, lfdn, lfpref, luask, ldask, lpask]:
    if c is not None:
        live[c] = pd.to_numeric(live[c], errors="coerce")

# helper: transform raw distance/fair into the ORIGINAL CALL SIDE
def side_signed_distance(df, call_side):
    x = df[ldist].astype(float)
    return x if str(call_side).upper()=="UP" else -x

def call_fair(df, call_side):
    if str(call_side).upper()=="UP":
        if lfup: return df[lfup].astype(float)
    else:
        if lfdn: return df[lfdn].astype(float)
    if lfpref:
        return df[lfpref].astype(float)
    return pd.Series(np.nan, index=df.index)

def call_ask(df, call_side):
    if str(call_side).upper()=="UP":
        if luask: return df[luask].astype(float)
    else:
        if ldask: return df[ldask].astype(float)
    if lpask:
        return df[lpask].astype(float)
    return pd.Series(np.nan, index=df.index)

# snapshot nearest a remaining-minute target, tolerance in minutes
def snap_near(q, target_rem, tol=0.60):
    if q.empty:
        return None
    z = q.copy()
    z["_d"] = (z[lrem] - target_rem).abs()
    i = z["_d"].idxmin()
    if float(z.loc[i,"_d"]) > tol:
        return None
    return z.loc[i]

checkpoints = [5.0,4.5,4.0,3.5,3.0,2.5,2.0,1.5]
rows = []

for _, cr in clean.iterrows():
    ticker = str(cr[rticker])
    call_side = str(cr[rcallside]).upper() if rcallside else ""
    q = live[live[lticker].astype(str)==ticker].copy().sort_values(lts)
    if q.empty:
        continue

    # Keep only at/after call time if available
    if rtime and pd.notna(cr[rtime]):
        ct = pd.to_datetime(cr[rtime], errors="coerce", utc=True)
        if pd.notna(ct):
            q = q[q[lts] >= ct].copy()
    if q.empty:
        continue

    q["_signed"] = side_signed_distance(q, call_side)
    q["_fair_call"] = call_fair(q, call_side)
    q["_ask_call"] = call_ask(q, call_side)

    rec = {
        "ticker":ticker,
        "correct":bool(cr[rcorrect]),
        "call_side":call_side,
        "initial_fair":pd.to_numeric(cr[rfair], errors="coerce") if rfair else np.nan,
        "initial_signed_distance":pd.to_numeric(cr[rinitdist], errors="coerce") if rinitdist else np.nan,
    }

    for cp in checkpoints:
        s = snap_near(q, cp)
        tag = str(cp).replace(".","p")
        if s is None:
            rec[f"rem_{tag}"]=np.nan
            rec[f"dist_{tag}"]=np.nan
            rec[f"fair_{tag}"]=np.nan
            rec[f"ask_{tag}"]=np.nan
        else:
            rec[f"rem_{tag}"]=float(s[lrem])
            rec[f"dist_{tag}"]=float(s["_signed"]) if pd.notna(s["_signed"]) else np.nan
            rec[f"fair_{tag}"]=float(s["_fair_call"]) if pd.notna(s["_fair_call"]) else np.nan
            rec[f"ask_{tag}"]=float(s["_ask_call"]) if pd.notna(s["_ask_call"]) else np.nan

    # derived precursor changes
    def val(kind, cp):
        return rec.get(f"{kind}_{str(cp).replace('.','p')}", np.nan)

    for a,b in [(5.0,4.0),(4.5,3.5),(4.0,3.0),(3.5,2.5),(3.0,2.0),(2.5,1.5)]:
        rec[f"dist_change_{a}_{b}"] = val("dist",b)-val("dist",a) if pd.notna(val("dist",a)) and pd.notna(val("dist",b)) else np.nan
        rec[f"fair_change_{a}_{b}"] = val("fair",b)-val("fair",a) if pd.notna(val("fair",a)) and pd.notna(val("fair",b)) else np.nan
        rec[f"ask_change_{a}_{b}"] = val("ask",b)-val("ask",a) if pd.notna(val("ask",a)) and pd.notna(val("ask",b)) else np.nan

    # minimum support seen from 5m through 2m
    w = q[(q[lrem] <= 5.4) & (q[lrem] >= 1.8)]
    rec["min_signed_distance_5to2"] = float(w["_signed"].min()) if len(w) else np.nan
    rec["min_fair_5to2"] = float(w["_fair_call"].min()) if len(w) else np.nan

    rows.append(rec)

d = pd.DataFrame(rows)
d.to_csv(DETAILS, index=False)

print(f"\nUsable CLEAN calls: {len(d)}")
print(f"Usable winners: {int(d.correct.sum())}")
print(f"Usable misses: {int((~d.correct).sum())}")

miss = d[~d.correct].copy()
win = d[d.correct].copy()

print("\n=== CLEAN MISS PRECURSOR PROFILES ===")
show_cols = ["ticker","call_side","initial_fair","initial_signed_distance",
             "dist_5p0","dist_4p0","dist_3p0","dist_2p0",
             "fair_5p0","fair_4p0","fair_3p0","fair_2p0",
             "dist_change_4.0_3.0","fair_change_4.0_3.0",
             "dist_change_3.0_2.0","fair_change_3.0_2.0",
             "min_signed_distance_5to2","min_fair_5to2"]
print(miss[[c for c in show_cols if c in miss.columns]].to_string(index=False))

# Pre-specified diagnostic grid: EARLY precursor only (3–5m area)
cands = []

def score_rule(name, mask):
    mask = mask.fillna(False)
    flagged = int(mask.sum())
    misses_caught = int((mask & (~d.correct)).sum())
    total_misses = int((~d.correct).sum())
    good_flagged = int((mask & d.correct).sum())
    kept = int((~mask).sum())
    kept_correct = int(((~mask) & d.correct).sum())
    kept_acc = kept_correct/kept if kept else np.nan
    capture = misses_caught/total_misses if total_misses else np.nan
    false_warn = good_flagged/int(d.correct.sum()) if int(d.correct.sum()) else np.nan
    cands.append({
        "rule":name,"flagged":flagged,"misses_caught":misses_caught,
        "total_misses":total_misses,"good_flagged":good_flagged,
        "false_warn":false_warn,"kept":kept,"kept_accuracy":kept_acc,"capture":capture
    })

# Single-point weakness at 3–5m
for cp in [5.0,4.5,4.0,3.5,3.0]:
    tag=str(cp).replace(".","p")
    for th in [100,75,50,25,0,-25]:
        score_rule(f"{cp}m signed_distance <= ${th}", d[f"dist_{tag}"] <= th)
    for th in [0.80,0.70,0.60,0.50,0.40]:
        score_rule(f"{cp}m call_fair <= {th:.2f}", d[f"fair_{tag}"] <= th)

# Deterioration over one-minute windows before 3m
for a,b in [(5.0,4.0),(4.5,3.5),(4.0,3.0),(3.5,2.5)]:
    dc = d[f"dist_change_{a}_{b}"]
    fc = d[f"fair_change_{a}_{b}"]
    for th in [-25,-50,-75,-100]:
        score_rule(f"distance change {a}->{b}m <= {th}", dc <= th)
    for th in [-0.05,-0.10,-0.15,-0.20]:
        score_rule(f"fair change {a}->{b}m <= {th:.2f}", fc <= th)

# Combined precursor patterns, still diagnostic only
score_rule("3m distance <= $25 AND 3m fair <= 0.60",
           (d["dist_3p0"] <= 25) & (d["fair_3p0"] <= 0.60))
score_rule("4->3m distance drop >= $50 OR fair drop >= 10pt",
           (d["dist_change_4.0_3.0"] <= -50) | (d["fair_change_4.0_3.0"] <= -0.10))
score_rule("min 5to2 distance < 0",
           d["min_signed_distance_5to2"] < 0)
score_rule("min 5to2 fair < 0.50",
           d["min_fair_5to2"] < 0.50)

res = pd.DataFrame(cands)
# rank: capture first, then low false warning, then high kept accuracy
res = res.sort_values(["capture","false_warn","kept_accuracy","flagged"],
                      ascending=[False,True,False,True]).reset_index(drop=True)

print("\n=== TOP PRECURSOR DIAGNOSTICS ===")
print(res.head(25).to_string(index=False, float_format=lambda x:f"{x:.3f}"))

# chronological holdout: last 40% of usable clean calls, preserving file order if call_time exists
if rtime and rtime in clean.columns:
    # map call time into d
    m = clean[[rticker,rtime]].copy()
    m.columns=["ticker","_call_time"]
    d2=d.merge(m,on="ticker",how="left")
    d2["_call_time"]=pd.to_datetime(d2["_call_time"],errors="coerce",utc=True)
    d2=d2.sort_values("_call_time")
else:
    d2=d.copy()

cut=max(1,int(math.floor(len(d2)*0.60)))
hold=d2.iloc[cut:].copy()

print(f"\n=== CHRONOLOGICAL HOLDOUT: LAST 40% ===")
print(f"Holdout CLEAN calls: {len(hold)} | winners={int(hold.correct.sum())} | misses={int((~hold.correct).sum())}")

# re-score only top 10 rule names on holdout using parser
def apply_named_rule(df, name):
    try:
        if "signed_distance <= $" in name:
            cp=float(name.split("m ")[0]); th=float(name.split("$")[1])
            return df[f"dist_{str(cp).replace('.','p')}"] <= th
        if "call_fair <=" in name:
            cp=float(name.split("m ")[0]); th=float(name.rsplit(" ",1)[1])
            return df[f"fair_{str(cp).replace('.','p')}"] <= th
        if name.startswith("distance change"):
            seg=name.split()[2]; a,b=map(float,seg.replace("m","").split("->"))
            th=float(name.rsplit(" ",1)[1])
            return df[f"dist_change_{a}_{b}"] <= th
        if name.startswith("fair change"):
            seg=name.split()[2]; a,b=map(float,seg.replace("m","").split("->"))
            th=float(name.rsplit(" ",1)[1])
            return df[f"fair_change_{a}_{b}"] <= th
        if name=="3m distance <= $25 AND 3m fair <= 0.60":
            return (df["dist_3p0"]<=25)&(df["fair_3p0"]<=0.60)
        if name=="4->3m distance drop >= $50 OR fair drop >= 10pt":
            return (df["dist_change_4.0_3.0"]<=-50)|(df["fair_change_4.0_3.0"]<=-0.10)
        if name=="min 5to2 distance < 0":
            return df["min_signed_distance_5to2"]<0
        if name=="min 5to2 fair < 0.50":
            return df["min_fair_5to2"]<0.50
    except Exception:
        pass
    return pd.Series(False,index=df.index)

for name in res.head(10)["rule"]:
    mask=apply_named_rule(hold,name).fillna(False)
    tm=int((~hold.correct).sum())
    caught=int((mask & (~hold.correct)).sum())
    good=int((mask & hold.correct).sum())
    kept=int((~mask).sum())
    keptcorr=int(((~mask)&hold.correct).sum())
    acc=keptcorr/kept if kept else np.nan
    print(f"{name:55s} | flagged={int(mask.sum()):2d} | caught={caught}/{tm} | good_flagged={good:2d} | kept={kept:2d} | kept_acc={acc:.1%}")

res.to_csv(OUT,index=False)
print(f"\nSaved: {OUT}")
print(f"Saved: {DETAILS}")
print("=== PRECURSOR AUDIT COMPLETE ===")
print("Research only. No rule installed.")
