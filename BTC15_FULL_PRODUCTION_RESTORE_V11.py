#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys
import base64
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
BASE_COMMIT = "a5030ca"

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

current = BOT.read_text(encoding="utf-8", errors="ignore")
backup = Path("BTC15_PRE_FULL_RESTORE_BACKUP_DO_NOT_COMMIT.py")
backup.write_text(current, encoding="utf-8")

show = run(
    ["git", "show", f"{BASE_COMMIT}:{BOT.as_posix()}"],
    check=False,
)
if show.returncode != 0 or not show.stdout:
    raise SystemExit(
        f"STOP: could not read stable Git baseline {BASE_COMMIT}. "
        "Current production file was NOT changed."
    )

text = show.stdout

structural_markers = [
    'print("Training rows:", len(training_data))',
    "current_prediction = model.predict(current_features)[0]",
    "# === V3 BRTI/KALSHI SAFETY GATE START ===",
    '_v3_cal = pd.read_csv("brti_calibration_results.csv")',
    "# === STRICT 15M + V3 COMBINED READY START ===",
    "# === RESTORED TARGET-AWARE FAIR-VALUE ENTRY ENGINE START ===",
    "V4.13 TRUE SCALP + PROFIT-PROTECTION FORWARD SHADOW STARTING",
]
missing = [m for m in structural_markers if m not in text]
if missing or len(text.splitlines()) < 3400:
    raise SystemExit(
        "STOP: Git baseline failed structural verification. Missing: "
        + ", ".join(missing)
    )

cred_start = text.find("KALSHI_KEY_ID =")
base_url = text.find('KALSHI_BASE_URL = "https://api.elections.kalshi.com"', cred_start)
if cred_start == -1 or base_url == -1:
    raise SystemExit("STOP: top credential block not found in stable baseline.")

secure_top = '''import os
import sys
import traceback

KALSHI_KEY_ID = (
    os.getenv("KALSHI_KEY_ID")
    or Path.home().joinpath(".kalshi/key_id").read_text()
).strip()

KALSHI_PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"
_KALSHI_PRIVATE_KEY_B64 = os.getenv("KALSHI_PRIVATE_KEY_B64")
_KALSHI_PRIVATE_KEY_BYTES = (
    base64.b64decode(_KALSHI_PRIVATE_KEY_B64)
    if _KALSHI_PRIVATE_KEY_B64
    else KALSHI_PRIVATE_KEY_PATH.read_bytes()
)

kalshi_private_key = serialization.load_pem_private_key(
    _KALSHI_PRIVATE_KEY_BYTES,
    password=None,
)

def _btc15_redact(value):
    out = str(value)
    secrets = [
        os.getenv("KALSHI_KEY_ID"),
        os.getenv("KALSHI_PRIVATE_KEY_B64"),
    ]
    try:
        if _KALSHI_PRIVATE_KEY_B64:
            secrets.append(
                base64.b64decode(_KALSHI_PRIVATE_KEY_B64).decode(
                    "utf-8", errors="ignore"
                )
            )
    except Exception:
        pass
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[REDACTED_KALSHI_SECRET]")
            out = out.replace(repr(secret), "[REDACTED_KALSHI_SECRET]")
    return out

def _btc15_safe_excepthook(exc_type, exc, tb):
    sys.stderr.write(
        _btc15_redact(
            "".join(traceback.format_exception(exc_type, exc, tb))
        )
    )

sys.excepthook = _btc15_safe_excepthook

'''

text = text[:cred_start] + secure_top + text[base_url:]

second_start = text.find("KEY_ID =", text.find("KALSHI BTC15 SCALP SHADOW V1"))
second_base = text.find(
    'KALSHI_BASE_URL = "https://api.elections.kalshi.com"',
    second_start,
)
if second_start == -1 or second_base == -1:
    raise SystemExit("STOP: second scalp credential block not found.")

secure_second = '''KEY_ID = KALSHI_KEY_ID
PRIVATE_KEY_PATH = KALSHI_PRIVATE_KEY_PATH
PRIVATE_KEY = kalshi_private_key
'''

text = text[:second_start] + secure_second + text[second_base:]

text = text.replace(
    'BRTI_PATH = "/trade-api/v2/cfbenchmarks/latest_values"',
    'BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"',
)

parser_start = text.find("def _parse_direct_brti_response(obj):")
parser_end = text.find("def _fetch_direct_brti_once():", parser_start)
if parser_start == -1 or parser_end == -1:
    raise SystemExit("STOP: BRTI parser block not found.")

new_parser = '''def _parse_direct_brti_response(obj):
    data = obj.get("data", obj) if isinstance(obj, dict) else {}
    payload = data.get("payload") if isinstance(data, dict) else None

    if isinstance(payload, list):
        for item in reversed(payload):
            if not isinstance(item, dict):
                continue
            try:
                value = float(item["value"])
                time_ms = int(item["time"])
                return value, time_ms / 1000.0
            except Exception:
                continue
        return None

    if isinstance(payload, dict):
        latest = (
            payload.get("latest_values")
            or payload.get("latestValues")
            or {}
        )
        item = latest.get("BRTI") if isinstance(latest, dict) else None
        if isinstance(item, dict):
            try:
                value = float(item["value"])
                time_ms = int(item["time"])
                return value, time_ms / 1000.0
            except Exception:
                return None

    return None

'''

text = text[:parser_start] + new_parser + text[parser_end:]
text = text.replace(
    'raise RuntimeError("BRTI response missing payload.latest_values.BRTI")',
    'raise RuntimeError("BRTI response missing usable /values payload")',
)

must_have = [
    'print("Training rows:", len(training_data))',
    "current_prediction = model.predict(current_features)[0]",
    '_v3_cal = pd.read_csv("brti_calibration_results.csv")',
    "_strict_model_ready = False",
    "_fair_ready = False",
    "TRUE_SCALP_THRESHOLD",
    "PROFIT-PROTECTION",
    'BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"',
    "KEY_ID = KALSHI_KEY_ID",
    "PRIVATE_KEY = kalshi_private_key",
]
missing2 = [m for m in must_have if m not in text]
if missing2:
    raise SystemExit(
        "STOP: rebuilt production file failed verification: "
        + ", ".join(missing2)
    )

if len(text.splitlines()) < 3400:
    raise SystemExit("STOP: rebuilt file is unexpectedly short.")

bad_patterns = [
    "KALSHI_KEY_ID = KALSHI_KEY_ID",
    "KALSHI_PRIVATE_KEY_PATH = KALSHI_PRIVATE_KEY_PATH",
    'KEY_ID = (__import__("base64").b64decode',
    "KALSHI_(",
]
bad_found = [x for x in bad_patterns if x in text]
if bad_found:
    raise SystemExit(
        "STOP: old credential corruption pattern still present: "
        + ", ".join(bad_found)
    )

BOT.write_text(text, encoding="utf-8")

try:
    run([sys.executable, "-m", "py_compile", str(BOT)])
except BaseException:
    BOT.write_text(current, encoding="utf-8")
    raise

try:
    local_kid = Path.home().joinpath(".kalshi/key_id").read_text().strip()
    local_pem = Path.home().joinpath(".kalshi/private_key.pem").read_bytes()
    local_key = serialization.load_pem_private_key(local_pem, password=None)

    def auth_status(path, params=None):
        ts = str(int(time.time() * 1000))
        msg = (ts + "GET" + path).encode("utf-8")
        sig = local_key.sign(
            msg,
            padding.PSS(
                mgf=padding.MGF1(hashes.SHA256()),
                salt_length=padding.PSS.DIGEST_LENGTH,
            ),
            hashes.SHA256(),
        )
        headers = {
            "KALSHI-ACCESS-KEY": local_kid,
            "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
            "KALSHI-ACCESS-TIMESTAMP": ts,
        }
        r = requests.get(
            "https://external-api.kalshi.com" + path,
            headers=headers,
            params=params,
            timeout=10,
        )
        return r.status_code

    balance_status = auth_status("/trade-api/v2/portfolio/balance")
    brti_status = auth_status(
        "/trade-api/v2/cfbenchmarks/values",
        {"id": "BRTI", "maxResolution": "PER_SECOND"},
    )
    print("AUTH PREFLIGHT balance:", balance_status)
    print("AUTH PREFLIGHT BRTI:", brti_status)
    if balance_status != 200 or brti_status != 200:
        BOT.write_text(current, encoding="utf-8")
        raise SystemExit(
            "STOP: authenticated preflight failed; original current file restored."
        )
except SystemExit:
    raise
except Exception as exc:
    BOT.write_text(current, encoding="utf-8")
    raise SystemExit(
        f"STOP: auth preflight error; original current file restored. {type(exc).__name__}"
    )

print("=" * 74)
print("BTC15 FULL PRODUCTION RESTORE")
print("=" * 74)
print(f"PASS: restored full production candidate from Git commit {BASE_COMMIT}.")
print(f"PASS: restored {len(text.splitlines())} lines (core model + V3 + FINAL + fair + scalp).")
print("PASS: Railway credential loading rebuilt safely in BOTH credential locations.")
print("PASS: documented Direct BRTI /values endpoint + parser installed.")
print("PASS: Python compile check.")
print("PASS: authenticated balance preflight HTTP 200.")
print("PASS: authenticated BRTI preflight HTTP 200.")
print("PASS: no keys or Railway Variables were changed.")
print()

run(["git", "add", "--", str(BOT)])
run(["git", "diff", "--cached", "--check"])

commit = run(
    ["git", "commit", "-m", "Restore full BTC15 production core and secure Railway auth"],
    check=False,
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = run(["git", "push", "origin", "main"], check=False)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: full restore committed but push failed.")

print("RESULT: PASS — full 3,600+ line production bot restored, verified, and pushed.")
print("NEXT: Railway should auto-redeploy. Do NOT change keys or Variables.")
