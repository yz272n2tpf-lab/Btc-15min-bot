"""Descriptive ladder attribution on an already qualified common universe.

Removing a lane here measures unique observed coverage, not a refitted-model
ablation or causal predictive contribution. Labels never select calls.
"""
import argparse
from collections import Counter
import json
from pathlib import Path
from summarize_passive_acceptance import stamp, summary

LANES = ('early', 'final', 'scalp')


def contribution(report):
    registry = report['universe_registry']
    identified = [r['ticker'] for r in registry if r.get('official_identified')]
    if len(identified) != len(set(identified)):
        raise ValueError('Duplicate official contract in universe')
    universe = set(identified)
    calls = {}
    for lane in LANES:
        calls[lane] = {}
        for call in report['lanes'][lane]['calls']:
            ticker = call['contract']
            if ticker not in universe:
                raise ValueError('Call outside registered universe')
            if ticker in calls[lane]:
                raise ValueError('Multiple first calls for one lane/contract')
            calls[lane][ticker] = call
    union = set().union(*(set(calls[l]) for l in LANES))
    out = {}
    for lane in LANES:
        own = set(calls[lane])
        others = set().union(*(set(calls[l]) for l in LANES if l != lane))
        unique = own - others
        entries = list(calls[lane].values())
        labeled = [c for c in entries if c.get('official_result') in ('yes', 'no')]
        failures = [c for c in labeled if (c['side'] == 'UP') != (c['official_result'] == 'yes')]
        path = [c for c in entries if c.get('sampled_bid_path', {}).get('sample_count', 0)]
        out[lane] = dict(
            call_contracts=len(own), unique_contracts=sorted(unique),
            unique_coverage_increment_official=len(unique)/len(universe) if universe else None,
            union_without_lane=len(others), overlap_with_other_lanes=len(own & others),
            scheduled_coverage=len(own)/len(registry) if registry else None,
            direction_labeled=len(labeled), direction_failures=failures,
            direction_accuracy=(len(labeled)-len(failures))/len(labeled) if labeled else None,
            entry_ask=summary(c['entry_ask'] for c in entries),
            entry_le_45c=sum(c['entry_ask'] <= .45 for c in entries),
            entry_le_50c=sum(c['entry_ask'] <= .50 for c in entries),
            entry_25_to_35c=sum(.25 <= c['entry_ask'] <= .35 for c in entries),
            minutes_remaining=summary(c['minutes_remaining'] for c in entries),
            path_observed_contracts=len(path), path_missing_contracts=len(entries)-len(path),
            observed_positive_movement=sum(c['sampled_bid_path']['observed_mfe'] > 0 for c in path),
            observed_nonpositive_movement=sum(c['sampled_bid_path']['observed_mfe'] <= 0 for c in path),
            sampled_mfe=summary(c['sampled_bid_path']['observed_mfe'] for c in path),
            sampled_mae=summary(c['sampled_bid_path']['observed_mae'] for c in path),
            scalp_direction_is_secondary=(lane == 'scalp'),
        )
    pairs = {}
    for index, left in enumerate(LANES):
        for right in LANES[index+1:]:
            overlap = set(calls[left]) & set(calls[right])
            pairs[left+'+'+right] = dict(
                contracts=len(overlap), same_side=sum(calls[left][t]['side']==calls[right][t]['side'] for t in overlap),
                opposite_side=sum(calls[left][t]['side']!=calls[right][t]['side'] for t in overlap),
                right_minus_left_call_seconds=summary((stamp(calls[right][t]['observed_utc'])-
                    stamp(calls[left][t]['observed_utc'])).total_seconds() for t in overlap))
    first = Counter()
    for ticker in union:
        available = [(stamp(calls[l][ticker]['observed_utc']), l) for l in LANES if ticker in calls[l]]
        earliest = min(t for t,l in available)
        first['+'.join(l for t,l in available if t == earliest)] += 1
    return dict(cohort_id=report['cohort_id'], phase=report['phase'],
        scheduled_contract_slots=len(registry), official_contracts=len(universe),
        missing_official_slots=len(registry)-len(universe), union_call_contracts=len(union),
        no_call_official_contracts=sorted(universe-union), first_observed_lane=dict(first),
        ladders=out, pair_relationships=pairs,
        limitations=['Descriptive unique coverage is not causal predictive contribution.',
                    'First calls do not represent complete flip/reentry/lock or exit lifecycles.',
                    'Regime attribution requires source features joined at the original decision time.',
                    'Sampled MFE/MAE and nonpositive movement are censored; no fill, net profit or complete false-positive rate.',
                    'No production threshold/weight selection or acceptance is made.'],
        orders=False)


if __name__ == '__main__':
    parser=argparse.ArgumentParser();parser.add_argument('report',type=Path)
    parser.add_argument('--output',type=Path,required=True);args=parser.parse_args()
    result=contribution(json.loads(args.report.read_text()))
    with args.output.open('x') as stream:json.dump(result,stream,indent=2,allow_nan=False)
