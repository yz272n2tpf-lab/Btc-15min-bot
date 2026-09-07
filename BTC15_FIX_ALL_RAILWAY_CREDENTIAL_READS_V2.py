#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

text = BOT.read_text(encoding="utf-8", errors="ignore")
original = text

# Patch EVERY remaining direct Kalshi private-key file read in the production bot.
private_patterns = [
    "KALSHI_PRIVATE_KEY_PATH.read_bytes()",
    "PRIVATE_KEY_PATH.read_bytes()",
]
private_count = 0
for old in private_patterns:
    count = text.count(old)
    if count:
        replacement = (
            f'(base64.b64decode(__import__("os").getenv("KALSHI_PRIVATE_KEY_B64")) '
            f'if __import__("os").getenv("KALSHI_PRIVATE_KEY_B64") else {old})'
        )
        text = text.replace(old, replacement)
        private_count += count

# Patch common remaining key-id file reads too, so Railway does not hit the same problem next.
key_patterns = [
    'Path.home().joinpath(".kalshi/key_id").read_text().strip()',
    "Path.home().joinpath('.kalshi/key_id').read_text().strip()",
]
key_count = 0
for old in key_patterns:
    count = text.count(old)
    if count:
        replacement = f'(__import__("os").getenv("KALSHI_KEY_ID") or {old}).strip()'
        text = text.replace(old, replacement)
        key_count += count

if text == original:
    print("PASS: no remaining direct Kalshi credential file reads matched.")
else:
    BOT.write_text(text, encoding="utf-8")
    print(f"PASS: patched remaining private-key reads: {private_count}")
    print(f"PASS: patched remaining key-id reads: {key_count}")

subprocess.run(["python", "-m", "py_compile", str(BOT)], check=True)
print("PASS: Python compile check.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
commit = subprocess.run(
    ["git", "commit", "-m", "Fix all Railway Kalshi credential reads"],
    text=True, capture_output=True
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = subprocess.run(["git", "push", "origin", "main"], text=True, capture_output=True)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: fix is committed, but push failed. Run: git push origin main")

print("RESULT: PASS — all matched Railway credential reads fixed and pushed.")
