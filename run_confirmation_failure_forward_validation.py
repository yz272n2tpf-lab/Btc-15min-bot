from pathlib import Path
from datetime import datetime, timezone
import subprocess
import sys

MARKER = Path("confirmation_failure_forward_start_utc.txt")

print("=== CONFIRMATION-FAILURE FORWARD VALIDATION LAUNCHER ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print()
print("FROZEN LAYER A:")
print("  EARLY WARNING = max deterioration within 4m >= $100")
print("  LATE DANGER   = max deterioration within 6m >= $85")
print()
print("FROZEN CONFIRMATION-FAILURE CANDIDATE:")
print("  checkpoint = 4 minutes after qualifying call")
print("  distance gain < +$10")
print("  AND fair-value gain < 0")
print("  warning only; does NOT reverse call")
print()
print("Rules will NOT be changed during this forward test.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if MARKER.exists():
    print("Marker already exists:", MARKER)
    print("Preserving original forward-test start time.")
    print("Marker value:", MARKER.read_text().strip())
else:
    now = datetime.now(timezone.utc).isoformat()
    MARKER.write_text(now)
    print("Forward-test start UTC:", now)
    print("Marker saved to:", MARKER)

print()
print("Starting synchronized Kalshi + BTC collection...")
print("Press Ctrl+C ONCE to stop both.")
print()

try:
    subprocess.run([sys.executable, "run_synced_kalshi_flow_collection.py"], check=False)
except KeyboardInterrupt:
    print("\nStopped by user.")
