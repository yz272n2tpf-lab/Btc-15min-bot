#!/usr/bin/env python3
from pathlib import Path
import base64
import os
import stat

kdir = Path.home() / ".kalshi"
key_id_path = kdir / "key_id"
private_path = kdir / "private_key.pem"
out = Path("RAILWAY_SECRETS_COPY_ME.txt")

if not key_id_path.exists():
    raise SystemExit("STOP: ~/.kalshi/key_id not found")
if not private_path.exists():
    raise SystemExit("STOP: ~/.kalshi/private_key.pem not found")

key_id = key_id_path.read_text(encoding="utf-8", errors="ignore").strip()
private_bytes = private_path.read_bytes()

if not key_id:
    raise SystemExit("STOP: key_id is empty")
if b"PRIVATE KEY" not in private_bytes:
    raise SystemExit("STOP: private_key.pem does not look like a private key")

pem_b64 = base64.b64encode(private_bytes).decode("ascii")

out.write_text(
    f"KALSHI_KEY_ID={key_id}\n"
    f"KALSHI_PRIVATE_KEY_B64={pem_b64}\n",
    encoding="utf-8",
)
os.chmod(out, stat.S_IRUSR | stat.S_IWUSR)

exclude = Path(".git/info/exclude")
exclude.parent.mkdir(parents=True, exist_ok=True)
existing = exclude.read_text(encoding="utf-8", errors="ignore") if exclude.exists() else ""
if out.name not in existing.splitlines():
    with exclude.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(out.name + "\n")

print("PASS: Railway secret copy file created.")
print("OPEN/DOWNLOAD: RAILWAY_SECRETS_COPY_ME.txt")
print("Secret values were NOT printed.")
