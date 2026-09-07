from pathlib import Path
import pandas as pd

LOG_PATH = Path("kalshi_live_fair_value_shadow_log.csv")
RESULTS_PATH = Path("kalshi_contract_results.csv")

SNAPSHOT_OUT = Path("kalshi_attractive_entry_lifecycle_snapshots.csv")
SUMMARY_OUT = Path("kalshi_attractive_entry_lifecycle_summary.csv")

REQUIRED = {
    "timestamp_utc","ticker","target","elapsed_min","remaining_min",
    "distance_target","flip_prob","stay_prob",
    "fair_up","fair_down","up_ask","down_ask",
    "signal_status","entry_status"
}

def fail(msg):
    raise SystemExit(f"\nERROR: {msg}\n")

def load_log():
    if not LOG_PATH.exists():
        fail(f"Missing {LOG_PATH}")

    df = pd.read_csv(LOG_PATH)
    missing = REQUIRED - set(df.columns)
    if missing:
        fail("Missing columns: " + ", ".join(sorted(missing)))

    for col in [
        "target","elapsed_min","remaining_min","distance_target",
        "flip_prob","stay_prob","fair_up","fair_down","up_ask","down_ask"
    ]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp_utc","ticker"]).copy()
    return df.sort_values(["ticker","timestamp_utc"]).reset_index(drop=True)

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

def build_side_rows(df):
    rows = []

    for _, r in df.iterrows():
        for side in ("UP","DOWN"):
            ask_col = "up_ask" if side == "UP" else "down_ask"
            fair_col = "fair_up" if side == "UP" else "fair_down"

            ask = r.get(ask_col)
            fair = r.get(fair_col)

            if pd.isna(ask) or pd.isna(fair):
                continue

            edge = fair - ask

            rows.append({
                "timestamp_utc": r["timestamp_utc"],
                "ticker": r["ticker"],
                "target": r["target"],
                "side": side,
                "ask": ask,
                "ask_cents": round(ask * 100, 1),
                "fair": fair,
                "fair_pct": round(fair * 100, 1),
                "edge": edge,
                "edge_pct": round(edge * 100, 1),
                "elapsed_min": r["elapsed_min"],
                "remaining_min": r["remaining_min"],
                "distance_target": r["distance_target"],
                "flip_prob": r["flip_prob"],
                "stay_prob": r["stay_prob"],
                "signal_status": r["signal_status"],
                "entry_status": r["entry_status"],
                "attractive_le_50": bool(ask <= 0.50 and edge > 0),
                "attractive_le_40": bool(ask <= 0.40 and edge > 0),
                "attractive_le_30": bool(ask <= 0.30 and edge > 0),
                "edge_10pt_plus": bool(edge >= 0.10),
                "edge_15pt_plus": bool(edge >= 0.15),
                "edge_20pt_plus": bool(edge >= 0.20),
            })

    return pd.DataFrame(rows)

def add_results(side_rows, results):
    out = side_rows.merge(results, on="ticker", how="left")
    out["final_side"] = out["final_side"].fillna("UNRESOLVED")
    out["eventual_winner_side"] = out.apply(
        lambda r: (
            "UNRESOLVED"
            if r["final_side"] == "UNRESOLVED"
            else ("YES" if r["side"] == r["final_side"] else "NO")
        ),
        axis=1
    )
    return out

def first_true(group, col):
    g = group[group[col]]
    if g.empty:
        return None
    return g.iloc[0]

def cheapest_true(group, col):
    g = group[group[col]]
    if g.empty:
        return None
    return g.loc[g["ask"].idxmin()]

def summarize(side_rows):
    summary_rows = []

    for (ticker, side), g in side_rows.groupby(["ticker","side"], sort=True):
        g = g.sort_values("timestamp_utc").reset_index(drop=True)

        first50 = first_true(g, "attractive_le_50")
        first40 = first_true(g, "attractive_le_40")
        first30 = first_true(g, "attractive_le_30")

        cheap50 = cheapest_true(g, "attractive_le_50")

        positive = g[g["edge"] > 0]
        best_edge = None if positive.empty else positive.loc[positive["edge"].idxmax()]

        final_side = g["final_side"].iloc[0]
        won = (
            "UNRESOLVED"
            if final_side == "UNRESOLVED"
            else ("YES" if side == final_side else "NO")
        )

        def val(row, col):
            return None if row is None else row[col]

        summary_rows.append({
            "ticker": ticker,
            "side": side,
            "final_side": final_side,
            "eventual_winner_side": won,

            "first_le50_ask": val(first50, "ask"),
            "first_le50_elapsed": val(first50, "elapsed_min"),
            "first_le50_remaining": val(first50, "remaining_min"),
            "first_le50_fair": val(first50, "fair"),
            "first_le50_edge": val(first50, "edge"),

            "first_le40_ask": val(first40, "ask"),
            "first_le40_elapsed": val(first40, "elapsed_min"),
            "first_le40_remaining": val(first40, "remaining_min"),
            "first_le40_fair": val(first40, "fair"),
            "first_le40_edge": val(first40, "edge"),

            "first_le30_ask": val(first30, "ask"),
            "first_le30_elapsed": val(first30, "elapsed_min"),
            "first_le30_remaining": val(first30, "remaining_min"),
            "first_le30_fair": val(first30, "fair"),
            "first_le30_edge": val(first30, "edge"),

            "cheapest_attractive_ask": val(cheap50, "ask"),
            "cheapest_attractive_elapsed": val(cheap50, "elapsed_min"),
            "cheapest_attractive_remaining": val(cheap50, "remaining_min"),
            "cheapest_attractive_fair": val(cheap50, "fair"),
            "cheapest_attractive_edge": val(cheap50, "edge"),

            "best_positive_edge": val(best_edge, "edge"),
            "best_positive_edge_ask": val(best_edge, "ask"),
            "best_positive_edge_fair": val(best_edge, "fair"),
            "best_positive_edge_elapsed": val(best_edge, "elapsed_min"),
            "best_positive_edge_remaining": val(best_edge, "remaining_min"),

            "saw_attractive_le50": bool(g["attractive_le_50"].any()),
            "saw_attractive_le40": bool(g["attractive_le_40"].any()),
            "saw_attractive_le30": bool(g["attractive_le_30"].any()),
        })

    return pd.DataFrame(summary_rows)

def print_report(side_rows, summary):
    print("\n=== KALSHI ATTRACTIVE ENTRY LIFECYCLE VALIDATOR ===")
    print("Tracks BOTH UP and DOWN throughout the full 15-minute contract.")
    print("Cheap eventual-winner opportunities are preserved even if direction flips later.")
    print("Signal-only: YES")
    print("Orders placed: NO")
    print("bot.py modified: NO")

    print(f"\nSnapshots analyzed: {len(side_rows)} side-snapshots")
    print(f"Contracts represented: {side_rows['ticker'].nunique()}")

    attr = side_rows[side_rows["attractive_le_50"]]
    print(f"Attractive <=50c side-snapshots: {len(attr)}")

    if not attr.empty:
        print("\n=== FIRST / CHEAPEST ATTRACTIVE OPPORTUNITIES BY CONTRACT + SIDE ===")
        cols = [
            "ticker","side","final_side","eventual_winner_side",
            "first_le50_ask","first_le50_remaining","first_le50_fair","first_le50_edge",
            "first_le30_ask","first_le30_remaining","first_le30_fair","first_le30_edge",
            "cheapest_attractive_ask","cheapest_attractive_remaining",
            "cheapest_attractive_fair","cheapest_attractive_edge"
        ]
        print(summary[cols].to_string(index=False))

    resolved = summary[summary["final_side"] != "UNRESOLVED"].copy()
    if resolved.empty:
        print("\nNo settled contracts yet. That is okay.")
        print("Once kalshi_contract_results.csv contains official results, rerun this file.")
    else:
        winners = resolved[resolved["eventual_winner_side"] == "YES"]

        print("\n=== DID THE EVENTUAL WINNER BECOME ATTRACTIVE? ===")
        for threshold, col in [
            ("<=50c","saw_attractive_le50"),
            ("<=40c","saw_attractive_le40"),
            ("<=30c","saw_attractive_le30"),
        ]:
            n = len(winners)
            hit = int(winners[col].sum()) if n else 0
            rate = hit / n if n else 0.0
            print(f"{threshold}: {hit}/{n} winner-sides had an attractive window ({rate:.1%})")

        winner_first50 = winners[winners["saw_attractive_le50"]]
        if not winner_first50.empty:
            print("\n=== EVENTUAL-WINNER <=50c WINDOWS ===")
            cols = [
                "ticker","side","first_le50_ask","first_le50_remaining",
                "first_le50_fair","first_le50_edge",
                "cheapest_attractive_ask","cheapest_attractive_remaining"
            ]
            print(winner_first50[cols].to_string(index=False))

def main():
    df = load_log()
    results = load_results()

    side_rows = build_side_rows(df)
    side_rows = add_results(side_rows, results)
    summary = summarize(side_rows)

    side_rows.to_csv(SNAPSHOT_OUT, index=False)
    summary.to_csv(SUMMARY_OUT, index=False)

    print_report(side_rows, summary)

    print(f"\nSaved snapshot report: {SNAPSHOT_OUT}")
    print(f"Saved lifecycle summary: {SUMMARY_OUT}")

if __name__ == "__main__":
    main()
