"""Read-only operational readiness check for the already deployed EARLY recorder.

All work is in isolated Railway; remote MAIN/V81 commands only read non-secret
flag/config metadata, known Oct-13 recorder receipts and free-space counters.
No stop/seal operation, source modification, deployment, or trading action.
"""
import json
import shlex
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_main import (
    check_local, scan_host, run, stop, KNOWN, KEY, GATEWAY
)
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_transfer import PRODUCTION

def assess(name, domain, expected, role):
    raw = r"""
import hashlib,json,os,pathlib,shutil,time
from pathlib import Path
K = ("RAILWAY_PROJECT_ID","RAILWAY_ENVIRONMENT_ID","RAILWAY_SERVICE_ID","RAILWAY_VOLUME_ID","RAILWAY_VOLUME_MOUNT_PATH","RAILWAY_GIT_COMMIT_SHA")
flag = os.environ.get("BTC15_RECORDING_ENABLED")
cfg_path = os.environ.get("BTC15_RECORDING_CONFIG")
cfg_hash = os.environ.get("BTC15_RECORDING_CONFIG_SHA256")
cfg = None
reason = None
if cfg_path:
    p = Path(cfg_path)
    if p.is_file() and not p.is_symlink() and p.stat().st_size <= 65536:
        blob = p.read_bytes()
        if cfg_hash and hashlib.sha256(blob).hexdigest()==cfg_hash:
            try:cfg=json.loads(blob)
            except (json.JSONDecodeError,UnicodeError):reason="CONFIG_JSON_INVALID"
        else:reason="CONFIG_SHA_MISMATCH"
    else:reason="CONFIG_PATH_UNAVAILABLE_OR_OVERSIZE"
else:reason="CONFIG_PATH_NOT_SET"
out = dict(
    identity={key:os.environ.get(key) for key in K},
    enabled=flag=="1",enabled_variable_present=flag is not None,
    config_status=reason or "HASH_VERIFIED",
    configured_run_id=cfg.get("run_id") if isinstance(cfg,dict) else None,
    config_profile=cfg.get("profile") if isinstance(cfg,dict) else None,
    configured_duration_seconds=cfg.get("duration_seconds") if isinstance(cfg,dict) else None,
    capture_opt_in=cfg.get("capture_enabled") if isinstance(cfg,dict) else None,
    signal_only=cfg.get("signal_only") if isinstance(cfg,dict) else None,
    orders=cfg.get("orders") if isinstance(cfg,dict) else None,
    disk_free_bytes=shutil.disk_usage("/data").free,
    roles={}
)
for r in ("main","information","v81"):
    root=Path("/data/btc15_recordings/PF_20261013_4d0f8ed15e")/r
    if not root.is_dir() or root.is_symlink():continue
    z=dict()
    for fn in ("identity.json","health.json","terminal-status.json","seal.json"):
        p=root/fn
        z[fn+"_present"]=p.is_file() and not p.is_symlink()
        if not z[fn+"_present"] or p.stat().st_size>1048576:continue
        val=json.loads(p.read_bytes())
        if fn=="identity.json":
            z["identity_role"]=val.get("role");z["identity_mode"]=val.get("mode")
            z["identity_started"]=val.get("started")
        if fn=="health.json":
            z["health_age_seconds"]=round(time.time()-p.stat().st_mtime,1)
            z["health_admission"]=val.get("admission");z["health_stopped"]=val.get("stopped")
            z["health_records"]=val.get("records");z["health_failure"]=val.get("failure")
        if fn=="terminal-status.json":
            z["terminal_status"]=val.get("status");z["terminal_reason"]=val.get("reason")
            z["terminal_failure"]=val.get("failure");z["terminal_records"]=val.get("records")
        if fn=="seal.json":z["seal_status"]=val.get("status")
    out["roles"][r]=z
print("BTC15_LIVE_RECORDER_CHECK "+json.dumps(out,sort_keys=True))
"""
    command = [
        "ssh", "-T", "-oBatchMode=yes", "-oIdentitiesOnly=yes",
        "-oStrictHostKeyChecking=yes", "-oUserKnownHostsFile="+str(KNOWN),
        "-oGlobalKnownHostsFile=/dev/null", "-oCheckHostIP=no",
        "-oConnectTimeout=10", "-oConnectionAttempts=1",
        "-i",str(KEY),domain+"@"+GATEWAY,"python -B -c "+shlex.quote(raw)
    ]
    result=run(command,45)
    if result.returncode:
        stop(name+"_RECORDER_READ_ONLY_CHECK_FAILED",
             "exit="+str(result.returncode)+" stderr="+result.stderr[:260])
    match=[line[len("BTC15_LIVE_RECORDER_CHECK "):] for line in result.stdout.splitlines()
           if line.startswith("BTC15_LIVE_RECORDER_CHECK ")]
    if len(match)!=1:stop(name+"_RECORDER_CHECK_RESPONSE_MISSING")
    answer=json.loads(match[0])
    fail=[k for k,v in expected.items() if answer.get("identity",{}).get(k)!=v]
    if fail:stop(name+"_RECORDER_CHECK_REMOTE_IDENTITY_MISMATCH",",".join(fail))
    del answer["identity"]
    print("BTC15_LIVE_RECORDER_READINESS "+json.dumps(dict(service=name,**answer),sort_keys=True),flush=True)

def main():
    check_local()
    scan_host()
    for name,(domain,expected,role) in PRODUCTION.items():
        assess(name,domain,expected,role)

if __name__=="__main__":
    main()
