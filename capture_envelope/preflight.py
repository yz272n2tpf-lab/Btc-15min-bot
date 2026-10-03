"""Qualification-only prerequisite test; imports the unchanged d61c capture.

No runtime, strategy, queue, socket, or timing setting is patched. The intentional
excursion stays below the formerly imposed 12k/s stress and adds no writer pause.
"""
import gzip
import hashlib
import json
import os
from pathlib import Path
import signal
import socket
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen

from capture2.runtime import CaptureProducer, SenderPopulation
from capture2.test_writer_pipeline import CONFIG, KEY, SOURCE, end, wait_for
from capture2.writer import packet
from sprint_evidence.passive_capture import Identity

ROOT = Path(__file__).resolve().parents[1]
CANDIDATE = 'd61c021cb405b08603864d077f03474473d2a5f3'
ENVELOPE = {
    'main': [(100, 1100), (250, 2250), (1000, 4000), (5000, 10000), (10000, 20000)],
    'v81': [(100, 350), (250, 750), (1000, 2500), (5000, 6250), (10000, 10000)],
}

def rolling_peak(times, width_ns):
    left = peak = 0
    for right, stamp in enumerate(times):
        while stamp - times[left] >= width_ns:
            left += 1
        peak = max(peak, right-left+1)
    return peak

def exercise(side, rate):
    with tempfile.TemporaryDirectory() as d:
        root = Path(d)
        address = str(root/'events.sock')
        with socket.socket() as s:
            s.bind(('127.0.0.1', 0))
            port = s.getsockname()[1]
        config = dict(CONFIG, directory=d, socket=address, max_seconds=60,
                      quota_bytes=64*1024*1024, port=port)
        cp = root/'config.json'
        cp.write_text(json.dumps(config))
        proc = subprocess.Popen([sys.executable, '-B', '-m', 'capture2.writer', '--config', str(cp)],
                                cwd=ROOT, start_new_session=True)
        population = SenderPopulation(root, end(45))
        p = None
        def health():
            with urlopen(f'http://127.0.0.1:{port}/ground-zero/manifest', timeout=5) as response:
                assert response.status == 200
                return json.load(response)['health']
        try:
            wait_for(lambda: Path(address).exists(), 10)
            p = CaptureProducer(address, Identity(side+'-quote', 'build', SOURCE, 'run', 'domain', 'boot'),
                                KEY, end_boot_ns=population.end_boot_ns,
                                status_path=root/'transport-quote.json', population=population)
            fixture = json.loads((ROOT/'capture_durability/transport_fixture.json').read_text())
            count = 2*rate
            started = time.monotonic()
            for i in range(count):
                assert p.offer('LIFECYCLE_EMISSION', fixture[i % len(fixture)]), p.last_error
                if (i+1) % 10 == 0:
                    delay = started + (i+1)/rate - time.monotonic()
                    if delay > 0:
                        time.sleep(delay)
            offered_seconds = time.monotonic()-started
            p.close()
            population.close()
            wait_for(lambda: population.snapshot()['active'] == 0, 10)
            population.thread.join(3)
            wait_for(lambda: health()['packets'] == count, 10)
            (root/'drain.stop').touch()
            wait_for(lambda: (root/'final_health.json').exists(), 10)
            h = health()
            a = h['transport_accounting']
            with urlopen(f"http://127.0.0.1:{port}/ground-zero/transports?snapshot={a['snapshot_id']}&offset=0", timeout=5) as response:
                page = json.load(response)
            times = []
            for raw in gzip.open(root/'packets.jsonl.gz', 'rb'):
                event = packet(raw, CONFIG)
                assert event['sequence'] == len(times)+1 and event['prior_dropped'] == 0
                times.append(event['hook_read']['before_boot_ns'])
            assert len(times) == count
            peaks = [{'window_ms': ms, 'limit_packets': limit,
                      'observed_packets': rolling_peak(times, ms*1000000)}
                     for ms, limit in ENVELOPE[side]]
            exceeded = [x for x in peaks if x['observed_packets'] > x['limit_packets']]
            assert exceeded, 'EXCURSION_NOT_EXERCISED'
            transport = p.sock.snapshot()
            # Requirement 8: an otherwise lossless rate excursion must be flagged.
            # Current candidate has no rate-policy state in runtime or accounting.
            return dict(side=side, status='FAIL' if a['complete'] and not a['errors'] else 'REVIEW',
                        failure='OVER_ENVELOPE_NOT_FLAGGED' if a['complete'] and not a['errors'] else a['errors'],
                        quote_packets=count, offered_seconds=offered_seconds,
                        offered_pps=count/offered_seconds, all_archived_authenticated=True,
                        envelope_peaks=peaks, exceeded=exceeded, transport=transport,
                        aggregate=a, individual_records=page['records'],
                        writer_health={k:v for k,v in h.items() if k not in ('transport_accounting', 'streams')},
                        manifest_http_status=200, production_or_live_test=False,
                        sustained_throughput_qualified=False)
        finally:
            if p:
                p.close()
            population.close()
            population.thread.join(3)
            os.killpg(proc.pid, signal.SIGTERM)
            proc.wait(timeout=10)

if __name__ == '__main__':
    output = ROOT/'capture_envelope/results'
    output.mkdir(parents=True, exist_ok=True)
    preservation = json.loads((ROOT/'capture_writer/results/preservation.json').read_text())
    hashes = {f: hashlib.sha256((ROOT/f).read_bytes()).hexdigest()
              for f in preservation['capture_file_hashes']}
    assert hashes == preservation['capture_file_hashes']
    assert hashlib.sha256((ROOT/'capture2_payload.json').read_bytes()).hexdigest() == preservation['payload_sha256']
    result = dict(candidate=CANDIDATE, capture_hashes_unchanged=True,
                  payload_sha256=preservation['payload_sha256'],
                  envelope_packet_limits=ENVELOPE, qualification='FAIL',
                  reason='REQUIREMENT_8_PREFLIGHT', sides=[])
    for side, rate in [('main', 6000), ('v81', 3500)]:
        try:
            result['sides'].append(exercise(side, rate))
        except Exception as exc:
            result['sides'].append(dict(side=side, status='FAIL', failure=repr(exc)))
            break
    (output/'preflight.json').write_text(json.dumps(result, indent=2))
    print(json.dumps(result, indent=2), flush=True)
    sys.exit(1)
