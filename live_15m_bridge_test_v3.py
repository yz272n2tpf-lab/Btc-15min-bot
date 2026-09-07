import base64
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import pandas as pd
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
from sklearn.ensemble import RandomForestClassifier


# ============================================================
# LIVE 15-MIN MODEL + KALSHI BRIDGE V3
#
# Adds validated BRTI/Kalshi target safety layer:
#   - Coinbase HL2 proxy
#   - Coinbase-minus-BRTI bias estimated from calibration CSV
#   - $11 validated uncertainty / WAIT zone
#
# READY requires:
#   1) strict model conditions
#   2) BRTI-adjusted BTC gap outside +/- $11
#   3) BRTI side agrees with model direction
#
# NO ORDERS.
# NO CHANGES TO bot.py.
# ============================================================


BRTI_BUFFER_DOLLARS = 11.0
CALIBRATION_CSV = Path("brti_calibration_results.csv")
BTC_CACHE = Path("btc_35d_live_cache.csv")

KEY_ID = Path.home().joinpath(".kalshi/key_id").read_text().strip()
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"

private_key = serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(),
    password=None,
)

KALSHI_BASE_URL = "https://api.elections.kalshi.com"


def kalshi_headers(method, path):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path

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

    markets = data.get("markets", [])
    now = datetime.now(timezone.utc)

    active = []

    for m in markets:
        open_dt = parse_dt(m.get("open_time"))
        close_dt = parse_dt(m.get("close_time"))

        if open_dt is None or close_dt is None:
            continue

        if open_dt <= now < close_dt:
            active.append(m)

    if not active:
        return None

    return min(
        active,
        key=lambda m: parse_dt(m.get("close_time")),
    )


def fetch_coinbase_range(start, end, granularity=60):
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

    rows = []
    batch_start = start
    step_seconds = granularity * 300

    while batch_start < end:
        batch_end = min(
            batch_start + timedelta(seconds=step_seconds),
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

    df["Datetime"] = pd.to_datetime(df["Time"], unit="s", utc=True)

    df = (
        df.drop_duplicates("Datetime")
        .sort_values("Datetime")
        .set_index("Datetime")
    )

    return df[["Open", "High", "Low", "Close", "Volume"]]


def load_live_history():
    now = datetime.now(timezone.utc)

    if BTC_CACHE.exists():
        print("Using cached BTC history...")

        old = pd.read_csv(
            BTC_CACHE,
            index_col="Datetime",
            parse_dates=True,
        )

        if old.index.tz is None:
            old.index = old.index.tz_localize("UTC")
        else:
            old.index = old.index.tz_convert("UTC")

        update_start = old.index.max() - timedelta(minutes=5)
        fresh = fetch_coinbase_range(update_start, now)

        data = pd.concat([old, fresh])
        data = data[~data.index.duplicated(keep="last")].sort_index()

        cutoff = now - timedelta(days=35)
        data = data[data.index >= cutoff]

    else:
        print("Loading 35-day BTC history...")
        data = fetch_coinbase_range(
            now - timedelta(days=35),
            now,
        )

    data.to_csv(BTC_CACHE, index_label="Datetime")
    return data


def build_features(data):
    df = data.copy()

    df["contract_bucket"] = df.index.floor("15min")

    df["contract_start_price"] = (
        df.groupby("contract_bucket")["Open"].transform("first")
    )

    df["contract_final_close"] = (
        df.groupby("contract_bucket")["Close"].transform("last")
    )

    df["elapsed_minute"] = (
        (df.index.to_series(index=df.index) - df["contract_bucket"])
        .dt.total_seconds()
        / 60.0
    )

    df["remaining_minutes"] = 15.0 - df["elapsed_minute"]

    df["move_from_start_pct"] = (
        df["Close"] / df["contract_start_price"] - 1.0
    )

    df["distance_abs"] = df["move_from_start_pct"].abs()
    df["return_1m"] = df["Close"].pct_change(1)
    df["return_3m"] = df["Close"].pct_change(3)
    df["return_5m"] = df["Close"].pct_change(5)
    df["momentum_1m"] = df["return_1m"] - df["return_1m"].shift(1)
    df["volatility_5m"] = df["return_1m"].rolling(5).std()
    df["sma_5"] = df["Close"].rolling(5).mean()
    df["sma_distance_5"] = df["Close"] / df["sma_5"] - 1.0

    df["contract_outcome"] = (
        df["contract_final_close"] > df["contract_start_price"]
    )

    return df


FEATURES = [
    "elapsed_minute",
    "remaining_minutes",
    "move_from_start_pct",
    "return_1m",
    "return_3m",
    "return_5m",
    "momentum_1m",
    "volatility_5m",
    "sma_distance_5",
]


def agreement_hits(row, pred):
    hits = 0

    for col in ["return_1m", "return_3m", "return_5m"]:
        v = row[col]

        if pd.isna(v):
            continue

        if pred and v > 0:
            hits += 1
        elif (not pred) and v < 0:
            hits += 1

    return hits


def load_brti_bias():
    if not CALIBRATION_CSV.exists():
        raise SystemExit(
            "Missing brti_calibration_results.csv. "
            "Run the calibration audit first."
        )

    c = pd.read_csv(CALIBRATION_CSV)

    required = [
        "target_brti",
        "final_brti",
        "target_cb_hl2",
        "final_cb_hl2",
    ]

    missing = [x for x in required if x not in c.columns]

    if missing:
        raise SystemExit(
            f"Calibration CSV missing columns: {missing}"
        )

    errors = pd.concat(
        [
            c["target_cb_hl2"] - c["target_brti"],
            c["final_cb_hl2"] - c["final_brti"],
        ],
        ignore_index=True,
    )

    return float(errors.mean())


print("=== LIVE 15-MIN MODEL + KALSHI BRIDGE V3 ===")

kalshi = get_current_kalshi_btc()

if kalshi is None:
    raise SystemExit(
        "No truly active KXBTC15M contract found."
    )

brti_bias = load_brti_bias()

data = load_live_history()

print("BTC 1-minute rows:", len(data))
print("BRTI calibration bias:", f"${brti_bias:+.2f}")
print("Validated BRTI safety buffer:", f"${BRTI_BUFFER_DOLLARS:.2f}")

df = build_features(data)

current_bucket = df.index[-1].floor("15min")

train = df[
    df["contract_bucket"] < current_bucket
].dropna(
    subset=FEATURES + ["contract_outcome"]
).copy()

live_contract = df[
    df["contract_bucket"] == current_bucket
].dropna(
    subset=FEATURES
).copy()

if train.empty or live_contract.empty:
    raise SystemExit(
        "Not enough BTC data for live bridge."
    )

print("Training rows:", len(train))
print("Live contract rows:", len(live_contract))
print("Training one live model...")

model = RandomForestClassifier(
    n_estimators=1200,
    max_depth=8,
    random_state=42,
    class_weight="balanced",
    n_jobs=-1,
)

model.fit(
    train[FEATURES],
    train["contract_outcome"],
)

live_contract["model_pred"] = model.predict(
    live_contract[FEATURES]
)

live_contract["model_conf"] = model.predict_proba(
    live_contract[FEATURES]
).max(axis=1)

latest = live_contract.iloc[-1]
previous = live_contract.iloc[-2] if len(live_contract) >= 2 else None

pred = bool(latest["model_pred"])
direction = "UP" if pred else "DOWN"
confidence = float(latest["model_conf"])

prev_conf = (
    float(previous["model_conf"])
    if previous is not None
    else None
)

confidence_change = (
    confidence - prev_conf
    if prev_conf is not None
    else None
)

agree = agreement_hits(latest, pred)
distance = float(latest["distance_abs"])
elapsed = float(latest["elapsed_minute"])

strict_model_ready = (
    elapsed >= 8
    and elapsed < 10
    and confidence >= 0.95
    and agree >= 3
    and confidence_change is not None
    and confidence_change >= 0
    and distance >= 0.00175
)


# ---------------- LIVE KALSHI TRACK ----------------

target = num(kalshi.get("floor_strike"))

yes_bid = num(kalshi.get("yes_bid_dollars"))
yes_ask = num(kalshi.get("yes_ask_dollars"))
no_bid = num(kalshi.get("no_bid_dollars"))
no_ask = num(kalshi.get("no_ask_dollars"))

open_dt = parse_dt(kalshi.get("open_time"))
close_dt = parse_dt(kalshi.get("close_time"))
now = datetime.now(timezone.utc)

seconds_left = max(
    0,
    int((close_dt - now).total_seconds()),
)

seconds_elapsed = max(
    0,
    int((now - open_dt).total_seconds()),
)


# ---------------- BRTI-AWARE LIVE PROXY ----------------

latest_candle = data.iloc[-1]

coinbase_hl2 = (
    float(latest_candle["High"])
    + float(latest_candle["Low"])
) / 2.0

estimated_brti = coinbase_hl2 - brti_bias

adjusted_gap = (
    estimated_brti - target
    if target is not None
    else None
)

inside_brti_wait_zone = (
    adjusted_gap is not None
    and abs(adjusted_gap) <= BRTI_BUFFER_DOLLARS
)

brti_direction = None

if adjusted_gap is not None:
    brti_direction = "UP" if adjusted_gap > 0 else "DOWN"

brti_agrees = (
    brti_direction == direction
    if brti_direction is not None
    else False
)

brti_ready = (
    adjusted_gap is not None
    and not inside_brti_wait_zone
    and brti_agrees
)

combined_ready = (
    strict_model_ready
    and brti_ready
)

model_side_ask = (
    yes_ask
    if direction == "UP"
    else no_ask
)


# ---------------- OUTPUT ----------------

print()
print("=== ACTIVE KALSHI CONTRACT ===")
print("Ticker:", kalshi.get("ticker"))
print("Title:", kalshi.get("title"))
print(
    "Target:",
    f"${target:,.2f}"
    if target is not None
    else "UNKNOWN",
)
print("Open:", kalshi.get("open_time"))
print("Close:", kalshi.get("close_time"))
print(
    "Contract elapsed:",
    f"{seconds_elapsed // 60}m {seconds_elapsed % 60}s",
)
print(
    "Time remaining:",
    f"{seconds_left // 60}m {seconds_left % 60}s",
)

print()
print("=== KALSHI LIVE ODDS ===")
print("UP bid/ask:", yes_bid, "/", yes_ask)
print("DOWN bid/ask:", no_bid, "/", no_ask)

print()
print("=== BRTI-AWARE TARGET TRACK ===")
print("Coinbase latest HL2:", f"${coinbase_hl2:,.2f}")
print(
    "Estimated BRTI:",
    f"${estimated_brti:,.2f}",
)
print(
    "Training calibration bias:",
    f"${brti_bias:+.2f}",
)
print(
    "Estimated BRTI vs Kalshi target:",
    f"${adjusted_gap:+.2f}"
    if adjusted_gap is not None
    else "UNKNOWN",
)
print(
    "Validated WAIT zone:",
    f"+/-${BRTI_BUFFER_DOLLARS:.2f}",
)
print(
    "Inside BRTI danger zone:",
    "YES" if inside_brti_wait_zone else "NO",
)
print(
    "BRTI directional side:",
    brti_direction if brti_direction else "UNKNOWN",
)

print()
print("=== VALIDATED 15-MIN MODEL TRACK ===")
print("Model direction:", direction)
print("Model confidence:", f"{confidence:.1%}")
print("Elapsed model minute:", f"{elapsed:.0f}")
print(
    "BTC distance from BTC 15m start:",
    f"{distance:.3%}",
)
print("Directional agreement:", f"{agree}/3")
print(
    "Confidence strengthening:",
    "YES"
    if confidence_change is not None and confidence_change >= 0
    else "NO",
)
print(
    "Confidence change 1m:",
    f"{confidence_change:+.4f}"
    if confidence_change is not None
    else "N/A",
)

print()
print("=== LAYER STATUS ===")
print(
    "STRICT MODEL READY:",
    "YES" if strict_model_ready else "NO",
)
print(
    "BRTI GATE READY:",
    "YES" if brti_ready else "NO",
)
print(
    "BRTI AGREES WITH MODEL:",
    "YES" if brti_agrees else "NO",
)

print()
print("=== COMBINED 15-MIN VERDICT ===")

if combined_ready:
    print("STATUS: READY")
    print("FINAL 15-MIN:", direction)
    print(
        "Reason: strict model conditions + "
        "BRTI target gate both confirm."
    )
else:
    print("STATUS: WAIT")
    print("CURRENT MODEL LEAN:", direction)

    if not strict_model_ready:
        print("Blocker: strict model conditions not fully met.")

    if inside_brti_wait_zone:
        print(
            "Blocker: BRTI-adjusted BTC is inside "
            "the validated +/-$11 danger zone."
        )

    if (
        adjusted_gap is not None
        and not inside_brti_wait_zone
        and not brti_agrees
    ):
        print(
            "Blocker: BRTI target side disagrees "
            "with model direction."
        )

if model_side_ask is not None:
    print(
        "Kalshi ask on model side:",
        f"{model_side_ask:.4f}",
        f"({model_side_ask:.1%})",
    )

print()
print("=== V3 SAFETY CHECK ===")
print("Orders placed: NO")
print("bot.py changed: NO")
