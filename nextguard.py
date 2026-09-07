from pathlib import Path
from datetime import datetime, timezone
import subprocess, sys

M=Path("kalshi_guard_phase2_start_utc.txt")
if not M.exists():
    M.write_text(datetime.now(timezone.utc).isoformat()+"\n")
print("=== FRESH 5M/3M GUARD FORWARD RUN ===")
print("Start UTC:", M.read_text().strip())
print("5m <= $75: CAUTION only")
print("3m <= $75: HARD-GUARD candidate")
print("Rules frozen. No bot.py changes. No scalp changes. No orders.")
print("Press Ctrl+C ONCE when we are ready to stop.\n")

subprocess.run([sys.executable, "run_synced_kalshi_flow_collection.py"], check=False)
