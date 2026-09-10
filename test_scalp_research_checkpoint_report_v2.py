#!/usr/bin/env python3
"""Regression tests for scalp_research_checkpoint_report_v2.py."""

from scalp_research_checkpoint_report_v2 import parse_v6, summarize_grade


def result(*, gain='+0.100', hit10='False', hit20='False', to5='None', to10='None'):
    return (
        'LEAD_V6 RESULT | V6_QUALIFIED | TEST-CONTRACT | UP | zone PREFERRED_7_30C '
        f'| style BURST | entry 0.120 | max_exec_gain {gain} | adverse -0.010 '
        f'| hit10 {hit10} | hit20 {hit20} | to_exec+5c {to5} | to_exec+10c {to10} '
        '| to_exec+20c None | kalshi_reprice+5c None'
    )


def test_duplicate_result_is_counted_once():
    line = result(gain='+0.170', hit10='True', to5='8.0', to10='28.0')
    rows, _ = parse_v6([line, line])
    assert len(rows) == 1


def test_hit5_uses_execution_timing_not_rounded_gain():
    rows, _ = parse_v6([result(gain='+0.049', hit10='False', to5='12.0')])
    assert rows[0]['hit5'] is True


def test_hit10_uses_explicit_flag_not_displayed_gain_boundary():
    rows, _ = parse_v6([result(gain='+0.100', hit10='False', to5='10.0', to10='None')])
    assert rows[0]['hit10'] is False
    assert 'hit10=0.0%' in summarize_grade(rows, 'V6_QUALIFIED')


def test_hit10_within_30_seconds_requires_explicit_hit_and_timing():
    rows, _ = parse_v6([
        result(gain='+0.120', hit10='True', to5='6.0', to10='30.0'),
        result(gain='+0.150', hit10='True', to5='6.0', to10='31.0'),
    ])
    assert rows[0]['hit10_30s'] is True
    assert rows[1]['hit10_30s'] is False


def test_reject_snapshots_use_max_per_contract_not_sum():
    lines = [
        'LEAD_V6 MIDCONTRACT | C1 | V5 n=0 | V6 n=0 | rejects price=1 degraded=42 base=16 high=0',
        'LEAD_V6 MIDCONTRACT | C1 | V5 n=0 | V6 n=0 | rejects price=1 degraded=77 base=20 high=0',
        'LEAD_V6 MIDCONTRACT | C2 | V5 n=0 | V6 n=0 | rejects price=0 degraded=25 base=5 high=2',
    ]
    _, rejects = parse_v6(lines)
    assert rejects['price'] == 1
    assert rejects['degraded'] == 102
    assert rejects['base'] == 25
    assert rejects['high'] == 2


if __name__ == '__main__':
    tests = [obj for name, obj in sorted(globals().items()) if name.startswith('test_') and callable(obj)]
    for t in tests:
        t()
    print(f'{len(tests)}/{len(tests)} checkpoint V2 regression tests passed')
