from pathlib import Path
import subprocess
import sys
import time
import pandas as pd

MONITOR = Path("kalshi_live_fair_value_shadow_monitor.py")
LOG = Path("kalshi_live_fair_value_shadow_log.csv")

INTERVAL_SECONDS = 30

print("=== KALSHI CONTINUOUS LIVE EDGE TRACKER ===")
print("Purpose: continuously track fair probability vs live Kalshi price")
print("throughout each active BTC 15-minute contract.")
print("Signal-only: YES")
print("Orders placed: NO")
print("bot.py modified: NO")
print(f"Refresh interval: {INTERVAL_SECONDS} seconds")
print("Press Ctrl+C to stop.")
print()

if not MONITOR.exists():
    raise SystemExit(
        "ERROR: kalshi_live_fair_value_shadow_monitor.py not found "
        "in the current project folder."
    )

last_ticker = None
last_status = None
last_entry = None

def pct(x):
    try:
        return f"{float(x):.1%}"
    except Exception:
        return "N/A"

def money(x):
    try:
        return f"{float(x):.2f}"
    except Exception:
        return "N/A"

while True:
    cycle_start = time.time()

    try:
        result = subprocess.run(
            [sys.executable, str(MONITOR)],
            capture_output=True,
            text=True,
            timeout=90,
        )

        if result.returncode != 0:
            print()
            print("MONITOR ERROR")
            print(result.stderr.strip() or result.stdout.strip())
        elif not LOG.exists():
            print("Waiting for first live shadow log row...")
        else:
            df = pd.read_csv(LOG)

            if df.empty:
                print("Waiting for first live shadow log row...")
            else:
                r = df.iloc[-1]

                ticker = str(r.get("ticker", "UNKNOWN"))
                preferred_side = str(r.get("preferred_side", "UNKNOWN"))
                fair = r.get("fair_preferred")
                ask = r.get("preferred_ask")
                edge = r.get("edge")
                remaining = r.get("remaining_min")
                elapsed = r.get("elapsed_min")
                distance = r.get("distance_target")
                signal_status = str(r.get("signal_status", "UNKNOWN"))
                entry_status = str(r.get("entry_status", "UNKNOWN"))
                flip_prob = r.get("flip_prob")

                if ticker != last_ticker:
                    print()
                    print("=" * 72)
                    print("NEW CONTRACT:", ticker)
                    print("=" * 72)
                    last_ticker = ticker
                    last_status = None
                    last_entry = None

                try:
                    remaining_text = f"{float(remaining):5.2f}m"
                except Exception:
                    remaining_text = " N/A "

                try:
                    elapsed_text = f"{float(elapsed):5.2f}m"
                except Exception:
                    elapsed_text = " N/A "

                try:
                    distance_text = f"${float(distance):+,.2f}"
                except Exception:
                    distance_text = "N/A"

                line = (
                    f"LEFT {remaining_text} | "
                    f"ELAPSED {elapsed_text} | "
                    f"{preferred_side:4s} FAIR {pct(fair):>6s} | "
                    f"ASK {money(ask):>4s} | "
                    f"EDGE {pct(edge):>7s} | "
                    f"FLIP {pct(flip_prob):>6s} | "
                    f"DIST {distance_text}"
                )

                print(line)
                print(
                    f"  SIGNAL: {signal_status} | "
                    f"ENTRY: {entry_status}"
                )

                # Highlight meaningful changes without changing any trading logic.
                if signal_status != last_status:
                    print("  >>> SIGNAL STATUS CHANGED:", signal_status)
                    last_status = signal_status

                if entry_status != last_entry:
                    print("  >>> ENTRY STATUS CHANGED:", entry_status)
                    last_entry = entry_status

                if (
                    "ATTRACTIVE" in entry_status
                    or "IDEAL" in entry_status
                ):
                    print(
                        "  >>> ATTRACTIVE-ENTRY WINDOW DETECTED "
                        "(shadow signal only)"
                    )

                if (
                    "LOCK" in signal_status
                    and "NO VALUE" in entry_status
                ):
                    print(
                        "  >>> DIRECTION MAY BE LOCKED, "
                        "BUT ENTRY PRICE IS NOT ATTRACTIVE"
                    )

    except KeyboardInterrupt:
        print()
        print("Tracker stopped by user.")
        break

    except Exception as e:
        print("TRACKER ERROR:", repr(e))

    elapsed_cycle = time.time() - cycle_start
    sleep_for = max(1.0, INTERVAL_SECONDS - elapsed_cycle)

    try:
        time.sleep(sleep_for)
    except KeyboardInterrupt:
        print()
        print("Tracker stopped by user.")
        break
