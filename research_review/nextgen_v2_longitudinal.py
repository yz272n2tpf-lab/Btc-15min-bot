#!/usr/bin/env python3
"""Build a read-only time-series scorecard from coherent V2 bundle archives.

The collector is cumulative, so this tool never adds checkpoint totals together.
It verifies one frozen window and uses each opportunity identity once per checkpoint.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import nextgen_v2_review as review


def opportunity_map(bundle):
    result = {}
    for family, lanes in bundle['audit']['audit_records'].items():
        for lane, rows in lanes.items():
            result[(family, lane)] = {review.record_key(row): row for row in rows}
    return result


def stable_projection(row):
    """Fields that must not change after an opportunity enters a full-contract audit."""
    ignored = {'source_age_sec'}
    return {key: value for key, value in row.items() if key not in ignored}


def validate_series(bundles, manifest):
    errors = []
    if not bundles:
        return ['No checkpoint bundles supplied']
    ordered = sorted(bundles, key=lambda b: b.get('captured_utc', ''))
    if ordered != bundles:
        errors.append('Checkpoint inputs are not in chronological order')
    previous = None
    seen_captures = set()
    for index, bundle in enumerate(bundles):
        prefix = f'checkpoint {index + 1}'
        capture = bundle.get('captured_utc')
        if capture in seen_captures:
            errors.append(f'{prefix}: duplicate capture timestamp')
        seen_captures.add(capture)
        for error in review.validate(bundle, manifest):
            errors.append(f'{prefix}: {error}')
        state = bundle.get('state', {})
        if previous is not None:
            prior_state = previous.get('state', {})
            for field in ('version', 'window_id', 'code_sha256', 'cutoff_utc'):
                if state.get(field) != prior_state.get(field):
                    errors.append(f'{prefix}: frozen {field} changed across checkpoints')
            for field in ('future_full_contracts', 'serial_signals'):
                if isinstance(state.get(field), int) and isinstance(prior_state.get(field), int) and state[field] < prior_state[field]:
                    errors.append(f'{prefix}: cumulative {field} regressed')
            prior_rows, current_rows = opportunity_map(previous), opportunity_map(bundle)
            for lane, old in prior_rows.items():
                new = current_rows.get(lane, {})
                missing = set(old) - set(new)
                if missing:
                    errors.append(f'{prefix}: {lane[0]}/{lane[1]} lost {len(missing)} historical opportunities')
                changed = [key for key in set(old) & set(new)
                           if stable_projection(old[key]) != stable_projection(new[key])]
                if changed:
                    errors.append(f'{prefix}: {lane[0]}/{lane[1]} changed {len(changed)} historical opportunities')
        previous = bundle
    return errors


def concise_comparison(item):
    base = {'family': item['family'], 'experiment': item['experiment'], 'control': item['control']}
    if item['family'] == review.WATCH:
        keys = ('matched_opportunities', 'paired_warned_exits', 'paired_warned_exit_contracts',
                'paired_lead_improvement_sec', 'at_least_5s_earlier_pairs', 'at_least_5s_later_pairs',
                'shadow_warning_metrics', 'control_warning_metrics', 'exit_policy_unchanged')
    else:
        keys = ('shadow_entries', 'control_entries', 'matched_entries', 'control_only_entries',
                'signal_retention_vs_control', 'shadow_contracts', 'control_contracts',
                'contracts_lost_vs_control', 'contracts_added_vs_control',
                'shadow_true_contract_coverage', 'control_true_contract_coverage',
                'both_protected_exits', 'both_protected_exit_contracts',
                'paired_entry_price_improvement_c', 'one_lot_paired_net_delta_c',
                'ten_lot_paired_net_delta_c', 'one_lot_control_only_avg_net_c')
    base.update({key: item.get(key) for key in keys})
    return base


def build_series(bundles, manifest):
    errors = validate_series(bundles, manifest)
    result = {
        'scorecard_version': 'NEXTGEN_V2_LONGITUDINAL_1',
        'valid_series': not errors,
        'integrity_errors': errors,
        'orders': False,
        'automatic_promotion': False,
        'same_sample_promotion': False,
        'winner_selected': False,
        'later_fresh_certification_required': True,
        'checkpoint_count': len(bundles),
        'checkpoints': [],
    }
    if errors:
        result['status'] = 'BLOCKED_INVALID_SERIES'
        return result
    for bundle in bundles:
        snapshot = review.build_review(bundle, manifest)
        result['checkpoints'].append({
            'captured_utc': snapshot['captured_utc'],
            'source_sha256': snapshot['source_sha256'],
            'future_full_contracts': snapshot['future_full_contracts'],
            'serial_signals': snapshot['serial_signals'],
            'review_floor_met': snapshot['review_floor_met'],
            'comparisons': [concise_comparison(item) for item in snapshot['comparisons']],
        })
    latest = result['checkpoints'][-1]
    result.update(
        status='REVIEW_FLOOR_MET' if latest['review_floor_met'] else 'COLLECTING',
        window_id=manifest['window_id'], code_sha256=manifest['code_sha256'],
        latest_capture_utc=latest['captured_utc'],
        latest_future_full_contracts=latest['future_full_contracts'],
        latest_serial_signals=latest['serial_signals'],
        remaining_full_contracts=max(0, manifest['minimum_full_contracts']-latest['future_full_contracts']),
        remaining_serial_signals=max(0, manifest['minimum_signals']-latest['serial_signals']),
        latest_comparisons=latest['comparisons'],
        cumulative_snapshots_are_not_summed=True,
        sample_floor_is_not_per_lane_sufficiency=True,
    )
    return result


def markdown(scorecard):
    lines = ['# V2 longitudinal scorecard', '',
             f"Status: **{scorecard['status']}**. Winner selected: **No**. No promotion.", '']
    if not scorecard['valid_series']:
        return '\n'.join(lines + ['Series rejected; no trend comparison produced.', '',
                                   *['- '+error for error in scorecard['integrity_errors']]])+'\n'
    lines += [f"Accepted checkpoints: **{scorecard['checkpoint_count']}**.",
              f"Latest sample: **{scorecard['latest_future_full_contracts']} contracts / {scorecard['latest_serial_signals']} signals**.",
              f"Remaining to overall review floor: **{scorecard['remaining_full_contracts']} contracts / {scorecard['remaining_serial_signals']} signals**.", '',
              '| Captured UTC | Full contracts | Signals | Review floor |',
              '| --- | ---: | ---: | --- |']
    for point in scorecard['checkpoints']:
        lines.append(f"| {point['captured_utc']} | {point['future_full_contracts']} | {point['serial_signals']} | {'Yes' if point['review_floor_met'] else 'No'} |")
    lines += ['', 'Cumulative checkpoints are never summed. Each row is a complete frozen-window snapshot, and the latest snapshot supplies current totals.', '',
              '## CURRENT STATE', '',
              '- CONTROL: Frozen collectors and comparison policies are read only.',
              '- NEW SHADOW: Longitudinal evidence is summarized without changing experiment logic.',
              '- BLOCKED: No winner or certification decision until adequate evidence and a separate future certification window.',
              '- NEXT STEP: Add later coherent bundles in chronological order and rerun this scorecard.']
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundles', nargs='+', type=Path, help='Chronological bundle.json paths')
    parser.add_argument('--manifest', type=Path, default=review.MANIFEST_PATH)
    parser.add_argument('--output', type=Path, required=True, help='New output directory; never overwritten')
    args = parser.parse_args(argv)
    try:
        manifest = json.loads(args.manifest.read_text())
        bundles = [json.loads(path.read_text()) for path in args.bundles]
        scorecard = build_series(bundles, manifest)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output/'scorecard.json').write_text(json.dumps(scorecard, indent=2, sort_keys=True, allow_nan=False)+'\n')
        (args.output/'scorecard.md').write_text(markdown(scorecard))
        print(json.dumps({'status': scorecard['status'], 'valid_series': scorecard['valid_series'],
                          'checkpoints': scorecard['checkpoint_count'], 'output': str(args.output.resolve()),
                          'orders': False, 'winner_selected': False}))
        return 0 if scorecard['valid_series'] else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'SERIES_BUILD_FAILED', 'error_type': type(exc).__name__, 'orders': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
