from pathlib import Path
from datetime import datetime, timezone
import subprocess
import time
import signal
import sys
import os

MARKER = Path("layer_a_forward_validation_start_utc.txt")
MONITOR = Path("kalshi_live_fair_value_shadow_monitor.py")
FLOW = Path("btc_large_flow_shadow_collector.py")

print("=== LAYER A FORWARD VALIDATION LAUNCHER ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print()
print("FROZEN LAYER A RULES:")
print("EARLY WARNING = 4-minute deterioration >= $100")
print("LATE DANGER   = 6-minute deterioration >= $85")
print()
print("Rules will NOT be changed during this forward test.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

for p in [MONITOR, FLOW]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing {p}")

start = datetime.now(timezone.utc).isoformat()
MARKER.write_text(start + "\n")

print("Layer A forward-test start UTC:", start)
print("Marker saved to:", MARKER.name)
print()

monitor_cmd = f"while true; do python {MONITOR.name}; sleep 30; done"

print("Starting synchronized Kalshi + BTC collection...")
print("Press Ctrl+C ONCE to stop both.")
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
        m = monitor_proc.poll()
        f = flow_proc.poll()

        if m is not None:
            print(f"\nERROR: Kalshi monitor exited with code {m}")
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
                os.killpg(proc.pid, signal.SIGTERM)
            except Exception:
                try:
                    proc.kill()
                except Exception:
                    pass

print()
print("=== LAYER A FORWARD COLLECTION STOPPED ===")
print("Marker preserved:", MARKER.name)
print("Do NOT overwrite or edit that marker.")
