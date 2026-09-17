"""Offline synthetic storage/cycle benchmark; never starts the service loop.

Run this same harness with the pinned base and candidate packages in separate
processes. Account application os.write bytes (including durability metadata),
retained file bytes, allocated blocks, inodes, process CPU/wall and peak RSS.
No compression. No live provider/service request or real evidence is used.
"""
import argparse
import json
import os
from pathlib import Path
import resource
import statistics
import tempfile
import time
from unittest.mock import patch

import requests
from integrity_sentinel.adversarial_body_dedup_v1 import runtime, synthetic_audit, endpoint


def files(root):
    paths = list(root.rglob('*'))
    regular = [p for p in paths if p.is_file()]
    return {'retained_bytes': sum(p.stat().st_size for p in regular),
            'allocated_bytes': sum(p.stat().st_blocks * 512 for p in paths),
            'files': len(regular), 'directories': sum(p.is_dir() for p in paths),
            'body_objects': len(list(root.rglob('*.body')))}


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--mode', choices=['identical', 'change6', 'unique'], default='identical')
    parser.add_argument('--samples', type=int, default=24)
    parser.add_argument('--records-per-lane', type=int, default=16)
    parser.add_argument('--sustain-seconds', type=float, default=0)
    args = parser.parse_args()
    timings, cpu, writes, fsyncs = [], [], [0], [0]
    health_results = []
    real_write, real_sync = os.write, os.fsync
    def count_write(fd, raw):
        result = real_write(fd, raw)
        writes[0] += result
        return result
    def count_sync(fd):
        fsyncs[0] += 1
        return real_sync(fd)
    rss_before = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
    with tempfile.TemporaryDirectory(prefix='sentinel-storage-benchmark-') as td, \
            patch.dict(os.environ, {}, clear=True), \
            patch.object(requests.adapters.HTTPAdapter, 'send', side_effect=AssertionError('network forbidden')), \
            patch('os.write', side_effect=count_write), patch('os.fsync', side_effect=count_sync):
        raw = synthetic_audit(args.records_per_lane)
        r, transport = runtime(td, raw)
        start = time.monotonic()
        next_tick = start
        next_membership = 0.
        observations = cycles = 0
        maximum_overrun = 0.
        count_at_first = size_at_first = None
        while True:
            now = time.monotonic()
            if args.sustain_seconds:
                if now - start >= args.sustain_seconds: break
                if now < next_tick:
                    time.sleep(min(1., next_tick - now))
                    continue
                maximum_overrun = max(maximum_overrun, now - next_tick)
                include = now >= next_membership
            else:
                if cycles >= args.samples * 2: break
                include = cycles % 2 == 0
            if include:
                revision = 0 if args.mode == 'identical' else observations // 6 if args.mode == 'change6' else observations
                transport.audit = synthetic_audit(args.records_per_lane, revision)
                observations += 1
            wall_start, cpu_start = time.perf_counter(), time.process_time()
            r.run_cycle(include_membership=include)
            code, state = endpoint(r)
            health_results.append({'cycle': cycles + 1, 'http_status': code, 'failures': state['health_failures']})
            assert state['orders'] is False and state['certifiable_evidence'] is False
            timings.append(time.perf_counter() - wall_start)
            cpu.append(time.process_time() - cpu_start)
            if cycles == 0:
                count_at_first, size_at_first = writes[0], files(Path(td))['retained_bytes']
            cycles += 1
            if args.sustain_seconds:
                # Exactly the existing loop policy: telemetry 5s, membership10s.
                if include: next_membership = now + r.membership_poll_sec
                next_tick = now + r.poll_sec
        elapsed = time.monotonic() - start
        measured = files(Path(td))
        io_bytes, sync_count = writes[0], fsyncs[0]
        obs = [row['body'] for row in r.membership._iter_records()
               if row['body'].get('record_type') == 'SOURCE_OBSERVATION']
        counts = {name: sum(o['source'] == name for o in obs) for name in
                  ('early_membership', 'final_membership', 'combined_membership', 'nextgen_membership')}
        assert set(counts.values()) == {observations}
        r.session.close()
        before_reopen = {str(p): p.stat().st_size for p in Path(td).rglob('*.body')}
        reopen_start, reopen_cpu = time.perf_counter(), time.process_time()
        reopened, _ = runtime(td, raw)
        assert reopened.membership.status().chain_valid and reopened.telemetry.status().chain_valid
        reopen_wall, reopen_cpu = time.perf_counter() - reopen_start, time.process_time() - reopen_cpu
        assert before_reopen == {str(p): p.stat().st_size for p in Path(td).rglob('*.body')}
        reopened.run_cycle()
        assert endpoint(reopened)[0] == 200
        reopened.session.close()
        rss_peak = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss * 1024
        n = observations
        # Projection is this measured all-feed mix per Nextgen observation,
        # not a capacity guarantee; distinct-body ratio is explicit below.
        daily = 86400 / 10
        report = {'scenario': vars(args), 'body_bytes': len(raw), 'telemetry_cycles': cycles,
            'membership_observations_per_source': counts, 'elapsed_seconds': elapsed,
            'application_bytes_written': io_bytes, 'fsync_calls': sync_count, **measured,
            'first_cycle_application_bytes': count_at_first, 'first_cycle_retained_bytes': size_at_first,
            'projected_application_GB_per_day': io_bytes / n * daily / 1e9,
            'projected_retained_GB_per_day': measured['retained_bytes'] / n * daily / 1e9,
            'projected_body_objects_per_day': (0 if not measured['body_objects'] else
                1 if args.mode == 'identical' else daily / 6 if args.mode == 'change6' else daily),
            'mean_cycle_wall_ms': statistics.mean(timings) * 1000,
            'p95_cycle_wall_ms': sorted(timings)[max(0, int(len(timings) * .95) - 1)] * 1000,
            'max_cycle_wall_ms': max(timings) * 1000, 'first_cycle_wall_ms': timings[0] * 1000,
            'mean_cycle_cpu_ms': statistics.mean(cpu) * 1000, 'total_cycle_cpu_seconds': sum(cpu),
            'peak_rss_bytes': rss_peak, 'incremental_peak_rss_bytes': max(0, rss_peak - rss_before),
            'reopen_verify_wall_ms': reopen_wall * 1000, 'reopen_verify_cpu_ms': reopen_cpu * 1000,
            'max_scheduling_lateness_ms': maximum_overrun * 1000, 'reopen_verified': True,
            'offline': True, 'healthy_cycles': sum(x['http_status'] == 200 for x in health_results),
            'unhealthy_cycles': [x for x in health_results if x['http_status'] != 200],
            'cycles_over_5_seconds': sum(t > 5 for t in timings),
            'expected_telemetry_cycles_at_5s': int(__import__('math').ceil(args.sustain_seconds / 5)) if args.sustain_seconds else None,
            'unique_body_caveat': 'No cross-observation dedup savings claimed when every body changes.',
            'measurement_scope': 'Application writes include all seven sources, events, anchors and markers; filesystem journal/device write amplification excluded. GB is decimal. Peak RSS is process high-water, not exact live heap.'}
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
