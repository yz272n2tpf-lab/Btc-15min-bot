from pathlib import Path
import time
import pandas as pd

LOG_PATH = Path("kalshi_live_fair_value_shadow_log.csv")

POLL_SECONDS = 2.0

# Entry tiers. These are SHADOW-SIGNAL labels only.
IDEAL_MAX_ASK = 0.50
DEEP_VALUE_MAX_ASK = 0.30

MIN_FAIR_WATCH = 0.60
MIN_FAIR_IDEAL = 0.70
MIN_FAIR_STRONG = 0.80
MIN_FAIR_LOCK = 0.90

MIN_EDGE_WATCH = 0.08
MIN_EDGE_IDEAL = 0.15
MIN_EDGE_STRONG = 0.20

REQUIRED = {
    "timestamp_utc","ticker","elapsed_min","remaining_min",
    "distance_target","flip_prob","stay_prob",
    "fair_up","fair_down","up_ask","down_ask"
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

    for c in [
        "elapsed_min","remaining_min","distance_target",
        "flip_prob","stay_prob","fair_up","fair_down",
        "up_ask","down_ask"
    ]:
        df[c] = pd.to_numeric(df[c], errors="coerce")

    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"], utc=True, errors="coerce")
    df = df.dropna(subset=["timestamp_utc","ticker"])
    return df.sort_values("timestamp_utc").reset_index(drop=True)

def classify(side, ask, fair, remaining, flip):
    if pd.isna(ask) or pd.isna(fair):
        return "NO DATA", ""

    edge = fair - ask

    # Lock status is about outcome confidence, not entry attractiveness.
    if fair >= MIN_FAIR_LOCK and flip <= 0.10:
        lock_text = "90%+ LOCK"
    elif fair >= MIN_FAIR_STRONG and flip <= 0.20:
        lock_text = "STRONG"
    elif fair >= MIN_FAIR_IDEAL:
        lock_text = "LEAN"
    else:
        lock_text = "RAW"

    # Entry status is separate from direction confidence.
    if ask <= DEEP_VALUE_MAX_ASK and fair >= MIN_FAIR_IDEAL and edge >= MIN_EDGE_IDEAL:
        entry = "DEEP VALUE <=30c"
    elif ask <= IDEAL_MAX_ASK and fair >= MIN_FAIR_STRONG and edge >= MIN_EDGE_STRONG:
        entry = "IDEAL <=50c / STRONG EDGE"
    elif ask <= IDEAL_MAX_ASK and fair >= MIN_FAIR_IDEAL and edge >= MIN_EDGE_IDEAL:
        entry = "IDEAL <=50c"
    elif ask <= IDEAL_MAX_ASK and fair >= MIN_FAIR_WATCH and edge >= MIN_EDGE_WATCH:
        entry = "VALUE WATCH <=50c"
    elif edge > 0:
        entry = "SMALL EDGE"
    else:
        entry = "NO VALUE"

    # Very early contract caution: cheap can be attractive, but flip risk can still be high.
    caution = ""
    if remaining >= 10 and flip >= 0.35 and entry.startswith(("DEEP","IDEAL","VALUE")):
        caution = "HIGH EARLY FLIP RISK"
    elif remaining >= 7 and flip >= 0.25 and entry.startswith(("DEEP","IDEAL","VALUE")):
        caution = "MODERATE FLIP RISK"
    elif remaining <= 5 and fair >= 0.90 and flip <= 0.10:
        caution = "LATE LOCK / PRICE MAY BE EXPENSIVE"

    return f"{lock_text} | {entry}", caution

def side_line(side, ask, fair, remaining, flip):
    edge = fair - ask
    status, caution = classify(side, ask, fair, remaining, flip)

    text = (
        f"{side:<4} ASK {ask:>5.2f} ({ask*100:>5.1f}c) | "
        f"FAIR {fair*100:>5.1f}% | "
        f"EDGE {edge*100:>+6.1f}pt | "
        f"FLIP {flip*100:>5.1f}% | "
        f"{status}"
    )
    if caution:
        text += f" | {caution}"
    return text

def process_row(r):
    ticker = str(r["ticker"])
    remaining = float(r["remaining_min"])
    elapsed = float(r["elapsed_min"])
    flip = float(r["flip_prob"])

    print("\n" + "=" * 92)
    print(f"CONTRACT: {ticker}")
    print(f"TIME LEFT: {remaining:.2f} min | ELAPSED: {elapsed:.2f} min | DIST: ${float(r['distance_target']):+.2f}")
    print("-" * 92)

    up_ask = float(r["up_ask"])
    down_ask = float(r["down_ask"])
    fair_up = float(r["fair_up"])
    fair_down = float(r["fair_down"])

    print(side_line("UP", up_ask, fair_up, remaining, flip))
    print(side_line("DOWN", down_ask, fair_down, remaining, flip))

    # Pick the best positive edge at THIS exact live snapshot.
    choices = [
        ("UP", up_ask, fair_up, fair_up - up_ask),
        ("DOWN", down_ask, fair_down, fair_down - down_ask),
    ]
    choices = [x for x in choices if x[3] > 0]
    if choices:
        best = max(choices, key=lambda x: x[3])
        side, ask, fair, edge = best
        status, caution = classify(side, ask, fair, remaining, flip)

        print("-" * 92)
        print(
            f"BEST LIVE VALUE: {side} @ {ask*100:.1f}c | "
            f"fair {fair*100:.1f}% | edge {edge*100:+.1f}pt"
        )
        print(f"DECISION: {status}")
        if caution:
            print(f"RISK NOTE: {caution}")

        # Explicitly surface the exact type of entry the user cares about.
        if ask <= 0.30 and fair >= 0.70 and edge >= 0.15:
            print(">>> DEEP-VALUE WINDOW DETECTED: <=30c WITH MATERIAL FINAL-OUTCOME EDGE")
        elif ask <= 0.50 and fair >= 0.70 and edge >= 0.15:
            print(">>> ATTRACTIVE BUY-IN WINDOW DETECTED: <=50c WITH MATERIAL EDGE")
    else:
        print("-" * 92)
        print("BEST LIVE VALUE: NONE")
        print("DECISION: WAIT / NO POSITIVE MODEL EDGE")

def main():
    print("=== KALSHI LIVE ATTRACTIVE-ENTRY DECISION LAYER ===")
    print("Reads the existing live shadow log only.")
    print("Evaluates BOTH UP and DOWN on every new snapshot.")
    print("Signal-only: YES")
    print("Orders placed: NO")
    print("bot.py modified: NO")
    print(f"Refresh: every {POLL_SECONDS:.0f} seconds")
    print("Press Ctrl+C to stop.\n")

    last_seen = None

    try:
        while True:
            try:
                df = load_log()

                if df.empty:
                    time.sleep(POLL_SECONDS)
                    continue

                latest = df.iloc[-1]
                stamp = latest["timestamp_utc"]

                if last_seen is None or stamp > last_seen:
                    process_row(latest)
                    last_seen = stamp

            except Exception as e:
                print(f"\nMonitor warning: {e}")

            time.sleep(POLL_SECONDS)

    except KeyboardInterrupt:
        print("\nTracker stopped by user.")

if __name__ == "__main__":
    main()
