"""Import verified bundles and publish only the two authorized candidate refs.

Run in an existing authenticated checkout of yz272n2tpf-lab/Btc-15min-bot.
Default mode verifies package bytes only. --push is required for Git writes.
No credential creation, configuration changes, workflow dispatch or deployment.
"""
from pathlib import Path
import argparse
import hashlib
import os
import subprocess

PACKAGE = Path(__file__).resolve().parent
REPOSITORY = 'yz272n2tpf-lab/Btc-15min-bot'
LANES = [
    ('main-candidate.bundle', '3e71a3e9b99bcda2187bcd2eeb702b08d2615c2191e13b6e8fbd815c153097c9',
     '020f8a38d07e0a11e983a1e3bee3b06a4898c2f3', 'candidate/v2-product-20261004'),
    ('v81-candidate-corrected.bundle', 'a19550c78677e6f2b5cb275dd5330aedfa047fc7808789220cac5b6aa36f3b9a',
     '985260e4166559701fc96b5582ca2211619d53ee', 'candidate/v81-product-20261004')]
PRODUCTION = {
    'refs/heads/release/ladder-completion-20261003': 'de4f3e20b8657eb8cfee91bd4e525c103b5bf513',
    'refs/heads/release/v81-ladder-completion-20261003': '60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1'}

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--repo', type=Path)
    parser.add_argument('--push', action='store_true')
    args = parser.parse_args()
    for filename, expected, _, _ in LANES:
        assert hashlib.sha256((PACKAGE/filename).read_bytes()).hexdigest() == expected, filename
    print('Both exact bundle hashes PASS')
    if not args.push:
        print('Verification only. No refs imported or pushed. Use --repo EXISTING_CHECKOUT --push after authentication is available.')
        return
    if not args.repo:
        parser.error('--repo is required with --push')
    env = {**os.environ, 'GIT_TERMINAL_PROMPT': '0'}
    def git(*parts):
        return subprocess.check_output(['git','-C',str(args.repo),*parts],env=env,text=True).strip()
    origin = git('remote','get-url','origin')
    allowed = {'https://github.com/'+REPOSITORY, 'https://github.com/'+REPOSITORY+'.git',
               'git@github.com:'+REPOSITORY+'.git', 'ssh://git@github.com/'+REPOSITORY+'.git'}
    assert origin in allowed, 'Origin must be the existing authorized repository without embedded credentials'
    refs = list(PRODUCTION) + ['refs/heads/'+lane[3] for lane in LANES]
    def remote_refs():
        return {line.split()[1]: line.split()[0] for line in git('ls-remote','--heads','origin',*refs).splitlines()}
    before = remote_refs()
    for name, expected in PRODUCTION.items():
        assert before.get(name) == expected, 'Frozen production ref changed: '+name
    for filename, _, commit, branch in LANES:
        ref = 'refs/heads/'+branch
        permitted = {None, commit}
        if branch == 'candidate/v81-product-20261004':
            permitted.add('07406e46945cc0bfebbb25299c5da53e87ac6a2a')
        assert before.get(ref) in permitted, 'Unexpected candidate ref; review before writing: '+ref
        bundle = str(PACKAGE/filename)
        git('bundle','verify',bundle)
        git('fetch',bundle,'HEAD')
        assert git('rev-parse','FETCH_HEAD') == commit
    print(git('push','--atomic','origin',*[commit+':refs/heads/'+branch for _,_,commit,branch in LANES]))
    after = remote_refs()
    for _,_,commit,branch in LANES:
        assert after.get('refs/heads/'+branch) == commit, branch
        print(branch+' '+commit)
    for name, expected in PRODUCTION.items():
        assert after.get(name) == expected
    print('Exact candidate refs published; frozen production Git refs unchanged. No Railway action performed.')

if __name__ == '__main__':
    main()
