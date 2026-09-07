
import warnings
from pathlib import Path
import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

SIGNALS = Path("kalshi_true_scalp_forward_shadow_v1.csv")
SNAPS = Path("kalshi_scalp_shadow_snapshots_v1.csv")
UNIFIED = Path("kalshi_subminute_unified_v1_1.csv")

OUT_GRID = Path("scalp_exit_optimizer_v1_grid.csv")
OUT_TRADES = Path("scalp_exit_optimizer_v1_winner_trades.csv")

def bval(v):
    return str(v).strip().lower() in ("true","1","yes")

def find_col(df, names):
    for n in names:
        if n in df.columns:
            return n
    return None

def pct(x):
    return f"{x:.1f}%"

print("="*74)
print("TRUE SCALP EXIT / PROFIT-PROTECTION OPTIMIZER V1")
print("="*74)

if not SIGNALS.exists():
    raise SystemExit("ERROR: kalshi_true_scalp_forward_shadow_v1.csv missing")
if not SNAPS.exists():
    raise SystemExit("ERROR: kalshi_scalp_shadow_snapshots_v1.csv missing")

sig = pd.read_csv(SIGNALS)
sn = pd.read_csv(SNAPS)

sig_ts_col = find_col(sig, ["signal_timestamp_utc","entry_timestamp_utc","timestamp_utc"])
sn_ts_col = find_col(sn, ["timestamp_utc","ts_utc","timestamp"])
contract_col = find_col(sn, ["contract","ticker"])
seconds_col = find_col(sn, ["seconds_left","time_left_seconds"])

if not sig_ts_col or not sn_ts_col or not contract_col:
    raise SystemExit(
        "ERROR: Could not identify timestamp/contract columns in scalp files."
    )

sig[sig_ts_col] = pd.to_datetime(sig[sig_ts_col], errors="coerce", utc=True)
sn[sn_ts_col] = pd.to_datetime(sn[sn_ts_col], errors="coerce", utc=True)

# Optional synchronized features.
u = None
if UNIFIED.exists():
    try:
        u = pd.read_csv(UNIFIED)
        if "timestamp_utc" in u:
            u["timestamp_utc"] = pd.to_datetime(
                u["timestamp_utc"], errors="coerce", utc=True
            )
    except Exception:
        u = None

def side_bid_col(side):
    side = side.lower()
    return find_col(sn, [
        f"{side}_bid", f"{side}_best_bid", f"{side}_bid_price"
    ])

def enrich_feature_rows(path, contract, side):
    if u is None or path.empty:
        path = path.copy()
        path["_reversal"] = ""
        path["_brti_agree"] = np.nan
        return path

    uu = u[
        (u["contract"].astype(str) == str(contract))
        & (u["side"].astype(str).str.upper() == str(side).upper())
    ].copy()

    if uu.empty:
        path = path.copy()
        path["_reversal"] = ""
        path["_brti_agree"] = np.nan
        return path

    cols = ["timestamp_utc"]
    if "reversal_state" in uu:
        cols.append("reversal_state")
    if "brti_agrees_side" in uu:
        cols.append("brti_agrees_side")

    uu = uu[cols].sort_values("timestamp_utc")
    p = path.sort_values(sn_ts_col).copy()

    merged = pd.merge_asof(
        p,
        uu,
        left_on=sn_ts_col,
        right_on="timestamp_utc",
        direction="nearest",
        tolerance=pd.Timedelta(seconds=4),
    )
    merged["_reversal"] = (
        merged["reversal_state"].fillna("").astype(str)
        if "reversal_state" in merged else ""
    )
    if "brti_agrees_side" in merged:
        merged["_brti_agree"] = merged["brti_agrees_side"].map(
            lambda x: np.nan if pd.isna(x) else bval(x)
        )
    else:
        merged["_brti_agree"] = np.nan
    return merged

trades = []
for i, r in sig.sort_values(sig_ts_col).reset_index(drop=True).iterrows():
    contract = str(r["contract"])
    side = str(r["side"]).upper()
    entry_ts = r[sig_ts_col]
    entry_ask = float(r["entry_ask"])

    bid_col = side_bid_col(side)
    if not bid_col:
        raise SystemExit(f"ERROR: No {side} bid column found in snapshot file.")

    end_ts = entry_ts + pd.Timedelta(seconds=180)
    p = sn[
        (sn[contract_col].astype(str) == contract)
        & (sn[sn_ts_col] >= entry_ts)
        & (sn[sn_ts_col] <= end_ts)
    ][[sn_ts_col,bid_col] + ([seconds_col] if seconds_col else [])].copy()

    p[bid_col] = pd.to_numeric(p[bid_col], errors="coerce")
    p = p.dropna(subset=[sn_ts_col,bid_col]).sort_values(sn_ts_col)

    if p.empty:
        continue

    p = enrich_feature_rows(p, contract, side)
    p["elapsed"] = (p[sn_ts_col] - entry_ts).dt.total_seconds()
    p["profit"] = p[bid_col] - entry_ask

    trades.append({
        "trade_index": i,
        "contract": contract,
        "side": side,
        "entry_ts": entry_ts,
        "entry_ask": entry_ask,
        "path": p,
        "bid_col": bid_col,
    })

print(f"FRESH SIGNALS IN LOG: {len(sig)}")
print(f"RECONSTRUCTED 5s TRADE PATHS: {len(trades)}")

if len(trades) < 10:
    raise SystemExit(
        "STOP: fewer than 10 complete trade paths. "
        "Do not optimize exit logic from an insufficient sample."
    )

# Chronological development / untouched split for EXIT logic.
n = len(trades)
split = max(8, int(round(n * 0.65)))
split = min(split, n - 5)
dev = trades[:split]
hold = trades[split:]

print(f"EXIT DEVELOPMENT TRADES: {len(dev)}")
print(f"EXIT UNTOUCHED TRADES: {len(hold)}")
print("NOTE: these 17 fresh entries now become development/holdout data for EXIT logic.")
print("-"*74)

def simulate(t, target_c, floor_c, trail_c, feature_mode):
    p = t["path"]
    bid_col = t["bid_col"]
    e = t["entry_ask"]

    reached10 = False
    peak = -999.0
    t10 = None

    exit_bid = float(p.iloc[-1][bid_col])
    exit_elapsed = float(p.iloc[-1]["elapsed"])
    reason = "HORIZON"

    for _, row in p.iterrows():
        bid = float(row[bid_col])
        profit = bid - e
        elapsed = float(row["elapsed"])

        if not reached10:
            if profit >= 0.10:
                reached10 = True
                t10 = elapsed
                peak = profit
            else:
                continue

        peak = max(peak, profit)

        # Desired upside target.
        if profit >= target_c:
            exit_bid = bid
            exit_elapsed = elapsed
            reason = f"TARGET_{int(target_c*100)}"
            break

        # Dynamic profit floor / trailing protection.
        protect_level = max(floor_c, peak - trail_c)
        feature_exit = False

        if feature_mode in ("REVERSAL","EITHER"):
            rev = str(row.get("_reversal","")).upper()
            if rev in ("AGAINST","REVERSAL_WARN"):
                feature_exit = True

        if feature_mode in ("BRTI","EITHER"):
            agree = row.get("_brti_agree", np.nan)
            if agree is False:
                feature_exit = True

        if profit <= protect_level:
            exit_bid = bid
            exit_elapsed = elapsed
            reason = "TRAIL_PROTECT"
            break

        # Feature-based exits only after at least +10c has been achieved,
        # and only if we still retain at least the chosen floor.
        if feature_exit and profit >= floor_c:
            exit_bid = bid
            exit_elapsed = elapsed
            reason = f"FEATURE_{feature_mode}"
            break

    profit_c = exit_bid - e
    roi = profit_c / e if e > 0 else np.nan

    max_profit = float(p["profit"].max())
    capture = (
        profit_c / max_profit
        if max_profit > 0 else np.nan
    )

    return {
        "contract": t["contract"],
        "side": t["side"],
        "entry_ask": e,
        "exit_bid": exit_bid,
        "profit_c": profit_c,
        "roi": roi,
        "exit_elapsed": exit_elapsed,
        "reason": reason,
        "max_profit": max_profit,
        "capture": capture,
        "hit_18pct_roi": bool(roi >= 0.18) if np.isfinite(roi) else False,
        "held_profit_positive": bool(profit_c > 0),
        "t10": t10,
    }

def score(rows):
    x = pd.DataFrame(rows)
    return {
        "n": len(x),
        "roi18": 100*x["hit_18pct_roi"].mean(),
        "positive": 100*x["held_profit_positive"].mean(),
        "avg_profit_c": 100*x["profit_c"].mean(),
        "median_profit_c": 100*x["profit_c"].median(),
        "avg_roi": 100*x["roi"].mean(),
        "median_roi": 100*x["roi"].median(),
        "avg_capture": 100*x["capture"].replace([np.inf,-np.inf],np.nan).dropna().mean(),
        "avg_exit_sec": x["exit_elapsed"].mean(),
        "worst_profit_c": 100*x["profit_c"].min(),
    }

def fmt(m):
    return (
        f"18%+ ROI {m['roi18']:.1f}% | avg +{m['avg_profit_c']:.1f}c "
        f"({m['avg_roi']:.1f}% ROI) | median +{m['median_profit_c']:.1f}c | "
        f"capture {m['avg_capture']:.1f}% | worst {m['worst_profit_c']:+.1f}c"
    )

# Baseline: bank the first executable +10c.
def baseline10(t):
    p=t["path"]; bid_col=t["bid_col"]; e=t["entry_ask"]
    hit=p[p["profit"]>=0.10]
    if hit.empty:
        row=p.iloc[-1]; reason="HORIZON"
    else:
        row=hit.iloc[0]; reason="BANK_10"
    exit_bid=float(row[bid_col])
    profit_c=exit_bid-e
    roi=profit_c/e
    max_profit=float(p["profit"].max())
    return {
        "contract":t["contract"],"side":t["side"],"entry_ask":e,
        "exit_bid":exit_bid,"profit_c":profit_c,"roi":roi,
        "exit_elapsed":float(row["elapsed"]),"reason":reason,
        "max_profit":max_profit,
        "capture":profit_c/max_profit if max_profit>0 else np.nan,
        "hit_18pct_roi":bool(roi>=.18),"held_profit_positive":bool(profit_c>0),
        "t10":float(row["elapsed"]) if reason=="BANK_10" else None,
    }

dev_base=score([baseline10(t) for t in dev])
hold_base=score([baseline10(t) for t in hold])
print("BASELINE — BANK +10c IMMEDIATELY")
print(f"  DEVELOPMENT: {fmt(dev_base)}")
print(f"  UNTOUCHED:   {fmt(hold_base)}")
print("-"*74)

configs=[]
for target in [0.15,0.20]:
    for floor in [0.06,0.08,0.10]:
        for trail in [0.04,0.06,0.08,0.10]:
            for feature in ["NONE","REVERSAL","BRTI","EITHER"]:
                # Avoid impossible/redundant relationship.
                if floor >= target:
                    continue
                name=(
                    f"T{int(target*100)}_F{int(floor*100)}_"
                    f"TR{int(trail*100)}_{feature}"
                )
                configs.append((name,target,floor,trail,feature))

grid=[]
for name,target,floor,trail,feature in configs:
    dr=[simulate(t,target,floor,trail,feature) for t in dev]
    dm=score(dr)
    grid.append({
        "config":name,"target":target,"floor":floor,"trail":trail,
        "feature":feature,
        "dev_roi18":dm["roi18"],"dev_positive":dm["positive"],
        "dev_avg_profit_c":dm["avg_profit_c"],
        "dev_avg_roi":dm["avg_roi"],
        "dev_avg_capture":dm["avg_capture"],
        "dev_worst_profit_c":dm["worst_profit_c"],
    })

g=pd.DataFrame(grid)

# Conservative selection:
# 1) Must preserve the user's 18%+ ROI standard on >=90% of dev trades.
# 2) Must remain positive on all dev trades.
# 3) Prefer higher average cents, then capture, then simpler feature mode.
eligible=g[
    (g["dev_roi18"]>=90.0)
    & (g["dev_positive"]>=100.0)
].copy()

if eligible.empty:
    print("SCREEN RESULT: NO EXIT POLICY BEAT THE SAFETY BAR.")
    print("Keep +10c bank as the reference while more paths accumulate.")
    g.to_csv(OUT_GRID,index=False)
    raise SystemExit(0)

eligible["simplicity"] = eligible["feature"].map(
    {"NONE":3,"REVERSAL":2,"BRTI":2,"EITHER":1}
)
eligible=eligible.sort_values(
    ["dev_avg_profit_c","dev_avg_capture","simplicity"],
    ascending=[False,False,False]
)
w=eligible.iloc[0]

name=w["config"]
target=float(w["target"]); floor=float(w["floor"]); trail=float(w["trail"])
feature=str(w["feature"])

dev_rows=[simulate(t,target,floor,trail,feature) for t in dev]
hold_rows=[simulate(t,target,floor,trail,feature) for t in hold]
all_rows=[simulate(t,target,floor,trail,feature) for t in trades]

dm=score(dev_rows); hm=score(hold_rows); am=score(all_rows)

g.to_csv(OUT_GRID,index=False)
pd.DataFrame(all_rows).to_csv(OUT_TRADES,index=False)

print("DEVELOPMENT-SELECTED EXIT CANDIDATE")
print(f"  {name}")
print(f"  DEVELOPMENT: {fmt(dm)}")
print(f"  UNTOUCHED:   {fmt(hm)}")
print(f"  ALL 17 (descriptive): {fmt(am)}")
print("-"*74)

# Compare untouched candidate to untouched +10 baseline.
delta_profit = hm["avg_profit_c"] - hold_base["avg_profit_c"]
delta_roi = hm["avg_roi"] - hold_base["avg_roi"]

print("UNTOUCHED COMPARISON VS BANKING +10c")
print(f"  Extra average profit: {delta_profit:+.1f}c")
print(f"  Extra average ROI:    {delta_roi:+.1f} percentage points")
print(f"  18%+ ROI rate:        {hm['roi18']:.1f}%")
print(f"  Positive exits:       {hm['positive']:.1f}%")
print(f"  Worst exit profit:    {hm['worst_profit_c']:+.1f}c")
print("-"*74)

if (
    hm["n"] >= 5
    and hm["roi18"] >= 80.0
    and hm["positive"] >= 100.0
    and hm["avg_profit_c"] >= hold_base["avg_profit_c"]
):
    print("SCREEN RESULT: PROMISING PROFIT-PROTECTION CANDIDATE")
    print("NEXT: freeze it as SHADOW ONLY and forward-test it live.")
else:
    print("SCREEN RESULT: DO NOT PROMOTE EXIT CANDIDATE YET")
    print("Keep +10c as the safe checkpoint; gather more paths naturally.")

print(f"Saved grid: {OUT_GRID}")
print(f"Saved trades: {OUT_TRADES}")
print("="*74)
