#!/usr/bin/env python3
"""Read-only review of frozen V2 state/audit snapshots; Python standard library.

No collector imports, Railway writes, order endpoints, or promotion decisions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from datetime import datetime, timezone
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

MANIFEST_PATH = Path(__file__).with_name('nextgen_v2_manifest.json')
WATCH = 'watch_exit_v2'
FALSE_FLAGS = ('orders', 'automatic_promotion', 'same_sample_promotion', 'production_logic_changed')
TRUE_FLAGS = ('shadow_only', 'manual_execution_only', 'later_fresh_certification_required')


def timestamp(value):
    try:
        d = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
        return d.astimezone(timezone.utc) if d.tzinfo else None
    except (ValueError, TypeError):
        return None


def number(value):
    if isinstance(value, bool): return None
    try:
        result = float(value)
        return result if math.isfinite(result) else None
    except (TypeError, ValueError):
        return None


def average(values):
    xs = [number(x) for x in values if number(x) is not None]
    return statistics.fmean(xs) if xs else None


def share(numerator, denominator):
    return numerator / denominator if denominator else None


def record_key(row):
    return row.get('contract'), row.get('candidate_id'), row.get('opportunity_index')


def net(row, lot):
    scenario = ((row.get('fee_scenarios') or {}).get(str(lot)) or {}).get('TAKER_TAKER') or {}
    result = number(scenario.get('net_gain_c_per_contract'))
    if result is not None: return result
    return number(row.get('one_lot_taker_taker_net_c' if lot == 1 else 'ten_lot_taker_taker_net_c'))


def canonical_sha(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()).hexdigest()


def identity(value):
    return tuple(value.get(k) for k in ('version', 'window_id', 'source_sha256'))


def coherent_capture(read_json, manifest, clock=lambda: datetime.now(timezone.utc), attempts=3):
    """State/audit can race a refresh; use state-audit-state, retry as a unit."""
    for _ in range(attempts):
        first, audit, final = read_json('/state'), read_json('/audit'), read_json('/state')
        if identity(first) == identity(audit) == identity(final):
            return {'captured_utc': clock().isoformat(), 'manifest': manifest,
                    'state': final, 'audit': audit,
                    'state_sha256': canonical_sha(final), 'audit_sha256': canonical_sha(audit)}
    raise ValueError('Source changed during capture; no mixed snapshot was accepted')


class NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise ValueError('Unexpected redirect from frozen service URL')


def http_reader(base):
    if not base.startswith('https://') or '?' in base or '#' in base or '@' in base:
        raise ValueError('Manifest must contain an HTTPS service origin without credentials/query')
    opener = build_opener(NoRedirect())
    def read(path):
        req = Request(base.rstrip('/') + path, headers={'Cache-Control': 'no-cache', 'Accept': 'application/json'})
        with opener.open(req, timeout=30) as response:
            raw = response.read(32 * 1024 * 1024 + 1)
            if len(raw) > 32 * 1024 * 1024: raise ValueError('Snapshot exceeds 32 MiB')
            return json.loads(raw, parse_constant=lambda _: (_ for _ in ()).throw(ValueError('Non-finite JSON number')))
    return read


def validate(bundle, manifest, as_of=None):
    """Independently validate identity, safety, audit coverage and exit parity."""
    errors = []
    s, a = bundle.get('state', {}), bundle.get('audit', {})
    captured = timestamp(bundle.get('captured_utc'))
    clock = as_of or captured
    if not clock: errors.append('Missing timezone-aware capture time')
    for label, payload in (('state', s), ('audit', a)):
        if not isinstance(payload, dict): return [f'{label}: expected an object']
        if payload.get('ok') is not True: errors.append(f'{label}: not healthy')
        if bundle.get(label+'_sha256') != canonical_sha(payload): errors.append(f'{label}: saved digest mismatch')
        for name in FALSE_FLAGS:
            if payload.get(name) is not False: errors.append(f'{label}: unsafe or missing {name}')
        for name in TRUE_FLAGS:
            if payload.get(name) is not True: errors.append(f'{label}: unsafe or missing {name}')
    if identity(s) != identity(a): errors.append('State and audit identify different snapshots')
    for name in ('version', 'code_sha256', 'cutoff_utc', 'window_id'):
        if s.get(name) != manifest[name]: errors.append(f'Frozen {name} mismatch')
    expected_window = hashlib.sha256((manifest['code_sha256']+'|'+manifest['cutoff_utc']).encode()).hexdigest()
    if expected_window != manifest['window_id']: errors.append('Manifest window ID does not match code and cutoff')
    if s.get('prospective_window') is not True: errors.append('Snapshot is not the frozen prospective window')
    if not isinstance(s.get('source_sha256'), str) or len(s['source_sha256']) != 64:
        errors.append('Missing source SHA256')
    for field in ('last_poll_utc', 'source_latest_utc'):
        observed = timestamp(s.get(field))
        age = (clock-observed).total_seconds() if clock and observed else None
        if age is None or age < -60 or age > manifest['maximum_age_seconds']:
            errors.append(f'{field}: stale, future, or invalid')
    if (s.get('runtime_integrity') or {}).get('all_checks_pass') is not True:
        errors.append('Collector reports an integrity failure')
    counts = [s.get('future_full_contracts'), s.get('serial_signals')]
    if any(type(x) is not int or x < 0 for x in counts):
        return errors + ['Invalid sample counts']
    floor = counts[0] >= manifest['minimum_full_contracts'] and counts[1] >= manifest['minimum_signals']
    if (s.get('evidence_readiness') or {}).get('sample_ready') is not floor:
        errors.append('Sample readiness disagrees with counts')
    if s.get('status') not in ('COLLECTING_NEXTGEN_V2', 'READY_FOR_MANUAL_V2_COMPARISON'):
        errors.append('Unexpected collector status')
    if s.get('status') == 'READY_FOR_MANUAL_V2_COMPARISON' and not floor:
        errors.append('Premature review-ready status')
    audit = a.get('audit_records')
    if not isinstance(audit, dict) or set(audit) != set(manifest['families']):
        return errors + ['Audit families are incomplete']
    for family, spec in manifest['families'].items():
        expected = set(spec['controls'] + spec['experiments'])
        summaries, lanes = s.get(family), audit.get(family)
        if not isinstance(summaries, dict) or not isinstance(lanes, dict) or set(summaries) != expected or set(lanes) != expected:
            errors.append(f'{family}: incomplete lane set'); continue
        keys_by_lane = {}
        for lane, rows in lanes.items():
            label = f'{family}/{lane}'
            if not isinstance(rows, list) or any(not isinstance(r, dict) for r in rows):
                errors.append(label+': records must be objects'); continue
            if any(not isinstance(r.get('contract'), str) or not r['contract'] or
                   not isinstance(r.get('candidate_id'), str) or not r['candidate_id'] or
                   type(r.get('opportunity_index')) is not int or r['opportunity_index'] < 1 for r in rows):
                errors.append(label+': invalid opportunity identity'); continue
            keys = [record_key(r) for r in rows]
            keys_by_lane[lane] = set(keys)
            if len(keys) != len(set(keys)): errors.append(label+': duplicate opportunities')
            summary = summaries[lane]
            if not isinstance(summary, dict): errors.append(label+': summary must be an object'); continue
            if summary.get('signals') != len(rows): errors.append(label+': signal count mismatch')
            contracts = len({r['contract'] for r in rows})
            if contracts > counts[0]: errors.append(label+': contracts exceed full-contract universe')
            exits = sum(r.get('exit' if family == WATCH else 'protected_exit_observed') is True for r in rows)
            if summary.get('frozen_exit_signals' if family == WATCH else 'protected_exit_signals') != exits:
                errors.append(label+': protected exit count mismatch')
            if family != WATCH:
                if summary.get('contracts') != contracts: errors.append(label+': contract count mismatch')
                scored = sum(r.get('movement_scoreable', True) is True for r in rows)
                if summary.get('movement_scoreable_entries') != scored: errors.append(label+': scoreable count mismatch')
                for lot, field in ((1, 'one_lot_taker_taker_avg_net_c'), (10, 'ten_lot_taker_taker_avg_net_c')):
                    calculated = average(net(r, lot) for r in rows if r.get('protected_exit_observed'))
                    published = number(summary.get(field))
                    if (calculated is None) != (published is None) or (calculated is not None and abs(calculated-published) > 1e-8):
                        errors.append(label+f': {lot}-lot conditional economics mismatch')
            else:
                if summary.get('warning_signals') != sum(r.get('warning') is True for r in rows):
                    errors.append(label+': warning count mismatch')
                for r in rows:
                    warning, exit_time, lead = (number(r.get(k)) for k in ('warning_time_sec', 'exit_time_sec', 'lead'))
                    expected_lead = exit_time-warning if warning is not None and exit_time is not None else None
                    if r.get('warning') is not (warning is not None) or r.get('exit') is not (exit_time is not None):
                        errors.append(label+': warning/exit availability mismatch'); break
                    if lead != expected_lead or (lead is not None and lead < 0):
                        errors.append(label+': warning lead mismatch'); break
        if len(keys_by_lane) != len(expected): continue
        anchor_keys = keys_by_lane[spec['anchor']]
        for lane, keys in keys_by_lane.items():
            if not keys <= anchor_keys: errors.append(f'{family}/{lane}: opportunities outside frozen anchor')
            if family == WATCH and keys != anchor_keys: errors.append(f'{family}/{lane}: missing Watch opportunities')
        if family == WATCH:
            anchor = {record_key(r): r for r in lanes[spec['anchor']]}
            for lane, rows in lanes.items():
                for r in rows:
                    c = anchor.get(record_key(r))
                    if c is None: continue
                    fields = ('exit', 'exit_time_sec', 'exit_gain', 'one_lot_taker_taker_net_c', 'ten_lot_taker_taker_net_c')
                    if any(r.get(k) != c.get(k) for k in fields):
                        errors.append(f'{family}/{lane}: frozen exit/economics changed'); break
    anchor_rows = audit.get('candidate_verify_v2', {}).get('V1_IMMEDIATE', [])
    if len(anchor_rows) != counts[1]: errors.append('Serial signal total differs from immediate anchor')
    if all(isinstance(r, dict) for r in anchor_rows):
        global_keys = {record_key(r) for r in anchor_rows}
        for family, lane in ((WATCH, 'V1_1C'), ('selective_pullback_v2', 'V1_IMMEDIATE_CONTROL')):
            rs = audit.get(family, {}).get(lane, [])
            if isinstance(rs, list) and all(isinstance(r,dict) for r in rs) and {record_key(r) for r in rs} != global_keys:
                errors.append(f'{family}: anchor differs from frozen serial universe')
        rs = audit.get('scalp2_economics_v2', {}).get('CONTROL_V1_SCALP2', [])
        second_keys = {record_key(r) for r in anchor_rows if r.get('opportunity_index') == 2}
        if isinstance(rs, list) and all(isinstance(r,dict) for r in rs) and {record_key(r) for r in rs} != second_keys:
            errors.append('SCALP-2 anchor differs from frozen opportunity #2 universe')
    return errors


def economic_comparison(shadow, control, full_contracts=0):
    by_control = {record_key(r): r for r in control}
    by_shadow = {record_key(r): r for r in shadow}
    pairs = [(r, by_control[record_key(r)]) for r in shadow if record_key(r) in by_control]
    protected_pairs = [(r, c) for r, c in pairs if r.get('protected_exit_observed') and c.get('protected_exit_observed')]
    omitted = [r for r in control if record_key(r) not in by_shadow]
    extra = [r for r in shadow if record_key(r) not in by_control]
    shadow_contracts = {r['contract'] for r in shadow}
    control_contracts = {r['contract'] for r in control}
    def delta(field, sign=1):
        return average(sign*(number(r.get(field))-number(c.get(field))) for r, c in pairs
                       if number(r.get(field)) is not None and number(c.get(field)) is not None)
    result = {
        'shadow_entries': len(shadow), 'control_entries': len(control), 'matched_entries': len(pairs),
        'shadow_only_entries': len(extra), 'control_only_entries': len(omitted),
        'signal_retention_vs_control': share(len(shadow), len(control)),
        'shadow_contracts': len(shadow_contracts), 'control_contracts': len(control_contracts),
        'contracts_lost_vs_control': len(control_contracts-shadow_contracts),
        'contracts_added_vs_control': len(shadow_contracts-control_contracts),
        'shadow_true_contract_coverage': share(len(shadow_contracts), full_contracts),
        'control_true_contract_coverage': share(len(control_contracts), full_contracts),
        'control_only_observed_plus10': sum(bool(r.get('plus10')) for r in omitted),
        'control_only_protected_exits': sum(bool(r.get('protected_exit_observed')) for r in omitted),
        'shadow_without_protected_exit': sum(not r.get('protected_exit_observed') for r in shadow),
        'control_without_protected_exit': sum(not r.get('protected_exit_observed') for r in control),
        'both_protected_exits': len(protected_pairs),
        'both_protected_exit_contracts': len({r['contract'] for r, _ in protected_pairs}),
        'only_shadow_protected_exit_on_matched_entry': sum(bool(r.get('protected_exit_observed')) and not c.get('protected_exit_observed') for r,c in pairs),
        'only_control_protected_exit_on_matched_entry': sum(bool(c.get('protected_exit_observed')) and not r.get('protected_exit_observed') for r,c in pairs),
        'paired_entry_price_improvement_c': delta('entry_ask', -100),
        'conditional_net_scope': 'paired observed protected exits only; not total P&L',
    }
    for lot, label in ((1, 'one_lot'), (10, 'ten_lot')):
        eligible = [(r,c) for r,c in protected_pairs if net(r,lot) is not None and net(c,lot) is not None]
        result[label+'_paired_net_observations'] = len(eligible)
        result[label+'_paired_net_contracts'] = len({r['contract'] for r,c in eligible})
        result[label+'_paired_net_delta_c'] = average(net(r,lot)-net(c,lot) for r,c in eligible)
        result[label+'_control_only_avg_net_c'] = average(net(r,lot) for r in omitted if r.get('protected_exit_observed'))
    return result


def warning_comparison(shadow, control):
    baseline = {record_key(r): r for r in control}
    pairs = [(r, baseline[record_key(r)]) for r in shadow if record_key(r) in baseline]
    leads = [(r,c) for r,c in pairs if number(r.get('lead')) is not None and number(c.get('lead')) is not None]
    def details(rows):
        warned = [r for r in rows if r.get('warning')]
        exited = [r for r in rows if r.get('exit')]
        return {'warnings': len(warned), 'exits': len(exited),
                'exits_without_warning': sum(not r.get('warning') for r in exited),
                'unresolved_warnings': sum(bool(r.get('unresolved_warning')) for r in warned),
                'new_high_recovery_proxy_count': sum(bool(r.get('recovered_new_high_after_warning')) for r in warned),
                'new_high_recovery_proxy_rate': share(sum(bool(r.get('recovered_new_high_after_warning')) for r in warned), len(warned)),
                'exits_with_ge5s_lead_rate': share(sum(number(r.get('lead')) is not None and r['lead'] >= 5 for r in exited), len(exited))}
    return {'matched_opportunities': len(pairs), 'paired_warned_exits': len(leads),
            'paired_warned_exit_contracts': len({r['contract'] for r,c in leads}),
            'paired_lead_improvement_sec': average(r['lead']-c['lead'] for r,c in leads),
            'at_least_5s_earlier_pairs': sum(r['lead']-c['lead'] >= 5 for r,c in leads),
            'at_least_5s_later_pairs': sum(c['lead']-r['lead'] >= 5 for r,c in leads),
            'shadow_warning_metrics': details(shadow), 'control_warning_metrics': details(control),
            'warning_without_exit_is_not_automatically_false': True,
            'exit_policy_unchanged': all((r.get('exit_time_sec'),r.get('exit_gain')) == (c.get('exit_time_sec'),c.get('exit_gain')) for r,c in pairs)}


def build_review(bundle, manifest):
    errors = validate(bundle, manifest)
    s = bundle['state']
    result = {'review_version': 'NEXTGEN_V2_READ_ONLY_REVIEW_1', 'captured_utc': bundle.get('captured_utc'),
              'window_id': s.get('window_id'), 'code_sha256': s.get('code_sha256'),
              'source_sha256': s.get('source_sha256'), 'valid_snapshot': not errors, 'integrity_errors': errors,
              'orders': False, 'automatic_promotion': False, 'same_sample_promotion': False,
              'winner_selected': False, 'later_fresh_certification_required': True,
              'comparisons': [], 'sample_floor_is_not_per_lane_sufficiency': True}
    if errors:
        result['status'] = 'BLOCKED_INVALID_SNAPSHOT'
        return result
    full, signals = s['future_full_contracts'], s['serial_signals']
    floor = full >= manifest['minimum_full_contracts'] and signals >= manifest['minimum_signals']
    before_cutoff = timestamp(bundle['captured_utc']) < timestamp(manifest['cutoff_utc'])
    result.update(future_full_contracts=full, serial_signals=signals, review_floor_met=floor,
                  remaining_full_contracts=max(0, manifest['minimum_full_contracts']-full),
                  remaining_serial_signals=max(0, manifest['minimum_signals']-signals),
                  status='PRE_CUTOFF' if before_cutoff else ('REVIEW_FLOOR_MET' if floor else ('WAITING_FOR_FULL_CONTRACT' if not full else 'EARLY_DATA')))
    audit = bundle['audit']['audit_records']
    for family, spec in manifest['families'].items():
        for experiment in spec['experiments']:
            for control in spec['controls']:
                left, right = audit[family][experiment], audit[family][control]
                compared = warning_comparison(left,right) if family == WATCH else economic_comparison(left,right,full)
                result['comparisons'].append({'family': family, 'experiment': experiment, 'control': control,
                    **compared})
    result['limitations'] = [
        'Same-window independent replays anchored to V1 serial opportunities, not executable portfolio P&L.',
        'Matched protected-exit averages exclude unresolved/unprotected outcomes; omissions and unique contracts are shown separately.',
        'Source audit does not include full raw paths or individual contract first-seen timestamps; causal replay and cutoff eligibility cannot be independently re-proved from these endpoints.',
        'No winner ranking, statistical significance claim, confidence bound, promotion or certification decision is made.',
        'A zero conditional delta for a SCALP-2 filter means retained trades use the same economics; omitted trades and coverage still matter.',
    ]
    return result


def markdown(review):
    def fmt(x): return '—' if x is None else f'{x:.3f}' if isinstance(x,float) else str(x)
    lines = ['# V2 read-only review', '', f"Captured: {review['captured_utc']}", '',
             f"Status: **{review['status']}**. Winner selected: **No**. No promotion.", '']
    if not review['valid_snapshot']:
        return '\n'.join(lines + ['Snapshot rejected; no performance comparison produced.', '', *['- '+e for e in review['integrity_errors']]])+'\n'
    lines += [f"Eligible full contracts: **{review['future_full_contracts']}**; serial signals: **{review['serial_signals']}**.",
              f"Remaining to overall review floor: {review['remaining_full_contracts']} contracts / {review['remaining_serial_signals']} signals. Per-lane sufficiency is not established.", '',
              'All price/economics values below are cents per contract. Net deltas use the both-protected-exit subset.', '',
              '| Family / experiment | Control | Matched entries | Both exits / contracts | Control-only entries | Entry improvement ¢ | 1-lot net Δ ¢ | 10-lot net Δ ¢ |',
              '| --- | --- | ---: | ---: | ---: | ---: | ---: | ---: |']
    for c in review['comparisons']:
        if c['family'] == WATCH: continue
        lines.append(f"| {c['family']} / {c['experiment']} | {c['control']} | {c['matched_entries']} | {c['both_protected_exits']} / {c['both_protected_exit_contracts']} | {c['control_only_entries']} | {fmt(c['paired_entry_price_improvement_c'])} | {fmt(c['one_lot_paired_net_delta_c'])} | {fmt(c['ten_lot_paired_net_delta_c'])} |")
    lines += ['', '| Watch experiment | Control | Paired exits / contracts | Lead improvement seconds | ≥5s earlier / later | Unresolved warnings, V2 / V1 |',
              '| --- | --- | ---: | ---: | ---: | ---: |']
    for c in review['comparisons']:
        if c['family'] != WATCH: continue
        lines.append(f"| {c['experiment']} | {c['control']} | {c['paired_warned_exits']} / {c['paired_warned_exit_contracts']} | {fmt(c['paired_lead_improvement_sec'])} | {c['at_least_5s_earlier_pairs']} / {c['at_least_5s_later_pairs']} | {c['shadow_warning_metrics']['unresolved_warnings']} / {c['control_warning_metrics']['unresolved_warnings']} |")
    lines += ['', '## Interpretation limits', '', *['- '+x for x in review['limitations']], '',
              'Detailed omissions, protected-exit availability and new-high recovery proxy counts/rates are in review.json. Raw API responses are preserved in bundle.json.', '',
              '## CURRENT STATE', '', '- CONTROL: Read-only comparison; no collector writes.',
              '- NEW SHADOW: Existing V2 snapshot inspected; this tool is offline and undeployed.',
              '- BLOCKED: Further evidence is required before any prospective certification consideration.',
              '- NEXT STEP: Review a later coherent snapshot without changing the frozen experiment.']
    return '\n'.join(lines)+'\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=MANIFEST_PATH)
    parser.add_argument('--bundle', type=Path, help='Review an archived capture without network access')
    parser.add_argument('--output', type=Path, help='New output directory; existing directories are never overwritten')
    args = parser.parse_args(argv)
    manifest = json.loads(args.manifest.read_text())
    try:
        bundle = json.loads(args.bundle.read_text()) if args.bundle else coherent_capture(http_reader(manifest['service_url']), manifest)
        review = build_review(bundle, manifest)
        directory = args.output or Path(__file__).parent/'captures'/datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        directory.mkdir(parents=True, exist_ok=False)
        for name, content in (('bundle.json', bundle), ('review.json', review)):
            (directory/name).write_text(json.dumps(content, indent=2, sort_keys=True, allow_nan=False)+'\n')
        (directory/'review.md').write_text(markdown(review))
        print(json.dumps({'status': review['status'], 'output': str(directory.resolve()),
                          'integrity_errors': review['integrity_errors'], 'comparisons': len(review['comparisons']),
                          'orders': False, 'winner_selected': False}))
        return 0 if review['valid_snapshot'] else 2
    except (OSError, ValueError, KeyError, TypeError) as exc:
        # Avoid echoing source URLs or arbitrary remote bodies into logs.
        print(json.dumps({'status': 'CAPTURE_OR_REVIEW_FAILED', 'error_type': type(exc).__name__, 'orders': False}))
        return 2


if __name__ == '__main__': raise SystemExit(main())
