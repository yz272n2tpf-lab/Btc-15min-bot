from pathlib import Path
import shutil
import re
from datetime import datetime

BOT = Path("bot.py")
BACKUP = Path("bot_pre_v3_integration_backup.py")

if not BOT.exists():
    raise SystemExit("ERROR: bot.py not found in this folder.")

# Fresh safety backup of the actual current bot.py
shutil.copy2(BOT, BACKUP)

text = BOT.read_text(errors="replace")
lines = text.splitlines()

print("=== BOT.PY V3 INTEGRATION INSPECTION ===")
print("bot.py found: YES")
print("Backup created:", BACKUP.name)
print("Total lines:", len(lines))
print("Characters:", len(text))
print()

patterns = {
    "KALSHI AUTH / API": [
        r"def\s+kalshi_headers",
        r"def\s+kalshi_get",
        r"def\s+get_kalshi",
        r"def\s+get_live_kalshi",
        r"KALSHI_BASE_URL",
        r"KALSHI_KEY",
    ],
    "BTC LIVE / COINBASE": [
        r"coinbase",
        r"BTC.*spot",
        r"live.*btc",
        r"get_live_price",
        r"fetch.*btc",
    ],
    "MODEL / CONFIDENCE": [
        r"model.*confidence",
        r"confidence",
        r"predict_proba",
        r"model_pred",
        r"FINAL 15-MIN",
    ],
    "SCALP / REVERSAL": [
        r"SCALP",
        r"REVERSAL",
        r"scalp",
        r"reversal",
    ],
    "COMBINED OUTPUT": [
        r"COMBINED",
        r"MODEL-SIDE ENTRY",
        r"KALSHI UP ASK",
        r"KALSHI DOWN ASK",
        r"FINAL 15-MIN",
    ],
}

hits = {}

for group, regexes in patterns.items():
    group_hits = []

    for i, line in enumerate(lines, start=1):
        for pattern in regexes:
            if re.search(pattern, line, flags=re.IGNORECASE):
                group_hits.append((i, line.strip()))
                break

    # Deduplicate line hits.
    seen = set()
    unique = []
    for item in group_hits:
        if item[0] not in seen:
            unique.append(item)
            seen.add(item[0])

    hits[group] = unique

for group, group_hits in hits.items():
    print(f"=== {group} ===")

    if not group_hits:
        print("No anchor found.")
    else:
        for line_no, content in group_hits[:20]:
            print(f"Line {line_no}: {content}")

        if len(group_hits) > 20:
            print(f"... {len(group_hits) - 20} more matches")

    print()

# Print context around the most useful combined-output hit.
candidate_lines = []

for group in ["COMBINED OUTPUT", "KALSHI AUTH / API", "MODEL / CONFIDENCE"]:
    candidate_lines.extend([x[0] for x in hits[group]])

candidate_lines = sorted(set(candidate_lines))

print("=== TARGET CONTEXT WINDOWS ===")

if not candidate_lines:
    print("No target anchors found.")
else:
    # Pick up to 5 useful anchors spread through the file.
    selected = []
    for n in candidate_lines:
        if not selected or n - selected[-1] > 20:
            selected.append(n)
        if len(selected) >= 5:
            break

    for anchor in selected:
        start = max(1, anchor - 6)
        end = min(len(lines), anchor + 10)

        print()
        print(f"--- Around line {anchor} ({start}-{end}) ---")

        for n in range(start, end + 1):
            marker = ">>" if n == anchor else "  "
            print(f"{marker} {n:4d}: {lines[n-1]}")

print()
print("=== SAFETY CHECK ===")
print("bot.py modified: NO")
print("Backup exists:", "YES" if BACKUP.exists() else "NO")
print("Ready for V3 integration mapping.")
