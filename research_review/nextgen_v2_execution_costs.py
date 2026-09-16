#!/usr/bin/env python3
"""Offline extra-execution-cost sensitivity for frozen V2 audit bundles.

Fixed-entry/fixed-exit arithmetic only: NOT a fill simulator or a new strategy.
No network calls, collector imports, order handling, or promotion decisions.
"""
from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import nextgen_v2_review as review

VERSION = 'NEXTGEN_V2_EXTRA_EXECUTION_COST_1'
LOTS = (1, 10)
# Descriptive stress grid, not fitted thresholds or a pass/fail standard.
EXTRA_CENTS_PER_SIDE = (0, 1, 2, 5)
EPSILON = 1e-9


def has_exit(row, family):
    return row.get('exit' if family == review.WATCH else 'protected_exit_observed') is True


def cost_value(value):
    number = review.number(value)
    if number is None or number < 0:
        raise ValueError('Extra execution cost must be finite and nonnegative')
    return number


def stressed_net(row, family, lot, entry_cost_c, exit_cost_c):
    if lot not in LOTS:
        raise ValueError('Unsupported lot scenario')
    cost = cost_value(entry_cost_c) + cost_value(exit_cost_c)
    if not has_exit(row, family):
        return None
    net = review.net(row, lot)
    return None if net is None else net - cost


def statistics_for(values):
    return {
        'scored_exits': len(values),
        'conditional_mean_net_c_per_contract': review.average(values),
        'conditional_median_net_c_per_contract': statistics.median(values) if values else None,
        'conditional_min_net_c_per_contract': min(values) if values else None,
        'positive_observed_exits': sum(value > EPSILON for value in values),
        'zero_observed_exits': sum(abs(value) <= EPSILON for value in values),
        'negative_observed_exits': sum(value < -EPSILON for value in values),
        'positive_fraction_of_scored_exits': review.share(sum(value > EPSILON for value in values), len(values)),
    }


def lane_summary(rows, family, lot, full_contracts):
    protected = [row for row in rows if has_exit(row, family)]
    scored = [row for row in protected if review.net(row, lot) is not None]
    scenarios = []
    for per_side in EXTRA_CENTS_PER_SIDE:
        values = [stressed_net(row, family, lot, per_side, per_side) for row in scored]
        scenarios.append({
            'extra_entry_cost_c_per_contract': per_side,
            'extra_exit_cost_c_per_contract': per_side,
            'extra_round_trip_cost_c_per_contract': 2 * per_side,
            **statistics_for(values),
        })
    mean_net = scenarios[0]['conditional_mean_net_c_per_contract']
    return {
        'lot_scenario': lot,
        'entries': len(rows),
        'entry_contracts': len({row['contract'] for row in rows}),
        'entry_contract_coverage': review.share(len({row['contract'] for row in rows}), full_contracts),
        'protected_exits': len(protected),
        'without_observed_protected_exit': len(rows) - len(protected),
        'protected_exits_missing_fee_net': len(protected) - len(scored),
        'scored_exit_contracts': len({row['contract'] for row in scored}),
        'conditional_mean_break_even_extra_round_trip_c': max(0, mean_net) if mean_net is not None else None,
        'baseline_conditional_mean_positive': mean_net is not None and mean_net > EPSILON,
        'scenarios': scenarios,
    }


def paired_summary(shadow, control, family, lot):
    controls = {review.record_key(row): row for row in control}
    shadow_keys = {review.record_key(row) for row in shadow}
    matched = [(row, controls[review.record_key(row)]) for row in shadow if review.record_key(row) in controls]
    scored = [(left, right) for left, right in matched
              if stressed_net(left, family, lot, 0, 0) is not None
              and stressed_net(right, family, lot, 0, 0) is not None]
    scenarios = []
    for per_side in EXTRA_CENTS_PER_SIDE:
        left = [stressed_net(row, family, lot, per_side, per_side) for row, _ in scored]
        right = [stressed_net(row, family, lot, per_side, per_side) for _, row in scored]
        scenarios.append({
            'extra_round_trip_cost_c_per_contract': 2 * per_side,
            'shadow_conditional_mean_net_c': review.average(left),
            'control_conditional_mean_net_c': review.average(right),
            'conditional_paired_net_delta_c': review.average(a - b for a, b in zip(left, right)),
            'shadow_positive_observed_exits': sum(value > EPSILON for value in left),
            'control_positive_observed_exits': sum(value > EPSILON for value in right),
        })
    return {
        'lot_scenario': lot,
        'matched_entries': len(matched),
        'both_scored_exits': len(scored),
        'both_scored_exit_contracts': len({left['contract'] for left, _ in scored}),
        'matched_entries_excluded_for_missing_exit_or_fee_net': len(matched) - len(scored),
        'shadow_only_entries': sum(review.record_key(row) not in controls for row in shadow),
        'control_only_entries': sum(review.record_key(row) not in shadow_keys for row in control),
        'identical_cost_applied_to_both_policies': True,
        'scenarios': scenarios,
    }


def build_report(bundle, manifest):
    try:
        errors = review.validate(bundle, manifest)
    except (KeyError, TypeError, ValueError, AttributeError, OverflowError) as exc:
        errors = ['Malformed evidence: ' + type(exc).__name__]
    result = {
        'report_version': VERSION,
        'valid_snapshot': not errors,
        'integrity_errors': errors,
        'orders': False,
        'automatic_promotion': False,
        'same_sample_promotion': False,
        'winner_selected': False,
        'later_fresh_certification_required': True,
        'lane_results': [],
        'paired_comparisons': [],
    }
    if errors:
        result['status'] = 'BLOCKED_INVALID_SNAPSHOT'
        return result
    state, audit = bundle['state'], bundle['audit']['audit_records']
    result.update(
        status='DESCRIPTIVE_SENSITIVITY_ONLY', captured_utc=bundle['captured_utc'],
        code_sha256=state['code_sha256'], window_id=state['window_id'],
        source_sha256=state['source_sha256'], audit_sha256=bundle['audit_sha256'],
        future_full_contracts=state['future_full_contracts'], serial_signals=state['serial_signals'],
        assumptions={
            'fee_model': 'unchanged frozen V1 taker-entry/taker-exit net',
            'lot_scenarios': list(LOTS),
            'additional_cost_c_per_side': list(EXTRA_CENTS_PER_SIDE),
            'same_cost_for_every_scored_opportunity': True,
            'entries_and_exits_held_fixed': True,
            'fees_held_fixed_not_recalculated_for_hypothetical_prices': True,
            'observed_protected_exits_only': True,
            'no_fill_or_latency_simulation': True,
            'grid_is_descriptive_not_a_promotion_gate': True,
        },
        limitations=[
            'Conditional on observed protected exits with finite fee-net values; missing outcomes are not zero profit.',
            'Not realized profit, total portfolio P&L, a win rate, an executable backtest, or a manual-fill guarantee.',
            'A fixed extra cost does not model reaction delay, market depth, spread changes, path-dependent exits, or repriced fees.',
            'Equal costs cancel in a paired net delta; these scenarios cannot establish comparative policy superiority.',
            'Watch warnings do not change frozen exits here; no economics benefit is credited for earlier warnings.',
            'Repeated opportunities within a contract and copied opportunities across lanes are not independent evidence; never sum lanes.',
            'The review floor and descriptive stress grid do not permit same-sample selection or promotion; later certification remains separate.',
        ],
    )
    for family, spec in manifest['families'].items():
        for lane in spec['controls'] + spec['experiments']:
            result['lane_results'].append({
                'family': family, 'lane': lane,
                'role': 'CONTROL' if lane in spec['controls'] else 'EXPERIMENT',
                'lots': [lane_summary(audit[family][lane], family, lot, state['future_full_contracts']) for lot in LOTS],
            })
        for experiment in spec['experiments']:
            for control in spec['controls']:
                result['paired_comparisons'].append({
                    'family': family, 'experiment': experiment, 'control': control,
                    'lots': [paired_summary(audit[family][experiment], audit[family][control], family, lot) for lot in LOTS],
                })
    return result


def markdown(report):
    lines = ['# Extra execution-cost sensitivity', '', f"Status: **{report['status']}**. No winner selected.", '']
    if not report['valid_snapshot']:
        return '\n'.join(lines + ['No economics report produced.', '', *['- ' + e for e in report['integrity_errors']]]) + '\n'
    lines += [f"Captured UTC: {report['captured_utc']}",
              f"Full contracts: {report['future_full_contracts']}; serial opportunities: {report['serial_signals']}.", '',
              'One-lot taker/taker model. Values are conditional mean cents per contract on fee-scored protected exits only.',
              'Column headings are EXTRA round-trip cost: 0, 1, 2, or 5 cents at EACH side (entry plus exit).', '',
              '| Family / lane | Entries | Scored exits / contracts | No exit / missing fee net | +0c | +2c | +4c | +10c |',
              '| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |']
    for lane in report['lane_results']:
        row = lane['lots'][0]
        nets = ['—' if s['conditional_mean_net_c_per_contract'] is None else f"{s['conditional_mean_net_c_per_contract']:.3f}" for s in row['scenarios']]
        lines.append(f"| {lane['family']} / {lane['lane']} | {row['entries']} | {row['scenarios'][0]['scored_exits']} / {row['scored_exit_contracts']} | {row['without_observed_protected_exit']} / {row['protected_exits_missing_fee_net']} | " + ' | '.join(nets) + ' |')
    lines += ['', 'Ten-lot per-contract values, positive/zero/negative exit counts, omissions and all 28 paired comparisons are in stress.json.', '',
              '## Limits', '', *['- ' + item for item in report['limitations']], '',
              '## CURRENT STATE', '',
              '- CONTROL: Frozen source evidence is read only; no collector changes.',
              '- NEW SHADOW: Offline sensitivity arithmetic only; not deployed or used by live signals.',
              '- BLOCKED: Fill/latency performance and policy superiority are not established.',
              '- NEXT STEP: Repeat on later coherent evidence without adjusting the frozen experiment.']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path, help='Archived bundle.json; no network reads')
    parser.add_argument('--manifest', type=Path, default=review.MANIFEST_PATH)
    parser.add_argument('--output', type=Path, required=True, help='New output directory; no overwrites')
    args = parser.parse_args(argv)
    try:
        def reject_constant(_):
            raise ValueError('Non-finite JSON number')
        bundle = json.loads(args.bundle.read_text(), parse_constant=reject_constant)
        manifest = json.loads(args.manifest.read_text(), parse_constant=reject_constant)
        report = build_report(bundle, manifest)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'stress.json').write_text(json.dumps(report, sort_keys=True, indent=2, allow_nan=False) + '\n')
        (args.output / 'stress.md').write_text(markdown(report))
        print(json.dumps({'status': report['status'], 'lanes': len(report['lane_results']),
                          'comparisons': len(report['paired_comparisons']), 'orders': False,
                          'output': str(args.output.resolve())}))
        return 0 if report['valid_snapshot'] else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(json.dumps({'status': 'COST_REVIEW_FAILED', 'error_type': type(exc).__name__, 'orders': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
