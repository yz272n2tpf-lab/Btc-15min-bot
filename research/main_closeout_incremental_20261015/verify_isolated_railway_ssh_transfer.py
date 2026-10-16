"""Read-only SSH source identification and <=64KiB sample transfer from MAIN/V81.

Source services are never modified; this may only run in the isolated Railway
probe service with the previously pinned Railway SSH host key and registered
user-approved key. The original 24h evidence finisher is NOT invoked.
"""
import base64
import hashlib
import json
import os
from pathlib import Path
import shlex

from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_main import (
    check_local, scan_host, run, stop, MAIN, KEY, KNOWN, GATEWAY
)

PRODUCTION = {
    "MAIN": (
        "btc-15min-bot-production.up.railway.app",
        MAIN,
        "main",
    ),
    "V81": (
        "v81-live-diagnostics-production.up.railway.app",
        {
            "RAILWAY_PROJECT_ID": "baea4e22-d004-4434-b2c5-81a7fbc05086",
            "RAILWAY_ENVIRONMENT_ID": "61775c5d-c583-4dfc-af41-f25578856fd9",
            "RAILWAY_SERVICE_ID": "6025e83e-a41c-4e0a-8c16-f71120bd501b",
            "RAILWAY_VOLUME_ID": "d5eeafca-e0fc-42f0-b7d1-4705907720c6",
            "RAILWAY_VOLUME_MOUNT_PATH": "/data",
            "RAILWAY_GIT_COMMIT_SHA": "c14b3f9b04caea13e62bcdd6fb0e5990049aa17b",
        },
        "v81",
    ),
}
RUN_ID = "PF_20261013_4d0f8ed15e"
OUT = Path("/research-evidence/ssh-transfer-smoke-20261016")


def smoke_one(name, domain, expected, role):
    path = "/data/btc15_recordings/" + RUN_ID + "/" + role + "/identity.json"
    # The bounded payload is transported only in SSH stdout over the authenticated
    # session. It is never printed in the Railway logs or exposed via an endpoint.
    remote = (
        "import os,json,pathlib,hashlib,base64; "
        + "k=" + repr(tuple(expected)) + "; "
        + "p=pathlib.Path(" + repr(path) + "); "
        + "ok=p.is_file() and not p.is_symlink() and p.stat().st_size<=65536; "
        + "b=p.read_bytes() if ok else b''; "
        + "print('BTC15_REMOTE_SOURCE_PROBE '+json.dumps({"
        + "'environment':{x:os.environ.get(x) for x in k},"
        + "'file_present':ok,'file_len':len(b),"
        + "'file_sha256':hashlib.sha256(b).hexdigest() if ok else None,"
        + "'file_b64':base64.b64encode(b).decode() if ok else None"
        + "},sort_keys=True))"
    )
    target = domain + "@" + GATEWAY
    command = [
        "ssh", "-T", "-oBatchMode=yes", "-oIdentitiesOnly=yes",
        "-oStrictHostKeyChecking=yes", "-oUserKnownHostsFile=" + str(KNOWN),
        "-oGlobalKnownHostsFile=/dev/null", "-oCheckHostIP=no",
        "-oConnectTimeout=10", "-oConnectionAttempts=1",
        "-oServerAliveInterval=5", "-oServerAliveCountMax=2",
        "-i", str(KEY), target, "python -B -c " + shlex.quote(remote)
    ]
    x = run(command, 40)
    if x.returncode != 0:
        stop("SSH_" + name + "_CONNECTION_FAILED",
             "exit=" + str(x.returncode) + " stderr=" + x.stderr[:220])
    rows = [line[len("BTC15_REMOTE_SOURCE_PROBE "):]
            for line in x.stdout.splitlines() if line.startswith("BTC15_REMOTE_SOURCE_PROBE ")]
    if len(rows) != 1:
        stop("SSH_" + name + "_RESPONSE_MISSING")
    try:
        data = json.loads(rows[0])
    except json.JSONDecodeError:
        stop("SSH_" + name + "_RESPONSE_INVALID")
    failed = [k for k,v in expected.items() if data["environment"].get(k) != v]
    if failed:
        stop("SSH_" + name + "_IDENTITY_MISMATCH", ",".join(failed))
    result = {"service": name, "service_identity": "PASS",
              "matched_fields": len(expected), "sample_path": path,
              "existing_oct13_capture_file": bool(data["file_present"]),
              "sample_byte_count": 0, "verified_remote_to_isolated_transfer": False}
    if data["file_present"]:
        b = base64.b64decode(data["file_b64"],validate=True)
        if len(b) != data["file_len"] or hashlib.sha256(b).hexdigest() != data["file_sha256"]:
            stop("SSH_" + name + "_TRANSFER_INTEGRITY")
        obj = json.loads(b)
        if obj.get("schema") != "BTC15_CAPTURE_IDENTITY_V1" or obj.get("role") != role:
            stop("SSH_" + name + "_CAPTURE_IDENTITY_SCHEMA")
        if not OUT.exists(): OUT.mkdir(mode=0o700)
        if OUT.is_symlink():stop("SSH_TRANSFER_DESTINATION_SYMLINK")
        dest = OUT / (name.lower() + "_identity.json")
        if dest.exists():
            if dest.is_symlink() or hashlib.sha256(dest.read_bytes()).digest() != hashlib.sha256(b).digest():
                stop("SSH_" + name + "_DESTINATION_CONFLICT")
        else:
            fd = os.open(dest,os.O_WRONLY|os.O_CREAT|os.O_EXCL,0o600)
            with os.fdopen(fd,"wb") as f:
                f.write(b);f.flush();os.fsync(f.fileno())
        result.update(sample_byte_count=len(b),
                      file_sha256=data["file_sha256"],
                      verified_remote_to_isolated_transfer=True,
                      existing_capture_mode=obj.get("mode"))
    print("BTC15_SSH_SOURCE_RESULT " + json.dumps(result,sort_keys=True),flush=True)
    return result


def main():
    check_local()
    scan_host()  # Requires the prior pinned value to still match.
    results=[]
    for name, (domain, expected, role) in PRODUCTION.items():
        results.append(smoke_one(name,domain,expected,role))
    print("BTC15_SSH_TRANSFER_SUMMARY " + json.dumps({
        "result":"PASS" if all(x["service_identity"]=="PASS" for x in results) else "FAIL",
        "services_verified":len(results),
        "samples_transferred":sum(x["verified_remote_to_isolated_transfer"] for x in results),
        "recording_started":False,"production_changes":False,
        "historical_evidence_untouched":True,"codespaces_used":False,"orders":False
    },sort_keys=True),flush=True)

if __name__ == "__main__":
    main()
