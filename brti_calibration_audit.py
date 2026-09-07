import base64
import time
from datetime import datetime, timezone, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding


# ============================================================
# BRTI / KALSHI TARGET CALIBRATION AUDIT
#
# PURPOSE
# -------
# Compare Kalshi's actual settled BRTI-based values against
# Coinbase's matching 1-minute candles.
#
# For each settled KXBTC15M contract:
#   TARGET BRTI:
#       Kalshi floor_strike
#       compared with Coinbase candle during minute immediately
#       BEFORE contract open.
#
#   FINAL BRTI:
#       Kalshi expiration_value
#       compared with Coinbase candle during final minute BEFORE
#       contract close.
#
# Coinbase proxy values tested:
#   - candle close
#   - OHLC4 = (open + high + low + close) / 4
#   - HL2   = (high + low) / 2
#
# This does NOT assume Coinbase equals BRTI.
# It measures the real historical difference.
#
# NO ORDERS.
# NO CHANGES TO bot.py.
# ============================================================


LOOKBACK_DAYS = 7
MAX_MARKETS = 900

KEY_ID = Path.home().joinpath(".kalshi/key_id").read_text().strip()
PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"

private_key = serialization.load_pem_private_key(
    PRIVATE_KEY_PATH.read_bytes(),
    password=None,
)

KALSHI_BASE_URL = "https://api.elections.kalshi.com"


def kalshi_headers(method, path):
    timestamp = str(int(time.time() * 1000))
    message = timestamp + method + path

    signature = private_key.sign(
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
        timeout=20,
    )
    r.raise_for_status()
    return r.json()


def parse_dt(value):
    if not value:
        return None

    try:
        return datetime.fromisoformat(
            str(value).replace("Z", "+00:00")
        )
    except Exception:
        return None


def number(value):
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def fetch_recent_settled_markets():
    all_markets = []
    cursor = None

    for status in ["settled", "closed"]:
        all_markets = []
        cursor = None

        while len(all_markets) < MAX_MARKETS:
            params = {
                "series_ticker": "KXBTC15M",
                "status": status,
                "limit": min(1000, MAX_MARKETS - len(all_markets)),
            }

            if cursor:
                params["cursor"] = cursor

            try:
                data = kalshi_get(
                    "/trade-api/v2/markets",
                    params=params,
                )
            except requests.HTTPError:
                all_markets = []
                break

            batch = data.get("markets", [])

            if not batch:
                break

            all_markets.extend(batch)

            cursor = data.get("cursor")

            if not cursor:
                break

        if all_markets:
            print("Kalshi historical status used:", status)
            return all_markets

    return []


def fetch_coinbase_candles(start, end):
    url = "https://api.exchange.coinbase.com/products/BTC-USD/candles"

    rows = []
    batch_start = start

    while batch_start < end:
        batch_end = min(
            batch_start + timedelta(minutes=300),
            end,
        )

        params = {
            "granularity": 60,
            "start": batch_start.isoformat(),
            "end": batch_end.isoformat(),
        }

        r = requests.get(
            url,
            params=params,
            timeout=20,
        )

        r.raise_for_status()

        batch = r.json()

        if isinstance(batch, list):
            rows.extend(batch)

        batch_start = batch_end
        time.sleep(0.03)

    df = pd.DataFrame(
        rows,
        columns=[
            "Time",
            "Low",
            "High",
            "Open",
            "Close",
            "Volume",
        ],
    )

    if df.empty:
        return df

    df["Datetime"] = pd.to_datetime(
        df["Time"],
        unit="s",
        utc=True,
    )

    df = (
        df.drop_duplicates("Datetime")
        .sort_values("Datetime")
        .set_index("Datetime")
    )

    df["OHLC4"] = (
        df["Open"]
        + df["High"]
        + df["Low"]
        + df["Close"]
    ) / 4.0

    df["HL2"] = (
        df["High"]
        + df["Low"]
    ) / 2.0

    return df


print("=== BRTI / KALSHI CALIBRATION AUDIT ===")
print("Lookback:", LOOKBACK_DAYS, "days")

markets = fetch_recent_settled_markets()

if not markets:
    raise SystemExit(
        "No settled/closed KXBTC15M markets returned."
    )

cutoff = datetime.now(timezone.utc) - timedelta(
    days=LOOKBACK_DAYS
)

records = []

for m in markets:
    open_dt = parse_dt(m.get("open_time"))
    close_dt = parse_dt(m.get("close_time"))

    target = number(m.get("floor_strike"))
    final = number(m.get("expiration_value"))

    if (
        open_dt is None
        or close_dt is None
        or target is None
        or final is None
    ):
        continue

    if close_dt < cutoff:
        continue

    records.append(
        {
            "ticker": m.get("ticker"),
            "open_dt": open_dt,
            "close_dt": close_dt,
            "target_brti": target,
            "final_brti": final,
            "result": m.get("result"),
        }
    )

if not records:
    raise SystemExit(
        "No recent markets with target + expiration_value found."
    )

contracts = pd.DataFrame(records)

contracts = contracts.sort_values(
    "open_dt"
).drop_duplicates(
    "ticker"
)

print("Usable settled contracts:", len(contracts))

coinbase_start = (
    contracts["open_dt"].min()
    - timedelta(minutes=2)
)

coinbase_end = (
    contracts["close_dt"].max()
    + timedelta(minutes=1)
)

print("Loading matching Coinbase 1-minute candles...")

cb = fetch_coinbase_candles(
    coinbase_start,
    coinbase_end,
)

print("Coinbase 1-minute rows:", len(cb))

if cb.empty:
    raise SystemExit(
        "No Coinbase candles returned."
    )


def get_candle(timestamp):
    minute = pd.Timestamp(
        timestamp
    ).floor("min")

    if minute in cb.index:
        return cb.loc[minute]

    return None


audit_rows = []

for _, row in contracts.iterrows():
    # Kalshi target uses the 60 seconds immediately before open.
    target_minute = (
        pd.Timestamp(row["open_dt"])
        - pd.Timedelta(minutes=1)
    ).floor("min")

    # Kalshi final uses the last 60 seconds before close.
    final_minute = (
        pd.Timestamp(row["close_dt"])
        - pd.Timedelta(minutes=1)
    ).floor("min")

    if target_minute not in cb.index:
        continue

    if final_minute not in cb.index:
        continue

    target_cb = cb.loc[target_minute]
    final_cb = cb.loc[final_minute]

    item = {
        "ticker": row["ticker"],
        "target_brti": row["target_brti"],
        "final_brti": row["final_brti"],
        "result": row["result"],

        "target_cb_close": float(target_cb["Close"]),
        "target_cb_ohlc4": float(target_cb["OHLC4"]),
        "target_cb_hl2": float(target_cb["HL2"]),

        "final_cb_close": float(final_cb["Close"]),
        "final_cb_ohlc4": float(final_cb["OHLC4"]),
        "final_cb_hl2": float(final_cb["HL2"]),
    }

    for proxy in ["close", "ohlc4", "hl2"]:
        item[f"target_err_{proxy}"] = (
            item[f"target_cb_{proxy}"]
            - item["target_brti"]
        )

        item[f"final_err_{proxy}"] = (
            item[f"final_cb_{proxy}"]
            - item["final_brti"]
        )

    audit_rows.append(item)

audit = pd.DataFrame(audit_rows)

if audit.empty:
    raise SystemExit(
        "No contracts aligned to Coinbase candles."
    )

print()
print("Aligned contracts:", len(audit))


def print_error_stats(label, series):
    s = pd.Series(series).dropna()

    if s.empty:
        return

    abs_s = s.abs()

    print(label)
    print(
        "  mean signed error:",
        f"${s.mean():+.2f}"
    )
    print(
        "  median signed error:",
        f"${s.median():+.2f}"
    )
    print(
        "  mean absolute error:",
        f"${abs_s.mean():.2f}"
    )
    print(
        "  median absolute error:",
        f"${abs_s.median():.2f}"
    )
    print(
        "  90th pct absolute error:",
        f"${abs_s.quantile(0.90):.2f}"
    )
    print(
        "  95th pct absolute error:",
        f"${abs_s.quantile(0.95):.2f}"
    )
    print(
        "  max absolute error:",
        f"${abs_s.max():.2f}"
    )


print()
print("=== TARGET-MINUTE CALIBRATION ===")

for proxy in ["close", "ohlc4", "hl2"]:
    print_error_stats(
        proxy.upper(),
        audit[f"target_err_{proxy}"],
    )

print()
print("=== FINAL-MINUTE CALIBRATION ===")

for proxy in ["close", "ohlc4", "hl2"]:
    print_error_stats(
        proxy.upper(),
        audit[f"final_err_{proxy}"],
    )


# Choose best proxy by total mean absolute error across
# both target and final calibration.
scores = {}

for proxy in ["close", "ohlc4", "hl2"]:
    combined_abs = pd.concat(
        [
            audit[f"target_err_{proxy}"].abs(),
            audit[f"final_err_{proxy}"].abs(),
        ],
        ignore_index=True,
    )

    scores[proxy] = combined_abs.mean()

best_proxy = min(
    scores,
    key=scores.get,
)

all_errors = pd.concat(
    [
        audit[f"target_err_{best_proxy}"],
        audit[f"final_err_{best_proxy}"],
    ],
    ignore_index=True,
).dropna()

bias = all_errors.mean()
abs_errors = all_errors.abs()

p90_buffer = abs_errors.quantile(0.90)
p95_buffer = abs_errors.quantile(0.95)

print()
print("=== BEST COINBASE PROXY ===")
print(
    "Best proxy:",
    best_proxy.upper(),
)
print(
    "Combined mean absolute error:",
    f"${scores[best_proxy]:.2f}",
)
print(
    "Estimated Coinbase minus BRTI bias:",
    f"${bias:+.2f}",
)
print(
    "90% historical mismatch buffer:",
    f"${p90_buffer:.2f}",
)
print(
    "95% historical mismatch buffer:",
    f"${p95_buffer:.2f}",
)


# Settlement-direction agreement:
# Would Coinbase proxy have predicted the same UP/DOWN
# outcome as actual Kalshi BRTI final vs BRTI target?
actual_up = (
    audit["final_brti"]
    >= audit["target_brti"]
)

proxy_final = audit[
    f"final_cb_{best_proxy}"
]

# Bias-adjust Coinbase proxy toward estimated BRTI.
proxy_final_adjusted = (
    proxy_final - bias
)

proxy_up_raw = (
    proxy_final
    >= audit["target_brti"]
)

proxy_up_adjusted = (
    proxy_final_adjusted
    >= audit["target_brti"]
)

raw_agreement = (
    proxy_up_raw == actual_up
).mean()

adjusted_agreement = (
    proxy_up_adjusted == actual_up
).mean()

print()
print("=== SETTLEMENT DIRECTION AGREEMENT ===")
print(
    "Raw Coinbase proxy vs Kalshi result:",
    f"{raw_agreement:.3f}",
)
print(
    "Bias-adjusted proxy vs Kalshi result:",
    f"{adjusted_agreement:.3f}",
)


# Most dangerous cases are contracts where actual final BRTI
# was close enough to target that source mismatch matters.
actual_distance = (
    audit["final_brti"]
    - audit["target_brti"]
).abs()

for threshold in [10, 20, 30, 50, 100]:
    mask = actual_distance <= threshold

    if mask.sum() == 0:
        continue

    agree = (
        proxy_up_adjusted[mask]
        == actual_up[mask]
    ).mean()

    print(
        f"Within ${threshold} of Kalshi target:",
        f"{mask.sum()} contracts",
        "| adjusted direction agreement",
        f"{agree:.3f}",
    )


print()
print("=== CALIBRATION VERDICT ===")
print(
    "Use this audit to decide whether Coinbase can be "
    "safely translated into a BRTI-aware target buffer."
)
print(
    "Do NOT treat Coinbase as identical to BRTI."
)
print(
    "NO orders placed."
)
print(
    "NO changes to bot.py."
)

audit.to_csv(
    "brti_calibration_results.csv",
    index=False,
)

print()
print(
    "Saved detailed audit:",
    "brti_calibration_results.csv",
)
