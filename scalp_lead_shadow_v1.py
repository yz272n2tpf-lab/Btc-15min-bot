#!/usr/bin/env python3
"""SCALP LEAD SHADOW V1

Independent, signal-only research collector for the BTC15 scalp/reversal ladder.
It does NOT place orders and does NOT change FINAL/Early/production logic.

Goal: measure whether BTC/BRTI sub-minute evidence appears BEFORE Kalshi reprices
an inexpensive UP/DOWN side, then measure executable future BID expansion.
"""

import os, re, time, base64
from collections import deque
from datetime import datetime, timezone

import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

POLL_SECONDS = 1.0
HISTORY_SECONDS = 180
FORWARD_SECONDS = 90
MAX_ENTRY_ASK = 0.45            # research ceiling only, NOT a target entry
BROAD_BTC_5S = 4.0              # deliberately broad collection thresholds
BROAD_BTC_15S = 8.0
MAX_KALSHI_MOVE_5S = 0.03       # still relatively unrepriced
TARGETS = (0.05, 0.10, 0.15, 0.25)

KALSHI_KEY_ID = os.environ["KALSHI_KEY_ID"].strip()
PRIVATE_B64 = os.environ["KALSHI_PRIVATE_KEY_B64"].strip()
PRIVATE_KEY = serialization.load_pem_private_key(base64.b64decode(PRIVATE_B64), password=None)

MARKET_BASE = "https://api.elections.kalshi.com"
EXTERNAL_BASE = "https://external-api.kalshi.com"
BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"
COINBASE_URL = "https://api.exchange.coinbase.com/products/BTC-USD/ticker"

hist = deque()
pending = []
last_candidate = {}


def headers(method, path):
    ts = str(int(time.time() * 1000))
    msg = ts + method.upper() + path
    sig = PRIVATE_KEY.sign(
        msg.encode(),
        padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KALSHI_KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode(),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }


def parse_dt(v):
    try:
        return datetime.fromisoformat(str(v).replace("Z", "+00:00"))
    except Exception:
        return None


def num(v):
    try:
        return float(v)
    except Exception:
        return None


def active_market():
    path = "/trade-api/v2/markets"
    r = requests.get(
        MARKET_BASE + path,
        headers=headers("GET", path),
        params={"status": "open", "series_ticker": "KXBTC15M", "limit": 1000},
        timeout=7,
    )
    r.raise_for_status()
    now = datetime.now(timezone.utc)
    rows = []
    for m in r.json().get("markets", []):
        op, cl = parse_dt(m.get("open_time")), parse_dt(m.get("close_time"))
        if op and cl and op <= now < cl and str(m.get("ticker", "")).startswith("KXBTC15M"):
            rows.append(m)
    return min(rows, key=lambda x: parse_dt(x.get("close_time"))) if rows else None


def target_of(m):
    for k in ("floor_strike", "functional_strike"):
        v = num(m.get(k))
        if v is not None:
            return v
    text = " ".join(str(m.get(k) or "") for k in ("yes_sub_title", "title", "subtitle"))
    mm = re.search(r"Target\s*Price\s*:\s*\$?\s*([0-9][0-9,]*(?:\.[0-9]+)?)", text, re.I)
    return float(mm.group(1).replace(",", "")) if mm else None


def coinbase():
    r = requests.get(COINBASE_URL, timeout=5)
    r.raise_for_status()
    return float(r.json()["price"])


def _find_brti_value(obj):
    """Resilient parser for Kalshi CF Benchmarks response shapes."""
    found = []
    def walk(x):
        if isinstance(x, dict):
            if "value" in x:
                v = num(x.get("value"))
                if v is not None and 1000 < v < 1000000:
                    found.append(v)
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
    walk(obj)
    return found[-1] if found else None


def brti():
    try:
        r = requests.get(
            EXTERNAL_BASE + BRTI_PATH,
            headers=headers("GET", BRTI_PATH),
            params={"id": "BRTI", "maxResolution": "PER_SECOND"},
            timeout=5,
        )
        r.raise_for_status()
        return _find_brti_value(r.json())
    except Exception:
        return None


def point_ago(now_ts, seconds, ticker):
    want = now_ts - seconds
    for row in reversed(hist):
        if row["ticker"] == ticker and row["ts"] <= want:
            return row
    return None


def delta(row, side, field, seconds):
    old = point_ago(row["ts"], seconds, row["ticker"])
    if not old:
        return None
    if field == "btc":
        return (row["btc"] - old["btc"]) * (1 if side == "UP" else -1)
    if field == "brti":
        if row["brti"] is None or old["brti"] is None:
            return None
        return (row["brti"] - old["brti"]) * (1 if side == "UP" else -1)
    return row[f"{side.lower()}_ask"] - old[f"{side.lower()}_ask"]


def broad_candidate(row, side):
    ask = row[f"{side.lower()}_ask"]
    if ask is None or ask > MAX_ENTRY_ASK:
        return False, {}
    btc5 = delta(row, side, "btc", 5)
    btc15 = delta(row, side, "btc", 15)
    brti5 = delta(row, side, "brti", 5)
    ask5 = delta(row, side, "ask", 5)
    if btc5 is None or btc15 is None or ask5 is None:
        return False, {}
    btc_push = btc5 >= BROAD_BTC_5S or btc15 >= BROAD_BTC_15S
    brti_ok = brti5 is None or brti5 > 0
    unrepriced = ask5 <= MAX_KALSHI_MOVE_5S
    return bool(btc_push and brti_ok and unrepriced), {
        "btc5": btc5, "btc15": btc15, "brti5": brti5, "ask5": ask5,
    }


def create_candidate(row, side, feats):
    key = (row["ticker"], side)
    if row["ts"] - last_candidate.get(key, 0) < 20:
        return
    last_candidate[key] = row["ts"]
    ask = row[f"{side.lower()}_ask"]
    bid = row[f"{side.lower()}_bid"]
    ev = {
        "ticker": row["ticker"], "side": side, "ts": row["ts"],
        "entry_ask": ask, "entry_bid": bid, "max_bid": bid, "min_bid": bid,
        "first_5c": None, "first_10c": None, "first_ask_5c": None,
        "features": feats,
    }
    pending.append(ev)
    print(
        f"LEAD_SHADOW CANDIDATE | {row['ticker']} | {side} | ask {ask:.3f} | "
        f"btc5 ${feats['btc5']:+.2f} | btc15 ${feats['btc15']:+.2f} | "
        f"brti5 {('N/A' if feats['brti5'] is None else f'${feats[\"brti5\"]:+.2f}')} | "
        f"ask5 {feats['ask5']:+.3f} | left {row['seconds_left']:.0f}s",
        flush=True,
    )


def update_pending(row):
    done = []
    for e in pending:
        if e["ticker"] != row["ticker"]:
            done.append(e); continue
        side = e["side"].lower()
        bid, ask = row[f"{side}_bid"], row[f"{side}_ask"]
        if bid is not None:
            e["max_bid"] = max(e["max_bid"], bid)
            e["min_bid"] = min(e["min_bid"], bid)
            gain = bid - e["entry_ask"]
            if gain >= 0.05 and e["first_5c"] is None: e["first_5c"] = row["ts"]
            if gain >= 0.10 and e["first_10c"] is None: e["first_10c"] = row["ts"]
        if ask is not None and ask - e["entry_ask"] >= 0.05 and e["first_ask_5c"] is None:
            e["first_ask_5c"] = row["ts"]
        if row["ts"] - e["ts"] >= FORWARD_SECONDS or row["seconds_left"] <= 0:
            done.append(e)
    for e in done:
        try: pending.remove(e)
        except ValueError: pass
        elapsed = max(0, row["ts"] - e["ts"])
        gain = e["max_bid"] - e["entry_ask"]
        adverse = e["min_bid"] - e["entry_ask"]
        t5 = None if e["first_5c"] is None else e["first_5c"] - e["ts"]
        t10 = None if e["first_10c"] is None else e["first_10c"] - e["ts"]
        repr5 = None if e["first_ask_5c"] is None else e["first_ask_5c"] - e["ts"]
        print(
            f"LEAD_SHADOW RESULT | {e['ticker']} | {e['side']} | entry {e['entry_ask']:.3f} | "
            f"max_exec_gain {gain:+.3f} | adverse {adverse:+.3f} | "
            f"to_exec+5c {t5} | to_exec+10c {t10} | to_ask_reprice+5c {repr5} | obs {elapsed:.0f}s",
            flush=True,
        )


def snapshot():
    m = active_market()
    if not m:
        return None
    now = datetime.now(timezone.utc)
    cl = parse_dt(m.get("close_time"))
    ticker = str(m.get("ticker"))
    up_bid = num(m.get("yes_bid_dollars")); up_ask = num(m.get("yes_ask_dollars"))
    dn_bid = num(m.get("no_bid_dollars")); dn_ask = num(m.get("no_ask_dollars"))
    if None in (up_bid, up_ask, dn_bid, dn_ask):
        return None
    return {
        "ts": time.time(), "now": now, "ticker": ticker,
        "seconds_left": max(0.0, (cl-now).total_seconds()),
        "target": target_of(m), "btc": coinbase(), "brti": brti(),
        "up_bid": up_bid, "up_ask": up_ask, "down_bid": dn_bid, "down_ask": dn_ask,
    }


print("SCALP LEAD SHADOW V1 START | 1s polling | signal-only | NO ORDERS", flush=True)
print("Purpose: timestamp BTC/BRTI impulse evidence BEFORE Kalshi repricing and measure future executable expansion.", flush=True)

while True:
    started = time.time()
    try:
        row = snapshot()
        if row:
            hist.append(row)
            cutoff = row["ts"] - HISTORY_SECONDS
            while hist and hist[0]["ts"] < cutoff:
                hist.popleft()
            update_pending(row)
            for side in ("UP", "DOWN"):
                ok, feats = broad_candidate(row, side)
                if ok:
                    create_candidate(row, side, feats)
            if int(row["ts"]) % 30 == 0:
                print(
                    f"LEAD_SHADOW HEARTBEAT | {row['ticker']} | {row['seconds_left']/60:.2f}m | "
                    f"BTC {row['btc']:.2f} | BRTI {('N/A' if row['brti'] is None else f'{row[\"brti\"]:.2f}')} | "
                    f"UP {row['up_ask']:.3f} | DOWN {row['down_ask']:.3f} | pending {len(pending)}",
                    flush=True,
                )
    except Exception as exc:
        print(f"LEAD_SHADOW WARNING | {type(exc).__name__}: {exc}", flush=True)
    delay = max(0.05, POLL_SECONDS - (time.time()-started))
    time.sleep(delay)
