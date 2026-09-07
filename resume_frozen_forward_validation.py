from pathlib import Path
import subprocess
import time
import signal
import sys
import os

MARKER = Path("frozen_forward_validation_start_utc.txt")
MONITOR = Path("kalshi_live_fair_value_shadow_monitor.py")
FLOW = Path("btc_large_flow_shadow_collector.py")

print("=== RESUME FROZEN FORWARD VALIDATION ===")
print()

if not MARKER.exists():
    raise SystemExit("ERROR: frozen_forward_validation_start_utc.txt is missing. Do NOT create a new start time.")

start = MARKER.read_text().strip()

print("ORIGINAL frozen start UTC:", start)
print("Marker preserved: YES")
print()
print("FROZEN TIERS:")
print("SAFE       = 3-minute deterioration < $100")
print("WEAKENING  = $100 to $149.99")
print("DANGER     = >= $150")
print()
print("Thresholds changed: NO")
print("Scalp logic changed: NO")
print("bot.py changed: NO")
print("Orders placed: NO")
print()

for p in [MONITOR, FLOW]:
    if not p.exists():
        raise SystemExit(f"ERROR: missing {p}")

monitor_cmd = f"while true; do python {MONITOR.name}; sleep 30; done"

print("Resuming synchronized Kalshi + BTC collection...")
print("Press Ctrl+C ONCE to stop both.")
print()

monitor_proc = subprocess.Popen(["bash", "-lc", monitor_cmd], start_new_session=True)
flow_proc = subprocess.Popen([sys.executable, FLOW.name], start_new_session=True)

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
print("=== FORWARD COLLECTION STOPPED ===")
print("Original marker preserved:", MARKER.name)
