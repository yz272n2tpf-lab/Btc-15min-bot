"""Read-back integrity only. Does not run qualification or mutate production."""
from pathlib import Path
import datetime, hashlib, io, json, subprocess, zipfile

ROOT=Path('/workspace/scratch/7500f1a32278')
REPO=ROOT/'v2_correction'
OUT=ROOT/'v2_packaging_closure'
IDENTITY=json.loads((OUT/'publication_identity.json').read_text())
COMMIT=IDENTITY['artifact_commit']
PREFIX='release_review/v2-product-r1-packaging-20261004/'

def git(*args):
    return subprocess.check_output(['git','-C',str(REPO),*args])

def sha(raw): return hashlib.sha256(raw).hexdigest()

def canonical(value):
    if isinstance(value,dict): return {k:canonical(v) for k,v in value.items()}
    if isinstance(value,list): return sorted((canonical(v) for v in value),key=lambda v:json.dumps(v,sort_keys=True))
    return value

assert git('rev-parse','origin/'+IDENTITY['review_branch']).decode().strip()==COMMIT
assert git('rev-parse',COMMIT+'^{tree}').decode().strip()==IDENTITY['artifact_tree']
assert not git('diff','--name-only','613161e7d69f4f4662db307b867031de335c24bf',COMMIT,'--','release_review/v2-product-r1-20261004')
remote={}
inventory=json.loads((OUT/'upload_inventory.json').read_text())
for n,item in enumerate(inventory,1):
    raw=git('show',COMMIT+':'+item['path'])
    assert sha(raw)==item['sha256'],item['path']
    assert git('rev-parse',COMMIT+':'+item['path']).decode().strip()==item['blob_sha']
    remote[item['path']]=raw
    if n%5==0: print('Remote file hashes verified:',n,flush=True)
archive=remote[PREFIX+'BTC15_V2_Corrected_Release_Package_20261004.zip']
with zipfile.ZipFile(io.BytesIO(archive)) as z:
    assert z.testzip() is None
    sums=z.read('SHA256SUMS').decode().splitlines()
    assert len(sums)==19
    for line in sums:
        expected,name=line.split('  ',1)
        assert sha(z.read(name))==expected,name
        assert z.read(name)==remote[PREFIX+name],name
    original=z.read('original/BTC15_V2_Offline_Release_Package_20261004.zip')
    assert sha(original)=='cab80bc15f65b90e79ba814236e0687e7f0a1fba81b4471410d49a85448d3dd6'
    with zipfile.ZipFile(io.BytesIO(original)) as old:
        assert old.testzip() is None
        old_sums=old.read('SHA256SUMS').decode().splitlines();assert len(old_sums)==90
        for line in old_sums:
            expected,name=line.split('  ',1)
            assert sha(old.read(name))==expected,name
        rollback=old.read('BTC15_V2_PRODUCT_RELEASE_REVIEW.md')
        assert rollback==z.read('BTC15_V2_PRODUCT_RELEASE_REVIEW.original.md')
        assert sha(rollback)=='00018d05f6ae3c92ac6a546f1422dd0bfa598b436ce53504b0ca7c1ebb2b5fb0'
    for bundle,commit,tree in [('main-candidate.bundle','020f8a38d07e0a11e983a1e3bee3b06a4898c2f3','5ffab0fa22364129502d2c9bb817cc2eba862a1c'),('v81-candidate-corrected.bundle','985260e4166559701fc96b5582ca2211619d53ee','172b9eaa9686b165ec3cd396ba9398b715d31028')]:
        path=OUT/('remote-'+bundle);path.write_bytes(z.read(bundle))
        subprocess.run(['git','-C',str(REPO),'bundle','verify',str(path)],check=True,capture_output=True)
        heads=git('bundle','list-heads',str(path)).decode();assert commit in heads
        assert git('rev-parse',commit+'^{tree}').decode().strip()==tree

railway={}
for lane in ('main','v81','environment'):
    before=json.loads((OUT/f'railway_before_{lane}.json').read_text())
    after=json.loads((OUT/f'railway_after_{lane}.json').read_text())
    railway[lane]=canonical(before)==canonical(after)
    assert railway[lane],lane+' changed'
    if lane!='environment':
        previous=json.loads(git('show','613161e7d69f4f4662db307b867031de335c24bf:release_review/v2-product-r1-20261004/railway_after_'+lane+'.json'))
        assert canonical(previous)==canonical(after),lane+' changed since previous review'
environment=json.loads((OUT/'railway_after_environment.json').read_text())
assert environment['staged'] is None
for service in environment['services']:
    branch=(service.get('source') or {}).get('branch') or ''
    assert not branch.startswith('candidate/') and branch!=IDENTITY['review_branch']

refs={line.split()[1]:line.split()[0] for line in git('ls-remote','--heads','origin','candidate/*','ops/v2-product-review-20261004','release/ladder-completion-20261003','release/v81-ladder-completion-20261003').decode().splitlines()}
assert refs['refs/heads/'+IDENTITY['review_branch']]==COMMIT
assert refs['refs/heads/release/ladder-completion-20261003']=='de4f3e20b8657eb8cfee91bd4e525c103b5bf513'
assert refs['refs/heads/release/v81-ladder-completion-20261003']=='60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1'
assert 'refs/heads/candidate/v2-product-20261004' not in refs
assert 'refs/heads/candidate/v81-product-20261004' not in refs
report={'schema':'BTC15_PACKAGING_CORRECTION_GITHUB_READBACK_R1',
    'verified_at_utc':datetime.datetime.now(datetime.timezone.utc).isoformat(),**IDENTITY,
    'remote_artifact_files_verified':len(inventory),'corrected_package_sha256':sha(archive),
    'corrected_package_hashes_verified':19,'original_nested_package_hashes_verified':90,
    'original_review_folder_unchanged':True,'both_active_bundles_verified':True,
    'rollback_package_intact':True,'packaging_blocker_closed':True,
    'candidate_refs_published':False,'remote_refs':refs,
    'remaining_publication_blocker':'Existing authenticated exact-object Git push required. GitHub connector cannot import original local commit metadata; browser signed out. No credential creation attempted.',
    'railway_configs_deployments_unchanged':railway,'railway_main_v81_unchanged_since_previous_review':True,
    'railway_service_count':len(environment['services']),'railway_staged_changes':None,
    'corrected_v81_commit':'985260e4166559701fc96b5582ca2211619d53ee',
    'main_commit_unchanged':'020f8a38d07e0a11e983a1e3bee3b06a4898c2f3',
    'full_qualification_repeated':False,'affected_bridge_tests_pass':17,'affected_tests_failed':0,
    'obsolete_v81_fixture_errors':{'count':4,'unchanged':True,'frozen_baseline_equivalent':True},
    'production_deployed':False,'orders':False,'status':'PACKAGING_CLOSED_EXACT_REF_PUBLICATION_BLOCKED'}
(OUT/'post_publication_verification.json').write_text(json.dumps(report,indent=2)+'\n')
print(json.dumps(report,indent=2))
