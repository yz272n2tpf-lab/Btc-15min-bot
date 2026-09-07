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
import time
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

print("\n--- STRICT 15-MIN + V3 FINAL GATE ---")
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
print(
    "STRICT MODEL READY:",
    "YES" if _strict_model_ready else "NO",
)
print(
    "BRTI/KALSHI GATE READY:",
    "YES" if bool(_v3_brti_gate_ready) else "NO",
)

if _final_15m_ready:
    print("ENTRY STATUS: READY")
    print("ENTRY SIDE:", _final_15m_direction)
else:
    print("ENTRY STATUS: WAIT")

print("EXPECTED FINAL OUTCOME:", _final_15m_direction)
print("MODEL LEAN:", _model_15m_direction)

if "_strict_error_text" in globals():
    print("Strict-gate safety note:", _strict_error_text)

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
                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    