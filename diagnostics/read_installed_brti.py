#!/usr/bin/env python3
"""One approved GET using the installed BRTI fetcher/poller, then in-memory validation.
Not an installer or launcher. No edits to the bot, manifests, permits or markers.
Consumer transport is simulated in this diagnostic process: nginx, firewall and
service-user execution are NOT tested. Never starts poller threads or a server.
"""
import argparse
import fcntl
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import re
import resource
import signal
import stat
import subprocess
import sys
import time

BASE = Path('/opt/btc15-pilot/release')
ETC = Path('/etc/btc15-pilot')
LOCK = Path('/var/lib/btc15-pilot/brti/owner.lock')
URL = 'https://external-api.kalshi.com/trade-api/v2/cfbenchmarks/values'
PINNED = {
    'owner/brti_shared_feed_v1.py': '3c33030f585eaaba80b68e6db816b08169471c6c77e060617a7bc0c08821dd0d',
    'owner/brti_shared_feed_guarded_launcher_v1.py': 'bca189306208c40df22e8fbca1a574eb48db98fa8d44270b63702b1fb002d546',
    'candidate/main/btc15_brti_shared_consumer_v1.py': '71097966ba6072e1bc7a97e049427d40b5838ef60a0cbfd71d2c08fdbba959b8',
    'candidate/main/btc15_v2_product/brti_profile.py': '1ca2850c32906a20aced226e1bca663f9adcf43e4fa4d528043116f1e86bd4af',
}
REPORT = {}

class Hold(Exception):
    pass

def need(ok, code):
    if not ok:
        raise Hold(code)

def fixed_error(exc):
    if type(exc) is Hold and re.fullmatch(r'[A-Z][A-Z0-9_]{1,90}', str(exc)):
        return str(exc)
    if type(exc) is ValueError and re.fullmatch(r'BRTI_[A-Z0-9_]{1,90}', str(exc)):
        return str(exc)
    return type(exc).__name__

def read_file(path, limit, secret=False):
    for p in path.parents:
        s = p.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             'UNTRUSTED_PARENT')
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s = os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1,
             'UNTRUSTED_FILE')
        need(not s.st_mode & (0o077 if secret else 0o022), 'FILE_PERMISSIONS')
        need(0 < s.st_size <= limit, 'FILE_SIZE')
        result = bytearray()
        while len(result) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(result)))
            if not part:
                break
            result.extend(part)
        need(len(result) <= limit, 'FILE_SIZE')
        return bytes(result)
    finally:
        os.close(fd)

def require_stopped():
    r = subprocess.run(['systemctl','list-units','--all','--plain','--no-legend',
                        '--no-pager','--full','btc15*.service','btc15*.timer'],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=8)
    need(r.returncode == 0, 'SERVICE_STATE_UNAVAILABLE')
    rows = [line.split() for line in r.stdout.splitlines() if line.strip()]
    need(rows, 'BTC15_UNITS_NOT_FOUND')
    for row in rows:
        need(len(row) >= 4, 'SERVICE_STATE_UNRECOGNIZED')
        expired = row[0] == 'btc15-pilot-deadline.timer' and row[2:4] == ['active','elapsed']
        need(row[2] in ('inactive','failed') or expired, 'BTC15_ACTIVE_NO_REQUEST')
    r = subprocess.run(['timedatectl','show','--property=NTPSynchronized','--value'],
                       stdin=subprocess.DEVNULL, capture_output=True, text=True, timeout=8)
    need(r.returncode == 0 and r.stdout.strip() == 'yes', 'CLOCK_NOT_SYNCHRONIZED')

def no_file_changes(event, args):
    if event in ('os.remove','os.rename','os.mkdir','os.rmdir','os.chmod','os.chown',
                 'os.link','os.symlink','os.truncate','os.utime','os.system',
                 'subprocess.Popen','os.posix_spawn','os.exec','os.fork','sqlite3.connect'):
        raise Hold('DIAGNOSTIC_SIDE_EFFECT_REFUSED')
    if event == 'open':
        mode, flags = args[1:3]
        if ((isinstance(mode,str) and any(x in mode for x in 'wax+')) or
            (isinstance(flags,int) and flags &
             (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
            raise Hold('DIAGNOSTIC_FILE_WRITE_REFUSED')

def load_module(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec)
    sys.modules[name] = mod
    spec.loader.exec_module(mod)
    return mod

class SingleRequest:
    """Keep original request construction, but prohibit redirects and a second GET."""
    def __init__(self, session):
        self.session = session
        self.count = 0

    def get(self, url, **kwargs):
        need(self.count == 0, 'SECOND_REQUEST_REFUSED')
        need(url == URL and kwargs.get('params') == {'id':'BRTI','maxResolution':'PER_SECOND'},
             'UNEXPECTED_ENDPOINT_REFUSED')
        need(not kwargs.get('proxies'), 'EXPLICIT_PROXY_REFUSED')
        # Never send the authorized headers through a proxy selected by shell env.
        import requests
        need(not requests.utils.get_environ_proxies(url), 'PROXY_ENV_REVIEW_NO_REQUEST')
        self.count += 1
        kwargs['allow_redirects'] = False
        started = time.monotonic()
        response = self.session.get(url, **kwargs)
        REPORT['HTTP_STATUS'] = int(response.status_code)
        REPORT['REQUEST_MS'] = round((time.monotonic()-started)*1000,1)
        need(len(response.content) <= 4*1024*1024, 'RESPONSE_TOO_LARGE')
        return response

def exercise(feed, consumer, fetcher):
    import requests
    fetcher.http.mount('https://', requests.adapters.HTTPAdapter(max_retries=0))
    underlying = fetcher.http
    guard = SingleRequest(underlying)
    fetcher.http = guard
    try:
        def observed_fetch():
            try:
                return fetcher.fetch_once()
            except Exception as exc:
                REPORT['ORIGINAL_FETCH_ERROR'] = fixed_error(exc)
                raise
        poller = feed.SharedBrtiPoller(observed_fetch, poll_interval_s=1.0,
                                      max_qualification_age_s=1.35, max_429_backoff_s=30.0)
        # One direct invocation only: never start(), _run(), main(), or make_server().
        poller.poll_once()
        snap = poller.snapshot()
        REPORT['UPSTREAM_REQUESTS'] = guard.count
        REPORT['ORIGINAL_FEED_STATUS'] = snap['status']
        REPORT['ORIGINAL_FEED_QUALIFIED'] = snap['clean_for_qualification']
        REPORT['ORIGINAL_UPSTREAM_OK'] = snap['upstream_ok']
        REPORT['ORIGINAL_ERROR_TYPE'] = snap['last_error_type'] or 'NONE'
        age = snap.get('age_ms')
        REPORT['SOURCE_AGE_MS'] = round(age,1) if type(age) in (int,float) and math.isfinite(age) else 'UNAVAILABLE'
        REPORT['AGE_LIMIT_MS'] = snap['max_qualification_age_ms']
        saved = consumer._legacy_get
        def memory_get(path, base_url, timeout_s):
            need(base_url is None, 'UNEXPECTED_CONSUMER_ENDPOINT')
            if path == '/state':
                return poller.snapshot()
            if path == '/ticks':
                return poller.history()
            raise Hold('UNEXPECTED_CONSUMER_PATH')
        consumer._legacy_get = memory_get
        try:
            point = consumer.read_shared_brti()
            ticks = consumer.read_shared_brti_ticks(owner_epoch=point['owner_epoch'])
            consumer.require_clear()
            REPORT['ORIGINAL_CONSUMER_IN_MEMORY'] = 'PASS'
            REPORT['HISTORY_ROWS'] = len(ticks)
        except Exception as exc:
            REPORT['ORIGINAL_CONSUMER_IN_MEMORY'] = 'FAIL_'+fixed_error(exc)
        finally:
            consumer._legacy_get = saved
    finally:
        underlying.close()

def alarm_handler(signum, frame):
    raise Hold('WALL_CLOCK_LIMIT_NO_RETRY')

def main():
    argparse.ArgumentParser(description=__doc__).parse_args()
    need(os.geteuid() == 0 and BASE.is_dir(), 'EXISTING_SERVER_ROOT_REQUIRED')
    sys.dont_write_bytecode = True
    resource.setrlimit(resource.RLIMIT_CORE,(0,0))
    print('One GET using the installed bot reader; downstream validation is IN MEMORY.', flush=True)
    print('No installation, bot start, orders, retries, or changes to permits/markers.', flush=True)
    print('Valid provider access and no other BRTI collectors are required.', flush=True)
    if input('Type READ to authorize this one request; Return cancels: ').strip().upper() != 'READ':
        print('CANCELLED_NO_REQUEST', flush=True)
        return 0
    signal.signal(signal.SIGALRM,alarm_handler)
    signal.alarm(40)
    require_stopped()
    for p in LOCK.parents:
        s=p.lstat()
        need(stat.S_ISDIR(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             'OWNER_LOCK_PARENT')
    fd=os.open(LOCK,os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        s=os.fstat(fd)
        need(stat.S_ISREG(s.st_mode) and s.st_uid == 0 and s.st_nlink == 1,'OWNER_LOCK_FILE')
        try:
            fcntl.flock(fd,fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise Hold('ANOTHER_OWNER_NO_REQUEST') from None
        require_stopped()
        for rel,h in PINNED.items():
            need(hashlib.sha256(read_file(BASE/rel,100000)).hexdigest() == h,'INSTALLED_SOURCE_MISMATCH')
        REPORT['INSTALLED_SOURCE_HASHES'] = 'MATCH'
        raw=read_file(ETC/'authorized-release.json',65536)
        receipt=json.loads(raw)
        need(receipt.get('orders') is False and receipt.get('signal_only') is True,'SIGNAL_ONLY_IDENTITY')
        need(receipt['brti']['owner_source_sha256'] == PINNED['owner/brti_shared_feed_v1.py'],
             'RECEIPT_SOURCE_MISMATCH')
        need(receipt['brti']['owner_launcher_sha256'] == PINNED['owner/brti_shared_feed_guarded_launcher_v1.py'],
             'RECEIPT_LAUNCHER_MISMATCH')
        # Receipt is read for expected source identity, NOT used as launch authorization.
        sys.path.insert(0,str(BASE/'candidate/main'))
        from btc15_v2_product.brti_profile import environment
        os.environ.update(environment(receipt),
                          BTC15_LINUX_IDENTITY=str(ETC/'authorized-release.json'),
                          BTC15_LINUX_IDENTITY_SHA256=hashlib.sha256(raw).hexdigest(),
                          BTC15_DATA_DIR='/run/btc15-pilot/health')
        key=read_file(ETC/'secrets/brti.key-id',4096,True).decode().strip()
        pem=read_file(ETC/'secrets/brti.key-b64',32768,True).decode().strip()
        need(bool(key) and bool(pem),'EMPTY_CREDENTIAL')
        sys.addaudithook(no_file_changes)
        feed=load_module('_btc15_original_feed',BASE/'owner/brti_shared_feed_v1.py')
        consumer=load_module('_btc15_original_consumer',BASE/'candidate/main/btc15_brti_shared_consumer_v1.py')
        fetcher=feed.KalshiBrtiFetcher(key,pem,timeout_s=1.5)
        exercise(feed,consumer,fetcher)
    finally:
        os.close(fd)
        signal.alarm(0)
    print('=== INSTALLED_READER_RESULT ===',flush=True)
    for k,v in REPORT.items():
        print(str(k)+'='+str(v),flush=True)
    print('LIMIT: simulated consumer transport; nginx/firewall/service-user execution NOT tested.',flush=True)
    print('NO_BOT_FILE_CHANGES_NO_START_NO_ORDERS_NO_PERMIT_USE',flush=True)
    return 0

if __name__ == '__main__':
    try:
        sys.exit(main())
    except (EOFError,KeyboardInterrupt):
        print('\nCANCELLED_NO_RETRY',flush=True)
        sys.exit(2)
    except Exception as exc:
        code=str(exc) if type(exc) is Hold else fixed_error(exc)
        print('HOLD_NO_RETRY: '+code,flush=True)
        for k,v in REPORT.items():
            print(str(k)+'='+str(v),flush=True)
        sys.exit(2)
