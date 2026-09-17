#!/usr/bin/env python3
"""Offline decision/omission ledger from validated frozen V2 audit evidence.

No new policies, inferred skip reasons, imputed profits, live writes or ranking.
"""
from __future__ import annotations

import argparse
import html
import json
from collections import Counter
from pathlib import Path

import nextgen_v2_review as review

EPSILON = 1e-9
MAX_MARKDOWN_DETAILS = 40


def outcome(row, family, lot):
    if row is None:
        return {'state': 'NO_RECORD', 'net_c_per_contract': None}
    observed = row.get('exit' if family == review.WATCH else 'protected_exit_observed')
    if observed is not True:
        return {'state': 'NO_OBSERVED_PROTECTED_EXIT', 'net_c_per_contract': None}
    net = review.net(row, lot)
    if net is None:
        return {'state': 'PROTECTED_EXIT_WITHOUT_FEE_NET', 'net_c_per_contract': None}
    sign = 'POSITIVE' if net > EPSILON else 'NEGATIVE' if net < -EPSILON else 'ZERO'
    return {'state': 'OBSERVED_' + sign + '_NET_EXIT', 'net_c_per_contract': net}


def decision_fact(row, family):
    watch = family == review.WATCH
    present = row is not None
    acted = row.get('warning') is True if watch and present else present if not watch else False
    reason = row.get('decision_reason') if present else None
    reason = reason if isinstance(reason, str) and reason.strip() else None
    ask = review.number(row.get('entry_ask')) if present and not watch else None
    delay = None
    if present and not watch:
        delay = review.number(row.get('entry_elapsed_sec'))
        if delay is None:
            delay = review.number(row.get('actual_delay_sec'))
    return {
        'record_present': present,
        'action_kind': 'WARNING' if watch else 'ENTRY',
        'action_observed': acted,
        'action_state': ('WARNING_RECORDED' if acted else 'NO_WARNING_RECORDED') if watch
                        else ('ENTRY_RECORDED' if acted else 'NO_ENTRY_RECORDED'),
        'reason_availability': 'EXPORTED' if reason is not None else 'NOT_EXPORTED',
        'exported_reason': reason,
        'entry_ask_c': 100 * ask if ask is not None else None,
        'entry_delay_sec': delay,
        'outcomes': {str(lot): outcome(row, family, lot) for lot in (1, 10)},
        'warning_time_sec': review.number(row.get('warning_time_sec')) if watch and present else None,
        'warning_lead_sec': review.number(row.get('lead')) if watch and present else None,
        'exit_time_sec': review.number(row.get('exit_time_sec')) if watch and present else None,
        'unresolved_warning': row.get('unresolved_warning') is True if watch and present else None,
        'new_high_after_warning_proxy': row.get('recovered_new_high_after_warning') is True if watch and present else None,
    }


def comparison(family_rows, family, experiment, control):
    watch = family == review.WATCH
    records = []
    for source in family_rows:
        left, right = source['lanes'][experiment], source['lanes'][control]
        actions = (left['action_observed'], right['action_observed'])
        category = {(True, True): 'BOTH', (True, False): 'EXPERIMENT_ONLY',
                    (False, True): 'CONTROL_ONLY', (False, False): 'NEITHER'}[actions]
        lead_l, lead_r = left['warning_lead_sec'], right['warning_lead_sec']
        row = {
            'contract': source['contract'], 'candidate_id': source['candidate_id'],
            'opportunity_index': source['opportunity_index'], 'action_class': category,
            'experiment_outcome_one_lot': left['outcomes']['1'],
            'control_outcome_one_lot': right['outcomes']['1'],
            'experiment_reason_availability': left['reason_availability'],
            'experiment_exported_reason': left['exported_reason'],
            'entry_price_improvement_c': None,
            'paired_warning_lead_improvement_sec': lead_l - lead_r if lead_l is not None and lead_r is not None else None,
            'both_protected_net_delta_c': {},
        }
        if not watch and actions == (True, True) and left['entry_ask_c'] is not None and right['entry_ask_c'] is not None:
            row['entry_price_improvement_c'] = right['entry_ask_c'] - left['entry_ask_c']
        for lot in ('1', '10'):
            net_l, net_r = left['outcomes'][lot]['net_c_per_contract'], right['outcomes'][lot]['net_c_per_contract']
            row['both_protected_net_delta_c'][lot] = net_l - net_r if net_l is not None and net_r is not None else None
        records.append(row)
    classes = Counter(row['action_class'] for row in records)
    missing = [row for row in records if row['action_class'] == 'CONTROL_ONLY']
    summary = {
        'family': family, 'experiment': experiment, 'control': control,
        'action_kind': 'WARNING' if watch else 'ENTRY',
        'anchor_opportunities': len(records),
        'anchor_contracts': len({row['contract'] for row in records}),
        'action_class_counts': {name: classes[name] for name in ('BOTH', 'EXPERIMENT_ONLY', 'CONTROL_ONLY', 'NEITHER')},
        'experiment_actions': classes['BOTH'] + classes['EXPERIMENT_ONLY'],
        'control_actions': classes['BOTH'] + classes['CONTROL_ONLY'],
        'control_only_contracts': len({row['contract'] for row in missing}),
        'control_only_outcome_counts_one_lot': dict(sorted(Counter(row['control_outcome_one_lot']['state'] for row in missing).items())) if not watch else None,
        'control_only_warning_with_observed_exit': sum(row['control_outcome_one_lot']['state'] not in ('NO_RECORD', 'NO_OBSERVED_PROTECTED_EXIT') for row in missing) if watch else None,
        'records': records,
    }
    if sum(summary['action_class_counts'].values()) != len(family_rows):
        raise ValueError('Ledger opportunity accounting mismatch')
    return summary


def build_ledger(bundle, manifest):
    try:
        errors = review.validate(bundle, manifest)
    except (KeyError, ValueError, TypeError, AttributeError, OverflowError) as exc:
        errors = ['Malformed snapshot: ' + type(exc).__name__]
    result = {
        'ledger_version': 'NEXTGEN_V2_DECISION_LEDGER_1', 'valid_snapshot': not errors,
        'integrity_errors': errors, 'orders': False, 'automatic_promotion': False,
        'same_sample_promotion': False, 'winner_selected': False,
        'later_fresh_certification_required': True, 'skip_reasons_inferred': False,
        'family_rows': [], 'comparisons': [],
    }
    if errors:
        result['status'] = 'BLOCKED_INVALID_SNAPSHOT'
        return result
    state, audit = bundle['state'], bundle['audit']['audit_records']
    global_rows = audit['candidate_verify_v2']['V1_IMMEDIATE']
    signaled_contracts = len({row['contract'] for row in global_rows})
    result.update(
        status='DESCRIPTIVE_LEDGER_ONLY', captured_utc=bundle['captured_utc'],
        code_sha256=state['code_sha256'], window_id=state['window_id'], source_sha256=state['source_sha256'],
        source_audit_sha256=bundle['audit_sha256'], future_full_contracts=state['future_full_contracts'],
        serial_signals=state['serial_signals'], contracts_with_serial_opportunities=signaled_contracts,
        full_contracts_without_serial_opportunities=state['future_full_contracts'] - signaled_contracts,
        quiet_contract_identifiers_available=False,
        family_anchor_counts={},
        limitations=[
            'A missing lane entry is NO_ENTRY_RECORDED; its exact skip reason is NOT_EXPORTED unless the audit explicitly provides it.',
            'Do not infer a failed confirmation, timeout, adverse move, or price rejection from later outcomes or a missing row.',
            'Watch rows describe warnings, not new entries. An absent warning is not an absent trade; frozen exits remain separate.',
            'Net values describe observed protected exits under frozen fees only, not executed profits or total portfolio P&L.',
            'Control-only positive or negative outcomes are hindsight descriptions, not proof of good or bad real-time selection.',
            'No-exit and missing-fee outcomes remain unknown; zero net is an observed zero, not a substituted missing result.',
            'The same opportunity appears across independent lanes and comparisons. Never add family rows or comparison counts into sample size.',
            'Quiet full contracts remain in the universe count, but their individual identifiers and raw causal paths are not exported.',
        ],
    )
    for family, spec in manifest['families'].items():
        indexes = {lane: {review.record_key(row): row for row in rows} for lane, rows in audit[family].items()}
        family_rows = []
        for key in sorted(indexes[spec['anchor']]):
            family_rows.append({
                'family': family, 'contract': key[0], 'candidate_id': key[1], 'opportunity_index': key[2],
                'lanes': {lane: decision_fact(indexes[lane].get(key), family) for lane in spec['controls'] + spec['experiments']},
            })
        result['family_anchor_counts'][family] = len(family_rows)
        result['family_rows'].extend(family_rows)
        for experiment in spec['experiments']:
            for control in spec['controls']:
                result['comparisons'].append(comparison(family_rows, family, experiment, control))
    return result


def cell(value):
    if value is None:
        return '—'
    text = f'{value:.3f}' if isinstance(value, float) else str(value)
    return html.escape(text, quote=True).replace('|', '&#124;').replace('\n', ' ').replace('\r', ' ').replace('`', '&#96;')


def markdown(ledger, manifest):
    lines = ['# V2 decision and omission ledger', '', f"Status: **{ledger['status']}**. No winner selected.", '']
    if not ledger['valid_snapshot']:
        return '\n'.join(lines + ['No ledger produced.', '', *['- ' + cell(error) for error in ledger['integrity_errors']]]) + '\n'
    lines += [f"Captured UTC: {ledger['captured_utc']}",
              f"Full contracts: {ledger['future_full_contracts']}; unique serial opportunities: {ledger['serial_signals']}.",
              f"Full contracts with no serial opportunity: {ledger['full_contracts_without_serial_opportunities']} (individual quiet-contract IDs unavailable).", '',
              'Summary below compares each experiment with its family anchor. All 28 comparisons and full records are in ledger.json.',
              'ENTRY counts concern entries; WARNING counts concern warnings only. Control-only outcomes are hindsight, not selection proof.', '',
              '| Family / experiment | Action | Anchor | Both | Experiment only | Control only | Neither |',
              '| --- | --- | --- | ---: | ---: | ---: | ---: |']
    for item in ledger['comparisons']:
        if item['control'] != manifest['families'][item['family']]['anchor']:
            continue
        counts = item['action_class_counts']
        lines.append('| ' + ' | '.join(cell(value) for value in [item['family'] + ' / ' + item['experiment'], item['action_kind'], item['control'], *[counts[name] for name in ('BOTH', 'EXPERIMENT_ONLY', 'CONTROL_ONLY', 'NEITHER')]]) + ' |')
    lines += ['', '## Per-opportunity detail', '',
              f'First {MAX_MARKDOWN_DETAILS} experiment/anchor cases in deterministic identity order are shown; JSON is not truncated.',
              'Prices and net values are cents per contract under the one-lot taker/taker model.', '',
              '| Contract / candidate / opportunity | Experiment | State | Exported reason | Entry c | Experiment outcome / net c | Anchor outcome / net c |',
              '| --- | --- | --- | --- | ---: | --- | --- |']
    details = []
    for source in ledger['family_rows']:
        spec = manifest['families'][source['family']]
        for lane in spec['experiments']:
            left, right = source['lanes'][lane], source['lanes'][spec['anchor']]
            lnet, rnet = left['outcomes']['1'], right['outcomes']['1']
            details.append([f"{source['contract']} / {source['candidate_id']} / #{source['opportunity_index']}", lane,
                            left['action_state'], left['exported_reason'] or 'NOT_EXPORTED', left['entry_ask_c'],
                            lnet['state'] + ' / ' + cell(lnet['net_c_per_contract']),
                            rnet['state'] + ' / ' + cell(rnet['net_c_per_contract'])])
    for row in details[:MAX_MARKDOWN_DETAILS]:
        lines.append('| ' + ' | '.join(cell(value) for value in row) + ' |')
    lines += ['', f'Detail rows shown: {min(len(details), MAX_MARKDOWN_DETAILS)} of {len(details)}.', '',
              '## Limits', '', *['- ' + item for item in ledger['limitations']], '',
              '## CURRENT STATE', '', '- CONTROL: Frozen evidence read only; no collector changes.',
              '- NEW SHADOW: Undeployed per-opportunity review, no new policy or live alert.',
              '- BLOCKED: Skip explanations and raw causal paths are not fully exported; no efficacy decision.',
              '- NEXT STEP: Repeat on later coherent evidence; preserve all frozen policies.']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('bundle', type=Path)
    parser.add_argument('--manifest', type=Path, default=review.MANIFEST_PATH)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwrite an existing ledger')
    args = parser.parse_args(argv)
    try:
        def reject_constant(_):
            raise ValueError('Non-finite JSON constant')
        bundle = json.loads(args.bundle.read_text(), parse_constant=reject_constant)
        manifest = json.loads(args.manifest.read_text(), parse_constant=reject_constant)
        ledger = build_ledger(bundle, manifest)
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'ledger.json').write_text(json.dumps(ledger, indent=2, sort_keys=True, allow_nan=False) + '\n')
        (args.output / 'ledger.md').write_text(markdown(ledger, manifest))
        print(json.dumps({'status': ledger['status'], 'family_rows': len(ledger['family_rows']),
                          'comparisons': len(ledger['comparisons']), 'output': str(args.output.resolve()), 'orders': False}))
        return 0 if ledger['valid_snapshot'] else 2
    except (OSError, ValueError, TypeError, KeyError) as exc:
        print(json.dumps({'status': 'LEDGER_FAILED', 'error_type': type(exc).__name__, 'orders': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
