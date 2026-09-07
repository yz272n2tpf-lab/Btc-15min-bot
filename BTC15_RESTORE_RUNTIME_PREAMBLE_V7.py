#!/usr/bin/env python3
from pathlib import Path
import re
import subprocess
import sys

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

original = BOT.read_text(encoding="utf-8", errors="ignore")
text = original

# Guard: the secure credential bootstrap must already be present.
required_secure = [
    "KALSHI_KEY_ID",
    "KALSHI_PRIVATE_KEY_B64",
    "PRIVATE_KEY = kalshi_private_key",
]
missing_secure = [x for x in required_secure if x not in text]
if missing_secure:
    raise SystemExit(
        "STOP: secure credential bootstrap is not complete; nothing changed."
    )

# Restore runtime imports that were unintentionally removed with the old
# credential/startup block.
imports_to_add = []
if not re.search(r'^\s*import\s+json\b', text, re.M):
    imports_to_add.append("import json")
if not re.search(r'^\s*import\s+math\b', text, re.M):
    imports_to_add.append("import math")
if not re.search(r'^\s*import\s+signal\b', text, re.M):
    imports_to_add.append("import signal")
if not re.search(r'^\s*import\s+threading\b', text, re.M):
    imports_to_add.append("import threading")
if not re.search(r'^\s*from\s+collections\s+import\s+.*\bdeque\b', text, re.M):
    imports_to_add.append("from collections import deque")

if imports_to_add:
    # Put these after the existing top import area, before executable startup code.
    anchor = 'from datetime import datetime, timezone, timedelta\n'
    if anchor not in text:
        raise SystemExit("STOP: datetime import anchor not found; nothing changed.")
    text = text.replace(
        anchor,
        anchor + "\n".join(imports_to_add) + "\n",
        1,
    )

# Restore the original scalp-runtime constants/log paths only when absent.
runtime_defs = [
    ("POLL_SECONDS", 'POLL_SECONDS = 5'),
    ("MAX_HISTORY_SECONDS", 'MAX_HISTORY_SECONDS = 240'),
    ("EVENT_HORIZON_SECONDS", 'EVENT_HORIZON_SECONDS = 180'),
    ("CHEAP_EVENT_CEILING", 'CHEAP_EVENT_CEILING = 0.45'),
    ("EVENT_SAMPLE_SPACING_SECONDS", 'EVENT_SAMPLE_SPACING_SECONDS = 15'),
    ("STOP_LOSS", 'STOP_LOSS = 0.10'),
    ("TARGETS", 'TARGETS = [0.08, 0.10, 0.15, 0.20]'),
    ("SNAPSHOT_LOG", 'SNAPSHOT_LOG = Path("kalshi_scalp_shadow_snapshots_v1.csv")'),
    ("EVENT_LOG", 'EVENT_LOG = Path("kalshi_scalp_shadow_events_v1.csv")'),
    ("STATE_FILE", 'STATE_FILE = Path("kalshi_scalp_shadow_state_v1.json")'),
]

missing_defs = []
for name, line in runtime_defs:
    if not re.search(rf'^\s*{re.escape(name)}\s*=', text, re.M):
        missing_defs.append(line)

if missing_defs:
    anchor = "running = True"
    pos = text.find(anchor)
    if pos == -1:
        raise SystemExit("STOP: runtime anchor not found; nothing changed.")
    block = (
        "# Restored original BTC15 scalp runtime support block\n"
        + "\n".join(missing_defs)
        + "\n\n"
    )
    text = text[:pos] + block + text[pos:]

# Hard verification before writing.
required_after = [
    "from collections import deque",
    "import signal",
    "import threading",
    "import json",
    "POLL_SECONDS =",
    "MAX_HISTORY_SECONDS =",
    "EVENT_HORIZON_SECONDS =",
    "CHEAP_EVENT_CEILING =",
    "EVENT_SAMPLE_SPACING_SECONDS =",
    "STOP_LOSS =",
    "TARGETS =",
    "SNAPSHOT_LOG =",
    "EVENT_LOG =",
    "STATE_FILE =",
]
missing_after = [x for x in required_after if x not in text]
if missing_after:
    raise SystemExit(
        "STOP: runtime restore verification failed: "
        + ", ".join(missing_after)
    )

BOT.write_text(text, encoding="utf-8")

try:
    subprocess.run([sys.executable, "-m", "py_compile", str(BOT)], check=True)
except Exception:
    BOT.write_text(original, encoding="utf-8")
    raise

print("PASS: restored deque/signal/threading/json runtime imports.")
print("PASS: restored original scalp runtime constants and log paths.")
print("PASS: secure Railway/Kalshi credential bootstrap preserved.")
print("PASS: Python compile check.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
subprocess.run(["git", "diff", "--cached", "--check"], check=True)

commit = subprocess.run(
    ["git", "commit", "-m", "Restore BTC15 runtime preamble after Railway credential patch"],
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
    raise SystemExit("STOP: runtime restore committed but push failed.")

print("RESULT: PASS — full missing runtime support restored and pushed.")
print("NEXT: Railway should auto-redeploy. Do NOT change keys or Variables.")
