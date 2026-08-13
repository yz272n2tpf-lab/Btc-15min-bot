timeframes = ["15m", "10m", "5m", "4m", "3m", "1m", "45s", "30s", "15s", "10s", "5s"]
print(timeframes)
roles = {"15m": "trend", "10m": "trend", "5m": "decision", "4m": "momentum", "3m": "momentum", "1m": "trigger", "45s": "short", "30s": "short", "15s": "short", "10s": "short", "5s": "short"}
print(roles)
import yfinance as yf
btc=yf.Ticker("BTC-USD")
data=btc.history(period="1d",interval="15m")
print(data.tail())
print("Current BTC price:", data.iloc[-1]["Close"])
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
print("Contract end:", contract_end)
start_price = data.loc[contract_start]["Open"]
print("15-minute start price:", start_price)
move_from_start = data.iloc[-1]["Close"] - start_price
print("Move from 15-minute start:", move_from_start)
move_percent = (move_from_start / start_price) * 100
print("Move from start (%):", move_percent)
recent_change = data.iloc[-1]["Close"] - data.iloc[-2]["Close"]
print("Recent 15-minute change:", recent_change)
data_1m = btc.history(period="1d", interval="1m")
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
training_data = btc.history(period="60d", interval="15m")
print("Training rows:", len(training_data))
training_data["future_close"] = training_data["Close"].shift(-1)
training_data["outcome"] = training_data["future_close"] > training_data["Close"]
training_data = training_data.dropna(subset=["future_close"])
print("UP outcomes:", training_data["outcome"].sum())
print("DOWN outcomes:", (~training_data["outcome"]).sum())
split_index = int(len(training_data) * 0.8)
train_data = training_data.iloc[:split_index]
test_data = training_data.iloc[split_index:]
baseline_up = train_data["outcome"].mean()
baseline_accuracy = max(baseline_up, 1 - baseline_up)
print("Baseline accuracy:", baseline_accuracy)
train_data["SMA20"] = train_data["Close"].rolling(20).mean()
test_data["SMA20"] = test_data["Close"].rolling(20).mean()
test_valid = test_data.dropna(subset=["SMA20"]).copy()
test_valid["prediction"] = test_valid["Close"] > test_valid["SMA20"]
sma_accuracy = (test_valid["prediction"] == test_valid["outcome"]).mean()
print("SMA20 test accuracy:", sma_accuracy)
test_valid["momentum_prediction"] = test_valid["Close"].diff() > 0
momentum_accuracy = (test_valid["momentum_prediction"] == test_valid["outcome"]).mean()
print("Momentum test accuracy:", momentum_accuracy)
test_valid["five_min_prediction"] = test_valid["Close"] > test_valid["Close"].shift(5)
five_min_accuracy = (test_valid["five_min_prediction"] == test_valid["outcome"]).mean()
print("5-minute momentum accuracy:", five_min_accuracy)
data_5m = btc.history(period="60d", interval="5m")
print("5-minute rows:", len(data_5m))
data_5m["five_min_change"] = data_5m["Close"].diff().shift(1)
print("5-minute data ready:", len(data_5m))
five_min_features = data_5m[["five_min_change"]].copy()
print("5-minute feature ready")
training_data = training_data.sort_index()
test_data["five_min_change"] = five_min_features["five_min_change"].reindex(test_data.index, method="ffill")
test_valid["five_min_change"] = test_data["five_min_change"].reindex(test_valid.index)
test_valid["five_min_signal"] = test_valid["five_min_change"] > 0
five_min_aligned_accuracy = (test_valid["five_min_signal"] == test_valid["outcome"]).mean()
print("Aligned 5-minute accuracy:", five_min_aligned_accuracy)
test_valid["sma_signal"] = test_valid["Close"] > test_valid["SMA20"]
test_valid["momentum_signal"] = test_valid["Close"].diff() > 0
test_valid["five_min_signal"] = test_valid["five_min_change"] > 0
test_valid["all_agree"] = (test_valid["sma_signal"] == test_valid["momentum_signal"]) & (test_valid["sma_signal"] == test_valid["five_min_signal"])
agreement_accuracy = (test_valid.loc[test_valid["all_agree"], "sma_signal"] == test_valid.loc[test_valid["all_agree"], "outcome"]).mean()
print("All-three agreement accuracy:", agreement_accuracy)
# Predictive 15-minute features
model_data = training_data.copy()

model_data["return_1"] = model_data["Close"].pct_change(1)
model_data["return_3"] = model_data["Close"].pct_change(3)
model_data["return_5"] = model_data["Close"].pct_change(5)

model_data["sma_5"] = model_data["Close"].rolling(5).mean()
model_data["sma_20"] = model_data["Close"].rolling(20).mean()

model_data["sma_distance"] = (
    model_data["Close"] / model_data["sma_20"] - 1
)

model_data["trend_5_20"] = (
    model_data["sma_5"] / model_data["sma_20"] - 1
)

model_data["volatility_10"] = (
    model_data["return_1"].rolling(10).std()
)

model_data = model_data.dropna()

print("Predictive feature rows:", len(model_data))
print("Features ready")
feature_columns = [
    "return_1",
    "return_3",
    "return_5",
    "sma_distance",
    "trend_5_20",
    "volatility_10"
]

X = model_data[feature_columns]
y = model_data["outcome"]

split = int(len(model_data) * 0.8)

X_train = X.iloc[:split]
X_test = X.iloc[split:]
y_train = y.iloc[:split]
y_test = y.iloc[split:]

print("Model train rows:", len(X_train))
print("Model test rows:", len(X_test))
print("Target balance:", y_test.mean())
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score

model = RandomForestClassifier(
    n_estimators=300,
    max_depth=6,
    random_state=42,
    class_weight="balanced"
)

model.fit(X_train, y_train)

pred = model.predict(X_test)

model_accuracy = accuracy_score(y_test, pred)

print("Model accuracy:", model_accuracy)