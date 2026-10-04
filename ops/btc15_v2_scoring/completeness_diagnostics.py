"""Offline reporting axes. Never promotes strict eligibility or invokes strategy.

Input is the existing bridge report, after its identity/hash/census checks.
Schedule coverage describes recorded attempts, not continuous usable prices.
"""
from collections import Counter

SUMMARY_FLAGS = {'JOURNAL_MISSING_OR_PARTIAL', 'UNAVAILABLE_INTERVALS'}


def lane_diagnostic(row):
    unavailable = row['unavailable_publications']
    reasons = set(row['missing']) - SUMMARY_FLAGS
    absent = row['coverage'] is None and row['observation_count'] == 0
    if absent:
        # An asynchronous snapshot pair may contain a later slot in one lane.
        # This is absence, not evidence of corrupted census within the other DB.
        reasons = {'NOT_IN_LANE_SNAPSHOT'}
    elif ('JOURNAL_MISSING_OR_PARTIAL' in row['missing']
          and not unavailable and not reasons):
        reasons.add('UNEXPLAINED_JOURNAL_PARTIAL_FLAG')
    schedule_covered = not reasons and not absent
    state = ('NOT_IN_LANE_SNAPSHOT' if absent else
             'PARTIAL_OBSERVATION_SCHEDULE' if reasons else
             'OBSERVATION_SCHEDULE_COVERED_WITH_UNAVAILABLE' if unavailable else
             'OBSERVATION_SCHEDULE_COVERED')
    cov = row['coverage'] or {}
    calls = row.get('final', {}).get('calls', [])
    early = row.get('early', {}).get('qualified', [])
    scalp = row.get('scalp', {}).get('events', [])
    return dict(
        observation_state=state, observation_schedule_covered=schedule_covered,
        observation_limitations=sorted(reasons),
        original_missing=list(row['missing']),
        first_observation_delay_seconds=(cov['first_at']-row['opened']) if cov.get('first_at') is not None else None,
        last_observation_to_close_seconds=(row['closed']-cov['last_at']) if cov.get('last_at') is not None else None,
        publication_gap_count=len(row['publication_gaps']),
        source_availability=dict(observations=row['observation_count'], unavailable=unavailable,
            recorded_without_unavailable=row['observation_count']-unavailable,
            reasons=dict(Counter(u['reason'] for u in row['unavailable_observations']))),
        settlement_state=('AUTHORITATIVE_LINKED' if row['settled'] else
                          'NOT_IN_LANE_SNAPSHOT' if absent else
                          cov.get('settlement_status', 'PENDING_OR_UNLINKED')),
        observed_events=dict(early_origins=len(early), final_publications=len(calls), scalp_origins=len(scalp)),
        strict_fully_scoreable=row['fully_scoreable'],
        # Observed calls can be assessed against their own linked settlement.
        # Partial windows do not establish the first actual call or coverage.
        first_retained_final_call=(dict(publication_id=calls[0]['publication_id'],
            signal_ts=calls[0]['signal_ts'], side=calls[0]['independent_final']['side'],
            correct=calls[0]['correct'], ref=calls[0]['ref']) if calls else None),
        pass_scope='RECORDED_PUBLICATIONS_ONLY; UNAVAILABLE_IS_NOT_PASS',
    )


def diagnose(report):
    contracts=[]
    for contract in report['contracts']:
        lanes={lane:lane_diagnostic(row) for lane,row in contract['lanes'].items()}
        contracts.append(dict(contract=contract['contract'], opened=contract['opened'], lanes=lanes))
    summaries={}
    for lane in ('main','v81'):
        rows=[c['lanes'][lane] for c in contracts]
        settled=[r for r in rows if r['settlement_state']=='AUTHORITATIVE_LINKED']
        first=[r['first_retained_final_call'] for r in settled if r['first_retained_final_call']]
        summaries[lane]=dict(
            observation_states=dict(Counter(r['observation_state'] for r in rows)),
            settlement_states=dict(Counter(r['settlement_state'] for r in rows)),
            settled_observation_schedule_covered=sum(r['observation_schedule_covered'] for r in settled),
            observed_settled_final_publications=sum(r['observed_events']['final_publications'] for r in settled),
            settled_contracts_with_retained_final_calls=len(first),
            first_retained_final_correct=sum(r['correct'] is True for r in first),
            first_retained_final_incorrect=sum(r['correct'] is False for r in first),
            observed_early_origins=sum(r['observed_events']['early_origins'] for r in rows),
            observed_scalp_origins=sum(r['observed_events']['scalp_origins'] for r in rows),
        )
    return dict(schema='BTC15_V2_COMPLETENESS_DIAGNOSTICS_V1',
        evidence_class=report['evidence_class'], lanes=summaries, contracts=contracts,
        strict_counts_unchanged=dict(report['counts']),
        meaning='Recorded attempts, usable sources, settlement, and retained calls are separate axes.',
        reliability_claim=None, new_complete_cohort_claim=False,
        source_limit='Derived from validated bridge output; does not replace raw snapshot validation.',
        signal_only=True, orders=False)
