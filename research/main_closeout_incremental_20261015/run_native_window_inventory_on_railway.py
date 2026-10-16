"""Measure new bounded streaming reader stage on preserved native MAIN/V81 files.

This calls the EXISTING ops.recording_workflow.evidence module. It does not
execute strategies, certify quote/settlement associations, or start recording.
Original archives, previously measured full SQLite indexes and failed role
seals remain immutable. All work stays in isolated Railway.
"""
import hashlib
import json
import os
from pathlib import Path
import resource
import shutil
import time

from ops.recording_workflow.evidence import streaming_window_inventory,file_sha

ROOT=Path('/research-evidence')
TARGET=ROOT/'native_sample_window_inventory_20261016'
SOURCES={
    'MAIN':ROOT/'early_main_oct13_batch_benchmark_20261016',
    'V81':ROOT/'early_v81_oct13_batch_benchmark_20261016',
}
EXPECTED_RECORDS={'MAIN':2942,'V81':26484}
EXPECTED_ORIGINAL_HASHES={
    'MAIN':'27f425257292ef1a5329b814eaf784adb708a9c7af275c15881ffe1da2be73d4',
    'V81':'391c4810cc3f4c7828aa1132781084a6b6f22ecef11ee01810bef60622d8b382'
}

def run():
    expected={
      'RAILWAY_PROJECT_ID':'87ad03d5-e1d6-47d6-b1ea-159cd7594686',
      'RAILWAY_ENVIRONMENT_ID':'12d241b7-23b4-4421-aafd-142e943555ee',
      'RAILWAY_SERVICE_ID':'1fff593b-8b09-4cc4-8c51-f9603082657f',
      'RAILWAY_VOLUME_ID':'2dba2ef6-b84d-4abf-9d04-58a1e77082c5',
      'RAILWAY_VOLUME_MOUNT_PATH':'/research-evidence'
    }
    if any(os.getenv(k)!=v for k,v in expected.items()):raise RuntimeError('ISOLATED_RAILWAY_IDENTITY')
    if TARGET.exists():raise RuntimeError('EXISTING_INVENTORY_OUTPUT_NO_OVERWRITE')
    if shutil.disk_usage(ROOT).free<8*1024**3:raise RuntimeError('READER_SPACE_RESERVE')
    TARGET.mkdir(mode=0o700)
    results={}
    for role,source in SOURCES.items():
        files=sorted((source/'original_immutable').glob('*.jsonl.gz'))
        if not 1<=len(files)<=128:raise RuntimeError('MISSING_OR_OVERSIZE_SOURCE_LIST')
        if sum(p.stat().st_size for p in files)>64*1024**2:raise RuntimeError('SOURCE_COPY_TOO_LARGE')
        assert all(p.is_file() and not p.is_symlink() for p in files)
        dest=TARGET/role/'input'/'source.segments'
        dest.mkdir(parents=True,mode=0o700)
        for p in files:
            copy=dest/p.name
            with p.open('rb') as original,copy.open('xb') as to:
                for block in iter(lambda:original.read(1024**2),b''):
                    to.write(block)
            if file_sha(copy)!=file_sha(p):raise RuntimeError('SOURCE_HASH_DRIFT')
        beg=time.monotonic()
        report=streaming_window_inventory(TARGET/role/'input',TARGET/role/'windowed',
                                           window_seconds=900,max_window_bytes=8*1024**2,
                                           max_window_records=20000)
        elapsed=time.monotonic()-beg
        if report['record_count']!=EXPECTED_RECORDS[role]:
            raise RuntimeError('READER_TOTAL_COUNT_MISMATCH:'+role)
        if report['structural_integrity']!='PASS':
            raise RuntimeError('READER_STRUCTURE_FAIL:'+role)
        if report['complete_market_evidence'] or report['early_strategy_qualified']:
            raise RuntimeError('UNAUTHORIZED_EARLY_QUALIFICATION')
        report_min=dict(
            role=role,structural_integrity=report['structural_integrity'],
            record_count=report['record_count'],source_file_count=report['source_file_count'],
            decoded_bytes=report['decoded_bytes'],window_count=report['windows'],
            max_window_records=report['max_window_observed_records'],
            max_window_bytes=report['max_window_observed_bytes'],
            manifest_bytes=report['windows_manifest_bytes'],
            manifest_sha256=report['windows_manifest_sha256'],
            unclocked_records=report['unclocked_records'],
            clock_regressions=report['clock_regressions'],
            original_capture_gaps=report['loss_indicators'],
            original_capture_complete=False,
            early_qualified=False,
            cpu_wall_seconds=round(elapsed,3),
            process_max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
            per_record_sqlite_index_created=False
        )
        results[role]=report_min
        print('BTC15_REAL_WINDOWED_INDEX_RESULT '+json.dumps(report_min,sort_keys=True),flush=True)
    manifest=dict(schema='BTC15_NATIVE_WINDOWED_READER_STAGE_RESEARCH_V1',
                  status='PASS_STRUCTURAL_WINDOWS_ONLY',measurements=results,
                  full_lifecycle_reader_qualified=False,actual_24h_capture_started=False,
                  native_original_capture_gap_free=False,
                  note='The original existing CampaignVerifier still needs contract-specific bounded state handoff',
                  production_modified=False,orders=False,codespaces_used=False)
    (TARGET/'STAGE_RESULTS.json').write_text(json.dumps(manifest,sort_keys=True))
    print('BTC15_REAL_WINDOWED_INDEX_SUMMARY '+json.dumps(manifest,sort_keys=True),flush=True)

if __name__=='__main__':run()
