from pathlib import Path
import time
import requests
import pandas as pd

LOG_PATH = Path("kalshi_live_fair_value_shadow_log.csv")
RESULTS_PATH = Path("kalshi_contract_results.csv")

BASE_URL = "https://external-api.kalshi.com/trade-api/v2"


def get_market_result(ticker):
    url = f"{BASE_URL}/markets/{ticker}"
    r = requests.get(url, timeout=15)
    r.raise_for_status()
    market = r.json().get("market", {})

    status = str(market.get("status", "")).lower().strip()
    result = str(market.get("result", "")).lower().strip()

    if status != "finalized":

        return None

    if result == "yes":
        return "UP"
    if result == "no":
        return "DOWN"

    return None


def main():
    if not LOG_PATH.exists():
        raise SystemExit(f"Missing {LOG_PATH}")

    df = pd.read_csv(LOG_PATH)
    if "ticker" not in df.columns:
        raise SystemExit("Log is missing ticker column")

    tickers = sorted(df["ticker"].dropna().astype(str).unique())

    existing = pd.DataFrame(columns=["ticker", "final_side"])
    if RESULTS_PATH.exists():
        try:
            existing = pd.read_csv(RESULTS_PATH)
        except Exception:
            existing = pd.DataFrame(columns=["ticker", "final_side"])

    known = {}
    if {"ticker", "final_side"}.issubset(existing.columns):
        for _, row in existing.iterrows():
            side = str(row["final_side"]).upper().strip()
            if side in ("UP", "DOWN"):
                known[str(row["ticker"])] = side

    print("=== KALSHI SETTLEMENT RESOLVER ===")
    print("Uses Kalshi market result only.")
    print("Orders placed: NO")
    print("bot.py modified: NO")
    print()

    rows = []
    for ticker in tickers:
        if ticker in known:
            side = known[ticker]
            print(f"{ticker} -> already saved: {side}")
            rows.append({"ticker": ticker, "final_side": side})
            continue

        try:
            side = get_market_result(ticker)
            if side:
                print(f"{ticker} -> SETTLED {side}")
                rows.append({"ticker": ticker, "final_side": side})
            else:
                print(f"{ticker} -> not settled yet")
        except Exception as e:
            print(f"{ticker} -> API error: {e}")

        time.sleep(0.15)

    if rows:
        out = pd.DataFrame(rows).drop_duplicates("ticker", keep="last")
        out.to_csv(RESULTS_PATH, index=False)
        print()
        print(f"Saved: {RESULTS_PATH}")
        print(f"Resolved contracts saved: {len(out)}")
    else:
        print()
        print("No settled contracts available yet.")


if __name__ == "__main__":
    main()
