"""Bounded, SELECT-only incident extraction. Does not import production code.

Run only against an EXISTING consistent OFFLINE journal/WAL snapshot.
The interval and contract allowlist are fixed; stdout is the only application
output. SQLite can update shared-memory locking metadata even with mode=ro:
this utility is NOT authorization to open a production volume under a strict
no-volume-modification boundary. It was tested only against temporary databases.
Do not use immutable=1 to ignore a WAL: it could omit committed rows.
"""
import argparse
import hashlib
import json
from pathlib import Path
import sqlite3
import zlib

START=1791728880.0  # 2026-10-11T14:28:00Z
END=1791729180.0    # 2026-10-11T14:33:00Z, exclusive
CONTRACTS=('KXBTC15M-26OCT111030-30','KXBTC15M-26OCT111045-45')
MAX_ROWS=1200
MAX_BODY=262144


def extract(path, lane):
    path=Path(path).resolve(strict=True)
    if not path.is_file() or lane not in ('main','v81'):
        raise ValueError('EXISTING_MAIN_OR_V81_JOURNAL_REQUIRED')
    with sqlite3.connect(path.as_uri()+'?mode=ro',uri=True,timeout=.2) as db:
        db.execute('PRAGMA query_only=ON')
        db.execute('BEGIN')
        actual=db.execute("SELECT v FROM meta WHERE k='lane'").fetchone()
        if not actual or actual[0]!=lane:
            raise ValueError('JOURNAL_LANE_MISMATCH')
        rows=db.execute('SELECT seq,at,contract,kind,sha256,body FROM events '
            'WHERE at>=? AND at<? AND (contract IN (?,?) OR contract IS NULL) '
            'ORDER BY seq LIMIT ?', (START,END,*CONTRACTS,MAX_ROWS+1)).fetchall()
        if len(rows)>MAX_ROWS:
            raise ValueError('BOUNDED_EXTRACTION_LIMIT_EXCEEDED')
        records=[]
        for seq,at,contract,kind,sha,body in rows:
            dec=zlib.decompressobj();raw=dec.decompress(body,MAX_BODY+1)
            if len(raw)>MAX_BODY or not dec.eof or dec.unused_data or hashlib.sha256(raw).hexdigest()!=sha:
                raise ValueError('JOURNAL_BODY_INTEGRITY_FAILURE:'+str(seq))
            records.append(dict(seq=seq,at=at,contract=contract,kind=kind,sha256=sha,record=json.loads(raw)))
        db.rollback()
    return dict(schema='BTC15_BOUNDED_READONLY_INCIDENT_V1',lane=lane,journal=str(path),
        start_utc='2026-10-11T14:28:00Z',end_utc_exclusive='2026-10-11T14:33:00Z',
        contracts=list(CONTRACTS),row_count=len(records),rows=records,
        provenance='Existing SQLite events; each uncompressed body SHA256 verified. Does not independently certify source quotes.',
        production_mutation=False,signal_only=True,orders=False)


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--journal',type=Path,required=True)
    p.add_argument('--lane',choices=('main','v81'),required=True)
    a=p.parse_args();print(json.dumps(extract(a.journal,a.lane),separators=(',',':')))
