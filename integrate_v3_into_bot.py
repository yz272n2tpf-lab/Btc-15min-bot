from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

BOT = Path("bot.py")
PRE_V3_BACKUP = Path("bot_pre_v3_integration_backup.py")
AUTO_BACKUP = Path("bot_before_v3_auto_integration.py")
CALIBRATION_CSV = Path("brti_calibration_results.csv")

START_MARKER = "# === V3 BRTI/KALSHI SAFETY GATE START ==="
END_MARKER = "# === V3 BRTI/KALSHI SAFETY GATE END ==="

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found.")

if not PRE_V3_BACKUP.exists():
    raise SystemExit(
        "ERROR: bot_pre_v3_integration_backup.py not found. "
        "Run inspect_bot_for_v3_integration.py first."
    )

if not CALIBRATION_CSV.exists():
    raise SystemExit(
        "ERROR: brti_calibration_results.csv not found."
    )

original = BOT.read_text()

if START_MARKER in original:
    raise SystemExit(
        "STOP: V3 integration marker already exists in bot.py. "
        "No changes made."
    )

shutil.copy2(BOT, AUTO_BACKUP)

anchor = 'print("Current 15-minute confidence:",\n        round(current_confidence, 3))\n'

if anchor not in original:
    anchor = 'print("Current 15-minute confidence:",\n          round(current_confidence, 3))\n'

if anchor not in original:
    raise SystemExit(
        "ERROR: Exact live-confidence anchor not found. "
        "bot.py was NOT changed."
    )

v3_block = r'''

# === V3 BRTI/KALSHI SAFETY GATE START ===
# Validated target-safety layer.
# Signal-only. This block NEVER places orders.

V3_BRTI_BUFFER_DOLLARS = 11.0
_v3_brti_gate_ready = False
_v3_brti_agrees = False
_v3_inside_wait_zone = True
_v3_adjusted_gap = None
_v3_brti_direction = "UNKNOWN"
_v3_target = None
_v3_status = "WAIT"

try:
    _v3_cal = pd.read_csv("brti_calibration_results.csv")

    _v3_errors = pd.concat(
        [
            _v3_cal["target_cb_hl2"] - _v3_cal["target_brti"],
            _v3_cal["final_cb_hl2"] - _v3_cal["final_brti"],
        ],
        ignore_index=True,
    )

    _v3_brti_bias = float(_v3_errors.mean())

    _v3_markets = get_kalshi_btc_markets()
    _v3_now = datetime.now(timezone.utc)
    _v3_active = []

    for _v3_market in _v3_markets:
        _v3_ticker = str(_v3_market.get("ticker", ""))

        if not _v3_ticker.startswith("KXBTC15M"):
            continue

        _v3_open_raw = _v3_market.get("open_time")
        _v3_close_raw = _v3_market.get("close_time")

        if not _v3_open_raw or not _v3_close_raw:
            continue

        try:
            _v3_open = datetime.fromisoformat(
                str(_v3_open_raw).replace("Z", "+00:00")
            )
            _v3_close = datetime.fromisoformat(
                str(_v3_close_raw).replace("Z", "+00:00")
            )
        except Exception:
            continue

        if _v3_open <= _v3_now < _v3_close:
            _v3_active.append((_v3_close, _v3_market))

    if _v3_active:
        _v3_active.sort(key=lambda x: x[0])
        _v3_market = _v3_active[0][1]

        try:
            _v3_target = float(_v3_market.get("floor_strike"))
        except (TypeError, ValueError):
            _v3_target = None

        _v3_latest_row = data_1m.iloc[-1]
        _v3_coinbase_hl2 = (
            float(_v3_latest_row["High"])
            + float(_v3_latest_row["Low"])
        ) / 2.0

        _v3_estimated_brti = _v3_coinbase_hl2 - _v3_brti_bias

        if _v3_target is not None:
            _v3_adjusted_gap = _v3_estimated_brti - _v3_target
            _v3_inside_wait_zone = (
                abs(_v3_adjusted_gap) <= V3_BRTI_BUFFER_DOLLARS
            )

            if _v3_adjusted_gap > 0:
                _v3_brti_direction = "UP"
            elif _v3_adjusted_gap < 0:
                _v3_brti_direction = "DOWN"
            else:
                _v3_brti_direction = "FLAT"

            _v3_model_direction = (
                "UP" if bool(current_prediction) else "DOWN"
            )

            _v3_brti_agrees = (
                _v3_brti_direction == _v3_model_direction
            )

            _v3_brti_gate_ready = (
                (not _v3_inside_wait_zone)
                and _v3_brti_agrees
            )

    if _v3_brti_gate_ready:
        _v3_status = "BRTI GATE READY"
    else:
        _v3_status = "WAIT"

except Exception as _v3_error:
    _v3_status = "WAIT"
    _v3_brti_gate_ready = False
    _v3_error_text = str(_v3_error)

print("\n--- V3 BRTI / KALSHI SAFETY GATE ---")
print("Validated BRTI buffer: +/-$11.00")
print(
    "Kalshi target:",
    f"${_v3_target:,.2f}" if _v3_target is not None else "UNKNOWN",
)
print(
    "Adjusted BRTI gap:",
    f"${_v3_adjusted_gap:+.2f}"
    if _v3_adjusted_gap is not None
    else "UNKNOWN",
)
print("BRTI direction:", _v3_brti_direction)
print(
    "Inside +/-$11 WAIT zone:",
    "YES" if _v3_inside_wait_zone else "NO",
)
print(
    "BRTI agrees with 15-min model:",
    "YES" if _v3_brti_agrees else "NO",
)
print(
    "BRTI gate ready:",
    "YES" if _v3_brti_gate_ready else "NO",
)
print("V3 safety status:", _v3_status)

if "_v3_error_text" in globals():
    print("V3 safety note:", _v3_error_text)

# === V3 BRTI/KALSHI SAFETY GATE END ===
'''

modified = original.replace(anchor, anchor + v3_block, 1)

if modified == original:
    raise SystemExit("ERROR: Integration produced no change.")

BOT.write_text(modified)

result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(BOT)],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    shutil.copy2(AUTO_BACKUP, BOT)

    print("=== V3 INTEGRATION FAILED ===")
    print("Syntax error detected.")
    print(result.stderr)
    print("Automatic rollback completed.")
    print("bot.py restored: YES")
    raise SystemExit(1)

new_lines = BOT.read_text().splitlines()

start_line = None
end_line = None

for i, line in enumerate(new_lines, start=1):
    if START_MARKER in line:
        start_line = i
    if END_MARKER in line:
        end_line = i

print("=== V3 AUTO-INTEGRATION COMPLETE ===")
print("Timestamp:", datetime.now().isoformat(timespec="seconds"))
print("Pre-V3 backup exists:", PRE_V3_BACKUP.exists())
print("Automatic backup created:", AUTO_BACKUP.name)
print("Syntax check: PASSED")
print("V3 start line:", start_line)
print("V3 end line:", end_line)
print("Scalp logic changed: NO")
print("Order-placement code added: NO")
print("Signal-only behavior preserved: YES")
print()
print("NEXT: run bot.py and inspect the V3 gate output.")
