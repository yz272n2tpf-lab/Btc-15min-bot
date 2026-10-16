"""Research-only native-sample index footprint measurement with existing indexer.

Uses immutable verified benchmark copies on isolated Railway. No external input
collection or strategy evaluation; not a new validator. Source/proof gaps do
not become PASS. Temporary index outputs stay on the isolated volume.
"""
import hashlib
import json
import os
from pathlib import Path
import shutil
import time
from ops.recording_workflow.evidence import index_run

BASE=Path("/research-evidence")
SAMPLES={
    "MAIN":BASE/"early_main_oct13_batch_benchmark_20261016",
    "V81":BASE/"early_v81_oct13_batch_benchmark_20261016",
}
WORK=BASE/"native_sample_index_footprint_20261016"
MAX_FILE=10*1024*1024
MAX_TOTAL=64*1024*1024

def sha(path):
    h=hashlib.sha256()
    with path.open("rb") as f:
        for b in iter(lambda:f.read(1024*1024),b""):h.update(b)
    return h.hexdigest()

def main():
    ids={
        "RAILWAY_PROJECT_ID":"87ad03d5-e1d6-47d6-b1ea-159cd7594686",
        "RAILWAY_ENVIRONMENT_ID":"12d241b7-23b4-4421-aafd-142e943555ee",
        "RAILWAY_SERVICE_ID":"1fff593b-8b09-4cc4-8c51-f9603082657f",
        "RAILWAY_VOLUME_ID":"2dba2ef6-b84d-4abf-9d04-58a1e77082c5",
        "RAILWAY_VOLUME_MOUNT_PATH":"/research-evidence",
    }
    if any(os.getenv(k)!=v for k,v in ids.items()):
        raise RuntimeError("ISOLATED_IDENTITY_MISMATCH")
    if WORK.exists():raise RuntimeError("INDEX_MEASUREMENT_ALREADY_EXISTS")
    if shutil.disk_usage(BASE).free<10*1024**3:
        raise RuntimeError("INSUFFICIENT_ISOLATED_RESERVE")
    WORK.mkdir(mode=0o700)
    outputs={}
    for role,root in SAMPLES.items():
        original=root/"original_immutable"
        if not original.is_dir() or original.is_symlink():
            raise RuntimeError("ORIGINAL_SOURCE_UNAVAILABLE:"+role)
        segments=sorted(original.glob("*.jsonl.gz"))
        if not 1<=len(segments)<=128 or any(x.is_symlink() for x in segments):
            raise RuntimeError("ORIGINAL_FILE_INVENTORY:"+role)
        if sum(x.stat().st_size for x in segments)>MAX_TOTAL or any(x.stat().st_size>MAX_FILE for x in segments):
            raise RuntimeError("ORIGINAL_SIZE_BOUND:"+role)
        dest=WORK/role
        (dest/"run"/"source.segments").mkdir(parents=True,mode=0o700)
        for file in segments:
            copy=dest/"run"/"source.segments"/file.name
            shutil.copyfile(file,copy)
            if sha(file)!=sha(copy):raise RuntimeError("INPUT_HASH_DRIFT:"+role)
        began=time.monotonic()
        idx=index_run(dest/"run",dest/"index",profile="day")
        elapsed=time.monotonic()-began
        rows=sum(idx["counts"].values())
        size=(dest/"index"/"index.sqlite3").stat().st_size
        outputs[role]={
            "record_count":rows,"file_count":len(idx["files"]),
            "index_bytes":size,"index_bytes_per_record":round(size/rows,3) if rows else None,
            "index_elapsed_seconds":round(elapsed,3),
            "reported_gap_count":len(idx.get("gaps",[])),
            "gap_labels":sorted(set(x.get("reason") for x in idx.get("gaps",[]))),
            "index_sha256_verified":sha(dest/"index"/"index.sqlite3")==idx["index_sha256"],
        }
        print("BTC15_NATIVE_INDEX_MEASUREMENT "+json.dumps({"role":role,**outputs[role]},sort_keys=True),flush=True)
    data={
        "schema":"BTC15_REAL_NATIVE_PRELIMINARY_INDEX_FOOTPRINT_V1",
        "samples":outputs,"authentic_complete":False,
        "existing_indexer_used":True,"original_data_mutated":False,
        "no_new_validator":True,"orders":False,
        "capacity_proven_24h":False
    }
    (WORK/"INDEX_MEASUREMENTS.json").write_text(json.dumps(data,sort_keys=True))
    print("BTC15_NATIVE_INDEX_SUMMARY "+json.dumps(data,sort_keys=True),flush=True)
if __name__=="__main__":main()
