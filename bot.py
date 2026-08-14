from sklearn.model_selection import TimeSeriesSplit
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

model_data["acceleration"] = (
    model_data["return_1"] - model_data["return_3"] / 3
)

model_data["volatility"] = model_data["return_1"].rolling(6).std()
model_data["momentum_3"] = model_data["Close"].pct_change(3)
    


feature_columns = [
    "return_1",
    "return_3",
    "return_5",
    "sma_distance",
"acceleration",
    "trend_5_20",
    "volatility",
    "momentum_3",
] 
model_data = model_data.dropna(
    subset=feature_columns + ["outcome"]
).copy()

split_index = int(len(model_data) * 0.8)

train_data = model_data.iloc[:split_index]
test_data = model_data.iloc[split_index:]

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