from pathlib import Path
import csv
import json
import time
import urllib.request
from datetime import datetime, timezone
from collections import deque

PRODUCT = "BTC-USD"
TRADES_URL = f"https://api.exchange.coinbase.com/products/{PRODUCT}/trades"
BOOK_URL = f"https://api.exchange.coinbase.com/products/{PRODUCT}/book?level=2"

OUT = Path("btc_large_flow_shadow_log.csv")
INTERVAL_SECONDS = 30
ROLLING_WINDOWS = 40  # ~20 minutes at 30-second intervals

# "Large" is intentionally adaptive-first. Absolute dollar buckets are
# also logged so we can later study $250k/$500k/$1m+ bursts explicitly.
ABS_LARGE_THRESHOLDS = [250_000, 500_000, 1_000_000]

print("=== BTC LARGE FLOW SHADOW COLLECTOR ===")
print("Purpose: add abnormal buy/sell flow context to FINAL 15-minute UP/DOWN research.")
print("Signal-only: YES")
print("Orders placed: NO")
print("bot.py modified: NO")
print("Scalp logic changed: NO")
print()
print(f"Refresh interval: {INTERVAL_SECONDS} seconds")
print("Press Ctrl+C to stop.")
print()

def get_json(url):
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        },
    )
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read().decode("utf-8"))

def safe_float(x, default=0.0):
    try:
        return float(x)
    except Exception:
        return default

def zscore(value, history):
    if len(history) < 8:
        return 0.0
    arr = list(history)
    mean = sum(arr) / len(arr)
    var = sum((x - mean) ** 2 for x in arr) / len(arr)
    sd = var ** 0.5
    if sd <= 1e-12:
        return 0.0
    return (value - mean) / sd

def fetch_trade_window():
    trades = get_json(TRADES_URL)
    if not isinstance(trades, list):
        raise RuntimeError("Coinbase trades response was not a list")

    parsed = []

    for t in trades:
        price = safe_float(t.get("price"))
        size = safe_float(t.get("size"))
        maker_side = str(t.get("side") or "").lower()

        if price <= 0 or size <= 0:
            continue

        notional = price * size

        # Coinbase Exchange trade 'side' is the maker side.
        # Aggressive/taker side is therefore the opposite.
        if maker_side == "sell":
            aggressive_side = "BUY"
        elif maker_side == "buy":
            aggressive_side = "SELL"
        else:
            aggressive_side = "UNKNOWN"

        parsed.append({
            "trade_id": str(t.get("trade_id") or ""),
            "price": price,
            "size": size,
            "notional": notional,
            "aggressive_side": aggressive_side,
            "time": str(t.get("time") or ""),
        })

    return parsed

def fetch_book():
    book = get_json(BOOK_URL)

    bids = book.get("bids") or []
    asks = book.get("asks") or []

    def side_notional(levels, n=25):
        total = 0.0
        for row in levels[:n]:
            if len(row) < 2:
                continue
            px = safe_float(row[0])
            qty = safe_float(row[1])
            total += px * qty
        return total

    bid_depth = side_notional(bids)
    ask_depth = side_notional(asks)

    denom = bid_depth + ask_depth
    book_imbalance = (
        (bid_depth - ask_depth) / denom
        if denom > 0 else 0.0
    )

    best_bid = safe_float(bids[0][0]) if bids else 0.0
    best_ask = safe_float(asks[0][0]) if asks else 0.0
    mid = (
        (best_bid + best_ask) / 2
        if best_bid > 0 and best_ask > 0
        else max(best_bid, best_ask)
    )

    return {
        "bid_depth_25": bid_depth,
        "ask_depth_25": ask_depth,
        "book_imbalance": book_imbalance,
        "best_bid": best_bid,
        "best_ask": best_ask,
        "mid": mid,
    }

header = [
    "timestamp_utc",
    "mid_price",
    "price_change_30s",
    "trade_count",
    "aggressive_buy_notional",
    "aggressive_sell_notional",
    "total_notional",
    "flow_imbalance",
    "largest_trade_notional",
    "largest_trade_side",
    "trades_ge_250k",
    "trades_ge_500k",
    "trades_ge_1m",
    "notional_zscore",
    "buy_notional_zscore",
    "sell_notional_zscore",
    "bid_depth_25",
    "ask_depth_25",
    "book_imbalance",
    "flow_label",
    "absorption_label",
]

if not OUT.exists():
    with OUT.open("w", newline="") as f:
        csv.writer(f).writerow(header)

seen_trade_ids = set()
total_hist = deque(maxlen=ROLLING_WINDOWS)
buy_hist = deque(maxlen=ROLLING_WINDOWS)
sell_hist = deque(maxlen=ROLLING_WINDOWS)

last_mid = None

while True:
    cycle_start = time.time()

    try:
        trades = fetch_trade_window()
        book = fetch_book()

        # Only count trades not seen during prior cycles.
        fresh = []
        for t in trades:
            tid = t["trade_id"]
            if tid and tid in seen_trade_ids:
                continue
            fresh.append(t)
            if tid:
                seen_trade_ids.add(tid)

        # Prevent unbounded memory growth.
        if len(seen_trade_ids) > 10000:
            recent_ids = {
                t["trade_id"] for t in trades
                if t["trade_id"]
            }
            seen_trade_ids = recent_ids

        buy_notional = sum(
            t["notional"] for t in fresh
            if t["aggressive_side"] == "BUY"
        )
        sell_notional = sum(
            t["notional"] for t in fresh
            if t["aggressive_side"] == "SELL"
        )
        total_notional = buy_notional + sell_notional

        denom = buy_notional + sell_notional
        flow_imbalance = (
            (buy_notional - sell_notional) / denom
            if denom > 0 else 0.0
        )

        if fresh:
            largest = max(fresh, key=lambda x: x["notional"])
            largest_notional = largest["notional"]
            largest_side = largest["aggressive_side"]
        else:
            largest_notional = 0.0
            largest_side = "NONE"

        bucket_counts = []
        for threshold in ABS_LARGE_THRESHOLDS:
            bucket_counts.append(
                sum(1 for t in fresh if t["notional"] >= threshold)
            )

        total_z = zscore(total_notional, total_hist)
        buy_z = zscore(buy_notional, buy_hist)
        sell_z = zscore(sell_notional, sell_hist)

        mid = book["mid"]
        if last_mid is None or last_mid <= 0:
            price_change = 0.0
        else:
            price_change = mid - last_mid

        # Flow classification.
        if total_z >= 2.5 and flow_imbalance >= 0.40:
            flow_label = "ABNORMAL_BUY_PRESSURE"
        elif total_z >= 2.5 and flow_imbalance <= -0.40:
            flow_label = "ABNORMAL_SELL_PRESSURE"
        elif bucket_counts[2] > 0 and flow_imbalance > 0:
            flow_label = "MILLION_PLUS_BUY_BURST"
        elif bucket_counts[2] > 0 and flow_imbalance < 0:
            flow_label = "MILLION_PLUS_SELL_BURST"
        elif abs(flow_imbalance) >= 0.50:
            flow_label = (
                "BUY_IMBALANCE"
                if flow_imbalance > 0
                else "SELL_IMBALANCE"
            )
        else:
            flow_label = "NORMAL_OR_MIXED"

        # Crude absorption research flag:
        # strong directional flow with little or opposite price response.
        absorption_label = "NONE"

        if buy_notional > 0 and flow_imbalance >= 0.50:
            if price_change <= 0:
                absorption_label = "BUY_FLOW_ABSORBED_OR_REVERSED"
            elif abs(price_change) < 5:
                absorption_label = "BUY_FLOW_WEAK_FOLLOW_THROUGH"

        if sell_notional > 0 and flow_imbalance <= -0.50:
            if price_change >= 0:
                absorption_label = "SELL_FLOW_ABSORBED_OR_REVERSED"
            elif abs(price_change) < 5:
                absorption_label = "SELL_FLOW_WEAK_FOLLOW_THROUGH"

        now = datetime.now(timezone.utc).isoformat()

        row = [
            now,
            mid,
            price_change,
            len(fresh),
            buy_notional,
            sell_notional,
            total_notional,
            flow_imbalance,
            largest_notional,
            largest_side,
            bucket_counts[0],
            bucket_counts[1],
            bucket_counts[2],
            total_z,
            buy_z,
            sell_z,
            book["bid_depth_25"],
            book["ask_depth_25"],
            book["book_imbalance"],
            flow_label,
            absorption_label,
        ]

        with OUT.open("a", newline="") as f:
            csv.writer(f).writerow(row)

        print(
            f"{now} | "
            f"BTC ${mid:,.2f} | "
            f"Δ ${price_change:+.2f} | "
            f"BUY ${buy_notional:,.0f} | "
            f"SELL ${sell_notional:,.0f} | "
            f"IMB {flow_imbalance:+.1%} | "
            f"LARGEST ${largest_notional:,.0f} {largest_side} | "
            f"Z {total_z:+.2f} | "
            f"{flow_label} | {absorption_label}"
        )

        total_hist.append(total_notional)
        buy_hist.append(buy_notional)
        sell_hist.append(sell_notional)
        last_mid = mid

    except KeyboardInterrupt:
        print()
        print("Collector stopped by user.")
        break
    except Exception as e:
        print("COLLECTOR ERROR:", repr(e))

    elapsed = time.time() - cycle_start
    sleep_for = max(1.0, INTERVAL_SECONDS - elapsed)

    try:
        time.sleep(sleep_for)
    except KeyboardInterrupt:
        print()
        print("Collector stopped by user.")
        break
