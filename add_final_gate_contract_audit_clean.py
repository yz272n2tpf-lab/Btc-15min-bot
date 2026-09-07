from pathlib import Path
import shutil
import subprocess
import sys

BOT = Path("bot.py")
BACKUP = Path("bot_before_final_gate_contract_audit.py")

ANCHOR = 'print("\\n--- STRICT 15-MIN + V3 FINAL GATE ---")'
AUDIT = '\nprint("\\n--- FINAL GATE CONTRACT AUDIT ---")\n\ntry:\n    _audit_market = _strict_active_market\n\n    _audit_ticker = str(_audit_market.get("ticker", "UNKNOWN"))\n    _audit_open = _audit_market.get("open_time")\n    _audit_close = _audit_market.get("close_time")\n\n    try:\n        _audit_target = float(_audit_market.get("floor_strike"))\n    except (TypeError, ValueError):\n        _audit_target = None\n\n    _audit_up_bid = _audit_market.get("yes_bid_dollars")\n    _audit_up_ask = _audit_market.get("yes_ask_dollars")\n    _audit_down_bid = _audit_market.get("no_bid_dollars")\n    _audit_down_ask = _audit_market.get("no_ask_dollars")\n\n    print("KALSHI TICKER:", _audit_ticker)\n    print("KALSHI OPEN:", _audit_open)\n    print("KALSHI CLOSE:", _audit_close)\n    print(\n        "KALSHI TARGET:",\n        f"${_audit_target:,.2f}" if _audit_target is not None else "UNKNOWN",\n    )\n    print("UP BID/ASK:", _audit_up_bid, "/", _audit_up_ask)\n    print("DOWN BID/ASK:", _audit_down_bid, "/", _audit_down_ask)\n    print(\n        "BRTI-ADJUSTED GAP:",\n        f"${_v3_adjusted_gap:+.2f}"\n        if _v3_adjusted_gap is not None\n        else "UNKNOWN",\n    )\n    print("BRTI TARGET SIDE:", _v3_brti_direction)\n    print("MODEL SIDE:", _model_15m_direction)\n    print("EXPECTED FINAL SOURCE: BRTI/KALSHI TARGET SIDE")\n    print("EXPECTED FINAL OUTCOME:", _final_15m_direction)\n\nexcept Exception as _audit_error:\n    print("CONTRACT AUDIT ERROR:", str(_audit_error))\n    print("EXPECTED FINAL OUTCOME remains fail-closed.")\n'

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found.")

text = BOT.read_text()

if "FINAL GATE CONTRACT AUDIT" in text:
    raise SystemExit("STOP: contract audit already installed. No changes made.")

if ANCHOR not in text:
    raise SystemExit("ERROR: strict final-gate anchor not found. No changes made.")

shutil.copy2(BOT, BACKUP)

updated = text.replace(ANCHOR, AUDIT + "\n" + ANCHOR, 1)
BOT.write_text(updated)

result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(BOT)],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    shutil.copy2(BACKUP, BOT)
    print("=== FINAL GATE CONTRACT AUDIT INSTALL FAILED ===")
    print(result.stderr)
    print("Automatic rollback completed.")
    print("bot.py restored: YES")
    raise SystemExit(1)

print("=== FINAL GATE CONTRACT AUDIT INSTALLED ===")
print("Backup created:", BACKUP.name)
print("Syntax check: PASSED")
print("Decision logic changed: NO")
print("Scalp logic changed: NO")
print("Order-placement code added: NO")
print("Signal-only behavior preserved: YES")
print()
print("NEXT: run bot.py and send FINAL GATE CONTRACT AUDIT + STRICT FINAL GATE.")
