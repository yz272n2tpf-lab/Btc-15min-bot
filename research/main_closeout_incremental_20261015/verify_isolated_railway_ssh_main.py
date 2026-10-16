"""BTC15 isolated Railway -> MAIN read-only SSH identity check.

Use exactly once in the existing isolated test service. First-contact server-key
pinning (TOFU) was explicitly approved by the owner. Never touch native files,
recorder configuration, markets, trading models, or volume data in production.
"""
import hashlib
import json
import os
from pathlib import Path
import shlex
import stat
import subprocess

ISOLATED = {
    "RAILWAY_PROJECT_ID": "87ad03d5-e1d6-47d6-b1ea-159cd7594686",
    "RAILWAY_ENVIRONMENT_ID": "12d241b7-23b4-4421-aafd-142e943555ee",
    "RAILWAY_SERVICE_ID": "1fff593b-8b09-4cc4-8c51-f9603082657f",
    "RAILWAY_VOLUME_ID": "2dba2ef6-b84d-4abf-9d04-58a1e77082c5",
    "RAILWAY_VOLUME_MOUNT_PATH": "/research-evidence",
}
MAIN = {
    "RAILWAY_PROJECT_ID": "baea4e22-d004-4434-b2c5-81a7fbc05086",
    "RAILWAY_ENVIRONMENT_ID": "61775c5d-c583-4dfc-af41-f25578856fd9",
    "RAILWAY_SERVICE_ID": "ab28dca6-7bea-4956-bdb9-dbb7b4c74635",
    "RAILWAY_VOLUME_ID": "6ced6b1a-3755-4518-a240-c895e936d443",
    "RAILWAY_VOLUME_MOUNT_PATH": "/data",
    "RAILWAY_GIT_COMMIT_SHA": "dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72",
}
GATEWAY = "ssh.railway.com"
DESTINATION = "btc-15min-bot-production.up.railway.app@" + GATEWAY
KEYDIR = Path("/research-evidence/ssh-identity")
KEY = KEYDIR / "btc15_early_isolated_transfer_ed25519"
KNOWN = KEYDIR / "railway_ssh_known_hosts"


def stop(reason, detail=""):
    print("BTC15_SSH_IDENTITY_TEST " + json.dumps(
        {"result": "BLOCKED", "reason": reason, "detail": detail[:380],
         "server_identity_verified": False, "native_ssh_identity_verified": False,
         "production_changes": False, "recording_started": False,
         "evidence_transferred": False, "orders": False}, sort_keys=True), flush=True)
    raise SystemExit(2)


def run(args, seconds=30):
    return subprocess.run(args, stdin=subprocess.DEVNULL, text=True,
                          capture_output=True, timeout=seconds, check=False)


def check_local():
    for key, value in ISOLATED.items():
        if os.getenv(key) != value:
            stop("ISOLATED_SERVICE_IDENTITY", key)
    if not KEYDIR.is_dir() or KEYDIR.is_symlink() or not KEY.is_file() or KEY.is_symlink():
        stop("ISOLATED_PRIVATE_KEY_NOT_FOUND")
    if (stat.S_IMODE(KEY.stat().st_mode) & 0o077) != 0:
        stop("INSECURE_PRIVATE_KEY_FILE_PERMISSIONS")
    if not Path("/research-evidence/early_capacity_probe_second_attempt/QUALIFICATION.json").is_file():
        stop("EXISTING_CAPACITY_RECEIPT_MISSING")


def scan_host():
    scans = []
    for attempt in range(2):
        try:
            x = run(["ssh-keyscan", "-T", "8", "-t", "ed25519", GATEWAY], 14)
        except subprocess.TimeoutExpired:
            stop("RAILWAY_SSH_KEYSCAN_TIMEOUT")
        entries = []
        for line in x.stdout.splitlines():
            parts = line.strip().split()
            if len(parts) >= 3 and parts[0] == GATEWAY and parts[1] == "ssh-ed25519":
                entries.append(" ".join(parts[:3]))
        entries = sorted(set(entries))
        if len(entries) != 1:
            stop("RAILWAY_SSH_SERVER_KEY_NOT_AVAILABLE",
                 "scan=" + str(attempt+1) + " exit=" + str(x.returncode)
                 + " stderr=" + x.stderr[:130])
        scans.append(entries[0])
    if scans[0] != scans[1]:
        stop("RAILWAY_SSH_SERVER_KEY_INCONSISTENT")
    key_line = scans[0]
    # Pin on first contact, reject subsequent changes without automatically
    # overwriting the trusted value.
    existed = KNOWN.exists()
    if existed:
        if KNOWN.is_symlink() or KNOWN.read_text().strip() != key_line:
            stop("PINNED_RAILWAY_SERVER_KEY_CHANGED")
    else:
        fd = os.open(KNOWN, os.O_WRONLY|os.O_CREAT|os.O_EXCL, 0o600)
        with os.fdopen(fd, "w") as dest:
            dest.write(key_line + "\n")
            dest.flush()
            os.fsync(dest.fileno())
    fingerprint = run(["ssh-keygen", "-lf", str(KNOWN)], 10)
    if fingerprint.returncode != 0:
        stop("RAILWAY_SSH_SERVER_KEY_FINGERPRINT_FAILED")
    print("BTC15_SSH_SERVER_FIRST_CONTACT " + json.dumps({
        "policy": "USER_AUTHORIZED_TRUST_ON_FIRST_USE",
        "host": GATEWAY, "host_key_type": "ssh-ed25519",
        "pin_reused": existed,
        "fingerprint": fingerprint.stdout.strip(),
        "key_material_disclosed": False}, sort_keys=True), flush=True)


def main():
    check_local()
    scan_host()
    # Remote Python reads only the six non-secret Railway identity fields.
    # No shell writes, file listing, API fetch, recorder stop, or env dump.
    remote = ("import os,json; keys=" + repr(tuple(MAIN)) +
              "; print('BTC15_REMOTE_IDENTITY '+json.dumps({k:os.environ.get(k) for k in keys},sort_keys=True))")
    cmd = [
        "ssh", "-T", "-oBatchMode=yes", "-oIdentitiesOnly=yes",
        "-oStrictHostKeyChecking=yes", "-oUserKnownHostsFile=" + str(KNOWN),
        "-oGlobalKnownHostsFile=/dev/null", "-oCheckHostIP=no",
        "-oConnectTimeout=10", "-oConnectionAttempts=1",
        "-oServerAliveInterval=5", "-oServerAliveCountMax=2",
        "-i", str(KEY), DESTINATION, "python -B -c " + shlex.quote(remote)
    ]
    try:
        result = run(cmd, 35)
    except subprocess.TimeoutExpired:
        stop("RAILWAY_SSH_MAIN_TIMEOUT")
    if result.returncode != 0:
        stop("RAILWAY_SSH_MAIN_CONNECT_FAILED",
             "exit=" + str(result.returncode) + " stderr=" + result.stderr[:300])
    identities = [line[len("BTC15_REMOTE_IDENTITY "):]
                  for line in result.stdout.splitlines() if line.startswith("BTC15_REMOTE_IDENTITY ")]
    if len(identities) != 1:
        stop("RAILWAY_MAIN_RESPONSE_IDENTITY_MISSING",
             "output_bytes=" + str(len(result.stdout)))
    try:
        observed = json.loads(identities[0])
    except json.JSONDecodeError:
        stop("RAILWAY_MAIN_RESPONSE_NOT_JSON")
    failed = [k for k,v in MAIN.items() if observed.get(k) != v]
    if failed:
        stop("RAILWAY_MAIN_SERVICE_IDENTITY_MISMATCH", ",".join(failed))
    print("BTC15_SSH_IDENTITY_TEST " + json.dumps({
        "result": "PASS", "source": "MAIN",
        "ssh_public_key_accepted": True, "pinned_host_key_verified": True,
        "native_ssh_identity_verified": True, "matched_fields": len(MAIN),
        "host_key_trust": "FIRST_CONTACT_PINNED",
        "production_changes": False, "recording_started": False,
        "evidence_transferred": False, "orders": False
    }, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()