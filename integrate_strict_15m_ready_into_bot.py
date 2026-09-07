from pathlib import Path
import shutil
import subprocess
import sys
from datetime import datetime

BOT = Path("bot.py")
BACKUP = Path("bot_before_strict_15m_ready_integration.py")

START_MARKER = "# === STRICT 15M + V3 COMBINED READY START ==="
END_MARKER = "# === STRICT 15M + V3 COMBINED READY END ==="
V3_END = "# === V3 BRTI/KALSHI SAFETY GATE END ==="

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found.")

original = BOT.read_text()

if START_MARKER in original:
    raise SystemExit(
        "STOP: strict combined-ready block already exists. No changes made."
    )

if V3_END not in original:
    raise SystemExit(
        "ERROR: V3 BRTI/Kalshi block not found. No changes made."
    )

shutil.copy2(BOT, BACKUP)

strict_block = r'''

# === STRICT 15M + V3 COMBINED READY START ===
# Final 15-minute signal gate.
# Signal-only: NEVER places orders.

_strict_model_ready = False
_strict_elapsed_minute = None
_strict_distance = None
_strict_agreement = 0
_strict_conf_change = None
_final_15m_ready = False
_final_15m_direction = "UP" if bool(current_prediction) else "DOWN"

try:
    _strict_now_ts = live_valid.index[-1]

    if getattr(_strict_now_ts, "tzinfo", None) is None:
        _strict_now_ts = pd.Timestamp(_strict_now_ts, tz="UTC")
    else:
        _strict_now_ts = pd.Timestamp(_strict_now_ts).tz_convert("UTC")

    _strict_bucket = _strict_now_ts.floor("15min")
    _strict_elapsed_minute = (
        (_strict_now_ts - _strict_bucket).total_seconds() / 60.0
    )

    _strict_data = data_1m.copy()

    if _strict_data.index.tz is None:
        _strict_data.index = _strict_data.index.tz_localize("UTC")
    else:
        _strict_data.index = _strict_data.index.tz_convert("UTC")

    _strict_contract_rows = _strict_data[
        (_strict_data.index >= _strict_bucket)
        & (_strict_data.index < _strict_bucket + pd.Timedelta(minutes=15))
    ]

    if not _strict_contract_rows.empty:
        _strict_start_price = float(_strict_contract_rows.iloc[0]["Open"])
        _strict_latest_close = float(_strict_contract_rows.iloc[-1]["Close"])
        _strict_distance = abs(
            _strict_latest_close / _strict_start_price - 1.0
        )

    _strict_closes = _strict_data["Close"].astype(float)

    _strict_r1 = (
        _strict_closes.iloc[-1] / _strict_closes.iloc[-2] - 1.0
        if len(_strict_closes) >= 2 else 0.0
    )
    _strict_r3 = (
        _strict_closes.iloc[-1] / _strict_closes.iloc[-4] - 1.0
        if len(_strict_closes) >= 4 else 0.0
    )
    _strict_r5 = (
        _strict_closes.iloc[-1] / _strict_closes.iloc[-6] - 1.0
        if len(_strict_closes) >= 6 else 0.0
    )

    _strict_pred_up = bool(current_prediction)

    for _strict_ret in (_strict_r1, _strict_r3, _strict_r5):
        if _strict_pred_up and _strict_ret > 0:
            _strict_agreement += 1
        elif (not _strict_pred_up) and _strict_ret < 0:
            _strict_agreement += 1

    if len(live_valid) >= 2:
        _strict_prev_features = live_valid.loc[
            [live_valid.index[-2]],
            feature_columns,
        ]
        _strict_prev_prob = model.predict_proba(
            _strict_prev_features
        )[0]
        _strict_prev_conf = float(_strict_prev_prob.max())
        _strict_conf_change = float(current_confidence) - _strict_prev_conf

    _strict_model_ready = (
        _strict_elapsed_minute is not None
        and 8.0 <= _strict_elapsed_minute < 10.0
        and float(current_confidence) >= 0.95
        and _strict_agreement == 3
        and _strict_conf_change is not None
        and _strict_conf_change >= 0.0
        and _strict_distance is not None
        and _strict_distance >= 0.00175
    )

    _final_15m_ready = (
        _strict_model_ready
        and bool(_v3_brti_gate_ready)
    )

except Exception as _strict_error:
    _strict_model_ready = False
    _final_15m_ready = False
    _strict_error_text = str(_strict_error)

print("\n--- STRICT 15-MIN + V3 FINAL GATE ---")
print("Direction:", _final_15m_direction)
print("Model confidence:", f"{float(current_confidence):.1%}")
print(
    "Elapsed contract minute:",
    f"{_strict_elapsed_minute:.2f}"
    if _strict_elapsed_minute is not None
    else "UNKNOWN",
)
print(
    "BTC distance from 15m start:",
    f"{_strict_distance:.3%}"
    if _strict_distance is not None
    else "UNKNOWN",
)
print("Directional agreement:", f"{_strict_agreement}/3")
print(
    "Confidence strengthening:",
    "YES"
    if _strict_conf_change is not None and _strict_conf_change >= 0
    else "NO",
)
print(
    "Confidence change:",
    f"{_strict_conf_change:+.4f}"
    if _strict_conf_change is not None
    else "UNKNOWN",
)
print(
    "STRICT MODEL READY:",
    "YES" if _strict_model_ready else "NO",
)
print(
    "BRTI/KALSHI GATE READY:",
    "YES" if bool(_v3_brti_gate_ready) else "NO",
)

if _final_15m_ready:
    print("FINAL 15-MIN STATUS: READY")
    print("FINAL 15-MIN DIRECTION:", _final_15m_direction)
else:
    print("FINAL 15-MIN STATUS: WAIT")
    print("CURRENT LEAN:", _final_15m_direction)

if "_strict_error_text" in globals():
    print("Strict-gate safety note:", _strict_error_text)

# === STRICT 15M + V3 COMBINED READY END ===
'''

modified = original.replace(V3_END, V3_END + strict_block, 1)
BOT.write_text(modified)

result = subprocess.run(
    [sys.executable, "-m", "py_compile", str(BOT)],
    capture_output=True,
    text=True,
)

if result.returncode != 0:
    shutil.copy2(BACKUP, BOT)
    print("=== STRICT GATE INTEGRATION FAILED ===")
    print(result.stderr)
    print("Automatic rollback completed.")
    print("bot.py restored: YES")
    raise SystemExit(1)

lines = BOT.read_text().splitlines()
start_line = None
end_line = None

for i, line in enumerate(lines, start=1):
    if START_MARKER in line:
        start_line = i
    if END_MARKER in line:
        end_line = i

print("=== STRICT 15M + V3 INTEGRATION COMPLETE ===")
print("Timestamp:", datetime.now().isoformat(timespec="seconds"))
print("Backup created:", BACKUP.name)
print("Syntax check: PASSED")
print("Strict block start line:", start_line)
print("Strict block end line:", end_line)
print("Scalp logic changed: NO")
print("Order-placement code added: NO")
print("Signal-only behavior preserved: YES")
print()
print("NEXT: run bot.py and inspect STRICT 15-MIN + V3 FINAL GATE.")
