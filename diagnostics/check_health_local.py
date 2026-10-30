#!/usr/bin/env python3
"""BTC15 local health prerequisite check: no network, writes, starts or permit use.

Checks existing installation validators and mutual TLS entirely in memory.
Never prints keys, certificates, receipt contents, URLs or environment values.
A pass is not a live feed test and does not authorize a start.
"""
import hashlib
import json
import os
from pathlib import Path
import re
import ssl
import sys

ETC = Path('/etc/btc15-pilot')
SOURCE = Path('/opt/btc15-pilot/release/candidate/main')
RESULTS = {}


def deny_changes(event, args):
    if event.startswith(('socket.', 'subprocess.')) or event in (
        'os.system', 'os.posix_spawn', 'os.exec', 'os.fork', 'sqlite3.connect',
        'os.remove', 'os.rename', 'os.rmdir', 'os.mkdir', 'os.chmod',
        'os.chown', 'os.link', 'os.symlink', 'os.truncate', 'os.utime'):
        raise RuntimeError('READ_ONLY_CHECK_BLOCKED_SIDE_EFFECT')
    if event == 'open':
        mode, flags = args[1:3]
        if ((isinstance(mode, str) and any(x in mode for x in 'wax+')) or
            (isinstance(flags, int) and flags &
             (os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND))):
            raise RuntimeError('READ_ONLY_CHECK_BLOCKED_FILE_WRITE')


def error_code(exc):
    # Only fixed machine-readable codes; never arbitrary exception messages.
    if isinstance(exc, ssl.SSLCertVerificationError):
        return 'TLS_CERT_VERIFY_CODE_' + str(exc.verify_code)
    if isinstance(exc, ssl.SSLError):
        reason = str(getattr(exc, 'reason', 'SSL_ERROR'))
        return reason if re.fullmatch('[A-Z0-9_]{1,80}', reason) else 'SSL_ERROR'
    if type(exc) is ValueError:
        code = str(exc).split(':', 1)[0]
        if re.fullmatch('[A-Z][A-Z0-9_]{1,80}', code):
            return code
    return type(exc).__name__


def check(label, fn):
    try:
        value = fn()
    except Exception as exc:
        RESULTS[label] = 'FAIL ' + error_code(exc)
        return None
    RESULTS[label] = 'PASS'
    return value


def contexts(ca, server_cert, server_key, client_cert, client_key):
    # No sockets and no environment SSLKEYLOGFILE use.
    client = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    client.minimum_version = ssl.TLSVersion.TLSv1_2
    client.load_verify_locations(cafile=str(ca))
    client.load_cert_chain(str(client_cert), str(client_key), password='')
    server = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
    server.minimum_version = ssl.TLSVersion.TLSv1_2
    server.verify_mode = ssl.CERT_REQUIRED
    server.load_verify_locations(cafile=str(ca))
    server.load_cert_chain(str(server_cert), str(server_key), password='')
    return client, server


def handshake(client, server):
    ci, co, si, so = (ssl.MemoryBIO() for _ in range(4))
    c = client.wrap_bio(ci, co, server_hostname='127.0.0.1')
    s = server.wrap_bio(si, so, server_side=True)
    done = [False, False]
    for _ in range(20):
        for i, peer in enumerate((c, s)):
            if not done[i]:
                try:
                    peer.do_handshake()
                    done[i] = True
                except (ssl.SSLWantReadError, ssl.SSLWantWriteError):
                    pass
        for outgoing, incoming in ((co, si), (so, ci)):
            if outgoing.pending:
                incoming.write(outgoing.read())
        if all(done):
            return True
    raise ValueError('TLS_MEMORY_HANDSHAKE_INCOMPLETE')


def main():
    if os.geteuid() != 0 or not SOURCE.is_dir():
        print('HOLD: EXISTING_SERVER_ROOT_REQUIRED', flush=True)
        return 2
    sys.dont_write_bytecode = True
    sys.addaudithook(deny_changes)
    sys.path.insert(0, str(SOURCE))
    try:
        from btc15_v2_product.linux_installation import receipt, verify_host
        from btc15_v2_product.brti_profile import check as profile_check, environment
        from btc15_v2_product.local_tls import request_options
    except Exception as exc:
        print('MODULE_IMPORT: FAIL ' + error_code(exc), flush=True)
        return 2
    print('CHECKING_LOCAL_HEALTH_ONLY; NO_START; NO_NETWORK', flush=True)
    r = check('STORED_RELEASE_IDENTITY', receipt)
    if r is not None:
        check('INSTALLED_HOST_VALIDATION', lambda: verify_host(r))
        check('STORED_BRTI_PROFILE', lambda: profile_check(
            r, environment(r), production=r.get('evidence_class') == 'PRODUCTION'))
        os.environ['CREDENTIALS_DIRECTORY'] = str(ETC / 'health')
        check('HEALTH_CLIENT_FILE_RULES', lambda: request_options(r['brti']))
    pair = check('TLS_KEY_CERT_LOAD', lambda: contexts(
        ETC / 'tls/ca.crt', ETC / 'tls/server.crt', ETC / 'secrets/server.key',
        ETC / 'health/brti-client.crt', ETC / 'health/brti-client.key'))
    if pair is not None:
        check('MUTUAL_TLS_IN_MEMORY', lambda: handshake(*pair))
    else:
        RESULTS['MUTUAL_TLS_IN_MEMORY'] = 'NOT_RUN: KEY_CERT_LOAD_FAILED'
    print('=== LOCAL_HEALTH_RESULT ===', flush=True)
    for name, result in RESULTS.items():
        print(name + ': ' + result, flush=True)
    print('NO_FILES_CHANGED; NO_SERVICES_STARTED; NO_PERMITS_USED', flush=True)
    print('LIMIT: DOES_NOT_TEST_NGINX_FIREWALL_OR_UPSTREAM_BRTI', flush=True)
    return 0 if all(v == 'PASS' for v in RESULTS.values()) else 2


if __name__ == '__main__':
    sys.exit(main())
