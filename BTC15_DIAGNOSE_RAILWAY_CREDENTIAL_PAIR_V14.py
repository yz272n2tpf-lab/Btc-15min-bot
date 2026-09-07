#!/usr/bin/env python3
from pathlib import Path
import base64
import hashlib
import os
import stat
import subprocess
import sys
from cryptography.hazmat.primitives import serialization

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
LOCAL_ID = Path.home() / ".kalshi" / "key_id"
LOCAL_KEY = Path.home() / ".kalshi" / "private_key.pem"
SECRETS_OUT = Path("RAILWAY_SECRETS_VERIFIED_V14.txt")

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

if not BOT.exists() or not LOCAL_ID.exists() or not LOCAL_KEY.exists():
    raise SystemExit("STOP: required bot/local verified Kalshi files are missing.")

kid = LOCAL_ID.read_text(encoding="utf-8").strip()
pem = LOCAL_KEY.read_bytes()
key = serialization.load_pem_private_key(pem, password=None)

pub_der = key.public_key().public_bytes(
    serialization.Encoding.DER,
    serialization.PublicFormat.SubjectPublicKeyInfo,
)
expected_id_hash = hashlib.sha256(kid.encode()).hexdigest()
expected_pub_hash = hashlib.sha256(pub_der).hexdigest()

SECRETS_OUT.write_text(
    f"KALSHI_KEY_ID={kid}\n"
    f"KALSHI_PRIVATE_KEY_B64={base64.b64encode(pem).decode('ascii')}\n",
    encoding="utf-8",
)
os.chmod(SECRETS_OUT, stat.S_IRUSR | stat.S_IWUSR)

exclude = Path(".git/info/exclude")
existing = exclude.read_text(encoding="utf-8", errors="ignore") if exclude.exists() else ""
if SECRETS_OUT.name not in existing.splitlines():
    with exclude.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(SECRETS_OUT.name + "\n")

text = BOT.read_text(encoding="utf-8", errors="ignore")
original = text

marker_start = "# === RAILWAY VERIFIED-CREDENTIAL DIAGNOSTIC V14 START ==="
marker_end = "# === RAILWAY VERIFIED-CREDENTIAL DIAGNOSTIC V14 END ==="

if marker_start in text and marker_end in text:
    s = text.find(marker_start)
    e = text.find(marker_end, s) + len(marker_end)
    text = text[:s] + text[e:].lstrip("\n")

anchor = text.find("def kalshi_get(path, params=None):")
if anchor == -1:
    raise SystemExit("STOP: kalshi_get anchor not found. Nothing changed.")

diag_template = '''{marker_start}
def _railway_verified_credential_diagnostic_v14():
    import hashlib as _hashlib_v14
    try:
        _env_id_hash = _hashlib_v14.sha256(
            str(KALSHI_KEY_ID).strip().encode("utf-8")
        ).hexdigest()

        _pub_der = kalshi_private_key.public_key().public_bytes(
            serialization.Encoding.DER,
            serialization.PublicFormat.SubjectPublicKeyInfo,
        )
        _env_pub_hash = _hashlib_v14.sha256(_pub_der).hexdigest()

        print("RAILWAY KEY-ID MATCH LOCAL VERIFIED:", _env_id_hash == "{expected_id_hash}")
        print("RAILWAY PRIVATE-KEY MATCH LOCAL VERIFIED:", _env_pub_hash == "{expected_pub_hash}")

        _base = "https://external-api.kalshi.com"

        _balance_path = "/trade-api/v2/portfolio/balance"
        _rb = requests.get(
            _base + _balance_path,
            headers=kalshi_headers("GET", _balance_path),
            timeout=8,
        )
        print("RAILWAY AUTH BALANCE HTTP:", _rb.status_code)

        _brti_path = "/trade-api/v2/cfbenchmarks/values"
        _rr = requests.get(
            _base + _brti_path,
            headers=kalshi_headers("GET", _brti_path),
            params={{"id": "BRTI", "maxResolution": "PER_SECOND"}},
            timeout=8,
        )
        print("RAILWAY AUTH BRTI HTTP:", _rr.status_code)

    except Exception as _exc_v14:
        print("RAILWAY AUTH DIAGNOSTIC ERROR:", type(_exc_v14).__name__)

_railway_verified_credential_diagnostic_v14()
{marker_end}

'''

diag = diag_template.format(
    marker_start=marker_start,
    marker_end=marker_end,
    expected_id_hash=expected_id_hash,
    expected_pub_hash=expected_pub_hash,
)

text = text[:anchor] + diag + text[anchor:]
BOT.write_text(text, encoding="utf-8")

try:
    run([sys.executable, "-m", "py_compile", str(BOT)])
except BaseException:
    BOT.write_text(original, encoding="utf-8")
    raise

print("PASS: Railway credential fingerprint diagnostic installed.")
print("PASS: compares Railway runtime pair to the locally verified 200/200 pair.")
print("PASS: runtime will test balance + BRTI and print HTTP status only.")
print("PASS: fresh verified Railway copy file created.")
print("PASS: no secret values will be printed in Railway logs.")
print("PASS: Python compile check.")

run(["git", "add", "--", str(BOT)])
run(["git", "diff", "--cached", "--check"])

commit = run(
    ["git", "commit", "-m", "Add Railway verified credential diagnostic"],
    check=False,
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = run(["git", "push", "origin", "main"], check=False)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: diagnostic committed but push failed.")

print("RESULT: PASS — Railway credential diagnostic pushed.")
print("NEXT: wait for Railway redeploy and check the four RAILWAY ... lines.")
