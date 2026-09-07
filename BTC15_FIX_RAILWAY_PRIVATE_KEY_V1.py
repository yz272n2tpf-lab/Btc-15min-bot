#!/usr/bin/env python3
from pathlib import Path
import subprocess

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")

if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

text = BOT.read_text(encoding="utf-8", errors="ignore")
old = '    KALSHI_PRIVATE_KEY_PATH.read_bytes(),'
new = '    base64.b64decode(__import__("os").getenv("KALSHI_PRIVATE_KEY_B64")) if __import__("os").getenv("KALSHI_PRIVATE_KEY_B64") else KALSHI_PRIVATE_KEY_PATH.read_bytes(),'

if new in text:
    print("PASS: Railway private-key fix is already installed.")
elif old not in text:
    raise SystemExit("STOP: expected private-key line not found. Nothing changed.")
else:
    text = text.replace(old, new, 1)
    BOT.write_text(text, encoding="utf-8")
    print("PASS: Railway private-key wiring patched.")

subprocess.run(["python", "-m", "py_compile", str(BOT)], check=True)
print("PASS: Python compile check.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
result = subprocess.run(
    ["git", "commit", "-m", "Fix Railway private key environment loading"],
    text=True, capture_output=True
)
combined = (result.stdout or "") + (result.stderr or "")
if result.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(result.returncode)

push = subprocess.run(["git", "push", "origin", "main"], text=True, capture_output=True)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: patch/commit succeeded, but git push failed. Run: git push origin main")

print("RESULT: PASS — fix pushed to GitHub. Railway should auto-redeploy.")
