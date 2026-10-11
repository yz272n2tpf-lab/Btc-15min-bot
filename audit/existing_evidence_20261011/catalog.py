"""Read-only catalog of existing repository/Library evidence; never opens live DBs.

Content hashes identify duplicate files; record/contract deduplication is a
separate analysis step. Archives are read in memory, never blindly extracted.
"""
from __future__ import annotations
import argparse, csv, gzip, hashlib, io, json, re, subprocess, tarfile, zipfile
from collections import Counter
from datetime import datetime
from pathlib import Path

DATA_SUFFIXES = ('.csv', '.jsonl', '.ndjson', '.gz', '.sqlite', '.sqlite3', '.db')

def digest(b): return hashlib.sha256(b).hexdigest()

def csv_summary(raw):
    reader = csv.DictReader(io.StringIO(raw.decode('utf-8-sig', errors='replace')))
    cols = reader.fieldnames or []
    ids = set(); dates = {}; missing = Counter(); seen = set(); n = malformed = 0
    idcols = [c for c in cols if c.lower() in ('ticker','contract','contract_id','contract_ticker','market_ticker')]
    timecols = [c for c in cols if any(w in c.lower() for w in ('timestamp','_utc','_time','_at'))]
    for row in reader:
        n += 1
        if None in row: malformed += 1
        seen.add(digest(json.dumps(row, sort_keys=True, default=str).encode()) if None not in row else str(row))
        for c in cols:
            if row.get(c) in ('',None,'nan','NaN','None','null'): missing[c] += 1
        for c in idcols:
            if row.get(c): ids.add(row[c])
        for c in timecols:
            v = row.get(c) or ''
            if re.match(r'20\d\d-\d\d-\d\d',v):
                a = dates.setdefault(c,[v,v]);a[0]=min(a[0],v);a[1]=max(a[1],v)
    return dict(rows=n,exact_unique_rows=len(seen),duplicate_rows=n-len(seen),malformed_rows=malformed,
                columns=cols,contract_columns=idcols,contracts=len(ids),contract_ids=sorted(ids),
                time_ranges=dates,missing_by_column=dict(missing))

def run(repo, library, recovered_git, out, cache):
    cache.mkdir(parents=True,exist_ok=True)
    records={}; archives=[]; errors=[]
    def record(raw, source, name):
        sha=digest(raw)
        if sha in records:
            records[sha]['sources'].append(source);return
        obj=dict(sha256=sha,bytes=len(raw),name=name,sources=[source])
        if name.lower().endswith('.csv'):
            try:obj.update(csv_summary(raw))
            except Exception as e:obj['parse_error']=str(e)
        records[sha]=obj
        if name.lower().endswith(DATA_SUFFIXES):
            dest=cache/sha
            if not dest.exists():dest.write_bytes(raw)
    def visit(raw, source, name, depth=0):
        low=name.lower()
        if low.endswith('.zip'):
            sha=digest(raw);archives.append(dict(source=source,sha256=sha,bytes=len(raw)))
            try:
                with zipfile.ZipFile(io.BytesIO(raw)) as z:
                    for x in z.infolist():
                        if x.is_dir():continue
                        child=source+'!'+x.filename
                        if x.filename.lower().endswith(('.zip','.tar.gz','.tgz')) and depth<4:
                            visit(z.read(x),child,x.filename,depth+1)
                        elif x.filename.lower().endswith(DATA_SUFFIXES+('.json','.txt','.md')):
                            record(z.read(x),child,x.filename)
            except Exception as e:errors.append(dict(source=source,error=str(e)))
        elif low.endswith(('.tar.gz','.tgz')):
            sha=digest(raw);archives.append(dict(source=source,sha256=sha,bytes=len(raw)))
            try:
                with tarfile.open(fileobj=io.BytesIO(raw),mode='r:gz') as t:
                    for x in t:
                        if x.isfile() and x.name.lower().endswith(DATA_SUFFIXES+('.json','.txt','.md')):
                            record(t.extractfile(x).read(),source+'!'+x.name,x.name)
            except Exception as e:errors.append(dict(source=source,error=str(e)))
        else:record(raw,source,name)
    # Current tracked root/subdirectory evidence, including archives.
    for p in sorted(repo.rglob('*')):
        if not p.is_file() or '.git' in p.parts or out in p.parents:continue
        if p.name.lower().endswith(DATA_SUFFIXES+('.zip',)):
            visit(p.read_bytes(),'repo:'+str(p.relative_to(repo)),p.name)
    for base,label in [(library,'library'),(recovered_git,'git_recovered')]:
        for p in sorted(base.rglob('*')):
            if p.is_file() and p.name.lower().endswith(DATA_SUFFIXES+('.zip','.json')):
                visit(p.read_bytes(),label+':'+str(p.relative_to(base)),p.name)
    result=dict(files=list(records.values()),archives=archives,errors=errors,
                note='Content-identical files collapsed. Different schemas/derived rows are NOT independent observations.')
    (out/'corpus_inventory.json').write_text(json.dumps(result,indent=2))
    summary=dict(unique_contents=len(records),csv_contents=sum('rows' in r for r in records.values()),
                 csv_rows=sum(r.get('rows',0) for r in records.values()),archives=len(archives),
                 unique_archives=len({r['sha256'] for r in archives}),errors=errors)
    print(json.dumps(summary))

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--workspace',type=Path,required=True)
    a=p.parse_args();w=a.workspace
    run(w/'repo',w/'recovered-library',w/'recovered-git',w/'repo/audit/existing_evidence_20261011',w/'evidence-corpus')
