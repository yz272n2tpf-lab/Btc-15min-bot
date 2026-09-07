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
from sklearn.ensemble import RandomForestClassifier
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
# against the ACTUAL Kalshi ask. The strict FINAL OUTCOME gate is unchanged.
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
# V4.7 VALIDATED ENTRY WINNER
# ------------------------------------------------------------
# Historical actual Kalshi 1-minute bid/ask tournament:
# Validation: 16/16 correct
# Untouched holdout: 20/22 correct = 90.9%
# Avg actual ask: 31.9c
# Avg time left: 6.09m
#
# Exact winning rule:
#   ask <= 45c
#   fair >= 75%
#   edge >= 8pt
#   2m <= time left <= 10m
#   abs target gap >= $25
#   no persistence requirement
#   no strengthening requirement
#   no forced current-side agreement
#
# ENTRY guidance only — NEVER FINAL authority.
# ============================================================
_entry_winner_ready = False

if not _fair_ready:
    _opportunity_status = 'WATCH'
    _opportunity_reason = 'Target-aware fair probability unavailable — fail closed'
elif _opportunity_ask is None or _opportunity_edge is None:
    _opportunity_status = 'WATCH'
    _opportunity_reason = 'Waiting for complete live Kalshi ask/fair-value data'
else:
    try:
        _entry_time_left = (
            max(0.0, 15.0-float(_strict_elapsed_minute))
            if _strict_elapsed_minute is not None else None
        )
        _entry_gap = (
            abs(float(_fair_distance_target))
            if _fair_distance_target is not None else None
        )

        _entry_winner_ready = bool(
            _opportunity_ask <= 0.45
            and _opportunity_model_prob >= 0.75
            and _opportunity_edge >= 0.08
            and _entry_time_left is not None
            and 2.0 <= _entry_time_left <= 10.0
            and _entry_gap is not None
            and _entry_gap >= 25.0
        )
    except Exception:
        _entry_winner_ready = False

    if _entry_winner_ready:
        _opportunity_status = 'OPPORTUNITY'
        _opportunity_reason = (
            'Validated entry winner: ask <=45c, fair >=75%, edge >=8pt, '
            '2-10m left, target gap >=$25'
        )
    elif _opportunity_ask > 0.45:
        _opportunity_status = 'WAIT'
        _opportunity_reason = 'Preferred side is above the validated <=45c entry ceiling'
    elif _entry_time_left is not None and (
        _entry_time_left < 2.0 or _entry_time_left > 10.0
    ):
        _opportunity_status = 'WATCH'
        _opportunity_reason = 'Price is acceptable, but outside validated 2-10m entry window'
    elif _entry_gap is not None and _entry_gap < 25.0:
        _opportunity_status = 'WATCH'
        _opportunity_reason = 'Price is acceptable, but target gap is below validated $25 minimum'
    elif _opportunity_model_prob < 0.75:
        _opportunity_status = 'WATCH'
        _opportunity_reason = 'Price is acceptable, but fair probability is below validated 75%'
    elif _opportunity_edge < 0.08:
        _opportunity_status = 'WATCH'
        _opportunity_reason = 'Price is acceptable, but model edge is below validated 8pt'
    else:
        _opportunity_status = 'WATCH'
        _opportunity_reason = 'Validated entry rule has not fully qualified'

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
print('VALIDATED ENTRY READY:', 'YES' if _entry_winner_ready else 'NO')
print(
    'ENTRY TIME WINDOW:',
    f'{_entry_time_left:.2f}m left' if '_entry_time_left' in globals() and _entry_time_left is not None else 'N/A'
)
print(
    'ENTRY TARGET GAP:',
    f'${_entry_gap:.2f}' if '_entry_gap' in globals() and _entry_gap is not None else 'N/A'
)
print('REASON:', _opportunity_reason)
print('FINAL-CALL AUTHORITY: NO — entry/value guidance only')

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
            "distance/range >=1.0x"
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
    _two_final_reason = "Final-call evidence has not cleared the existing strict gate"

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
_snapshot_log = Path('kalshi_two_output_live_log_v4_7.csv')
_snapshot_fields = [
    'timestamp_utc','contract','elapsed_min','time_left_min',
    'btc_price','kalshi_target','target_gap_dollars',
    'up_ask','down_ask',
    'raw_general_side','raw_general_confidence',
    'fair_ready','fair_up','fair_down','fair_preferred_side','fair_preferred',
    'fair_flip_prob','fair_stay_prob','preferred_kalshi_ask','fair_edge_vs_ask',
    'opportunity_status','price_zone','entry_winner_ready','entry_time_left','entry_target_gap',
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
    'entry_winner_ready': bool(_entry_winner_ready),
    'entry_time_left': _entry_time_left if '_entry_time_left' in globals() else None,
    'entry_target_gap': _entry_gap if '_entry_gap' in globals() else None,
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


    # ==========================================
# INTRAPERIOD SCALP SIGNAL
# ==========================================

print("\n--- SCALP SIGNAL ---")
print("1-minute move:", one_minute_change)
print("5-minute move:", five_minute_change)
print("Momentum change:", momentum_change)
scalp_score = 0

if one_minute_change > 0:
    scalp_score += 1
else:
    scalp_score -= 1

if momentum_change > 0:
    scalp_score += 1
else:
    scalp_score -= 1

if five_minute_change > 0:
    scalp_score += 1
else:
    scalp_score -= 1

print("Scalp score:", scalp_score)
if scalp_score >= 3:
    scalp_signal = "BUY UP"
elif scalp_score <= -3:
    scalp_signal = "BUY DOWN"
else:
    scalp_signal = "WAIT"

print("Scalp signal:", scalp_signal)
reversal_signal = "NONE"

if five_minute_change < 0 and momentum_change > 0:
    reversal_signal = "POSSIBLE UP REVERSAL"
elif five_minute_change > 0 and momentum_change < 0:
    reversal_signal = "POSSIBLE DOWN REVERSAL"

print("Reversal watch:", reversal_signal)
# ==========================================
# SCALP BACKTEST
# ==========================================

print("\n--- SCALP BACKTEST ---")
scalp_bt = data_1m.copy()

scalp_bt["change_1m"] = scalp_bt["Close"].diff(1)
scalp_bt["change_5m"] = scalp_bt["Close"].diff(5)

scalp_bt["previous_1m_change"] = scalp_bt["Close"].shift(1) - scalp_bt["Close"].shift(2)

scalp_bt["momentum_change"] = (
    scalp_bt["change_1m"] - scalp_bt["previous_1m_change"]
)
scalp_bt["early_score"] = 0
scalp_bt.loc[scalp_bt["change_1m"] > 0, "early_score"] += 1
scalp_bt.loc[scalp_bt["change_1m"] <= 0, "early_score"] -= 1
scalp_bt.loc[scalp_bt["momentum_change"] > 0, "early_score"] += 1
scalp_bt.loc[scalp_bt["momentum_change"] <= 0, "early_score"] -= 1
print("Early score counts:", scalp_bt["early_score"].value_counts().sort_index().to_dict())
scalp_bt["future_close_5m"] = scalp_bt["Close"].shift(-5)

early_up = scalp_bt["early_score"] == 2
early_down = scalp_bt["early_score"] == -2

early_up_accuracy = (
    scalp_bt.loc[early_up, "future_close_5m"]
    > scalp_bt.loc[early_up, "Close"]
).mean()

early_down_accuracy = (
    scalp_bt.loc[early_down, "future_close_5m"]
    < scalp_bt.loc[early_down, "Close"]
).mean()

print("EARLY +2 -> UP 5m accuracy:", early_up_accuracy)
print("EARLY -2 -> DOWN 5m accuracy:", early_down_accuracy)
early_up = scalp_bt["early_score"] == 2
early_down = scalp_bt["early_score"] == -2
scalp_bt["future_close_5m"] = scalp_bt["Close"].shift(-5)
scalp_bt["future_high_5m"] = scalp_bt["High"].shift(-1).rolling(5).max().shift(-4)
scalp_bt["future_low_5m"] = scalp_bt["Low"].shift(-1).rolling(5).min().shift(-4)
early_up_move = scalp_bt.loc[early_up, "future_high_5m"] - scalp_bt.loc[early_up, "Close"]
early_down_move = scalp_bt.loc[early_down, "Close"] - scalp_bt.loc[early_down, "future_low_5m"]
for target in [10, 15, 20, 30, 40, 50]:
        up_hit_rate = (early_up_move >= target).mean()
        down_hit_rate = (early_down_move >= target).mean()
        print(f"${target} target | EARLY UP: {up_hit_rate:.3f} | EARLY DOWN: {down_hit_rate:.3f}")
strong_up = early_up & (scalp_bt["change_5m"] > 0)
strong_down = early_down & (scalp_bt["change_5m"] < 0)
strong_up_move = scalp_bt.loc[strong_up, "future_high_5m"] - scalp_bt.loc[strong_up, "Close"]
strong_down_move = scalp_bt.loc[strong_down, "Close"] - scalp_bt.loc[strong_down, "future_low_5m"]
print("STRONG signal counts:", strong_up.sum(), strong_down.sum())
for target in [10, 15, 20, 30, 40, 50]:
                strong_up_rate = (strong_up_move >= target).mean()
                strong_down_rate = (strong_down_move >= target).mean()
                print(f"${target} STRONG | UP: {strong_up_rate:.3f} | DOWN: {strong_down_rate:.3f}")


print("Scalp backtest rows:", len(scalp_bt))
scalp_bt["scalp_score"] = 0

scalp_bt.loc[scalp_bt["change_1m"] > 0, "scalp_score"] += 1
scalp_bt.loc[scalp_bt["change_1m"] <= 0, "scalp_score"] -= 1

scalp_bt.loc[scalp_bt["change_5m"] > 0, "scalp_score"] += 1
scalp_bt.loc[scalp_bt["change_5m"] <= 0, "scalp_score"] -= 1

scalp_bt.loc[scalp_bt["momentum_change"] > 0, "scalp_score"] += 1
scalp_bt.loc[scalp_bt["momentum_change"] <= 0, "scalp_score"] -= 1

print("Historical BUY UP signals:", (scalp_bt["scalp_score"] == 3).sum())
print("Historical BUY DOWN signals:", (scalp_bt["scalp_score"] == -3).sum())
scalp_bt["next_close"] = scalp_bt["Close"].shift(-1)

up_mask = scalp_bt["scalp_score"] == 3
down_mask = scalp_bt["scalp_score"] == -3

up_accuracy = (
    scalp_bt.loc[up_mask, "next_close"]
    > scalp_bt.loc[up_mask, "Close"]
).mean()

down_accuracy = (
    scalp_bt.loc[down_mask, "next_close"]
    < scalp_bt.loc[down_mask, "Close"]
).mean()

print("BUY UP next-minute accuracy:", up_accuracy)
print("BUY DOWN next-minute accuracy:", down_accuracy)
scalp_bt["future_high_3m"] = (
    scalp_bt["High"].shift(-1)
    .rolling(3)
    .max()
    .shift(-2)
)

scalp_bt["future_low_3m"] = (
    scalp_bt["Low"].shift(-1)
    .rolling(3)
    .min()
    .shift(-2)
)

scalp_bt["max_up_move_3m"] = (
    scalp_bt["future_high_3m"] - scalp_bt["Close"]
)

scalp_bt["max_down_move_3m"] = (
    scalp_bt["Close"] - scalp_bt["future_low_3m"]
)
up_3m_moves = scalp_bt.loc[up_mask, "max_up_move_3m"]
down_3m_moves = scalp_bt.loc[down_mask, "max_down_move_3m"]

print("BUY UP avg best move next 3m:", up_3m_moves.mean())
print("BUY UP median best move next 3m:", up_3m_moves.median())

print("BUY DOWN avg best move next 3m:", down_3m_moves.mean())
print("BUY DOWN median best move next 3m:", down_3m_moves.median())
for target in [10, 15, 20, 25, 30]:
    up_hit_rate = (up_3m_moves >= target).mean()
    down_hit_rate = (down_3m_moves >= target).mean()

    print(
        f"${target} target -> "
        f"BUY UP: {up_hit_rate:.3f} | "
        f"BUY DOWN: {down_hit_rate:.3f}"
    )
    print("\n--- SCALP SCORE STRENGTH ---")

for score_threshold in [1, 2, 3]:
    strong_up = scalp_bt["scalp_score"] >= score_threshold
    strong_down = scalp_bt["scalp_score"] <= -score_threshold

    print(
        f"Score {score_threshold}+ | "
        f"UP signals: {strong_up.sum()} | "
        f"DOWN signals: {strong_down.sum()}"
    )
    scalp_bt["contract_start_time"] = scalp_bt.index.floor("15min")

scalp_bt["contract_start_price"] = (
    scalp_bt.groupby("contract_start_time")["Open"]
    .transform("first")
)

scalp_bt["move_from_contract_start"] = (
    scalp_bt["Close"] - scalp_bt["contract_start_price"]
)

scalp_bt["minute_in_contract"] = (
    (scalp_bt.index - scalp_bt["contract_start_time"])
    .dt.total_seconds() / 60
)



print("\n--- DISTANCE x TIME TEST ---")

for minute_start, minute_end in [(0, 5), (5, 10), (10, 15)]:
    time_mask = (
        (scalp_bt["minute_in_contract"] >= minute_start) &
        (scalp_bt["minute_in_contract"] < minute_end)
    )

    print(f"\nMinutes {minute_start}-{minute_end}:")

    for distance in [20, 30, 40, 50]:
        up_setup = (
            time_mask &
            (scalp_bt["scalp_score"] >= 3) &
            (scalp_bt["move_from_contract_start"] <= -distance)
        )

        down_setup = (
            time_mask &
            (scalp_bt["scalp_score"] <= -3) &
            (scalp_bt["move_from_contract_start"] >= distance)
        )

        up_hits = (
            scalp_bt.loc[up_setup, "future_high_3m"] -
            scalp_bt.loc[up_setup, "Close"]
        ) >= 10

        down_hits = (
            scalp_bt.loc[down_setup, "Close"] -
            scalp_bt.loc[down_setup, "future_low_3m"]
        ) >= 10

        print(
            f"${distance} | "
            f"UP {up_setup.sum()} @ {up_hits.mean():.3f} | "
            f"DOWN {down_setup.sum()} @ {down_hits.mean():.3f}"
        )

print(
    "Contract-start distance sample:",
    scalp_bt["move_from_contract_start"].tail()
)


scalp_bt["minute_in_contract"] = (
    (scalp_bt.index - scalp_bt["contract_start_time"])
    .dt.total_seconds() / 60
)
print("\n--- CONTRACT DISTANCE TEST ---")


for distance in [10, 20, 30, 40, 50]:
    up_setup = (
        (scalp_bt["scalp_score"] >= 3) &
        (scalp_bt["move_from_contract_start"] <= -distance)
    )

    down_setup = (
        (scalp_bt["scalp_score"] <= -3) &
        (scalp_bt["move_from_contract_start"] >= distance)
    )

    up_hits = (
        scalp_bt.loc[up_setup, "future_high_3m"] -
        scalp_bt.loc[up_setup, "Close"]
    ) >= 10

    down_hits = (
        scalp_bt.loc[down_setup, "Close"] -
        scalp_bt.loc[down_setup, "future_low_3m"]
    ) >= 10

    print(
        f"${distance} distance | "
        f"UP: {up_setup.sum()} signals, {up_hits.mean():.3f} hit rate | "
        f"DOWN: {down_setup.sum()} signals, {down_hits.mean():.3f} hit rate"
    )
    for minute_start, minute_end in [(0, 5), (5, 10), (10, 15)]:
        time_mask = (
                    (scalp_bt["minute_in_contract"] >= minute_start) &
                    (scalp_bt["minute_in_contract"] < minute_end)
                    )
        print(f"\nMinutes {minute_start}-{minute_end}:")
        for distance in [20, 30, 40, 50]:

                    up_setup = (
                                      time_mask &
                                      (scalp_bt["scalp_score"] >= 3) &

                                             (scalp_bt["move_from_contract_start"] <= -distance)
                                             )
                    down_setup = (
                        time_mask &
                        (scalp_bt["scalp_score"] <= -3) &
                        (scalp_bt["move_from_contract_start"] >= distance)
                        )
                    up_hits = (

scalp_bt.loc[up_setup, "future_high_3m"] -
scalp_bt.loc[up_setup, "Close"]
) >= 10
                    down_hits = (
                        scalp_bt.loc[down_setup, "Close"] -
                        scalp_bt.loc[down_setup, "future_low_3m"]
                        ) >= 10
                    print(
                        f"${distance} | "
                        f"UP {up_setup.sum()} @ {up_hits.mean():.3f} | "
                        f"DOWN {down_setup.sum()} @ {down_hits.mean():.3f}"
                        )
                    

                    
print("\n--- KALSHI MARKET TEST ---")
_market_data = kalshi_get(
    "/trade-api/v2/markets",
    params={
        "status": "open",
        "series_ticker": "KXBTC15M",
        "limit": 1000,
    },
)


_exact_matches = []

for _market in _market_data.get("markets", []):
    _ticker = str(_market.get("ticker", ""))
    _event_ticker = str(_market.get("event_ticker", ""))
    _title = str(_market.get("title", ""))
    _subtitle = str(_market.get("subtitle", ""))

    _search_text = " ".join([
        _ticker,
        _event_ticker,
        _title,
        _subtitle,
    ]).upper()

    if (
        ("BTC" in _search_text or "BITCOIN" in _search_text)
        and (
            "15 MIN" in _search_text
            or "15-MIN" in _search_text
            or "15MIN" in _search_text
            or "UP OR DOWN" in _search_text
        )
    ):
        _exact_matches.append(_market)

print("MATCHES FOUND:", len(_exact_matches))
print()

for _market in _exact_matches:
    print("TICKER:", _market.get("ticker"))
    print("EVENT TICKER:", _market.get("event_ticker"))
    print("TITLE:", _market.get("title"))
    print("SUBTITLE:", _market.get("subtitle"))
    print("OPEN TIME:", _market.get("open_time"))
    print("CLOSE TIME:", _market.get("close_time"))
    print("YES BID:", _market.get("yes_bid_dollars"))
print("YES ASK:", _market.get("yes_ask_dollars"))
print("NO BID:", _market.get("no_bid_dollars"))
print("NO ASK:", _market.get("no_ask_dollars"))
print("-" * 60)
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    
