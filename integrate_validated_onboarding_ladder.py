
from pathlib import Path
import shutil
import py_compile

BOT = Path("bot.py")
BACKUP = Path("bot_before_validated_onboarding_ladder.py")

START = "# === VALIDATED ONBOARDING LADDER START ==="
END = "# === VALIDATED ONBOARDING LADDER END ==="

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found.")

text = BOT.read_text()

if START in text or END in text:
    raise SystemExit(
        "STOP: onboarding ladder markers already exist in bot.py. "
        "No changes made."
    )

anchor = 'print("\\n--- STRICT 15-MIN + V3 FINAL GATE ---")'
if anchor not in text:
    raise SystemExit(
        "ERROR: exact STRICT 15-MIN + V3 FINAL GATE anchor not found. "
        "No changes made."
    )

shutil.copy2(BOT, BACKUP)

block = r'''
# === VALIDATED ONBOARDING LADDER START ===
# Historical validation after corrected Kalshi timing:
# - Minute 8 qualified: minute 7 & 8 agree, both confidence >= 85%.
# - Minute 11 final lock: minute 9 & 11 agree, both >= 85%,
#   OR minute 11 confidence >= 90%.
# Signal-only. This block NEVER places orders and does not alter scalp logic.

_ladder_status = "RAW FORECAST"
_ladder_direction = _model_15m_direction
_ladder_confidence = float(current_confidence)
_ladder_reason = "Every-contract raw 15-minute forecast"
_ladder_contract_ticker = None
_ladder_state_path = Path(".kalshi_15m_ladder_state.json")
_ladder_state = {}

try:
    if _strict_active_market is not None:
        _ladder_contract_ticker = str(
            _strict_active_market.get("ticker", "")
        ) or None

    if _ladder_contract_ticker is not None and _strict_elapsed_minute is not None:
        import json as _ladder_json

        if _ladder_state_path.exists():
            try:
                _ladder_state = _ladder_json.loads(
                    _ladder_state_path.read_text()
                )
            except Exception:
                _ladder_state = {}

        # Never carry checkpoint history from one Kalshi contract into another.
        if _ladder_state.get("ticker") != _ladder_contract_ticker:
            _ladder_state = {
                "ticker": _ladder_contract_ticker,
                "checkpoints": {},
            }

        _ladder_checkpoints = _ladder_state.setdefault("checkpoints", {})
        _ladder_elapsed = float(_strict_elapsed_minute)

        # Capture each checkpoint only once, using the first live run at/after it.
        # A checkpoint is accepted only before the next checkpoint window.
        _ladder_windows = {
            "7": (7.0, 8.0),
            "8": (8.0, 9.0),
            "9": (9.0, 11.0),
            "11": (11.0, 15.0),
        }

        for _cp, (_lo, _hi) in _ladder_windows.items():
            if (
                _cp not in _ladder_checkpoints
                and _ladder_elapsed >= _lo
                and _ladder_elapsed < _hi
            ):
                _ladder_checkpoints[_cp] = {
                    "direction": _model_15m_direction,
                    "confidence": float(current_confidence),
                    "elapsed": _ladder_elapsed,
                }

        # Persist only signal state. No credentials, orders, or account data.
        _ladder_state_path.write_text(
            _ladder_json.dumps(_ladder_state, indent=2)
        )

        _cp7 = _ladder_checkpoints.get("7")
        _cp8 = _ladder_checkpoints.get("8")
        _cp9 = _ladder_checkpoints.get("9")
        _cp11 = _ladder_checkpoints.get("11")

        _minute8_qualified = bool(
            _cp7
            and _cp8
            and _cp7["direction"] == _cp8["direction"]
            and float(_cp7["confidence"]) >= 0.85
            and float(_cp8["confidence"]) >= 0.85
        )

        _minute11_lock = bool(
            _cp11
            and (
                (
                    _cp9
                    and _cp9["direction"] == _cp11["direction"]
                    and float(_cp9["confidence"]) >= 0.85
                    and float(_cp11["confidence"]) >= 0.85
                )
                or float(_cp11["confidence"]) >= 0.90
            )
        )

        # First validated stage wins during the contract.
        if _minute8_qualified:
            _ladder_status = "MINUTE 8 QUALIFIED"
            _ladder_direction = _cp8["direction"]
            _ladder_confidence = float(_cp8["confidence"])
            _ladder_reason = (
                "Minute 7 & 8 agree; both model confidences >=85%"
            )

        # Minute 11 is the stronger/final stage and supersedes minute 8.
        if _minute11_lock:
            _ladder_status = "MINUTE 11 FINAL LOCK"
            _ladder_direction = _cp11["direction"]
            _ladder_confidence = float(_cp11["confidence"])

            if (
                _cp9
                and _cp9["direction"] == _cp11["direction"]
                and float(_cp9["confidence"]) >= 0.85
                and float(_cp11["confidence"]) >= 0.85
            ):
                _ladder_reason = (
                    "Minute 9 & 11 agree; both model confidences >=85%"
                )
            else:
                _ladder_reason = "Minute 11 model confidence >=90%"

except Exception as _ladder_error:
    # Fail closed: preserve raw forecast and never create a false qualified call.
    _ladder_status = "RAW FORECAST"
    _ladder_direction = _model_15m_direction
    _ladder_confidence = float(current_confidence)
    _ladder_reason = f"Ladder state unavailable: {_ladder_error}"

print("\n--- VALIDATED 15-MIN SIGNAL LADDER ---")
print("CONTRACT:", _ladder_contract_ticker or "UNKNOWN")
print("SIGNAL STATUS:", _ladder_status)
print("SIGNAL DIRECTION:", _ladder_direction)
print("SIGNAL CONFIDENCE:", f"{_ladder_confidence:.1%}")
print("SIGNAL REASON:", _ladder_reason)

if _ladder_contract_ticker is not None:
    try:
        _ladder_seen = sorted(
            _ladder_state.get("checkpoints", {}).keys(),
            key=lambda x: int(x),
        )
        print(
            "SAME-CONTRACT CHECKPOINTS CAPTURED:",
            ", ".join(_ladder_seen) if _ladder_seen else "NONE",
        )
    except Exception:
        pass

print("SIGNAL-ONLY: YES")
# === VALIDATED ONBOARDING LADDER END ===

'''

text = text.replace(anchor, block + anchor, 1)
BOT.write_text(text)

try:
    py_compile.compile(str(BOT), doraise=True)
except Exception as exc:
    shutil.copy2(BACKUP, BOT)
    raise SystemExit(
        "SYNTAX CHECK FAILED. bot.py restored from backup.\n"
        + str(exc)
    )

print("=== VALIDATED ONBOARDING LADDER INTEGRATION COMPLETE ===")
print("Backup created:", BACKUP.name)
print("Syntax check: PASSED")
print("Corrected Kalshi clock changed: NO")
print("Existing BRTI/final gate changed: NO")
print("Scalp logic changed: NO")
print("Order-placement code added: NO")
print("Signal-only behavior preserved: YES")
print("Persistent same-contract state: .kalshi_15m_ladder_state.json")
print()
print("Integrated rules:")
print("RAW: every contract keeps current UP/DOWN forecast")
print("M8: minute 7 & 8 agree and both confidence >=85%")
print("M11: minute 9 & 11 agree and both >=85%, OR minute 11 >=90%")
print()
print("NEXT: run bot.py and inspect VALIDATED 15-MIN SIGNAL LADDER.")
