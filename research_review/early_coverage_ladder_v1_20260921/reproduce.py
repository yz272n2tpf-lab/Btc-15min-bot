#!/usr/bin/env python3
"""One-command, offline reproduction using immutable source data and saved settlements."""
import hashlib,json,subprocess,sys,zipfile
from pathlib import Path
HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]

def main():
    expected=json.loads((HERE/'reproduction_hashes.json').read_text())
    archive=HERE/'evidence.zip'
    assert hashlib.sha256(archive.read_bytes()).hexdigest()==expected['evidence.zip']
    with zipfile.ZipFile(archive) as z:
        for info in z.infolist():
            target=(HERE/info.filename).resolve()
            if not target.is_relative_to(HERE):raise ValueError('Unsafe archive path')
        z.extractall(HERE)
    for script in ['prepare.py','score.py']:
        subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,check=True)
    subprocess.run([sys.executable,'-m','unittest','discover','-s',str(HERE),'-p','test_study.py','-v'],cwd=ROOT,check=True)
    for script in ['audit.py','report.py']:
        subprocess.run([sys.executable,str(HERE/script)],cwd=ROOT,check=True)
    for name,digest in expected.items():
        actual=hashlib.sha256((HERE/name).read_bytes()).hexdigest()
        if actual!=digest:raise AssertionError('Reproduction hash mismatch: '+name)
    print('OFFLINE REPRODUCTION PASS — all frozen output hashes match. SIGNAL ONLY / NO ORDERS.')

if __name__=='__main__':main()
