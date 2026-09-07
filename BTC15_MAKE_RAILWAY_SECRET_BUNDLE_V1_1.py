#!/usr/bin/env python3
from pathlib import Path
import base64
import os
import stat

HOME = Path.home()
KDIR = HOME / ".kalshi"
OUT = Path("RAILWAY_SECRETS_DO_NOT_COMMIT.env")

key_id_path = KDIR / "key_id"
pem_path = KDIR / "private_key.pem"

if not key_id_path.exists():
    raise SystemExit(f"STOP: missing {key_id_path}")
if not pem_path.exists():
    raise SystemExit(f"STOP: missing {pem_path}")

key_id = key_id_path.read_text(encoding="utf-8", errors="ignore").strip()
pem_text = pem_path.read_text(encoding="utf-8", errors="ignore")

if not key_id:
    raise SystemExit("STOP: key_id file is empty")

if not any(marker in pem_text for marker in (
    "BEGIN PRIVATE KEY",
    "BEGIN RSA PRIVATE KEY",
    "BEGIN EC PRIVATE KEY",
)):
    raise SystemExit("STOP: private_key.pem does not look like a PEM private key")

pem_b64 = base64.b64encode(pem_text.encode("utf-8")).decode("ascii")

OUT.write_text(
    f"KALSHI_KEY_ID={key_id}\n"
    f"KALSHI_PRIVATE_KEY_B64={pem_b64}\n",
    encoding="utf-8"
)
os.chmod(OUT, stat.S_IRUSR | stat.S_IWUSR)

exclude = Path(".git/info/exclude")
exclude.parent.mkdir(parents=True, exist_ok=True)
existing = exclude.read_text(encoding="utf-8", errors="ignore") if exclude.exists() else ""
if OUT.name not in existing.splitlines():
    with exclude.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(OUT.name + "\n")

print("=" * 72)
print("BTC15 RAILWAY SECRET BUNDLE V1.1")
print("=" * 72)
print("Created:", OUT.name)
print("Using private key:", pem_path.name)
print("Secret values were NOT printed to the terminal.")
print()
print("NEXT:")
print("1) Open RAILWAY_SECRETS_DO_NOT_COMMIT.env")
print("2) Copy ALL contents")
print("3) Railway > Variables > Raw Editor")
print("4) Paste and save/apply")
print("5) Delete the local .env file after Railway accepts it")
print("=" * 