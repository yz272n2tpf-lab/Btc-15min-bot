#!/usr/bin/env python3
from pathlib import Path
import subprocess
import sys

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")
if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

original = BOT.read_text(encoding="utf-8", errors="ignore")
text = original

old_path = 'BRTI_PATH = "/trade-api/v2/cfbenchmarks/latest_values"'
new_path = 'BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"'

if old_path not in text and new_path not in text:
    raise SystemExit("STOP: BRTI path assignment not found. Nothing changed.")

if old_path in text:
    text = text.replace(old_path, new_path, 1)

start = text.find("def _parse_direct_brti_response(obj):")
end = text.find("def _fetch_direct_brti_once():")
if start == -1 or end == -1 or end <= start:
    raise SystemExit("STOP: direct BRTI parser block not found. Nothing changed.")

new_parser = '''def _parse_direct_brti_response(obj):
    # Kalshi wraps the raw CF Benchmarks response in {"data": ...}.
    data = obj.get("data", obj) if isinstance(obj, dict) else {}
    payload = data.get("payload") if isinstance(data, dict) else None

    # Documented /values response: payload is an array of published values
    # in ascending timestamp order. Use the newest valid item.
    if isinstance(payload, list):
        for item in reversed(payload):
            if not isinstance(item, dict):
                continue
            try:
                value = float(item["value"])
                time_ms = int(item["time"])
                return value, time_ms / 1000.0
            except Exception:
                continue
        return None

    # Backward-compatible fallback for the older latest_values shape.
    if isinstance(payload, dict):
        latest = (
            payload.get("latest_values")
            or payload.get("latestValues")
            or {}
        )
        item = latest.get("BRTI") if isinstance(latest, dict) else None
        if isinstance(item, dict):
            try:
                value = float(item["value"])
                time_ms = int(item["time"])
                return value, time_ms / 1000.0
            except Exception:
                return None

    return None

'''

text = text[:start] + new_parser + text[end:]

old_error = 'raise RuntimeError("BRTI response missing payload.latest_values.BRTI")'
new_error = 'raise RuntimeError("BRTI response missing usable /values payload")'
text = text.replace(old_error, new_error)

required = [
    'BRTI_PATH = "/trade-api/v2/cfbenchmarks/values"',
    "if isinstance(payload, list):",
    "for item in reversed(payload):",
    'float(item["value"])',
    'int(item["time"])',
]
missing = [x for x in required if x not in text]
if missing:
    raise SystemExit("STOP: verification failed: " + ", ".join(missing))

BOT.write_text(text, encoding="utf-8")

try:
    subprocess.run([sys.executable, "-m", "py_compile", str(BOT)], check=True)
except Exception:
    BOT.write_text(original, encoding="utf-8")
    raise

print("PASS: direct BRTI path changed from latest_values to documented values endpoint.")
print("PASS: parser updated for documented /values payload array.")
print("PASS: backward-compatible latest_values parser fallback retained.")
print("PASS: Python compile check.")
print("PASS: no keys or Railway Variables changed.")

subprocess.run(["git", "add", "--", str(BOT)], check=True)
subprocess.run(["git", "diff", "--cached", "--check"], check=True)

commit = subprocess.run(
    ["git", "commit", "-m", "Fix direct BRTI CF Benchmarks endpoint"],
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
    raise SystemExit("STOP: BRTI fix committed but push failed.")

print("RESULT: PASS — documented direct BRTI endpoint/parser fixed and pushed.")
print("NEXT: Railway should auto-redeploy. Do NOT change keys or Variables.")
