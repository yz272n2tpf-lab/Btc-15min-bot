"""Reproducible exact-source bundles using the existing allowlisted installer.

Reads local Git objects only. No network, deployment, native launch or capture.
Recover missing objects via authenticated GitHub before invoking this module.
"""
import argparse
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

from ops.live_recording.install import prepare, inventory, rollback
from ops.live_recording.policy import BASES, MANIFESTS, file_sha, canonical, need
from ops.recording_workflow.staging import allowlist

ROOT = Path(__file__).resolve().parents[2]
BASELINE = '0daf1ac442c4f5276d3e748421bfd13deef4ea1f'
DEPLOYED = {
    'main': 'dd46b7bc2fcc49865c49dc59eb7ad7d7316f6d72',
    'v81': 'c14b3f9b04caea13e62bcdd6fb0e5990049aa17b',
}
DEPLOYMENTS = {
    'main': 'c0993600-34b7-4501-92cd-b8d4a934b68a',
    'v81': '21bf7fd3-c294-46d9-8a0a-f551cce7a303',
}

def git(*args, data=None):
    return subprocess.check_output(['git', *args], cwd=ROOT, input=data,
                                   env=dict(os.environ, GIT_NO_LAZY_FETCH='1'))

def tree_entries(commit):
    # cat-file does not walk ancestry (git show may demand missing ancestors).
    tree = git('cat-file', 'commit', commit).splitlines()[0].split()[1].decode()
    entries = []
    for row in git('ls-tree', '-rz', tree).split(b'\0'):
        if not row:
            continue
        head, path = row.split(b'\t', 1)
        mode, kind, oid = head.decode().split()
        need(kind == 'blob' and mode in ('100644', '100755'), 'REGULAR_SOURCE_ONLY')
        name = path.decode()
        need(not Path(name).is_absolute() and '..' not in Path(name).parts, 'SOURCE_PATH')
        entries.append((name, mode, oid))
    return tree, entries

def export(commit, target):
    tree, entries = tree_entries(commit)
    need(not target.exists(), 'NEW_EXPORT_REQUIRED')
    # Refuse missing blobs BEFORE starting cat-file; never trigger a lazy fetch.
    have = set(git('cat-file', '--batch-all-objects', '--batch-check=%(objectname)').decode().split())
    need(all(oid in have for _, _, oid in entries), 'PINNED_BLOB_UNAVAILABLE')
    target.mkdir(parents=True)
    for name, mode, oid in entries:
        raw = git('cat-file', 'blob', oid)
        need(hashlib.sha1(b'blob '+str(len(raw)).encode()+b'\0'+raw).hexdigest() == oid, 'GIT_BLOB_INTEGRITY')
        p = target / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(raw)
        p.chmod(int(mode[-3:], 8))
    return dict(commit=commit, tree=tree, files=len(entries))

def deterministic_bundle(root, destination):
    with open(destination, 'xb') as f, gzip.GzipFile(filename='', mode='wb', fileobj=f, mtime=0, compresslevel=6) as g:
        with tarfile.open(fileobj=g, mode='w|', format=tarfile.PAX_FORMAT) as t:
            for p in sorted(root.rglob('*')):
                if not p.is_file():
                    continue
                need(not p.is_symlink(), 'BUNDLE_SYMLINK')
                raw = p.read_bytes()
                info = tarfile.TarInfo(p.relative_to(root).as_posix())
                info.size = len(raw)
                info.mode = 0o755 if p.stat().st_mode & 0o111 else 0o644
                info.mtime = info.uid = info.gid = 0
                info.uname = info.gname = ''
                t.addfile(info, io.BytesIO(raw))
    return dict(sha256=file_sha(destination), bytes=destination.stat().st_size)

def build(out):
    out = Path(out).resolve()
    need(not out.exists(), 'NEW_BUNDLE_DIRECTORY_REQUIRED')
    need(not out.is_relative_to('/data') and not out.is_relative_to('/app'), 'LOCAL_ONLY')
    out.mkdir(parents=True)
    result = dict(schema='BTC15_NATIVE_DIAGNOSTIC_PACKAGES_V1', baseline=BASELINE,
                  production_executed=False, capture_activated=False, orders=False, packages={})
    for lane in ('main', 'v81'):
        source, deployed, target = (out / (lane + s) for s in ('-base', '-deployed', '-installed'))
        base_id = export(BASES[lane], source)
        deployed_id = export(DEPLOYED[lane], deployed)
        before, live = inventory(source), inventory(deployed)
        receipt = prepare(source, target, ROOT, lane, before, {'files': [{'path': p} for p in allowlist()]})
        after = inventory(target)
        allowed = set(receipt['candidate_files']) | {'BTC15_RECORDER_INSTALL.json'}
        changed = {p: dict(deployed=live.get(p), candidate=after.get(p))
                   for p in sorted(set(live) | set(after)) if live.get(p) != after.get(p)}
        need(set(changed) <= allowed, 'UNAPPROVED_DEPLOYED_DIFF')
        need(not any(v['candidate'] is None for v in changed.values()), 'NO_SOURCE_DELETIONS')
        # All bootstrap entrypoints and existing native writers must be EXACTLY
        # the already deployed bytes. Only recorder/evidence modules may differ.
        entrypoints = ['btc15_v2_native.py', 'btc15_v2_launch.py', 'btc15_v2_product/worker.py']
        writers = ['btc15_information_journal_v1.py', 'btc15_information_service_v1.py', 'btc15_quote_proof_offpath_v1.py']
        need(all(after[p] == live[p] for p in entrypoints + writers), 'DEPLOYED_NATIVE_WRITER_OR_ENTRYPOINT_DRIFT')
        need(all(p.startswith(('ops/live_recording/', 'ops/recording_workflow/', 'candidates/early_recording_20261012/'))
                 or p in ('BTC15_RECORDER_INSTALL.json', 'BTC15_V2_PRODUCT_RELEASE_R1.json') for p in changed), 'CAPTURE_ONLY_DIFF')
        original = json.loads((source / 'BTC15_V2_PRODUCT_RELEASE_R1.json').read_bytes())
        freeze = json.loads((source / 'BTC15_LADDER_COMPLETION_FREEZE_20261003.json').read_bytes())
        protected = {**freeze['files_sha256' if lane == 'main' else 'v81_files_sha256'],
                     **original['lane_protected_files'][lane]}
        for p, digest in protected.items():
            need(after[p] == live[p] == digest, 'PROTECTED_PRODUCTION_BYTES:' + p)
        # Exercise the existing installer rollback on a fresh COPY, never on evidence.
        rollback_copy = out / (lane + '-rollback-test')
        shutil.copytree(target, rollback_copy)
        rolled_back = rollback(rollback_copy, source)
        deployed_rollback = out / (lane + '-deployed-rollback-test')
        shutil.copytree(target, deployed_rollback)
        for p in changed:
            dst = deployed_rollback / p
            if p in live:
                shutil.copyfile(deployed / p, dst)
            else:
                dst.unlink()
        need(inventory(deployed_rollback) == live, 'DEPLOYED_ROLLBACK_INTEGRITY')
        archive = out / ('btc15-native-diagnostic-' + lane + '-20261017.tar.gz')
        archive_info = deterministic_bundle(target, archive)
        repeat = out / (lane + '-reproducibility.tar.gz')
        need(deterministic_bundle(target, repeat) == archive_info, 'NONDETERMINISTIC_PACKAGE')
        package = dict(package_id='BTC15_NATIVE_DIAGNOSTIC_' + lane.upper() + '_20261017',
                       roles=['main', 'information'] if lane == 'main' else ['v81'],
                       base=base_id, deployed=deployed_id, deployment=DEPLOYMENTS[lane],
                       archive=archive.name, **archive_info,
                       inventory_sha256=hashlib.sha256(canonical(after)).hexdigest(),
                       manifest_sha256=after['BTC15_V2_PRODUCT_RELEASE_R1.json'],
                       install_sha256=after['BTC15_RECORDER_INSTALL.json'],
                       original_manifest_sha256=MANIFESTS[lane],
                       file_count=len(after), unchanged_deployed_files=sum(live.get(p) == h for p,h in after.items()),
                       changed_vs_deployed=changed, protected_files=protected,
                       entrypoints_and_native_writers_unchanged=True, rollback_to_original=rolled_back,
                       rollback_to_deployed=dict(exact=True, files=len(live)),
                       default_off=True, signal_only=True, orders=False)
        result['packages'][lane] = package
        (out / (lane + '-inventory.json')).write_bytes(canonical(after))
    result['packages']['information'] = dict(
        package_id='BTC15_NATIVE_DIAGNOSTIC_INFORMATION_20261017',
        shared_installation='main', standalone_installation=False,
        reason='Existing MAIN worker and volume; no new service or duplicate installation.',
        **{k: result['packages']['main'][k] for k in ('archive', 'sha256', 'bytes', 'manifest_sha256', 'install_sha256', 'inventory_sha256')})
    (out / 'PACKAGES.json').write_bytes(canonical(result))
    return result

if __name__ == '__main__':
    p = argparse.ArgumentParser()
    p.add_argument('--out', required=True)
    r = build(p.parse_args().out)
    print(json.dumps({lane: {k: v[k] for k in ('package_id', 'sha256', 'bytes')} for lane, v in r['packages'].items()}, indent=2))
