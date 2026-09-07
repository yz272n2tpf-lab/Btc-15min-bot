#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

original = BOT.read_text(encoding="utf-8", errors="ignore")

start_marker = "import os\n"
end_marker = 'KALSHI_BASE_URL = "https://api.elections.kalshi.com"'

start = original.find(start_marker)
end = original.find(end_marker)

if start == -1 or end == -1 or end <= start:
    raise SystemExit("STOP: could not safely locate the credential bootstrap block. Nothing changed.")

bootstrap = '''import os
import sys
import traceback

KALSHI_KEY_ID = (
    os.getenv("KALSHI_KEY_ID")
    or Path.home().joinpath(".kalshi/key_id").read_text()
).strip()
KEY_ID = KALSHI_KEY_ID

KALSHI_PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"
PRIVATE_KEY_PATH = KALSHI_PRIVATE_KEY_PATH

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
PRIVATE_KEY = kalshi_private_key

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

updated = original[:start] + bootstrap + original[end:]

checks = {
    "KEY_ID alias": "KEY_ID = KALSHI_KEY_ID",
    "private path definition": 'KALSHI_PRIVATE_KEY_PATH = Path.home() / ".kalshi" / "private_key.pem"',
    "Railway B64 loader": '_KALSHI_PRIVATE_KEY_B64 = os.getenv("KALSHI_PRIVATE_KEY_B64")',
    "PEM loader": "serialization.load_pem_private_key(",
    "PRIVATE_KEY alias": "PRIVATE_KEY = kalshi_private_key",
    "redaction": "def _btc15_redact",
}
missing = [name for name, needle in checks.items() if needle not in updated]
if missing:
    raise SystemExit("STOP: generated bootstrap failed checks: " + ", ".join(missing))

bad_patterns = [
    "KALSHI_KEY_ID = KALSHI_KEY_ID",
    "KALSHI_PRIVATE_KEY_PATH = KALSHI_PRIVATE_KEY_PATH",
    "PRIVATE_KEY = PRIVATE_KEY",
]
found_bad = [p for p in bad_patterns if p in updated]
if found_bad:
    raise SystemExit("STOP: unsafe self-assignment remains: " + ", ".join(found_bad))

BOT.write_text(updated, encoding="utf-8")

try:
    subprocess.run([sys.executable, "-m", "py_compile", str(BOT)], check=True)

    preflight = '''
import os, base64, time, requests
from pathlib import Path
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

kid = (os.getenv("KALSHI_KEY_ID") or Path.home().joinpath(".kalshi/key_id").read_text()).strip()
p = Path.home() / ".kalshi" / "private_key.pem"
b64 = os.getenv("KALSHI_PRIVATE_KEY_B64")
raw = base64.b64decode(b64) if b64 else p.read_bytes()
key = serialization.load_pem_private_key(raw, password=None)
assert kid and hasattr(key, "sign")

path = "/trade-api/v2/portfolio/balance"
ts = str(int(time.time() * 1000))
msg = ts + "GET" + path
sig = key.sign(
    msg.encode("utf-8"),
    padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=padding.PSS.DIGEST_LENGTH),
    hashes.SHA256(),
)
headers = {
    "KALSHI-ACCESS-KEY": kid,
    "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
    "KALSHI-ACCESS-TIMESTAMP": ts,
}
r = requests.get("https://api.elections.kalshi.com" + path, headers=headers, timeout=10)
if r.status_code != 200:
    raise SystemExit("AUTH_PREFLIGHT_FAILED:" + str(r.status_code))
'''
    pf = subprocess.run(
        [sys.executable, "-c", preflight],
        text=True,
        capture_output=True,
        timeout=20,
    )
    if pf.returncode != 0:
        raise RuntimeError((pf.stdout or "") + (pf.stderr or ""))

except Exception as exc:
    BOT.write_text(original, encoding="utf-8")
    raise SystemExit(f"STOP: preflight failed; production file restored. {exc}")

print("PASS: rebuilt the ENTIRE Railway/Kalshi credential bootstrap.")
print("PASS: KEY_ID and private-key aliases are all defined.")
print("PASS: Railway environment-variable loading is installed.")
print("PASS: secret-redaction protection is installed.")
print("PASS: Python compile check.")
print("PASS: local authenticated Kalshi read-only preflight.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
subprocess.run(["git", "diff", "--cached", "--check"], check=True)

commit = subprocess.run(
    ["git", "commit", "-m", "Rebuild Railway Kalshi credential bootstrap"],
    text=True,
    capture_output=True,
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = subprocess.run(
    ["git", "push", "origin", "main"],
    text=True,
    capture_output=True,
)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: bootstrap fixed and committed, but git push failed.")

print("RESULT: PASS — full credential bootstrap verified and pushed.")
print("NEXT: Railway should auto-redeploy. Do NOT change Variables.")
