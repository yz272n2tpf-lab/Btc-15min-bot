#!/usr/bin/env python3
from pathlib import Path
import base64
import os
import stat
import subprocess
import sys
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
PRIVATE_PATH = Path.home() / ".kalshi" / "private_key.pem"
KEY_ID_PATH = Path.home() / ".kalshi" / "key_id"
SECRETS_OUT = Path("RAILWAY_SECRETS_COPY_ME.txt")

if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")
if not PRIVATE_PATH.exists():
    raise SystemExit("STOP: missing ~/.kalshi/private_key.pem")

private_bytes = PRIVATE_PATH.read_bytes()
private_key = serialization.load_pem_private_key(private_bytes, password=None)

candidates = [
    "a2282882-1393-4b94-ba76-eac255ab81dd",
    "4d408c96-0add-4eed-8974-b81349f01a56",
]

def auth_status(key_id):
    path = "/trade-api/v2/portfolio/balance"
    ts = str(int(time.time() * 1000))
    message = f"{ts}GET{path}".encode("utf-8")
    sig = private_key.sign(
        message,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    headers = {
        "KALSHI-ACCESS-KEY": key_id,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }
    r = requests.get(
        "https://external-api.kalshi.com" + path,
        headers=headers,
        timeout=10,
    )
    return r.status_code

statuses = []
for i, kid in enumerate(candidates, start=1):
    try:
        code = auth_status(kid)
    except Exception as exc:
        code = f"ERROR:{type(exc).__name__}"
    statuses.append(code)
    print(f"Candidate {i} auth status: {code}")

matches = [i for i, code in enumerate(statuses) if code == 200]
if len(matches) != 1:
    raise SystemExit(
        "STOP: could not uniquely match the local private key to one Kalshi key. "
        "Nothing changed."
    )

winner = candidates[matches[0]]
print(f"PASS: local private key matched Kalshi read-only key candidate {matches[0] + 1}.")

KEY_ID_PATH.parent.mkdir(parents=True, exist_ok=True)
KEY_ID_PATH.write_text(winner + "\n", encoding="utf-8")
os.chmod(KEY_ID_PATH, 0o600)
print("PASS: correct Kalshi key ID saved locally.")

pem_b64 = base64.b64encode(private_bytes).decode("ascii")
SECRETS_OUT.write_text(
    f"KALSHI_KEY_ID={winner}\n"
    f"KALSHI_PRIVATE_KEY_B64={pem_b64}\n",
    encoding="utf-8",
)
os.chmod(SECRETS_OUT, stat.S_IRUSR | stat.S_IWUSR)

exclude = Path(".git/info/exclude")
exclude.parent.mkdir(parents=True, exist_ok=True)
existing = exclude.read_text(encoding="utf-8", errors="ignore") if exclude.exists() else ""
if SECRETS_OUT.name not in existing.splitlines():
    with exclude.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(SECRETS_OUT.name + "\n")
print("PASS: Railway secret copy file rebuilt with matching credentials.")

original = BOT.read_text(encoding="utf-8", errors="ignore")
start_marker = "import os\nimport sys\nimport traceback\n"
end_marker = 'KALSHI_BASE_URL = "https://api.elections.kalshi.com"'

start = original.find(start_marker)
end = original.find(end_marker)

if start == -1 or end == -1 or end <= start:
    raise SystemExit("STOP: could not safely locate credential bootstrap. Nothing pushed.")

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

for bad in [
    "KALSHI_KEY_ID = KALSHI_KEY_ID",
    "KALSHI_PRIVATE_KEY_PATH = KALSHI_PRIVATE_KEY_PATH",
    "PRIVATE_KEY = PRIVATE_KEY",
]:
    if bad in updated:
        raise SystemExit("STOP: unsafe self-assignment remains. Nothing pushed.")

BOT.write_text(updated, encoding="utf-8")

try:
    subprocess.run([sys.executable, "-m", "py_compile", str(BOT)], check=True)
except Exception:
    BOT.write_text(original, encoding="utf-8")
    raise

print("PASS: full Railway/Kalshi credential bootstrap rebuilt.")
print("PASS: Python compile check.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
subprocess.run(["git", "diff", "--cached", "--check"], check=True)

commit = subprocess.run(
    ["git", "commit", "-m", "Match Kalshi key and rebuild Railway credential bootstrap"],
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
    raise SystemExit("STOP: code fixed and committed, but push failed.")

print("RESULT: PASS — matching key identified, bootstrap fixed, and pushed.")
print("NEXT: update Railway Variables once using RAILWAY_SECRETS_COPY_ME.txt.")
