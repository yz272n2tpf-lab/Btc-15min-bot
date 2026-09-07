#!/usr/bin/env python3
from pathlib import Path
import base64
import os
import stat

HOME = Path.home()
KDIR = HOME / ".kalshi"
OUT = Path("RAILWAY_SECRETS_DO_NOT_COMMIT.env")

key_id_path = KDIR / "key_id"
if not key_id_path.exists():
    raise SystemExit(f"STOP: missing {key_id_path}")

key_id = key_id_path.read_text(encoding="utf-8", errors="ignore").strip()
if not key_id:
    raise SystemExit("STOP: key_id file is empty")

# Find the private key file without guessing its exact filename.
candidates = []
for p in KDIR.iterdir():
    if not p.is_file() or p.name == "key_id":
        continue
    try:
        txt = p.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        continue
    if "BEGIN PRIVATE KEY" in txt or "BEGIN RSA PRIVATE KEY" in txt or "BEGIN EC PRIVATE KEY" in txt:
        candidates.append((p, txt))

if len(candidates) == 0:
    raise SystemExit("STOP: could not find a PEM private key in ~/.kalshi")
if len(candidates) > 1:
    print("STOP: more than one PEM private key found in ~/.kalshi:")
    for p, _ in candidates:
        print(" -", p.name)
    print("No secrets file was created.")
    raise SystemExit(2)

pem_path, pem_text = candidates[0]
pem_b64 = base64.b64encode(pem_text.encode("utf-8")).decode("ascii")

OUT.write_text(
    f"KALSHI_KEY_ID={key_id}\n"
    f"KALSHI_PRIVATE_KEY_B64={pem_b64}\n",
    encoding="utf-8"
)
os.chmod(OUT, stat.S_IRUSR | stat.S_IWUSR)

# Keep this local secret bundle out of normal git status/commits.
exclude = Path(".git/info/exclude")
exclude.parent.mkdir(parents=True, exist_ok=True)
existing = exclude.read_text(encoding="utf-8", errors="ignore") if exclude.exists() else ""
entry = OUT.name
if entry not in existing.splitlines():
    with exclude.open("a", encoding="utf-8") as f:
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(entry + "\n")

print("=" * 72)
print("BTC15 RAILWAY SECRET BUNDLE")
print("=" * 72)
print("Created:", OUT.name)
print("Key ID chars:", len(key_id))
print("Private key source:", pem_path.name)
print("Private key B64 chars:", len(pem_b64))
print("Secret values were NOT printed to the terminal.")
print()
print("NEXT:")
print("1) Open RAILWAY_SECRETS_DO_NOT_COMMIT.env in the editor.")
print("2) Copy ALL of its contents.")
print("3) In Railway > Variables > Raw Editor, paste it.")
print("4) Apply/save the variables.")
print("5) Delete this local file after Railway accepts them.")
print("=" * 72)
