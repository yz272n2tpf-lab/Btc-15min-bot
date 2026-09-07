from sklearn.model_selection import TimeSeriesSplit
timeframes = ["15m", "10m", "5m", "4m", "3m", "1m", "45s", "30s", "15s", "10s", "5s"]
print(timeframes)
roles = {"15m": "trend", "10m": "trend", "5m": "decision", "4m": "momentum", "3m": "momentum", "1m": "trigger", "45s": "short", "30s": "short", "15s": "short", "10s": "short", "5s": "short"}
print(roles)
import requests
import base64
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding
import pandas as pd
import numpy as np
import re
from zoneinfo import ZoneInfo
from sklearn.linear_model import LogisticRegression
import time
import csv
from datetime import datetime, timezone, timedelta
KALSHI_KEY_ID = Path.home().joinpath(".kalshi/key_id").read_text().strip()
KALSHI_PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"
kalshi_private_key = serialization.load_pem_private_key(
    KALSHI_PRIVATE_KEY_PATH.read_bytes(),
            password=None,

)
KALSHI_BASE_URL = "https://api.elections.kalshi.com"
def kalshi_headers(method, path):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method.upper() + path

    signature = kalshi_private_key.sign(
        message.encode("utf-8"),
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )

    signature_b64 = base64.b64encode(signature).decode("utf-8")

    return {
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": signature_b64,
        "KALSHI-ACCESS-TIMESTAMP": timestamp,
    }


def kalshi_get(path, params=None):
    response = requests.get(
        KALSHI_BASE_URL + path,
        headers=kalshi_headers("GET", path),
        params=params,
        timeout=10,
    )
    response.raise_for_status()
    return response.json()
             
def get_kalshi_btc_markets():
    data = kalshi_get(
        "/trade-api/v2/markets",
        params={
            "status": "open",
                    "series_ticker": "KXBTC15M",
            "limit": 1000,
        },
    )

    markets = data.get("markets", [])

    btc_markets = []
    for market in markets:
        text = " ".join(
            str(market.get(key, ""))
            for key in ["ticker", "title", "subtitle", "event_ticker"]
        ).upper()

        if "BTC" in text or "BITCOIN" in text:
            btc_markets.append(market)

    return btc_markets

def get_live_kalshi_snapshot():
    markets = get_kalshi_btc_markets()
    if not markets:
        return None

    market = markets[0]

    return {
        "ticker": market.get("ticker"),
        "close_time": market.get("close_time"),
        "up_bid": market.get("yes_bid_dollars"),
        "up_ask": market.get("yes_ask_dollars"),
        "down_bid": market.get("no_bid_dollars"),
        "down_ask": market.get("no_ask_dollars"),
    }
def coinbase_history(days, granularity):
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days)

    rows = []
    batch_seconds = granularity * 300
    batch_start = start

    while batch_start < end:
        batch_end = min(
            batch_start + timedelta(seconds=batch_seconds),
            end
        )

        params = {
            "granularity": granularity,
            "start": batch_start.isoformat(),
            "end": batch_end.isoformat(),
        }

        response = requests.get(url, params=params, timeout=20)
        response.raise_for_status()
        rows.extend(response.json())

        batch_start = batch_end
        time.sleep(0.15)

    df = pd.DataFrame(
        rows,
        columns=["Time", "Low", "High", "Open", "Close", "Volume"]
    )

    df["Datetime"] = pd.to_datetime(df["Time"], unit="s", utc=True)
    df = df.drop_duplicates("Datetime").sort_values("Datetime")
    df = df.set_index("Datetime")

    return df[["Open", "High", "Low", "Close", "Volume"]]


data = coinbase_history(5, 900)
print(data.tail())
print("BTC data rows:", len(data))
if data.empty:
    raise SystemExit("ERROR: Yahoo returned no BTC data")
print("Current BTC price:", "NO DATA" if data.empty else data.iloc[-1]["Close"])
print("Data rows:", len(data))
data["SMA20"] = data["Close"].rolling(20).mean()
print("SMA20:", data.iloc[-1]["SMA20"])
difference = data.iloc[-1]["Close"] - data.iloc[-1]["SMA20"]
if data.iloc[-1]["Close"] > data.iloc[-1]["SMA20"]:
    print("Signal: BULLISH")
else:
    print("Signal: BEARISH")
print("Distance from SMA20:", difference)
from datetime import datetime, timezone
from datetime import timedelta
now = datetime.now(timezone.utc)
contract_start = now.replace(minute=(now.minute // 15) * 15, second=0, microsecond=0)
contract_end = contract_start + timedelta(minutes=15)
print("Contract start:", contract_start)
("Contract end:", contract_end)
start_price = data.iloc[-1]["Open"]
print("15-minute start price:", start_price)
move_from_start = data.iloc[-1]["Close"] - start_price
print("Move from 15-minute start:", move_from_start)
move_percent = (move_from_start / start_price) * 100
print("Move from start (%):", move_percent)
recent_change = data.iloc[-1]["Close"] - data.iloc[-2]["Close"]
print("Recent 15-minute change:", recent_change)
data_1m = coinbase_history(5, 60)
one_minute_change = data_1m.iloc[-1]["Close"] - data_1m.iloc[-2]["Close"]
print("1-minute change:", one_minute_change)
five_minute_change = data_1m.iloc[-1]["Close"] - data_1m.iloc[-6]["Close"]
print("5-minute change:", five_minute_change)
previous_1m_change = data_1m.iloc[-2]["Close"] - data_1m.iloc[-3]["Close"]
print("Previous 1-minute change:", previous_1m_change)
momentum_change = one_minute_change - previous_1m_change
print("1-minute momentum change:", momentum_change)
direction_score = move_from_start + one_minute_change + five_minute_change
print("Direction score:", direction_score)
training_data = coinbase_history(60, 900)
print("Training rows:", len(training_data))
training_data["future_open"] = training_data["Open"].shift(-1)
training_data["future_close"] = training_data["Close"].shift(-1)

training_data["outcome"] = (
    training_data["future_close"] > training_data["future_open"]
)

training_data = training_data.dropna(
    subset=["future_open", "future_close"]
)
print("UP outcomes:", training_data["outcome"].sum())
print("DOWN outcomes:", (~training_data["outcome"]).sum())



# Predictive 15-minute features
model_data = training_data.copy()

model_data["return_1"] = model_data["Close"].pct_change(1)
model_data["return_3"] = model_data["Close"].pct_change(3)
model_data["return_5"] = model_data["Close"].pct_change(5)
model_data["body_strength"] = (
    (model_data["Close"] - model_data["Open"]) /
    (model_data["High"] - model_data["Low"])
)
model_data["range_percent"] = (
    (model_data["High"] - model_data["Low"]) /
    model_data["Open"]
)
model_data["body_strength"] = model_data["body_strength"].replace([float("inf"), float("-inf")], 0)
model_data["sma_5"] = model_data["Close"].rolling(5).mean()
model_data["sma_20"] = model_data["Close"].rolling(20).mean()

model_data["sma_distance"] = (
    model_data["Close"] / model_data["sma_20"] - 1
)

model_data["trend_5_20"] = (
    model_data["sma_5"] / model_data["sma_20"] - 1
)

model_data["acceleration"] = (
    model_data["return_1"] - model_data["return_3"] / 3
)

model_data["volatility"] = model_data["return_1"].rolling(6).std()
model_data["momentum_3"] = model_data["Close"].pct_change(3)
    


feature_columns = [
"return_3",
"body_strength",
"trend_5_20",  
"sma_distance",    
"acceleration",
"momentum_3",
] 
model_data = model_data.dropna(
    subset=feature_columns + ["outcome"]
).copy()
walk_forward_splits = [0.60, 0.70, 0.80]
split_index = int(len(model_data) * walk_forward_splits[-2])

train_data = model_data.iloc[:split_index]
test_data = model_data.iloc[split_index:]
print("Current split:", walk_forward_splits[-1], "| Train:", len(train_data), "| Test:", len(test_data))
X_train = train_data[feature_columns]
y_train = train_data["outcome"]

X_test = test_data[feature_columns]
y_test = test_data["outcome"]

print("Model train rows:", len(X_train))
print("Model test rows:", len(X_test))
print("Target balance:", y_test.mean())
from sklearn.ensemble import RandomForestClassifier, HistGradientBoostingClassifier
from sklearn.metrics import accuracy_score

model = RandomForestClassifier(
    n_estimators=1200,
    max_depth=8,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

pred = model.predict(X_test)

model_accuracy = accuracy_score(y_test, pred)

print("Model accuracy:", model_accuracy)
probabilities = model.predict_proba(X_test)

confidence = probabilities.max(axis=1)

high_confidence = confidence >= 0.70

high_conf_accuracy = (
    pred[high_confidence] == y_test.iloc[high_confidence]
).mean()

print("High-confidence trades:", high_confidence.sum())
print("High-confidence accuracy:", high_conf_accuracy)
for threshold in [0.55, 0.60, 0.65, 0.69, 0.70, 0.75, 0.80]:
    mask = confidence >= threshold
    if mask.sum() > 0:
        acc = (pred[mask] == y_test.iloc[mask]).mean()
        print(f"Threshold {threshold}: {mask.sum()} trades, accuracy {acc:.3f}")
walk_forward_windows = [
    (0.60, 0.70),
    (0.70, 0.80),
    (0.80, 1.00),
]
walk_forward_results = []
threshold_summary = {
    0.55: {"correct": 0, "total": 0},
    0.60: {"correct": 0, "total": 0},
    0.65: {"correct": 0, "total": 0},
    0.70: {"correct": 0, "total": 0},
}
for train_end, test_end in walk_forward_windows:
        train_end_idx = int(len(model_data) * train_end)
        test_end_idx = int(len(model_data) * test_end)

        wf_train = model_data.iloc[:train_end_idx]
        wf_test = model_data.iloc[train_end_idx:test_end_idx]
        wf_X_train = wf_train[feature_columns]
        wf_y_train = wf_train["outcome"]

        wf_X_test = wf_test[feature_columns]
        wf_y_test = wf_test["outcome"]
        wf_model = RandomForestClassifier(
    n_estimators=1200,
    max_depth=8,
    random_state=42,
    class_weight="balanced"
)

        wf_model.fit(wf_X_train, wf_y_train)
        wf_pred = wf_model.predict(wf_X_test)
        wf_accuracy = accuracy_score(wf_y_test, wf_pred)
        wf_probabilities = wf_model.predict_proba(wf_X_test)
        wf_confidence = wf_probabilities.max(axis=1)
        wf_test = wf_test.copy()
        
        wf_test["wf_pred"] = wf_pred
        wf_test["correct"] = wf_test["wf_pred"] == wf_test["outcome"]
        wf_test["trend_aligned"] = ((wf_test["wf_pred"] == 1) & (wf_test["trend_5_20"] > 0)) | ((wf_test["wf_pred"] == 0) & (wf_test["trend_5_20"] < 0))
        for wf_threshold in [0.55, 0.60, 0.65, 0.70]:
         wf_high_confidence = wf_confidence >= wf_threshold
         print("WF TEST COLUMNS:", wf_test.columns.tolist())
         wf_distance = ((wf_test["Close"] - wf_test["Open"]) / wf_test["Open"]).abs().to_numpy()
         wf_far_mask = wf_distance >= 0.002
         wf_far_high_confidence = wf_high_confidence & wf_far_mask
         wf_far_total = wf_far_high_confidence.sum()
         wf_far_correct = (wf_pred[wf_far_high_confidence] == wf_y_test.iloc[wf_far_high_confidence]).sum()
         if wf_threshold == 0.60:
          print(">>> WF FAR:", wf_far_total, "correct:", wf_far_correct, "threshold:", wf_threshold)
         wf_trend_aligned = wf_test["trend_aligned"].to_numpy()
         wf_trend_high_confidence = wf_high_confidence & wf_trend_aligned
         wf_trend_total = wf_trend_high_confidence.sum()
         wf_trend_correct = (wf_pred[wf_trend_high_confidence] == wf_y_test.iloc[wf_trend_high_confidence]).sum()
         print("WF TREND-ALIGNED:", wf_trend_total, "correct:", wf_trend_correct)
         wf_trend_up = wf_trend_high_confidence & (wf_pred == 1)
         wf_trend_down = wf_trend_high_confidence & (wf_pred == 0)
         wf_trend_up_correct = (wf_pred[wf_trend_up] == wf_y_test.iloc[wf_trend_up]).sum()
         wf_trend_down_correct = (wf_pred[wf_trend_down] == wf_y_test.iloc[wf_trend_down]).sum()
         print("WF TREND UP:", wf_trend_up.sum(), "correct:", wf_trend_up_correct, "| TREND DOWN:", wf_trend_down.sum(), "correct:", wf_trend_down_correct)
         wf_high_conf_pred = wf_pred[wf_high_confidence]
         wf_high_conf_accuracy = (wf_pred[wf_high_confidence] == wf_y_test.iloc[wf_high_confidence]).mean()
         wf_high_conf_actual = wf_y_test.iloc[wf_high_confidence]
         wf_up_mask = wf_high_conf_pred == 1
         wf_down_mask = wf_high_conf_pred == 0
         wf_up_correct = (wf_high_conf_pred[wf_up_mask] == wf_high_conf_actual.iloc[wf_up_mask]).sum()
         wf_down_correct = (wf_high_conf_pred[wf_down_mask] == wf_high_conf_actual.iloc[wf_down_mask]).sum()
         wf_up_total = wf_up_mask.sum()
         wf_down_total = wf_down_mask.sum()
         print("WF UP:", wf_up_total, "correct:", wf_up_correct, "| DOWN:", wf_down_total, "correct:", wf_down_correct)
         threshold_summary[wf_threshold]["total"] += int(wf_high_confidence.sum())
         threshold_summary[wf_threshold]["correct"] += int((wf_pred[wf_high_confidence] == wf_y_test.iloc[wf_high_confidence]).sum())
         print(
    
        f"WF {train_end:.2f}->{test_end:.2f} threshold {wf_threshold:.2f} high-confidence: "
        f"{wf_high_confidence.sum()} trades, accuracy {wf_high_conf_accuracy}"

         )
        walk_forward_results.append(wf_accuracy)

        print(
    f"Walk-forward {train_end:.2f} -> {test_end:.2f}: "
    f"{len(wf_test)} rows, accuracy {wf_accuracy:.3f}"
        )  
        print("\n=== WALK-FORWARD THRESHOLD SUMMARY ===")
for t, stats in threshold_summary.items():
    total = stats["total"]
    correct = stats["correct"]
    accuracy = correct / total if total else 0
    print(f"{t:.2f}: {correct}/{total} = {accuracy:.3f}")
# Live 15-minute prediction
live_data = data.copy()

live_data["return_1"] = live_data["Close"].pct_change(1)
live_data["return_3"] = live_data["Close"].pct_change(3)
live_data["return_5"] = live_data["Close"].pct_change(5)

live_data["sma_5"] = live_data["Close"].rolling(5).mean()
live_data["sma_20"] = live_data["Close"].rolling(20).mean()

live_data["sma_distance"] = (
    live_data["Close"] / live_data["sma_20"] - 1
)

live_data["trend_5_20"] = (
    live_data["sma_5"] / live_data["sma_20"] - 1
)

live_data["acceleration"] = (
    live_data["return_1"] - live_data["return_3"]
) / 3

live_data["volatility"] = (
    live_data["return_1"].rolling(6).std()
)

live_data["momentum_3"] = (
    live_data["Close"].pct_change(3)
)
live_data["body_strength"] = (
    (live_data["Close"] - live_data["Open"]) /
    (live_data["High"] - live_data["Low"])
)
print("MISSING VALUES:", live_data[feature_columns].isna().sum())
print("LIVE ROWS:", len(live_data))
live_valid = live_data.dropna(
    subset=feature_columns
).copy()
print("LIVE VALID ROWS:", len(live_valid))
print("LIVE COLUMNS:", list(live_valid.columns))

if live_valid.empty:
    print("Not enough data for live prediction.")
else:
    current_features = live_valid.loc[[live_valid.index[-1]], feature_columns]
    current_prediction = model.predict(current_features)[0]
    current_probabilities = model.predict_proba(current_features)[0]
    current_confidence = current_probabilities.max()

    print("Current 15-minute prediction:",
          "UP" if current_prediction else "DOWN")

    print("Current 15-minute confidence:",
          round(current_confidence, 3))


# === V3 BRTI/KALSHI SAFETY GATE START ===
# Validated target-safety layer.
# Signal-only. This block NEVER places orders.

V3_BRTI_BUFFER_DOLLARS = 11.0
_v3_brti_gate_ready = False
_v3_brti_agrees = False
_v3_inside_wait_zone = True
_v3_adjusted_gap = None
_v3_brti_direction = "UNKNOWN"
_v3_target = None
_v3_status = "WAIT"

try:
    _v3_cal = pd.read_csv("brti_calibration_results.csv")

    _v3_errors = pd.concat(
        [
            _v3_cal["target_cb_hl2"] - _v3_cal["target_brti"],
            _v3_cal["final_cb_hl2"] - _v3_cal["final_brti"],
        ],
        ignore_index=True,
    )

    _v3_brti_bias = float(_v3_errors.mean())

    _v3_markets = get_kalshi_btc_markets()
    _v3_now = datetime.now(timezone.utc)
    _v3_active = []

    for _v3_market in _v3_markets:
        _v3_ticker = str(_v3_market.get("ticker", ""))

        if not _v3_ticker.startswith("KXBTC15M"):
            continue

        _v3_open_raw = _v3_market.get("open_time")
        _v3_close_raw = _v3_market.get("close_time")

        if not _v3_open_raw or not _v3_close_raw:
            continue

        try:
            _v3_open = datetime.fromisoformat(
                str(_v3_open_raw).replace("Z", "+00:00")
            )
            _v3_close = datetime.fromisoformat(
                str(_v3_close_raw).replace("Z", "+00:00")
            )
        except Exception:
            continue

        if _v3_open <= _v3_now < _v3_close:
            _v3_active.append((_v3_close, _v3_market))

    if _v3_active:
        _v3_active.sort(key=lambda x: x[0])
        _v3_market = _v3_active[0][1]

        try:
            _v3_target = float(_v3_market.get("floor_strike"))
        except (TypeError, ValueError):
            _v3_target = None

        _v3_latest_row = data_1m.iloc[-1]
        _v3_coinbase_hl2 = (
            float(_v3_latest_row["High"])
            + float(_v3_latest_row["Low"])
        ) / 2.0

        _v3_estimated_brti = _v3_coinbase_hl2 - _v3_brti_bias

        if _v3_target is not None:
            _v3_adjusted_gap = _v3_estimated_brti - _v3_target
            _v3_inside_wait_zone = (
                abs(_v3_adjusted_gap) <= V3_BRTI_BUFFER_DOLLARS
            )

            if _v3_adjusted_gap > 0:
                _v3_brti_direction = "UP"
            elif _v3_adjusted_gap < 0:
                _v3_brti_direction = "DOWN"
            else:
                _v3_brti_direction = "FLAT"

            _v3_model_direction = (
                "UP" if bool(current_prediction) else "DOWN"
            )

            _v3_brti_agrees = (
                _v3_brti_direction == _v3_model_direction
            )

            _v3_brti_gate_ready = (
                (not _v3_inside_wait_zone)
                and _v3_brti_agrees
            )

    if _v3_brti_gate_ready:
        _v3_status = "BRTI GATE READY"
    else:
        _v3_status = "WAIT"

except Exception as _v3_error:
    _v3_status = "WAIT"
    _v3_brti_gate_ready = False
    _v3_error_text = str(_v3_error)

print("\n--- V3 BRTI / KALSHI SAFETY GATE ---")
print("Validated BRTI buffer: +/-$11.00")
print(
    "Kalshi target:",
    f"${_v3_target:,.2f}" if _v3_target is not None else "UNKNOWN",
)
print(
    "Adjusted BRTI gap:",
    f"${_v3_adjusted_gap:+.2f}"
    if _v3_adjusted_gap is not None
    else "UNKNOWN",
)
print("BRTI direction:", _v3_brti_direction)
print(
    "Inside +/-$11 WAIT zone:",
    "YES" if _v3_inside_wait_zone else "NO",
)
print(
    "BRTI agrees with 15-min model:",
    "YES" if _v3_brti_agrees else "NO",
)
print(
    "BRTI gate ready:",
    "YES" if _v3_brti_gate_ready else "NO",
)
print("V3 safety status:", _v3_status)

if "_v3_error_text" in globals():
    print("V3 safety note:", _v3_error_text)

# === V3 BRTI/KALSHI SAFETY GATE END ===

# === STRICT 15M + V3 COMBINED READY START ===
# Final 15-minute signal gate.
# Signal-only: NEVER places orders.

_strict_model_ready = False
_strict_elapsed_minute = None
_strict_distance = None
_strict_agreement = 0
_strict_conf_change = None
_final_15m_ready = False
_model_15m_direction = "UP" if bool(current_prediction) else "DOWN"

# Final-outcome direction must be Kalshi-target-aware.
if _v3_brti_direction in ("UP", "DOWN"):
    _final_15m_direction = _v3_brti_direction
else:
    _final_15m_direction = _model_15m_direction


try:
    # Use the ACTUAL active Kalshi contract clock.
    _strict_now_ts = pd.Timestamp(datetime.now(timezone.utc))

    _strict_kalshi_markets = get_kalshi_btc_markets()
    _strict_active_market = None
    _strict_active_close = None

    for _strict_market in _strict_kalshi_markets:
        _strict_ticker = str(_strict_market.get("ticker", ""))

        if not _strict_ticker.startswith("KXBTC15M"):
            continue

        _strict_open_raw = _strict_market.get("open_time")
        _strict_close_raw = _strict_market.get("close_time")

        if not _strict_open_raw or not _strict_close_raw:
            continue

        try:
            _strict_open_ts = pd.Timestamp(_strict_open_raw)
            _strict_close_ts = pd.Timestamp(_strict_close_raw)

            if _strict_open_ts.tzinfo is None:
                _strict_open_ts = _strict_open_ts.tz_localize("UTC")
            else:
                _strict_open_ts = _strict_open_ts.tz_convert("UTC")

            if _strict_close_ts.tzinfo is None:
                _strict_close_ts = _strict_close_ts.tz_localize("UTC")
            else:
                _strict_close_ts = _strict_close_ts.tz_convert("UTC")

        except Exception:
            continue

        if _strict_open_ts <= _strict_now_ts < _strict_close_ts:
            if (
                _strict_active_market is None
                or _strict_close_ts < _strict_active_close
            ):
                _strict_active_market = _strict_market
                _strict_active_close = _strict_close_ts
                _strict_active_open = _strict_open_ts

    if _strict_active_market is None:
        raise RuntimeError("No active Kalshi BTC 15-minute contract found.")

    _strict_elapsed_minute = (
        (_strict_now_ts - _strict_active_open).total_seconds() / 60.0
    )

    # Use Kalshi contract open time for the BTC start window.
    _strict_bucket = _strict_active_open

    _strict_data = data_1m.copy()

    if _strict_data.index.tz is None:
        _strict_data.index = _strict_data.index.tz_localize("UTC")
    else:
        _strict_data.index = _strict_data.index.tz_convert("UTC")

    _strict_contract_rows = _strict_data[
        (_strict_data.index >= _strict_bucket)
        & (_strict_data.index < _strict_bucket + pd.Timedelta(minutes=15))
    ]

    if not _strict_contract_rows.empty:
        _strict_start_price = float(_strict_contract_rows.iloc[0]["Open"])
        _strict_latest_close = float(_strict_contract_rows.iloc[-1]["Close"])
        _strict_distance = abs(
            _strict_latest_close / _strict_start_price - 1.0
        )

    _strict_closes = _strict_data["Close"].astype(float)

    _strict_r1 = (
        _strict_closes.iloc[-1] / _strict_closes.iloc[-2] - 1.0
        if len(_strict_closes) >= 2 else 0.0
    )
    _strict_r3 = (
        _strict_closes.iloc[-1] / _strict_closes.iloc[-4] - 1.0
        if len(_strict_closes) >= 4 else 0.0
    )
    _strict_r5 = (
        _strict_closes.iloc[-1] / _strict_closes.iloc[-6] - 1.0
        if len(_strict_closes) >= 6 else 0.0
    )

    _strict_pred_up = bool(current_prediction)

    for _strict_ret in (_strict_r1, _strict_r3, _strict_r5):
        if _strict_pred_up and _strict_ret > 0:
            _strict_agreement += 1
        elif (not _strict_pred_up) and _strict_ret < 0:
            _strict_agreement += 1

    if len(live_valid) >= 2:
        _strict_prev_features = live_valid.loc[
            [live_valid.index[-2]],
            feature_columns,
        ]
        _strict_prev_prob = model.predict_proba(
            _strict_prev_features
        )[0]
        _strict_prev_conf = float(_strict_prev_prob.max())
        _strict_conf_change = float(current_confidence) - _strict_prev_conf

    _strict_model_ready = (
        _strict_elapsed_minute is not None
        and 8.0 <= _strict_elapsed_minute < 10.0
        and float(current_confidence) >= 0.95
        and _strict_agreement == 3
        and _strict_conf_change is not None
        and _strict_conf_change >= 0.0
        and _strict_distance is not None
        and _strict_distance >= 0.00175
    )

    # Entry readiness remains strict.
    _final_15m_ready = (
        _strict_model_ready
        and bool(_v3_brti_gate_ready)
        and (_model_15m_direction == _final_15m_direction)
    )

except Exception as _strict_error:
    _strict_model_ready = False
    _final_15m_ready = False
    _strict_error_text = str(_strict_error)


print("\n--- FINAL GATE CONTRACT AUDIT ---")

try:
    _audit_market = _strict_active_market

    _audit_ticker = str(_audit_market.get("ticker", "UNKNOWN"))
    _audit_open = _audit_market.get("open_time")
    _audit_close = _audit_market.get("close_time")

    try:
        _audit_target = float(_audit_market.get("floor_strike"))
    except (TypeError, ValueError):
        _audit_target = None

    _audit_up_bid = _audit_market.get("yes_bid_dollars")
    _audit_up_ask = _audit_market.get("yes_ask_dollars")
    _audit_down_bid = _audit_market.get("no_bid_dollars")
    _audit_down_ask = _audit_market.get("no_ask_dollars")

    print("KALSHI TICKER:", _audit_ticker)
    print("KALSHI OPEN:", _audit_open)
    print("KALSHI CLOSE:", _audit_close)
    print(
        "KALSHI TARGET:",
        f"${_audit_target:,.2f}" if _audit_target is not None else "UNKNOWN",
    )
    print("UP BID/ASK:", _audit_up_bid, "/", _audit_up_ask)
    print("DOWN BID/ASK:", _audit_down_bid, "/", _audit_down_ask)
    print(
        "BRTI-ADJUSTED GAP:",
        f"${_v3_adjusted_gap:+.2f}"
        if _v3_adjusted_gap is not None
        else "UNKNOWN",
    )
    print("BRTI TARGET SIDE:", _v3_brti_direction)
    print("MODEL SIDE:", _model_15m_direction)
    print("EXPECTED FINAL SOURCE: BRTI/KALSHI TARGET SIDE")
    print("EXPECTED FINAL OUTCOME:", _final_15m_direction)

except Exception as _audit_error:
    print("CONTRACT AUDIT ERROR:", str(_audit_error))
    print("EXPECTED FINAL OUTCOME remains fail-closed.")


# === RESTORED TARGET-AWARE FAIR-VALUE ENTRY ENGINE START ===
# This restores the Kalshi-target-aware probability path that was previously
# validated/shadow-tested for entry value. It is separate from the strict
# FINAL CALL gate below and NEVER places orders.
#
# Key distinction:
#   old current_confidence = general 15-minute direction model confidence
#   fair_preferred         = calibrated probability of the ACTIVE Kalshi
#                            contract settling on the preferred side vs target
#
# EARLY OPPORTUNITY uses fair value + ACTUAL Kalshi ask. FINAL CALL remains
# fail-closed on the existing strict gate until separately revalidated.

_fair_ready = False
_fair_error_text = None
_fair_up = None
_fair_down = None
_fair_preferred_side = None
_fair_preferred = None
_fair_flip_prob = None
_fair_stay_prob = None
_fair_raw_flip = None
_fair_up_ask = None
_fair_down_ask = None
_fair_preferred_ask = None
_fair_edge = None
_fair_current_side = None
_fair_distance_target = None
_fair_dist_over_range5 = None
_fair_calibration_contracts = 0
_fair_calibration_snapshots = 0

try:
    _fair_cal = _v3_cal.copy()

    # Use the same 35-day BTC history base as the standalone fair-value
    # monitor that was validated successfully. Merge in the bot's freshest
    # 1-minute rows so live calculations stay current without requiring a
    # second fetch path.
    _fair_cache_path = Path("btc_35d_live_cache.csv")
    if _fair_cache_path.exists():
        _fair_cached = pd.read_csv(
            _fair_cache_path,
            index_col="Datetime",
            parse_dates=True,
        )
        if _fair_cached.index.tz is None:
            _fair_cached.index = _fair_cached.index.tz_localize("UTC")
        else:
            _fair_cached.index = _fair_cached.index.tz_convert("UTC")

        _fair_live_rows = data_1m.copy()
        if _fair_live_rows.index.tz is None:
            _fair_live_rows.index = _fair_live_rows.index.tz_localize("UTC")
        else:
            _fair_live_rows.index = _fair_live_rows.index.tz_convert("UTC")

        _fair_btc = pd.concat([_fair_cached, _fair_live_rows])
        _fair_btc = (
            _fair_btc[~_fair_btc.index.duplicated(keep="last")]
            .sort_index()
        )
        _fair_cutoff = pd.Timestamp(datetime.now(timezone.utc)) - pd.Timedelta(days=35)
        _fair_btc = _fair_btc[_fair_btc.index >= _fair_cutoff]
    else:
        _fair_btc = data_1m.copy()

    if _fair_btc.index.tz is None:
        _fair_btc.index = _fair_btc.index.tz_localize('UTC')
    else:
        _fair_btc.index = _fair_btc.index.tz_convert('UTC')

    for _c in ['Open','High','Low','Close','Volume']:
        if _c in _fair_btc.columns:
            _fair_btc[_c] = pd.to_numeric(_fair_btc[_c], errors='coerce')

    _fair_months = {m:i+1 for i,m in enumerate(
        ['JAN','FEB','MAR','APR','MAY','JUN','JUL','AUG','SEP','OCT','NOV','DEC']
    )}

    def _fair_parse_contract_times(_ticker):
        _m = re.search(
            r'KXBTC15M-(\d{2})([A-Z]{3})(\d{2})(\d{2})(\d{2})-',
            str(_ticker).upper(),
        )
        if not _m:
            return pd.NaT, pd.NaT
        _yy, _mon, _dd, _hh, _mm = _m.groups()
        _wall = pd.Timestamp(
            year=2000+int(_yy), month=_fair_months[_mon], day=int(_dd),
            hour=int(_hh), minute=int(_mm),
        )
        _close = _wall.tz_localize(ZoneInfo('America/New_York')).tz_convert('UTC')
        return _close-pd.Timedelta(minutes=15), _close

    def _fair_price_at_or_before(_df, _ts):
        _i = _df.index.searchsorted(_ts, side='right') - 1
        if _i < 0:
            return np.nan, pd.NaT
        _ti = _df.index[_i]
        if _ts - _ti > pd.Timedelta(minutes=2):
            return np.nan, pd.NaT
        return float(_df.iloc[_i]['Close']), _ti

    def _fair_build_snapshot(_df, _start, _target, _final_side=None, _elapsed=None, _cut=None):
        if _cut is None:
            _cut = _start + pd.Timedelta(minutes=float(_elapsed))
        _elapsed_actual = (_cut-_start).total_seconds()/60.0
        _pstart, _tstart = _fair_price_at_or_before(_df, _start)
        _vals = [
            _fair_price_at_or_before(_df, _cut-pd.Timedelta(minutes=_m))
            for _m in [0,1,2,3,5]
        ]
        if pd.isna(_pstart) or any(pd.isna(_v[0]) for _v in _vals):
            return None
        _p0,_p1,_p2,_p3,_p5 = [_v[0] for _v in _vals]
        _w = _df.loc[(_df.index > _cut-pd.Timedelta(minutes=5)) & (_df.index <= _cut)]
        if len(_w) < 3:
            return None
        _closes = _w['Close'].dropna()
        if len(_closes) < 2:
            return None
        _latest_used = max([_tstart] + [_v[1] for _v in _vals] + [_w.index.max()])
        if _latest_used > _cut:
            raise RuntimeError('FAIR ENGINE FUTURE DATA DETECTED')

        _current_side = int(_p0 >= _target)
        _dist = _p0-_target
        _abs_dist = abs(_dist)
        _remaining = max(0.0, 15.0-_elapsed_actual)
        _sign = 1.0 if _current_side == 1 else -1.0
        _move1 = _p0-_p1
        _move2 = _p0-_p2
        _move3 = _p0-_p3
        _move5 = _p0-_p5
        _range5 = float(_w['High'].max()-_w['Low'].min())

        _row = {
            'elapsed': float(_elapsed_actual),
            'remaining': float(_remaining),
            'current_side': int(_current_side),
            'dist_target': float(_dist),
            'abs_dist_target': float(_abs_dist),
            'dist_target_pct': float(_dist/_target),
            'move_from_start': float(_p0-_pstart),
            'move_from_start_pct': float((_p0-_pstart)/_pstart),
            'move1': float(_move1), 'move2': float(_move2),
            'move3': float(_move3), 'move5': float(_move5),
            'support1': float(_move1*_sign), 'support2': float(_move2*_sign),
            'support3': float(_move3*_sign), 'support5': float(_move5*_sign),
            'range5': float(_range5),
            'vol5': float(_closes.pct_change().std(ddof=0)),
            'dist_per_min_remaining': float(_abs_dist/max(_remaining,0.25)),
            'dist_over_range5': float(_abs_dist/max(_range5,1.0)),
            'current_coinbase_close': float(_p0),
        }
        if _final_side is not None:
            _row['final_side'] = int(_final_side)
            _row['flip'] = int(int(_final_side) != _current_side)
        return _row

    _fair_features = [
        'elapsed','remaining','current_side',
        'dist_target','abs_dist_target','dist_target_pct',
        'move_from_start','move_from_start_pct',
        'move1','move2','move3','move5',
        'support1','support2','support3','support5',
        'range5','vol5','dist_per_min_remaining','dist_over_range5',
    ]

    _fair_pairs = _fair_cal['ticker'].map(_fair_parse_contract_times)
    _fair_cal['start'] = [_x[0] for _x in _fair_pairs]
    _fair_cal['close'] = [_x[1] for _x in _fair_pairs]
    _fair_cal['target_brti'] = pd.to_numeric(_fair_cal['target_brti'], errors='coerce')
    _fair_cal['final_brti'] = pd.to_numeric(_fair_cal['final_brti'], errors='coerce')
    _fair_cal['final_side'] = (
        _fair_cal['result'].astype(str).str.lower().map({'yes':1,'no':0})
    )
    _fair_cal = _fair_cal.dropna(
        subset=['start','close','target_brti','final_brti','final_side']
    ).sort_values('start').reset_index(drop=True)

    _fair_hist_rows = []
    for _, _r in _fair_cal.iterrows():
        for _elapsed in range(1,15):
            _s = _fair_build_snapshot(
                _fair_btc, _r['start'], float(_r['target_brti']),
                _final_side=int(_r['final_side']), _elapsed=_elapsed,
            )
            if _s is not None:
                _s['ticker'] = _r['ticker']
                _s['start'] = _r['start']
                _fair_hist_rows.append(_s)

    _fair_hist = pd.DataFrame(_fair_hist_rows)
    if _fair_hist.empty:
        raise RuntimeError('No historical fair-value feature rows available')

    _fair_coverage = _fair_hist.groupby('ticker')['elapsed'].nunique()
    _fair_keep = _fair_coverage[_fair_coverage >= 10].index
    _fair_hist = _fair_hist[_fair_hist['ticker'].isin(_fair_keep)].copy()
    _fair_contracts = (
        _fair_hist[['ticker','start']].drop_duplicates('ticker')
        .sort_values('start').reset_index(drop=True)
    )
    # V4.6: exact chronology used by the offline tournament winner.
    # First 50% = RF model training.
    # Next 20%  = sigmoid probability calibration.
    # Final 30% was reserved for validation + untouched holdout and therefore
    # remains excluded from fitting so live behavior matches the tested model.
    _fair_model_end = int(len(_fair_contracts)*0.50)
    _fair_calib_end = int(len(_fair_contracts)*0.70)
    if (
        _fair_model_end <= 0
        or _fair_calib_end <= _fair_model_end
        or _fair_calib_end >= len(_fair_contracts)
    ):
        raise RuntimeError('Not enough contracts for tournament chronology split')

    _fair_model_contracts = _fair_contracts.iloc[:_fair_model_end]
    _fair_calib_contracts = _fair_contracts.iloc[_fair_model_end:_fair_calib_end]
    if _fair_model_contracts['start'].max() >= _fair_calib_contracts['start'].min():
        raise RuntimeError('FAIR ENGINE TRAIN/CALIBRATION CHRONOLOGY FAILURE')

    _fair_model_ticks = set(_fair_model_contracts['ticker'])
    _fair_calib_ticks = set(_fair_calib_contracts['ticker'])
    _fair_train = _fair_hist[_fair_hist['ticker'].isin(_fair_model_ticks)].copy()
    _fair_calibrate = _fair_hist[_fair_hist['ticker'].isin(_fair_calib_ticks)].copy()

    if len(_fair_calib_contracts) < 20:
        raise RuntimeError('FAIR ENGINE SAFETY FAILURE: fewer than 20 calibration contracts in current BTC cache')

    _fair_rf = RandomForestClassifier(
        n_estimators=900, max_depth=9, min_samples_leaf=12,
        class_weight='balanced', random_state=42, n_jobs=-1,
    )
    _fair_rf.fit(_fair_train[_fair_features], _fair_train['flip'])
    _fair_calib_raw = _fair_rf.predict_proba(_fair_calibrate[_fair_features])[:,1]

    _fair_sigmoid = LogisticRegression(
        solver='lbfgs', C=1.0, max_iter=1000, random_state=42,
    )
    _fair_sigmoid.fit(
        _fair_calib_raw.reshape(-1,1), _fair_calibrate['flip'].astype(int)
    )

    _fair_live_start = pd.Timestamp(_strict_active_open)
    if _fair_live_start.tzinfo is None:
        _fair_live_start = _fair_live_start.tz_localize('UTC')
    else:
        _fair_live_start = _fair_live_start.tz_convert('UTC')
    _fair_now = pd.Timestamp(datetime.now(timezone.utc))
    _fair_live = _fair_build_snapshot(
        _fair_btc, _fair_live_start, float(_audit_target), _cut=_fair_now,
    )
    if _fair_live is None:
        raise RuntimeError('Not enough current 1-minute BTC data for fair probability')

    _fair_live_frame = pd.DataFrame([_fair_live])
    _fair_raw_flip = float(_fair_rf.predict_proba(_fair_live_frame[_fair_features])[0,1])
    _fair_flip_prob = float(
        _fair_sigmoid.predict_proba(np.array([[_fair_raw_flip]]))[0,1]
    )
    _fair_flip_prob = float(np.clip(_fair_flip_prob, 0.001, 0.999))
    _fair_stay_prob = 1.0-_fair_flip_prob
    _fair_current_side = int(_fair_live['current_side'])
    _fair_distance_target = float(_fair_live['dist_target'])
    _fair_dist_over_range5 = float(_fair_live['dist_over_range5'])

    if _fair_current_side == 1:
        _fair_up = _fair_stay_prob
        _fair_down = _fair_flip_prob
    else:
        _fair_up = _fair_flip_prob
        _fair_down = _fair_stay_prob

    _fair_preferred_side = 'UP' if _fair_up >= _fair_down else 'DOWN'
    _fair_preferred = max(_fair_up, _fair_down)
    _fair_up_ask = float(_audit_up_ask) if _audit_up_ask is not None else None
    _fair_down_ask = float(_audit_down_ask) if _audit_down_ask is not None else None
    _fair_preferred_ask = _fair_up_ask if _fair_preferred_side == 'UP' else _fair_down_ask
    _fair_edge = (
        _fair_preferred-_fair_preferred_ask
        if _fair_preferred_ask is not None else None
    )
    _fair_calibration_contracts = len(_fair_calib_contracts)
    _fair_calibration_snapshots = len(_fair_calibrate)
    _fair_ready = True

except Exception as _fair_error:
    _fair_ready = False
    _fair_error_text = str(_fair_error)

print('\n--- TARGET-AWARE FAIR-VALUE ENTRY ENGINE ---')
print('READY:', 'YES' if _fair_ready else 'NO')
print('BTC HISTORY SOURCE:', '35-DAY CACHE + FRESH 1M' if Path("btc_35d_live_cache.csv").exists() else 'CURRENT BOT 1M HISTORY ONLY')
if _fair_ready:
    print('FAIR UP:', f'{_fair_up:.1%}')
    print('FAIR DOWN:', f'{_fair_down:.1%}')
    print('PREFERRED SIDE:', _fair_preferred_side)
    print('PREFERRED FAIR:', f'{_fair_preferred:.1%}')
    print('UP ASK:', f'{_fair_up_ask:.0%}' if _fair_up_ask is not None else 'UNKNOWN')
    print('DOWN ASK:', f'{_fair_down_ask:.0%}' if _fair_down_ask is not None else 'UNKNOWN')
    print('PREFERRED-SIDE EDGE:', f'{_fair_edge:+.1%}' if _fair_edge is not None else 'UNKNOWN')
    print('DISTANCE FROM KALSHI TARGET:', f'${_fair_distance_target:+.2f}')
    print('DISTANCE / RECENT 5M RANGE:', f'{_fair_dist_over_range5:.2f}x')
    print('CALIBRATION:', f'{_fair_calibration_contracts} contracts / {_fair_calibration_snapshots} snapshots')
else:
    print('FAIR-VALUE NOTE:', _fair_error_text or 'Unavailable')
# === RESTORED TARGET-AWARE FAIR-VALUE ENTRY ENGINE END ===

# === VALIDATED ONBOARDING LADDER START ===
# Historical validation after corrected Kalshi timing:
# - Minute 8 qualified: minute 7 & 8 agree, both confidence >= 85%.
# - Minute 11 final lock: minute 9 & 11 agree, both >= 85%,
#   OR minute 11 confidence >= 90%.
# Signal-only. This block NEVER places orders and does not alter scalp logic.

_ladder_status = "RAW FORECAST"
_ladder_direction = _model_15m_direction
_ladder_confidence = float(current_confidence)
_ladder_reason = "Every-contract raw 15-minute forecast"
_ladder_contract_ticker = None
_ladder_state_path = Path(".kalshi_15m_ladder_state.json")
_ladder_state = {}

try:
    if _strict_active_market is not None:
        _ladder_contract_ticker = str(
            _strict_active_market.get("ticker", "")
        ) or None

    if _ladder_contract_ticker is not None and _strict_elapsed_minute is not None:
        import json as _ladder_json

        if _ladder_state_path.exists():
            try:
                _ladder_state = _ladder_json.loads(
                    _ladder_state_path.read_text()
                )
            except Exception:
                _ladder_state = {}

        # Never carry checkpoint history from one Kalshi contract into another.
        if _ladder_state.get("ticker") != _ladder_contract_ticker:
            _ladder_state = {
                "ticker": _ladder_contract_ticker,
                "checkpoints": {},
            }

        _ladder_checkpoints = _ladder_state.setdefault("checkpoints", {})
        _ladder_elapsed = float(_strict_elapsed_minute)

        # Capture each checkpoint only once, using the first live run at/after it.
        # A checkpoint is accepted only before the next checkpoint window.
        _ladder_windows = {
            "7": (7.0, 8.0),
            "8": (8.0, 9.0),
            "9": (9.0, 11.0),
            "11": (11.0, 15.0),
        }

        for _cp, (_lo, _hi) in _ladder_windows.items():
            if (
                _cp not in _ladder_checkpoints
                and _ladder_elapsed >= _lo
                and _ladder_elapsed < _hi
            ):
                _ladder_checkpoints[_cp] = {
                    "direction": _model_15m_direction,
                    "confidence": float(current_confidence),
                    "elapsed": _ladder_elapsed,
                }

        # Persist only signal state. No credentials, orders, or account data.
        _ladder_state_path.write_text(
            _ladder_json.dumps(_ladder_state, indent=2)
        )

        _cp7 = _ladder_checkpoints.get("7")
        _cp8 = _ladder_checkpoints.get("8")
        _cp9 = _ladder_checkpoints.get("9")
        _cp11 = _ladder_checkpoints.get("11")

        _minute8_qualified = bool(
            _cp7
            and _cp8
            and _cp7["direction"] == _cp8["direction"]
            and float(_cp7["confidence"]) >= 0.85
            and float(_cp8["confidence"]) >= 0.85
        )

        _minute11_lock = bool(
            _cp11
            and (
                (
                    _cp9
                    and _cp9["direction"] == _cp11["direction"]
                    and float(_cp9["confidence"]) >= 0.85
                    and float(_cp11["confidence"]) >= 0.85
                )
                or float(_cp11["confidence"]) >= 0.90
            )
        )

        # First validated stage wins during the contract.
        if _minute8_qualified:
            _ladder_status = "MINUTE 8 QUALIFIED"
            _ladder_direction = _cp8["direction"]
            _ladder_confidence = float(_cp8["confidence"])
            _ladder_reason = (
                "Minute 7 & 8 agree; both model confidences >=85%"
            )

        # Minute 11 is the stronger/final stage and supersedes minute 8.
        if _minute11_lock:
            _ladder_status = "MINUTE 11 FINAL LOCK"
            _ladder_direction = _cp11["direction"]
            _ladder_confidence = float(_cp11["confidence"])

            if (
                _cp9
                and _cp9["direction"] == _cp11["direction"]
                and float(_cp9["confidence"]) >= 0.85
                and float(_cp11["confidence"]) >= 0.85
            ):
                _ladder_reason = (
                    "Minute 9 & 11 agree; both model confidences >=85%"
                )
            else:
                _ladder_reason = "Minute 11 model confidence >=90%"

except Exception as _ladder_error:
    # Fail closed: preserve raw forecast and never create a false qualified call.
    _ladder_status = "RAW FORECAST"
    _ladder_direction = _model_15m_direction
    _ladder_confidence = float(current_confidence)
    _ladder_reason = f"Ladder state unavailable: {_ladder_error}"

# ============================================================
# TWO-OUTPUT LIVE DECISION VIEW — V4
# EARLY OPPORTUNITY now uses the restored target-aware FAIR probability
# against the ACTUAL Kalshi ask. FINAL uses the locked V4.6 tournament winner.
# ============================================================

_two_up_ask = globals().get('_audit_up_ask')
_two_down_ask = globals().get('_audit_down_ask')
try:
    _two_up_ask = float(_two_up_ask) if _two_up_ask is not None else None
except (TypeError, ValueError):
    _two_up_ask = None
try:
    _two_down_ask = float(_two_down_ask) if _two_down_ask is not None else None
except (TypeError, ValueError):
    _two_down_ask = None

# Prefer the target-aware fair-value engine. Fail closed to the old raw model
# only for display if fair value is temporarily unavailable.
if _fair_ready:
    _opportunity_side = _fair_preferred_side
    _opportunity_model_prob = float(_fair_preferred)
    _opportunity_ask = _fair_preferred_ask
    _opportunity_edge = _fair_edge
else:
    _opportunity_side = _model_15m_direction
    _opportunity_model_prob = float(current_confidence)
    _opportunity_ask = _two_up_ask if _opportunity_side == 'UP' else _two_down_ask
    _opportunity_edge = (
        _opportunity_model_prob-_opportunity_ask
        if _opportunity_ask is not None else None
    )

if _opportunity_ask is None:
    _opportunity_price_zone = 'NO LIVE ASK'
elif _opportunity_ask <= 0.30:
    _opportunity_price_zone = 'DEEP VALUE <=30c'
elif _opportunity_ask <= 0.40:
    _opportunity_price_zone = 'ATTRACTIVE 31-40c'
elif _opportunity_ask <= 0.50:
    _opportunity_price_zone = 'ACCEPTABLE 41-50c'
else:
    _opportunity_price_zone = 'EXPENSIVE / WAIT'

# ============================================================
# V4.7 — EXACT HISTORICAL ENTRY TOURNAMENT WINNER
# ============================================================
# Selected on the 99-contract chronological validation slice.
# Untouched 100-contract entry holdout:
#   90.9% accuracy (20/22), 22% coverage,
#   average ask 31.9c, median ask 34.0c,
#   average time left 6.09m, median 6.00m.
#
# Winner parameters:
#   ask <= 45c
#   target-aware fair >= 75%
#   fair edge vs actual ask >= 8pt
#   2m <= time left <= 10m
#   abs distance from exact Kalshi target >= $25
#   no persistence requirement
#   no strengthening requirement
#   no forced agreement with current target side
#
# ENTRY guidance only — never FINAL CALL authority.
# ============================================================
_entry_tournament_ready = False
_entry_time_left = None
_entry_abs_gap = None

try:
    _entry_time_left = (
        max(0.0, 15.0-float(_strict_elapsed_minute))
        if _strict_elapsed_minute is not None else None
    )
    _entry_abs_gap = (
        abs(float(_fair_distance_target))
        if _fair_distance_target is not None else None
    )

    _entry_tournament_ready = bool(
        _fair_ready
        and _opportunity_ask is not None
        and _opportunity_edge is not None
        and _entry_time_left is not None
        and _entry_abs_gap is not None
        and float(_opportunity_ask) <= 0.45
        and float(_opportunity_model_prob) >= 0.75
        and float(_opportunity_edge) >= 0.08
        and 2.0 <= float(_entry_time_left) <= 10.0
        and float(_entry_abs_gap) >= 25.0
    )
except Exception:
    _entry_tournament_ready = False

if not _fair_ready:
    _opportunity_status = 'WATCH'
    _opportunity_reason = 'Target-aware fair probability unavailable — fail closed'
elif _opportunity_ask is None or _opportunity_edge is None:
    _opportunity_status = 'WATCH'
    _opportunity_reason = 'Waiting for complete live Kalshi ask/fair-value data'
elif _entry_tournament_ready:
    _opportunity_status = 'OPPORTUNITY'
    _opportunity_reason = (
        'ENTRY TOURNAMENT WINNER: ask <=45c, fair >=75%, edge >=8pt, '
        '2-10m left, >=$25 from Kalshi target'
    )
elif _opportunity_ask > 0.50:
    _opportunity_status = 'WAIT'
    _opportunity_reason = 'Preferred side is above the user <=50c entry ceiling'
elif _opportunity_ask > 0.45:
    _opportunity_status = 'VALUE WATCH'
    _opportunity_reason = (
        'Price is <=50c but above the validated <=45c tournament ceiling'
    )
else:
    _opportunity_status = 'WATCH'
    _opportunity_reason = (
        'Price is inside the validated entry ceiling, but one or more '
        'tournament evidence gates have not cleared'
    )

print('\n============================================================')
print('EARLY OPPORTUNITY — TARGET-AWARE / NOT FINAL OUTCOME')
print('============================================================')
print('CONTRACT:', _ladder_contract_ticker or 'UNKNOWN')
print('EARLY SIDE:', _opportunity_side)
print('TARGET-AWARE FAIR:', f'{_opportunity_model_prob:.1%}')
print('RAW GENERAL MODEL:', _model_15m_direction, f'{float(current_confidence):.1%}')
print('FAIR UP / DOWN:',
      (f'{_fair_up:.1%} / {_fair_down:.1%}' if _fair_ready else 'UNAVAILABLE'))
print('LIVE KALSHI ASK:', f'{_opportunity_ask:.0%}' if _opportunity_ask is not None else 'UNKNOWN')
print('MODEL EDGE VS ASK:', f'{_opportunity_edge:+.1%}' if _opportunity_edge is not None else 'UNKNOWN')
print('PRICE ZONE:', _opportunity_price_zone)
print('OPPORTUNITY STATUS:', _opportunity_status)
print('ENTRY TOURNAMENT READY:', 'YES' if _entry_tournament_ready else 'NO')
print(
    'ENTRY TIME WINDOW:',
    f'{_entry_time_left:.2f} min left' if _entry_time_left is not None else 'UNKNOWN'
)
print(
    'ENTRY ABS TARGET GAP:',
    f'${_entry_abs_gap:.2f}' if _entry_abs_gap is not None else 'UNKNOWN'
)
print('VALIDATED ENTRY CEILING: 45c')
print('VALIDATED ENTRY FAIR MIN: 75%')
print('VALIDATED ENTRY EDGE MIN: 8pt')
print('REASON:', _opportunity_reason)
print('FINAL-CALL AUTHORITY: NO — entry/value guidance only')


# ============================================================
# V4.10 DIRECT BRTI AUTHORITY GATE
# ============================================================
# Coinbase remains the prediction/momentum feature source used by the
# historically validated fair-value model.
#
# Direct CF Benchmarks BRTI is the authoritative LIVE Kalshi target-side
# reference. It does not retrain or replace the model. It is an additional
# fail-closed safety gate on the validated FINAL winner:
#   - direct BRTI must be fresh
#   - direct BRTI must be outside the existing +/-$11 wait zone
#   - preferred fair side must agree with the direct BRTI target side
# ============================================================

_direct_brti_authority_ready = False
_direct_brti_authority_value = None
_direct_brti_authority_age = None
_direct_brti_authority_gap = None
_direct_brti_authority_side = None
_direct_brti_authority_error = None
DIRECT_BRTI_AUTH_MAX_AGE_SECONDS = 5.0
DIRECT_BRTI_AUTH_WAIT_DOLLARS = 11.0

def _direct_brti_authority_fetch():
    _path = "/trade-api/v2/cfbenchmarks/latest_values"
    _base = "https://external-api.kalshi.com"
    _resp = requests.get(
        _base + _path,
        headers=kalshi_headers("GET", _path),
        params={"id": "BRTI", "maxResolution": "PER_SECOND"},
        timeout=8,
    )
    _resp.raise_for_status()
    _obj = _resp.json()
    _data = _obj.get("data", _obj) if isinstance(_obj, dict) else {}
    _payload = _data.get("payload", _data) if isinstance(_data, dict) else {}
    _latest = (
        _payload.get("latest_values")
        or _payload.get("latestValues")
        or {}
    )
    _item = _latest.get("BRTI") if isinstance(_latest, dict) else None
    if not isinstance(_item, dict):
        raise RuntimeError("direct BRTI payload missing BRTI")
    _value = float(_item["value"])
    _cf_ts = int(_item["time"]) / 1000.0
    _age = max(0.0, time.time() - _cf_ts)
    return _value, _age

try:
    if _audit_target is None:
        raise RuntimeError("Kalshi target unavailable for direct BRTI authority")

    (
        _direct_brti_authority_value,
        _direct_brti_authority_age,
    ) = _direct_brti_authority_fetch()

    _direct_brti_authority_gap = (
        float(_direct_brti_authority_value) - float(_audit_target)
    )
    _direct_brti_authority_side = (
        "UP" if _direct_brti_authority_gap > 0
        else "DOWN" if _direct_brti_authority_gap < 0
        else "FLAT"
    )

    _direct_brti_authority_ready = bool(
        _direct_brti_authority_age <= DIRECT_BRTI_AUTH_MAX_AGE_SECONDS
        and abs(_direct_brti_authority_gap) > DIRECT_BRTI_AUTH_WAIT_DOLLARS
        and _direct_brti_authority_side in ("UP", "DOWN")
    )

except Exception as _direct_brti_authority_exc:
    _direct_brti_authority_ready = False
    _direct_brti_authority_error = str(_direct_brti_authority_exc)

print("\n--- V4.10 DIRECT BRTI AUTHORITY GATE ---")
print(
    "DIRECT BRTI:",
    (
        f"${_direct_brti_authority_value:,.2f}"
        if _direct_brti_authority_value is not None
        else "UNAVAILABLE"
    ),
)
print(
    "DIRECT BRTI AGE:",
    (
        f"{_direct_brti_authority_age:.1f}s"
        if _direct_brti_authority_age is not None
        else "UNKNOWN"
    ),
)
print(
    "DIRECT BRTI GAP:",
    (
        f"${_direct_brti_authority_gap:+.2f}"
        if _direct_brti_authority_gap is not None
        else "UNKNOWN"
    ),
)
print("DIRECT BRTI SIDE:", _direct_brti_authority_side or "UNKNOWN")
print(
    "DIRECT BRTI AUTHORITY READY:",
    "YES" if _direct_brti_authority_ready else "NO",
)
if _direct_brti_authority_error:
    print("DIRECT BRTI AUTHORITY NOTE:", _direct_brti_authority_error)

# ============================================================
# V4.3 DECISIVE TARGET-AWARE FINAL PATH
# One focused change: allow a FINAL CALL when the restored
# target-aware fair-value model itself reaches a historically
# high-confidence zone and BTC is meaningfully separated from
# the exact Kalshi strike. This does NOT change entry logic.
#
# Gate:
# V4.6 = EXACT OFFLINE TOURNAMENT WINNER
# ---------------------------------------
# Untouched holdout result:
#   97.9% accuracy, 47/100 contracts called,
#   avg 4.64m left, median 5.00m left.
#
# Winner parameters:
#   fair >= 90%
#   time left <= 8m
#   if time left > 6m: gap >= $75
#   if time left <= 6m: gap >= $50
#   distance / recent 5m range >= 1.0x
#   preferred fair side must equal the actual target side
#   no extra momentum-support requirement
#
# IMPORTANT: The legacy strict gate remains visible as a diagnostic, but
# V4.6 FINAL CALL authority comes from the validated tournament winner only.
# This preserves the meaning of the 97.9% untouched-holdout result.
# ============================================================
_decisive_final_ready = False
_decisive_final_side = None
_decisive_final_confidence = None
_decisive_required_gap = None

# Preserve legacy information for diagnostics only.
_legacy_final_ready = bool(_final_15m_ready)
_legacy_final_direction = _final_15m_direction

try:
    _decisive_time_left = (
        max(0.0, 15.0-float(_strict_elapsed_minute))
        if _strict_elapsed_minute is not None else None
    )
    _decisive_gap = (
        float(_fair_distance_target)
        if _fair_distance_target is not None else None
    )
    _decisive_target_side = (
        'UP' if _decisive_gap is not None and _decisive_gap > 0
        else 'DOWN' if _decisive_gap is not None and _decisive_gap < 0
        else None
    )
    _decisive_required_gap = (
        75.0
        if _decisive_time_left is not None and _decisive_time_left > 6.0
        else 50.0
    )

    _decisive_final_ready = bool(
        _fair_ready
        and _decisive_time_left is not None
        and _decisive_time_left <= 8.0
        and float(_fair_preferred) >= 0.90
        and _decisive_gap is not None
        and abs(_decisive_gap) >= _decisive_required_gap
        and _fair_dist_over_range5 is not None
        and float(_fair_dist_over_range5) >= 1.0
        and _fair_preferred_side == _decisive_target_side
        and _direct_brti_authority_ready
        and _fair_preferred_side == _direct_brti_authority_side
    )

    if _decisive_final_ready:
        _decisive_final_side = _fair_preferred_side
        _decisive_final_confidence = float(_fair_preferred)
except Exception:
    _decisive_final_ready = False

# Tournament winner is the sole V4.6 FINAL authority.
_final_15m_ready = bool(_decisive_final_ready)
_final_15m_direction = (
    _decisive_final_side if _decisive_final_ready else _legacy_final_direction
)

print("\n============================================================")
print("FINAL OUTCOME — END OF 15-MIN CONTRACT")
print("============================================================")

if _final_15m_ready:
    _two_final_status = "FINAL CALL"
    _two_final_side = _final_15m_direction
    if _decisive_final_ready:
        _two_final_confidence = float(_decisive_final_confidence)
        _two_final_reason = (
            "Tournament winner: fair >=90%, <=8m left, "
            "gap >=$75 when >6m or >=$50 when <=6m, "
            "distance/range >=1.0x, direct BRTI authority agrees"
        )
        _final_call_source = "TOURNAMENT WINNER"
    else:
        _two_final_confidence = float(current_confidence)
        _two_final_reason = (
            "Existing strict model gate + BRTI/Kalshi gate agree"
        )
        _final_call_source = "LEGACY DIAGNOSTIC"
else:
    _final_call_source = "NONE"
    _two_final_status = "PASS"
    _two_final_side = "NONE"
    _two_final_confidence = None
    _two_final_reason = "Final-call evidence has not cleared the validated tournament gate"

print("STATUS:", _two_final_status)
print("FINAL SIDE:", _two_final_side)
print(
    "FINAL CONFIDENCE:",
    f"{_two_final_confidence:.1%}"
    if _two_final_confidence is not None
    else "NOT QUALIFIED",
)
print(
    "TIME LEFT:",
    f"{max(0.0, 15.0 - float(_strict_elapsed_minute)):.2f} min"
    if _strict_elapsed_minute is not None
    else "UNKNOWN",
)
print("REASON:", _two_final_reason)

# Keep the validated ladder visible as supporting evidence, not as a
# replacement for the strict final-call gate.
print("\n--- SUPPORTING VALIDATED LADDER ---")
print("LADDER STATUS:", _ladder_status)
print("LADDER DIRECTION:", _ladder_direction)
print("LADDER CONFIDENCE:", f"{_ladder_confidence:.1%}")
print("LADDER REASON:", _ladder_reason)

if _ladder_contract_ticker is not None:
    try:
        _ladder_seen = sorted(
            _ladder_state.get("checkpoints", {}).keys(),
            key=lambda x: int(x),
        )
        print(
            "SAME-CONTRACT CHECKPOINTS:",
            ", ".join(_ladder_seen) if _ladder_seen else "NONE",
        )
    except Exception:
        pass

print("\n--- FINAL GATE DIAGNOSTICS ---")
print("EXPECTED FINAL OUTCOME:", _final_15m_direction)
print("MODEL LEAN:", _model_15m_direction)
print(
    "MODEL CONFIRMS FINAL OUTCOME:",
    "YES" if _model_15m_direction == _final_15m_direction else "NO",
)
print("Model confidence:", f"{float(current_confidence):.1%}")
print(
    "Elapsed contract minute:",
    f"{_strict_elapsed_minute:.2f}"
    if _strict_elapsed_minute is not None
    else "UNKNOWN",
)
print(
    "BTC distance from 15m start:",
    f"{_strict_distance:.3%}"
    if _strict_distance is not None
    else "UNKNOWN",
)
print("Directional agreement:", f"{_strict_agreement}/3")
print(
    "Confidence strengthening:",
    "YES"
    if _strict_conf_change is not None and _strict_conf_change >= 0
    else "NO",
)
print(
    "Confidence change:",
    f"{_strict_conf_change:+.4f}"
    if _strict_conf_change is not None
    else "UNKNOWN",
)
print("STRICT MODEL READY:", "YES" if _strict_model_ready else "NO")
print("LEGACY FINAL READY (DIAGNOSTIC):", "YES" if _legacy_final_ready else "NO")
print("TOURNAMENT FINAL READY:", "YES" if _decisive_final_ready else "NO")
print(
    "DIRECT BRTI FINAL AUTHORITY:",
    "YES" if _direct_brti_authority_ready else "NO",
)
print(
    "DIRECT BRTI FINAL SIDE:",
    _direct_brti_authority_side or "UNKNOWN",
)
print(
    "TOURNAMENT REQUIRED GAP:",
    f"${_decisive_required_gap:.0f}" if _decisive_required_gap is not None else "N/A"
)
print(
    "DISTANCE / 5M RANGE:",
    f"{_fair_dist_over_range5:.2f}x" if _fair_dist_over_range5 is not None else "N/A"
)
print("FINAL CALL SOURCE:", _final_call_source)
print(
    "BRTI/KALSHI GATE READY:",
    "YES" if bool(_v3_brti_gate_ready) else "NO",
)

if "_strict_error_text" in globals():
    print("Strict-gate safety note:", _strict_error_text)

# ============================================================
# AUTOMATIC V4 LIVE SNAPSHOT LOG
# New filename avoids mixing the V3 and V4 CSV schemas.
# ============================================================
_snapshot_log = Path('kalshi_two_output_live_log_v4_13.csv')
_snapshot_fields = [
    'timestamp_utc','contract','elapsed_min','time_left_min',
    'btc_price','kalshi_target','target_gap_dollars',
    'up_ask','down_ask',
    'raw_general_side','raw_general_confidence',
    'fair_ready','fair_up','fair_down','fair_preferred_side','fair_preferred',
    'fair_flip_prob','fair_stay_prob','preferred_kalshi_ask','fair_edge_vs_ask',
    'opportunity_status','price_zone','entry_tournament_ready','entry_time_left','entry_abs_target_gap','entry_rule_version',
    'ladder_status','ladder_direction','ladder_confidence','checkpoints',
    'expected_final_outcome','final_status','final_side','final_confidence','final_call_source','decisive_fair_ready','required_gap','dist_over_range5','legacy_final_ready',
    'strict_distance_pct','directional_agreement','confidence_change',
    'strict_model_ready','brti_kalshi_gate_ready',
]

try:
    _snapshot_btc_price = float(data_1m.iloc[-1]['Close']) if not data_1m.empty else None
except Exception:
    _snapshot_btc_price = None
try:
    _snapshot_target = float(_audit_target) if _audit_target is not None else None
except Exception:
    _snapshot_target = None
_snapshot_gap_dollars = (
    _snapshot_btc_price-_snapshot_target
    if _snapshot_btc_price is not None and _snapshot_target is not None else None
)
try:
    _snapshot_checkpoints = ','.join(sorted(
        _ladder_state.get('checkpoints', {}).keys(), key=lambda x:int(x)
    ))
except Exception:
    _snapshot_checkpoints = ''

_snapshot_row = {
    'timestamp_utc': datetime.now(timezone.utc).isoformat(),
    'contract': _ladder_contract_ticker or '',
    'elapsed_min': _strict_elapsed_minute,
    'time_left_min': max(0.0,15.0-float(_strict_elapsed_minute)) if _strict_elapsed_minute is not None else None,
    'btc_price': _snapshot_btc_price,
    'kalshi_target': _snapshot_target,
    'target_gap_dollars': _snapshot_gap_dollars,
    'up_ask': _two_up_ask,
    'down_ask': _two_down_ask,
    'raw_general_side': _model_15m_direction,
    'raw_general_confidence': float(current_confidence),
    'fair_ready': bool(_fair_ready),
    'fair_up': _fair_up,
    'fair_down': _fair_down,
    'fair_preferred_side': _fair_preferred_side,
    'fair_preferred': _fair_preferred,
    'fair_flip_prob': _fair_flip_prob,
    'fair_stay_prob': _fair_stay_prob,
    'preferred_kalshi_ask': _opportunity_ask,
    'fair_edge_vs_ask': _opportunity_edge,
    'opportunity_status': _opportunity_status,
    'price_zone': _opportunity_price_zone,
    'entry_tournament_ready': bool(_entry_tournament_ready),
    'entry_time_left': _entry_time_left,
    'entry_abs_target_gap': _entry_abs_gap,
    'entry_rule_version': 'V3_HISTORICAL_WINNER',
    'ladder_status': _ladder_status,
    'ladder_direction': _ladder_direction,
    'ladder_confidence': _ladder_confidence,
    'checkpoints': _snapshot_checkpoints,
    'expected_final_outcome': _final_15m_direction,
    'final_status': _two_final_status,
    'final_side': _two_final_side,
    'final_confidence': _two_final_confidence,
    'final_call_source': _final_call_source,
    'decisive_fair_ready': bool(_decisive_final_ready),
    'required_gap': _decisive_required_gap,
    'dist_over_range5': _fair_dist_over_range5,
    'legacy_final_ready': bool(_legacy_final_ready),
    'strict_distance_pct': _strict_distance,
    'directional_agreement': _strict_agreement,
    'confidence_change': _strict_conf_change,
    'strict_model_ready': bool(_strict_model_ready),
    'brti_kalshi_gate_ready': bool(_v3_brti_gate_ready),
}

_snapshot_new_file = not _snapshot_log.exists() or _snapshot_log.stat().st_size == 0
with _snapshot_log.open('a', newline='') as _snapshot_f:
    _snapshot_writer = csv.DictWriter(_snapshot_f, fieldnames=_snapshot_fields)
    if _snapshot_new_file:
        _snapshot_writer.writeheader()
    _snapshot_writer.writerow(_snapshot_row)

print('AUTO SNAPSHOT LOG:', _snapshot_log)

print("\nSIGNAL-ONLY: YES")
print("ORDERS PLACED: NO")
# === STRICT 15M + V3 COMBINED READY END ===

# =====================================================================
# V4.8.1 TRUE SCALP SHADOW — TARGET LOOKUP FIX
# =====================================================================
# FINAL authority: unchanged.
# Tier-1 ENTRY: unchanged.
# New scalp definition: unchanged.
# Fix only: robust exact Kalshi target extraction for live KXBTC15M.
# =====================================================================

print("\n" + "="*72)
print("V4.13 TRUE SCALP + PROFIT-PROTECTION FORWARD SHADOW STARTING")
print("FINAL + TIER-1 ABOVE: PRESERVED")
print("TARGET LOOKUP FIX: INSTALLED")
print("NEW SCALP TARGET: MATERIAL TEMPORARY MOVES")
print("DIRECT BRTI: LIVE TARGET-SIDE AUTHORITY + FINAL-60 SETTLEMENT TRACKING")
print("UNIFIED SUBMINUTE: 5s SYNCHRONIZED UP/DOWN DATASET ENABLED")
print("="*72)

"""
KALSHI BTC15 SCALP SHADOW V1
============================

Lightweight high-frequency data collector for the project's TRUE scalp vision.

- Polls every 5 seconds.
- Exact active Kalshi KXBTC15M contract.
- Actual UP/DOWN bid + ask.
- Live Coinbase BTC spot.
- Both sides evaluated independently.
- Creates forward shadow events from cheap-side snapshots.
- Measures executable future BID gain over the next 3 minutes.
- Material targets: +8c / +10c / +15c / +20c.
- Tracks whether -10c stop level happens first.
- Signal only. NO ORDERS.

This does NOT modify bot.py and does NOT change FINAL/Tier-1 entry.
"""

from pathlib import Path
from datetime import datetime, timezone
import time, base64, csv, json, math, signal, sys, threading
from collections import deque
import re

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

POLL_SECONDS = 5
MAX_HISTORY_SECONDS = 240
EVENT_HORIZON_SECONDS = 180
CHEAP_EVENT_CEILING = 0.45
EVENT_SAMPLE_SPACING_SECONDS = 15
STOP_LOSS = 0.10
TARGETS = [0.08, 0.10, 0.15, 0.20]

SNAPSHOT_LOG = Path("kalshi_scalp_shadow_snapshots_v1.csv")
EVENT_LOG = Path("kalshi_scalp_shadow_events_v1.csv")
STATE_FILE = Path("kalshi_scalp_shadow_state_v1.json")

KEY_ID = Path.home().joinpath(".kalshi/key_id").read_text().strip()
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"
PRIVATE_KEY = serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(), password=None
)

KALSHI_BASE_URL = "https://api.elections.kalshi.com"
COINBASE_TICKER = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"

running = True
history = deque()
pending = []
last_event_created = {}
active_ticker = None

def stop_handler(signum, frame):
    global running
    running = False
    print("\nSTOP REQUESTED — finishing current write safely...")

signal.signal(signal.SIGINT, stop_handler)
signal.signal(signal.SIGTERM, stop_handler)

def kalshi_headers(method, path):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method.upper() + path
    signature = PRIVATE_KEY.sign(
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
        timeout=10,
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

def num(v):
    try:
        return float(v)
    except Exception:
        return None

def get_active_market():
    data = kalshi_get(
        "/trade-api/v2/markets",
        params={"status":"open","series_ticker":"KXBTC15M","limit":1000},
    )
    now = datetime.now(timezone.utc)
    active = []
    for m in data.get("markets", []):
        ticker = str(m.get("ticker",""))
        op = parse_dt(m.get("open_time"))
        cl = parse_dt(m.get("close_time"))
        if (
            ticker.startswith("KXBTC15M")
            and op is not None and cl is not None
            and op <= now < cl
        ):
            active.append(m)
    if not active:
        return None
    return min(active, key=lambda m: parse_dt(m.get("close_time")))

def extract_target(market):
    # Preferred source: Kalshi's numeric strike field.
    for key in ("floor_strike", "functional_strike"):
        v = market.get(key)
        try:
            if v is not None and str(v).strip() != "":
                return float(str(v).replace(",", "").replace("$", ""))
        except Exception:
            pass

    # KXBTC15M live records can expose the exact target in the label/title
    # even when floor_strike is absent in the list response.
    texts = [
        market.get("yes_sub_title"),
        market.get("title"),
        market.get("subtitle"),
    ]
    patterns = [
        r"Target\s*Price\s*:\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)",
        r"\$([0-9][0-9,]*(?:\.[0-9]+)?)\s*target",
    ]
    for raw in texts:
        text = str(raw or "")
        for pat in patterns:
            m = re.search(pat, text, flags=re.IGNORECASE)
            if m:
                try:
                    return float(m.group(1).replace(",", ""))
                except Exception:
                    pass

    # Last fallback: fetch this exact market by ticker; this endpoint may
    # contain fields omitted from the list response.
    ticker = str(market.get("ticker") or "")
    if ticker:
        try:
            exact = kalshi_get(f"/trade-api/v2/markets/{ticker}").get("market", {})
            if exact and exact is not market:
                for key in ("floor_strike", "functional_strike"):
                    v = exact.get(key)
                    try:
                        if v is not None and str(v).strip() != "":
                            return float(str(v).replace(",", "").replace("$", ""))
                    except Exception:
                        pass
                for raw in (
                    exact.get("yes_sub_title"),
                    exact.get("title"),
                    exact.get("subtitle"),
                ):
                    text = str(raw or "")
                    for pat in patterns:
                        m = re.search(pat, text, flags=re.IGNORECASE)
                        if m:
                            return float(m.group(1).replace(",", ""))
        except Exception:
            pass

    return None


# =====================================================================
# V4.9 DIRECT CF BENCHMARKS BRTI PARITY SHADOW
# =====================================================================
# SHADOW ONLY:
# - Does NOT replace the existing validated estimated-BRTI safety gate yet.
# - Polls Kalshi's authenticated CF Benchmarks passthrough once per second.
# - Keeps BRTI readings keyed by the CF Benchmarks publication timestamp.
# - Computes the live final-60-second average for the active KXBTC15M contract.
# - Logs Coinbase vs direct BRTI vs Kalshi target for parity validation.
# - NO ORDERS.
# =====================================================================

BRTI_KALSHI_BASE_URL = "https://external-api.kalshi.com"
BRTI_PATH = "/trade-api/v2/cfbenchmarks/latest_values"
BRTI_PARAMS = {"id": "BRTI", "maxResolution": "PER_SECOND"}
BRTI_POLL_SECONDS = 1.0
BRTI_MAX_AGE_SECONDS = 5.0

BRTI_PARITY_LOG = Path("kalshi_direct_brti_parity_v1.csv")
BRTI_PARITY_FIELDS = [
    "timestamp_utc","contract","target","seconds_left",
    "coinbase_spot","direct_brti","brti_timestamp_utc",
    "brti_age_seconds","brti_minus_coinbase",
    "brti_gap_to_target","brti_side",
    "final60_count","final60_average",
    "final60_gap_to_target","final60_side","final60_complete",
    "direct_brti_ready",
]

_brti_lock = threading.Lock()
_brti_samples = deque(maxlen=600)
_brti_last_error = None
_brti_last_error_print = 0.0

if not BRTI_PARITY_LOG.exists():
    with BRTI_PARITY_LOG.open("w", newline="") as _bf:
        csv.DictWriter(_bf, fieldnames=BRTI_PARITY_FIELDS).writeheader()

def _parse_direct_brti_response(obj):
    # Kalshi wraps the raw CF Benchmarks response in {"data": ...}.
    data = obj.get("data", obj) if isinstance(obj, dict) else {}
    payload = data.get("payload", data) if isinstance(data, dict) else {}

    latest = {}
    if isinstance(payload, dict):
        latest = (
            payload.get("latest_values")
            or payload.get("latestValues")
            or {}
        )

    item = latest.get("BRTI") if isinstance(latest, dict) else None
    if not isinstance(item, dict):
        return None

    try:
        value = float(item["value"])
        time_ms = int(item["time"])
    except Exception:
        return None

    return value, time_ms / 1000.0

def _fetch_direct_brti_once():
    r = requests.get(
        BRTI_KALSHI_BASE_URL + BRTI_PATH,
        headers=kalshi_headers("GET", BRTI_PATH),
        params=BRTI_PARAMS,
        timeout=8,
    )
    r.raise_for_status()
    parsed = _parse_direct_brti_response(r.json())
    if parsed is None:
        raise RuntimeError("BRTI response missing payload.latest_values.BRTI")
    return parsed

def _brti_poller():
    global _brti_last_error, _brti_last_error_print
    last_seen_cf_ts = None

    while running:
        cycle = time.time()
        try:
            value, cf_ts = _fetch_direct_brti_once()

            # Store one publication per CF timestamp; do not duplicate the same
            # BRTI point if a poll returns the previous second's value.
            if last_seen_cf_ts != cf_ts:
                with _brti_lock:
                    _brti_samples.append((cf_ts, value))
                last_seen_cf_ts = cf_ts

            _brti_last_error = None

        except Exception as exc:
            _brti_last_error = f"{type(exc).__name__}: {exc}"
            # Avoid flooding the terminal if entitlement/API is unavailable.
            if time.time() - _brti_last_error_print >= 30:
                print("DIRECT BRTI WARNING:", _brti_last_error)
                _brti_last_error_print = time.time()

        elapsed = time.time() - cycle
        time.sleep(max(0.05, BRTI_POLL_SECONDS - elapsed))

def _latest_brti():
    with _brti_lock:
        if not _brti_samples:
            return None
        cf_ts, value = _brti_samples[-1]

    age = max(0.0, time.time() - cf_ts)
    return {
        "value": float(value),
        "cf_ts": float(cf_ts),
        "age": float(age),
        "ready": bool(age <= BRTI_MAX_AGE_SECONDS),
    }

def _brti_contract_snapshot(close_dt, target, coinbase_spot):
    latest = _latest_brti()
    if latest is None:
        return None

    close_ts = close_dt.timestamp()
    start60 = close_ts - 60.0

    with _brti_lock:
        samples = list(_brti_samples)

    # CF BRTI is PER_SECOND here. Deduplicate by publication second.
    by_second = {}
    for cf_ts, value in samples:
        if start60 <= cf_ts < close_ts:
            by_second[int(cf_ts)] = float(value)

    vals = [by_second[k] for k in sorted(by_second)]
    count = len(vals)
    avg60 = float(sum(vals) / count) if count else None

    brti_value = latest["value"]
    brti_gap = brti_value - float(target)
    brti_side = "UP" if brti_gap > 0 else ("DOWN" if brti_gap < 0 else "FLAT")

    avg_gap = None if avg60 is None else avg60 - float(target)
    avg_side = (
        None if avg_gap is None else
        ("UP" if avg_gap > 0 else ("DOWN" if avg_gap < 0 else "FLAT"))
    )

    return {
        "value": brti_value,
        "cf_ts": latest["cf_ts"],
        "age": latest["age"],
        "ready": latest["ready"],
        "minus_coinbase": brti_value - float(coinbase_spot),
        "gap": brti_gap,
        "side": brti_side,
        "final60_count": count,
        "final60_avg": avg60,
        "final60_gap": avg_gap,
        "final60_side": avg_side,
        "final60_complete": bool(count >= 60),
    }

def _log_brti_parity(now, ticker, target, seconds_left, btc, close_dt, b):
    row = {
        "timestamp_utc": now.isoformat(),
        "contract": ticker,
        "target": target,
        "seconds_left": round(seconds_left, 2),
        "coinbase_spot": btc,
        "direct_brti": None if b is None else b["value"],
        "brti_timestamp_utc": (
            None if b is None else
            datetime.fromtimestamp(b["cf_ts"], tz=timezone.utc).isoformat()
        ),
        "brti_age_seconds": None if b is None else round(b["age"], 3),
        "brti_minus_coinbase": None if b is None else b["minus_coinbase"],
        "brti_gap_to_target": None if b is None else b["gap"],
        "brti_side": None if b is None else b["side"],
        "final60_count": None if b is None else b["final60_count"],
        "final60_average": None if b is None else b["final60_avg"],
        "final60_gap_to_target": None if b is None else b["final60_gap"],
        "final60_side": None if b is None else b["final60_side"],
        "final60_complete": False if b is None else b["final60_complete"],
        "direct_brti_ready": False if b is None else b["ready"],
    }
    append_csv(BRTI_PARITY_LOG, BRTI_PARITY_FIELDS, row)
    return row


def get_btc_spot():
    r = requests.get(COINBASE_TICKER, timeout=8)
    r.raise_for_status()
    data = r.json()
    return float(data["price"])

def ensure_csv(path, fields):
    if not path.exists():
        with path.open("w", newline="") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()

SNAPSHOT_FIELDS = [
    "timestamp_utc","contract","target","seconds_left","btc_price","btc_gap",
    "up_bid","up_ask","up_spread","down_bid","down_ask","down_spread",
    "btc_move_5s","btc_move_15s","btc_move_30s","btc_move_60s","btc_move_120s",
    "up_ask_move_5s","up_ask_move_15s","up_ask_move_30s","up_ask_move_60s","up_ask_move_120s",
    "down_ask_move_5s","down_ask_move_15s","down_ask_move_30s","down_ask_move_60s","down_ask_move_120s",
    "up_low_30s","up_low_60s","up_low_120s","up_high_30s","up_high_60s","up_high_120s",
    "down_low_30s","down_low_60s","down_low_120s","down_high_30s","down_high_60s","down_high_120s",
    "up_bounce_from_60s_low","up_drawdown_from_60s_high",
    "down_bounce_from_60s_low","down_drawdown_from_60s_high",
]

EVENT_FIELDS = [
    "event_id","contract","side","entry_timestamp_utc","entry_ask","entry_bid",
    "target","btc_price","btc_gap","seconds_left",
    "btc_move_15s","btc_move_30s","btc_move_60s",
    "ask_move_15s","ask_move_30s","ask_move_60s",
    "recent_low_60s","recent_high_60s","bounce_from_low","drawdown_from_high",
    "outcome_timestamp_utc","observed_seconds",
    "max_future_bid","max_gain_vs_entry_ask","min_future_bid","max_adverse_vs_entry_ask",
    "hit_8c","seconds_to_8c","hit_10c","seconds_to_10c",
    "hit_15c","seconds_to_15c","hit_20c","seconds_to_20c",
    "stop_10c_hit","stop_seconds","notes",
]

ensure_csv(SNAPSHOT_LOG, SNAPSHOT_FIELDS)
ensure_csv(EVENT_LOG, EVENT_FIELDS)

def append_csv(path, fields, row):
    with path.open("a", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writerow({k: row.get(k) for k in fields})

def point_ago(now_ts, seconds):
    target = now_ts - seconds
    best = None
    for r in reversed(history):
        if r["ts"] <= target:
            best = r
            break
    return best

def rows_since(now_ts, seconds):
    cutoff = now_ts - seconds
    return [r for r in history if r["ts"] >= cutoff]

def delta(field, now_ts, seconds, current):
    old = point_ago(now_ts, seconds)
    if old is None or old.get(field) is None or current is None:
        return None
    return current - old[field]

def low_high(field, now_ts, seconds):
    vals = [r.get(field) for r in rows_since(now_ts, seconds)]
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None
    return min(vals), max(vals)

def maybe_create_event(side, snap, now_ts):
    ask = snap[f"{side.lower()}_ask"]
    bid = snap[f"{side.lower()}_bid"]
    if ask is None or bid is None:
        return
    if ask > CHEAP_EVENT_CEILING:
        return
    if snap["seconds_left"] is None or snap["seconds_left"] < 20:
        return

    key = (snap["contract"], side)
    last = last_event_created.get(key)
    if last is not None and now_ts - last < EVENT_SAMPLE_SPACING_SECONDS:
        return

    prefix = side.lower()
    event_id = f"{snap['contract']}|{side}|{int(now_ts*1000)}"
    event = {
        "event_id": event_id,
        "contract": snap["contract"],
        "side": side,
        "entry_ts": now_ts,
        "entry_timestamp_utc": snap["timestamp_utc"],
        "entry_ask": ask,
        "entry_bid": bid,
        "target": snap["target"],
        "btc_price": snap["btc_price"],
        "btc_gap": snap["btc_gap"],
        "seconds_left": snap["seconds_left"],
        "btc_move_15s": snap["btc_move_15s"],
        "btc_move_30s": snap["btc_move_30s"],
        "btc_move_60s": snap["btc_move_60s"],
        "ask_move_15s": snap[f"{prefix}_ask_move_15s"],
        "ask_move_30s": snap[f"{prefix}_ask_move_30s"],
        "ask_move_60s": snap[f"{prefix}_ask_move_60s"],
        "recent_low_60s": snap[f"{prefix}_low_60s"],
        "recent_high_60s": snap[f"{prefix}_high_60s"],
        "bounce_from_low": snap[f"{prefix}_bounce_from_60s_low"],
        "drawdown_from_high": snap[f"{prefix}_drawdown_from_60s_high"],
        "max_future_bid": bid,
        "min_future_bid": bid,
        "hits": {t: None for t in TARGETS},
        "stop_ts": None,
        "done": False,
    }
    pending.append(event)
    last_event_created[key] = now_ts

def update_pending(snap, now_ts):
    finished = []
    for e in pending:
        if e["done"]:
            continue
        if e["contract"] != snap["contract"]:
            # Contract rolled. Finalize with whatever was observed.
            e["done"] = True
            finished.append(e)
            continue

        bid = snap[f"{e['side'].lower()}_bid"]
        if bid is None:
            continue

        e["max_future_bid"] = max(e["max_future_bid"], bid)
        e["min_future_bid"] = min(e["min_future_bid"], bid)

        elapsed = now_ts - e["entry_ts"]

        # Stop chronology: once stop is hit, later targets do not count.
        if e["stop_ts"] is None and bid <= e["entry_ask"] - STOP_LOSS:
            e["stop_ts"] = now_ts

        for t in TARGETS:
            if e["hits"][t] is None:
                if e["stop_ts"] is None and bid >= e["entry_ask"] + t:
                    e["hits"][t] = now_ts

        if elapsed >= EVENT_HORIZON_SECONDS or snap["seconds_left"] <= 0:
            e["done"] = True
            finished.append(e)

    for e in finished:
        finalize_event(e, now_ts)
        try:
            pending.remove(e)
        except ValueError:
            pass

def finalize_event(e, now_ts):
    max_gain = e["max_future_bid"] - e["entry_ask"]
    adverse = e["min_future_bid"] - e["entry_ask"]

    row = {
        "event_id": e["event_id"],
        "contract": e["contract"],
        "side": e["side"],
        "entry_timestamp_utc": e["entry_timestamp_utc"],
        "entry_ask": e["entry_ask"],
        "entry_bid": e["entry_bid"],
        "target": e["target"],
        "btc_price": e["btc_price"],
        "btc_gap": e["btc_gap"],
        "seconds_left": e["seconds_left"],
        "btc_move_15s": e["btc_move_15s"],
        "btc_move_30s": e["btc_move_30s"],
        "btc_move_60s": e["btc_move_60s"],
        "ask_move_15s": e["ask_move_15s"],
        "ask_move_30s": e["ask_move_30s"],
        "ask_move_60s": e["ask_move_60s"],
        "recent_low_60s": e["recent_low_60s"],
        "recent_high_60s": e["recent_high_60s"],
        "bounce_from_low": e["bounce_from_low"],
        "drawdown_from_high": e["drawdown_from_high"],
        "outcome_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "observed_seconds": max(0, int(now_ts - e["entry_ts"])),
        "max_future_bid": e["max_future_bid"],
        "max_gain_vs_entry_ask": max_gain,
        "min_future_bid": e["min_future_bid"],
        "max_adverse_vs_entry_ask": adverse,
        "hit_8c": e["hits"][0.08] is not None,
        "seconds_to_8c": None if e["hits"][0.08] is None else round(e["hits"][0.08]-e["entry_ts"],1),
        "hit_10c": e["hits"][0.10] is not None,
        "seconds_to_10c": None if e["hits"][0.10] is None else round(e["hits"][0.10]-e["entry_ts"],1),
        "hit_15c": e["hits"][0.15] is not None,
        "seconds_to_15c": None if e["hits"][0.15] is None else round(e["hits"][0.15]-e["entry_ts"],1),
        "hit_20c": e["hits"][0.20] is not None,
        "seconds_to_20c": None if e["hits"][0.20] is None else round(e["hits"][0.20]-e["entry_ts"],1),
        "stop_10c_hit": e["stop_ts"] is not None,
        "stop_seconds": None if e["stop_ts"] is None else round(e["stop_ts"]-e["entry_ts"],1),
        "notes": "SHADOW LABEL ONLY — NOT A LIVE TRADE SIGNAL",
    }
    append_csv(EVENT_LOG, EVENT_FIELDS, row)

def save_state():
    state = {
        "saved_utc": datetime.now(timezone.utc).isoformat(),
        "snapshot_log": str(SNAPSHOT_LOG),
        "event_log": str(EVENT_LOG),
        "pending_events": len(pending),
        "poll_seconds": POLL_SECONDS,
        "event_horizon_seconds": EVENT_HORIZON_SECONDS,
    }
    STATE_FILE.write_text(json.dumps(state, indent=2))

print("="*72)
print("KALSHI BTC15 SCALP SHADOW V1")
print("TRUE SCALP DEFINITION — MATERIAL TEMPORARY MOVES")
print("="*72)
print(f"Poll cadence: {POLL_SECONDS}s")
print("Shadow event entry ceiling: 45c")
print("Forward targets: +8c / +10c / +15c / +20c")
print("Stop reference: -10c")
print("Forward horizon: 3 minutes")
print("Both UP and DOWN evaluated independently")
print("NO ORDERS — SHADOW DATA ONLY")

# =====================================================================
# V4.8.4 EARLY-CONFIDENCE SHADOW LOGGER — LIVE + ROLLOVER FIX
# =====================================================================
# Observation only. FINAL, Tier-1 ENTRY and true-scalp logic are unchanged.
#
# FIX:
# V4.8.2 reused the one-time startup opportunity variables inside the 5-second
# loop. V4.8.3 recomputes the SAME target-aware calibrated fair-value model
# every 5 seconds using:
#   - current active KXBTC15M contract
#   - exact current target
#   - current Coinbase BTC spot
#   - current Kalshi UP/DOWN asks
#
# The model itself is NOT retrained or changed. This is a live shadow
# observation path only.
# =====================================================================


# V4.8.4: rolling live BTC history so early-confidence logging survives
# KXBTC15M contract rollovers without depending on a startup-only 1m snapshot.
_ec_btc_ticks = deque()

def _ec_append_btc_tick(now, btc_spot):
    _ts = pd.Timestamp(now)
    if _ts.tzinfo is None:
        _ts = _ts.tz_localize("UTC")
    else:
        _ts = _ts.tz_convert("UTC")
    _ec_btc_ticks.append((_ts, float(btc_spot)))
    _cutoff = _ts - pd.Timedelta(minutes=20)
    while _ec_btc_ticks and _ec_btc_ticks[0][0] < _cutoff:
        _ec_btc_ticks.popleft()

def _ec_live_minute_bars():
    if not _ec_btc_ticks:
        return pd.DataFrame(columns=["Open","High","Low","Close","Volume"])
    _ticks = pd.DataFrame(
        list(_ec_btc_ticks), columns=["Datetime","price"]
    ).set_index("Datetime").sort_index()
    _bars = _ticks["price"].resample("1min").agg(
        Open="first", High="max", Low="min", Close="last"
    )
    _bars["Volume"] = 0.0
    return _bars.dropna(subset=["Close"])

def _live_fair_shadow(now, ticker, target, btc_spot, up_ask, down_ask):
    """
    Recompute the preserved target-aware fair model at the current 5-second
    timestamp. Uses a synthetic current-minute OHLC row whose last price is the
    current Coinbase BTC spot. This affects SHADOW LOGGING ONLY.
    """
    if not _fair_ready:
        return None

    _pair = _fair_parse_contract_times(ticker)
    _start = _pair[0]
    if _start is None or pd.isna(_start):
        return None

    if _start.tzinfo is None:
        _start = _start.tz_localize("UTC")
    else:
        _start = _start.tz_convert("UTC")

    _cut = pd.Timestamp(now)
    if _cut.tzinfo is None:
        _cut = _cut.tz_localize("UTC")
    else:
        _cut = _cut.tz_convert("UTC")

    # Merge the startup historical base with rolling live BTC minute bars.
    # This is the V4.8.4 rollover fix: after the active contract changes,
    # current bars continue to exist instead of the fair logger going stale.
    _ec_append_btc_tick(_cut, btc_spot)
    _live_bars = _ec_live_minute_bars()

    _slice_start = _start - pd.Timedelta(minutes=6)
    _base = _fair_btc.loc[
        (_fair_btc.index >= _slice_start) & (_fair_btc.index <= _cut)
    ].copy()

    if not _live_bars.empty:
        _live_part = _live_bars.loc[
            (_live_bars.index >= _slice_start) & (_live_bars.index <= _cut)
        ].copy()
        _tmp = pd.concat([_base, _live_part])
        _tmp = (
            _tmp[~_tmp.index.duplicated(keep="last")]
            .sort_index()
        )
    else:
        _tmp = _base

    if _tmp.empty:
        return None

    _minute = _cut.floor("min")

    # Update/append the in-progress minute with current BTC spot. The historical
    # model is still the same 1-minute target-aware model; this gives the shadow
    # logger sub-minute observation of its current state.
    if _minute in _tmp.index:
        _old = _tmp.loc[_minute]
        if isinstance(_old, pd.DataFrame):
            _old = _old.iloc[-1]
        _open = float(_old.get("Open", btc_spot))
        _high = max(float(_old.get("High", btc_spot)), float(btc_spot))
        _low = min(float(_old.get("Low", btc_spot)), float(btc_spot))
        _vol = float(_old.get("Volume", 0.0) or 0.0)
    else:
        _open = float(btc_spot)
        _high = float(btc_spot)
        _low = float(btc_spot)
        _vol = 0.0

    _tmp.loc[_minute, "Open"] = _open
    _tmp.loc[_minute, "High"] = _high
    _tmp.loc[_minute, "Low"] = _low
    _tmp.loc[_minute, "Close"] = float(btc_spot)
    if "Volume" in _tmp.columns:
        _tmp.loc[_minute, "Volume"] = _vol
    _tmp = _tmp.sort_index()

    _snap = _fair_build_snapshot(
        _tmp, _start, float(target), _cut=_cut
    )
    if _snap is None:
        return None

    _frame = pd.DataFrame([_snap])
    _raw_flip = float(
        _fair_rf.predict_proba(_frame[_fair_features])[0, 1]
    )
    _flip = float(
        _fair_sigmoid.predict_proba(np.array([[_raw_flip]]))[0, 1]
    )
    _flip = float(np.clip(_flip, 0.001, 0.999))
    _stay = 1.0 - _flip
    _current_side = int(_snap["current_side"])

    if _current_side == 1:
        _up_fair, _down_fair = _stay, _flip
    else:
        _up_fair, _down_fair = _flip, _stay

    _side = "UP" if _up_fair >= _down_fair else "DOWN"
    _fair = max(_up_fair, _down_fair)
    _ask = float(up_ask) if _side == "UP" else float(down_ask)
    _edge = _fair - _ask

    return {
        "side": _side,
        "fair": float(_fair),
        "ask": float(_ask),
        "edge": float(_edge),
        "up_fair": float(_up_fair),
        "down_fair": float(_down_fair),
        "current_side": int(_current_side),
        "dist_target": float(_snap["dist_target"]),
        "abs_dist_target": float(abs(_snap["dist_target"])),
        "range5": float(_snap["range5"]),
        "vol5": float(_snap["vol5"]),
        "dist_over_range5": float(_snap["dist_over_range5"]),
    }

EARLY_CONF_LOG = Path("kalshi_early_conf_shadow_v1_2.csv")
EARLY_CONF_FIELDS = [
    "timestamp_utc","contract","target","seconds_left",
    "btc_price","btc_gap","preferred_side","preferred_ask",
    "preferred_fair","edge",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "candidate_persistence_30s","provisional_candidate",
]
_early_hist = deque()
ensure_csv(EARLY_CONF_LOG, EARLY_CONF_FIELDS)

def _early_point_ago(now_ts, seconds):
    target_ts = now_ts - seconds
    for r in reversed(_early_hist):
        if r["ts"] <= target_ts:
            return r
    return None

def _early_delta(field, now_ts, seconds, current):
    old = _early_point_ago(now_ts, seconds)
    if old is None or old.get(field) is None or current is None:
        return None
    return current - old[field]

def _candidate_flag(ask, fair, edge, seconds_left, abs_gap):
    if None in (ask, fair, edge, seconds_left, abs_gap):
        return False
    return (
        ask <= 0.45
        and fair >= 0.75
        and edge >= 0.20
        and 240 <= seconds_left <= 600
        and abs_gap >= 25.0
    )

def log_early_conf_shadow(
    now, now_ts, ticker, target, seconds_left, btc, btc_gap,
    preferred_side, preferred_ask, preferred_fair, edge
):
    cand = _candidate_flag(
        preferred_ask, preferred_fair, edge, seconds_left, abs(btc_gap)
    )
    _early_hist.append({
        "ts": now_ts, "contract": ticker,
        "ask": preferred_ask, "fair": preferred_fair,
        "candidate": cand,
    })
    while _early_hist and now_ts - _early_hist[0]["ts"] > 90:
        _early_hist.popleft()

    recent30 = [
        r for r in _early_hist
        if r["contract"] == ticker and now_ts-r["ts"] <= 30
    ]
    persistence = sum(1 for r in recent30 if r["candidate"])

    _row = {
        "timestamp_utc": now.isoformat(),
        "contract": ticker,
        "target": target,
        "seconds_left": round(seconds_left,2),
        "btc_price": btc,
        "btc_gap": btc_gap,
        "preferred_side": preferred_side,
        "preferred_ask": preferred_ask,
        "preferred_fair": preferred_fair,
        "edge": edge,
        "fair_move_5s": _early_delta("fair", now_ts, 5, preferred_fair),
        "fair_move_15s": _early_delta("fair", now_ts, 15, preferred_fair),
        "fair_move_30s": _early_delta("fair", now_ts, 30, preferred_fair),
        "ask_move_5s": _early_delta("ask", now_ts, 5, preferred_ask),
        "ask_move_15s": _early_delta("ask", now_ts, 15, preferred_ask),
        "ask_move_30s": _early_delta("ask", now_ts, 30, preferred_ask),
        "candidate_persistence_30s": persistence,
        "provisional_candidate": cand,
    }
    append_csv(EARLY_CONF_LOG, EARLY_CONF_FIELDS, _row)
    return _row

print(f"Snapshot log: {SNAPSHOT_LOG}")
print(f"Event log: {EVENT_LOG}")
print()


# =====================================================================
# V4.11 UNIFIED SUB-MINUTE EARLY-ENTRY COLLECTOR
# =====================================================================
# Observation / dataset creation only.
#
# Every 5 seconds:
#   - one UP row
#   - one DOWN row
# Both rows share the same timestamp and live market snapshot.
#
# Synchronizes:
#   BTC 5s/15s/30s/60s/120s momentum
#   Kalshi bid/ask/spread and ask slope
#   target-aware fair for BOTH sides
#   fair slope
#   direct BRTI / target-side agreement
#   cheap-candidate persistence
#   Kalshi lag diagnostics
#   reversal-state diagnostics
#
# No orders. No FINAL/Tier-1/scalp authority changes.
# =====================================================================

UNIFIED_SUBMINUTE_LOG = Path("kalshi_subminute_unified_v1_1.csv")
UNIFIED_SUBMINUTE_FIELDS = [
    "timestamp_utc","contract","side","side_num",
    "target","seconds_left","minutes_left",
    "btc_price","btc_gap","btc_gap_side","abs_btc_gap",
    "side_bid","side_ask","side_spread","opposite_ask","quote_advantage",
    "btc_move_5s_side","btc_move_15s_side","btc_move_30s_side",
    "btc_move_60s_side","btc_move_120s_side",
    "ask_move_5s","ask_move_15s","ask_move_30s",
    "ask_move_60s","ask_move_120s",
    "recent_low_30s","recent_low_60s","recent_low_120s",
    "recent_high_30s","recent_high_60s","recent_high_120s",
    "bounce_from_60s_low","drawdown_from_60s_high",
    "side_fair","side_edge",
    "fair_move_5s","fair_move_15s","fair_move_30s",
    "preferred_fair_side","preferred_fair","preferred_edge",
    "current_target_side","preferred_side_match",
    "dist_over_range5","range5","vol5",
    "broad_candidate","candidate_persistence_30s",
    "brti_value","brti_age_seconds","brti_ready",
    "brti_gap_to_target","brti_gap_side",
    "brti_minus_coinbase","brti_minus_coinbase_side",
    "brti_side","brti_agrees_side",
    "kalshi_lag_15s","kalshi_lag_30s",
    "reversal_state",
    "final60_count","final60_average","final60_side","final60_complete",
]
ensure_csv(UNIFIED_SUBMINUTE_LOG, UNIFIED_SUBMINUTE_FIELDS)

_unified_hist = deque()

def _unified_point_ago(contract, side, now_ts, seconds):
    target_ts = now_ts - seconds
    for r in reversed(_unified_hist):
        if (
            r["contract"] == contract
            and r["side"] == side
            and r["ts"] <= target_ts
        ):
            return r
    return None

def _unified_delta(contract, side, field, now_ts, seconds, current):
    old = _unified_point_ago(contract, side, now_ts, seconds)
    if old is None or old.get(field) is None or current is None:
        return None
    return float(current) - float(old[field])

def _unified_candidate_persistence(contract, side, now_ts):
    cutoff = now_ts - 30.0
    return sum(
        1 for r in _unified_hist
        if r["contract"] == contract
        and r["side"] == side
        and r["ts"] >= cutoff
        and bool(r.get("broad_candidate"))
    )

def _unified_reversal_state(
    btc5, btc15, btc30,
    ask5, ask15, ask30,
):
    vals = [btc5, btc15, btc30, ask5, ask15, ask30]
    if any(v is None or pd.isna(v) for v in vals):
        return "WARMING"

    # Side-aligned: positive BTC and positive contract ask are favorable.
    if btc5 > 0 and btc15 > 0 and btc30 > 0 and ask5 >= 0 and ask15 >= 0:
        return "PUSH"

    if btc30 > 0 and btc15 > 0 and btc5 < 0 and ask5 < 0:
        return "PULLBACK"

    if btc30 > 0 and btc15 < 0 and btc5 < 0 and ask15 < 0:
        return "REVERSAL_WARN"

    if btc30 < 0 and btc15 < 0 and ask15 <= 0:
        return "AGAINST"

    return "MIXED"

def log_unified_subminute(
    now, now_ts, ticker, target, seconds_left, btc, btc_gap,
    snap, fair_live, brti_live,
):
    # Always write the synchronized market/BTC/BRTI row.
    # Fair fields are optional during warm-up and populate automatically
    # once the target-aware fair engine becomes available.
    out_rows = []
    minutes_left = float(seconds_left) / 60.0
    current_target_side = "UP" if btc_gap >= 0 else "DOWN"

    for side in ("UP","DOWN"):
        p = side.lower()
        q = "down" if p == "up" else "up"
        sign = 1.0 if side == "UP" else -1.0

        side_ask = snap.get(f"{p}_ask")
        side_bid = snap.get(f"{p}_bid")
        opp_ask = snap.get(f"{q}_ask")

        if side_ask is None:
            continue

        side_fair = None
        side_edge = None
        fair5 = None
        fair15 = None
        fair30 = None

        if fair_live is not None:
            side_fair = (
                float(fair_live["up_fair"])
                if side == "UP"
                else float(fair_live["down_fair"])
            )
            side_edge = side_fair - float(side_ask)

            fair5 = _unified_delta(
                ticker, side, "fair", now_ts, 5, side_fair
            )
            fair15 = _unified_delta(
                ticker, side, "fair", now_ts, 15, side_fair
            )
            fair30 = _unified_delta(
                ticker, side, "fair", now_ts, 30, side_fair
            )

        btc5 = snap.get("btc_move_5s")
        btc15 = snap.get("btc_move_15s")
        btc30 = snap.get("btc_move_30s")
        btc60 = snap.get("btc_move_60s")
        btc120 = snap.get("btc_move_120s")

        btc5s = None if btc5 is None else float(btc5) * sign
        btc15s = None if btc15 is None else float(btc15) * sign
        btc30s = None if btc30 is None else float(btc30) * sign
        btc60s = None if btc60 is None else float(btc60) * sign
        btc120s = None if btc120 is None else float(btc120) * sign

        ask5 = snap.get(f"{p}_ask_move_5s")
        ask15 = snap.get(f"{p}_ask_move_15s")
        ask30 = snap.get(f"{p}_ask_move_30s")
        ask60 = snap.get(f"{p}_ask_move_60s")
        ask120 = snap.get(f"{p}_ask_move_120s")

        # Broad development candidate. Raw rows are logged regardless.
        broad_candidate = bool(
            side_fair is not None
            and side_edge is not None
            and 240.0 <= float(seconds_left) <= 600.0
            and float(side_ask) <= 0.50
            and side_fair >= 0.60
            and side_edge >= 0.00
        )

        persistence = _unified_candidate_persistence(
            ticker, side, now_ts
        )

        brti_value = None
        brti_age = None
        brti_ready = False
        brti_gap = None
        brti_minus_cb = None
        brti_side = None
        brti_agrees = None
        final60_count = None
        final60_avg = None
        final60_side = None
        final60_complete = False

        if brti_live is not None:
            brti_value = brti_live.get("value")
            brti_age = brti_live.get("age")
            brti_ready = bool(brti_live.get("ready"))
            brti_gap = brti_live.get("gap")
            brti_minus_cb = brti_live.get("minus_coinbase")
            brti_side = brti_live.get("side")
            brti_agrees = bool(brti_side == side)
            final60_count = brti_live.get("final60_count")
            final60_avg = brti_live.get("final60_avg")
            final60_side = brti_live.get("final60_side")
            final60_complete = bool(
                brti_live.get("final60_complete")
            )

        # "Lag" here means BTC moved in favor while Kalshi's side ask
        # has not yet moved with it. This is a raw diagnostic feature,
        # not a trade signal.
        kalshi_lag_15 = bool(
            btc15s is not None
            and ask15 is not None
            and btc15s > 0
            and float(ask15) <= 0
        )
        kalshi_lag_30 = bool(
            btc30s is not None
            and ask30 is not None
            and btc30s > 0
            and float(ask30) <= 0
        )

        reversal_state = _unified_reversal_state(
            btc5s, btc15s, btc30s,
            ask5, ask15, ask30,
        )

        row = {
            "timestamp_utc": now.isoformat(),
            "contract": ticker,
            "side": side,
            "side_num": 1 if side == "UP" else 0,
            "target": target,
            "seconds_left": round(float(seconds_left),2),
            "minutes_left": minutes_left,
            "btc_price": btc,
            "btc_gap": btc_gap,
            "btc_gap_side": float(btc_gap) * sign,
            "abs_btc_gap": abs(float(btc_gap)),
            "side_bid": side_bid,
            "side_ask": side_ask,
            "side_spread": (
                None if side_bid is None
                else float(side_ask)-float(side_bid)
            ),
            "opposite_ask": opp_ask,
            "quote_advantage": (
                None if opp_ask is None
                else float(opp_ask)-float(side_ask)
            ),
            "btc_move_5s_side": btc5s,
            "btc_move_15s_side": btc15s,
            "btc_move_30s_side": btc30s,
            "btc_move_60s_side": btc60s,
            "btc_move_120s_side": btc120s,
            "ask_move_5s": ask5,
            "ask_move_15s": ask15,
            "ask_move_30s": ask30,
            "ask_move_60s": ask60,
            "ask_move_120s": ask120,
            "recent_low_30s": snap.get(f"{p}_low_30s"),
            "recent_low_60s": snap.get(f"{p}_low_60s"),
            "recent_low_120s": snap.get(f"{p}_low_120s"),
            "recent_high_30s": snap.get(f"{p}_high_30s"),
            "recent_high_60s": snap.get(f"{p}_high_60s"),
            "recent_high_120s": snap.get(f"{p}_high_120s"),
            "bounce_from_60s_low": snap.get(
                f"{p}_bounce_from_60s_low"
            ),
            "drawdown_from_60s_high": snap.get(
                f"{p}_drawdown_from_60s_high"
            ),
            "side_fair": side_fair,
            "side_edge": side_edge,
            "fair_move_5s": fair5,
            "fair_move_15s": fair15,
            "fair_move_30s": fair30,
            "preferred_fair_side": (None if fair_live is None else fair_live.get("side")),
            "preferred_fair": (None if fair_live is None else fair_live.get("fair")),
            "preferred_edge": (None if fair_live is None else fair_live.get("edge")),
            "current_target_side": current_target_side,
            "preferred_side_match": (
                None if fair_live is None
                else bool(fair_live.get("side") == side)
            ),
            "dist_over_range5": (None if fair_live is None else fair_live.get("dist_over_range5")),
            "range5": (None if fair_live is None else fair_live.get("range5")),
            "vol5": (None if fair_live is None else fair_live.get("vol5")),
            "broad_candidate": broad_candidate,
            "candidate_persistence_30s": persistence,
            "brti_value": brti_value,
            "brti_age_seconds": brti_age,
            "brti_ready": brti_ready,
            "brti_gap_to_target": brti_gap,
            "brti_gap_side": (
                None if brti_gap is None
                else float(brti_gap) * sign
            ),
            "brti_minus_coinbase": brti_minus_cb,
            "brti_minus_coinbase_side": (
                None if brti_minus_cb is None
                else float(brti_minus_cb) * sign
            ),
            "brti_side": brti_side,
            "brti_agrees_side": brti_agrees,
            "kalshi_lag_15s": kalshi_lag_15,
            "kalshi_lag_30s": kalshi_lag_30,
            "reversal_state": reversal_state,
            "final60_count": final60_count,
            "final60_average": final60_avg,
            "final60_side": final60_side,
            "final60_complete": final60_complete,
        }

        append_csv(
            UNIFIED_SUBMINUTE_LOG,
            UNIFIED_SUBMINUTE_FIELDS,
            row,
        )

        _unified_hist.append({
            "ts": now_ts,
            "contract": ticker,
            "side": side,
            "fair": side_fair,
            "broad_candidate": broad_candidate,
        })

        out_rows.append(row)

    # Retain only ~3 minutes of unified history.
    cutoff = now_ts - 180.0
    while _unified_hist and _unified_hist[0]["ts"] < cutoff:
        _unified_hist.popleft()

    return out_rows

print(f"Unified sub-minute log: {UNIFIED_SUBMINUTE_LOG}")


# =====================================================================
# V4.12 TRUE-SCALP FORWARD SHADOW CANDIDATE
# =====================================================================
# FROZEN DEVELOPMENT CANDIDATE — NOT A PRODUCTION TRADE SIGNAL.
#
# Development evidence from original overnight dataset:
#   17/18 = 94.4% +10c-before--10c-stop
#   18 signals across 10/20 later walk-forward contracts
#   avg entry 38.2c | avg time left 9.53m
#   median seconds to +10c = 20s
#   +15c follow-through 72.2% | +20c 61.1%
#
# Training is frozen to the original overnight event cutoff so future forward
# results cannot leak back into model fitting.
# =====================================================================

TRUE_SCALP_TRAIN_CUTOFF = pd.Timestamp(
    "2026-09-03T14:24:57.562191+00:00"
)
TRUE_SCALP_THRESHOLD = 0.925
TRUE_SCALP_MIN_SECONDS_LEFT = 120.0
TRUE_SCALP_MAX_ASK = 0.45
TRUE_SCALP_COOLDOWN_SECONDS = 120.0
TRUE_SCALP_HORIZON_SECONDS = 180.0
TRUE_SCALP_STOP = 0.10
TRUE_SCALP_TARGETS = [0.10, 0.15, 0.20]

TRUE_SCALP_LOG = Path("kalshi_true_scalp_forward_shadow_v1.csv")
TRUE_SCALP_FIELDS = [
    "signal_id","contract","side","signal_timestamp_utc",
    "scalp_probability","entry_ask","entry_bid",
    "seconds_left","minutes_left",
    "btc_gap_side","abs_gap",
    "btc_move_15s_side","btc_move_30s_side","btc_move_60s_side",
    "ask_move_15s","ask_move_30s","ask_move_60s",
    "bounce_from_low","drawdown_from_high","ask_position_60",
    "outcome_timestamp_utc","observed_seconds",
    "max_future_bid","min_future_bid",
    "hit_10c","seconds_to_10c",
    "hit_15c","seconds_to_15c",
    "hit_20c","seconds_to_20c",
    "stop_10c_hit","stop_seconds",
    "result_10c_before_stop","notes",
]
ensure_csv(TRUE_SCALP_LOG, TRUE_SCALP_FIELDS)

_TRUE_SCALP_FEATURES = [
    "entry_ask","minutes_left","btc_gap_side","abs_gap",
    "btc_move_15s_side","btc_move_30s_side","btc_move_60s_side",
    "ask_move_15s","ask_move_30s","ask_move_60s",
    "bounce_from_low","drawdown_from_high","ask_position_60","side_num",
]

_true_scalp_model = None
_true_scalp_medians = None
_true_scalp_ready = False
_true_scalp_pending = []
_true_scalp_last_signal = {}


# =====================================================================
# V4.13 PROFIT-PROTECTION FORWARD SHADOW
# =====================================================================
# FROZEN EXIT CANDIDATE FROM OFFLINE DEVELOPMENT/UNTOUCHED SCREEN.
# NOT A PRODUCTION EXIT SIGNAL.
#
# Candidate: T20_F6_TR4_BRTI
#   1) Do nothing until executable BID reaches entry ASK +10c.
#   2) At +10c, ARM profit protection.
#   3) Continue toward +20c target.
#   4) After arming, protect at max(+6c, peak profit -4c).
#   5) Direct BRTI disagreement with trade side may trigger a shadow exit
#      only while executable profit is still at least +6c.
#
# Offline screen on the 17 fresh scalp paths:
#   Untouched 6 trades: 100% >=18% ROI
#   avg +29.2c / 71.0% ROI
#   median +28c
#   worst +11c
#
# IMPORTANT: six untouched exits are encouraging but not enough to lock.
# This module is FORWARD SHADOW ONLY. NO ORDERS.
# =====================================================================

PROFIT_SHADOW_ARM = 0.10
PROFIT_SHADOW_TARGET = 0.20
PROFIT_SHADOW_FLOOR = 0.06
PROFIT_SHADOW_TRAIL = 0.04
PROFIT_SHADOW_HORIZON_SECONDS = 180.0

PROFIT_SHADOW_LOG = Path("kalshi_profit_protection_forward_shadow_v1.csv")
PROFIT_SHADOW_FIELDS = [
    "signal_id","contract","side",
    "entry_timestamp_utc","entry_ask",
    "armed","arm_timestamp_utc","arm_seconds",
    "peak_profit_c","exit_timestamp_utc","exit_seconds",
    "exit_bid","profit_c","roi_pct","exit_reason",
    "brti_ready_at_exit","brti_side_at_exit","brti_agreed_at_exit",
    "target_profit_c","floor_profit_c","trail_c",
    "notes",
]
ensure_csv(PROFIT_SHADOW_LOG, PROFIT_SHADOW_FIELDS)

_profit_shadow_pending = []

def _start_profit_shadow(e):
    _profit_shadow_pending.append({
        "signal_id": e["signal_id"],
        "contract": e["contract"],
        "side": e["side"],
        "entry_ts": e["entry_ts"],
        "entry_timestamp_utc": e["signal_timestamp_utc"],
        "entry_ask": float(e["entry_ask"]),
        "armed": False,
        "arm_ts": None,
        "peak_profit": None,
        "finished": False,
    })

def _profit_shadow_finalize(st, now_ts, bid, reason, brti_contract):
    profit = float(bid) - float(st["entry_ask"])
    roi = (
        profit / float(st["entry_ask"])
        if float(st["entry_ask"]) > 0 else None
    )

    brti_ready = None
    brti_side = None
    brti_agreed = None
    if brti_contract is not None:
        brti_ready = bool(brti_contract.get("ready"))
        brti_side = brti_contract.get("side")
        if brti_side in ("UP","DOWN"):
            brti_agreed = bool(brti_side == st["side"])

    append_csv(
        PROFIT_SHADOW_LOG,
        PROFIT_SHADOW_FIELDS,
        {
            "signal_id": st["signal_id"],
            "contract": st["contract"],
            "side": st["side"],
            "entry_timestamp_utc": st["entry_timestamp_utc"],
            "entry_ask": st["entry_ask"],
            "armed": st["armed"],
            "arm_timestamp_utc": (
                None if st["arm_ts"] is None
                else datetime.fromtimestamp(
                    st["arm_ts"], tz=timezone.utc
                ).isoformat()
            ),
            "arm_seconds": (
                None if st["arm_ts"] is None
                else round(st["arm_ts"] - st["entry_ts"],1)
            ),
            "peak_profit_c": (
                None if st["peak_profit"] is None
                else round(st["peak_profit"] * 100,1)
            ),
            "exit_timestamp_utc": datetime.fromtimestamp(
                now_ts, tz=timezone.utc
            ).isoformat(),
            "exit_seconds": round(now_ts - st["entry_ts"],1),
            "exit_bid": float(bid),
            "profit_c": round(profit * 100,1),
            "roi_pct": (
                None if roi is None else round(roi * 100,1)
            ),
            "exit_reason": reason,
            "brti_ready_at_exit": brti_ready,
            "brti_side_at_exit": brti_side,
            "brti_agreed_at_exit": brti_agreed,
            "target_profit_c": int(PROFIT_SHADOW_TARGET * 100),
            "floor_profit_c": int(PROFIT_SHADOW_FLOOR * 100),
            "trail_c": int(PROFIT_SHADOW_TRAIL * 100),
            "notes": (
                "FROZEN T20_F6_TR4_BRTI — FORWARD SHADOW ONLY"
            ),
        }
    )

    print(
        "PROFIT SHADOW EXIT | "
        f"{st['side']} | {reason} | "
        f"entry {st['entry_ask']:.0%} | "
        f"exit {float(bid):.0%} | "
        f"profit {profit*100:+.1f}c | "
        f"ROI {0 if roi is None else roi*100:.1f}%"
    )
    st["finished"] = True

def _update_profit_shadow(snap, now_ts, brti_contract):
    finished = []

    for st in _profit_shadow_pending:
        if st["finished"]:
            finished.append(st)
            continue

        # Contract rollover or horizon: finalize at current available bid
        # only if still in the same contract. Otherwise remove unfinished
        # shadow state without inventing an exit.
        if st["contract"] != snap["contract"]:
            finished.append(st)
            continue

        bid = snap.get(f"{st['side'].lower()}_bid")
        if bid is None:
            continue
        bid = float(bid)
        profit = bid - st["entry_ask"]

        if not st["armed"]:
            if profit >= PROFIT_SHADOW_ARM:
                st["armed"] = True
                st["arm_ts"] = now_ts
                st["peak_profit"] = profit
                print(
                    "PROFIT SHADOW ARMED | "
                    f"{st['side']} | "
                    f"entry {st['entry_ask']:.0%} | "
                    f"bid {bid:.0%} | "
                    f"profit {profit*100:+.1f}c | "
                    "target +20c"
                )
            elif (
                now_ts - st["entry_ts"]
                >= PROFIT_SHADOW_HORIZON_SECONDS
            ):
                finished.append(st)
            continue

        st["peak_profit"] = max(
            float(st["peak_profit"]), profit
        )

        if profit >= PROFIT_SHADOW_TARGET:
            _profit_shadow_finalize(
                st, now_ts, bid, "TARGET_20", brti_contract
            )
            finished.append(st)
            continue

        protect_level = max(
            PROFIT_SHADOW_FLOOR,
            float(st["peak_profit"]) - PROFIT_SHADOW_TRAIL,
        )

        if profit <= protect_level:
            _profit_shadow_finalize(
                st, now_ts, bid, "TRAIL_PROTECT", brti_contract
            )
            finished.append(st)
            continue

        brti_disagree = False
        if (
            brti_contract is not None
            and bool(brti_contract.get("ready"))
            and brti_contract.get("side") in ("UP","DOWN")
        ):
            brti_disagree = (
                brti_contract.get("side") != st["side"]
            )

        if brti_disagree and profit >= PROFIT_SHADOW_FLOOR:
            _profit_shadow_finalize(
                st, now_ts, bid, "BRTI_PROTECT", brti_contract
            )
            finished.append(st)
            continue

        if (
            now_ts - st["entry_ts"]
            >= PROFIT_SHADOW_HORIZON_SECONDS
        ):
            _profit_shadow_finalize(
                st, now_ts, bid, "HORIZON", brti_contract
            )
            finished.append(st)

    for st in finished:
        try:
            _profit_shadow_pending.remove(st)
        except ValueError:
            pass

print(
    "PROFIT-PROTECTION SHADOW READY | "
    "arm +10c | target +20c | floor +6c | trail 4c | "
    "BRTI protect | NO ORDERS"
)
print(f"Profit-protection forward log: {PROFIT_SHADOW_LOG}")

def _truthy(v):
    return str(v).strip().lower() in ("true","1","yes")

def _train_true_scalp_candidate():
    global _true_scalp_model, _true_scalp_medians, _true_scalp_ready

    if not EVENT_LOG.exists():
        print("TRUE SCALP SHADOW: training event log missing — disabled")
        return

    try:
        d = pd.read_csv(EVENT_LOG)
        d["entry_timestamp_utc"] = pd.to_datetime(
            d["entry_timestamp_utc"], errors="coerce", utc=True
        )
        d = d[
            d["entry_timestamp_utc"].notna()
            & (d["entry_timestamp_utc"] <= TRUE_SCALP_TRAIN_CUTOFF)
        ].copy()

        if len(d) < 500:
            print(
                "TRUE SCALP SHADOW: fewer than 500 frozen training events — disabled"
            )
            return

        for c in [
            "entry_ask","seconds_left","btc_gap",
            "btc_move_15s","btc_move_30s","btc_move_60s",
            "ask_move_15s","ask_move_30s","ask_move_60s",
            "recent_low_60s","recent_high_60s",
            "bounce_from_low","drawdown_from_high",
        ]:
            d[c] = pd.to_numeric(d[c], errors="coerce")

        d["minutes_left"] = d["seconds_left"] / 60.0
        d["side_num"] = (
            d["side"].astype(str).str.upper() == "UP"
        ).astype(int)
        sign = np.where(d["side_num"] == 1, 1.0, -1.0)
        d["btc_gap_side"] = d["btc_gap"] * sign
        d["abs_gap"] = d["btc_gap"].abs()
        d["btc_move_15s_side"] = d["btc_move_15s"] * sign
        d["btc_move_30s_side"] = d["btc_move_30s"] * sign
        d["btc_move_60s_side"] = d["btc_move_60s"] * sign

        span = (
            d["recent_high_60s"] - d["recent_low_60s"]
        ).replace(0, np.nan)
        d["ask_position_60"] = (
            d["entry_ask"] - d["recent_low_60s"]
        ) / span

        d["target10"] = d["hit_10c"].map(_truthy).astype(int)

        _true_scalp_medians = (
            d[_TRUE_SCALP_FEATURES]
            .apply(pd.to_numeric, errors="coerce")
            .median()
            .fillna(0.0)
        )

        X = (
            d[_TRUE_SCALP_FEATURES]
            .apply(pd.to_numeric, errors="coerce")
            .fillna(_true_scalp_medians)
            .fillna(0.0)
        )
        y = d["target10"].astype(int)

        _true_scalp_model = HistGradientBoostingClassifier(
            max_iter=250,
            max_depth=4,
            learning_rate=0.04,
            min_samples_leaf=15,
            l2_regularization=1.0,
            random_state=3,
        )
        _true_scalp_model.fit(X, y)
        _true_scalp_ready = True

        print(
            "TRUE SCALP FORWARD SHADOW READY | "
            f"frozen events {len(d)} | "
            f"threshold {TRUE_SCALP_THRESHOLD:.3f} | "
            "target +10c before -10c"
        )

    except Exception as exc:
        _true_scalp_ready = False
        print("TRUE SCALP SHADOW TRAIN WARNING:", str(exc))

def _true_scalp_live_features(side, snap):
    p = side.lower()
    sign = 1.0 if side == "UP" else -1.0
    ask = snap.get(f"{p}_ask")
    bid = snap.get(f"{p}_bid")
    if ask is None or bid is None:
        return None

    low60 = snap.get(f"{p}_low_60s")
    high60 = snap.get(f"{p}_high_60s")
    ask_pos = None
    if (
        low60 is not None and high60 is not None
        and float(high60) != float(low60)
    ):
        ask_pos = (
            float(ask) - float(low60)
        ) / (float(high60) - float(low60))

    return {
        "entry_ask": float(ask),
        "minutes_left": float(snap["seconds_left"]) / 60.0,
        "btc_gap_side": float(snap["btc_gap"]) * sign,
        "abs_gap": abs(float(snap["btc_gap"])),
        "btc_move_15s_side": (
            None if snap.get("btc_move_15s") is None
            else float(snap["btc_move_15s"]) * sign
        ),
        "btc_move_30s_side": (
            None if snap.get("btc_move_30s") is None
            else float(snap["btc_move_30s"]) * sign
        ),
        "btc_move_60s_side": (
            None if snap.get("btc_move_60s") is None
            else float(snap["btc_move_60s"]) * sign
        ),
        "ask_move_15s": snap.get(f"{p}_ask_move_15s"),
        "ask_move_30s": snap.get(f"{p}_ask_move_30s"),
        "ask_move_60s": snap.get(f"{p}_ask_move_60s"),
        "bounce_from_low": snap.get(f"{p}_bounce_from_60s_low"),
        "drawdown_from_high": snap.get(f"{p}_drawdown_from_60s_high"),
        "ask_position_60": ask_pos,
        "side_num": 1 if side == "UP" else 0,
    }

def _true_scalp_probability(side, snap):
    if not _true_scalp_ready:
        return None, None
    feat = _true_scalp_live_features(side, snap)
    if feat is None:
        return None, None

    row = pd.DataFrame([feat])
    for c in _TRUE_SCALP_FEATURES:
        row[c] = pd.to_numeric(row[c], errors="coerce")
        row[c] = row[c].fillna(
            _true_scalp_medians.get(c, 0.0)
        )

    prob = float(
        _true_scalp_model.predict_proba(
            row[_TRUE_SCALP_FEATURES]
        )[0,1]
    )
    return prob, feat

def _maybe_true_scalp_signal(side, snap, now_ts):
    probability, feat = _true_scalp_probability(side, snap)
    if probability is None:
        return

    if float(snap["seconds_left"]) < TRUE_SCALP_MIN_SECONDS_LEFT:
        return
    if float(feat["entry_ask"]) > TRUE_SCALP_MAX_ASK:
        return
    if probability < TRUE_SCALP_THRESHOLD:
        return

    key = (snap["contract"], side)
    last = _true_scalp_last_signal.get(key)
    if (
        last is not None
        and now_ts - last < TRUE_SCALP_COOLDOWN_SECONDS
    ):
        return

    p = side.lower()
    entry_bid = snap.get(f"{p}_bid")
    if entry_bid is None:
        return

    signal_id = (
        f"{snap['contract']}|{side}|SCALP|{int(now_ts*1000)}"
    )
    e = {
        "signal_id": signal_id,
        "contract": snap["contract"],
        "side": side,
        "entry_ts": now_ts,
        "signal_timestamp_utc": snap["timestamp_utc"],
        "scalp_probability": probability,
        "entry_ask": float(feat["entry_ask"]),
        "entry_bid": float(entry_bid),
        "seconds_left": float(snap["seconds_left"]),
        "features": feat,
        "max_future_bid": float(entry_bid),
        "min_future_bid": float(entry_bid),
        "hits": {t: None for t in TRUE_SCALP_TARGETS},
        "stop_ts": None,
    }
    _true_scalp_pending.append(e)
    _true_scalp_last_signal[key] = now_ts

    # V4.13: attach frozen profit-protection shadow to this scalp entry.
    _start_profit_shadow(e)

    print(
        "TRUE SCALP SHADOW | "
        f"{side} | p {probability:.1%} | "
        f"ask {feat['entry_ask']:.0%} | "
        f"{feat['minutes_left']:.2f}m left | "
        "target +10c before -10c"
    )

def _finalize_true_scalp(e, now_ts):
    f = e["features"]
    hit10 = e["hits"][0.10] is not None

    row = {
        "signal_id": e["signal_id"],
        "contract": e["contract"],
        "side": e["side"],
        "signal_timestamp_utc": e["signal_timestamp_utc"],
        "scalp_probability": e["scalp_probability"],
        "entry_ask": e["entry_ask"],
        "entry_bid": e["entry_bid"],
        "seconds_left": e["seconds_left"],
        "minutes_left": f["minutes_left"],
        "btc_gap_side": f["btc_gap_side"],
        "abs_gap": f["abs_gap"],
        "btc_move_15s_side": f["btc_move_15s_side"],
        "btc_move_30s_side": f["btc_move_30s_side"],
        "btc_move_60s_side": f["btc_move_60s_side"],
        "ask_move_15s": f["ask_move_15s"],
        "ask_move_30s": f["ask_move_30s"],
        "ask_move_60s": f["ask_move_60s"],
        "bounce_from_low": f["bounce_from_low"],
        "drawdown_from_high": f["drawdown_from_high"],
        "ask_position_60": f["ask_position_60"],
        "outcome_timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "observed_seconds": max(0, int(now_ts - e["entry_ts"])),
        "max_future_bid": e["max_future_bid"],
        "min_future_bid": e["min_future_bid"],
        "hit_10c": hit10,
        "seconds_to_10c": (
            None if e["hits"][0.10] is None
            else round(e["hits"][0.10] - e["entry_ts"],1)
        ),
        "hit_15c": e["hits"][0.15] is not None,
        "seconds_to_15c": (
            None if e["hits"][0.15] is None
            else round(e["hits"][0.15] - e["entry_ts"],1)
        ),
        "hit_20c": e["hits"][0.20] is not None,
        "seconds_to_20c": (
            None if e["hits"][0.20] is None
            else round(e["hits"][0.20] - e["entry_ts"],1)
        ),
        "stop_10c_hit": e["stop_ts"] is not None,
        "stop_seconds": (
            None if e["stop_ts"] is None
            else round(e["stop_ts"] - e["entry_ts"],1)
        ),
        "result_10c_before_stop": hit10,
        "notes": "FROZEN DEVELOPMENT CANDIDATE — FORWARD SHADOW ONLY",
    }
    append_csv(TRUE_SCALP_LOG, TRUE_SCALP_FIELDS, row)

def _update_true_scalp_pending(snap, now_ts):
    finished = []
    for e in _true_scalp_pending:
        if e["contract"] != snap["contract"]:
            finished.append(e)
            continue

        bid = snap.get(f"{e['side'].lower()}_bid")
        if bid is None:
            continue
        bid = float(bid)

        e["max_future_bid"] = max(e["max_future_bid"], bid)
        e["min_future_bid"] = min(e["min_future_bid"], bid)

        if (
            e["stop_ts"] is None
            and bid <= e["entry_ask"] - TRUE_SCALP_STOP
        ):
            e["stop_ts"] = now_ts

        for t in TRUE_SCALP_TARGETS:
            if (
                e["hits"][t] is None
                and e["stop_ts"] is None
                and bid >= e["entry_ask"] + t
            ):
                e["hits"][t] = now_ts

        if (
            now_ts - e["entry_ts"] >= TRUE_SCALP_HORIZON_SECONDS
            or float(snap["seconds_left"]) <= 0
        ):
            finished.append(e)

    for e in finished:
        _finalize_true_scalp(e, now_ts)
        try:
            _true_scalp_pending.remove(e)
        except ValueError:
            pass

_train_true_scalp_candidate()
print(f"True scalp forward log: {TRUE_SCALP_LOG}")





# V4.9.2: retain the just-ended contract long enough to write the complete
# 60-reading CF Benchmarks settlement window after Kalshi removes it from the
# active-market list.
_brti_last_contract_meta = None
_brti_finalized_contracts = set()

def _try_finalize_brti_contract(meta, now):
    if not meta:
        return False

    ticker = meta["ticker"]
    if ticker in _brti_finalized_contracts:
        return True

    close_dt = meta["close_dt"]
    # Wait slightly beyond close so the final CF publication has arrived.
    if now < close_dt + timedelta(seconds=2):
        return False

    try:
        btc_now = get_btc_spot()
    except Exception:
        btc_now = meta.get("last_btc")
        if btc_now is None:
            return False

    b = _brti_contract_snapshot(
        close_dt, meta["target"], btc_now
    )
    if b is None:
        return False

    # Do not declare success until the exact 60 one-second readings exist.
    if b["final60_count"] < 60:
        return False

    _log_brti_parity(
        now,
        ticker,
        meta["target"],
        0.0,
        btc_now,
        close_dt,
        b,
    )

    print(
        "BRTI FINALIZED | "
        f"{ticker} | "
        f"{b['final60_count']}/60 readings | "
        f"avg ${b['final60_avg']:,.2f} | "
        f"side {b['final60_side']} | "
        f"complete {b['final60_complete']}"
    )

    _brti_finalized_contracts.add(ticker)
    return True

print("Direct CF Benchmarks BRTI parity shadow: STARTING")
print("BRTI source: Kalshi CF Benchmarks passthrough / BRTI / PER_SECOND")
print(f"BRTI parity log: {BRTI_PARITY_LOG}")
_brti_thread = threading.Thread(
    target=_brti_poller,
    name="direct-brti-poller",
    daemon=True,
)
_brti_thread.start()

iteration = 0
while running:
    cycle_start = time.time()
    try:
        market = get_active_market()
        if market is None:
            _now_gap = datetime.now(timezone.utc)
            _try_finalize_brti_contract(_brti_last_contract_meta, _now_gap)
            print("NO ACTIVE KXBTC15M CONTRACT — retrying...")
            time.sleep(POLL_SECONDS)
            continue

        now = datetime.now(timezone.utc)
        now_ts = now.timestamp()
        ticker = str(market.get("ticker",""))
        target = extract_target(market)
        close_dt = parse_dt(market.get("close_time"))
        up_bid = num(market.get("yes_bid_dollars"))
        up_ask = num(market.get("yes_ask_dollars"))
        down_bid = num(market.get("no_bid_dollars"))
        down_ask = num(market.get("no_ask_dollars"))
        btc = get_btc_spot()

        if target is None or close_dt is None:
            raise RuntimeError("Active market missing target/clock after exact-market fallback")

        # If Kalshi has already rolled to a new contract, finalize the previous
        # contract from the retained direct-BRTI buffer before replacing it.
        if (
            _brti_last_contract_meta is not None
            and _brti_last_contract_meta["ticker"] != ticker
        ):
            _try_finalize_brti_contract(_brti_last_contract_meta, now)

        _brti_last_contract_meta = {
            "ticker": ticker,
            "target": float(target),
            "close_dt": close_dt,
            "last_btc": float(btc),
        }

        seconds_left = max(0.0, (close_dt-now).total_seconds())
        btc_gap = btc-target
        if _brti_last_contract_meta is not None:
            _brti_last_contract_meta["last_btc"] = float(btc)

        # On rollover, clear short rolling history so deltas never cross contracts.
        if history and history[-1]["contract"] != ticker:
            history.clear()

        raw = {
            "ts": now_ts, "contract": ticker, "btc": btc,
            "up_ask": up_ask, "down_ask": down_ask,
        }
        history.append(raw)
        while history and now_ts-history[0]["ts"] > MAX_HISTORY_SECONDS:
            history.popleft()

        snap = {
            "timestamp_utc": now.isoformat(),
            "contract": ticker,
            "target": target,
            "seconds_left": round(seconds_left,2),
            "btc_price": btc,
            "btc_gap": btc_gap,
            "up_bid": up_bid, "up_ask": up_ask,
            "up_spread": None if up_bid is None or up_ask is None else up_ask-up_bid,
            "down_bid": down_bid, "down_ask": down_ask,
            "down_spread": None if down_bid is None or down_ask is None else down_ask-down_bid,
        }

        for sec in [5,15,30,60,120]:
            snap[f"btc_move_{sec}s"] = delta("btc", now_ts, sec, btc)
            snap[f"up_ask_move_{sec}s"] = delta("up_ask", now_ts, sec, up_ask)
            snap[f"down_ask_move_{sec}s"] = delta("down_ask", now_ts, sec, down_ask)

        for side in ["up","down"]:
            for sec in [30,60,120]:
                lo, hi = low_high(f"{side}_ask", now_ts, sec)
                snap[f"{side}_low_{sec}s"] = lo
                snap[f"{side}_high_{sec}s"] = hi
            lo60 = snap[f"{side}_low_60s"]
            hi60 = snap[f"{side}_high_60s"]
            cur = snap[f"{side}_ask"]
            snap[f"{side}_bounce_from_60s_low"] = (
                None if cur is None or lo60 is None else cur-lo60
            )
            snap[f"{side}_drawdown_from_60s_high"] = (
                None if cur is None or hi60 is None else hi60-cur
            )

        append_csv(SNAPSHOT_LOG, SNAPSHOT_FIELDS, snap)

        # V4.9 direct BRTI parity shadow — observation only.
        _brti_contract = None
        _brti_row = None
        try:
            _brti_contract = _brti_contract_snapshot(
                close_dt, target, btc
            )
            _brti_row = _log_brti_parity(
                now, ticker, target, seconds_left, btc, close_dt,
                _brti_contract,
            )
        except Exception as _brti_main_error:
            if iteration % 12 == 0:
                print("BRTI PARITY WARNING:", str(_brti_main_error))

        # V4.8.4: recompute target-aware fair/ask/edge live every 5 seconds with rolling BTC history.
        _ec_row = None
        _ec_live = None
        try:
            _ec_live = _live_fair_shadow(
                now, ticker, target, btc, up_ask, down_ask
            )
            if _ec_live is not None:
                _ec_row = log_early_conf_shadow(
                    now, now_ts, ticker, target, seconds_left, btc, btc_gap,
                    _ec_live["side"],
                    _ec_live["ask"],
                    _ec_live["fair"],
                    _ec_live["edge"],
                )
        except Exception as _ec_error:
            if iteration % 12 == 0:
                print("EARLY-CONF SHADOW WARNING:", str(_ec_error))

        # V4.11 unified synchronized early-entry dataset.
        _unified_rows = []
        try:
            _unified_rows = log_unified_subminute(
                now, now_ts, ticker, target, seconds_left,
                btc, btc_gap, snap, _ec_live, _brti_contract,
            )
        except Exception as _unified_error:
            if iteration % 12 == 0:
                print(
                    "UNIFIED SUBMINUTE WARNING:",
                    str(_unified_error),
                )

        # Update existing events BEFORE creating new ones at this timestamp.
        update_pending(snap, now_ts)

        # V4.12 frozen true-scalp candidate — FORWARD SHADOW ONLY.
        _update_true_scalp_pending(snap, now_ts)
        _update_profit_shadow(snap, now_ts, _brti_contract)
        _maybe_true_scalp_signal("UP", snap, now_ts)
        _maybe_true_scalp_signal("DOWN", snap, now_ts)

        maybe_create_event("UP", snap, now_ts)
        maybe_create_event("DOWN", snap, now_ts)

        iteration += 1
        if iteration % 6 == 0:
            # Compact 30-second heartbeat.
            print(
                f"{now.strftime('%H:%M:%S')}Z | {ticker} | "
                f"{seconds_left/60:.2f}m left | BTC gap ${btc_gap:+.2f} | "
                f"UP {up_bid}/{up_ask} | DOWN {down_bid}/{down_ask} | "
                f"pending {len(pending)} | "
                f"profit-shadow {len(_profit_shadow_pending)}"
            )
            if _brti_contract is not None:
                _b = _brti_contract
                print(
                    "  DIRECT BRTI | "
                    f"${_b['value']:,.2f} | "
                    f"vs Coinbase ${_b['minus_coinbase']:+.2f} | "
                    f"gap ${_b['gap']:+.2f} | "
                    f"side {_b['side']} | "
                    f"age {_b['age']:.1f}s | "
                    f"ready {_b['ready']}"
                )
                if seconds_left <= 65:
                    _avg_text = (
                        "N/A" if _b["final60_avg"] is None
                        else f"${_b['final60_avg']:,.2f}"
                    )
                    print(
                        "  BRTI FINAL-60 | "
                        f"{_b['final60_count']}/60 readings | "
                        f"avg {_avg_text} | "
                        f"side {_b['final60_side']} | "
                        f"complete {_b['final60_complete']}"
                    )

            if _ec_row is not None:
                print(
                    "  EARLY-CONF LIVE | "
                    f"{_ec_row['preferred_side']} | "
                    f"fair {_ec_row['preferred_fair']:.1%} | "
                    f"ask {_ec_row['preferred_ask']:.0%} | "
                    f"edge {_ec_row['edge']:+.1%} | "
                    f"persist30 {_ec_row['candidate_persistence_30s']} | "
                    f"candidate {_ec_row['provisional_candidate']}"
                )

            if _unified_rows:
                _pref = next(
                    (
                        r for r in _unified_rows
                        if r.get("preferred_fair_side") is not None
                        and r["side"] == r["preferred_fair_side"]
                    ),
                    next(
                        (
                            r for r in _unified_rows
                            if r.get("brti_agrees_side") is True
                        ),
                        _unified_rows[0],
                    ),
                )
                _fair_txt = (
                    "warming"
                    if _pref["side_fair"] is None
                    else f"{_pref['side_fair']:.1%}"
                )
                _edge_txt = (
                    "warming"
                    if _pref["side_edge"] is None
                    else f"{_pref['side_edge']:+.1%}"
                )
                print(
                    "  UNIFIED EARLY | "
                    f"{_pref['side']} | "
                    f"ask {_pref['side_ask']:.0%} | "
                    f"fair {_fair_txt} | "
                    f"edge {_edge_txt} | "
                    f"BRTI agree {_pref['brti_agrees_side']} | "
                    f"persist30 {_pref['candidate_persistence_30s']} | "
                    f"lag15 {_pref['kalshi_lag_15s']} | "
                    f"reversal {_pref['reversal_state']}"
                )
            save_state()

    except Exception as e:
        print(f"SHADOW WARNING: {type(e).__name__}: {e}")

    elapsed = time.time()-cycle_start
    sleep_for = max(0.25, POLL_SECONDS-elapsed)
    time.sleep(sleep_for)

# Finalize pending rows with partial observation on shutdown.
now_ts = time.time()
for e in list(pending):
    finalize_event(e, now_ts)
pending.clear()
save_state()

print("SCALP SHADOW STOPPED CLEANLY")
print(f"Snapshots: {SNAPSHOT_LOG}")
print(f"Events: {EVENT_LOG}")
