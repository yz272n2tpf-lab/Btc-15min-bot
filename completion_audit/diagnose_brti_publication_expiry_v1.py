"""Infrastructure-only diagnosis of existing frozen evidence; never fit or score.

No price, side, model probability, entry, settlement, or outcome is analyzed.
An observer receipt is never substituted for a main-process receipt.
"""
import hashlib
import json
import statistics
from collections import Counter
from datetime import datetime
from pathlib import Path


def epoch(value):
    stamp = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if stamp.tzinfo is None:
        raise ValueError('timezone required')
    return stamp.timestamp()


def summary(values):
    a = sorted(values)
    return dict(n=len(a), minimum=min(a), median=statistics.median(a),
                p95=a[int(.95*(len(a)-1))], maximum=max(a)) if a else dict(n=0)


def fresh_at(original_decision, original_source, original_receipt, observed):
    """Fixed decision identity; repeating publication cannot renew its deadline."""
    return (original_source <= original_receipt <= original_decision <= observed
            and observed-original_source <= 5.0)


def analyze(directory):
    p = Path(directory)
    deliveries = [json.loads(r['message'].split(' | ', 1)[1])
                  for r in json.loads((p/'runtime_logs.json').read_text())['delivery']]
    decisions = {r['decision_utc']: r for r in deliveries}
    assert len(decisions) == len(deliveries) == 668
    start, end = map(epoch, ['2026-09-24T20:15:00Z', '2026-09-24T21:15:00Z'])
    first_seen, counts, expired_frames, examples = {}, Counter(), set(), []
    api_delays, ages, expired_excess, source_identity_errors = [], [], [], []
    expired_normal_or_long_hold = Counter()
    owner_first, owner_fresh = {}, 0
    owner_counters = []
    checked_rows = 0
    for line in (p/'records.jsonl').open():
        r = json.loads(line)
        now, s = epoch(r['response_received_utc']), r['state']
        assert start <= epoch(r['request_started_utc']) < end
        if r['service'] == 'owner':
            source = s['source_ts_ms']/1000
            owner_first.setdefault(source, r)
            owner_fresh += (s['status'] == 'PRIMARY_OK'
                            and s['clean_for_qualification'] is True
                            and 0 <= now-source <= 5)
            owner_counters.append([s['upstream_ok'], s['upstream_errors'], s['http_429']])
            continue
        if r['service'] != 'main':
            continue
        checked_rows += 1
        stamp = s['source_timestamp_utc']
        decision = epoch(stamp)
        if stamp not in first_seen:
            first_seen[stamp] = now
            if stamp in decisions:
                api_delays.append(now-decision)
        d = decisions.get(stamp)
        market, parity, health, safety = [s[k] for k in ('market', 'parity', 'health', 'safety')]
        source_age = now-decision
        close = decision+s['timer']['seconds_left']
        # Rounded seconds_left in the source CSV is used by the deployed observer.
        # Timestamp matching is additionally required against the delivery ledger.
        current = bool(d and d['ticker'] == s['contract'] and now < close)
        usable = (current and 0 <= source_age <= 15 and health['paired_quotes'] is True
                  and safety['read_only'] is True and safety['orders_enabled'] is False
                  and parity['status'] == 'PASS' and parity['contract'] == s['contract']
                  and parity['api_contract'] == s['contract']
                  and 0 <= now-epoch(parity['timestamp_utc']) <= 45)
        if not current:
            counts['rollover_prior_or_no_current_contract'] += 1
            continue
        source = d['source_ts']
        receipt = d['delivery']['observed_ts']
        assert source <= receipt <= decision
        assert d['ready'] is True and 0 <= decision-source <= 5
        if abs(decision-market['brti_age_seconds']-source) > 1e-6:
            source_identity_errors.append(stamp)
        if not usable:
            counts['quote_parity_or_source_wait'] += 1
            continue
        assert market['brti_ready'] is True
        if fresh_at(decision, source, receipt, now):
            counts['qualified'] += 1
        else:
            counts['otherwise_usable_but_retained_brti_expired'] += 1
            expired_frames.add(stamp)
            expired_excess.append(now-source-5)
            expired_normal_or_long_hold['within_5_181s_snapshot_age' if source_age <= 5.181
                                        else 'longer_retained_snapshot'] += 1
            if len(examples) < 3:
                examples.append(dict(original_decision_utc=stamp,
                    source_epoch=source, main_first_receipt_epoch=receipt,
                    observer_response_utc=r['response_received_utc'],
                    age_at_original_decision=decision-source,
                    age_at_observation=now-source,
                    expiry_epoch=source+5, next_decision_required=True))
        ages.append(now-source)
    assert not source_identity_errors
    assert checked_rows == 3600
    assert counts == dict(qualified=1504, otherwise_usable_but_retained_brti_expired=1754,
                         quote_parity_or_source_wait=237, rollover_prior_or_no_current_contract=105)
    # Strict best-case mathematical bound at unchanged decision clocks. This
    # deliberately assumes instantaneous source->main transport and publication,
    # and grants access to every owner publication by SOURCE time. It is NOT a
    # causal replay, candidate forecast, recovered observation, or validation win.
    # Even this unattainable advantage cannot fill every unchanged 5s interval.
    oracle_sources = sorted(owner_first)
    import bisect
    ideal_no_delay_bound = 0
    for line in (p/'records.jsonl').open():
        r = json.loads(line)
        if r['service'] != 'main':
            continue
        observed = epoch(r['response_received_utc'])
        j = bisect.bisect_right([epoch(x['decision_utc']) for x in deliveries], observed)-1
        if j < 0:
            continue
        decision = epoch(deliveries[j]['decision_utc'])
        i = bisect.bisect_right(oracle_sources, decision)-1
        if i >= 0 and observed-oracle_sources[i] <= 5:
            ideal_no_delay_bound += 1
    pairs = [(a,b) for a,b in zip(deliveries, deliveries[1:]) if a['ticker'] == b['ticker']]
    hashes = {name: hashlib.sha256((p/name).read_bytes()).hexdigest()
              for name in ('records.jsonl', 'runtime_logs.json', 'fair_inputs.jsonl', 'detailed_validation.json')}
    return dict(schema='BTC15_PUBLICATION_EXPIRY_MECHANISM_V1',
        evidence_role='IMMUTABLE_VALIDATION_INFRASTRUCTURE_DIAGNOSIS_ONLY',
        window=['2026-09-24T20:15:00Z','2026-09-24T21:15:00Z'], input_sha256=hashes,
        counts=dict(counts), original_decisions=len(deliveries),
        original_decisions_fresh_causal=sum(d['ready'] and d['source_ts'] <= d['delivery']['observed_ts'] <= epoch(d['decision_utc'])
                                         and 0 <= epoch(d['decision_utc'])-d['source_ts'] <= 5 for d in deliveries),
        retained_source_identity_mismatches=source_identity_errors,
        distinct_frames_observed_after_expiry=len(expired_frames),
        expiry_observations_by_retention=dict(expired_normal_or_long_hold),
        source_to_main_receipt_seconds=summary([d['delivery']['observed_ts']-d['source_ts'] for d in deliveries]),
        main_receipt_to_decision_seconds=summary([epoch(d['decision_utc'])-d['delivery']['observed_ts'] for d in deliveries]),
        brti_age_at_decision_seconds=summary([d['age_at_decision'] for d in deliveries]),
        original_decision_to_qualification_check_seconds=summary([d['delivery']['checked_ts']-epoch(d['decision_utc']) for d in deliveries]),
        decision_to_first_sampled_API_response_seconds=summary(api_delays),
        within_contract_decision_interval_seconds=summary([epoch(b['decision_utc'])-epoch(a['decision_utc']) for a,b in pairs]),
        expiry_duration_until_next_same_contract_decision_seconds=summary([max(0.,epoch(b['decision_utc'])-a['source_ts']-5) for a,b in pairs]),
        expired_observation_excess_seconds=summary(expired_excess),
        owner=dict(samples=len(owner_counters), fresh_samples=owner_fresh, distinct_source_publications=len(owner_first),
                   new_successes=owner_counters[-1][0]-owner_counters[0][0],
                   new_errors=owner_counters[-1][1]-owner_counters[0][1],
                   new_429=owner_counters[-1][2]-owner_counters[0][2],
                   distinct_source_step_seconds=summary([b-a for a,b in zip(oracle_sources,oracle_sources[1:])])),
        examples=examples,
        impossible_oracle_bound=dict(qualified_observation_instants=ideal_no_delay_bound, total=3600,
            percent=100*ideal_no_delay_bound/3600,
            meaning='Unattainable optimistic upper bound only: ignores receipt/transport delay, source-to-owner delay, API lag and ALL quote/parity waits; fixed real decision times and observed owner publications. NOT a proposed correction or causal replay.'),
        timing_identifiability='Owner HTTP request completion and all main 1s receipts were not journaled. Do not attribute combined source-to-main latency to transport alone, or borrow observer receipts as main receipts.',
        proof='At frozen decision d with source s<=receipt<=d, absolute deadline is s+5. Next complete decision d_next leaves max(0,d_next-(s+5)) expiry seconds. Repeating publication, resending state or relabeling generated_utc cannot change this deadline.',
        conclusion='Frozen 5s complete-decision cadence produces structural publication expiry. Decision-time BRTI availability is already 668/668; continuous retained-frame freshness is a different metric. Faster consumer/browser polling alone cannot remove the cadence floor.',
        strategy_analysis=False, strategy_changes=False, production_changes=False, signal_only=True, orders=False)


if __name__ == '__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('evidence_directory');args=parser.parse_args()
    print(json.dumps(analyze(args.evidence_directory), indent=2, allow_nan=False))
