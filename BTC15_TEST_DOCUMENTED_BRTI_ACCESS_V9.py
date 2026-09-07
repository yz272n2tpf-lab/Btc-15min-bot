#!/usr/bin/env python3
from pathlib import Path
import base64, time, requests
from cryptography.hazmat.primitives import hashes, serialization
from cryptography.hazmat.primitives.asymmetric import padding

BASE = "https://external-api.kalshi.com"
KEY_ID = Path.home().joinpath(".kalshi/key_id").read_text().strip()
PRIVATE_KEY = serialization.load_pem_private_key(
    Path.home().joinpath(".kalshi/private_key.pem").read_bytes(),
    password=None,
)

def headers(method, path):
    ts = str(int(time.time() * 1000))
    msg = (ts + method.upper() + path).encode("utf-8")
    sig = PRIVATE_KEY.sign(
        msg,
        padding.PSS(
            mgf=padding.MGF1(hashes.SHA256()),
            salt_length=padding.PSS.DIGEST_LENGTH,
        ),
        hashes.SHA256(),
    )
    return {
        "KALSHI-ACCESS-KEY": KEY_ID,
        "KALSHI-ACCESS-SIGNATURE": base64.b64encode(sig).decode("utf-8"),
        "KALSHI-ACCESS-TIMESTAMP": ts,
    }

def check(label, path, params=None):
    r = requests.get(
        BASE + path,
        headers=headers("GET", path),
        params=params,
        timeout=10,
    )
    print(f"{label}: HTTP {r.status_code}")
    return r.status_code

print("=" * 66)
print("BTC15 DOCUMENTED BRTI ACCESS TEST")
print("READ-ONLY TEST — NO FILES CHANGED — NO GIT PUSH")
print("=" * 66)

balance = check(
    "Normal authenticated Kalshi endpoint",
    "/trade-api/v2/portfolio/balance",
)

brti = check(
    "Documented CF Benchmarks BRTI endpoint",
    "/trade-api/v2/cfbenchmarks/values",
    {"id": "BRTI", "maxResolution": "PER_SECOND"},
)

print()
if balance == 200 and brti == 200:
    print("RESULT: PASS — key works AND this account has CF Benchmarks access.")
    print("NEXT: patch production BRTI path from latest_values to values.")
elif balance == 200 and brti in (401, 403):
    print("RESULT: ENTITLEMENT BLOCK — normal Kalshi auth works, but CF Benchmarks access is denied.")
    print("NEXT: do NOT change keys. Keep direct BRTI shadow disabled/fail-closed or request Kalshi entitlement.")
elif balance != 200:
    print("RESULT: AUTH TEST FAILED — normal authenticated endpoint did not return 200.")
    print("NEXT: stop. Do not change production.")
else:
    print(f"RESULT: CF ENDPOINT RETURNED HTTP {brti}.")
    print("NEXT: inspect this status before changing production.")
