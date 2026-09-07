#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

text = BOT.read_text(encoding="utf-8", errors="ignore")
original = text

# Patch the existing local Kalshi credential reads so Railway env secrets are used first.
# Codespaces/local ~/.kalshi fallback remains intact.
key_pat = re.compile(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*Path\.home\(\)\.joinpath\((["\'])\.kalshi/key_id\3\)\.read_text\(\)(?:\.strip\(\))?\s*$', re.MULTILINE)
pem_pat = re.compile(r'^(\s*)([A-Za-z_][A-Za-z0-9_]*)\s*=\s*Path\.home\(\)\.joinpath\((["\'])(\.kalshi/[^"\']*(?:pem|key)[^"\']*)\3\)\.read_text\(\)(?:\.strip\(\))?\s*$', re.MULTILINE | re.IGNORECASE)

km = key_pat.search(text)
if not km:
    raise SystemExit("STOP: could not find the existing ~/.kalshi/key_id read. No file changed.")

indent, lhs = km.group(1), km.group(2)
key_repl = f'{indent}{lhs} = (__import__("os").getenv("KALSHI_KEY_ID") or Path.home().joinpath(".kalshi/key_id").read_text()).strip()'
text = key_pat.sub(key_repl, text, count=1)

pm = pem_pat.search(text)
if not pm:
    raise SystemExit("STOP: could not identify the existing Kalshi private-key file read. No file changed.")

pindent, plhs, _, local_pem = pm.group(1), pm.group(2), pm.group(3), pm.group(4)
pem_repl = (
    f'{pindent}{plhs} = ('
    f'__import__("base64").b64decode(__import__("os").getenv("KALSHI_PRIVATE_KEY_B64")).decode("utf-8") '
    f'if __import__("os").getenv("KALSHI_PRIVATE_KEY_B64") '
    f'else Path.home().joinpath("{local_pem}").read_text())'
)
text = pem_pat.sub(pem_repl, text, count=1)

if text == original:
    raise SystemExit("STOP: no changes made.")

BOT.write_text(text, encoding="utf-8")

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

print("="*76)
print("BTC15 RAILWAY SECRET BRIDGE V1.1")
print("="*76)
print("Patched:", BOT.name)
print("Railway variables: KALSHI_KEY_ID + KALSHI_PRIVATE_KEY_B64")
print("Local ~/.kalshi fallback preserved.")
print("NO TRADING LOGIC CHANGED.")

run(["python", "-m", "py_compile", str(BOT)])
run(["git", "add", "--", str(BOT)])
staged = run(["git", "diff", "--cached", "--name-only"]).stdout.splitlines()
unexpected = [x for x in staged if x != str(BOT)]
if unexpected:
    print("STOP: unexpected staged files:", unexpected)
    run(["git", "reset"], check=False)
    raise SystemExit(5)

if staged:
    c = run(["git", "commit", "-m", "Add Railway Kalshi secret bridge"], check=False)
    print(c.stdout or c.stderr)
    combined = (c.stdout or "") + (c.stderr or "")
    if c.returncode != 0 and "nothing to commit" not in combined.lower():
        raise SystemExit(c.returncode)

p = run(["git", "push", "origin", "main"], check=False)
print(p.stdout or p.stderr)
if p.returncode != 0:
    print("RESULT: COMMIT CREATED, PUSH NEEDS RETRY")
    print("Run: git push origin main")
    raise SystemExit(p.returncode)

print("="*76)
print("RESULT: PASS — Railway secret bridge pushed to GitHub.")
print("NEXT: return to Railway Variables. Do not restart old crash.")
print("="*76)
