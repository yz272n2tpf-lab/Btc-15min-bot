"""Durable clean-collector run identity and fixed paths. SIGNAL ONLY / NO ORDERS."""
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import runpy


def prepare(root, run_id, code_root, require_mount=True):
    root, code_root = Path(root).resolve(), Path(code_root).resolve()
    if not root.is_dir() or (require_mount and not os.path.ismount(root)):
        raise RuntimeError('An existing persistent data mount is required')
    if not run_id or any(c not in 'abcdefghijklmnopqrstuvwxyz0123456789-_' for c in run_id):
        raise ValueError('Explicit safe run identity required')
    names = ('scalp_move_shadow_v1.py', 'scalp_move_shadow_v2_finalprod_clean.py',
             'btc15_brti_shared_consumer_v1.py', 'btc15_kalshi_quote_provenance_v1.py',
             'btc15_common_observer_v1.py', 'scalp_path_export_bridge_v1.py')
    fingerprints = {name: hashlib.sha256((code_root/name).read_bytes()).hexdigest() for name in names}
    event = root / ('scalp_' + run_id + '_events.csv')
    state = root / ('scalp_' + run_id + '_state.json')
    manifest = root / ('scalp_' + run_id + '_manifest.json')
    common = root / ('scalp_' + run_id + '_common.jsonl.gz')
    identity = dict(run_id=run_id, source_schema=2, brti_transport='legacy_shared_http',
                    source_sha256=fingerprints, event_csv=str(event), state_json=str(state),
                    common_observations=str(common),manifest_path=str(manifest),
                    qualification_max_age_seconds=5, signal_only=True, orders=False)
    if manifest.exists():
        previous = json.loads(manifest.read_text())
        if any(previous.get(k) != v for k,v in identity.items()):
            raise RuntimeError('Existing run identity differs; use a new explicit run ID')
    else:
        if event.exists() or state.exists() or common.exists():
            raise RuntimeError('Unidentified existing data preserved; refusing to append')
        with manifest.open('x', encoding='utf-8') as stream:
            json.dump(identity | dict(created_utc=datetime.now(timezone.utc).isoformat(),
                                     railway_commit=os.getenv('RAILWAY_GIT_COMMIT_SHA'),
                                     phase='DEVELOPMENT_UNTIL_SEPARATE_COHORT_REGISTRATION'), stream, indent=2)
            stream.flush(); os.fsync(stream.fileno())
    return identity


def main():
    if os.getenv('BTC15_USE_SHARED_BRTI') != '1' or os.getenv('BTC15_BRTI_TRANSPORT') != 'legacy_shared_http':
        raise RuntimeError('Clean collector requires the intended shared owner transport')
    if not os.getenv('BTC15_BRTI_SHARED_URL', '').strip():
        raise RuntimeError('Direct durable shared owner URL is required')
    from btc15_preserve_evidence_v1 import preserve
    print('CLEAN PRIOR EVIDENCE | '+json.dumps(preserve(os.getenv('BTC15_DATA_DIR','/data'),
          'clean-before-shared-v2-20260923'))+' | NO ORDERS',flush=True)
    identity = prepare(os.getenv('BTC15_DATA_DIR', '/data'), os.getenv('BTC15_CLEAN_RUN_ID', ''), Path.cwd())
    os.environ['SCALP_EVENT_CSV'] = identity['event_csv']
    os.environ['SCALP_STATE_JSON'] = identity['state_json']
    os.environ['SCALP_COLLECTOR_SCRIPT'] = 'scalp_move_shadow_v2_finalprod_clean.py'
    os.environ['BTC15_COMMON_OBSERVATIONS'] = identity['common_observations']
    os.environ['BTC15_RUN_MANIFEST'] = identity['manifest_path']
    print('CLEAN DURABLE RUN | '+json.dumps(identity, sort_keys=True)+' | NO ORDERS', flush=True)
    import shutil
    print('CLEAN DATA CAPACITY | '+json.dumps(dict(zip(('total_bytes','used_bytes','free_bytes'),shutil.disk_usage('/data'))))+' | NO ORDERS',flush=True)
    from btc15_common_observer_v1 import start
    start(identity['common_observations'],identity['run_id'])
    runpy.run_path('scalp_path_export_bridge_v1.py', run_name='__main__')


if __name__ == '__main__': main()
