from pathlib import Path
import subprocess
import time
import signal
import sys
import os

MARKER = Path("layer_a_forward_validation_start_utc.txt")
MONITOR = Path("kalshi_live_fair_value_shadow_monitor.py")
FLOW = Path("btc_large_flow_shadow_collector.py")

print("=== RESUME LAYER A FORWARD VALIDATION ===")
print()

if not MARKER.exists():
    raise SystemExit("ERROR: layer_a_forward_validation_start_utc.txt is missing. Do NOT create a new Layer A start time.")

start = MARKER.read_text().strip()

print("ORIGINAL Layer A start UTC:", start)
print("Marker preserved: YES")
print()
print("FROZEN LAYER A RULES:")
print("EARLY WARNING = 4-minute deterioration >= $100")
print("LATE DANGER   = 6-minute deterioration >= $85")
print()
print("Rules changed: NO")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
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
        if monitor_proc.poll() is not None:
            print(f"\nERROR: Kalshi monitor exited with code {monitor_proc.returncode}")
            break
        if flow_proc.poll() is not None:
            print(f"\nERROR: BTC flow collector exited with code {flow_proc.returncode}")
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
print("Original marker preserved:", MARKER.name)
