#!/usr/bin/env python3
"""One explicitly approved BRTI data GET, not a bot launch or an installer.

No retries, redirects, signals, orders, service starts, permit/marker changes,
or production edits. Takes the existing exclusive owner lock while reading.
Prints only status codes and aggregate timing/schema information, never keys,
headers, prices, response bodies or arbitrary error messages.
"""
import argparse
import base64
from datetime import datetime, timezone
import fcntl
import json
import math
import os
from pathlib import Path
import resource
import signal
import stat
import subprocess
import sys
import time

URL = 'https://external-api.kalshi.com/trade-api/v2/cfbenchmarks/values'
API_PATH = '/trade-api/v2/cfbenchmarks/values'
ETC = Path('/etc/btc15-pilot')
LOCK = Path('/var/lib/btc15-pilot/brti/owner.lock')
LIMIT_MS = 1350.0
MAX_BYTES = 4 * 1024 * 1024

class Hold(Exception):
    pass

def need(ok, code):
    if not ok:
        raise Hold(code)

def say(key, value):
    print(f'{key}={value}', flush=True)

def read_regular(path, limit, secret=False):
    for parent in path.parents:
        s = parent.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not (s.st_mode & 0o022),
             'UNTRUSTED_PARENT')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and s.st_nlink == 1 and s.st_uid == 0,
             'UNTRUSTED_FILE')
        need(not (s.st_mode & (0o077 if secret else 0o022)), 'FILE_PERMISSION_REVIEW')
        need(0 < s.st_size <= limit, 'FILE_SIZE_REVIEW')
        data = os.read(fd, limit + 1)
        need(len(data) <= limit, 'FILE_SIZE_REVIEW')
        return data
    finally:
        os.close(fd)

def stopped():
    r = subprocess.run(
        ['systemctl', 'list-units', '--all', '--plain', '--no-legend',
         '--no-pager', '--full', 'btc15*.service', 'btc15*.timer'],
        stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=8)
    need(r.returncode == 0, 'SERVICE_STATE_UNAVAILABLE')
    rows = [x.split() for x in r.stdout.splitlines() if x.strip()]
    need(rows, 'BTC15_UNITS_NOT_FOUND')
    for row in rows:
        need(len(row) >= 4, 'SERVICE_STATE_UNRECOGNIZED')
        expired_stop_timer = row[0] == 'btc15-pilot-deadline.timer' and row[2:4] == ['active', 'elapsed']
        need(row[2] in ('inactive', 'failed') or expired_stop_timer,
             'BTC15_SERVICE_OR_TIMER_ACTIVE_NO_REQUEST')
    r = subprocess.run(['timedatectl', 'show', '--property=NTPSynchronized', '--value'],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=8)
    need(r.returncode == 0 and r.stdout.strip() == 'yes', 'CLOCK_NOT_SYNCHRONIZED')

def parse_summary(obj, received):
    data = obj.get('data', obj) if isinstance(obj, dict) else None
    if not isinstance(data, dict):
        return {'PAYLOAD': 'UNEXPECTED_ENVELOPE'}
    if data.get('id', 'BRTI') != 'BRTI':
        return {'PAYLOAD': 'WRONG_INDEX'}
    if data.get('error'):
        return {'PAYLOAD': 'UPSTREAM_ERROR_FIELD_PRESENT'}
    rows = data.get('payload')
    if not isinstance(rows, list) or not rows:
        return {'PAYLOAD': 'MISSING_OR_NONLIST_PUBLICATIONS'}
    invalid = 0
    conflicts = 0
    future = 0
    points = {}
    for item in rows:
        if not isinstance(item, dict) or item.get('id', 'BRTI') != 'BRTI':
            invalid += 1
            continue
        try:
            t = float(item.get('time'))
            v = float(item.get('value'))
            good = (not isinstance(item.get('time'), bool) and math.isfinite(t)
                    and t == int(t) and t > 0 and math.isfinite(v) and 1000 < v < 1000000)
        except (TypeError, ValueError, OverflowError):
            good = False
        if not good:
            invalid += 1
            continue
        t = int(t)
        if t > received * 1000:
            future += 1
        if t in points and points[t] != v:
            conflicts += 1
        points[t] = v
    result = {'PUBLICATIONS': len(rows), 'INVALID_ROWS': invalid,
              'CONFLICTS': conflicts, 'FUTURE_ROWS': future}
    if invalid or conflicts or future or not points:
        result['PAYLOAD'] = 'INVALID_OR_CONFLICTING'
        return result
    age = received * 1000 - max(points)
    result.update(PAYLOAD='VALID_SOURCE_TIMESTAMPS', NEWEST_AGE_MS=round(age, 1),
                  CONFIGURED_LIMIT_MS=LIMIT_MS,
                  THIS_SAMPLE_AGE_CHECK='WITHIN_LIMIT' if 0 <= age <= LIMIT_MS else 'TOO_OLD')
    return result

def headers(key_id, private_b64):
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import padding, rsa
    key = serialization.load_pem_private_key(base64.b64decode(private_b64), password=None)
    need(isinstance(key, rsa.RSAPrivateKey), 'RSA_KEY_REQUIRED')
    stamp = str(int(time.time() * 1000))
    signature = key.sign((stamp + 'GET' + API_PATH).encode(),
                         padding.PSS(mgf=padding.MGF1(hashes.SHA256()), salt_length=32),
                         hashes.SHA256())
    return {'KALSHI-ACCESS-KEY': key_id,
            'KALSHI-ACCESS-TIMESTAMP': stamp,
            'KALSHI-ACCESS-SIGNATURE': base64.b64encode(signature).decode(),
            'Accept': 'application/json', 'Accept-Encoding': 'identity'}

def one_get(auth, session_factory=None):
    import requests
    if session_factory is None:
        session_factory = requests.Session
    started = time.monotonic()
    try:
        with session_factory() as session:
            session.trust_env = False
            session.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
            with session.get(URL, headers=auth,
                             params={'id': 'BRTI', 'maxResolution': 'PER_SECOND'},
                             timeout=(1.5, 1.5), allow_redirects=False, stream=True) as response:
                status = response.status_code
                result = {'HTTP_STATUS': status}
                if status != 200:
                    result['UPSTREAM_RESULT'] = {
                        401: 'AUTHENTICATION_REJECTED', 403: 'ACCESS_DENIED',
                        429: 'RATE_LIMITED_NO_RETRY', 503: 'UPSTREAM_UNAVAILABLE',
                    }.get(status, 'HTTP_NOT_200_NO_RETRY')
                    return result
                raw = bytearray()
                for chunk in response.iter_content(chunk_size=65536):
                    need(time.monotonic() - started < 8, 'RESPONSE_DEADLINE_NO_RETRY')
                    raw.extend(chunk)
                    need(len(raw) <= MAX_BYTES, 'RESPONSE_TOO_LARGE_NO_RETRY')
                received = time.time()
                result['REQUEST_MS'] = round((time.monotonic() - started) * 1000, 1)
                try:
                    obj = json.loads(raw)
                except (ValueError, UnicodeError):
                    result['PAYLOAD'] = 'INVALID_JSON'
                    return result
                result.update(parse_summary(obj, received))
                return result
    except requests.exceptions.SSLError:
        return {'UPSTREAM_RESULT': 'TLS_VERIFICATION_FAILED_NO_RETRY'}
    except requests.exceptions.Timeout:
        return {'UPSTREAM_RESULT': 'REQUEST_TIMEOUT_NO_RETRY'}
    except requests.exceptions.ConnectionError:
        return {'UPSTREAM_RESULT': 'CONNECTION_OR_BODY_READ_FAILED_NO_RETRY'}
    except requests.exceptions.RequestException:
        return {'UPSTREAM_RESULT': 'REQUEST_FAILED_NO_RETRY'}

def alarm_handler(signum, frame):
    raise Hold('WALL_CLOCK_DEADLINE_NO_RETRY')

def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    need(os.geteuid() == 0 and Path('/opt/btc15-pilot/release/owner').is_dir(),
         'EXISTING_SERVER_ROOT_REQUIRED')
    sys.dont_write_bytecode = True
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    print('ONE DIAGNOSTIC GET ONLY. This uses your existing Kalshi BRTI credentials.', flush=True)
    print('No bot launch, orders, retries, permit reuse, file changes, or freshness changes.', flush=True)
    print('Proceed only with valid provider access and all other collectors stopped.', flush=True)
    answer = input('Type READ to authorize this single request, or press Return to cancel: ')
    if answer.strip().upper() != 'READ':
        print('CANCELLED_NO_REQUEST', flush=True)
        return 0
    signal.signal(signal.SIGALRM, alarm_handler)
    signal.alarm(30)
    stopped()
    for parent in LOCK.parents:
        s = parent.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             'UNTRUSTED_OWNER_LOCK_PARENT')
    fd = os.open(LOCK, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1,
             'UNTRUSTED_OWNER_LOCK')
        try:
            fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Hold('ANOTHER_BRTI_OWNER_NO_REQUEST') from None
        stopped()
        key_id = read_regular(ETC / 'secrets/brti.key-id', 4096, True).decode().strip()
        key_b64 = read_regular(ETC / 'secrets/brti.key-b64', 32768, True).strip()
        need(bool(key_id) and bool(key_b64), 'CREDENTIAL_MISSING')
        auth = headers(key_id, key_b64)
        print('=== BRTI_ONE_READ_RESULT ===', flush=True)
        say('OBSERVED_AT_UTC', datetime.now(timezone.utc).isoformat())
        for k, v in one_get(auth).items():
            say(k, v)
    finally:
        os.close(fd)
        signal.alarm(0)
    print('FINISHED_NO_START_NO_ORDERS_NO_BOT_FILE_OR_PERMIT_CHANGES', flush=True)
    print('LIMIT: One sample; not the previous failure cause or full live-bot acceptance.', flush=True)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (EOFError, KeyboardInterrupt):
        print('\nCANCELLED_NO_RETRY', flush=True)
        sys.exit(2)
    except Hold as exc:
        print('HOLD_NO_RETRY: ' + str(exc), flush=True)
        sys.exit(2)
    except Exception as exc:
        print('HOLD_NO_RETRY: ' + type(exc).__name__, flush=True)
        sys.exit(2)
