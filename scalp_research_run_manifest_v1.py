#!/usr/bin/env python3
"""Research run manifest / version lock V1.

Research-only. NO ORDERS. NO STRATEGY CHANGES.

Purpose
-------
Capture the exact code/config state used for a scalp test run so results from
multiple V6 revisions cannot accidentally be mixed together. This makes each
checkpoint reproducible and gives the review/report tools a stable run ID.
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any

TRACKED_FILES = [
    'scalp_lead_shadow_v6.py',
    'scalp_profit_protection_shadow_v1.py',
    'scalp_trade_path_shadow_v1.py',
    'scalp_profit_protection_live_shadow_v1.py',
    'scalp_brti_health_shadow_v1.py',
    'scalp_research_test_gate_v1.py',
    'scalp_research_checkpoint_report_v1.py',
    'scalp_v6_missed_opportunity_audit_v1.py',
]

OUT = Path('scalp_research_run_manifest_v1.json')


def sha256_file(path: Path) -> str | None:
    if not path.exists() or not path.is_file():
        return None
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def git_value(*args: str) -> str | None:
    try:
        return subprocess.check_output(['git', *args], text=True, stderr=subprocess.DEVNULL).strip() or None
    except Exception:
        return None


def build_manifest() -> Dict[str, Any]:
    files = {name: sha256_file(Path(name)) for name in TRACKED_FILES}
    core = {
        'created_utc': datetime.now(timezone.utc).isoformat(),
        'branch': git_value('rev-parse', '--abbrev-ref', 'HEAD'),
        'commit': git_value('rev-parse', 'HEAD'),
        'dirty': bool(git_value('status', '--porcelain')),
        'signal_only': True,
        'orders_enabled': False,
        'research_generation': 'V6',
        'entry_horizon_seconds': 180,
        'tracked_files': files,
    }

    # Stable run ID excludes the creation timestamp, so the exact same code state
    # receives the same ID even if this script is rerun later.
    stable = dict(core)
    stable.pop('created_utc', None)
    stable_blob = json.dumps(stable, sort_keys=True, separators=(',', ':')).encode()
    core['run_id'] = hashlib.sha256(stable_blob).hexdigest()[:16]
    return core


def main() -> None:
    m = build_manifest()
    OUT.write_text(json.dumps(m, indent=2, sort_keys=True) + '\n', encoding='utf-8')
    print('SCALP_RESEARCH_RUN | id=%s | branch=%s | commit=%s | dirty=%s' % (
        m['run_id'], m['branch'], m['commit'], m['dirty']))
    missing = [k for k, v in m['tracked_files'].items() if v is None]
    if missing:
        print('SCALP_RESEARCH_RUN WARNING | missing tracked files: %s' % ', '.join(missing))
    else:
        print('SCALP_RESEARCH_RUN | all tracked research files fingerprinted')
    print('Manifest:', OUT)


if __name__ == '__main__':
    main()
