
import base64, time, itertools, warnings
from pathlib import Path
from datetime import datetime
import requests
import numpy as np
import pandas as pd
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

warnings.filterwarnings("ignore")

DATA = Path("kalshi_subminute_unified_v1_1.csv")
OUT_GRID = Path("unified_early_screen_v1_grid.csv")
OUT_SIGNALS = Path("unified_early_screen_v1_winner_signals.csv")

KALSHI_BASE_URL = "https://api.elections.kalshi.com"
KEY_ID_PATH = Path.home() / ".kalshi" / "key_id"
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"

def truthy_series(s):
    return s.astype(str).str.strip().str.lower().isin(["true","1","yes"])

def auth_ready():
    return KEY_ID_PATH.exists() and PRIVATE_KEY_PATH.exists()

if not DATA.exists():
    raise SystemExit("ERROR: kalshi_subminute_unified_v1_1.csv not found")

if not auth_ready():
    raise SystemExit("ERROR: Kalshi API credentials not found in ~/.kalshi")

KEY_ID = KEY_ID_PATH.read_text().strip()
PRIVATE_KEY = serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(), password=None
)

def kalshi_headers(method, path):
    ts = str(int(time.time() * 1000))
    msg = ts + method.upper() + path
    sig = PRIVATE_KEY.sign(
        msg.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }

def kalshi_get(path, params=None):
    r = requests.get(
        KALSHI_BASE_URL + path,
        headers=kalshi_headers("GET", path),
        params=params,
        timeout=12,
    )
    r.raise_for_status()
    return r.json()

def official_side(ticker):
    try:
        m = kalshi_get(f"/trade-api/v2/markets/{ticker}").get("market", {})
    except Exception as e:
        return None, f"API {type(e).__name__}: {e}"

    result = str(m.get("result") or "").strip().lower()
    if result == "yes":
        return "UP", "official_result"
    if result == "no":
        return "DOWN", "official_result"

    # Conservative fallback for API schema variants.
    for k in ("settlement_result","settled_result"):
        v = str(m.get(k) or "").strip().lower()
        if v == "yes":
            return "UP", k
        if v == "no":
            return "DOWN", k

    return None, f"unsettled/result={result!r}"

def as_bool_col(df, col):
    if col not in df:
        return pd.Series(False, index=df.index)
    return truthy_series(df[col])

def safe_numeric(df, cols):
    for c in cols:
        if c in df:
            df[c] = pd.to_numeric(df[c], errors="coerce")

def contract_time_key(ticker):
    # Primary ordering comes from first observed timestamp, so no ticker parser needed.
    return ticker

def first_signal_per_contract(df, mask):
    x = df.loc[mask].copy()
    if x.empty:
        return x

    # Earliest actionable moment = greatest minutes_left within each contract.
    # If both sides qualify at the same instant, prefer higher fair, then edge.
    x = x.sort_values(
        ["contract","minutes_left","side_fair","side_edge"],
        ascending=[True,False,False,False],
    )
    return x.groupby("contract", as_index=False).head(1).copy()

def metrics(signals, contracts):
    n_contracts = len(contracts)
    n = len(signals)
    if n == 0:
        return {
            "calls":0, "accuracy":np.nan, "coverage":0.0,
            "avg_ask":np.nan, "median_ask":np.nan,
            "pct_20_40":np.nan, "avg_time":np.nan, "median_time":np.nan,
        }

    correct = (signals["side"] == signals["official_side"]).astype(int)
    ask = pd.to_numeric(signals["side_ask"], errors="coerce")
    mins = pd.to_numeric(signals["minutes_left"], errors="coerce")
    return {
        "calls":n,
        "accuracy":100*correct.mean(),
        "coverage":100*n/max(1,n_contracts),
        "avg_ask":100*ask.mean(),
        "median_ask":100*ask.median(),
        "pct_20_40":100*((ask >= .20) & (ask <= .40)).mean(),
        "avg_time":mins.mean(),
        "median_time":mins.median(),
    }

def fmt(m):
    if m["calls"] == 0:
        return "0 calls"
    return (
        f"{m['accuracy']:.1f}% | {m['calls']} calls | "
        f"{m['coverage']:.1f}% cov | avg ask {m['avg_ask']:.1f}c | "
        f"20–40c {m['pct_20_40']:.1f}% | avg {m['avg_time']:.2f}m left"
    )

print("="*72)
print("UNIFIED SUB-MINUTE EARLY ENTRY — OFFLINE SCREEN V1")
print("="*72)

d = pd.read_csv(DATA)
d["timestamp_utc"] = pd.to_datetime(d["timestamp_utc"], errors="coerce", utc=True)

safe_numeric(d, [
    "minutes_left","seconds_left","side_ask","side_bid","side_fair","side_edge",
    "candidate_persistence_30s","btc_gap_side","abs_btc_gap",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "brti_gap_side","brti_age_seconds","dist_over_range5",
])

d["brti_ready_b"] = as_bool_col(d, "brti_ready")
d["brti_agrees_b"] = as_bool_col(d, "brti_agrees_side")
d["lag15_b"] = as_bool_col(d, "kalshi_lag_15s")
d["lag30_b"] = as_bool_col(d, "kalshi_lag_30s")

print(f"RAW ROWS: {len(d)}")
print(f"RAW CONTRACTS: {d['contract'].nunique()}")

# Label using official Kalshi settlement result.
labels = {}
label_source = {}
for ticker in sorted(d["contract"].dropna().astype(str).unique()):
    side, source = official_side(ticker)
    labels[ticker] = side
    label_source[ticker] = source
    time.sleep(0.08)

d["official_side"] = d["contract"].map(labels)
settled = [t for t,s in labels.items() if s in ("UP","DOWN")]
unresolved = [t for t,s in labels.items() if s not in ("UP","DOWN")]

print(f"OFFICIAL SETTLED: {len(settled)}")
if unresolved:
    print(f"UNRESOLVED/UNSETTLED: {len(unresolved)}")
    for t in unresolved[:8]:
        print(f"  {t}: {label_source[t]}")

d = d[d["official_side"].isin(["UP","DOWN"])].copy()

# Require useful capture of the whole early window to avoid scoring partial contracts.
coverage = (
    d.groupby("contract")
     .agg(
        first_ts=("timestamp_utc","min"),
        max_minutes=("minutes_left","max"),
        min_minutes=("minutes_left","min"),
        rows=("contract","size"),
     )
     .reset_index()
)
coverage["full_early_window"] = (
    (coverage["max_minutes"] >= 9.5)
    & (coverage["min_minutes"] <= 4.2)
)

full_contracts = coverage.loc[coverage["full_early_window"], "contract"].tolist()
partial_contracts = coverage.loc[~coverage["full_early_window"], "contract"].tolist()

print(f"FULL 10→4m WINDOWS: {len(full_contracts)}")
print(f"PARTIAL WINDOWS EXCLUDED: {len(partial_contracts)}")

if len(full_contracts) < 6:
    raise SystemExit(
        "STOP: fewer than 6 fully captured settled contracts. "
        "Dataset is useful but too small for an honest chronological screen."
    )

d = d[d["contract"].isin(full_contracts)].copy()

# Chronological order by first timestamp.
order = (
    d.groupby("contract")["timestamp_utc"].min()
     .sort_values()
     .index.tolist()
)

# Keep an untouched late block. Small sample, so this is screening, NOT validation.
split = max(4, int(round(len(order) * 0.65)))
split = min(split, len(order)-3)
dev_contracts = order[:split]
hold_contracts = order[split:]

print(f"DISCOVERY CONTRACTS: {len(dev_contracts)}")
print(f"UNTOUCHED LATE CONTRACTS: {len(hold_contracts)}")
print("NOTE: small sample = RESEARCH SCREEN ONLY, not production validation.")
print("-"*72)

# Base requirements permanently preserve economics/timing.
base = (
    d["minutes_left"].between(4.0, 10.0, inclusive="both")
    & (d["side_ask"] <= 0.50)
    & d["side_fair"].notna()
    & d["side_edge"].notna()
)

safe_reversal = ~d["reversal_state"].astype(str).isin(
    ["AGAINST","REVERSAL_WARN"]
)

rows = []
configs = []

for ask_max in [0.40,0.45,0.50]:
    for fair_min in [0.60,0.65,0.70,0.75,0.80]:
        for edge_min in [0.00,0.05,0.10]:
            for persist_min in [0,3,5]:
                for require_safe in [False,True]:
                    for lag_mode in ["ANY","LAG15OR30"]:
                        name = (
                            f"A{int(ask_max*100)}_F{int(fair_min*100)}_"
                            f"E{int(edge_min*100)}_P{persist_min}_"
                            f"{'SAFE' if require_safe else 'ALL'}_{lag_mode}"
                        )
                        mask = (
                            base
                            & (d["side_ask"] <= ask_max)
                            & (d["side_fair"] >= fair_min)
                            & (d["side_edge"] >= edge_min)
                            & d["brti_ready_b"]
                            & d["brti_agrees_b"]
                            & (d["brti_age_seconds"] <= 5.0)
                            & (d["candidate_persistence_30s"] >= persist_min)
                        )
                        if require_safe:
                            mask &= safe_reversal
                        if lag_mode == "LAG15OR30":
                            mask &= (d["lag15_b"] | d["lag30_b"])

                        configs.append((name, mask))

for name, mask in configs:
    dev_df = d[d["contract"].isin(dev_contracts)]
    hold_df = d[d["contract"].isin(hold_contracts)]

    dev_sig = first_signal_per_contract(dev_df, mask.loc[dev_df.index])
    hold_sig = first_signal_per_contract(hold_df, mask.loc[hold_df.index])

    dm = metrics(dev_sig, dev_contracts)
    hm = metrics(hold_sig, hold_contracts)

    rows.append({
        "config":name,
        "dev_calls":dm["calls"],
        "dev_accuracy":dm["accuracy"],
        "dev_coverage":dm["coverage"],
        "dev_avg_ask":dm["avg_ask"],
        "dev_pct_20_40":dm["pct_20_40"],
        "dev_avg_time":dm["avg_time"],
        "hold_calls":hm["calls"],
        "hold_accuracy":hm["accuracy"],
        "hold_coverage":hm["coverage"],
        "hold_avg_ask":hm["avg_ask"],
        "hold_pct_20_40":hm["pct_20_40"],
        "hold_avg_time":hm["avg_time"],
    })

grid = pd.DataFrame(rows)

# Select without looking at holdout:
# require at least 3 discovery calls, then accuracy, coverage, cheaper entry, earlier timing.
eligible = grid[grid["dev_calls"] >= 3].copy()
if eligible.empty:
    eligible = grid[grid["dev_calls"] >= 2].copy()

if eligible.empty:
    raise SystemExit("No discovery configuration produced enough calls to screen.")

eligible = eligible.sort_values(
    ["dev_accuracy","dev_coverage","dev_avg_ask","dev_avg_time"],
    ascending=[False,False,True,False],
)
winner = eligible.iloc[0]
winner_name = winner["config"]

# Recover winner mask.
winner_mask = dict(configs)[winner_name]
dev_df = d[d["contract"].isin(dev_contracts)]
hold_df = d[d["contract"].isin(hold_contracts)]
all_df = d[d["contract"].isin(order)]

dev_sig = first_signal_per_contract(dev_df, winner_mask.loc[dev_df.index])
hold_sig = first_signal_per_contract(hold_df, winner_mask.loc[hold_df.index])
all_sig = first_signal_per_contract(all_df, winner_mask.loc[all_df.index])

dm = metrics(dev_sig, dev_contracts)
hm = metrics(hold_sig, hold_contracts)
am = metrics(all_sig, order)

grid.to_csv(OUT_GRID, index=False)
all_sig.to_csv(OUT_SIGNALS, index=False)

print("DISCOVERY-SELECTED WINNER:")
print(f"  {winner_name}")
print(f"DISCOVERY: {fmt(dm)}")
print(f"UNTOUCHED: {fmt(hm)}")
print(f"ALL FULL-WINDOW CONTRACTS (descriptive only): {fmt(am)}")
print("-"*72)

# Fixed reference rules, not selected by optimizer.
fixed_rules = {
    "BASE_BRTI": (
        base & d["brti_ready_b"] & d["brti_agrees_b"]
        & (d["brti_age_seconds"] <= 5.0)
    ),
    "BASE_BRTI_SAFE": (
        base & d["brti_ready_b"] & d["brti_agrees_b"]
        & (d["brti_age_seconds"] <= 5.0) & safe_reversal
    ),
    "CHEAP45_FAIR70_SAFE": (
        base & (d["side_ask"] <= .45) & (d["side_fair"] >= .70)
        & (d["side_edge"] >= .05)
        & d["brti_ready_b"] & d["brti_agrees_b"]
        & (d["brti_age_seconds"] <= 5.0) & safe_reversal
    ),
}

print("FIXED REFERENCE RULES — UNTOUCHED LATE BLOCK:")
for name, mask in fixed_rules.items():
    sig = first_signal_per_contract(
        hold_df, mask.loc[hold_df.index]
    )
    print(f"  {name}: {fmt(metrics(sig, hold_contracts))}")

print("="*72)

# Conservative interpretation.
if hm["calls"] >= 4 and hm["accuracy"] >= 90:
    print("SCREEN RESULT: PROMISING EARLY-ENTRY STRUCTURE")
    print("Do NOT production-lock it yet; sample is still small.")
elif hm["calls"] >= 3 and hm["accuracy"] >= 80:
    print("SCREEN RESULT: SOME SIGNAL, NOT YET STRONG ENOUGH")
    print("Preserve the features; accumulate more contracts naturally.")
else:
    print("SCREEN RESULT: NO STABLE EARLY-ENTRY RULE YET")
    print("Do not weaken FINAL or scalp to force coverage.")

print(f"Saved grid: {OUT_GRID}")
print(f"Saved winner signals: {OUT_SIGNALS}")
print("="*72)
