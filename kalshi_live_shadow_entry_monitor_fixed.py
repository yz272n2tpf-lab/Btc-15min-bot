from pathlib import Path
import base64
import time
import requests
import pandas as pd
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

LOG = Path("kalshi_live_shadow_log.csv")

print("=== KALSHI LIVE SHADOW ENTRY MONITOR - FIXED ===")
print("Purpose: verify exact live KXBTC15M contract timing and pricing.")
print("Read-only: YES")
print("Orders placed: NO")
print("bot.py modified: NO")
print()

# --- Read-only Kalshi authentication ---
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

def num(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None

def utc_ts(value):
    if not value:
        return None

    try:
        ts = pd.Timestamp(value)
    except Exception:
        return None

    if ts.tzinfo is None:
        ts = ts.tz_localize("UTC")
    else:
        ts = ts.tz_convert("UTC")

    return ts

def get_active_market():
    data = kalshi_get(
        "/trade-api/v2/markets",
        params={
            "status": "open",
            "series_ticker": "KXBTC15M",
            "limit": 1000,
        },
    )

    now = pd.Timestamp.now(tz="UTC")
    active = []

    for market in data.get("markets", []):
        ticker = str(market.get("ticker", ""))

        if not ticker.startswith("KXBTC15M"):
            continue

        open_ts = utc_ts(market.get("open_time"))
        close_ts = utc_ts(market.get("close_time"))

        if open_ts is None or close_ts is None:
            continue

        if open_ts <= now < close_ts:
            active.append((close_ts, market))

    if not active:
        return None

    active.sort(key=lambda x: x[0])
    return active[0][1]

market = get_active_market()

if market is None:
    raise SystemExit("NO ACTIVE KXBTC15M MARKET FOUND")

ticker = str(market.get("ticker"))
open_ts = utc_ts(market.get("open_time"))
close_ts = utc_ts(market.get("close_time"))
now = pd.Timestamp.now(tz="UTC")

elapsed = (now - open_ts).total_seconds() / 60.0
remaining = (close_ts - now).total_seconds() / 60.0

yes_bid = num(market.get("yes_bid_dollars"))
yes_ask = num(market.get("yes_ask_dollars"))
no_bid = num(market.get("no_bid_dollars"))
no_ask = num(market.get("no_ask_dollars"))

target = None
target_key = None

for key in [
    "floor_strike",
    "cap_strike",
    "strike",
    "target",
    "settlement_value",
]:
    value = num(market.get(key))
    if value is not None:
        target = value
        target_key = key
        break

print("CONTRACT:", ticker)
print("TITLE:", market.get("title"))
print("OPEN UTC:", open_ts)
print("CLOSE UTC:", close_ts)
print("ELAPSED MIN:", round(elapsed, 2))
print("TIME LEFT MIN:", round(remaining, 2))
print("UP BID/ASK:", yes_bid, "/", yes_ask)
print("DOWN BID/ASK:", no_bid, "/", no_ask)

if target is None:
    print("TARGET:", "NOT EXPOSED IN THIS MARKET PAYLOAD")
else:
    print("TARGET:", target, f"({target_key})")

print()
print("=== LIVE SHADOW PLUMBING CHECK ===")
print("Exact active KXBTC15M contract selected: YES")
print("Actual Kalshi clock used: YES")
print("Actual Kalshi bid/ask used: YES")
print("Fair probability connected: NOT YET")
print("Orders placed: NO")

row = {
    "timestamp_utc": now.isoformat(),
    "ticker": ticker,
    "open_utc": open_ts.isoformat(),
    "close_utc": close_ts.isoformat(),
    "elapsed_min": elapsed,
    "remaining_min": remaining,
    "target": target,
    "up_bid": yes_bid,
    "up_ask": yes_ask,
    "down_bid": no_bid,
    "down_ask": no_ask,
}

frame = pd.DataFrame([row])

if LOG.exists():
    frame.to_csv(LOG, mode="a", header=False, index=False)
else:
    frame.to_csv(LOG, index=False)

print("Logged to:", LOG)
print()
print("NEXT: compare this exact output to the live Kalshi app.")
print("If contract, clock, and prices match, connect calibrated fair probability next.")
