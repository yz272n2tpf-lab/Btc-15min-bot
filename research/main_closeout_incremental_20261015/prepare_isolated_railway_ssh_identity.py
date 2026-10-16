"""One-time isolated Railway SSH public-key preparation. No network or production writes.

Only the public key is printed. The private key remains on the dedicated,
non-production evidence volume, owned by the isolated service. Registering
this key with Railway is a SEPARATE user decision and may grant account-wide
SSH access. Nothing here starts authentic capture or any trading service.
"""
import hashlib
import json
import os
from pathlib import Path
import stat
import subprocess

PROJECT = "87ad03d5-e1d6-47d6-b1ea-159cd7594686"
ENVIRONMENT = "12d241b7-23b4-4421-aafd-142e943555ee"
SERVICE = "1fff593b-8b09-4cc4-8c51-f9603082657f"
VOLUME = "2dba2ef6-b84d-4abf-9d04-58a1e77082c5"
MOUNT = Path("/research-evidence")
NAME = "btc15_early_isolated_transfer_ed25519"


def main():
    expected = {
        "RAILWAY_PROJECT_ID": PROJECT,
        "RAILWAY_ENVIRONMENT_ID": ENVIRONMENT,
        "RAILWAY_SERVICE_ID": SERVICE,
        "RAILWAY_VOLUME_ID": VOLUME,
        "RAILWAY_VOLUME_MOUNT_PATH": str(MOUNT),
    }
    if any(os.environ.get(k) != v for k, v in expected.items()):
        raise RuntimeError("ISOLATED_RAILWAY_IDENTITY_REQUIRED")
    if not MOUNT.is_dir() or MOUNT.is_symlink():
        raise RuntimeError("DEDICATED_VOLUME_MISSING")
    if not (MOUNT / "early_capacity_probe_second_attempt" / "QUALIFICATION.json").is_file():
        raise RuntimeError("QUALIFICATION_EVIDENCE_MISSING")
    os.umask(0o077)
    root = MOUNT / "ssh-identity"
    if root.is_symlink():
        raise RuntimeError("IDENTITY_DIRECTORY_SYMLINK")
    root.mkdir(mode=0o700, exist_ok=True)
    root.chmod(0o700)
    private = root / NAME
    public = root / (NAME + ".pub")
    if private.is_symlink() or public.is_symlink():
        raise RuntimeError("IDENTITY_FILE_SYMLINK")
    if private.exists() != public.exists():
        raise RuntimeError("INCOMPLETE_IDENTITY_STOP")
    if not private.exists():
        subprocess.run([
            "ssh-keygen", "-q", "-t", "ed25519", "-N", "",
            "-C", "btc15-early-evidence-railway-20261016",
            "-f", str(private)
        ], check=True, timeout=30)
    if not private.is_file() or not public.is_file():
        raise RuntimeError("SSH_KEY_CREATION_FAILED")
    private.chmod(0o600)
    public.chmod(0o600)
    if stat.S_IMODE(private.stat().st_mode) != 0o600:
        raise RuntimeError("SSH_PRIVATE_KEY_PERMISSIONS")
    text = public.read_text().strip()
    if not text.startswith("ssh-ed25519 ") or len(text) > 900:
        raise RuntimeError("SSH_PUBLIC_KEY_FORMAT")
    result = subprocess.run(
        ["ssh-keygen", "-lf", str(public)], check=True,
        capture_output=True, text=True, timeout=15
    )
    print("BTC15_ISOLATED_SSH_PUBLIC_KEY " + text, flush=True)
    print("BTC15_ISOLATED_SSH_FINGERPRINT " + result.stdout.strip(), flush=True)
    print("BTC15_ISOLATED_SSH_READINESS " + json.dumps({
        "schema": "BTC15_ISOLATED_SSH_KEY_READY_V1",
        "isolated_project_verified": True,
        "private_key_stored_on_isolated_volume": True,
        "private_key_contents_printed": False,
        "public_key_sha256": hashlib.sha256(text.encode()).hexdigest(),
        "registered_with_railway": False,
        "ssh_host_trusted": False,
        "authentic_source_transfer_attempted": False,
        "production_change": False,
        "recording_campaign_started": False,
        "volume_data_preserved": True
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
