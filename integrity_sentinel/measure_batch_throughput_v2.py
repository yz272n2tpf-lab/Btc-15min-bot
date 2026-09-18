"""Offline V2 measurements using the EXACT failed V1 realistic fixture.

The scheduling loop is the V1 harness policy (5s telemetry, 10s membership;
next deadline from cycle start), with all seven synthetic sources unchanged.
Additional instrumentation reports batch cost, p50, CPU, and fresh-process
read-only verification. History runs seed complete real membership/provenance
rows before measuring a new 3,072-event observation. No provider access.
"""
import argparse
import json
import math
import multiprocessing
import os
from pathlib import Path
import resource
import statistics
import tempfile
import time
from unittest.mock import patch

import requests
from integrity_sentinel.adversarial_body_dedup_v1 import runtime, synthetic_audit, endpoint, snapshot
from integrity_sentinel.measure_body_dedup_v1 import files
from integrity_sentinel.recorder_core_v1 import AppendOnlyHashChainLedger
from integrity_sentinel.membership_batch_v2 import BatchedMembershipLedger
from integrity_sentinel.nextgen_body_store_v1 import NextgenBodyStore


def verify_child(root, pipe):
    try:
        root = Path(root)
        before = snapshot(root)
        start, cpu = time.perf_counter(), time.process_time()
        body_store = NextgenBodyStore(root)
        membership = BatchedMembershipLedger(root / 'membership.jsonl', body_store)
        telemetry = AppendOnlyHashChainLedger(root / 'telemetry.jsonl')
        assert membership.status().chain_valid and telemetry.status().chain_valid
        known = body_store.verify()
        verification = {'wall_ms': (time.perf_counter() - start) * 1000,
                        'cpu_ms': (time.process_time() - cpu) * 1000,
                        'membership_records': membership._records, 'telemetry_records': telemetry._records,
                        'body_objects': len(known), 'pid': os.getpid(), 'verified': True}
        assert snapshot(root) == before
        verification['all_files_unchanged'] = True
        pipe.send(verification)
    except BaseException as exc:
        pipe.send({'error': repr(exc)})
    finally: pipe.close()


def process_verify(root):
    ctx = multiprocessing.get_context('spawn')
    reader, writer = ctx.Pipe(duplex=False)
    process = ctx.Process(target=verify_child, args=(str(root), writer))
    start = time.perf_counter()
    process.start()
    writer.close()
    assert reader.poll(60), 'fresh-process verification timed out'
    result = reader.recv()
    process.join(10)
    assert process.exitcode == 0 and result.get('verified'), result
    assert result['pid'] != os.getpid()
    result['including_process_start_ms'] = (time.perf_counter() - start) * 1000
    reader.close()
    return result


def percentiles(values):
    ordered = sorted(values)
    return {'p50': statistics.median(values) * 1000,
            'p95': ordered[math.ceil(.95 * len(ordered)) - 1] * 1000,
            'max': max(values) * 1000}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seconds', type=float, default=305)
    parser.add_argument('--history-batches', type=int, default=0)
    parser.add_argument('--cycles', type=int, default=6)
    args = parser.parse_args()
    assert args.seconds >= 0 and 0 <= args.history_batches <= 20
    timings, cpus, health, batch_timings, starts = [], [], [], [], []
    writes, syncs = [0], [0]
    real_write, real_sync = os.write, os.fsync
    def write(fd, raw):
        result = real_write(fd, raw)
        writes[0] += result
        return result
    def sync(fd):
        syncs[0] += 1
        return real_sync(fd)
    with tempfile.TemporaryDirectory(prefix='batch-throughput-measure-') as td, \
            patch.dict(os.environ, {}, clear=True), \
            patch.object(requests.adapters.HTTPAdapter, 'send', side_effect=AssertionError('network forbidden')):
        raw = synthetic_audit(192)
        assert len(raw) == 1634996
        r, adapter = runtime(td, raw)
        assert r.poll_sec == 5 and r.membership_poll_sec == 10
        history_cycle_ms = []
        for index in range(args.history_batches):
            # Distinct events and immutable objects with the same row shape.
            adapter.audit = synthetic_audit(192, 1000 + index).replace(b'"entry_ask":0.45', ('"entry_ask":' + f'{.10 + index / 100:.2f}').encode())
            start = time.perf_counter()
            r.run_cycle()
            assert endpoint(r)[0] == 200
            assert len(r.seen_membership) == (index + 1) * 3072
            history_cycle_ms.append((time.perf_counter() - start) * 1000)
        pre = files(Path(td))
        prior_membership_count = r.membership.status().records
        prior_event_count = len(r.seen_membership)
        original_batch = r.membership.append_batch
        def measured_batch(events):
            w, c, before_bytes, before_syncs = time.perf_counter(), time.process_time(), writes[0], syncs[0]
            rows = original_batch(events)
            batch_timings.append({'events': len(events), 'wall_ms': (time.perf_counter() - w) * 1000,
                'cpu_ms': (time.process_time() - c) * 1000, 'application_bytes': writes[0] - before_bytes,
                'fsync_calls': syncs[0] - before_syncs})
            return rows
        with patch.object(r.membership, 'append_batch', side_effect=measured_batch), \
                patch('os.write', side_effect=write), patch('os.fsync', side_effect=sync):
            start = time.monotonic()
            next_tick, next_membership = start, 0.
            observations = cycles = 0
            late = 0.
            first_sizes = None
            while True:
                now = time.monotonic()
                if args.seconds:
                    if now - start >= args.seconds: break
                    if now < next_tick:
                        time.sleep(min(1., next_tick - now))
                        continue
                    late = max(late, now - next_tick)
                    include = now >= next_membership
                else:
                    if cycles >= args.cycles: break
                    include = cycles % 2 == 0
                if include:
                    adapter.audit = synthetic_audit(192, observations // 6)
                    observations += 1
                starts.append(now - start)
                w, c = time.perf_counter(), time.process_time()
                r.run_cycle(include_membership=include)
                code, state = endpoint(r)
                timings.append(time.perf_counter() - w)
                cpus.append(time.process_time() - c)
                health.append({'cycle': cycles + 1, 'http_status': code, 'failures': state['health_failures']})
                assert state['orders'] is False and state['certifiable_evidence'] is False
                if cycles == 0: first_sizes = {'application_bytes': writes[0], **files(Path(td))}
                cycles += 1
                if args.seconds:
                    if include: next_membership = now + r.membership_poll_sec
                    next_tick = now + r.poll_sec
            elapsed = time.monotonic() - start
        measured = files(Path(td))
        observations_rows = [row['body'] for row in r.membership._iter_records()
            if row['sequence'] > prior_membership_count and row['body'].get('record_type') == 'SOURCE_OBSERVATION']
        counts = {name: sum(o['source'] == name for o in observations_rows) for name in
            ('early_membership', 'final_membership', 'combined_membership', 'nextgen_membership')}
        assert set(counts.values()) == {observations}
        assert len(r.seen_membership) - prior_event_count == 3072
        assert len(batch_timings) == 1 and batch_timings[0]['events'] == 3072
        r.session.close()
        reopened = process_verify(td)
        expected_cycles = math.ceil(args.seconds / 5) if args.seconds else args.cycles
        expected_observations = math.ceil(args.seconds / 10) if args.seconds else math.ceil(args.cycles / 2)
        # Include cold start once in finite-window projection. A separate rate
        # excludes that first cycle; neither is an unbounded-capacity claim.
        retained_growth = measured['retained_bytes'] - pre['retained_bytes']
        report = {'scenario': vars(args), 'body_bytes': len(raw), 'new_membership_events': 3072,
            'prepopulated_events': prior_event_count, 'history_prepopulation_cycle_ms': history_cycle_ms,
            'prepopulated': pre, 'telemetry_cycles': cycles, 'expected_telemetry_cycles': expected_cycles,
            'membership_observations_per_source': counts, 'expected_membership_per_source': expected_observations,
            'elapsed_seconds': elapsed, 'healthy_cycles': sum(h['http_status'] == 200 for h in health),
            'unhealthy_cycles': [h for h in health if h['http_status'] != 200],
            'cycle_start_seconds': starts, 'cycle_wall_ms': [v * 1000 for v in timings],
            'cycle_cpu_ms': [v * 1000 for v in cpus], 'wall_ms': percentiles(timings), 'cpu_ms': percentiles(cpus),
            'initial_cycle_wall_ms': timings[0] * 1000, 'initial_cycle_cpu_ms': cpus[0] * 1000,
            'initial_batch': batch_timings[0], 'cycles_over_5_seconds': sum(t > 5 for t in timings),
            'maximum_scheduling_lateness_ms': late * 1000, 'application_bytes_written': writes[0],
            'fsync_calls': syncs[0], **measured, 'retained_growth_bytes': retained_growth,
            'first_cycle': first_sizes, 'peak_rss_bytes': resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024,
            'file_and_directory_inodes': measured['files'] + measured['directories'] + 1,
            'fresh_process_reopen': reopened,
            'window_projected_application_GB_day': writes[0] / observations * 8640 / 1e9,
            'window_projected_retained_growth_GB_day': retained_growth / observations * 8640 / 1e9,
            'post_initial_projected_application_GB_day': (writes[0] - first_sizes['application_bytes']) / max(1, observations - 1) * 8640 / 1e9,
            'post_initial_projected_retained_growth_GB_day': (measured['retained_bytes'] - first_sizes['retained_bytes']) / max(1, observations - 1) * 8640 / 1e9,
            'projected_new_body_objects_day': 1440,
            'cadence_pass': cycles == expected_cycles and all(n == expected_observations for n in counts.values())
                and all(h['http_status'] == 200 for h in health) and max(timings) < 5,
            'measurement_scope': 'Exact V1 synthetic seven-feed fixture, change6 body pattern. Application bytes include successful os.write return bytes, all source ledgers/anchors/markers, exclude history preparation/runtime initialization and device/journal amplification. GB decimal. RSS includes preparation. Every object is retained. History timing is finite-horizon, not constant-cost verification.'}
        print(json.dumps(report, indent=2))
        return 0 if report['cadence_pass'] else 1


if __name__ == '__main__': raise SystemExit(main())
