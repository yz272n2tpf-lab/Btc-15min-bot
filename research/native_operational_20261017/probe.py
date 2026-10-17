"""Prepared research-only operational probe; no producer writes or capture.

Execute only under a separately approved, bounded research run. Reuses the
existing private identity and lease probe. Never enrolls/replaces an SSH pin.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
import time
import uuid

from research.native_diagnostic_20261017 import lease_probe
from research.main_closeout_incremental_20261015.verify_isolated_railway_ssh_main import KEY, KNOWN, GATEWAY

ROOT = Path(__file__).resolve().parent
PREFIX = 'BTC15_OPERATIONAL_READ '
RESEARCH_MIN_FREE = 5 * 1024**3
PRODUCER_MIN_FREE = 2 * 1024**3 + 32 * 1024**2

# This fixed remote program imports only the standard library, does not load a
# native owner, and opens only approved application-source files read-only.
REMOTE = r'''
import hashlib, importlib.metadata, json, os, pathlib, platform, stat, sys, time
p = json.loads(sys.stdin.buffer.read(65537))
identity = {k: os.environ.get(k) for k in p['identity']}
bad = [k for k, v in p['identity'].items() if identity[k] != v]
if bad:
    print('BTC15_OPERATIONAL_READ '+json.dumps({'result':'BLOCKED','reason':'IDENTITY_MISMATCH','fields':bad}))
    raise SystemExit(2)
mount = pathlib.Path('/data')
if mount.is_symlink() or not mount.is_mount():
    raise SystemExit('ACTUAL_DATA_MOUNT_REQUIRED')
def sample():
    v = os.statvfs('/data')
    return {'at':time.time(),'monotonic':time.monotonic(),
            'available_bytes':v.f_bavail*v.f_frsize, 'free_bytes':v.f_bfree*v.f_frsize,
            'total_bytes':v.f_blocks*v.f_frsize,'block_size':v.f_frsize}
samples = [sample()]
files = {}
for rel in p['files']:
    if pathlib.PurePosixPath(rel).is_absolute() or '..' in pathlib.PurePosixPath(rel).parts:
        raise SystemExit('INVALID_SOURCE_PATH')
    f = pathlib.Path('/app') / rel
    if f.resolve() != f or not f.is_file():
        files[rel] = None
        continue
    fd = os.open(f, os.O_RDONLY | os.O_NOFOLLOW)
    with os.fdopen(fd,'rb') as h:
        st = os.fstat(h.fileno())
        if not stat.S_ISREG(st.st_mode) or st.st_size > 16*1024*1024:
            raise SystemExit('SOURCE_FILE_BOUND')
        digest = hashlib.sha256()
        for b in iter(lambda:h.read(65536),b''): digest.update(b)
        files[rel] = digest.hexdigest()
versions = {}
for name in p['dependencies']:
    try: versions[name] = importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError: versions[name] = None
# Two actual statvfs samples, ten seconds apart; no source or market polling.
time.sleep(max(0,10-(time.monotonic()-samples[0]['monotonic'])))
samples.append(sample())
print('BTC15_OPERATIONAL_READ '+json.dumps({'result':'READ_COMPLETE',
    'identity':identity,'python':platform.python_version(),'dependencies':versions,
    'source_hashes':files,'filesystem':samples,
    'recording_enabled':os.environ.get('BTC15_RECORDING_ENABLED')=='1',
    'production_writes':False,'capture':False,'orders':False},sort_keys=True))
'''


def check_local():
    bad = [k for k, v in lease_probe.EXPECTED.items() if os.environ.get(k) != v]
    if bad:
        raise ValueError('ISOLATED_RESEARCH_IDENTITY:' + ','.join(bad))
    mount = Path('/research-evidence')
    if mount.is_symlink() or not mount.is_mount():
        raise ValueError('ACTUAL_RESEARCH_MOUNT_REQUIRED')
    for p in (KEY, KNOWN):
        if p.is_symlink() or not p.is_file() or p.parent.is_symlink():
            raise ValueError('EXISTING_KEY_AND_HOST_PIN_REQUIRED')
    if KEY.stat().st_mode & 0o077:
        raise ValueError('PRIVATE_KEY_PERMISSIONS')
    if not 0 < KNOWN.stat().st_size <= 8192:
        raise ValueError('EXISTING_HOST_PIN_BOUND')
    v = os.statvfs(mount)
    available = v.f_bavail * v.f_frsize
    if available < RESEARCH_MIN_FREE:
        raise ValueError('RESEARCH_FREE_BYTES_BELOW_5_GIB')
    return available


def command(domain):
    return ['ssh', '-F', '/dev/null', '-T', '-oBatchMode=yes',
            '-oIdentitiesOnly=yes', '-oStrictHostKeyChecking=yes',
            '-oUserKnownHostsFile=' + str(KNOWN),
            '-oGlobalKnownHostsFile=/dev/null', '-oUpdateHostKeys=no',
            '-oCheckHostIP=no', '-oConnectTimeout=10', '-oConnectionAttempts=1',
            '-oServerAliveInterval=5', '-oServerAliveCountMax=2',
            '-i', str(KEY), domain + '@' + GATEWAY,
            'python -B -c ' + shlex.quote(REMOTE)]


def assess(plan, answer):
    if answer.get('result') != 'READ_COMPLETE':
        raise ValueError('REMOTE_IDENTITY_OR_READ_FAILED')
    if answer.get('identity') != plan['identity']:
        raise ValueError('REMOTE_IDENTITY_MISMATCH')
    file_mismatches = [k for k, v in plan['files'].items()
                       if answer.get('source_hashes', {}).get(k) != v]
    version_mismatches = [k for k, v in plan['dependencies'].items()
                          if answer.get('dependencies', {}).get(k) != v]
    samples = answer['filesystem']
    if len(samples) != 2 or samples[1]['monotonic'] <= samples[0]['monotonic']:
        raise ValueError('FILESYSTEM_SAMPLE_CLOCK')
    free = min(s['available_bytes'] for s in samples)
    rate = max(0, samples[0]['available_bytes'] - samples[1]['available_bytes']) / (samples[1]['monotonic'] - samples[0]['monotonic'])
    answer['assessment'] = dict(source_file_mismatches=file_mismatches,
        dependency_mismatches=version_mismatches,
        exact_capture_plus_reserve_bytes=PRODUCER_MIN_FREE,
        capture_plus_reserve_floor_pass=free >= PRODUCER_MIN_FREE,
        short_sample_net_consumption_bytes_per_second=rate,
        growth_allowance_still_requires_review=True,
        native_import_and_hook_compatibility_not_proven=True)
    return answer


def run():
    free = check_local()  # Before any subprocess, network or receipt creation.
    plan = json.loads((ROOT / 'NATIVE_READ_PLAN.json').read_text())
    receipt = Path('/research-evidence') / ('native-operational-' + uuid.uuid4().hex + '.json')
    result = dict(schema='BTC15_OPERATIONAL_PROBE_V1', at=time.time(),
                  research_free_bytes=free, producer_reads={}, result='BLOCKED',
                  production_changes=False, capture=False, orders=False)
    try:
        # Serial, at most one connection per producer. A source/identity mismatch
        # aborts the operation; low space does not prevent independent lease work.
        for role in ('main', 'v81'):
            p = plan[role]
            raw = json.dumps(p, separators=(',', ':'))
            if len(raw.encode()) > 65536:
                raise ValueError('READ_PLAN_BOUND')
            r = subprocess.run(command(p['domain']), input=raw, text=True,
                capture_output=True, timeout=45, check=False)
            if r.returncode or len(r.stdout.encode()) > 131072:
                raise ValueError(role + ':SSH_READ_FAILED:' + str(r.returncode))
            rows = [s[len(PREFIX):] for s in r.stdout.splitlines() if s.startswith(PREFIX)]
            if len(rows) != 1:
                raise ValueError(role + ':REMOTE_RESPONSE_COUNT')
            answer = assess(p, json.loads(rows[0]))
            result['producer_reads'][role] = answer
            if answer['assessment']['source_file_mismatches']:
                raise ValueError(role + ':PINNED_RUNTIME_SOURCE_MISMATCH')
        result['lease'] = lease_probe.run()  # Existing test; no database opens.
        result['result'] = 'READS_COMPLETE' if result['lease']['result'] == 'PASS' else 'BLOCKED'
        result['diagnostic_authorized'] = False
    except Exception as e:
        # Exception type only for subprocess exceptions; never dump SSH stdout,
        # private keys, inherited environment or arbitrary remote stderr.
        result['reason'] = str(e) if isinstance(e, ValueError) else type(e).__name__
    finally:
        blob = (json.dumps(result, sort_keys=True, indent=2) + '\n').encode()
        with receipt.open('xb') as f:
            os.chmod(receipt, 0o600)
            f.write(blob); f.flush(); os.fsync(f.fileno())
        fd = os.open(receipt.parent, os.O_RDONLY | os.O_DIRECTORY)
        try: os.fsync(fd)
        finally: os.close(fd)
    print(json.dumps({'result':result['result'],'receipt':str(receipt),
                      'sha256':hashlib.sha256(blob).hexdigest(),
                      'diagnostic_authorized':False}, sort_keys=True), flush=True)
    return 0 if result['result'] == 'READS_COMPLETE' else 2


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--authorized-research-only', action='store_true', required=True)
    parser.parse_args()
    try:
        raise SystemExit(run())
    except Exception as e:
        print(json.dumps({'result':'BLOCKED','reason':str(e) if isinstance(e, ValueError)
                          else type(e).__name__,'diagnostic_authorized':False}))
        raise SystemExit(2)
