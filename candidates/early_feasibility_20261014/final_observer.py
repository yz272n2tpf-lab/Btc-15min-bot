"""Single bounded external GET-only EARLY attempt; no production imports/writes.

Run from repository root with python -m candidates.early_feasibility_20261014.final_observer OUTDIR.
Use --self-test for offline guard tests. Never automatically rerun a failed attempt.
"""
import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import signal
import time
import unittest
import urllib.error
import urllib.request
from datetime import datetime, timezone

from .public_probe import ORIGIN, PATHS, MAX_BYTES, NoRedirect
from .pair_probe import validate_pair

TOTAL_SECONDS = 1200
SMOKE_SECONDS = 60
INTERVAL = 2.0
SLOW_SECONDS = 2.0
OUTPUT_CAP = 20 * 1024 * 1024
RAW_CAP = 18 * 1024 * 1024
PINNED_MAIN = 'dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72'


def utc():
    return datetime.now(timezone.utc).isoformat()


def digest(data):
    return hashlib.sha256(data).hexdigest()


def encode(value):
    return (json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False) + '\n').encode()


class StopCapture(Exception):
    pass


def future_pair(decision, quote, receipt_ts):
    result = validate_pair(decision, quote)
    if not result.get('valid'):
        return False
    clocks = [quote.get(k) for k in ('exchange_ts', 'accepted_ts', 'published_ts', 'served_ts', 'expires_at')]
    clocks.append(decision.get('published_ts'))
    if any(type(x) not in (int, float) or not math.isfinite(x) for x in clocks):
        return False
    if not quote.get('epoch') or quote.get('sid') is None or type(quote.get('sequence')) is not int:
        return False
    return (result['later_quote_source'] and result['later_quote_accepted']
            and quote['served_ts'] <= receipt_ts < quote['expires_at'])


class Evidence:
    def __init__(self, folder):
        self.folder = Path(folder)
        self.folder.mkdir(parents=True, exist_ok=False)
        self.raw = (self.folder / 'raw.jsonl').open('xb')
        self.bytes = 0
        self.records = 0

    def append(self, record):
        line = encode(record)
        if self.bytes + len(line) > RAW_CAP:
            raise StopCapture('RAW_OUTPUT_CAP')
        self.raw.write(line)
        self.raw.flush()
        os.fsync(self.raw.fileno())
        self.bytes += len(line)
        self.records += 1

    def seal(self, result):
        self.raw.close()
        with (self.folder / 'result.json').open('xb') as f:
            f.write(encode(result))
        manifest = dict(schema='BTC15_FINAL_CAPTURE_SHA256_V1', files={})
        for name in ('raw.jsonl', 'result.json'):
            data = (self.folder / name).read_bytes()
            manifest['files'][name] = dict(bytes=len(data), sha256=digest(data))
        with (self.folder / 'manifest.json').open('xb') as f:
            f.write(encode(manifest))
        assert sum(p.stat().st_size for p in self.folder.iterdir()) <= OUTPUT_CAP
        for p in self.folder.iterdir():
            p.chmod(0o444)


class Observer:
    def __init__(self, evidence, opener=None):
        self.evidence = evidence
        self.opener = opener or urllib.request.build_opener(NoRedirect())
        self.started = time.monotonic()
        self.last_request = {}
        self.request_count = {}
        self.decisions = {}
        self.quote_ids = set()
        self.joins = 0
        self.joined_decisions = set()
        self.defects = {}
        self.previous_quote = None
        self.target = None
        self.target_close = None
        self.current_ticker = None
        self.unavailable = {}
        self.coverage = None
        self.smoke_passed = False

    def mark(self, name):
        self.defects[name] = self.defects.get(name, 0) + 1

    def get(self, path):
        if path not in PATHS:
            raise StopCapture('PATH_NOT_ALLOWED')
        if path == '/ladders/coverage' and self.request_count.get(path):
            raise StopCapture('COVERAGE_ALREADY_READ')
        now = time.monotonic()
        if now - self.started >= TOTAL_SECONDS - SLOW_SECONDS:
            raise StopCapture('HARD_TIME_CAP')
        if now - self.last_request.get(path, -1e30) < INTERVAL:
            raise StopCapture('CADENCE_GUARD')
        if self.evidence.bytes > RAW_CAP - 400000:
            raise StopCapture('OUTPUT_CAP_BEFORE_REQUEST')
        self.last_request[path] = now
        self.request_count[path] = self.request_count.get(path, 0) + 1
        record = dict(path=path, url=ORIGIN+path, method='GET', request_utc=utc(),
                      request_unix=time.time(), elapsed_start_seconds=now-self.started)
        data = b''
        failure = None
        try:
            req = urllib.request.Request(ORIGIN+path, method='GET', headers={
                'Accept': 'application/json', 'User-Agent': 'BTC15-final-bounded-external-observer'})
            try:
                response = self.opener.open(req, timeout=SLOW_SECONDS)
            except urllib.error.HTTPError as exc:
                response = exc
            with response:
                record['http_status'] = response.code
                record['http_headers'] = list(response.headers.items())
                data = response.read(MAX_BYTES + 1)
                record['body_complete'] = len(data) <= MAX_BYTES
                if len(data) > MAX_BYTES:
                    failure = 'RESPONSE_TOO_LARGE'
                elif response.code != 200:
                    failure = 'HTTP_' + str(response.code)
        except Exception as exc:
            failure = type(exc).__name__ + ': ' + str(exc)[:300]
        record.update(receipt_utc=utc(), receipt_unix=time.time(),
                      request_duration_seconds=time.monotonic()-now,
                      body_base64=base64.b64encode(data).decode(), body_sha256=digest(data),
                      body_bytes=len(data))
        if failure is not None:
            record['error'] = failure
        self.evidence.append(record)
        if failure:
            raise StopCapture(failure)
        if record['request_duration_seconds'] >= SLOW_SECONDS:
            raise StopCapture('SLOW_REQUEST')
        try:
            value = json.loads(data)
        except (ValueError, UnicodeError) as exc:
            raise StopCapture('INVALID_JSON') from exc
        if not isinstance(value, dict):
            raise StopCapture('NOT_JSON_OBJECT')
        if value.get('signal_only') is not True or value.get('orders') is not False:
            raise StopCapture('SIGNAL_ONLY_IDENTITY')
        if path != '/ladders/coverage':
            if value.get('status') != 'AVAILABLE':
                self.mark(path + ':' + str(value.get('reason', 'UNAVAILABLE')))
                self.unavailable[path] = self.unavailable.get(path, 0) + 1
                if self.unavailable[path] >= 3:
                    raise StopCapture('SOURCE_UNHEALTHY:' + path)
            else:
                self.unavailable[path] = 0
        return value, record

    def consume(self, view, quote, receipt):
        if view.get('status') == 'AVAILABLE':
            key = (view.get('contract'), view.get('native_sequence'), view.get('published_ts'))
            if key in self.decisions:
                self.mark('DUPLICATE_NATIVE_DECISION')
                original = self.decisions[key]
                for field in ('early', 'prices', 'origin', 'management', 'final', 'feature_cutoff'):
                    if original.get(field) != view.get(field):
                        self.mark('CHANGED_DUPLICATE_DECISION_' + field)
            else:
                self.decisions[key] = view
            ticker = view.get('contract')
            if self.current_ticker is not None and ticker != self.current_ticker:
                self.mark('CONTRACT_ROLLOVER')
            self.current_ticker = ticker
        if quote.get('status') != 'AVAILABLE':
            return
        ident = quote.get('official_identity') or {}
        ticker = ident.get('contract')
        epoch, sid, seq = (quote.get(k) for k in ('epoch', 'sid', 'sequence'))
        if not epoch or sid is None or type(seq) is not int:
            self.mark('PROVIDER_IDENTITY_MISSING')
            return
        if ticker != view.get('contract'):
            self.mark('UNMATCHED_TICKER')
        qid = (ticker, epoch, sid, seq)
        if self.previous_quote:
            old = self.previous_quote
            if ticker == old[0]:
                if epoch != old[1]: self.mark('PROVIDER_EPOCH_CHANGED')
                elif sid != old[2]: self.mark('PROVIDER_SID_CHANGED')
                elif seq > old[3]+1: self.mark('SAMPLED_SEQUENCE_GAP')
                elif seq < old[3]: self.mark('SEQUENCE_REGRESSION')
                elif seq == old[3]: self.mark('DUPLICATE_QUOTE')
        self.previous_quote = qid
        if self.target is None and isinstance(ident.get('official_close'), (int, float)):
            self.target, self.target_close = ticker, ident['official_close']
        if quote.get('expires_at', 0) <= receipt['receipt_unix']:
            self.mark('STALE_QUOTE_AT_LOCAL_RECEIPT')
        if qid not in self.quote_ids:
            self.quote_ids.add(qid)
            for key, original in self.decisions.items():
                if future_pair(original, quote, receipt['receipt_unix']):
                    self.joins += 1
                    self.joined_decisions.add(key)

    def run(self):
        start_utc = utc()
        blocker = None
        reason = None
        try:
            while True:
                elapsed = time.monotonic() - self.started
                if elapsed >= SMOKE_SECONDS and not self.smoke_passed:
                    if not self.joins:
                        raise StopCapture('SMOKE_NO_CORRECT_TIME_SAME_CONTRACT_QUOTE')
                    self.smoke_passed = True
                    print(json.dumps(dict(smoke='PASS', elapsed_seconds=elapsed,
                                          valid_postdecision_joins=self.joins)), flush=True)
                if self.smoke_passed and (elapsed >= TOTAL_SECONDS-8 or
                        (self.target_close is not None and time.time() >= self.target_close+2)):
                    self.coverage, _ = self.get('/ladders/coverage')
                    reason = 'FIRST_OBSERVED_CONTRACT_FINISHED' if elapsed < TOTAL_SECONDS-8 else 'TIME_BUDGET_FINISH'
                    break
                view, _ = self.get('/ladders')
                quote, receipt = self.get('/ladders/quotes')
                self.consume(view, quote, receipt)
                wake = max(self.last_request.values()) + INTERVAL
                time.sleep(max(0, wake-time.monotonic()))
        except StopCapture as exc:
            blocker = str(exc)
            reason = 'STOPPED_NO_RETRY'
        except Exception as exc:
            blocker = type(exc).__name__ + ': ' + str(exc)[:300]
            reason = 'STOPPED_NO_RETRY'
        result = dict(schema='BTC15_FINAL_EARLY_EXTERNAL_EVIDENCE_V1',
            verdict='GO_TO_ANALYZE_ONLY' if blocker is None and self.smoke_passed and self.joins else 'NO_GO',
            blocker=blocker, finish_reason=reason, start_utc=start_utc, finish_utc=utc(),
            duration_seconds=time.monotonic()-self.started, requests=self.request_count,
            smoke_passed=self.smoke_passed, preserved_unique_decisions=len(self.decisions),
            valid_postdecision_joins=self.joins, joined_original_decisions=len(self.joined_decisions),
            unique_quote_identities=len(self.quote_ids), target_contract=self.target,
            target_close=self.target_close, observed_defects=self.defects,
            raw_records=self.evidence.records, raw_bytes=self.evidence.bytes,
            coverage_requested=self.coverage is not None, pinned_main=PINNED_MAIN,
            no_production_changes=True, no_orders=True, no_retry=True,
            limitations=['Sampling cannot prove all market ticks or full contract coverage.',
                'Displayed BID/ASK does not prove depth, fills, fees, slippage, profitability or EARLY accuracy.',
                'Missing exits, unmatched contracts and pending settlements remain unavailable.'])
        self.evidence.seal(result)
        print(json.dumps(result, indent=2), flush=True)
        return 0 if result['verdict'] == 'GO_TO_ANALYZE_ONLY' else 2


class GuardTests(unittest.TestCase):
    def test_original_native_time_not_get_time(self):
        from test_btc15_early_quote_pair_feasibility import fixture
        d, q = fixture()
        q.update(epoch='e', sid=1, sequence=10)
        self.assertTrue(future_pair(d, q, q['served_ts']+.01))
        q['exchange_ts'] = d['published_ts']
        self.assertFalse(future_pair(d, q, q['served_ts']+.01))

    def test_epoch_and_local_expiry_required(self):
        from test_btc15_early_quote_pair_feasibility import fixture
        d, q = fixture()
        q.update(epoch='e', sid=1, sequence=10)
        self.assertFalse(future_pair(d, q, q['expires_at']))
        q.pop('epoch')
        self.assertFalse(future_pair(d, q, q['served_ts']))

    def test_no_overwrite_and_cap(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            e = Evidence(Path(tmp)/'once')
            with self.assertRaises(FileExistsError): Evidence(Path(tmp)/'once')
            e.bytes = RAW_CAP
            with self.assertRaises(StopCapture): e.append({'a': 1})
            e.raw.close()

    def test_failure_stops_after_one_get(self):
        import tempfile
        class Failing:
            calls = 0
            def open(self, req, timeout):
                self.calls += 1
                raise urllib.error.URLError('offline fixture')
        with tempfile.TemporaryDirectory() as tmp:
            opener = Failing()
            e = Evidence(Path(tmp)/'once')
            o = Observer(e, opener)
            self.assertEqual(o.run(), 2)
            self.assertEqual(opener.calls, 1)
            r = json.loads((e.folder/'result.json').read_text())
            self.assertEqual(r['valid_postdecision_joins'], 0)
            self.assertFalse(r['coverage_requested'])

    def test_cadence_paths_and_single_coverage(self):
        import tempfile
        with tempfile.TemporaryDirectory() as tmp:
            e = Evidence(Path(tmp)/'once')
            o = Observer(e)
            with self.assertRaisesRegex(StopCapture, 'PATH_NOT_ALLOWED'): o.get('/orders')
            o.last_request['/ladders'] = time.monotonic()
            with self.assertRaisesRegex(StopCapture, 'CADENCE_GUARD'): o.get('/ladders')
            o.request_count['/ladders/coverage'] = 1
            with self.assertRaisesRegex(StopCapture, 'COVERAGE_ALREADY_READ'): o.get('/ladders/coverage')
            e.raw.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('output', nargs='?')
    parser.add_argument('--self-test', action='store_true')
    args = parser.parse_args()
    if args.self_test:
        return 0 if unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(GuardTests)).wasSuccessful() else 1
    if not args.output:
        parser.error('a new output directory is required')
    e = Evidence(args.output)
    o = Observer(e)
    def deadline(_signum, _frame):
        raise StopCapture('HARD_TIME_CAP')
    signal.signal(signal.SIGALRM, deadline)
    signal.setitimer(signal.ITIMER_REAL, TOTAL_SECONDS)
    try:
        return o.run()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)


if __name__ == '__main__':
    raise SystemExit(main())
