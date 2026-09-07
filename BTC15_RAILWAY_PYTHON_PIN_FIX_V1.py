#!/usr/bin/env python3
from pathlib import Path
import subprocess

print("="*72)
print("BTC15 RAILWAY PYTHON PIN FIX V1")
print("="*72)

# Railway/mise is failing on the exact old patch 3.12.1.
# Use the 3.12 minor line so Railway can select a currently supported 3.12 build.
Path(".python-version").write_text("3.12\n", encoding="utf-8")

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

run(["git","add","--",".python-version"])

staged = run(["git","diff","--cached","--name-only"]).stdout.splitlines()
unexpected = [x for x in staged if x != ".python-version"]
if unexpected:
    print("STOP: unexpected staged files:", unexpected)
    run(["git","reset"], check=False)
    raise SystemExit(3)

print("Changing Railway Python pin:")
print("  3.12.1  ->  3.12")
print()

c = run(["git","commit","-m","Use supported Railway Python 3.12 runtime"], check=False)
print(c.stdout or c.stderr)
text = (c.stdout or "") + (c.stderr or "")
if c.returncode != 0 and "nothing to commit" not in text.lower():
    raise SystemExit(c.returncode)

p = run(["git","push","origin","main"], check=False)
print(p.stdout or p.stderr)
if p.returncode != 0:
    print("RESULT: COMMIT CREATED, PUSH NEEDS RETRY")
    print("Run: git push origin main")
    raise SystemExit(p.returncode)

print("="*72)
print("RESULT: PASS — Python runtime pin fix pushed.")
print("Railway should auto-deploy this commit.")
print("NEXT: return to Railway and watch the NEW deployment.")
print("="*72)
