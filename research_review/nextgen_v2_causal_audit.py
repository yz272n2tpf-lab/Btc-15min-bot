#!/usr/bin/env python3
"""Offline synthetic mechanism audit of the unchanged, fingerprint-pinned V2.

Exercises event-time prefixes, future suffixes, outcome-label independence and
hand-specified boundaries. No raw live tape or efficacy/certification claim.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import importlib
import json
import math
import random
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = Path(__file__).with_name('nextgen_v2_manifest.json')
T0 = datetime(2030, 1, 1, tzinfo=timezone.utc)  # Synthetic clocks only.
SEED = 20260916
GENERATED_TAPES = 40


def fingerprint():
    digest = hashlib.sha256()
    files = sorted(ROOT.glob('shadow_diagnostics/*.py')) + [ROOT / 'requirements.txt', ROOT / 'railway.json']
    for path in files:
        digest.update(str(path.relative_to(ROOT)).encode() + b'\0' + path.read_bytes() + b'\0')
    return digest.hexdigest()


def load_core():
    directory = str(ROOT / 'shadow_diagnostics')
    if directory not in sys.path:
        sys.path.insert(0, directory)
    return importlib.import_module('scalp_nextgen_v2_core')


def make_op(ask=.45, strong=False, points=(), index=1):
    candidate = {'timestamp_utc': T0.isoformat(), 'confirm_count': 2 if strong else 1,
                 'structure_ok': True, 'brti_status': 'PRIMARY_OK',
                 'btc_against_side': False, 'brti_against_side': False, 'dual_reversal_evidence': False}
    op = {'contract': 'SYNTHETIC_ONLY', 'candidate_id': 'FIXTURE', 'opportunity_index': index,
          'entry_ask': ask, 'seconds_left': 600, 'btc_move5_norm': .8, 'btc_move15_norm': .7,
          '_candidate': candidate, '_paths': [], 'protected_exit_gain': None,
          'peak_gain': None, 'adverse_gain': None}
    op['_paths'] = [quote(op, *point) for point in points]
    return op


def quote(op, elapsed, bid, ask=None):
    return {'elapsed_sec': elapsed, 'timestamp_utc': (T0 + timedelta(seconds=elapsed)).isoformat(),
            'current_bid': bid, 'current_ask': min(1., bid + .005) if ask is None else ask,
            'exec_gain': bid - op['entry_ask']}


def decision_view(decision):
    return None if decision is None else (decision['entry_elapsed_sec'], decision['entry_ask'], decision['decision_reason'])


def same(left, right):
    if left is None or right is None:
        return left is right
    if isinstance(left, (tuple, list)) and isinstance(right, (tuple, list)):
        return len(left) == len(right) and all(same(a, b) for a, b in zip(left, right))
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=0, abs_tol=1e-10)
    return left == right


class Checks:
    def __init__(self):
        self.groups = {}
        self.failures = []

    def compare(self, group, name, actual, expected):
        counts = self.groups.setdefault(group, {'checks': 0, 'failures': 0})
        counts['checks'] += 1
        if not same(actual, expected):
            counts['failures'] += 1
            if len(self.failures) < 50:
                self.failures.append({'group': group, 'case': name,
                                      'actual': repr(actual)[:800], 'expected': repr(expected)[:800]})


def reference_exit(op, entry_ask=None, entry_time=0, watch=True):
    """Independent oracle on CLEAN synthetic quotes; no frozen exit helper calls."""
    peak = -math.inf
    armed = False
    for row in op['_paths']:
        if row['elapsed_sec'] < entry_time:
            continue
        gain = row['exec_gain'] if watch else row['current_bid'] - entry_ask
        peak = max(peak, gain)
        armed = armed or peak >= (.05 - 1e-12 if watch else .05)
        if armed and peak - gain >= .04 - 1e-12:
            return row['elapsed_sec'], gain
    return None, None


def boundary_checks(core, checks):
    weak = lambda points: make_op(points=points)
    verify = [
        ('strong_no_future', make_op(strong=True), (0, .45, 'IMMEDIATE_STRONG')),
        ('weak_no_future', weak([]), None),
        ('one_event', weak([(2, .46)]), None),
        ('two_flat_events', weak([(2, .45), (4, .45)]), None),
        ('two_events_plus1', weak([(2, .45), (4, .46)]), (4, .465, 'EVENT_CONFIRMED')),
        ('timeout_exact', weak([(26, .46), (30, .46)]), (30, .465, 'EVENT_CONFIRMED')),
        ('timeout_exceeded', weak([(26, .46), (30.001, .46)]), None),
        ('gap_exact', weak([(2, .46), (7, .46)]), (7, .465, 'EVENT_CONFIRMED')),
        ('gap_exceeded', weak([(2, .46), (7.001, .46)]), None),
        ('chase_exact', weak([(2, .46, .48), (4, .46, .48)]), (4, .48, 'EVENT_CONFIRMED')),
        ('chase_exceeded', weak([(2, .46, .48001), (4, .46, .48001)]), None),
        ('drawdown_resets', weak([(2, .46), (3, .44), (4, .46)]), None),
        ('crossed_quote_resets', weak([(2, .46), (3, .49, .48), (4, .46)]), None),
        ('zero_time_not_confirmation', weak([(0, .46), (4, .46)]), None),
    ]
    for name, op, expected in verify:
        checks.compare('verify_boundaries', name, decision_view(core.dynamic_verify_decision(op)), expected)
    for flag in ('btc_against_side', 'brti_against_side', 'dual_reversal_evidence'):
        for value in (True, None):
            op = make_op(strong=True); op['_candidate'][flag] = value
            checks.compare('verify_boundaries', f'{flag}_{value}', core.dynamic_verify_decision(op), None)
    for name, change in (
        ('missing_bid', lambda p: p.pop('current_bid')),
        ('missing_ask', lambda p: p.pop('current_ask')),
        ('invalid_timestamp', lambda p: p.update(timestamp_utc='not-a-clock')),
        ('inconsistent_clock', lambda p: p.update(timestamp_utc=T0.isoformat())),
    ):
        op = weak([(2, .46), (4, .46)]); change(op['_paths'][1])
        checks.compare('verify_boundaries', name, core.dynamic_verify_decision(op), None)
    op = weak([(2, .46), (4, .46)])
    op['_paths'][1]['timestamp_utc'] = op['_paths'][0]['timestamp_utc']
    checks.compare('verify_boundaries', 'duplicate_stamp', core.dynamic_verify_decision(op), None)

    for lane in core.PULLBACK_MODES:
        cases = [
            ('affordable_exact', make_op(ask=.50), (0, .50, 'IMMEDIATE_AFFORDABLE')),
            ('expensive_no_future', make_op(ask=.50001), None),
            ('pullback_price_exact', make_op(ask=.65, points=[(30, .495, .50)]), (30, .50, 'SELECTIVE_PULLBACK_LE50')),
            ('pullback_price_exceeded', make_op(ask=.65, points=[(30, .495, .50001)]), None),
            ('zero_time_pullback', make_op(ask=.65, points=[(0, .495, .50)]), None),
            ('short_window_exact', make_op(ask=.60, points=[(30, .495, .50)]), (30, .50, 'SELECTIVE_PULLBACK_LE50')),
            ('short_window_exceeded', make_op(ask=.60, points=[(30.001, .495, .50)]), None),
        ]
        for name, op, expected in cases:
            checks.compare('pullback_boundaries', lane + '/' + name, decision_view(core.selective_pullback_decision(op, lane)), expected)
        op = make_op(ask=.65, strong=True)
        expected = (0, .65, 'IMMEDIATE_STRONG') if lane == 'V2_BALANCED' else None
        checks.compare('pullback_boundaries', lane + '/expensive_strong', decision_view(core.selective_pullback_decision(op, lane)), expected)
        for elapsed in (60, 60.001):
            op = make_op(ask=.65, points=[(elapsed, .495, .50)])
            expected = (60, .50, 'SELECTIVE_PULLBACK_LE50') if lane == 'V2_PRICE_DISCIPLINED' and elapsed == 60 else None
            checks.compare('pullback_boundaries', f'{lane}/long_window_{elapsed}', decision_view(core.selective_pullback_decision(op, lane)), expected)

    for index, ask, left, strong in ((1, .45, 600, True), (2, .50, 360, True),
                                    (2, .50001, 600, True), (2, .50, 359.999, False)):
        op = make_op(ask=ask, strong=strong, index=index); op['seconds_left'] = left
        counts = tuple(len(core.scalp2_records([op])[lane]) for lane in core.SCALP2_MODES)
        wanted = (int(index == 2), int(index == 2 and ask <= .50),
                  int(index == 2 and ask <= .50 and left >= 360), int(index == 2 and ask <= .50 and strong))
        checks.compare('scalp2_boundaries', f'{index}/{ask}/{left}/{strong}', counts, wanted)

    op = make_op(points=[(2, .53), (4, .527), (6, .524), (8, .521), (10, .49)])
    for mode, warning in zip(core.WATCH_MODES, (10, 10, 10, 8, 6)):
        row = core.watch_measure(op, mode)
        checks.compare('watch_boundaries', mode + '/warning', row['warning_time_sec'], warning)
        checks.compare('watch_boundaries', mode + '/exit', (row['exit_time_sec'], row['exit_gain']), (10, .04))
    # A pre-entry 20-cent peak must not arm a later pullback entry's exit.
    op = make_op(ask=.65, points=[(2, .85, .86), (8, .48, .485), (12, .50, .505)])
    row = core.selective_pullback_record(op, 'V2_PRICE_DISCIPLINED')
    checks.compare('score_boundaries', 'exclude_pre_entry_peak', (row['entry_elapsed_sec'], row['peak_gain'], row['protected_exit_observed']), (8, .015, False))


def generated_checks(core, checks, count=GENERATED_TAPES):
    rng = random.Random(SEED)
    decisions = {'VERIFY': core.dynamic_verify_decision,
                 **{lane: (lambda op, lane=lane: core.selective_pullback_decision(op, lane)) for lane in core.PULLBACK_MODES}}
    for sample in range(count):
        ask = rng.choice((.35, .45, .50, .55, .60, .65))
        op = make_op(ask=ask, strong=bool(sample % 3 == 0), index=2)
        elapsed, bid = 0., ask - .005
        for _ in range(18):
            elapsed += rng.choice((1., 2., 4., 6.))
            bid = round(max(.02, min(.95, bid + rng.choice((-.08, -.02, -.005, 0, .005, .02, .08)))), 6)
            op['_paths'].append(quote(op, elapsed, bid))
        before = copy.deepcopy(op)
        for lane, decide in decisions.items():
            full = decide(op)
            for length in range(len(op['_paths']) + 1):
                prefix = copy.deepcopy(op); prefix['_paths'] = prefix['_paths'][:length]
                cutoff = prefix['_paths'][-1]['elapsed_sec'] if length else 0
                expected = full if full is not None and full['entry_elapsed_sec'] <= cutoff else None
                checks.compare('decision_prefix', f'{sample}/{lane}/{length}', decision_view(decide(prefix)), decision_view(expected))
            poisoned = copy.deepcopy(op)
            poisoned.update(plus5=1, plus10=1, plus20=1, protected_exit_gain=.99, peak_gain=.99, adverse_gain=-.99)
            for row in poisoned['_paths']:
                row['exec_gain'] = rng.choice((-.99, .99))
            checks.compare('decision_outcome_independence', f'{sample}/{lane}', decision_view(decide(poisoned)), decision_view(full))
            duplicated = copy.deepcopy(op); duplicated['_paths'] *= 2
            checks.compare('duplicate_evidence', f'{sample}/{lane}', decision_view(decide(duplicated)), decision_view(full))
            shuffled = copy.deepcopy(op); rng.shuffle(shuffled['_paths'])
            checks.compare('event_time_order', f'{sample}/{lane}', decision_view(decide(shuffled)), decision_view(full))
            if full is not None:
                end = full['entry_elapsed_sec']
                suffix = copy.deepcopy(op); suffix['_paths'] = [r for r in suffix['_paths'] if r['elapsed_sec'] <= end]
                suffix['_paths'] += [quote(op, end + n, bid) for n, bid in ((1, .01), (2, .95), (3, .02))]
                checks.compare('decision_future_suffix', f'{sample}/{lane}', decision_view(decide(suffix)), decision_view(full))
                scored = core.score_entry(op, full)
                expected = reference_exit(op, full['entry_ask'], end, watch=False)
                checks.compare('entry_exit_oracle', f'{sample}/{lane}', (scored['protected_exit_elapsed_sec'], scored['protected_exit_gain']), expected)
        for mode in core.WATCH_MODES:
            full = core.watch_measure(op, mode)
            checks.compare('watch_exit_oracle', f'{sample}/{mode}', (full['exit_time_sec'], full['exit_gain']), reference_exit(op))
            for length in range(len(op['_paths']) + 1):
                prefix = copy.deepcopy(op); prefix['_paths'] = prefix['_paths'][:length]
                cutoff = prefix['_paths'][-1]['elapsed_sec'] if length else 0
                actual = core.watch_measure(prefix, mode)
                expected = tuple(full[key] if full[key] is not None and full[key] <= cutoff else None for key in ('warning_time_sec', 'exit_time_sec'))
                checks.compare('watch_prefix', f'{sample}/{mode}/{length}', (actual['warning_time_sec'], actual['exit_time_sec']), expected)
        # Selection membership is allowed to depend on candidate facts, never outcome labels.
        original = tuple(len(rows) for rows in core.scalp2_records(opps=[op]).values())
        poisoned = copy.deepcopy(op); poisoned.update(plus10=1, protected_exit_gain=.2, peak_gain=.3)
        checks.compare('scalp2_outcome_independence', str(sample), tuple(len(rows) for rows in core.scalp2_records([poisoned]).values()), original)
        checks.compare('input_immutability', str(sample), op, before)


def run_audit(manifest, core=None, count=GENERATED_TAPES):
    actual_sha = fingerprint()
    report = {'audit_version': 'NEXTGEN_V2_SYNTHETIC_CAUSAL_1', 'code_sha256': actual_sha,
              'expected_code_sha256': manifest['code_sha256'], 'collector_commit': manifest['commit'],
              'orders': False, 'production_changes': False, 'automatic_promotion': False,
              'same_sample_promotion': False, 'winner_selected': False,
              'market_efficacy_established': False, 'live_raw_tape_audited': False,
              'certification_passed': False, 'seed': SEED, 'generated_tapes': count,
              'groups': {}, 'checks': 0, 'failures': [], 'failure_count': 0}
    if actual_sha != manifest['code_sha256']:
        report.update(status='BLOCKED_CODE_DRIFT', failure_count=1, failures=[{'case': 'source_fingerprint'}])
        return report
    core = core or load_core()
    checks = Checks()
    checks.compare('frozen_constants', 'arm_giveback', (core.ARM_GAIN, core.EXIT_GIVEBACK), (.05, .04))
    boundary_checks(core, checks)
    generated_checks(core, checks, count)
    checks.compare('source_integrity', 'fingerprint_after', fingerprint(), actual_sha)
    report.update(groups=checks.groups, checks=sum(group['checks'] for group in checks.groups.values()),
                  failure_count=sum(group['failures'] for group in checks.groups.values()), failures=checks.failures)
    report['status'] = 'MECHANISM_TESTS_FAIL' if report['failure_count'] else 'MECHANISM_TESTS_PASS'
    report['limitations'] = [
        'Synthetic deterministic fixtures test mechanics only, not efficacy, fill feasibility, latency, or market coverage.',
        'Prefixes are clean event-time prefixes. Receipt ordering, provider revisions and delayed/backdated rows are not validated here.',
        'Frozen Watch uses existing exec_gain semantics; this audit does not replace the V1 event clock or validate feed construction.',
        'This does not independently verify live raw paths, candidate feature causality, serial-opportunity creation, or cutoff eligibility.',
        'Existing summary-only evidence lacks raw paths; later certification still needs a separate prospective freeze and source audit.',
    ]
    return report


def markdown(report):
    lines = ['# Frozen V2 synthetic causal audit', '', f"Status: **{report['status']}**.", '',
             f"Checks: {report['checks']}; failures: {report['failure_count']}; synthetic tapes: {report['generated_tapes']}.", '',
             'No market-efficacy or certification claim. No live raw tape audited.', '',
             '| Check group | Checks | Failures |', '| --- | ---: | ---: |']
    for name, group in report['groups'].items():
        lines.append(f"| {name} | {group['checks']} | {group['failures']} |")
    if report['failures']:
        lines += ['', 'Failures (up to 50 shown):', '', *['- ' + str(failure) for failure in report['failures']]]
    lines += ['', '## Limits', '', *['- ' + item for item in report.get('limitations', [])], '',
              '## CURRENT STATE', '', '- CONTROL: Source fingerprint checked before and after; no collector writes.',
              '- NEW SHADOW: Undeployed offline mechanism tests only.',
              '- BLOCKED: Prospective performance and live data causality are not established.',
              '- NEXT STEP: Preserve this audit and continue reviewing unchanged prospective evidence.']
    return '\n'.join(lines) + '\n'


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--manifest', type=Path, default=MANIFEST)
    parser.add_argument('--output', type=Path, required=True, help='New directory; never overwrite prior audit')
    args = parser.parse_args(argv)
    try:
        report = run_audit(json.loads(args.manifest.read_text()))
        args.output.mkdir(parents=True, exist_ok=False)
        (args.output / 'audit.json').write_text(json.dumps(report, indent=2, sort_keys=True, allow_nan=False) + '\n')
        (args.output / 'audit.md').write_text(markdown(report))
        print(json.dumps({'status': report['status'], 'checks': report['checks'],
                          'failures': report['failure_count'], 'output': str(args.output.resolve()), 'orders': False}))
        return 0 if report['status'] == 'MECHANISM_TESTS_PASS' else 2
    except (OSError, ValueError, KeyError, TypeError, ImportError) as exc:
        print(json.dumps({'status': 'AUDIT_FAILED', 'error_type': type(exc).__name__, 'orders': False}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
