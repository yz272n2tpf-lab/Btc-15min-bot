"""Verify exact reviewed product bytes. Read-only, no network or runtime start."""
import argparse,hashlib,json
from pathlib import Path

def verify(root,lane):
    root=Path(root);m=json.loads((root/'BTC15_LADDER_COMPLETION_FREEZE_20261003.json').read_text())
    assert m['candidate']=='BTC15_LADDER_COMPLETION_20261003_V2'
    assert m['signal_only'] is True and m['orders'] is False
    for name,expected in m['files_sha256' if lane=='main' else 'v81_files_sha256'].items():
        actual=hashlib.sha256((root/name).read_bytes()).hexdigest()
        if actual!=expected:raise ValueError('FROZEN_FILE_MISMATCH:'+name)
    print('FROZEN V2 IDENTITY PASS | '+lane+' | SIGNAL ONLY | NO ORDERS')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--lane',choices=['main','v81'],default='main');p.add_argument('--root',type=Path,default=Path(__file__).parent)
    a=p.parse_args();verify(a.root,a.lane)
