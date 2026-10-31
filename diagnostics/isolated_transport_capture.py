#!/usr/bin/env python3
"""Offline local-transport reproduction, NOT a BTC15 launcher or installer.

Starts only disposable synthetic-data diagnostic processes in a separate
loopback-only network namespace. Never calls the production controller, changes
release files/approvals/permits/markers, or loads Kalshi credentials. Captures
sanitized exception classes, validation codes, and source locations. A pass is
not live-bot acceptance and cannot recover an exception from a terminated run.
"""
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import pwd
import re
import stat
import subprocess
import sys
import time
import uuid

BASE = Path('/opt/btc15-pilot')
ETC = Path('/etc/btc15-pilot')
PYTHON = BASE / 'venv/bin/python'
HOST = '17a3c0d0866942fca267eb21b674a8a4'
SOURCE = BASE / 'release/candidate/main'
FEED = BASE / 'release/owner/brti_shared_feed_v1.py'
PINS = {
    str(FEED): '3c33030f585eaaba80b68e6db816b08169471c6c77e060617a7bc0c08821dd0d',
    str(SOURCE / 'btc15_brti_shared_consumer_v1.py'): '71097966ba6072e1bc7a97e049427d40b5838ef60a0cbfd71d2c08fdbba959b8',
    str(ETC / 'nginx.conf'): 'c7ed92ad5c1ebe2edb4c8f8b0024537c36d0bbb9f62d78d1850d0d0257c6bf85',
}


class Hold(Exception):
    pass


def need(ok, code):
    if not ok:
        raise Hold(code)


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_source(path, limit=100000):
    path = Path(path)
    for p in (path, *path.parents):
        s = p.lstat()
        need(not stat.S_ISLNK(s.st_mode) and s.st_uid == 0 and not s.st_mode & 0o022,
             'UNTRUSTED_SOURCE_PATH')
    need(path.is_file() and path.stat().st_size <= limit, 'SOURCE_SIZE_OR_TYPE')
    return path.read_bytes()


def command(*args, timeout=15, checked=True):
    r = subprocess.run(list(args), stdin=subprocess.DEVNULL, capture_output=True,
                       text=True, timeout=timeout, check=False)
    if checked and r.returncode:
        # Do not echo arbitrary stderr/environment from commands.
        raise Hold('DIAGNOSTIC_COMMAND_FAILED_' + str(r.returncode))
    return r


def require_stopped():
    r = command('systemctl', 'list-units', '--all', '--plain', '--no-legend',
                '--no-pager', '--full', 'btc15*.service', 'btc15*.timer')
    rows = [x.split() for x in r.stdout.splitlines() if x.strip()]
    need(rows, 'BTC15_UNITS_NOT_FOUND')
    for row in rows:
        need(len(row) >= 4, 'UNIT_FORMAT')
        elapsed = row[0] == 'btc15-pilot-deadline.timer' and row[2:4] == ['active', 'elapsed']
        need(row[2] in ('inactive', 'failed') or elapsed, 'ACTIVE_BTC15_UNIT_NO_CAPTURE')


def validate_id(name):
    need(re.fullmatch(r'btc15-local-capture-[0-9a-f]{12}', name) is not None,
         'DIAGNOSTIC_NAME')


def namespace_inode():
    return os.stat('/proc/self/ns/net').st_ino


def error_detail(exc):
    result = []
    seen = set()
    while exc is not None and id(exc) not in seen and len(result) < 5:
        seen.add(id(exc))
        name = type(exc).__name__
        item = {'class': name if re.fullmatch('[A-Za-z_]{1,60}', name) else 'Exception'}
        if type(exc) in (ValueError, Hold) and len(exc.args) == 1 and type(exc.args[0]) is str:
            # Report only fixed code-like values, never URLs, values, or messages.
            code = exc.args[0]
            if ((type(exc) is Hold and re.fullmatch(r'[A-Z][A-Z0-9_]{1,100}', code)) or
                    re.fullmatch(r'BRTI_[A-Z0-9_]{1,100}', code)):
                item['code'] = code
        frames = []
        tb = exc.__traceback__
        while tb:
            filename = tb.tb_frame.f_code.co_filename
            if filename.startswith(str(BASE) + '/'):
                frames.append({'file': str(Path(filename).relative_to(BASE)), 'line': tb.tb_lineno})
            tb = tb.tb_next
        if frames:
            item['frames'] = frames[-4:]
        if type(getattr(exc, 'errno', None)) is int:
            item['errno'] = exc.errno
        result.append(item)
        exc = exc.__cause__ if exc.__cause__ is not None else (
            None if exc.__suppress_context__ else exc.__context__)
    return result


def show_error(label, exc):
    print(label + '=' + json.dumps(error_detail(exc), separators=(',', ':')), flush=True)


def guarded_namespace(name, host_ns, expected=None):
    validate_id(name)
    ours = namespace_inode()
    need(ours != int(host_ns), 'LOCAL_NETWORK_ISOLATION_MISSING')
    if expected is not None:
        need(ours == int(expected), 'LOCAL_NAMESPACE_JOIN_FAILED')
    interfaces = {p.name for p in Path('/sys/class/net').iterdir()}
    need(interfaces == {'lo'}, 'LOCAL_NONLOOPBACK_INTERFACE_PRESENT')


def fixture_process(name, host_ns, netns):
    guarded_namespace(name, host_ns, netns)
    need(os.getuid() == pwd.getpwnam('btc15-brti').pw_uid, 'LOCAL_BACKEND_UID')
    # No upstream client is constructed. Reject all outbound connects, even local.
    def audit(event, args):
        if event in ('socket.connect', 'socket.getaddrinfo', 'socket.gethostbyname'):
            raise Hold('LOCAL_FIXTURE_OUTBOUND_REFUSED')
        if event == 'socket.bind':
            need(args[1] == ('127.0.0.1', 8765), 'LOCAL_FIXTURE_BIND_REFUSED')
        if event in ('subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'):
            raise Hold('LOCAL_FIXTURE_SUBPROCESS_REFUSED')
    sys.addaudithook(audit)
    need(digest(read_source(FEED)) == PINS[str(FEED)], 'LOCAL_FEED_SOURCE_MISMATCH')
    spec = importlib.util.spec_from_file_location('_synthetic_capture_feed', FEED)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    def synthetic_only():
        ts = int(time.time() * 1000) - 20
        return [dict(index_id='BRTI', source_ts_ms=ts-i*1000, value=50000.0)
                for i in range(3600)]
    poller = module.SharedBrtiPoller(synthetic_only, poll_interval_s=1.0,
                                    max_qualification_age_s=1.35)
    server = module.make_server(poller, '127.0.0.1', 8765)
    poller.start()
    print('SYNTHETIC_FIXTURE_ONLY_NO_PROVIDER_CLIENT', flush=True)
    try:
        server.serve_forever(poll_interval=.2)
    finally:
        server.server_close()
        poller.stop()


def tls_process(name, host_ns, netns):
    guarded_namespace(name, host_ns, netns)
    need(os.getuid() == pwd.getpwnam('btc15-brti-tls').pw_uid, 'LOCAL_TLS_UID')
    template = read_source(ETC / 'nginx.conf')
    need(digest(template) == PINS[str(ETC / 'nginx.conf')], 'LOCAL_PROXY_SOURCE_MISMATCH')
    runtime = Path('/run') / (name + '-tls')
    creds = Path(os.environ['CREDENTIALS_DIRECTORY'])
    need(creds.is_absolute() and creds.is_dir(), 'LOCAL_TLS_CREDENTIAL_DIRECTORY')
    # Only a disposable config copy is changed. Real configuration is untouched.
    config = template.decode().replace('/run/btc15-pilot-brti-tls', str(runtime))
    config = config.replace('@CREDENTIALS@', str(creds))
    target = runtime / 'nginx.conf'
    with target.open('x') as f:
        f.write(config)
    os.chmod(target, 0o600)
    print('ISOLATED_PROXY_EXEC_NO_PRODUCTION_SERVICE_START', flush=True)
    os.execv('/usr/sbin/nginx', ['/usr/sbin/nginx', '-c', str(target), '-g', 'daemon off;'])


def child_command(name, role, host_ns, netns, script):
    unit = name + '-' + role
    args = ['systemd-run', '--quiet', '--unit='+unit, '--service-type=exec',
            '--uid=btc15-brti' + ('-tls' if role == 'tls' else ''),
            '-p', 'PrivateNetwork=yes', '-p', 'JoinsNamespaceOf='+name+'.service',
            '-p', 'RuntimeMaxSec=30s', '-p', 'TimeoutStopSec=2s', '-p', 'Restart=no',
            '-p', 'KillMode=control-group', '-p', 'PrivateTmp=yes',
            '-p', 'ProtectSystem=strict', '-p', 'ProtectHome=yes',
            '-p', 'NoNewPrivileges=yes', '-p', 'CapabilityBoundingSet=',
            '-p', 'UMask=0077', '-p', 'MemoryMax=256M', '-p', 'TasksMax=32',
            '-p', 'CPUQuota=' + ('25%' if role == 'tls' else '50%'),
            '-p', 'StandardOutput=journal', '-p', 'StandardError=journal']
    if role == 'tls':
        args += ['-p', 'RuntimeDirectory='+unit, '-p', 'RuntimeDirectoryMode=0700',
                 '-p', 'ReadWritePaths=/run/'+unit,
                 '-p', 'LoadCredential=server.crt:/etc/btc15-pilot/tls/server.crt',
                 '-p', 'LoadCredential=server.key:/etc/btc15-pilot/secrets/server.key']
    else:
        args += ['-p', 'InaccessiblePaths=-/etc/btc15-pilot/secrets -/etc/btc15-pilot/health']
    args += [str(PYTHON), '-I', '-B', str(script), role, name, str(host_ns), str(netns)]
    return unit, args


def coordinator(name, host_ns, script):
    guarded_namespace(name, host_ns)
    netns = namespace_inode()
    # Receipt used only for original consumer metadata. Never authorization to run a bot.
    raw = read_source(ETC / 'authorized-release.json', 65536)
    receipt = json.loads(raw)
    need(receipt.get('signal_only') is True and receipt.get('orders') is False,
         'LOCAL_SIGNAL_ONLY_IDENTITY')
    need(receipt['brti']['endpoint'] == 'https://127.0.0.1:8443', 'LOCAL_ENDPOINT_MISMATCH')
    sys.path.insert(0, str(SOURCE))
    from btc15_v2_product.brti_profile import environment
    os.environ.update(environment(receipt), BTC15_LINUX_IDENTITY=str(ETC/'authorized-release.json'),
                      BTC15_LINUX_IDENTITY_SHA256=digest(raw),
                      BTC15_DATA_DIR='/run/'+name,
                      CREDENTIALS_DIRECTORY='/etc/btc15-pilot/health')
    import btc15_brti_shared_consumer_v1 as consumer
    units = []
    passed = False
    last = None
    attempts = 0
    begun = time.monotonic()
    try:
        for role in ('fixture', 'tls'):
            unit, args = child_command(name, role, host_ns, netns, script)
            units.append(unit + '.service')
            command(*args, timeout=12)
        deadline = time.monotonic() + 10
        while time.monotonic() < deadline:
            attempts += 1
            try:
                point = consumer.read_shared_brti(timeout_s=.8)
                history = consumer.read_shared_brti_ticks(timeout_s=.8, owner_epoch=point['owner_epoch'])
                consumer.require_clear()
                passed = True
                break
            except Exception as exc:
                last = exc
                time.sleep(.25)
        print('=== LOCAL_TRANSPORT_CAPTURE ===', flush=True)
        print('DATA=SYNTHETIC_ONLY; UPSTREAM_REQUESTS=0', flush=True)
        print('NETWORK=ISOLATED_LOOPBACK; REAL_CONSUMER_HTTP=YES', flush=True)
        print('HTTP_VALIDATION_ATTEMPTS='+str(attempts), flush=True)
        print('TOTAL_SECONDS='+str(round(time.monotonic()-begun,3)), flush=True)
        if passed:
            print('MUTUAL_TLS_PROXY_ORIGINAL_CONSUMER=PASS', flush=True)
            print('SYNTHETIC_HISTORY_ROWS='+str(len(history)), flush=True)
            print('CONCLUSION=LOCAL_TRANSPORT_WORKED_IN_ISOLATED_REPLAY', flush=True)
        else:
            print('MUTUAL_TLS_PROXY_ORIGINAL_CONSUMER=FAIL', flush=True)
            if last is not None:
                show_error('CAPTURED_EXCEPTION', last)
        for unit in units:
            info = command('systemctl', 'show', unit, '--no-pager',
                           '-p', 'ActiveState', '-p', 'Result', '-p', 'ExecMainStatus', checked=False)
            print('DIAGNOSTIC_UNIT '+unit+' '+ ' '.join(info.stdout.splitlines()), flush=True)
            log = command('journalctl', '-u', unit, '-n', '30', '--no-pager', '-o', 'cat', checked=False)
            # Report only known local failure categories, not raw logs or paths.
            for phrase, code in (('Permission denied','PERMISSION_DENIED'),
                                 ('cannot load certificate','CERTIFICATE_LOAD_FAILED'),
                                 ('bind()','BIND_FAILURE'),
                                 ('connect() failed','BACKEND_CONNECT_FAILED'),
                                 ('upstream timed out','BACKEND_TIMEOUT'),
                                 ('SSL_do_handshake() failed','TLS_HANDSHAKE_FAILED')):
                if phrase.lower() in log.stdout.lower():
                    print('PROXY_LOG_CODE='+code, flush=True)
            for line in log.stdout.splitlines():
                if line.startswith('LOCAL_CHILD_ERROR='):
                    try:
                        obj=json.loads(line.partition('=')[2])
                        if isinstance(obj,list):
                            print('CHILD_EXCEPTION='+json.dumps(obj),flush=True)
                    except ValueError:
                        pass
    finally:
        # Stop ONLY our randomly named disposable units, never production units.
        for unit in reversed(units):
            command('systemctl', 'stop', unit, timeout=12, checked=False)
        for unit in units:
            state=command('systemctl','show',unit,'--property=MainPID','--value',checked=False)
            print('DISPOSABLE_PID_'+unit+'='+state.stdout.strip(),flush=True)
        print('DISPOSABLE_PROCESSES_STOP_REQUESTED; PRODUCTION_UNTOUCHED', flush=True)
    print('LIMIT=NOT_A_LIVE_START; NO_HISTORICAL_EXCEPTION_RECOVERY', flush=True)
    return 0 if passed else 2


def prepare():
    need(os.geteuid() == 0, 'ROOT_REQUIRED')
    need(Path('/etc/machine-id').read_text().strip() == HOST, 'WRONG_HOST')
    require_stopped()
    for path, expected in PINS.items():
        need(digest(read_source(path)) == expected, 'SOURCE_HASH_MISMATCH')
    for user in ('btc15-brti', 'btc15-brti-tls'):
        need(pwd.getpwnam(user).pw_uid > 0, 'NONROOT_ACCOUNT_REQUIRED')
    name = 'btc15-local-capture-' + uuid.uuid4().hex[:12]
    # Non-secret source copy for non-root diagnostic processes; no original file edits.
    folder = Path('/run') / (name + '-code')
    folder.mkdir(mode=0o755)
    folder.chmod(0o755)
    script = folder / 'capture.py'
    source = Path(__file__).read_bytes()
    with script.open('xb') as f:
        f.write(source)
    os.chmod(script, 0o644)
    need(digest(script.read_bytes()) == digest(source), 'CAPTURE_COPY_MISMATCH')
    host_ns = namespace_inode()
    print('OFFLINE_CAPTURE: temporary isolated synthetic-data processes only.', flush=True)
    print('NO_CONTROLLER_CALL; NO_PROVIDER_CREDENTIALS; NO_PERMIT_OR_RELEASE_EDITS', flush=True)
    args = ['systemd-run', '--quiet', '--wait', '--pipe', '--collect',
            '--unit='+name, '--service-type=exec',
            '-p', 'PrivateNetwork=yes', '-p', 'PrivateTmp=yes', '-p', 'ProtectHome=yes',
            '-p', 'ProtectSystem=strict', '-p', 'ReadWritePaths=/run/'+name,
            '-p', 'NoNewPrivileges=yes', '-p', 'RuntimeDirectory='+name,
            '-p', 'RuntimeDirectoryMode=0700', '-p', 'RuntimeMaxSec=60s',
            '-p', 'TimeoutStopSec=2s', '-p', 'Restart=no', '-p', 'KillMode=control-group',
            '-p', 'MemoryMax=512M', '-p', 'TasksMax=64',
            str(PYTHON), '-I', '-B', str(script), 'coordinator', name, str(host_ns)]
    result = subprocess.run(args, check=False, timeout=75)
    print('CAPTURE_EXIT='+str(result.returncode), flush=True)
    return result.returncode


if __name__ == '__main__':
    try:
        if len(sys.argv) == 1:
            sys.exit(prepare())
        role = sys.argv[1]
        if role == 'coordinator' and len(sys.argv) == 4:
            sys.exit(coordinator(sys.argv[2], sys.argv[3], Path(__file__)))
        if role == 'fixture' and len(sys.argv) == 5:
            fixture_process(*sys.argv[2:])
        elif role == 'tls' and len(sys.argv) == 5:
            tls_process(*sys.argv[2:])
        else:
            raise Hold('DIAGNOSTIC_ARGUMENTS')
    except (KeyboardInterrupt, EOFError):
        print('CAPTURE_CANCELLED; NO_PRODUCTION_START', flush=True)
        sys.exit(2)
    except Exception as exc:
        show_error('LOCAL_CHILD_ERROR', exc)
        sys.exit(2)
