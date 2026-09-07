from pathlib import Path
import shutil
import subprocess
import sys

BOT = Path("bot.py")
BACKUP = Path("bot_before_final_outcome_separation.py")

OLD_DIRECTION = '_final_15m_direction = "UP" if bool(current_prediction) else "DOWN"'
NEW_DIRECTION = (
    '_model_15m_direction = "UP" if bool(current_prediction) else "DOWN"\n\n'
    '# Final-outcome direction must be Kalshi-target-aware.\n'
    'if _v3_brti_direction in ("UP", "DOWN"):\n'
    '    _final_15m_direction = _v3_brti_direction\n'
    'else:\n'
    '    _final_15m_direction = _model_15m_direction\n'
)

OLD_READY = (
    '    _final_15m_ready = (\n'
    '        _strict_model_ready\n'
    '        and bool(_v3_brti_gate_ready)\n'
    '    )\n'
)

NEW_READY = (
    '    # Entry readiness remains strict.\n'
    '    _final_15m_ready = (\n'
    '        _strict_model_ready\n'
    '        and bool(_v3_brti_gate_ready)\n'
    '        and (_model_15m_direction == _final_15m_direction)\n'
    '    )\n'
)

OLD_OUTPUT = (
    'print("\\n--- STRICT 15-MIN + V3 FINAL GATE ---")\n'
    'print("Direction:", _final_15m_direction)\n'
    'print("Model confidence:", f"{float(current_confidence):.1%}")\n'
)

NEW_OUTPUT = (
    'print("\\n--- STRICT 15-MIN + V3 FINAL GATE ---")\n'
    'print("EXPECTED FINAL OUTCOME:", _final_15m_direction)\n'
    'print("MODEL LEAN:", _model_15m_direction)\n'
    'print(\n'
    '    "MODEL CONFIRMS FINAL OUTCOME:",\n'
    '    "YES" if _model_15m_direction == _final_15m_direction else "NO",\n'
    ')\n'
    'print("Model confidence:", f"{float(current_confidence):.1%}")\n'
)

OLD_FINAL = (
    'if _final_15m_ready:\n'
    '    print("FINAL 15-MIN STATUS: READY")\n'
    '    print("FINAL 15-MIN DIRECTION:", _final_15m_direction)\n'
    'else:\n'
    '    print("FINAL 15-MIN STATUS: WAIT")\n'
    '    print("CURRENT LEAN:", _final_15m_direction)\n'
)

NEW_FINAL = (
    'if _final_15m_ready:\n'
    '    print("ENTRY STATUS: READY")\n'
    '    print("ENTRY SIDE:", _final_15m_direction)\n'
    'else:\n'
    '    print("ENTRY STATUS: WAIT")\n'
    '\n'
    'print("EXPECTED FINAL OUTCOME:", _final_15m_direction)\n'
    'print("MODEL LEAN:", _model_15m_direction)\n'
)

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found.")

text = BOT.read_text()

missing = []
for label, needle in [
    ("direction block", OLD_DIRECTION),
    ("ready block", OLD_READY),
    ("output header", OLD_OUTPUT),
    ("final status block", OLD_FINAL),
]:
    if needle not in text:
        missing.append(label)

if missing:
    raise SystemExit(
        "ERROR: exact patch anchors not found: "
        + ", ".join(missing)
        + ". No changes made."
    )

shutil.copy2(BOT, BACKUP)

updated = text
updated = updated.replace(OLD_DIRECTION, NEW_DIRECTION, 1)
updated = updated.replace(OLD_READY, NEW_READY, 1)
updated = updated.replace(OLD_OUTPUT, NEW_OUTPUT, 1)
updated = updated.replace(OLD_FINAL, NEW_FINAL, 1)

BOT.write_text(updated)

result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(BOT)],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    shutil.copy2(BACKUP, BOT)
    print("=== FINAL OUTCOME SEPARATION PATCH FAILED ===")
    print(result.stderr)
    print("Automatic rollback completed.")
    print("bot.py restored: YES")
    raise SystemExit(1)

print("=== FINAL OUTCOME / ENTRY STATUS SEPARATION COMPLETE ===")
print("Backup created:", BACKUP.name)
print("Syntax check: PASSED")
print("Expected final outcome source: KALSHI/BRTI TARGET SIDE")
print("Model role: CONFIRMATION LAYER")
print("Entry readiness: STRICT MODEL + BRTI AGREEMENT")
print("Scalp logic changed: NO")
print("Order-placement code added: NO")
print("Signal-only behavior preserved: YES")
print()
print("NEXT: run bot.py and inspect EXPECTED FINAL OUTCOME + ENTRY STATUS.")
