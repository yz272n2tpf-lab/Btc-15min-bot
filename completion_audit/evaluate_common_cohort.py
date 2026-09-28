"""Read a registered phase only; refuse early holdout outcome evaluation."""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
from common_journal import scan
from cohort_registry import validate, utc, registry, identity
from summarize_passive_acceptance import analyze


def sources(path, run_id, start, end, damage):
    for member in scan(path, damage):
        row = member['record']
        if row.get('run_id') != run_id:
            raise ValueError('Mixed collector run identities')
        if row.get('record_type') != 'OBSERVATION':
            continue
        for source in row['sources']:
            began = utc(source['request_started_utc'])
            if not start <= began < end:
                continue
            yield dict(source, service='scalp' if source['service']=='serial' else source['service'],
                       start_epoch=began.timestamp())


def evaluate(manifest, phase, path, markets, now=None):
    copy = dict(manifest)
    expected = copy.pop('canonical_content_sha256_excluding_this_field')
    if identity(copy) != expected:
        raise ValueError('Manifest identity mismatch')
    validate(manifest)
    window = next(w for w in manifest['windows'] if w['role'] == phase)
    start, end = utc(window['start_utc']), utc(window['end_utc'])
    now = now or datetime.now(timezone.utc)
    if phase == 'untouched_holdout' and now < end:
        raise ValueError('Holdout is sealed until its fixed end')
    damage=[]
    records=list(sources(path,manifest['revisions']['clean']['run_id'],start,end,damage))
    result=analyze(records,start,end,markets,qualification_time='response_received')
    result.update(cohort_id=manifest['cohort_id'],phase=phase,as_of_utc=now.isoformat(),
                  registered_window_finished=now>=end,journal_damage=damage,
                  universe_registry=registry(window,markets,
                      [r['state'].get('contract') for r in records if isinstance(r.get('state'),dict)]),
                  runtime_identity_requires_deployment_log_reconciliation=True,
                  baseline_certified=False)
    return result


if __name__ == '__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest',type=Path,required=True)
    parser.add_argument('--phase',required=True)
    parser.add_argument('--journal',type=Path,required=True)
    parser.add_argument('--markets',type=Path,nargs='*',default=[])
    parser.add_argument('--output',type=Path,required=True)
    args=parser.parse_args()
    markets=[json.loads(path.read_text()) for path in args.markets]
    result=evaluate(json.loads(args.manifest.read_text()),args.phase,args.journal,
                    [r.get('market',r) for r in markets])
    # Derived reports are versioned by the caller; never replace a prior report.
    with args.output.open('x') as stream:
        json.dump(result,stream,indent=2,allow_nan=False);stream.write('\n')
    print(json.dumps(dict(output=str(args.output),phase=args.phase,counts=result['counts'],certified=False)))
