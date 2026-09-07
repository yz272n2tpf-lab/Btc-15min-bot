from pathlib import Path
from datetime import datetime, timezone
import json

MARKER = Path("kalshi_frozen_5m_guard_start_utc.txt")
SPEC = Path("kalshi_frozen_5m_guard_spec.json")

if MARKER.exists():
    print("=== FROZEN 5M GUARD ALREADY STARTED ===")
    print("Existing marker:", MARKER.read_text(encoding="utf-8").strip())
    print("Nothing changed.")
    raise SystemExit(0)

start = datetime.now(timezone.utc).isoformat()

spec = {
    "purpose": "Forward validation of earlier warning candidate",
    "checkpoint_minutes_remaining": 5.0,
    "signed_distance_warning_threshold_usd": 75.0,
    "cohort": "Layer A CLEAN qualifying calls",
    "truth_label": "Official Kalshi settlement only",
    "snapshot_method": "nearest snapshot to 5.0 minutes remaining using the same precursor-audit method",
    "research_only": True,
    "bot_py_changed": False,
    "scalp_logic_changed": False,
    "orders_enabled": False,
    "threshold_frozen": True
}

MARKER.write_text(start + "\n", encoding="utf-8")
SPEC.write_text(json.dumps(spec, indent=2) + "\n", encoding="utf-8")

print("=== FROZEN 5M GUARD FORWARD TEST STARTED ===")
print("Forward-test start UTC:", start)
print("FROZEN RULE: around 5 minutes remaining, WARN if original-call signed distance <= $75.")
print("Truth: official Kalshi settlement only.")
print("Cohort: Layer A CLEAN qualifying calls.")
print()
print("Original 3m frozen test files were NOT changed.")
print("No rule installed.")
print("No bot.py changes.")
print("No scalp changes.")
print("No orders.")
