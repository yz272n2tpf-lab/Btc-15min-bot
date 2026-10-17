"""Offline check of exact packages using observed native version metadata.

No native owner, callback, queue, capture, market request or thread is started.
This is not a native performance test; it resolves package/seam prerequisites.
"""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from ops.live_recording.install import inventory
from ops.live_recording.policy import canonical

ROOT = Path(__file__).resolve().parents[2]

CHILD = r'''
import hashlib,importlib.metadata,json,os,pathlib,socket,sys,threading,types
from unittest.mock import patch
def audit(event,args):
    if event.startswith('socket.') and event not in ('socket.__new__',):
        raise RuntimeError('NETWORK_FORBIDDEN:'+event)
    if event in ('subprocess.Popen','os.system','sqlite3.connect','os.mkdir','os.remove','os.rename'):
        raise RuntimeError('SIDE_EFFECT_FORBIDDEN:'+event)
    if event=='open':
        mode=args[1];flags=args[2]
        if (isinstance(mode,str) and any(c in mode for c in 'wa+')) or flags & (os.O_WRONLY|os.O_RDWR|os.O_CREAT|os.O_TRUNC):
            raise RuntimeError('FILE_WRITE_FORBIDDEN')
sys.addaudithook(audit)
def deny_thread(*a,**k):raise RuntimeError('THREAD_START_FORBIDDEN')
threading.Thread.start=deny_thread
p=json.load(sys.stdin)
from ops.live_recording.policy import attest
# Metadata replay is explicitly separated from imports actually installed here.
with patch.object(importlib.metadata,'version',side_effect=p['versions'].__getitem__):
    attestation=attest(pathlib.Path.cwd(),p['config'],p['role'])
from ops.live_recording import adapters,bootstrap
assert bootstrap.ACTIVE is None and bootstrap.ACTIVE_ADAPTER is None
gate=types.SimpleNamespace(active=False,gap=lambda *a,**k:None)
c=types.SimpleNamespace(role=p['role'],gate=gate)
bound=adapters.install(c)
assert isinstance(bound,adapters.Adapters)
assert bootstrap.ACTIVE is None and bootstrap.ACTIVE_ADAPTER is None
print('BTC15_STATIC_COMPATIBILITY '+json.dumps(dict(role=p['role'],package_attestation_with_observed_versions='PASS',
    adapter_install_and_seam_compile_only='PASS',python=sys.version,
    attestation=attestation,native_execution=False,callbacks_executed=False,
    capture=False,threads_started=0,network=False,orders=False),sort_keys=True))
'''


def main():
    base = ROOT / 'research/native_diagnostic_20261017'
    packages = json.loads((base / 'PACKAGES.json').read_text())['packages']
    config = json.loads((base / 'campaign.approval-draft.json').read_bytes())
    receipt = json.loads((Path(__file__).parent / 'PROBE_RECEIPT.json').read_text())
    bundle = Path(os.environ.get('BTC15_TEST_BUNDLES',
                  str(ROOT.parent / 'btc15-native-bundles-20261017')))
    results = {}
    for role in ('main', 'v81', 'information'):
        lane = 'main' if role == 'information' else role
        package = packages[lane]
        archive = bundle / package['archive']
        installed = bundle / (lane + '-installed')
        assert hashlib.sha256(canonical(inventory(installed))).hexdigest() == package['inventory_sha256']
        if archive.is_file():
            assert hashlib.sha256(archive.read_bytes()).hexdigest() == package['sha256']
        env = dict(os.environ, PYTHONDONTWRITEBYTECODE='1', BTC15_RECORDING_ENABLED='0')
        p = dict(role=role, config=config, versions=receipt['producer_reads'][lane]['dependencies'])
        r = subprocess.run([sys.executable, '-B', '-c', CHILD], input=json.dumps(p),
            cwd=bundle / (lane + '-installed'), env=env, text=True,
            capture_output=True, timeout=20)
        if r.returncode:
            raise RuntimeError(role + ': ' + r.stderr[-3000:])
        lines = [line.removeprefix('BTC15_STATIC_COMPATIBILITY ')
                 for line in r.stdout.splitlines()
                 if line.startswith('BTC15_STATIC_COMPATIBILITY ')]
        assert len(lines) == 1, 'missing or ambiguous child receipt'
        results[role] = json.loads(lines[0])
        results[role]['complete_package_inventory_sha256'] = package['inventory_sha256']
        results[role]['archive_rehashed_this_check'] = archive.is_file()
    print(json.dumps(dict(result='PASS',checks=results,
        scope='OFFLINE_EXACT_PACKAGE_STATIC_INSTALL; AUTHENTIC_NATIVE_VERSION_METADATA_REPLAY',
        native_hook_timing_and_live_behavior='UNPROVEN_DIAGNOSTIC_OBJECTIVE'), indent=2, sort_keys=True))


if __name__ == '__main__':
    main()
