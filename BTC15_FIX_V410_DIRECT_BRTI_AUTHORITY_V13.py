#!/usr/bin/env python3
from pathlib import Path
import base64
import subprocess
import sys
import time
import requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BOT = Path("bot_two_output_build_v4_13_profit_protection_shadow.py")

def run(args, check=True):
    p = subprocess.run(args, text=True, capture_output=True)
    if check and p.returncode != 0:
        print((p.stdout or "") + (p.stderr or ""))
        raise SystemExit(p.returncode)
    return p

if not BOT.exists():
    raise SystemExit(f"STOP: missing {BOT}")

original = BOT.read_text(encoding="utf-8", errors="ignore")

# Confirm the full production restore is still present.
required_full = [
    'print("Training rows:", len(training_data))',
    '_v3_cal = pd.read_csv("brti_calibration_results.csv")',
    "_fair_ready = False",
    "V4.10 DIRECT BRTI AUTHORITY GATE",
    "V4.13 TRUE SCALP + PROFIT-PROTECTION FORWARD SHADOW STARTING",
]
missing = [x for x in required_full if x not in original]
if missing or len(original.splitlines()) < 3400:
    raise SystemExit(
        "STOP: full production restore is not intact. Nothing changed."
    )

start = original.find("def _direct_brti_authority_fetch():")
end = original.find("try:\n    if _audit_target is None:", start)
if start == -1 or end == -1 or end <= start:
    raise SystemExit(
        "STOP: V4.10 Direct BRTI authority function not found. Nothing changed."
    )

new_func = '''def _direct_brti_authority_fetch():
    # Use Kalshi's documented CF Benchmarks passthrough endpoint.
    _path = "/trade-api/v2/cfbenchmarks/values"
    _base = "https://external-api.kalshi.com"
    _resp = requests.get(
        _base + _path,
        headers=kalshi_headers("GET", _path),
        params={"id": "BRTI", "maxResolution": "PER_SECOND"},
        timeout=8,
    )
    _resp.raise_for_status()
    _obj = _resp.json()
    _data = _obj.get("data", _obj) if isinstance(_obj, dict) else {}
    _payload = _data.get("payload") if isinstance(_data, dict) else None

    # /values returns recent values in ascending publication time.
    if not isinstance(_payload, list) or not _payload:
        raise RuntimeError("direct BRTI /values payload missing")

    _item = None
    for _candidate in reversed(_payload):
        if not isinstance(_candidate, dict):
            continue
        if _candidate.get("value") is None or _candidate.get("time") is None:
            continue
        _item = _candidate
        break

    if _item is None:
        raise RuntimeError("direct BRTI /values has no usable BRTI item")

    _value = float(_item["value"])
    _cf_ts = int(_item["time"]) / 1000.0
    _age = max(0.0, time.time() - _cf_ts)
    return _value, _age

'''

updated = original[:start] + new_func + original[end:]

# Verify the specific authority gate no longer contains the stale endpoint.
authority_block = updated[
    updated.find("def _direct_brti_authority_fetch():"):
    updated.find("try:\n    if _audit_target is None:", updated.find("def _direct_brti_authority_fetch():"))
]
if "/cfbenchmarks/latest_values" in authority_block:
    raise SystemExit("STOP: stale authority endpoint still present. Nothing changed.")
if '"/trade-api/v2/cfbenchmarks/values"' not in authority_block:
    raise SystemExit("STOP: documented authority endpoint missing. Nothing changed.")
if "reversed(_payload)" not in authority_block:
    raise SystemExit("STOP: /values array parser missing. Nothing changed.")

BOT.write_text(updated, encoding="utf-8")

try:
    run([sys.executable, "-m", "py_compile", str(BOT)])
except BaseException:
    BOT.write_text(original, encoding="utf-8")
    raise

# Read-only authenticated preflight using the already verified local pair.
try:
    kid = Path.home().joinpath(".kalshi/key_id").read_text().strip()
    pem = Path.home().joinpath(".kalshi/private_key.pem").read_bytes()
    key = serialization.load_pem_private_key(pem, password=None)

    path = "/trade-api/v2/cfbenchmarks/values"
    ts = str(int(time.time() * 1000))
    msg = (ts + "GET" + path).encode("utf-8")
    sig = key.sign(
        msg,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    headers = {
        "KALSHI-ACCESS-KEY": kid,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }
    r = requests.get(
        "https://external-api.kalshi.com" + path,
        headers=headers,
        params={"id": "BRTI", "maxResolution": "PER_SECOND"},
        timeout=10,
    )
    print("AUTHORITY PREFLIGHT HTTP:", r.status_code)
    if r.status_code != 200:
        BOT.write_text(original, encoding="utf-8")
        raise SystemExit("STOP: authority preflight failed; original file restored.")

    obj = r.json()
    data = obj.get("data", obj) if isinstance(obj, dict) else {}
    payload = data.get("payload") if isinstance(data, dict) else None
    if not isinstance(payload, list) or not payload:
        BOT.write_text(original, encoding="utf-8")
        raise SystemExit("STOP: /values payload is not a non-empty list; original file restored.")

    item = next(
        (
            x for x in reversed(payload)
            if isinstance(x, dict)
            and x.get("value") is not None
            and x.get("time") is not None
        ),
        None,
    )
    if item is None:
        BOT.write_text(original, encoding="utf-8")
        raise SystemExit("STOP: no usable BRTI item found; original file restored.")

    age = max(0.0, time.time() - int(item["time"]) / 1000.0)
    float(item["value"])
    print("AUTHORITY PREFLIGHT PARSE: PASS")
    print(f"AUTHORITY PREFLIGHT AGE: {age:.1f}s")

except SystemExit:
    raise
except Exception as exc:
    BOT.write_text(original, encoding="utf-8")
    raise SystemExit(
        f"STOP: authority preflight error; original file restored. {type(exc).__name__}"
    )

print("PASS: V4.10 Direct BRTI authority now uses documented /values endpoint.")
print("PASS: V4.10 authority parser now reads the /values payload array.")
print("PASS: full production core preserved.")
print("PASS: Python compile check.")
print("PASS: no Kalshi keys or Railway Variables changed.")

run(["git", "add", "--", str(BOT)])
run(["git", "diff", "--cached", "--check"])

commit = run(
    ["git", "commit", "-m", "Fix V4.10 direct BRTI authority endpoint"],
    check=False,
)
combined = (commit.stdout or "") + (commit.stderr or "")
if commit.returncode != 0 and "nothing to commit" not in combined.lower():
    print(combined)
    raise SystemExit(commit.returncode)

push = run(["git", "push", "origin", "main"], check=False)
print(push.stdout or push.stderr)
if push.returncode != 0:
    raise SystemExit("STOP: V4.10 authority fix committed but push failed.")

print("RESULT: PASS — V4.10 Direct BRTI authority fixed and pushed.")
print("NEXT: Railway should auto-redeploy. Do NOT change keys or Variables.")
