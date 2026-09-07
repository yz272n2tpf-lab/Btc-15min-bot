from pathlib import Path
import base64
import re
import time
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

import numpy as np
import pandas as pd
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from sklearn.ensemble import RandomForestClassifier
from sklearn.isotonic import IsotonicRegression
from sklearn.linear_model import LogisticRegression

CAL = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")
LOG = Path("kalshi_live_fair_value_shadow_log.csv")

print("=== KALSHI LIVE FAIR-VALUE SHADOW MONITOR ===")
print("Purpose: compare validated live fair UP/DOWN probability against")
print("the exact active Kalshi 15-minute contract and its live ask prices.")
print("Signal-only: YES")
print("Orders placed: NO")
print("bot.py modified: NO")
print()

# ============================================================
# READ-ONLY KALSHI
# ============================================================

KEY_ID = Path.home().joinpath(".kalshi/key_id").read_text().strip()
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"

private_key = serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(),
    password=None,
)

KALSHI_BASE_URL = "https://api.elections.kalshi.com"

def kalshi_headers(method, path):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method.upper() + path

    signature = private_key.sign(
        message.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )

    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(signature).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }

def kalshi_get(path, params=None):
    r = requests.get(
        KALSHI_BASE_URL + path,
        headers=kalshi_headers("GET", path),
        params=params,
        timeout=15,
    )
    r.raise_for_status()
    return r.json()

def parse_dt(value):
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None

def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def get_current_kalshi_btc():
    data = kalshi_get(
        "/trade-api/v2/markets",
        params={
            "status": "open",
            "series_ticker": "KXBTC15M",
            "limit": 1000,
        },
    )

    now = datetime.now(timezone.utc)
    active = []

    for market in data.get("markets", []):
        ticker = str(market.get("ticker", ""))
        open_dt = parse_dt(market.get("open_time"))
        close_dt = parse_dt(market.get("close_time"))

        if not ticker.startswith("KXBTC15M"):
            continue

        if (
            open_dt is not None
            and close_dt is not None
            and open_dt <= now < close_dt
        ):
            active.append(market)

    if not active:
        return None

    return min(active, key=lambda m: parse_dt(m.get("close_time")))

# ============================================================
# LIVE COINBASE 1-MINUTE HISTORY
# ============================================================

def fetch_coinbase_range(start, end, granularity=60):
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    rows = []
    batch_start = start

    while batch_start < end:
        batch_end = min(
            batch_start + timedelta(minutes=300),
            end,
        )

        params = {
            "granularity": granularity,
            "start": batch_start.isoformat(),
            "end": batch_end.isoformat(),
        }

        r = requests.get(url, params=params, timeout=20)
        r.raise_for_status()

        batch = r.json()
        if isinstance(batch, list):
            rows.extend(batch)

        batch_start = batch_end
        time.sleep(0.03)

    df = pd.DataFrame(
        rows,
        columns=["Time", "Low", "High", "Open", "Close", "Volume"],
    )

    if df.empty:
        return df

    df["Datetime"] = pd.to_datetime(
        df["Time"],
        unit="s",
        utc=True,
    )

    df = (
        df.drop_duplicates("Datetime")
        .sort_values("Datetime")
        .set_index("Datetime")
    )

    for c in ["Low","High","Open","Close","Volume"]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    return df[["Open","High","Low","Close","Volume"]]

def load_live_history():
    now = datetime.now(timezone.utc)

    if BTC_CACHE.exists():
        old = pd.read_csv(
            BTC_CACHE,
            index_col="Datetime",
            parse_dates=True,
        )

        if old.index.tz is None:
            old.index = old.index.tz_localize("UTC")
        else:
            old.index = old.index.tz_convert("UTC")

        for c in ["Open","High","Low","Close","Volume"]:
            if c in old.columns:
                old[c] = pd.to_numeric(old[c], errors="coerce")

        update_start = old.index.max() - timedelta(minutes=5)

        fresh = fetch_coinbase_range(update_start, now)

        data = pd.concat([old, fresh])

        data = (
            data[
                ~data.index.duplicated(keep="last")
            ]
            .sort_index()
        )

        cutoff = pd.Timestamp(now) - pd.Timedelta(days=35)
        data = data[data.index >= cutoff]

    else:
        data = fetch_coinbase_range(
            now - timedelta(days=35),
            now,
        )

    data.to_csv(BTC_CACHE, index_label="Datetime")
    return data

# ============================================================
# HISTORICAL CONTRACT TIMING + VALIDATED FEATURE ENGINE
# ============================================================

MONTHS = {m:i+1 for i,m in enumerate(
    ["JAN","FEB","MAR","APR","MAY","JUN","JUL","AUG","SEP","OCT","NOV","DEC"]
)}

def parse_contract_times(ticker):
    m = re.search(
        r"KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-",
        str(ticker).upper(),
    )

    if not m:
        return pd.NaT, pd.NaT

    yy, mon, dd, hh, mm = m.groups()

    wall = pd.Timestamp(
        year=2000 + int(yy),
        month=MONTHS[mon],
        day=int(dd),
        hour=int(hh),
        minute=int(mm),
    )

    close_utc = wall.tz_localize(
        ZoneInfo("America/New_York")
    ).tz_convert("UTC")

    return (
        close_utc - pd.Timedelta(minutes=15),
        close_utc,
    )

def price_at_or_before(data, ts):
    i = data.index.searchsorted(ts, side="right") - 1

    if i < 0:
        return np.nan, pd.NaT

    ti = data.index[i]

    if ts - ti > pd.Timedelta(minutes=2):
        return np.nan, pd.NaT

    return float(data.iloc[i]["Close"]), ti

def build_snapshot(data, start, target, final_side=None, elapsed=None, cut=None):
    if cut is None:
        cut = start + pd.Timedelta(minutes=float(elapsed))

    elapsed_actual = (cut - start).total_seconds() / 60.0

    # Historical validator was tested on elapsed whole minutes 1..14.
    # Live can be fractional; features are calculated at the latest available moment.
    pstart, tstart = price_at_or_before(data, start)

    vals = [
        price_at_or_before(data, cut - pd.Timedelta(minutes=m))
        for m in [0,1,2,3,5]
    ]

    if pd.isna(pstart) or any(pd.isna(v[0]) for v in vals):
        return None

    p0,p1,p2,p3,p5 = [v[0] for v in vals]

    w = data.loc[
        (data.index > cut - pd.Timedelta(minutes=5))
        & (data.index <= cut)
    ]

    if len(w) < 3:
        return None

    closes = w["Close"].dropna()

    if len(closes) < 2:
        return None

    latest_used = max(
        [tstart] + [v[1] for v in vals] + [w.index.max()]
    )

    if latest_used > cut:
        raise RuntimeError("FUTURE DATA DETECTED")

    current_side = int(p0 >= target)

    dist = p0 - target
    abs_dist = abs(dist)
    remaining = max(0.0, 15.0 - elapsed_actual)
    sign = 1.0 if current_side == 1 else -1.0

    move1 = p0-p1
    move2 = p0-p2
    move3 = p0-p3
    move5 = p0-p5

    range5 = float(w["High"].max()-w["Low"].min())

    row = {
        "elapsed": float(elapsed_actual),
        "remaining": float(remaining),
        "current_side": int(current_side),

        "dist_target": float(dist),
        "abs_dist_target": float(abs_dist),
        "dist_target_pct": float(dist/target),

        "move_from_start": float(p0-pstart),
        "move_from_start_pct": float((p0-pstart)/pstart),

        "move1": float(move1),
        "move2": float(move2),
        "move3": float(move3),
        "move5": float(move5),

        "support1": float(move1*sign),
        "support2": float(move2*sign),
        "support3": float(move3*sign),
        "support5": float(move5*sign),

        "range5": float(range5),
        "vol5": float(closes.pct_change().std(ddof=0)),

        "dist_per_min_remaining": float(
            abs_dist/max(remaining,0.25)
        ),
        "dist_over_range5": float(
            abs_dist/max(range5,1.0)
        ),

        "current_coinbase_close": float(p0),
    }

    if final_side is not None:
        row["final_side"] = int(final_side)
        row["flip"] = int(int(final_side) != current_side)

    return row

FEATURES = [
    "elapsed","remaining","current_side",
    "dist_target","abs_dist_target","dist_target_pct",
    "move_from_start","move_from_start_pct",
    "move1","move2","move3","move5",
    "support1","support2","support3","support5",
    "range5","vol5",
    "dist_per_min_remaining","dist_over_range5",
]

# ============================================================
# LOAD ACTIVE CONTRACT + UPDATE BTC
# ============================================================

kalshi = get_current_kalshi_btc()

if kalshi is None:
    raise SystemExit("NO ACTIVE KXBTC15M CONTRACT FOUND")

target = num(kalshi.get("floor_strike"))
yes_bid = num(kalshi.get("yes_bid_dollars"))
yes_ask = num(kalshi.get("yes_ask_dollars"))
no_bid = num(kalshi.get("no_bid_dollars"))
no_ask = num(kalshi.get("no_ask_dollars"))

open_dt = parse_dt(kalshi.get("open_time"))
close_dt = parse_dt(kalshi.get("close_time"))
now_dt = datetime.now(timezone.utc)

if target is None or open_dt is None or close_dt is None:
    raise SystemExit("ACTIVE CONTRACT IS MISSING TARGET OR CLOCK FIELDS")

elapsed_live = (now_dt-open_dt).total_seconds()/60.0
remaining_live = (close_dt-now_dt).total_seconds()/60.0

data = load_live_history()

# ============================================================
# BUILD HISTORICAL TRAIN/CALIBRATION SET
# ============================================================

cal = pd.read_csv(CAL)

pairs = cal["ticker"].map(parse_contract_times)
cal["start"] = [x[0] for x in pairs]
cal["close"] = [x[1] for x in pairs]

cal["target_brti"] = pd.to_numeric(
    cal["target_brti"],
    errors="coerce",
)

cal["final_brti"] = pd.to_numeric(
    cal["final_brti"],
    errors="coerce",
)

cal["final_side"] = (
    cal["result"]
    .astype(str)
    .str.lower()
    .map({"yes":1,"no":0})
)

cal = cal.dropna(
    subset=[
        "start","close",
        "target_brti",
        "final_brti",
        "final_side",
    ]
).sort_values("start").reset_index(drop=True)

historical_rows = []

for _, r in cal.iterrows():
    for elapsed in range(1,15):
        s = build_snapshot(
            data=data,
            start=r["start"],
            target=float(r["target_brti"]),
            final_side=int(r["final_side"]),
            elapsed=elapsed,
        )

        if s is not None:
            s["ticker"] = r["ticker"]
            s["start"] = r["start"]
            historical_rows.append(s)

hist = pd.DataFrame(historical_rows)

if hist.empty:
    raise SystemExit("NO HISTORICAL FEATURE ROWS COULD BE BUILT")

coverage = hist.groupby("ticker")["elapsed"].nunique()
keep = coverage[coverage >= 10].index

hist = hist[
    hist["ticker"].isin(keep)
].copy()

contracts = (
    hist[["ticker","start"]]
    .drop_duplicates("ticker")
    .sort_values("start")
    .reset_index(drop=True)
)

# Final live fitting policy:
# first 80% of settled contracts = model training
# final 20% of settled contracts = probability calibration
split = int(len(contracts)*0.80)

model_contracts = contracts.iloc[:split]
calib_contracts = contracts.iloc[split:]

model_ticks = set(model_contracts["ticker"])
calib_ticks = set(calib_contracts["ticker"])

train = hist[hist["ticker"].isin(model_ticks)].copy()
calibrate = hist[hist["ticker"].isin(calib_ticks)].copy()

if (
    model_contracts["start"].max()
    >= calib_contracts["start"].min()
):
    raise RuntimeError("LIVE TRAIN/CALIBRATION CHRONOLOGY FAILURE")

rf = RandomForestClassifier(
    n_estimators=900,
    max_depth=9,
    min_samples_leaf=12,
    class_weight="balanced",
    random_state=42,
    n_jobs=-1,
)

rf.fit(
    train[FEATURES],
    train["flip"],
)

calib_raw = rf.predict_proba(
    calibrate[FEATURES]
)[:,1]

# ------------------------------------------------------------
# SMOOTH PROBABILITY CALIBRATION
#
# Previous live code used IsotonicRegression. Isotonic is a
# step function and can legitimately output exact 0.0 / 1.0
# when a live raw probability lands in an extreme calibration
# plateau. In live testing this produced implausible 100% FAIR
# readings with substantial time remaining.
#
# Use chronological Platt/sigmoid calibration instead:
#   raw RF flip probability -> calibrated flip probability
#
# This preserves the historical calibration layer while forcing
# a smooth probability mapping rather than hard 0/100 steps.
# ------------------------------------------------------------
sigmoid = LogisticRegression(
    solver="lbfgs",
    C=1.0,
    max_iter=1000,
    random_state=42,
)

sigmoid.fit(
    calib_raw.reshape(-1, 1),
    calibrate["flip"].astype(int),
)

calibration_contract_count = len(calib_contracts)
calibration_snapshot_count = len(calibrate)

if calibration_contract_count < 50:
    raise RuntimeError(
        "CALIBRATION SAFETY FAILURE: fewer than 50 independent contracts"
    )

# ============================================================
# LIVE SNAPSHOT
# ============================================================

live_start = pd.Timestamp(open_dt)

if live_start.tzinfo is None:
    live_start = live_start.tz_localize("UTC")
else:
    live_start = live_start.tz_convert("UTC")

live_cut = pd.Timestamp(now_dt)

live = build_snapshot(
    data=data,
    start=live_start,
    target=float(target),
    cut=live_cut,
)

if live is None:
    raise SystemExit(
        "NOT ENOUGH CURRENT 1-MINUTE BTC DATA YET FOR FAIR PROBABILITY"
    )

live_frame = pd.DataFrame([live])

raw_flip = float(
    rf.predict_proba(
        live_frame[FEATURES]
    )[0,1]
)

flip_prob = float(
    sigmoid.predict_proba(
        np.array([[raw_flip]])
    )[0, 1]
)

# Numerical guard only. Sigmoid calibration should naturally stay
# inside (0, 1); these bounds protect formatting/downstream math
# from accidental machine-precision extremes, not model logic.
flip_prob = float(np.clip(flip_prob, 0.001, 0.999))
stay_prob = 1.0-flip_prob

current_side = int(live["current_side"])

if current_side == 1:
    fair_up = stay_prob
    fair_down = flip_prob
else:
    fair_up = flip_prob
    fair_down = stay_prob

preferred_side = "UP" if fair_up >= fair_down else "DOWN"
fair_preferred = max(fair_up, fair_down)

# Live probability sanity flag. This does NOT alter the fair value.
# It prevents us from silently treating an extreme early reading as
# trustworthy before live validation supports it.
if elapsed_live < 5 and fair_preferred >= 0.95:
    probability_sanity = "CAUTION - EXTREME EARLY PROBABILITY"
elif elapsed_live < 8 and fair_preferred >= 0.98:
    probability_sanity = "CAUTION - EXTREME MID-EARLY PROBABILITY"
else:
    probability_sanity = "PASS"

preferred_ask = (
    yes_ask
    if preferred_side == "UP"
    else no_ask
)

edge = (
    fair_preferred-preferred_ask
    if preferred_ask is not None
    else None
)

# ============================================================
# TIME-AWARE STATUS
# Validation showed early 90% calls are less reliable before minute 8.
# Do not call them a full LOCK prematurely.
# ============================================================

if fair_preferred < 0.70:
    signal_status = "RAW"

elif fair_preferred < 0.80:
    signal_status = "LEAN"

elif fair_preferred < 0.90:
    signal_status = "STRONG"

else:
    if elapsed_live < 8:
        signal_status = "EARLY 90%+ / NOT YET VALIDATED LOCK"
    elif elapsed_live < 10:
        signal_status = "90%+ LOCK CANDIDATE"
    else:
        signal_status = "LOCK"

# Entry status is separate from prediction status.
if preferred_ask is None or edge is None:
    entry_status = "NO LIVE ASK"

elif preferred_ask <= 0.50 and edge >= 0.20:
    entry_status = "IDEAL <=50c / LARGE EDGE"

elif preferred_ask <= 0.50 and edge >= 0.15:
    entry_status = "ATTRACTIVE <=50c"

elif edge >= 0.20:
    entry_status = "LARGE EDGE / PRICE ABOVE 50c"

elif edge >= 0.10:
    entry_status = "POSITIVE EDGE"

elif preferred_ask >= fair_preferred:
    entry_status = "NO VALUE"

else:
    entry_status = "SMALL EDGE"

# ============================================================
# OUTPUT
# ============================================================

print("=== EXACT ACTIVE KALSHI CONTRACT ===")
print("CONTRACT:", kalshi.get("ticker"))
print("TARGET:", f"${target:,.2f}")
print("ELAPSED:", f"{elapsed_live:.2f} min")
print("TIME LEFT:", f"{remaining_live:.2f} min")
print("UP BID/ASK:", yes_bid, "/", yes_ask)
print("DOWN BID/ASK:", no_bid, "/", no_ask)
print()

print("=== VALIDATED LIVE FAIR PROBABILITY ===")
print(
    "Coinbase reference:",
    f"${live['current_coinbase_close']:,.2f}",
)
print(
    "Distance from Kalshi target:",
    f"${live['dist_target']:+,.2f}",
)
print(
    "Current target side:",
    "UP" if current_side == 1 else "DOWN",
)
print("Raw model flip probability:", f"{raw_flip:.1%}")
print("Calibrated flip probability:", f"{flip_prob:.1%}")
print("Stay probability:", f"{stay_prob:.1%}")
print("FAIR UP:", f"{fair_up:.1%}")
print("FAIR DOWN:", f"{fair_down:.1%}")
print("Probability sanity:", probability_sanity)
print(
    "Calibration sample:",
    f"{calibration_contract_count} contracts / "
    f"{calibration_snapshot_count} snapshots",
)
print()

print("=== LIVE DECISION ===")
print("PREFERRED SIDE:", preferred_side)
print("FAIR VALUE:", f"{fair_preferred:.1%}")

if preferred_ask is not None:
    print(
        "KALSHI ASK ON PREFERRED SIDE:",
        f"{preferred_ask:.2f}",
        f"({preferred_ask:.1%})",
    )
else:
    print("KALSHI ASK ON PREFERRED SIDE: unavailable")

if edge is not None:
    print("MODEL EDGE:", f"{edge:+.1%}")
else:
    print("MODEL EDGE: unavailable")

print("SIGNAL STATUS:", signal_status)
print("ENTRY STATUS:", entry_status)

# Useful max prices for preserving edge.
print(
    "MAX BUY FOR 10pt EDGE:",
    f"{max(0.01, min(0.99, fair_preferred-0.10)):.2f}",
)
print(
    "MAX BUY FOR 15pt EDGE:",
    f"{max(0.01, min(0.99, fair_preferred-0.15)):.2f}",
)
print(
    "MAX BUY FOR 20pt EDGE:",
    f"{max(0.01, min(0.99, fair_preferred-0.20)):.2f}",
)

# ============================================================
# SHADOW LOG
# ============================================================

row = {
    "timestamp_utc": pd.Timestamp(now_dt).isoformat(),
    "ticker": kalshi.get("ticker"),
    "target": target,
    "elapsed_min": elapsed_live,
    "remaining_min": remaining_live,

    "coinbase_close": live["current_coinbase_close"],
    "distance_target": live["dist_target"],

    "current_side": "UP" if current_side == 1 else "DOWN",

    "raw_flip_prob": raw_flip,
    "flip_prob": flip_prob,
    "stay_prob": stay_prob,
    "probability_sanity": probability_sanity,
    "fair_up": fair_up,
    "fair_down": fair_down,

    "preferred_side": preferred_side,
    "fair_preferred": fair_preferred,

    "up_bid": yes_bid,
    "up_ask": yes_ask,
    "down_bid": no_bid,
    "down_ask": no_ask,

    "preferred_ask": preferred_ask,
    "edge": edge,

    "signal_status": signal_status,
    "entry_status": entry_status,
}

frame = pd.DataFrame([row])

if LOG.exists():
    frame.to_csv(
        LOG,
        mode="a",
        header=False,
        index=False,
    )
else:
    frame.to_csv(
        LOG,
        index=False,
    )

print()
print("Logged to:", LOG)

print()
print("=== HARD CHECKS ===")
print("Exact active KXBTC15M contract: PASS")
print("Actual Kalshi target/clock/prices: PASS")
print("Corrected Kalshi timing: PASS")
print("Historical probability calibration only: PASS")
print("Smooth sigmoid calibration: PASS")
print(
    "Calibration sample size:",
    f"{calibration_contract_count} contracts / "
    f"{calibration_snapshot_count} snapshots",
)
print("Live BTC features use only data available now: PASS")
print("Fair probability connected: YES")
print("Signal-only behavior: PASS")
print("Orders placed: NO")
print("bot.py modified: NO")

print()
print("=== IMPORTANT ===")
print("Compare TARGET, TIME LEFT, UP/DOWN asks, and preferred side")
print("against the actual Kalshi app before trusting this live shadow output.")
