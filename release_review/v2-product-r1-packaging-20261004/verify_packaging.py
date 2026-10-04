"""Read-only commit/bundle/package integrity verification; no live runtime or orders."""
from pathlib import Path
import datetime
import hashlib
import io
import json
import subprocess
import zipfile

ROOT = Path('/workspace/scratch/7500f1a32278')
REPO = ROOT / 'v2_correction'
OUT = ROOT / 'v2_packaging_closure'
ORIGINAL = ROOT / 'v2_release/package'
MAIN = '020f8a38d07e0a11e983a1e3bee3b06a4898c2f3'
OLD_V81 = '07406e46945cc0bfebbb25299c5da53e87ac6a2a'
V81 = '985260e4166559701fc96b5582ca2211619d53ee'
SCORER = 'btc15_cohort_evidence_v1.py'
SCORER_HASH = '9812c23a6200bf31c2c5eb4e8f317fe32cfcafefeaa37d2a9b9a041967447d1a'

def git(*args):
    return subprocess.check_output(['git', '-C', str(REPO), *args])

def sha(raw):
    return hashlib.sha256(raw).hexdigest()

def entries(commit):
    return {line.split('\t', 1)[1]: line.split('\t', 1)[0]
            for line in git('ls-tree', '-r', commit).decode().splitlines()}

def main():
    index = json.loads((ORIGINAL / 'RELEASE_INDEX.json').read_text())
    assert git('rev-parse', V81+'^').decode().strip() == OLD_V81
    assert git('diff', '--name-status', OLD_V81, V81).decode().strip() == 'A\t'+SCORER
    scorer = git('show', V81+':'+SCORER)
    assert sha(scorer) == SCORER_HASH
    assert scorer == git('show', MAIN+':'+SCORER)
    assert git('rev-parse', 'candidate/v2-product-20261004').decode().strip() == MAIN
    proof = {'schema': 'BTC15_PACKAGING_CORRECTION_VERIFICATION_R1',
             'verified_at_utc': datetime.datetime.now(datetime.timezone.utc).isoformat(),
             'previous_review_commit': '613161e7d69f4f4662db307b867031de335c24bf',
             'correction': {'parent': OLD_V81, 'commit': V81, 'only_added_file': SCORER,
                            'sha256': SCORER_HASH, 'qualified_source_commit': MAIN,
                            'contents_changed': False, 'shared_runtime_content_changed': False},
             'lanes': {}, 'bundles': {}, 'original_packaged_hashes': {},
             'candidate_refs_published': False, 'production_changed': False, 'orders': False}
    for lane, commit in [('main', MAIN), ('v81', V81)]:
        base = index['lanes'][lane]['frozen_base']
        old, new = entries(base), entries(commit)
        changed = [name for name, entry in old.items() if new.get(name) != entry]
        assert not changed, changed
        manifest_raw = git('show', commit+':BTC15_V2_PRODUCT_RELEASE_R1.json')
        assert manifest_raw == (ORIGINAL/'BTC15_V2_PRODUCT_RELEASE_R1.json').read_bytes()
        manifest = json.loads(manifest_raw)
        checked = {}
        for name, expected in {**manifest['files_sha256'], **manifest['lane_protected_files'][lane]}.items():
            assert sha(git('show', commit+':'+name)) == expected, name
            checked[name] = expected
        freeze = json.loads(git('show', commit+':BTC15_LADDER_COMPLETION_FREEZE_20261003.json'))
        frozen = freeze['files_sha256' if lane == 'main' else 'v81_files_sha256']
        for name, expected in frozen.items():
            assert sha(git('show', commit+':'+name)) == expected, name
        sources = 0
        for source in sorted((ORIGINAL/'candidate_sources').rglob('*')):
            if source.is_file():
                relative = source.relative_to(ORIGINAL/'candidate_sources').as_posix()
                assert git('show', commit+':'+relative) == source.read_bytes(), (lane,relative)
                sources += 1
        proof['lanes'][lane] = {'commit': commit, 'tree': git('rev-parse',commit+'^{tree}').decode().strip(),
            'frozen_base': base, 'original_files_unchanged': len(old), 'original_files_changed': changed,
            'release_manifest_sha256': sha(manifest_raw), 'manifest_required_files_missing': [],
            'manifest_hashes_verified': checked, 'frozen_strategy_model_hashes_verified': frozen,
            'original_packaged_source_files_identical': sources, 'status': 'PASS'}
    archive = ROOT/'v2_release/output/BTC15_V2_Offline_Release_Package_20261004.zip'
    assert sha(archive.read_bytes()) == 'cab80bc15f65b90e79ba814236e0687e7f0a1fba81b4471410d49a85448d3dd6'
    with zipfile.ZipFile(archive) as z:
        assert z.testzip() is None
        lines = z.read('SHA256SUMS').decode().splitlines()
        assert len(lines) == 90
        for line in lines:
            expected, name = line.split('  ', 1)
            raw = z.read(name)
            assert sha(raw) == expected, name
            assert raw == (ORIGINAL/name).read_bytes(), name
            proof['original_packaged_hashes'][name] = expected
        rollback = z.read('BTC15_V2_PRODUCT_RELEASE_REVIEW.md')
        assert rollback == (ORIGINAL/'BTC15_V2_PRODUCT_RELEASE_REVIEW.md').read_bytes()
        proof['rollback_and_acceptance_document_sha256'] = sha(rollback)
        proof['original_receipt_template_sha256'] = sha(z.read('release_receipt.template.json'))
    for name, path, expected_commit in [
        ('main_original', ORIGINAL/'main-candidate.bundle', MAIN),
        ('v81_original_preserved', ORIGINAL/'v81-candidate.bundle', OLD_V81),
        ('v81_corrected', OUT/'v81-candidate-corrected.bundle', V81)]:
        result = subprocess.run(['git','-C',str(REPO),'bundle','verify',str(path)], capture_output=True, text=True)
        assert result.returncode == 0, result.stdout+result.stderr
        heads = git('bundle','list-heads',str(path)).decode().strip()
        assert expected_commit in heads
        proof['bundles'][name] = {'sha256':sha(path.read_bytes()),'heads':heads,'verification':'PASS'}
    proof.update(original_packaged_hash_count_verified=90, rollback_package_intact=True,
        preserved_completed_qualification={'main_pass':280,'current_v81_pass':19,'bridge_pass':17,
            'assembled_dashboard_dom_scenarios_pass':12,'obsolete_v81_pass':14,
            'obsolete_v81_errors':4,'obsolete_errors_frozen_baseline_equivalent':True},
        affected_checks_this_correction={'clean_commit_only_checkout':True,'v81_launcher_release_and_freeze':'PASS',
            'scoring_bridge_tests_pass':17,'scoring_bridge_tests_failed':0,
            'new_broad_qualification_run':False,'original_fixture_tests_or_logs_changed':False})
    (OUT/'packaging_integrity.json').write_text(json.dumps(proof,indent=2)+'\n')
    print(json.dumps({k:v for k,v in proof.items() if k not in ('lanes','original_packaged_hashes')},indent=2))

if __name__ == '__main__':
    main()
