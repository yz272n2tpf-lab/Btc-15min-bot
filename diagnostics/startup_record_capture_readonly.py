#!/usr/bin/env python3
"""Read preserved BTC15 startup evidence. Never imports or invokes BTC15 code.

No installer, startup runner, health request, approval generator, or rearm.
Only fixed local files, systemctl show, and the failed run's journal are read.
Credential files, environment values, raw log messages and market data are omitted.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import stat
import subprocess
from datetime import datetime, timezone

BASE = Path('/opt/btc15-pilot')
ETC = Path('/etc/btc15-pilot')
HOST = '17a3c0d0866942fca267eb21b674a8a4'
CONTROLLER = 'btc15-permission-recovery-202610292130.service'
UNITS = (CONTROLLER, 'btc15-pilot-brti.service', 'btc15-pilot-brti-tls.service',
         'btc15-pilot-brti-firewall.service', 'btc15-pilot-failure-stop.service')
START = '2026-10-30 01:28:20 UTC'
END = '2026-10-30 01:29:10 UTC'
PINS = {'/opt/btc15-pilot/kit/tools/control.py': '3d6feee8d9119e60293f27f80b69f1f0988ee07fea0a76563bd25b051ffb9e38', '/opt/btc15-pilot/kit/tools/brti_health.py': '7c994fb5daacca0dff6a1982e9e90d94d85dfca9af3fb26633668fc5cace409d', '/opt/btc15-pilot/kit/tools/brti_owner.py': '2a61a14e67520796d8984405356f77f2134b57b06e4f5670e92bd2ac9111c789', '/opt/btc15-pilot/kit/tools/brti_tls.py': 'f25680193e6d47d5a91bbd3687c64bb98befd9ddc45881b05ad51ded07bf4a91', '/opt/btc15-pilot/release/candidate/main/btc15_v2_product/linux_installation.py': '433cb1312fd2f44a2a31b1c715b5e2a7ed018582cb7e154c6a3d8b2764b17edc', '/opt/btc15-pilot/release/candidate/main/btc15_v2_product/linux_identity.py': '656ff7070173affe96fcfad5dd5e72cc83a3474cd237401a12fbdd475bce24ec', '/opt/btc15-pilot/release/candidate/main/btc15_v2_product/brti_profile.py': '1ca2850c32906a20aced226e1bca663f9adcf43e4fa4d528043116f1e86bd4af', '/opt/btc15-pilot/release/candidate/main/btc15_v2_product/local_tls.py': '3097b1fd6348d8bbc9e27e85f9be7a33d96e91581098d4cb3d082cc3c14dfba8', '/opt/btc15-pilot/release/candidate/main/btc15_brti_shared_consumer_v1.py': '71097966ba6072e1bc7a97e049427d40b5838ef60a0cbfd71d2c08fdbba959b8', '/opt/btc15-pilot/release/owner/brti_shared_feed_v1.py': '3c33030f585eaaba80b68e6db816b08169471c6c77e060617a7bc0c08821dd0d', '/opt/btc15-pilot/release/owner/brti_shared_feed_guarded_launcher_v1.py': 'bca189306208c40df22e8fbca1a574eb48db98fa8d44270b63702b1fb002d546', '/etc/systemd/system/btc15-pilot-brti.service': 'b3d6ebedaf456d0a3bdd235d7a464093689092aee43c3044fc2414f41631557f', '/etc/systemd/system/btc15-pilot-brti-tls.service': '11c6ac9fb465a41ee83435809e1e6349bdba265ef0b9faea26606c3718adaa4e', '/etc/btc15-pilot/brti.env': '9fb1f436ad6bb73bfdc8afb24ded61104276c5fb9f5e3408d6f268219a5691c1', '/etc/btc15-pilot/nginx.conf': 'c7ed92ad5c1ebe2edb4c8f8b0024537c36d0bbb9f62d78d1850d0d0257c6bf85', '/root/BTC15_5PM_BRTI_PERMISSION_RECOVERY_V1.py': '053184cc05f15daab7dbeb71433ea37159e833baecd0ca721804ddf4ca22d3de', '/opt/btc15-pilot/release/CANDIDATE_MANIFEST.json': '5eebd8db46c35b86237436e3196853f08db2a0549fa590292f35be377dbfc257'}
PROPS = ('LoadState', 'FragmentPath', 'DropInPaths', 'Type', 'User', 'Group',
         'UMask', 'PrivateNetwork', 'NetworkNamespacePath', 'RestrictAddressFamilies',
         'IPAddressDeny', 'IPAddressAllow', 'CPUQuotaPerSecUSec', 'CPUQuotaPeriodUSec',
         'ProtectSystem', 'ProtectHome', 'NoNewPrivileges', 'CapabilityBoundingSet',
         'RuntimeDirectoryMode', 'RuntimeDirectoryPreserve', 'EnvironmentFiles',
         'MainPID', 'ActiveState', 'SubState', 'Result')
CODES = frozenset(('BRTI_STARTUP_FRESHNESS_TIMEOUT', 'BRTI_SOURCE_UNQUALIFIED',
    'BRTI_STRICT_FRESHNESS', 'BRTI_HTTP_NOT_200', 'BRTI_SAMPLE_FIELDS',
    'BRTI_HISTORY_SOURCE', 'BRTI_HISTORY_OWNER_MISMATCH', 'BRTI_TLS_CA_MISMATCH',
    'BRTI_TLS_CREDENTIALS_REQUIRED', 'BRTI_TLS_KEY_PERMISSIONS',
    'BRTI_OWNER_SOURCE_MISMATCH', 'BRTI_INTEGRITY_SCHEMA', 'BRTI_COHORT_INTEGRITY_STOP',
    'BRTI_CONFIG_BINDING', 'INDEPENDENT_PACKAGE', 'LINUX_SOURCE_HASH',
    'LINUX_CANDIDATE_IDENTITY', 'INSTALL_OPERATION_HASH', 'INSTALL_CONFIG_HASH',
    'INSTALL_UNIT_HASH', 'INSTALL_HOST_ID', 'SESSION_ALREADY_USED_NO_AUTOMATIC_REARM',
    'ORIGINAL_CONTROLLER_DID_NOT_CONFIRM_START_NO_RETRY'))
CLASSES = frozenset(('AssertionError', 'PermissionError', 'FileNotFoundError',
    'ValueError', 'KeyError', 'ConnectionError', 'ReadTimeout', 'ConnectTimeout',
    'SSLError', 'SSLCertVerificationError', 'CalledProcessError', 'OSError',
    'TimeoutExpired', 'RuntimeError'))


def emit(label, value):
    print(label + ' ' + json.dumps(value, sort_keys=True, separators=(',', ':')), flush=True)


def read_fixed(path, limit=1048576):
    path = Path(path)
    fd = os.open(path, os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK)
    try:
        info = os.fstat(fd)
        if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
            raise ValueError('FILE_TYPE_OR_SIZE')
        data = b''
        while len(data) <= limit:
            part = os.read(fd, min(65536, limit + 1 - len(data)))
            if not part:
                break
            data += part
        if len(data) > limit:
            raise ValueError('FILE_SIZE')
        return data
    finally:
        os.close(fd)


def command(args):
    # No shell and no caller-provided arguments; commands are explicitly bounded.
    allowed_show = (args[:2] == ['systemctl', 'show'] and args[2] in UNITS
                    and args[3] == '--no-pager'
                    and args[4:] == ['--property=' + ','.join(PROPS)])
    expected_journal = ['journalctl', '--no-pager', '--quiet', '-o', 'json',
                        '--since', START, '--until', END, '-n', '500']
    for unit in UNITS:
        expected_journal += ['-u', unit]
    if not (allowed_show or args == expected_journal):
        raise ValueError('READ_COMMAND_NOT_ALLOWLISTED')
    return subprocess.run(args, stdin=subprocess.DEVNULL, capture_output=True,
                          text=True, timeout=6, check=False,
                          env={'PATH': '/usr/sbin:/usr/bin:/sbin:/bin',
                               'LC_ALL': 'C', 'SYSTEMD_PAGER': 'cat'})


def sanitize_event(row):
    raw = row.get('MESSAGE', '')
    message = raw if isinstance(raw, str) else ''
    unit = row.get('UNIT') or row.get('_SYSTEMD_UNIT')
    unit = unit if unit in UNITS else 'manager'
    stamp = str(row.get('__REALTIME_TIMESTAMP', ''))
    if not re.fullmatch(r'[0-9]{10,20}', stamp):
        return None
    event = {'at_utc': datetime.fromtimestamp(int(stamp)/1e6, timezone.utc).isoformat(),
             'unit': unit}
    mono = str(row.get('__MONOTONIC_TIMESTAMP', ''))
    if re.fullmatch(r'[0-9]{1,20}', mono):
        event['monotonic_us'] = int(mono)
    pid = str(row.get('_PID', ''))
    if re.fullmatch(r'[0-9]{1,10}', pid):
        event['pid'] = int(pid)
    comm = row.get('_COMM')
    if comm in ('systemd', 'python', 'python3', 'python3.12', 'nginx'):
        event['process'] = comm
    tags = []
    markers = (
        ('EXECUTING_UNCHANGED_ORIGINAL_CONTROLLER_ONCE_WITH_UMASK_0022', 'CONTROLLER_INVOKED_UMASK_0022'),
        ('BRTI SHARED FEED ENABLED', 'OWNER_LAUNCHER_ENABLED'),
        ('BRTI SHARED FEED V1 START', 'OWNER_FEED_STARTED'),
        ('BRTI_SHARED CONFIG', 'OWNER_CONFIG'),
        ('BRTI_SHARED HEARTBEAT', 'OWNER_HEARTBEAT_PRESENT'),
        ('BRTI_START_REFUSED', 'OWNER_WRAPPER_REFUSED'),
        ('TLS_START_REFUSED', 'TLS_WRAPPER_REFUSED'),
        ('PILOT_CONTROL_REFUSED', 'CONTROLLER_REFUSED'),
        ('BRTI_STARTUP_CHECK_FAILURE', 'READINESS_DETAIL_PRESENT'),
        ('PILOT_FAILURE_DETAIL', 'CONTROLLER_DETAIL_PRESENT'),
        ('STOPPED: pilot units only', 'PROTECTED_STOP_CONFIRMED'),
        ('Permission denied', 'PERMISSION_DENIED'),
        ('cannot load certificate', 'NGINX_CERTIFICATE_LOAD_FAILURE'),
        ('SSL_do_handshake() failed', 'NGINX_TLS_HANDSHAKE_FAILURE'),
        ('connect() failed', 'NGINX_BACKEND_CONNECT_FAILURE'),
        ('upstream timed out', 'NGINX_BACKEND_TIMEOUT'),
        ('bind() to', 'NGINX_BIND_FAILURE'),
        ('No such file or directory', 'MISSING_PATH'),
        ('oom-kill', 'OOM_KILL'))
    for phrase, tag in markers:
        if phrase in message:
            tags.append(tag)
    if comm == 'systemd':
        for prefix, tag in (('Starting ', 'UNIT_STARTING'), ('Started ', 'UNIT_STARTED'),
                            ('Stopping ', 'UNIT_STOPPING'), ('Stopped ', 'UNIT_STOPPED')):
            if message.startswith(prefix):
                tags.append(tag)
        for phrase, tag in (('Deactivated successfully', 'UNIT_DEACTIVATED'),
                            ('Main process exited', 'PROCESS_EXITED'),
                            ('Failed with result', 'UNIT_FAILED')):
            if phrase in message:
                tags.append(tag)
        cpu = re.search(r'Consumed ([0-9]+(?:\.[0-9]+)?)([smu]s|s) CPU time', message)
        if cpu:
            event['cpu_time'] = cpu.group(1) + cpu.group(2)
    words = set(re.findall(r'\b[A-Za-z][A-Za-z0-9_]*\b', message))
    codes = sorted(words & CODES)
    classes = sorted(words & CLASSES)
    if codes:
        event['codes'] = codes
    if classes:
        event['exceptions'] = classes
    if tags:
        event['events'] = tags
    if not (tags or codes or classes or 'cpu_time' in event):
        return None
    return event


def main():
    if os.geteuid() != 0 or read_fixed('/etc/machine-id', 256).decode().strip() != HOST:
        raise ValueError('EXPECTED_EXISTING_SERVER_ROOT_REQUIRED')
    emit('CAPTURE', {'scope': 'preserved_2026-10-29_2130_EDT_startup',
                     'starts': 0, 'network_requests': 0, 'bot_imports': 0,
                     'changes_to_bot_or_approvals': 0})
    # Hash only startup-path files, never run the full installation validator.
    for path, expected in PINS.items():
        try:
            actual = hashlib.sha256(read_fixed(path)).hexdigest()
            emit('SOURCE', {'path': path, 'match': actual == expected, 'sha256': actual})
        except (OSError, ValueError) as exc:
            emit('SOURCE_UNAVAILABLE', {'path': path, 'type': type(exc).__name__})
    # These are present-day manager properties, not a reconstruction of a lost environment.
    for unit in (CONTROLLER, UNITS[1], UNITS[2]):
        result = command(['systemctl', 'show', unit, '--no-pager',
                          '--property=' + ','.join(PROPS)])
        props = dict(line.split('=', 1) for line in result.stdout.splitlines() if '=' in line)
        safe = {key: props[key] for key in PROPS if key in props}
        emit('CURRENT_UNIT_CONTEXT', {'unit': unit, 'exit': result.returncode, 'properties': safe})
    for name in ('session.json', 'stopped.json'):
        path = Path('/run/btc15-pilot') / name
        try:
            raw = read_fixed(path, 65536)
            value = json.loads(raw)
            info = path.lstat()
            safe = {'file': name, 'sha256': hashlib.sha256(raw).hexdigest(),
                    'mode': oct(stat.S_IMODE(info.st_mode)), 'uid': info.st_uid}
            for key in ('armed_at', 'stop_at', 'at'):
                if type(value.get(key)) in (int, float):
                    safe[key] = value[key]
            reason = value.get('reason')
            if reason in ('startup-failure', 'finite-deadline', 'operator-stop', 'authorization-or-deadline'):
                safe['reason'] = reason
            emit('PRESERVED_MARKER', safe)
        except (OSError, ValueError) as exc:
            emit('MARKER_UNAVAILABLE', {'file': name, 'type': type(exc).__name__})
    args = ['journalctl', '--no-pager', '--quiet', '-o', 'json',
            '--since', START, '--until', END, '-n', '500']
    for unit in UNITS:
        args += ['-u', unit]
    result = command(args)
    lines = result.stdout.splitlines()
    emit('FAILED_RUN_JOURNAL', {'since_utc': START, 'until_utc': END,
                               'exit': result.returncode, 'rows': len(lines),
                               'possibly_capped': len(lines) >= 500,
                               'raw_output_sha256': hashlib.sha256(result.stdout.encode()).hexdigest()})
    omitted = 0
    for line in lines:
        try:
            event = sanitize_event(json.loads(line))
        except (ValueError, TypeError, OverflowError, AttributeError):
            event = None
        if event is None:
            omitted += 1
        else:
            emit('EVENT', event)
    emit('END', {'unreported_journal_rows': omitted,
                 'no_start_no_rearm_no_orders': True,
                 'limit': 'Cannot recreate exceptions never logged or prove historical socket readiness from Type=simple.'})


if __name__ == '__main__':
    def deadline(signum, frame):
        raise TimeoutError('CAPTURE_TIME_LIMIT')
    signal.signal(signal.SIGALRM, deadline)
    signal.alarm(35)
    try:
        main()
    except Exception as exc:
        emit('CAPTURE_STOPPED', {'type': type(exc).__name__})
        raise SystemExit(2)
