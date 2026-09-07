#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

text = BOT.read_text(encoding="utf-8", errors="ignore")
original = text

top_pat = re.compile(
    r'KALSHI_KEY_ID\s*=.*?\n'
    r'KALSHI_PRIVATE_KEY_PATH\s*=.*?\n'
    r'kalshi_private_key\s*=\s*serialization\.load_pem_private_key\(\n'
    r'.*?\n'
    r'\s*password=None,\n'
    r'\s*\)\n',
    re.DOTALL,
)

top_repl = '''import os
import sys
import traceback

KALSHI_KEY_ID = (os.getenv("KALSHI_KEY_ID") or Path.home().joinpath(".kalshi/key_id").read_text()).strip()
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

def _btc15_redact(text):
    out = str(text)
    secrets = [
        os.getenv("KALSHI_KEY_ID"),
        os.getenv("KALSHI_PRIVATE_KEY_B64"),
    ]
    try:
        if _KALSHI_PRIVATE_KEY_B64:
            secrets.append(base64.b64decode(_KALSHI_PRIVATE_KEY_B64).decode("utf-8", errors="ignore"))
    except Exception:
        pass
    for secret in secrets:
        if secret:
            out = out.replace(secret, "[REDACTED_KALSHI_SECRET]")
            out = out.replace(repr(secret), "[REDACTED_KALSHI_SECRET]")
    return out

def _btc15_safe_excepthook(exc_type, exc, tb):
    sys.stderr.write(_btc15_redact("".join(traceback.format_exception(exc_type, exc, tb))))

sys.excepthook = _btc15_safe_excepthook
'''

text, n_top = top_pat.subn(top_repl, text, count=1)
if n_top != 1:
    raise SystemExit("STOP: could not safely identify the top credential block. Nothing written.")

dup_pat = re.compile(
    r'KEY_ID\s*=.*?\n'
    r'PRIVATE_KEY_PATH\s*=.*?\n'
    r'PRIVATE_KEY\s*=\s*serialization\.load_pem_private_key\(\n'
    r'.*?\n'
    r'\s*\)\n',
    re.DOTALL,
)

dup_repl = '''KEY_ID = KALSHI_KEY_ID
PRIVATE_KEY_PATH = KALSHI_PRIVATE_KEY_PATH
PRIVATE_KEY = kalshi_private_key
'''

text, n_dup = dup_pat.subn(dup_repl, text, count=1)
if n_dup != 1:
    raise SystemExit("STOP: could not safely identify the duplicate scalp credential block. Nothing written.")

text = text.replace(
    '_brti_last_error = f"{type(exc).__name__}: {exc}"',
    '_brti_last_error = _btc15_redact(f"{type(exc).__name__}: {exc}")'
)

if text == original:
    raise SystemExit("STOP: no changes made.")

BOT.write_text(text, encoding="utf-8")
print("PASS: credential wiring normalized.")
print("PASS: duplicate scalp key-id bug removed.")
print("PASS: exception redaction installed.")

subprocess.run(["python", "-m", "py_compile", str(BOT)], check=True)
print("PASS: Python compile check.")

check = BOT.read_text(encoding="utf-8", errors="ignore")
if 'KEY_ID = (__import__("base64").b64decode' in check:
    raise SystemExit("STOP: unsafe duplicate KEY_ID assignment still present.")
print("PASS: no private key can be used as KALSHI-ACCESS-KEY.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
commit = subprocess.run(
    ["git", "commit", "-m", "Secure Railway Kalshi credential wiring"],
    text=True, capture_output=True
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = subprocess.run(["git", "push", "origin", "main"], text=True, capture_output=True)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: security patch committed, but push failed. Run: git push origin main")

print("RESULT: PASS — security patch pushed. Do NOT add the replacement Kalshi key yet.")
