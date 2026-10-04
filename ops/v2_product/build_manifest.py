"""Offline release inventory. Commit/bundle hashes are external to avoid self-reference."""
import hashlib
import json
import subprocess
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]

def build():
    files=[*ROOT.glob('btc15_v2_product/*.py'),*ROOT.glob('btc15_v2_product/*.js'),
           ROOT/'btc15_v2_native.py',ROOT/'btc15_v2_launch.py',ROOT/'btc15_cohort_evidence_v1.py',
           *ROOT.glob('ops/btc15_v2_scoring/*.py')]
    pins={'main':'de4f3e20b8657eb8cfee91bd4e525c103b5bf513','v81':'60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1'}
    shared=['btc15_kalshi_quote_provenance_v1.py','btc15_brti_shared_consumer_v1.py','requirements.txt']
    main=['bot_two_output_build_v4_13_profit_protection_shadow.py','completion_audit/fair_input_candidate.py',
          'completion_audit/model_artifact/frozen_fair_candidate.joblib','completion_audit/frozen_model_artifact.py','btc15_decision_clock_v1.py',
          'kalshi_scalp_shadow_events_v1.csv']
    protected={lane:{name:hashlib.sha256(subprocess.check_output(['git','show',commit+':'+name],cwd=ROOT)).hexdigest()
                    for name in shared+(main if lane=='main' else [])} for lane,commit in pins.items()}
    manifest=dict(schema='BTC15_V2_PRODUCT_RELEASE_R1',revision='BTC15_V2_PRODUCT_20261004_R1',
        strategy='BTC15_LADDER_COMPLETION_20261003_V2',frozen_main='de4f3e20b8657eb8cfee91bd4e525c103b5bf513',
        frozen_v81='60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1',
        bridge_base='1d942014af22ab4acb3048a29dbbc831d5ecc924',live_handoff='61b3b4ddb3a816559355802ddd8dba27abfcdf00',
        signal_only=True,manual_execution_only=True,orders=False,
        frozen_files='Original lane-specific freeze manifest and verifier remain byte-identical and mandatory',
        files_sha256={str(p.relative_to(ROOT)):hashlib.sha256(p.read_bytes()).hexdigest() for p in sorted(files)},
        lane_protected_files=protected,
        performance_optimization='NONE: production stall not reproduced offline; stage instrumentation only',
        publication_repair='MAIN background BRTI closeouts wait for durable queue progress; native admission, cadence and fail-closed gates unchanged. Oct 4 incident attribution PROBABLE / NOT PROVEN.',
        source_change='Official metadata preparation and SAME timestamped WS provider, native consumption/qualification unchanged',
        evidence_change='Separate revision/deployment root; startup/restart slot excluded; additive admin only; strict classifier unchanged',
        deployment='NOT_AUTHORIZED; startup requires reviewed manifest/build authorization or reviewed receipt; scoring requires independent actual deployment receipt')
    (ROOT/'BTC15_V2_PRODUCT_RELEASE_R1.json').write_text(json.dumps(manifest,indent=2)+'\n')
    print('Release content manifest written; deployment remains locked.')

if __name__=='__main__':build()
