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
# LIVE 15-MIN MODEL + KALSHI BRIDGE TEST V2
#
# Fix in V2:
#   ONLY selects a contract where:
#       open_time <= now < close_time
#
# If no truly active contract exists, it stops cleanly.
#
# NO ORDERS.
# NO CHANGES TO bot.py.
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
        return None, markets

    market = min(
        active,
        key=lambda m: parse_dt(m.get("close_time")),
    )

    return market, markets


CACHE = Path("btc_35d_live_cache.csv")


def fetch_coinbase_range(start, end, granularity=60):
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

    rows = []
    step_seconds = granularity * 300
    batch_start = start

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

    df["Datetime"] = pd.to_datetime(
        df["Time"],
        unit="s",
        utc=True,
    )

    df = (
        df
        .drop_duplicates("Datetime")
        .sort_values("Datetime")
        .set_index("Datetime")
    )

    return df[["Open", "High", "Low", "Close", "Volume"]]


def load_live_history():
    now = datetime.now(timezone.utc)

    if CACHE.exists():
        print("Using cached BTC history...")

        old = pd.read_csv(
            CACHE,
            index_col="Datetime",
            parse_dates=True,
        )

        if old.index.tz is None:
            old.index = old.index.tz_localize("UTC")
        else:
            old.index = old.index.tz_convert("UTC")

        update_start = old.index.max() - timedelta(minutes=5)

        fresh = fetch_coinbase_range(
            update_start,
            now,
        )

        data = pd.concat([old, fresh])

        data = (
            data[
                ~data.index.duplicated(
                    keep="last"
                )
            ]
            .sort_index()
        )

        cutoff = now - timedelta(days=35)

        data = data[
            data.index >= cutoff
        ]

    else:
        print(
            "First bridge run: "
            "loading 35-day BTC history..."
        )

        data = fetch_coinbase_range(
            now - timedelta(days=35),
            now,
        )

    data.to_csv(
        CACHE,
        index_label="Datetime",
    )

    return data


def build_features(data):
    df = data.copy()

    df["contract_bucket"] = (
        df.index.floor("15min")
    )

    df["contract_start_price"] = (
        df
        .groupby("contract_bucket")["Open"]
        .transform("first")
    )

    df["contract_final_close"] = (
        df
        .groupby("contract_bucket")["Close"]
        .transform("last")
    )

    df["elapsed_minute"] = (
        (
            df.index.to_series(index=df.index)
            - df["contract_bucket"]
        ).dt.total_seconds()
        / 60.0
    )

    df["remaining_minutes"] = (
        15.0 - df["elapsed_minute"]
    )

    df["move_from_start_pct"] = (
        df["Close"]
        / df["contract_start_price"]
        - 1.0
    )

    df["distance_abs"] = (
        df["move_from_start_pct"].abs()
    )

    df["return_1m"] = (
        df["Close"].pct_change(1)
    )

    df["return_3m"] = (
        df["Close"].pct_change(3)
    )

    df["return_5m"] = (
        df["Close"].pct_change(5)
    )

    df["momentum_1m"] = (
        df["return_1m"]
        - df["return_1m"].shift(1)
    )

    df["volatility_5m"] = (
        df["return_1m"]
        .rolling(5)
        .std()
    )

    df["sma_5"] = (
        df["Close"]
        .rolling(5)
        .mean()
    )

    df["sma_distance_5"] = (
        df["Close"]
        / df["sma_5"]
        - 1.0
    )

    df["contract_outcome"] = (
        df["contract_final_close"]
        > df["contract_start_price"]
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

    for col in [
        "return_1m",
        "return_3m",
        "return_5m",
    ]:
        v = row[col]

        if pd.isna(v):
            continue

        if bool(pred) and v > 0:
            hits += 1

        elif (
            (not bool(pred))
            and v < 0
        ):
            hits += 1

    return hits


print(
    "=== LIVE 15-MIN MODEL + "
    "KALSHI BRIDGE V2 ==="
)

kalshi, all_markets = get_current_kalshi_btc()

if kalshi is None:
    print(
        "No truly ACTIVE KXBTC15M "
        "contract found right now."
    )

    print(
        "Open-status markets returned:",
        len(all_markets),
    )

    for m in all_markets[:5]:
        print(
            "candidate:",
            m.get("ticker"),
            "| open:",
            m.get("open_time"),
            "| close:",
            m.get("close_time"),
            "| status:",
            m.get("status"),
        )

    raise SystemExit(
        "Stopped cleanly rather than "
        "selecting an expired contract."
    )


data = load_live_history()

print(
    "BTC 1-minute rows:",
    len(data),
)

df = build_features(data)

current_bucket = (
    df.index[-1].floor("15min")
)

train = df[
    df["contract_bucket"]
    < current_bucket
].dropna(
    subset=FEATURES + ["contract_outcome"]
).copy()

live_contract = df[
    df["contract_bucket"]
    == current_bucket
].dropna(
    subset=FEATURES
).copy()

if train.empty or live_contract.empty:
    raise SystemExit(
        "Not enough BTC data "
        "for bridge test."
    )

print(
    "Training rows:",
    len(train),
)

print(
    "Live contract rows:",
    len(live_contract),
)

print(
    "Training one live model..."
)

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

live_contract["model_pred"] = (
    model.predict(
        live_contract[FEATURES]
    )
)

live_contract["model_conf"] = (
    model.predict_proba(
        live_contract[FEATURES]
    ).max(axis=1)
)

latest = (
    live_contract.iloc[-1]
)

previous = (
    live_contract.iloc[-2]
    if len(live_contract) >= 2
    else None
)

pred = bool(
    latest["model_pred"]
)

direction = (
    "UP"
    if pred
    else "DOWN"
)

confidence = float(
    latest["model_conf"]
)

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

agree = agreement_hits(
    latest,
    pred,
)

distance = float(
    latest["distance_abs"]
)

elapsed = float(
    latest["elapsed_minute"]
)

early_lock = (
    elapsed >= 8
    and elapsed < 10
    and confidence >= 0.95
    and agree >= 3
    and confidence_change is not None
    and confidence_change >= 0
    and distance >= 0.00175
)


target = num(
    kalshi.get("floor_strike")
)

yes_bid = num(
    kalshi.get("yes_bid_dollars")
)

yes_ask = num(
    kalshi.get("yes_ask_dollars")
)

no_bid = num(
    kalshi.get("no_bid_dollars")
)

no_ask = num(
    kalshi.get("no_ask_dollars")
)

open_dt = parse_dt(
    kalshi.get("open_time")
)

close_dt = parse_dt(
    kalshi.get("close_time")
)

now = datetime.now(timezone.utc)

seconds_left = max(
    0,
    int(
        (
            close_dt - now
        ).total_seconds()
    ),
)

seconds_elapsed = max(
    0,
    int(
        (
            now - open_dt
        ).total_seconds()
    ),
)

btc_spot = float(
    latest["Close"]
)

target_gap_dollars = (
    btc_spot - target
    if target is not None
    else None
)

target_gap_pct = (
    target_gap_dollars / target
    if target is not None
    and target != 0
    else None
)

model_side_ask = (
    yes_ask
    if direction == "UP"
    else no_ask
)


print()
print(
    "=== ACTIVE KALSHI CONTRACT ==="
)

print(
    "Ticker:",
    kalshi.get("ticker"),
)

print(
    "Title:",
    kalshi.get("title"),
)

print(
    "Target:",
    f"${target:,.2f}"
    if target is not None
    else "UNKNOWN",
)

print(
    "Open:",
    kalshi.get("open_time"),
)

print(
    "Close:",
    kalshi.get("close_time"),
)

print(
    "Contract elapsed:",
    f"{seconds_elapsed // 60}m "
    f"{seconds_elapsed % 60}s",
)

print(
    "Time remaining:",
    f"{seconds_left // 60}m "
    f"{seconds_left % 60}s",
)


print()
print(
    "=== KALSHI LIVE ODDS ==="
)

print(
    "UP bid/ask:",
    yes_bid,
    "/",
    yes_ask,
)

print(
    "DOWN bid/ask:",
    no_bid,
    "/",
    no_ask,
)


print()
print(
    "=== BTC / TARGET TRACK ==="
)

print(
    "BTC reference:",
    f"${btc_spot:,.2f}",
)

print(
    "BTC vs Kalshi target:",
    f"${target_gap_dollars:+,.2f}"
    if target_gap_dollars is not None
    else "UNKNOWN",
)

print(
    "Target gap %:",
    f"{target_gap_pct:+.3%}"
    if target_gap_pct is not None
    else "UNKNOWN",
)


print()
print(
    "=== VALIDATED 15-MIN MODEL TRACK ==="
)

print(
    "Model direction:",
    direction,
)

print(
    "Model confidence:",
    f"{confidence:.1%}",
)

print(
    "Elapsed model minute:",
    f"{elapsed:.0f}",
)

print(
    "BTC distance from BTC 15m start:",
    f"{distance:.3%}",
)

print(
    "Directional agreement:",
    f"{agree}/3",
)

print(
    "Confidence strengthening:",
    "YES"
    if (
        confidence_change is not None
        and confidence_change >= 0
    )
    else "NO",
)

print(
    "Confidence change 1m:",
    f"{confidence_change:+.4f}"
    if confidence_change is not None
    else "N/A",
)


print()
print(
    "=== STRICT EARLY_LOCK CHECK ==="
)

print(
    "EARLY_LOCK:",
    "YES"
    if early_lock
    else "NO / WAIT",
)

if model_side_ask is not None:
    print(
        "Kalshi ask on model side:",
        f"{model_side_ask:.4f}",
        f"({model_side_ask:.1%})",
    )

    raw_edge = (
        confidence
        - model_side_ask
    )

    print(
        "Raw model-vs-Kalshi gap:",
        f"{raw_edge:+.1%}",
    )

    print(
        "NOTE: raw gap is diagnostic only "
        "until BRTI/Kalshi-target "
        "calibration is validated."
    )


print()
print(
    "=== BRIDGE V2 VERDICT ==="
)

print(
    "Active Kalshi contract selection: PASSED"
)

print(
    "Model track and Kalshi contract "
    "track are both live."
)

print(
    "NO orders placed."
)

print(
    "NO changes to bot.py."
)
