#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
SOURCE_CANDIDATES = [
    Path("bot_two_output_build_v4_7_final_plus_entry_winner.py"),
    Path("bot_two_output_build_v4_7_final_entry_winners.py"),
    Path("bot_two_output_build_v4_6_tournament_winner.py"),
]

START = "# === RESTORED TARGET-AWARE FAIR-VALUE ENTRY ENGINE START ==="
END = "# === RESTORED TARGET-AWARE FAIR-VALUE ENTRY ENGINE END ==="
INSERT_BEFORE = "# V4.8.4 EARLY-CONFIDENCE SHADOW LOGGER"

if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

target_original = BOT.read_text(encoding="utf-8", errors="ignore")

# If the complete fair engine is already present, do not duplicate it.
if (
    START in target_original
    and END in target_original
    and "_fair_ready = False" in target_original
    and "def _fair_parse_contract_times" in target_original
    and "def _fair_build_snapshot" in target_original
):
    print("PASS: complete fair-value engine already present; nothing changed.")
    raise SystemExit(0)

source = next((p for p in SOURCE_CANDIDATES if p.exists()), None)
if source is None:
    raise SystemExit(
        "STOP: no preserved fair-engine source file found. Nothing changed."
    )

src = source.read_text(encoding="utf-8", errors="ignore")
s = src.find(START)
e = src.find(END)
if s == -1 or e == -1 or e <= s:
    raise SystemExit(
        f"STOP: could not extract preserved fair engine from {source.name}. Nothing changed."
    )
e += len(END)
fair_block = src[s:e] + "\n\n"

required = [
    "_fair_ready = False",
    "def _fair_parse_contract_times",
    "def _fair_build_snapshot",
    "_fair_rf = RandomForestClassifier",
    "_fair_sigmoid = LogisticRegression",
    "_fair_ready = True",
]
missing = [x for x in required if x not in fair_block]
if missing:
    raise SystemExit(
        "STOP: preserved fair block failed verification: " + ", ".join(missing)
    )

anchor = target_original.find(INSERT_BEFORE)
if anchor == -1:
    raise SystemExit(
        "STOP: early-confidence insertion anchor not found. Nothing changed."
    )

# Remove any incomplete fair-engine fragment if markers exist, then insert one
# complete preserved block immediately before the early-confidence logger.
text = target_original
old_s = text.find(START)
old_e = text.find(END)
if old_s != -1 and old_e != -1 and old_e > old_s:
    old_e += len(END)
    text = text[:old_s] + text[old_e:].lstrip("\n")
    anchor = text.find(INSERT_BEFORE)
    if anchor == -1:
        raise SystemExit("STOP: insertion anchor disappeared. Nothing changed.")

text = text[:anchor] + fair_block + text[anchor:]

# Verify definitions appear before their live shadow use.
use_pos = text.find("def _live_fair_shadow")
for needle in [
    "_fair_ready = False",
    "def _fair_parse_contract_times",
    "def _fair_build_snapshot",
]:
    pos = text.find(needle)
    if pos == -1 or (use_pos != -1 and pos > use_pos):
        raise SystemExit(
            f"STOP: ordering verification failed for {needle}. Nothing changed."
        )

BOT.write_text(text, encoding="utf-8")

try:
    subprocess.run([sys.executable, "-m", "py_compile", str(BOT)], check=True)
except Exception:
    BOT.write_text(target_original, encoding="utf-8")
    raise

print("PASS: restored COMPLETE preserved target-aware fair-value engine.")
print("PASS: _fair_ready and fair helper definitions now precede live early shadow.")
print(f"PASS: source used: {source.name}")
print("PASS: Python compile check.")
print("NOTE: Direct BRTI 401 was NOT changed by this patch.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
subprocess.run(["git", "diff", "--cached", "--check"], check=True)

commit = subprocess.run(
    ["git", "commit", "-m", "Restore preserved BTC15 fair value engine"],
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
    raise SystemExit("STOP: fair engine restored and committed, but push failed.")

print("RESULT: PASS — fair-value engine restored and pushed.")
print("NEXT: Railway should auto-redeploy. Do NOT change keys or Variables.")
