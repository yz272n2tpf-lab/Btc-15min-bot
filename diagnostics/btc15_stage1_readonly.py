#!/usr/bin/env python3
"""Read-only BTC15 BRTI Stage 1 diagnostic. NO ORDERS, NO NETWORK POLLING.
Does not edit files, run the controller, restart services or consume permits.
Prints no credential values. For the existing DigitalOcean installation only.
"""
import ast
import hashlib
import os
import re
import stat
import subprocess
import sys
from pathlib import Path
from datetime import datetime, timezone

BASE=Path("/opt/btc15-pilot")
RUN=Path("/run/btc15-pilot")
ETC=Path("/etc/btc15-pilot")
SERVICES=("brti","brti-tls","main","v81","monitor")
USERS=("btc15-brti","btc15-brti-tls","btc15-main","btc15-v81")

def call(*args,timeout=15):
    try:
        r=subprocess.run(args,stdin=subprocess.DEVNULL,capture_output=True,
                         text=True,timeout=timeout)
        return r.returncode,r.stdout
    except (OSError,subprocess.TimeoutExpired):
        return 125,""

def out(key,val):
    print(f"{key}: {val}",flush=True)

def mode(path):
    try:
        s=Path(path).lstat()
        if stat.S_ISLNK(s.st_mode):return "SYMLINK_REVIEW"
        return f"mode={stat.S_IMODE(s.st_mode):04o} uid={s.st_uid} gid={s.st_gid}"
    except (OSError,ValueError):
        return "MISSING_OR_UNREADABLE"

def services():
    for name in SERVICES:
        unit=f"btc15-pilot-{name}.service"
        rc,t=call("systemctl","show",unit,
                  "--property=LoadState,ActiveState,SubState,Result,MainPID,User",
                  "--no-pager")
        d=dict(l.split("=",1) for l in t.splitlines() if "=" in l)
        out("UNIT_"+name.upper().replace("-","_"),
            " ".join(f"{k}={d.get(k,'?')}" for k in
                     ("LoadState","ActiveState","SubState","Result","MainPID","User"))
            if rc==0 else "UNAVAILABLE")

def access():
    for p in (RUN,RUN/"session.json",RUN/"stopped.json",
              ETC/"authorized-release.json",ETC/"pilot-permit.json"):
        out("PATH_"+p.name,mode(p))
    for user in USERS:
        for p in (RUN/"session.json",ETC/"authorized-release.json",
                  ETC/"pilot-permit.json"):
            rc,_=call("runuser","-u",user,"--","test","-r",str(p))
            out("ACCESS_"+user+"_"+p.name,"YES" if rc==0 else "NO_OR_UNKNOWN")
    for user,p in (("btc15-main",ETC/"main.env"),
                   ("btc15-v81",ETC/"v81.env")):
        rc,_=call("runuser","-u",user,"--","test","-r",str(p))
        out("CONFIG_"+user,"READABLE" if rc==0 else "DENIED")
    owner=Path("/run/btc15-pilot-brti/owner-started.json")
    out("OWNER_STARTED_MARKER",mode(owner))
    out("OWNER_LOCK",mode("/var/lib/btc15-pilot/brti/owner.lock"))
    rc,t=call("systemctl","show","btc15-pilot-brti.service",
              "--property=RuntimeDirectoryPreserve,ActiveState,MainPID")
    out("OWNER_RUNTIME_POLICY"," ".join(t.strip().splitlines()) if rc==0 else "UNKNOWN")

def certs():
    for name in ("tls/ca.crt","tls/server.crt","tls/main.crt",
                 "tls/v81.crt","health/brti-client.crt"):
        p=ETC/name
        if not p.is_file() or p.is_symlink():label="MISSING_OR_SYMLINK"
        else:
            rc,_=call("openssl","x509","-noout","-checkend","7200",
                      "-in",str(p))
            label="VALID_NEXT_2H" if rc==0 else "EXPIRED_OR_INVALID"
        out("CERT_"+name.replace("/", "_"),label)

def source():
    files=("kit/tools/control.py","kit/tools/brti_health.py",
           "kit/tools/brti_owner.py","kit/tools/brti_tls.py",
           "release/owner/brti_shared_feed_v1.py",
           "release/candidate/main/btc15_brti_shared_consumer_v1.py")
    for rel in files:
        p=BASE/rel
        try:
            if p.is_symlink():raise ValueError("SYMLINK")
            raw=p.read_bytes()
            ast.parse(raw,filename=str(p))
            out("SOURCE_"+p.name,"SYNTAX_OK SHA256="+hashlib.sha256(raw).hexdigest()[:16])
        except (OSError,SyntaxError,ValueError):
            out("SOURCE_"+p.name,"MISSING_OR_INVALID")

def logs():
    args=["journalctl","--since","2026-10-30 01:28:00 UTC",
          "--until","2026-10-30 01:31:00 UTC","--no-pager","-o","cat"]
    for name in SERVICES:args.extend(["-u",f"btc15-pilot-{name}.service"])
    rc,text=call(*args,timeout=25)
    if rc!=0:
        out("OLD_LOGS","UNAVAILABLE");return
    patterns={
        "BRTI_FEED_STARTED":r"BRTI SHARED FEED V1 START",
        "FEED_HEARTBEATS":r"BRTI_SHARED HEARTBEAT",
        "OWNER_REFUSED":r"BRTI_START_REFUSED:",
        "TLS_REFUSED":r"TLS_START_REFUSED:",
        "MAIN_V81_STARTED":r"Started btc15-pilot-(?:main|v81)\.service",
        "HTTP_429_REPORTED":r"(?:HTTP_429|http_429=|rate.limit.exceeded)",
    }
    out("OLD_LOG_LINES",len(text.splitlines()))
    for key,pattern in patterns.items():
        out(key,len(re.findall(pattern,text,re.IGNORECASE)))
    out("OLD_LOG_LIMITATION","Upstream error cause not logged in this window")
    # Deliberately do not echo raw journal text or potentially private URLs.

def main():
    out("AUDIT","BTC15_STAGE1_READONLY_20261029")
    out("UTC",datetime.now(timezone.utc).isoformat())
    if os.geteuid()!=0 or not BASE.is_dir():
        out("HOLD","ROOT_OR_EXISTING_INSTALL_REQUIRED_NO_ACTION");return 2
    rc,text=call("timedatectl","show","--property=NTPSynchronized","--value")
    out("NTP",text.strip() if rc==0 else "UNKNOWN")
    services();access();certs();source();logs()
    out("COMPLETE","READ_ONLY_NO_KALSHI_REQUESTS_NO_ORDERS")
    out("LIMIT","LIVE_BRTI_FRESHNESS_STILL_NOT_PROVEN")
    return 0

if __name__=="__main__":
    sys.exit(main())
