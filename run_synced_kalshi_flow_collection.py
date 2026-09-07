from pathlib import Path
import subprocess
import time
import signal
import sys

MONITOR = Path("kalshi_live_fair_value_shadow_monitor.py")
FLOW = Path("btc_large_flow_shadow_collector.py")

print("=== SYNCHRONIZED KALSHI + BTC FLOW COLLECTION ===")
print("Purpose: collect more evidence for FINAL 15-minute UP/DOWN validation.")
print("Leading research question:")
print("Does the latest 30-second BTC move opposing the first >=80% supported call warn of a miss?")
print()
print("Signal-only: YES")
print("Orders placed: NO")
print("bot.py modified: NO")
print("Scalp logic changed: NO")
print()

if not MONITOR.exists():
    raise SystemExit(f"ERROR: missing {MONITOR}")
if not FLOW.exists():
    raise SystemExit(f"ERROR: missing {FLOW}")

monitor_cmd = (
    f"while true; do "
    f"python {MONITOR.name}; "
    f"sleep 30; "
    f"done"
)

print("Starting both synchronized processes...")
print("Press Ctrl+C ONCE to stop both cleanly.")
print()

monitor_proc = subprocess.Popen(
    ["bash", "-lc", monitor_cmd],
    start_new_session=True,
)

flow_proc = subprocess.Popen(
    [sys.executable, FLOW.name],
    start_new_session=True,
)

try:
    while True:
        # If either child unexpectedly exits, stop the other too.
        m = monitor_proc.poll()
        f = flow_proc.poll()

        if m is not None:
            print(f"\nERROR: Kalshi monitor process exited with code {m}")
            break

        if f is not None:
            print(f"\nERROR: BTC flow collector exited with code {f}")
            break

        time.sleep(2)

except KeyboardInterrupt:
    print("\nStopping both synchronized processes...")

finally:
    for proc in [monitor_proc, flow_proc]:
        if proc.poll() is None:
            try:
                # Terminate the full child process group.
                import os
                os.killpg(proc.pid, signal.SIGINT)
            except Exception:
                try:
                    proc.terminate()
                except Exception:
                    pass

    deadline = time.time() + 8
    while time.time() < deadline:
        if monitor_proc.poll() is not None and flow_proc.poll() is not None:
            break
        time.sleep(0.25)

    for proc in [monitor_proc, flow_proc]:
        if proc.poll() is None:
            try:
                import os
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

print()
print("=== COLLECTION STOPPED ===")
print("Both synchronized processes have been stopped.")
print("Kalshi snapshots remain in kalshi_live_fair_value_shadow_log.csv")
print("BTC flow remains in btc_large_flow_shadow_log.csv")
print()
print("No bot.py changes were made.")
print("No orders were placed.")
