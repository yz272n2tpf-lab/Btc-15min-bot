from pathlib import Path
from datetime import datetime, timezone
import json

MARKER = Path("kalshi_frozen_3m_guard_start_utc.txt")
SPEC = Path("kalshi_frozen_3m_guard_spec.json")

print("=== KALSHI FROZEN 3-MINUTE GUARD FORWARD VALIDATION ===")
print("Purpose: freeze the newly discovered 3-minute safety rule BEFORE any new forward contracts.")
print()
print("Research only.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders placed.")
print()

# Frozen rule discovered from the completed historical audit.
spec = {
    "rule_name": "FROZEN_3M_SIGNED_DISTANCE_GUARD",
    "version": 1,
    "evaluation_point": "approximately 3 minutes remaining",
    "signed_distance_threshold_dollars": 75.0,
    "warning_condition": "original-call signed distance <= 75.0",
    "action": "research warning/downgrade only",
    "truth_label": "official Kalshi settlement only",
    "notes": [
        "Do not tune this threshold using forward results.",
        "Do not install as a live rule until forward validation is complete.",
        "This is a late safety/reversal layer, not the primary early final-call trigger."
    ]
}

now = datetime.now(timezone.utc).isoformat()

# Do not silently overwrite an existing forward marker.
if MARKER.exists():
    existing = MARKER.read_text().strip()
    print(f"Existing frozen marker found: {existing}")
    print("Marker NOT changed.")
else:
    MARKER.write_text(now + "\n")
    print(f"Frozen forward-test start UTC: {now}")
    print(f"Saved marker: {MARKER}")

SPEC.write_text(json.dumps(spec, indent=2) + "\n")
print(f"Saved frozen spec: {SPEC}")
print()
print("FROZEN RULE:")
print("  At approximately 3 minutes remaining:")
print("  WARN if original-call signed distance <= $75.")
print()
print("IMPORTANT: threshold is now frozen for forward testing.")
print("No rule installed. No bot.py changes.")
