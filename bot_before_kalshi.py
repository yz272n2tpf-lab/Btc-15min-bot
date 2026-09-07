from sklearn.model_selection import TimeSeriesSplit
timeframes = ["15m", "10m", "5m", "4m", "3m", "1m", "45s", "30s", "15s", "10s", "5s"]
print(timeframes)
roles = {"15m": "trend", "10m": "trend", "5m": "decision", "4m": "momentum", "3m": "momentum", "1m": "trigger", "45s": "short", "30s": "short", "15s": "short", "10s": "short", "5s": "short"}
print(roles)
import requests
import pandas as pd
import time
from datetime import datetime, timezone, timedelta

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
                    

                    

                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                    