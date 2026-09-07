from pathlib import Path
from datetime import datetime, timezone
import subprocess
import sys

MARKER = Path("layer_b_forward_validation_start_utc.txt")

print("=== LAYER B FORWARD VALIDATION LAUNCHER ===")
print("Focus: FINAL 15-minute UP/DOWN only.")
print()
print("FROZEN LAYER A:")
print("  EARLY WARNING = max deterioration within 4m >= $100")
print("  LATE DANGER   = max deterioration within 6m >= $85")
print()
print("FROZEN LAYER B RESEARCH:")
print("  Use FIRST real post-call snapshot only if <= 60 seconds after call")
print("  SHOCK_DISTANCE = deterioration >= $30")
print("  SHOCK_FAIR     = original-side fair drop >= 5 percentage points")
print("  SHOCK_EITHER   = either condition")
print()
print("Rules will NOT be changed during this forward test.")
print("bot.py changed: NO")
print("Scalp logic changed: NO")
print("Orders placed: NO")
print()

if MARKER.exists():
    print(f"Marker already exists: {MARKER}")
    print("Preserving original forward-test start time.")
    print("Marker value:", MARKER.read_text().strip())
else:
    now = datetime.now(timezone.utc).isoformat()
    MARKER.write_text(now)
    print("Layer B forward-test start UTC:", now)
    print("Marker saved to:", MARKER)

print()
print("Starting synchronized Kalshi + BTC collection...")
print("Press Ctrl+C ONCE to stop both.")
print()

cmd = [sys.executable, "run_synced_kalshi_flow_collection.py"]

try:
    subprocess.run(cmd, check=False)
except KeyboardInterrupt:
    print("\nStopped by user.")
