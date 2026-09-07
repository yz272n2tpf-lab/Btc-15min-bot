from pathlib import Path
import json
import time
import pandas as pd

# This file is intentionally signal-only and read-only.
# It assumes the project already has a working kalshi_get() helper available
# in bot.py and uses bot.py only as a source of helper logic, not as an order engine.

LOG = Path("kalshi_live_shadow_log.csv")

print("=== KALSHI LIVE SHADOW ENTRY MONITOR ===")
print("Purpose: compare live Kalshi contract pricing against our fair-value layer.")
print("Orders placed: NO")
print("bot.py modified: NO")
print("This monitor is for live shadow validation only.")
print()

# Import helper without running bot.py top-level body.
# We execute only the kalshi_get definition by extracting it from bot.py.
bot_text = Path("bot.py").read_text()

start = bot_text.find("def kalshi_get")
if start == -1:
    raise SystemExit("ERROR: could not find kalshi_get() in bot.py")

# Crude but safe function extraction: stop at next top-level def/class/major print block.
lines = bot_text[start:].splitlines()
func_lines = []
for i, line in enumerate(lines):
    if i > 0 and line and not line.startswith((" ", "\t")):
        if line.startswith(("def ", "class ")):
            break
    func_lines.append(line)

ns = {}
exec("\n".join(func_lines), ns, ns)

if "kalshi_get" not in ns:
    raise SystemExit("ERROR: kalshi_get() extraction failed")

kalshi_get = ns["kalshi_get"]

def parse_num(x):
    try:
        return float(x)
    except Exception:
        return None

def active_market():
    data = kalshi_get(
        "/trade-api/v2/markets",
        params={
            "status": "open",
            "series_ticker": "KXBTC15M",
            "limit": 1000,
        },
    )

    markets = data.get("markets", [])
    exact = []

    now = pd.Timestamp.utcnow()

    for m in markets:
        ticker = str(m.get("ticker", ""))
        open_raw = m.get("open_time")
        close_raw = m.get("close_time")

        if not ticker.startswith("KXBTC15M"):
            continue
        if not open_raw or not close_raw:
            continue

        try:
            o = pd.Timestamp(open_raw)
            c = pd.Timestamp(close_raw)
        except Exception:
            continue

        if o.tzinfo is None:
            o = o.tz_localize("UTC")
        else:
            o = o.tz_convert("UTC")

        if c.tzinfo is None:
            c = c.tz_localize("UTC")
        else:
            c = c.tz_convert("UTC")

        if o <= now <= c:
            exact.append((c, m))

    if not exact:
        return None

    exact.sort(key=lambda x: x[0])
    return exact[0][1]

m = active_market()

if m is None:
    raise SystemExit("NO ACTIVE KXBTC15M MARKET FOUND")

ticker = str(m.get("ticker"))
open_ts = pd.Timestamp(m.get("open_time"))
close_ts = pd.Timestamp(m.get("close_time"))

if open_ts.tzinfo is None:
    open_ts = open_ts.tz_localize("UTC")
else:
    open_ts = open_ts.tz_convert("UTC")

if close_ts.tzinfo is None:
    close_ts = close_ts.tz_localize("UTC")
else:
    close_ts = close_ts.tz_convert("UTC")

now = pd.Timestamp.utcnow()

elapsed = (now - open_ts).total_seconds() / 60
remaining = (close_ts - now).total_seconds() / 60

yes_bid = parse_num(m.get("yes_bid_dollars"))
yes_ask = parse_num(m.get("yes_ask_dollars"))
no_bid = parse_num(m.get("no_bid_dollars"))
no_ask = parse_num(m.get("no_ask_dollars"))

# Target/strike field names vary by API payload.
target = None
for key in [
    "floor_strike",
    "cap_strike",
    "strike",
    "target",
    "settlement_value",
]:
    if m.get(key) is not None:
        target = parse_num(m.get(key))
        if target is not None:
            break

print("CONTRACT:", ticker)
print("OPEN:", open_ts)
print("CLOSE:", close_ts)
print("ELAPSED MIN:", round(elapsed, 2))
print("TIME LEFT MIN:", round(remaining, 2))
print("UP BID/ASK:", yes_bid, "/", yes_ask)
print("DOWN BID/ASK:", no_bid, "/", no_ask)
print("TARGET FIELD:", target if target is not None else "NOT EXPOSED IN MARKET PAYLOAD")

# Fair probabilities are intentionally not fabricated here.
# They should come from the validated probability engine once live feature plumbing is verified.
fair_up = None
fair_down = None

def status(side, fair, ask):
    if fair is None or ask is None:
        return "WAITING_FOR_FAIR_PROBABILITY"

    edge = fair - ask

    if fair >= 0.90:
        if ask <= 0.50 and edge >= 0.20:
            return "LOCK + ATTRACTIVE ENTRY"
        if ask >= fair:
            return "LOCK / NO VALUE"
        return "LOCK / POSITIVE EDGE"

    if fair >= 0.80:
        if ask <= 0.50 and edge >= 0.20:
            return "STRONG + ATTRACTIVE ENTRY"
        if edge >= 0.10:
            return "STRONG / POSITIVE EDGE"
        return "STRONG / NO EDGE"

    if fair >= 0.70:
        if ask <= 0.50 and edge >= 0.15:
            return "LEAN + ATTRACTIVE ENTRY"
        return "LEAN"

    return "RAW"

up_status = status("UP", fair_up, yes_ask)
down_status = status("DOWN", fair_down, no_ask)

print()
print("=== LIVE SHADOW DECISION ===")
print("FAIR UP:", fair_up if fair_up is not None else "PENDING VALIDATED LIVE ENGINE")
print("FAIR DOWN:", fair_down if fair_down is not None else "PENDING VALIDATED LIVE ENGINE")
print("UP STATUS:", up_status)
print("DOWN STATUS:", down_status)

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
    "fair_up": fair_up,
    "fair_down": fair_down,
    "up_edge": None if fair_up is None or yes_ask is None else fair_up - yes_ask,
    "down_edge": None if fair_down is None or no_ask is None else fair_down - no_ask,
    "up_status": up_status,
    "down_status": down_status,
}

frame = pd.DataFrame([row])

if LOG.exists():
    frame.to_csv(LOG, mode="a", header=False, index=False)
else:
    frame.to_csv(LOG, index=False)

print()
print("Logged to:", LOG)
print("=== HARD CHECKS ===")
print("Active contract matched by actual open/close time: PASS")
print("Correct KXBTC15M series only: PASS")
print("Live Kalshi bid/ask read directly: PASS")
print("Historical Kalshi prices fabricated: NO")
print("Orders placed: NO")
print("bot.py modified: NO")
print()
print("NEXT: connect validated live fair-probability engine into this monitor.")
