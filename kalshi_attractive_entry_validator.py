from pathlib import Path
import pandas as pd

LOG_PATH = Path("kalshi_live_fair_value_shadow_log.csv")
RESULTS_PATH = Path("kalshi_contract_results.csv")
OUT_PATH = Path("kalshi_attractive_entry_report.csv")

REQUIRED_COLUMNS = {
    "timestamp_utc","ticker","target","elapsed_min","remaining_min","coinbase_close",
    "distance_target","current_side","flip_prob","stay_prob","fair_up","fair_down",
    "preferred_side","fair_preferred","up_bid","up_ask","down_bid","down_ask",
    "preferred_ask","edge","signal_status","entry_status"
}

def fail(msg):
    raise SystemExit(f"\nERROR: {msg}\n")

def price_bucket(price):
    if pd.isna(price):
        return "UNKNOWN"
    if price <= 0.30:
        return "<=30c"
    if price <= 0.40:
        return "31-40c"
    if price <= 0.50:
        return "41-50c"
    return ">50c"

def load_log():
    if not LOG_PATH.exists():
        fail(f"{LOG_PATH} was not found.")
    df = pd.read_csv(LOG_PATH)
    missing = REQUIRED_COLUMNS - set(df.columns)
    if missing:
        fail("Missing columns: " + ", ".join(sorted(missing)))
    for col in [
        "target","elapsed_min","remaining_min","coinbase_close","distance_target",
        "flip_prob","stay_prob","fair_up","fair_down","fair_preferred",
        "up_bid","up_ask","down_bid","down_ask","preferred_ask","edge"
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    return df.dropna(subset=["timestamp_utc","ticker"]).sort_values(["ticker","timestamp_utc"])

def load_results():
    if not RESULTS_PATH.exists():
        return pd.DataFrame(columns=["ticker","final_side"])
    r = pd.read_csv(RESULTS_PATH)
    if not {"ticker","final_side"}.issubset(r.columns):
        fail(f"{RESULTS_PATH} must contain ticker,final_side")
    r = r[["ticker","final_side"]].copy()
    r["final_side"] = r["final_side"].astype(str).str.upper().str.strip()
    r = r[r["final_side"].isin(["UP","DOWN"])]
    return r.drop_duplicates("ticker", keep="last")

def build_candidates(df, results):
    work = df.copy()
    work["entry_price"] = work["preferred_ask"]
    work["entry_cents"] = (work["entry_price"] * 100).round(1)
    work["price_bucket"] = work["entry_price"].apply(price_bucket)

    attractive = work[
        work["preferred_side"].isin(["UP","DOWN"])
        & work["entry_price"].notna()
        & (work["entry_price"] <= 0.50)
        & (work["fair_preferred"] > work["entry_price"])
    ].copy()

    if attractive.empty:
        return attractive

    attractive["candidate_key"] = (
        attractive["ticker"].astype(str) + "|" +
        attractive["preferred_side"].astype(str) + "|" +
        attractive["price_bucket"].astype(str)
    )

    firsts = attractive.drop_duplicates("candidate_key", keep="first").copy()
    idx = attractive.groupby(["ticker","preferred_side"])["entry_price"].idxmin()
    cheapest = attractive.loc[idx].copy()
    cheapest["candidate_key"] = (
        cheapest["ticker"].astype(str) + "|" +
        cheapest["preferred_side"].astype(str) + "|CHEAPEST"
    )

    c = pd.concat([firsts, cheapest], ignore_index=True)
    c = c.drop_duplicates(["ticker","preferred_side","candidate_key"], keep="first")
    c = c.merge(results, on="ticker", how="left")
    c["final_side"] = c["final_side"].fillna("UNRESOLVED")
    c["won_final"] = c.apply(
        lambda r: "UNRESOLVED" if r["final_side"] == "UNRESOLVED"
        else ("YES" if r["preferred_side"] == r["final_side"] else "NO"),
        axis=1
    )

    cols = [
        "timestamp_utc","ticker","target","preferred_side","final_side","won_final",
        "entry_price","entry_cents","price_bucket","fair_preferred","edge","flip_prob",
        "stay_prob","elapsed_min","remaining_min","distance_target",
        "signal_status","entry_status","candidate_key"
    ]
    return c[cols].sort_values(["ticker","timestamp_utc"])

def summarize(c):
    print("\n=== KALSHI ATTRACTIVE ENTRY VALIDATOR ===")
    print("Judge cheap entries by the FINAL 15-minute winner.")
    print("Temporary flips do NOT automatically invalidate an entry.")
    print("Signal-only: YES")
    print("Orders placed: NO")
    print("bot.py modified: NO")

    if c.empty:
        print("\nNo attractive <=50c candidates logged yet.")
        return

    print(f"\nAttractive candidates: {len(c)}")
    print(f"Contracts represented: {c['ticker'].nunique()}")
    print(f"Resolved: {(c['final_side'] != 'UNRESOLVED').sum()}")
    print(f"Unresolved: {(c['final_side'] == 'UNRESOLVED').sum()}")

    cols = ["ticker","preferred_side","entry_cents","fair_preferred","edge",
            "remaining_min","flip_prob","final_side","won_final"]
    print("\n=== CANDIDATES ===")
    print(c[cols].to_string(index=False))

    resolved = c[c["final_side"] != "UNRESOLVED"].copy()
    if resolved.empty:
        print("\nNo settled results yet.")
        print("When available, create kalshi_contract_results.csv with:")
        print("ticker,final_side")
        print("KXBTC15M-...,UP")
        print("KXBTC15M-...,DOWN")
        return

    print("\n=== FINAL WIN RATE BY ENTRY PRICE ===")
    for bucket in ["<=30c","31-40c","41-50c"]:
        g = resolved[resolved["price_bucket"] == bucket]
        if len(g):
            wins = (g["won_final"] == "YES").sum()
            print(f"{bucket}: n={len(g)} wins={wins} win_rate={wins/len(g):.3f}")

def main():
    df = load_log()
    results = load_results()
    candidates = build_candidates(df, results)
    candidates.to_csv(OUT_PATH, index=False)
    summarize(candidates)
    print(f"\nSaved report: {OUT_PATH}")

if __name__ == "__main__":
    main()
