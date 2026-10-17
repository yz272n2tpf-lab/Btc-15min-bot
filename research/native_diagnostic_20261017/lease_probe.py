"""Prepared probe for the EXISTING isolated Railway volume, never production.

No database, producer, source stream, private key or historical evidence opens.
Run only after separate execution/start approval. Creates one new receipt directory
and uses the existing ReaderLease lock files without unlinking them.
"""
import argparse
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time
import uuid

EXPECTED = {
    'RAILWAY_PROJECT_ID': '87ad03d5-e1d6-47d6-b1ea-159cd7594686',
    'RAILWAY_ENVIRONMENT_ID': '12d241b7-23b4-4421-aafd-142e943555ee',
    'RAILWAY_SERVICE_ID': '1fff593b-8b09-4cc4-8c51-f9603082657f',
    'RAILWAY_VOLUME_ID': '2dba2ef6-b84d-4abf-9d04-58a1e77082c5',
    'RAILWAY_VOLUME_MOUNT_PATH': '/research-evidence',
}
RECOVERY_SHA256 = 'a18f6d5892489e7a01aa20c67d794b59f747b602cd71537f8518d355bf28326a'

def run():
    mismatch = [k for k, v in EXPECTED.items() if os.environ.get(k) != v]
    if mismatch:
        return dict(result='BLOCKED', reason='ISOLATED_RESEARCH_IDENTITY', fields=mismatch)
    mount = Path('/research-evidence')
    if not mount.is_mount() or mount.is_symlink():
        return dict(result='BLOCKED', reason='ACTUAL_RESEARCH_MOUNT_REQUIRED')
    from ops.live_recording import recovery_state
    if hashlib.sha256(Path(recovery_state.__file__).read_bytes()).hexdigest() != RECOVERY_SHA256:
        return dict(result='BLOCKED', reason='EXACT_READER_LEASE_CODE_REQUIRED')
    child = subprocess.Popen([sys.executable, '-B', '-c', '''
from ops.live_recording.recovery_state import ReaderLease
import sys
v=ReaderLease()
print('LOCKED',flush=True)
sys.stdin.read()
v.close()
'''], stdin=subprocess.PIPE, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    try:
        import selectors
        with selectors.DefaultSelector() as sel:
            sel.register(child.stdout, selectors.EVENT_READ)
            if not sel.select(10):
                raise RuntimeError('LEASE_HOLDER_START_TIMEOUT')
        if child.stdout.readline().strip() != 'LOCKED':
            raise RuntimeError('READER_LEASE_BUSY_OR_UNAVAILABLE')
        paths = [Path('/tmp') / ('btc15-bounded-reader-' + str(os.getuid()) + '.lock'),
                 mount / '.btc15-bounded-reader.lock']
        inodes = [p.stat().st_ino for p in paths]
        # Test the volume lock independently: a global /tmp conflict alone is
        # insufficient evidence that the mounted filesystem enforces exclusion.
        contender = '''
import fcntl,os
p='/research-evidence/.btc15-bounded-reader.lock'
fd=os.open(p,os.O_RDWR|os.O_NOFOLLOW|os.O_CLOEXEC)
try:
 try:fcntl.flock(fd,fcntl.LOCK_EX|fcntl.LOCK_NB)
 except BlockingIOError:print('VOLUME_EXCLUDED');raise SystemExit(0)
 raise SystemExit(3)
finally:os.close(fd)
'''
        r = subprocess.run([sys.executable, '-B', '-c', contender], capture_output=True, text=True, timeout=10)
        if r.returncode != 0 or r.stdout.strip() != 'VOLUME_EXCLUDED':
            raise RuntimeError('MOUNTED_VOLUME_EXCLUSION_FAILED')
        try:
            unexpected = recovery_state.ReaderLease()
        except ValueError as e:
            if 'SERIAL_READER_REQUIRED' not in str(e):
                raise
        else:
            unexpected.close()
            raise RuntimeError('SECOND_READER_NOT_EXCLUDED')
        child.kill()  # ONLY this probe's child process; never any service PID.
        child.communicate(timeout=10)
        if child.returncode != -signal.SIGKILL:
            raise RuntimeError('PROBE_CHILD_NOT_SIGKILLED')
        successor = recovery_state.ReaderLease()
        successor.close()
        if inodes != [p.stat().st_ino for p in paths]:
            raise RuntimeError('LEASE_INODE_REPLACED')
        out = mount / ('native-lease-probe-' + uuid.uuid4().hex)
        out.mkdir(mode=0o700)
        result = dict(result='PASS', at=time.time(), identity=EXPECTED,
                      reader_code_sha256=RECOVERY_SHA256, mounted_volume_exclusion=True,
                      full_reader_exclusion=True, sigkill_release_and_reacquisition=True,
                      lock_inodes_preserved=True, databases_opened=0,
                      historical_files_changed=0, production_changes=False, capture=False)
        from ops.live_recording.policy import atomic
        atomic(out / 'RESULT.json', result)
        return dict(result, receipt_path=str(out / 'RESULT.json'))
    finally:
        if child.poll() is None:
            child.kill()
            child.communicate(timeout=10)

if __name__ == '__main__':
    argparse.ArgumentParser(description=__doc__).parse_args()
    try:
        result = run()
    except Exception as e:
        result = dict(result='FAIL', reason=type(e).__name__ + ':' + str(e))
    print(json.dumps(result, sort_keys=True))
    raise SystemExit(0 if result['result'] == 'PASS' else 2)
