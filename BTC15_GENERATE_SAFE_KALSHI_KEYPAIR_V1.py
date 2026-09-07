#!/usr/bin/env python3
from pathlib import Path
import os
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.hazmat.primitives import serialization

home = Path.home()
kdir = home / ".kalshi"
kdir.mkdir(parents=True, exist_ok=True)
os.chmod(kdir, 0o700)

private_path = kdir / "private_key.pem"
public_path = Path("KALSHI_PUBLIC_KEY_TO_PASTE.pem")

key = rsa.generate_private_key(public_exponent=65537, key_size=2048)

private_bytes = key.private_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PrivateFormat.TraditionalOpenSSL,
    encryption_algorithm=serialization.NoEncryption(),
)
public_bytes = key.public_key().public_bytes(
    encoding=serialization.Encoding.PEM,
    format=serialization.PublicFormat.SubjectPublicKeyInfo,
)

private_path.write_bytes(private_bytes)
os.chmod(private_path, 0o600)
public_path.write_bytes(public_bytes)

for leftover in [Path("Tool 2.txt"), Path("RAILWAY_SECRETS_DO_NOT_COMMIT.env")]:
    if leftover.exists():
        leftover.unlink()

print("PASS: new private key generated safely in ~/.kalshi/private_key.pem")
print("PASS: public key created as KALSHI_PUBLIC_KEY_TO_PASTE.pem")
print("PASS: old temporary secret files removed if present")
print("NEXT: open ONLY KALSHI_PUBLIC_KEY_TO_PASTE.pem and copy it into Kalshi")
