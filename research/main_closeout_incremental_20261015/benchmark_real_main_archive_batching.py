"""Benchmark the existing capture-only batching against immutable Oct-13 MAIN gzip.

This is a bounded real-evidence I/O measurement, NOT an EARLY validator.
Source V81 is read-only; only the separate Railway research volume is written.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import time

from ops.live_recording.burst_journal_research import BatchedEvidenceJournal
from btc15_information_journal_v1 import CompressedJournal
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_main import (
    check_local, scan_host, KEY, KNOWN, GATEWAY
)

DOMAIN = "btc-15min-bot-production.up.railway.app"
ROOT = "/data/btc15_recordings/PF_20261013_4d0f8ed15e/main/source.segments"
OUT = Path("/research-evidence/early_main_oct13_batch_benchmark_20261016")
MAX_FILES = 128
MAX_TOTAL = 48 * 1024 * 1024
MAX_FILE = 8 * 1024 * 1024

def remote_run(script, *, timeout=40):
    cmd = [
        "ssh", "-T", "-oBatchMode=yes", "-oIdentitiesOnly=yes",
        "-oStrictHostKeyChecking=yes",
        "-oUserKnownHostsFile=" + str(KNOWN),
        "-oGlobalKnownHostsFile=/dev/null", "-oCheckHostIP=no",
        "-oConnectTimeout=10", "-oConnectionAttempts=1",
        "-oServerAliveInterval=5", "-oServerAliveCountMax=2",
        "-i", str(KEY), DOMAIN + "@" + GATEWAY,
        "python -B -c " + shlex.quote(script)
    ]
    result = subprocess.run(cmd, input=b"",capture_output=True,timeout=timeout)
    if result.returncode:
        raise RuntimeError("ISOLATED_SSH_READ_FAILED exit="+str(result.returncode))
    return result.stdout

def inventory():
    remote = (
        "import os,json,hashlib,pathlib; "
        "r=pathlib.Path("+repr(ROOT)+"); "
        "assert r.is_dir() and not r.is_symlink(); "
        "fs=sorted(p for p in r.glob('*.jsonl.gz') if p.is_file() and not p.is_symlink()); "
        "assert len(fs)>0 and len(fs)<=128; "
        "total=sum(p.stat().st_size for p in fs); "
        "assert total<="+str(MAX_TOTAL)+"; "
        "out=[dict(name=p.name,size=p.stat().st_size,"
        "sha256=hashlib.sha256(p.read_bytes()).hexdigest()) for p in fs]; "
        "print(json.dumps(out,sort_keys=True))"
    )
    return json.loads(remote_run(remote,timeout=30))

def fetch_item(meta, destination):
    name = meta["name"]
    if (len(name)>140 or "/" in name or "\\\\" in name or name.startswith(".")
            or not name.endswith(".jsonl.gz")):
        raise ValueError("INVALID_SOURCE_NAME")
    root=ROOT
    script=(
        "import pathlib,sys; r=pathlib.Path("+repr(root)+");"
        "p=r/"+repr(name)+"; assert p.is_file() and not p.is_symlink() and p.resolve().is_relative_to(r.resolve());"
        "assert p.stat().st_size<="+str(MAX_FILE)+"; sys.stdout.buffer.write(p.read_bytes())"
    )
    raw=remote_run(script,timeout=45)
    if len(raw)!=meta["size"] or hashlib.sha256(raw).hexdigest()!=meta["sha256"]:
        raise ValueError("SOURCE_COPY_INTEGRITY_FAILURE")
    target=destination/name
    with target.open("xb") as f:
        f.write(raw)
        f.flush()
        os.fsync(f.fileno())

def run():
    check_local()
    scan_host()
    if OUT.exists():
        raise RuntimeError("BENCHMARK_OUTPUT_ALREADY_EXISTS")
    originals=inventory()
    if len(originals)>MAX_FILES or sum(x["size"] for x in originals)>MAX_TOTAL:
        raise ValueError("SOURCE_INVENTORY_BOUND")
    OUT.mkdir(mode=0o700)
    src=OUT/"original_immutable"
    src.mkdir(mode=0o700)
    for entry in originals:
        fetch_item(entry,src)
    again=inventory()
    if again!=originals:
        raise ValueError("SOURCE_CHANGED_DURING_COPY")

    compressed_original=sum(e["size"] for e in originals)
    all_raw_sha=hashlib.sha256()
    total_raw=total_records=0
    journal=BatchedEvidenceJournal(CompressedJournal(
        OUT/"batched_new_evidence_only",
        segment_bytes=8*1024*1024,
        max_total_bytes=48*1024*1024,
        max_record_bytes=5*1024*1024
    ))
    start=time.monotonic()
    for e in originals:
        with gzip.open(src/e["name"],"rb") as f:
            while True:
                line=f.readline(5*1024*1024+1)
                if not line:break
                if len(line)>5*1024*1024 or not line.endswith(b"\n"):
                    raise ValueError("INVALID_ORIGINAL_ENVELOPE")
                all_raw_sha.update(line)
                journal.append(line)
                total_raw+=len(line)
                total_records+=1
    journal.flush()
    elapsed=time.monotonic()-start
    if journal.records!=total_records:
        raise ValueError("BATCHED_RECORD_COUNT_MISMATCH")
    verify_sha=hashlib.sha256()
    verify_count=0
    newer=list(Path(str(OUT/"batched_new_evidence_only")+".segments").glob("*.jsonl.gz"))
    for file in newer:
        with gzip.open(file,"rb") as f:
            for line in f:
                verify_sha.update(line)
                verify_count+=1
    if verify_count!=total_records or verify_sha.digest()!=all_raw_sha.digest():
        raise ValueError("REPACKED_BYTES_NOT_IDENTICAL")
    if journal.evidence_batch_status()["buffered_records"]!=0:
        raise ValueError("UNCOMMITTED_BUFFER")
    original_sample_seconds=40.505378579720855
    batched_bytes=sum(x.stat().st_size for x in newer)
    observed_event_rate=total_records/original_sample_seconds
    projected_events_if_sustained=observed_event_rate*86940
    result={
        "schema":"BTC15_OCT13_MAIN_REAL_EVIDENCE_BATCH_BENCHMARK_V1",
        "scope":"IMMUTABLE_RECORDED_PREFLIGHT_ONLY_NOT_COMPLETE_LIVE_CAPTURE",
        "source_service":"MAIN", "source_files":len(originals),
        "source_original_gzip_bytes":compressed_original,
        "decoded_bytes":total_raw,
        "exact_original_records":total_records,
        "new_batched_gzip_bytes":batched_bytes,
        "batched_members":journal.evidence_batch_status()["committed_batches"],
        "gzip_ratio_vs_original":round(batched_bytes/compressed_original,4),
        "unchanged_decoded_stream_sha256":verify_sha.hexdigest(),
        "identical_original_bytes":True,
        "writer_wall_seconds":round(elapsed,3),
        "writer_envelopes_per_second":round(total_records/elapsed,2) if elapsed else None,
        "observed_original_record_rate_per_sec":round(observed_event_rate,1),
        "if_sustained_day_records":int(projected_events_if_sustained),
        "if_sustained_day_compressed_bytes":int(batched_bytes/original_sample_seconds*86940),
        "current_main_day_record_cap":3000000,
        "current_main_day_compressed_cap_bytes":1024*1024*1024,
        "unqualified":"ISOLATED_INCOMPLETE_OCT13_PRELIMINARY_BURST; NO_COMPLETE_LIVE_CAPTURE; NO_TRADED_EDGE_CLAIM",
        "production_changes":False,"orders":False,"codespaces_used":False
    }
    path=OUT/"BENCHMARK.json"
    with path.open("x") as f:
        json.dump(result,f,sort_keys=True)
        f.flush()
        os.fsync(f.fileno())
    print("BTC15_MAIN_REAL_EVIDENCE_BATCH_RESULT "+json.dumps(result,sort_keys=True),flush=True)

if __name__=="__main__":
    run()