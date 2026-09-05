
import base64, time, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import requests

from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

warnings.filterwarnings("ignore")

UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")
SCALP = Path("kalshi_true_scalp_forward_shadow_v1.csv")

OUT_CONTRACTS = Path("union_coverage_gap_audit_v1_contracts.csv")
OUT_GAPS = Path("union_coverage_gap_audit_v1_gaps.csv")

KALSHI_BASE_URL = "https://api.elections.kalshi.com"
KEY_ID_PATH = Path.home() / ".kalshi" / "key_id"
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"

def truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def num(df,c):
    if c not in df.columns:
        df[c]=np.nan
    df[c]=pd.to_numeric(df[c],errors="coerce")

if not UNIFIED.exists():
    raise SystemExit("ERROR: unified log missing")
if not SCALP.exists():
    raise SystemExit("ERROR: primary scalp forward log missing")
if not (KEY_ID_PATH.exists() and PRIVATE_KEY_PATH.exists()):
    raise SystemExit("ERROR: Kalshi credentials missing")

KEY_ID=KEY_ID_PATH.read_text().strip()
PRIVATE_KEY=serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(), password=None
)

def headers(method,path):
    ts=str(int(time.time()*1000))
    msg=ts+method.upper()+path
    sig=PRIVATE_KEY.sign(
        msg.encode(),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY":KEY_ID,
        "KALSHI-ACCESS-SIGNATURE":base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP":ts,
    }

def official_side(ticker):
    path=f"/trade-api/v2/markets/{ticker}"
    try:
        r=requests.get(
            KALSHI_BASE_URL+path,
            headers=headers("GET",path),
            timeout=12,
        )
        r.raise_for_status()
        m=r.json().get("market",{})
    except Exception:
        return None

    for k in ("result","settlement_result","settled_result"):
        v=str(m.get(k) or "").strip().lower()
        if v=="yes":
            return "UP"
        if v=="no":
            return "DOWN"
    return None

print("="*82)
print("BTC15 UNION COVERAGE + GAP AUDIT V1")
print("="*82)

u=pd.read_csv(UNIFIED)
u["timestamp_utc"]=pd.to_datetime(
    u["timestamp_utc"],errors="coerce",utc=True
)

for c in [
    "minutes_left","side_ask","side_bid","preferred_fair",
    "abs_btc_gap","dist_over_range5","brti_age_seconds",
    "brti_gap_to_target","side_edge","btc_gap",
]:
    num(u,c)

u["brti_ready_b"]=u["brti_ready"].map(truthy)
u["brti_agrees_b"]=u["brti_agrees_side"].map(truthy)

contracts=(
    u.groupby("contract")["timestamp_utc"]
     .min().sort_values().index.tolist()
)

print(f"UNIFIED CONTRACTS: {len(contracts)}")

labels={}
for t in contracts:
    labels[t]=official_side(t)
    time.sleep(.05)

settled=[t for t in contracts if labels.get(t) in ("UP","DOWN")]
print(f"OFFICIAL SETTLED: {len(settled)}")

u=u[u["contract"].isin(settled)].copy()
u["official_side"]=u["contract"].map(labels)

# ------------------------------------------------------------------
# Reconstruct the locked FINAL gate on these same 5-second rows.
#
# Exact frozen logic:
#   fair >= 90%
#   <= 8m left
#   if >6m: abs BTC gap >= $75
#   if <=6m: abs BTC gap >= $50
#   dist/range5 >= 1.0
#   preferred fair side agrees with current target side
#   direct BRTI fresh <=5s
#   direct BRTI outside +/-$11 wait zone
#   direct BRTI side agrees with preferred fair side
# ------------------------------------------------------------------

final_rows=u[
    u["preferred_fair_side"].isin(["UP","DOWN"])
    & (u["side"]==u["preferred_fair_side"])
].copy()

final_rows["required_gap"]=np.where(
    final_rows["minutes_left"]>6.0,75.0,50.0
)

final_rows["final_ready"]=(
    final_rows["minutes_left"].between(0.0,8.0,inclusive="both")
    & (final_rows["preferred_fair"]>=.90)
    & (final_rows["abs_btc_gap"]>=final_rows["required_gap"])
    & (final_rows["dist_over_range5"]>=1.0)
    & (
        final_rows["preferred_fair_side"]
        == final_rows["current_target_side"]
    )
    & final_rows["brti_ready_b"]
    & (final_rows["brti_age_seconds"]<=5.0)
    & (final_rows["brti_gap_to_target"].abs()>11.0)
    & (
        final_rows["brti_side"]
        == final_rows["preferred_fair_side"]
    )
)

f=final_rows[final_rows["final_ready"]].copy()

# First qualifying FINAL per contract = earliest in real time,
# equivalently greatest time-left among qualifying rows.
f=f.sort_values(
    ["contract","timestamp_utc"],
    ascending=[True,True]
)
f_first=f.groupby("contract",as_index=False).head(1).copy()

f_first["final_correct"]=(
    f_first["preferred_fair_side"]==f_first["official_side"]
)

final_contracts=set(f_first["contract"].astype(str))

# ------------------------------------------------------------------
# Primary scalp signal stats / coverage.
# ------------------------------------------------------------------
s=pd.read_csv(SCALP)
s=s[s["contract"].astype(str).isin(settled)].copy()

if "result_10c_before_stop" in s.columns:
    s["scalp_win"]=s["result_10c_before_stop"].map(truthy)
else:
    s["scalp_win"]=False

s["entry_ask"]=pd.to_numeric(s["entry_ask"],errors="coerce")
s["minutes_left"]=pd.to_numeric(s["minutes_left"],errors="coerce")

scalp_contracts=set(s["contract"].astype(str))

# ------------------------------------------------------------------
# Contract-level union table.
# ------------------------------------------------------------------
rows=[]
for t in settled:
    cu=u[u["contract"]==t].copy()
    cf=f_first[f_first["contract"]==t]
    cs=s[s["contract"].astype(str)==str(t)]

    has_final=len(cf)>0
    has_scalp=len(cs)>0

    # Gap diagnostics from the full contract.
    pref=cu[
        cu["preferred_fair_side"].isin(["UP","DOWN"])
        & (cu["side"]==cu["preferred_fair_side"])
    ].copy()

    early=pref[pref["minutes_left"].between(4.0,10.0,inclusive="both")]

    max_fair=(
        float(early["preferred_fair"].max())
        if len(early) else np.nan
    )
    max_gap=(
        float(early["abs_btc_gap"].max())
        if len(early) else np.nan
    )
    min_ask=(
        float(early["side_ask"].min())
        if len(early) else np.nan
    )
    brti_agree_frac=(
        float(early["brti_agrees_b"].mean())
        if len(early) else np.nan
    )

    rev=early["reversal_state"].fillna("").astype(str).str.upper()
    chop_frac=(
        float(
            rev.isin(
                ["MIXED","AGAINST","REVERSAL_WARN","PULLBACK"]
            ).mean()
        )
        if len(early) else np.nan
    )

    rows.append({
        "contract":t,
        "official_side":labels.get(t),
        "final_call":has_final,
        "final_side":(
            cf.iloc[0]["preferred_fair_side"]
            if has_final else None
        ),
        "final_correct":(
            bool(cf.iloc[0]["final_correct"])
            if has_final else None
        ),
        "final_time_left":(
            float(cf.iloc[0]["minutes_left"])
            if has_final else None
        ),
        "scalp_signal":has_scalp,
        "scalp_signals":len(cs),
        "scalp_wins":(
            int(cs["scalp_win"].sum())
            if has_scalp else 0
        ),
        "scalp_all_won":(
            bool(cs["scalp_win"].all())
            if has_scalp else None
        ),
        "scalp_avg_entry_c":(
            float(cs["entry_ask"].mean()*100)
            if has_scalp else None
        ),
        "scalp_avg_time_left":(
            float(cs["minutes_left"].mean())
            if has_scalp else None
        ),
        "union_actionable":bool(has_final or has_scalp),
        "max_early_fair":max_fair,
        "max_early_abs_gap":max_gap,
        "min_early_ask":min_ask,
        "brti_agree_fraction":brti_agree_frac,
        "chop_fraction":chop_frac,
    })

audit=pd.DataFrame(rows)

# Gap taxonomy is descriptive only.
def classify_gap(r):
    if r["union_actionable"]:
        return ""

    fair=r["max_early_fair"]
    gap=r["max_early_abs_gap"]
    ask=r["min_early_ask"]
    brti=r["brti_agree_fraction"]
    chop=r["chop_fraction"]

    if np.isfinite(chop) and chop>=.55:
        return "CHOP / REVERSAL-HEAVY"
    if np.isfinite(gap) and gap<50:
        return "NEAR TARGET / SIDEWAYS"
    if np.isfinite(fair) and fair<.75:
        return "WEAK DIRECTIONAL EVIDENCE"
    if np.isfinite(brti) and brti<.60:
        return "BRTI / DIRECTION INSTABILITY"
    if np.isfinite(ask) and ask>.45:
        return "NO CHEAP ENTRY"
    return "MIXED / UNCLASSIFIED"

audit["gap_type"]=audit.apply(classify_gap,axis=1)

n=len(audit)
final_n=int(audit["final_call"].sum())
scalp_n=int(audit["scalp_signal"].sum())
union_n=int(audit["union_actionable"].sum())
both_n=int((audit["final_call"] & audit["scalp_signal"]).sum())
final_only=int((audit["final_call"] & ~audit["scalp_signal"]).sum())
scalp_only=int((~audit["final_call"] & audit["scalp_signal"]).sum())
neither=int((~audit["final_call"] & ~audit["scalp_signal"]).sum())

print("-"*82)
print("SAME-CONTRACT MODULE SCORECARD")

if final_n:
    fc=audit[audit["final_call"]]
    print(
        f"FINAL: {int(fc['final_correct'].sum())}/{final_n} = "
        f"{fc['final_correct'].mean()*100:.1f}% | "
        f"{final_n}/{n} contracts = {final_n/n*100:.1f}% coverage | "
        f"avg {fc['final_time_left'].mean():.2f}m left"
    )
else:
    print("FINAL: 0 calls on this dataset")

if len(s):
    print(
        f"PRIMARY SCALP: {int(s['scalp_win'].sum())}/{len(s)} = "
        f"{s['scalp_win'].mean()*100:.1f}% signals | "
        f"{scalp_n}/{n} contracts = {scalp_n/n*100:.1f}% coverage | "
        f"avg entry {s['entry_ask'].mean()*100:.1f}c | "
        f"avg {s['minutes_left'].mean():.2f}m left"
    )

print("-"*82)
print("UNION ACTIONABLE COVERAGE")
print(f"BOTH FINAL + SCALP: {both_n}")
print(f"FINAL ONLY:         {final_only}")
print(f"SCALP ONLY:         {scalp_only}")
print(f"NEITHER:            {neither}")
print(
    f"UNION COVERAGE:     {union_n}/{n} = "
    f"{union_n/n*100:.1f}%"
)

print("-"*82)
print("UNCOVERED CONTRACT GAP TYPES")

gaps=audit[~audit["union_actionable"]].copy()
if gaps.empty:
    print("NONE — FINAL + PRIMARY SCALP covered every settled contract.")
else:
    counts=gaps["gap_type"].value_counts()
    for k,v in counts.items():
        print(f"{k}: {v}")

    print("\nUNCOVERED CONTRACTS:")
    for _,r in gaps.iterrows():
        fair_txt = (
            "NA" if pd.isna(r["max_early_fair"])
            else f"{r['max_early_fair']*100:.0f}%"
        )
        gap_txt = (
            "NA" if pd.isna(r["max_early_abs_gap"])
            else f"${r['max_early_abs_gap']:.0f}"
        )
        ask_txt = (
            "NA" if pd.isna(r["min_early_ask"])
            else f"{r['min_early_ask']*100:.0f}c"
        )
        print(
            f"  {r['contract']} | {r['gap_type']} | "
            f"max fair {fair_txt} | max gap {gap_txt} | min ask {ask_txt}"
        )

audit.to_csv(OUT_CONTRACTS,index=False)
gaps.to_csv(OUT_GAPS,index=False)

print("="*82)

if union_n/n >= .90:
    print("DIRECTION: UNION COVERAGE IS ALREADY >=90% ON THIS SAMPLE.")
    print("Focus next on robustness/parity, not inventing more signal paths.")
elif union_n/n >= .75:
    print("DIRECTION: UNION COVERAGE IS STRONG BUT GAPS REMAIN.")
    print("Use the gap taxonomy above to choose ONE targeted next path.")
else:
    print("DIRECTION: UNION COVERAGE STILL NEEDS A MATERIAL GAP-FILL PATH.")
    print("Choose the next path from the dominant uncovered regime, not by guesswork.")

print(f"Saved contract audit: {OUT_CONTRACTS}")
print(f"Saved gap audit: {OUT_GAPS}")
print("="*82)
