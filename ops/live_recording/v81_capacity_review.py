"""Read-only V81 recorder capacity screening from bounded observed receipts.

This is a failure-window projection, NEVER authorization to change production
quotas, size a purchase, start a live recorder, or treat synthetic tests as
full-day qualification. No network, no filesystem mutation or source reduction.
"""
import argparse
import json
import math
from pathlib import Path

from .policy import PROFILES, MiB, GiB

DAY_HORIZON = PROFILES['day']['seconds']
PRE_HORIZON = PROFILES['preflight']['seconds']
MARGIN = 1.5
RECORD_RESERVE = 4
COMPRESSED_RESERVE = 6 * MiB
DECODED_RESERVE = 5 * MiB


def positive_finite(value, label):
    if type(value) not in (int, float) or not math.isfinite(value) or value <= 0:
        raise ValueError('BAD_MEASUREMENT:' + label)
    return value


def review_v81(snapshot):
    """Conservative screening only: failed start-up rates are NOT steady-state."""
    seconds = positive_finite(snapshot['elapsed'], 'elapsed')
    records = positive_finite(snapshot['records'], 'records')
    raw = positive_finite(snapshot['raw_bytes'], 'raw_bytes')
    compressed = positive_finite(snapshot['compressed_bytes'], 'compressed_bytes')
    losses = snapshot.get('writer', {}).get('losses', {})
    if type(losses) is not dict or any(type(v) is not int or v < 0 for v in losses.values()):
        raise ValueError('BAD_LOSS_COUNTERS')
    lost = sum(losses.values())
    # This is a lower bound because status snapshots may expose only the
    # latest loss delta, and some native events may not reach admission.
    attempted_lower_bound = records + lost
    rates = dict(recorded_records_per_sec=records / seconds,
                 attempted_records_per_sec_at_least=attempted_lower_bound / seconds,
                 raw_bytes_per_sec=raw / seconds,
                 old_codec_compressed_bytes_per_sec=compressed / seconds)
    profiles = {}
    for name, horizon in (('preflight', PRE_HORIZON), ('day', DAY_HORIZON)):
        profile = PROFILES[name]
        count_cap = profile['records'] // 4
        decoded_cap = profile['decoded'] // 4
        byte_cap = profile['compressed']['v81']
        # Old-codec bytes are illustrative only. Batched codec size MUST be
        # measured separately, with independent raw-file hash verification.
        projected = dict(
            recorded_records=math.ceil(rates['recorded_records_per_sec'] * horizon * MARGIN),
            admitted_demand_lower_bound=math.ceil(rates['attempted_records_per_sec_at_least'] * horizon * MARGIN),
            decoded_bytes=math.ceil(rates['raw_bytes_per_sec'] * horizon * MARGIN),
            old_codec_compressed_bytes=math.ceil(rates['old_codec_compressed_bytes_per_sec'] * horizon * MARGIN))
        capacity = dict(records=count_cap-RECORD_RESERVE,
                        decoded_bytes=decoded_cap-DECODED_RESERVE,
                        compressed_bytes=byte_cap-COMPRESSED_RESERVE)
        failures = []
        if projected['recorded_records'] >= capacity['records']:
            failures.append('RECORD_CAP_EXTRAPOLATION_EXCEEDED')
        if projected['decoded_bytes'] >= capacity['decoded_bytes']:
            failures.append('DECODED_CAP_EXTRAPOLATION_EXCEEDED')
        if projected['old_codec_compressed_bytes'] >= capacity['compressed_bytes']:
            failures.append('OLD_CODEC_COMPRESSED_CAP_EXTRAPOLATION_EXCEEDED')
        profiles[name] = dict(seconds=horizon, projected=projected,
                              reviewed_limits=capacity,
                              extrapolated_limits_within_profile=not failures,
                              blockers=failures)
    known_failed = bool(snapshot.get('failure')) or bool(lost) or bool(
        snapshot.get('writer', {}).get('archive_failed')) or snapshot.get('stopped') is False
    return dict(
        schema='BTC15_V81_FAILED_WINDOW_CAPACITY_SCREEN_V1',
        source='V81_TERMINAL_STATUS_PARTIAL_FAILED_WINDOW',
        sample_seconds=seconds, sample_records=records, observed_losses=losses,
        observed_failure=snapshot.get('failure'), observed_stopped=snapshot.get('stopped'),
        rates=rates, profiles=profiles, uncertainty=dict(
            startup_failure_window_only=True, real_peak_rate_unknown=True,
            lifetime_loss_count_may_be_larger=True,
            observed_old_codec_only=True, batched_codec_not_measured=True,
            original_input_distribution_unavailable=True),
        status='NO_GO_UNQUALIFIED', qualified_24h=False,
        hard_blockers=['INCOMPLETE_LIVE_CAPTURE' if known_failed else 'SHORT_SAMPLE_NOT_24H_QUALIFICATION',
                       'NO_VERIFIED_LOSSLESS_NATIVE_EVIDENCE_RATE',
                       'NO_COMPLETE_20_MIN_SEALED_RETRIEVED_REPORT',
                       'NO_INDEPENDENT_DAY_READER_CAPACITY_QUALIFICATION'],
        minimum_next_steps=[
            'Verify existing preserved original V81 segments against hashes; retain documented losses.',
            'Measure realistic payload distribution, admitted events and durable rate including 15m rollover.',
            'Establish reviewed role limits with independent runtime disk headroom and reporter storage.',
            'Run an authorized 20-minute preflight; require every role seal, zero gaps and independent report.'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--receipt', required=True, help='local READ-ONLY terminal-status.json')
    a = parser.parse_args()
    print(json.dumps(review_v81(json.loads(Path(a.receipt).read_text())),
                     sort_keys=True, indent=2))


if __name__ == '__main__':
    main()
