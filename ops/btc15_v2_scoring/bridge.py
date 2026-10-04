"""Offline compatibility bridge; no strategy evaluation, networking or order code.

snapshot: reads the existing mounted SQLite journal using mode=ro + backup().
score: accepts detached snapshots only; preserves raw V2 rows and calls the
unchanged established scorer classifiers. Never manufactures native V1 rows.
"""
import argparse
from collections import Counter
from contextlib import closing
from datetime import datetime, timezone
import hashlib
import importlib.util
import json
import math
import os
from pathlib import Path
import sqlite3
import time
from urllib.parse import quote
from zoneinfo import ZoneInfo
import zlib
import sys
from ops.btc15_v2_scoring import product_cohort
from ops.btc15_v2_scoring.completeness_diagnostics import diagnose

CANDIDATE = 'BTC15_LADDER_COMPLETION_20261003_V2'
JOURNAL = 'BTC15_LADDER_JOURNAL_V1'
SNAPSHOT = 'BTC15_V2_SQLITE_SNAPSHOT_V1'
REPORT = 'BTC15_V2_SCORING_CHECKPOINT_V1'
PROJECT = 'baea4e22-d004-4434-b2c5-81a7fbc05086'
ENVIRONMENT = '61775c5d-c583-4dfc-af41-f25578856fd9'
VOLUMES = {'main':'6ced6b1a-3755-4518-a240-c895e936d443',
           'v81':'d5eeafca-e0fc-42f0-b7d1-4705907720c6'}
IDENTITIES = {
    'main': dict(build='de4f3e20b8657eb8cfee91bd4e525c103b5bf513',
                 service='ab28dca6-7bea-4956-bdb9-dbb7b4c74635',
                 deployment='ce0ac4dd-a3c4-49bb-8ca7-d1b7ed5be2fa', interval=15),
    'v81': dict(build='60e6ebdd03e81a4c84385e1b5122302f3cf0b9f1',
                service='6025e83e-a41c-4e0a-8c16-f71120bd501b',
                deployment='2051e772-bd39-4dea-a77d-52fea0a07c02', interval=6),
}
# First possible complete window AFTER both applied deployments; not cohort start.
FIRST_POSSIBLE_OPEN = 1791087300
ACTIVE_RELEASE = None
SCORER_SHA256 = '9812c23a6200bf31c2c5eb4e8f317fe32cfcafefeaa37d2a9b9a041967447d1a'


def require(ok, reason):
    if not ok:
        raise ValueError(reason)


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode()


def sha(value):
    return hashlib.sha256(value).hexdigest()


def file_sha(path):
    digest=hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda:stream.read(1024*1024),b''):digest.update(block)
    return digest.hexdigest()


def utc(at):
    return datetime.fromtimestamp(at, timezone.utc).isoformat()


def epoch(value):
    return datetime.fromisoformat(value.replace('Z', '+00:00')).timestamp()


def number(value):
    return type(value) in (int, float) and math.isfinite(value)


def ticker(opened):
    d = datetime.fromtimestamp(opened+900, timezone.utc).astimezone(ZoneInfo('America/New_York'))
    return 'KXBTC15M-' + d.strftime('%y%b%d%H%M-%M').upper()


def readonly(path):
    db = sqlite3.connect(Path(path).resolve().as_uri()+'?mode=ro', uri=True, timeout=.2)
    db.row_factory = sqlite3.Row
    db.execute('PRAGMA query_only=ON')  # connection-only; not a journal mutation
    return db


def metadata(db):
    meta = dict(db.execute('SELECT k,v FROM meta'))
    lo, hi, count = db.execute('SELECT min(seq),max(seq),count(*) FROM events').fetchone()
    return dict(meta=meta, minimum_sequence=lo, maximum_sequence=hi, event_count=count)


def write_json(path, value):
    with Path(path).open('x') as out:
        out.write(json.dumps(value, indent=2, allow_nan=False)+'\n')


def snapshot(source, destination, lane, identity, evidence_class='PRODUCTION'):
    """No source writes/checkpoint/migration/immutable flag. Destination is new.

    The CLI supplies only the fixed mounted source and independently checked
    runtime identity. Test callers must label generated databases FIXTURE.
    """
    source, destination = Path(source).resolve(), Path(destination).resolve()
    receipt_path = Path(str(destination)+'.receipt.json')
    require(source.is_file(), 'SOURCE_MISSING')
    require(not destination.is_relative_to(source.parent), 'DESTINATION_INSIDE_SOURCE_DIRECTORY')
    require(not destination.exists() and not receipt_path.exists(), 'DESTINATION_EXISTS')
    started = time.time()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with destination.open('xb'):
        pass
    try:
        with closing(readonly(source)) as db, closing(sqlite3.connect(destination)) as out:
            # SQLite backup has a consistent read view and handles committed WAL.
            def progress(status, remaining, total):
                require(time.time()-started < 30, 'SNAPSHOT_DEADLINE_EXCEEDED')
            db.backup(out, pages=128, progress=progress, sleep=.02)
        with closing(readonly(destination)) as db:
            require(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLITE_INTEGRITY')
            m = metadata(db)
        require(m['meta'].get('schema') == JOURNAL and m['meta'].get('lane') == lane, 'SNAPSHOT_SCHEMA_LANE')
        result = dict(schema=SNAPSHOT, candidate=CANDIDATE, evidence_class=evidence_class,
                      lane=lane, identity=identity, source=str(source),
                      source_open_mode='ro', method='sqlite3.Connection.backup',
                      started_at=started, finished_at=time.time(),
                      snapshot_sha256=file_sha(destination),
                      journal_id=m['meta']['journal_id'],
                      minimum_sequence=m['minimum_sequence'], maximum_sequence=m['maximum_sequence'],
                      event_count=m['event_count'], integrity_check='ok')
        write_json(receipt_path, result)
        return result
    except Exception:
        # Delete only this newly created detached destination; never the source.
        destination.unlink(missing_ok=True)
        raise


def production_snapshot(lane, destination):
    require(not Path(destination).resolve().is_relative_to(Path('/data')), 'DESTINATION_MUST_BE_OFF_VOLUME')
    ids = IDENTITIES[lane]
    expected = {'RAILWAY_PROJECT_ID': PROJECT, 'RAILWAY_ENVIRONMENT_ID': ENVIRONMENT,
                'RAILWAY_SERVICE_ID': ids['service'], 'RAILWAY_DEPLOYMENT_ID': ids['deployment'],
                'RAILWAY_GIT_COMMIT_SHA': ids['build'], 'RAILWAY_VOLUME_MOUNT_PATH': '/data'}
    for key, value in expected.items():
        require(os.environ.get(key) == value, 'RUNTIME_IDENTITY:'+key)
    require(os.environ.get('RAILWAY_VOLUME_ID') == VOLUMES[lane], 'VOLUME_ID_MISMATCH')
    identity = dict(ids, project=PROJECT, environment=ENVIRONMENT,
                    volume=os.environ['RAILWAY_VOLUME_ID'], basis='RUNTIME_ENVIRONMENT_ALLOWLIST')
    return snapshot(product_cohort.source(sys.modules[__name__],lane), destination, lane, identity)


def load_scorer(path=None):
    path = Path(path) if path else Path(__file__).resolve().parents[2]/'btc15_cohort_evidence_v1.py'
    require(sha(path.read_bytes()) == SCORER_SHA256, 'ESTABLISHED_SCORER_CHANGED')
    spec = importlib.util.spec_from_file_location('established_btc15_scorer', path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_snapshot(path, lane, allow_fixture=False):
    path = Path(path)
    require(not path.resolve().is_relative_to(Path('/data')), 'SCORER_REQUIRES_DETACHED_SNAPSHOT')
    receipt = json.loads(Path(str(path)+'.receipt.json').read_text())
    require(receipt['schema'] == SNAPSHOT and receipt['candidate'] == CANDIDATE and receipt['lane'] == lane, 'RECEIPT_IDENTITY')
    fixture = receipt['evidence_class'] == 'FIXTURE'
    require(receipt['evidence_class'] == 'PRODUCTION' or (fixture and allow_fixture), 'FIXTURE_NOT_PRODUCTION')
    if not fixture:
        ids = receipt['identity']
        require(all(ids.get(k) == v for k,v in IDENTITIES[lane].items()), 'WRONG_PRODUCTION_IDENTITY')
        require(ids.get('project') == PROJECT and ids.get('environment') == ENVIRONMENT, 'WRONG_ENVIRONMENT')
        require(ids.get('volume') == VOLUMES[lane], 'WRONG_VOLUME')
        require(receipt['source'] == product_cohort.source(sys.modules[__name__],lane), 'WRONG_SOURCE')
    require(receipt['source_open_mode'] == 'ro' and receipt['method'] == 'sqlite3.Connection.backup', 'NOT_CONSISTENT_BACKUP')
    require(receipt['snapshot_sha256'] == file_sha(path), 'SNAPSHOT_HASH_MISMATCH')
    for suffix in ('-wal','-journal'):
        sidecar=Path(str(path)+suffix)
        require(not sidecar.exists() or sidecar.stat().st_size==0,'SNAPSHOT_HAS_UNMERGED_JOURNAL')
    records = []
    with closing(readonly(path)) as db:
        require(db.execute('PRAGMA integrity_check').fetchone()[0] == 'ok', 'SQLITE_INTEGRITY')
        m = metadata(db)
        product_cohort.validate_meta(sys.modules[__name__],m,lane)
        require(m['meta']['schema'] == JOURNAL and m['meta']['lane'] == lane, 'JOURNAL_SCHEMA_LANE')
        require(m['meta']['journal_id'] == receipt['journal_id'], 'JOURNAL_ID_CHANGED')
        for k in ('minimum_sequence', 'maximum_sequence', 'event_count'):
            require(m[k] == receipt[k], 'SNAPSHOT_CENSUS:'+k)
        require(m['event_count'] and m['maximum_sequence']-m['minimum_sequence']+1 == m['event_count'], 'SEQUENCE_GAP')
        require(int(m['meta']['sequence']) == m['maximum_sequence'], 'SEQUENCE_META_MISMATCH')
        for row in db.execute('SELECT * FROM events ORDER BY seq'):
            unpacker=zlib.decompressobj()
            raw=unpacker.decompress(row['body'],65537)
            require(len(raw)<=65536 and unpacker.eof and not unpacker.unused_data, 'INVALID_PACKED_RECORD')
            require(sha(raw) == row['sha256'], 'EVENT_HASH_MISMATCH')
            r=json.loads(raw, parse_constant=lambda s: (_ for _ in ()).throw(ValueError('NONFINITE_JSON')))
            product_cohort.validate_record(sys.modules[__name__],r,lane)
            require(r.get('schema') == JOURNAL and r.get('candidate') == CANDIDATE, 'OLD_OR_FOREIGN_COHORT')
            require(r.get('signal_only') is True and r.get('orders') is False, 'SIGNAL_ONLY_INVARIANT')
            require(r.get('published_ts') == row['at'] and r.get('contract') == row['contract'] and r.get('kind') == row['kind'], 'EVENT_COLUMNS_CONFLICT')
            require(number(row['at']), 'INVALID_TIMESTAMP')
            require(row['at'] <= receipt['finished_at'], 'EVENT_AFTER_SNAPSHOT')
            if lane == 'main':
                require(r.get('build') == IDENTITIES[lane]['build'], 'OLD_PRODUCTION_BUILD')
            elif r.get('build') is not None:
                require(r['build'] == IDENTITIES[lane]['build'], 'OLD_PRODUCTION_BUILD')
            # V8.1 omits build in the frozen journal writer: never synthesize it.
            ref=dict(lane=lane, journal_id=receipt['journal_id'], sequence=row['seq'],
                     record_sha256=row['sha256'], snapshot_sha256=receipt['snapshot_sha256'])
            records.append(dict(schema='BTC15_V2_SCORING_ADAPTER_V1', ref=ref, raw=r))
        contracts=[dict(r) for r in db.execute('SELECT * FROM contracts ORDER BY opened')]
        if ACTIVE_RELEASE is not None:
            starts=json.loads(m['meta'].get('startup_slots','[]'))
            require(all(c['missing'] for c in contracts if c['opened'] in starts),'STARTUP_COHORT_NOT_EXCLUDED')
    require(receipt['snapshot_sha256'] == file_sha(path), 'SNAPSHOT_CHANGED_DURING_READ')
    by_open={};settlements={};rollovers={}
    for e in records:
        r=e['raw']
        if r['kind']=='SETTLEMENT':settlements.setdefault(r['contract'],[]).append(e)
        elif r['kind']!='BRTI_CLOSEOUT':by_open.setdefault(int(r['published_ts']//900)*900,[]).append(e)
        terminal=r.get('terminal')
        if terminal and terminal['origin']['contract']!=r.get('contract'):
            rollovers.setdefault(terminal['origin']['contract'],[]).append(e)
    return dict(receipt=receipt, records=records, contracts=contracts, fixture=fixture,
                by_open=by_open,settlements=settlements,rollovers=rollovers)


def event_identity(r, lane):
    p = r.get('evidence', {}) if lane == 'main' else r.get('provenance', {})
    return (p.get('contract') if lane == 'main' else p.get('ticker'),
            p.get('official_open') if lane == 'main' else p.get('open_ts'),
            p.get('official_close') if lane == 'main' else p.get('close_ts'), p.get('target'))


def authoritative(records, contract, opened, target):
    good=[]
    for e in records:
        r=e['raw'];s=r.get('settlement', {})
        if r['kind'] != 'SETTLEMENT' or r.get('contract') != contract:
            continue
        if (s.get('source') == 'OFFICIAL_KALSHI_GET_MARKET' and s.get('status') == 'AUTHORITATIVE'
            and s.get('market_status') == 'finalized' and s.get('result') in ('yes','no')
            and s.get('ticker') == contract and s.get('open_ts') == opened and s.get('close_ts') == opened+900
            and number(s.get('target')) and s['target'] == target
            and s.get('side') == ('UP' if s['result'] == 'yes' else 'DOWN')
            and s.get('endpoint') == 'https://external-api.kalshi.com/trade-api/v2/markets/'+quote(contract,safe='')
            and number(s.get('received_ts')) and opened+900 <= s['received_ts'] <= r['published_ts']):
            good.append(dict(receipt=s, ref=e['ref']))
    require(len({g['receipt']['side'] for g in good}) <= 1, 'CONFLICTING_OFFICIAL_SETTLEMENT')
    return good[-1] if good else None


def origin_check(o, r, lane, opened, target):
    at=epoch(o['signal_timestamp_utc']) if lane == 'main' else o['signal_ts']
    require(o['contract'] == r['contract'] == ticker(opened) and o['target'] == target, 'ORIGIN_CONTRACT_TARGET')
    require(opened <= at < opened+900 and at == r['published_ts'], 'ORIGIN_SIGNAL_TIME')
    require(o['side'] in ('UP','DOWN') and number(o['original_ask']) and 0 < o['original_ask'] <= 1, 'ORIGIN_PRICE_SIDE')
    p=o['entry_provenance']; side=o['side'].lower()
    if lane == 'main':
        require(o['official_open'] == opened and o['official_close'] == opened+900, 'ORIGIN_WINDOW')
        require(p[side+'_ask'] == o['original_ask'] and p['candidate'] == CANDIDATE, 'ORIGIN_ASK_PROVENANCE')
        key=[CANDIDATE, o['contract'], [o['native_epoch'],o['native_sequence']], o['side']]
    else:
        require(o['open_ts'] == opened and o['close_ts'] == opened+900 and p['ticker'] == o['contract'] and p['target'] == target, 'ORIGIN_WINDOW')
        q=p['quote']
        require(q[side+'_ask'] == o['original_ask'] and q['source_ts_ms']/1000 <= q['validated_at_ms']/1000 <= at, 'ORIGIN_ASK_PROVENANCE')
        key=[CANDIDATE,o['contract'],o['side'],at,q['epoch'],q['sequence']]
    require(o['origin_id'] == sha(canonical(key)), 'ORIGIN_ID_MISMATCH')
    require(o.get('manual_fill') is None, 'UNEXPECTED_FILL')
    return at


def scalp_paths(events, all_events, opened, target, failures):
    origins={}; result=[]
    for e in events:
        r=e['raw']
        if r.get('event') != 'SCALP_SIGNAL': continue
        o=r['origin'];at=origin_check(o,r,'v81',opened,target)
        require(o['origin_id'] not in origins, 'DUPLICATE_SCALP_ORIGIN')
        origins[o['origin_id']]=dict(origin=o, origin_ref=e['ref'], signal_ts=at,
            later_bids=[], terminal=None, telemetry=None, guidance=[], missing=False, errors=[])
    # Process rollover terminals by immutable origin identity, not parent row ticker.
    for e in all_events:
        r=e['raw']; oid=r.get('origin_id')
        if oid in origins:
            x=origins[oid]
            x['guidance'].append(dict(state=r.get('guidance'),at=r['published_ts'],ref=e['ref']))
            if r.get('path') is not None:
                x['telemetry']=r['path'];x['missing'] |= bool(r['path'].get('missing'))
        b=r.get('later_bid')
        if b and b.get('origin_id') in origins:
            x=origins[b['origin_id']];o=x['origin'];q=b['quote']
            prev=x['later_bids'][-1]['quote'] if x['later_bids'] else o['entry_provenance']['quote']
            valid=(r.get('contract') == o['contract'] and b.get('side') == o['side']
                and q.get('ticker') == o['contract'] and b['bid'] == q[o['side'].lower()+'_bid']
                and number(b['bid']) and 0 <= b['bid'] <= 1
                and all(number(q.get(k)) and 0<=q[k]<=1 for k in ('up_bid','up_ask','down_bid','down_ask'))
                and q['up_bid']<=q['up_ask'] and q['down_bid']<=q['down_ask']
                and x['signal_ts'] < q['source_ts_ms']/1000 <= q['validated_at_ms']/1000 <= r['published_ts'] < o['close_ts']
                and q['source_ts_ms'] > prev['source_ts_ms']
                and (q['epoch'] != prev['epoch'] or (q['sid'] == prev['sid'] and q['sequence'] > prev['sequence']))
                and x['terminal'] is None)
            if valid:
                x['later_bids'].append(dict(b,ref=e['ref']))
                x['missing'] |= q['epoch'] != prev['epoch']
            else:
                x['errors'].append('INVALID_LATER_BID');failures['INVALID_LATER_BID']+=1
        for terminal in (r.get('terminal'),r.get('predecessor_exit')):
            if not terminal or terminal['origin']['origin_id'] not in origins: continue
            x=origins[terminal['origin']['origin_id']]
            require(terminal['origin'] == x['origin'], 'TERMINAL_ORIGIN_MUTATION')
            if x['terminal']:
                require(x['terminal']['value'] == terminal, 'TERMINAL_MUTATION')
                continue
            if terminal['state'] == 'EXIT':
                require(bool(x['later_bids']), 'EXIT_WITHOUT_LATER_BID')
                last=x['later_bids'][-1]
                require(terminal['quote'] == last['quote'] and terminal['executable_exit_bid'] == last['bid']
                        and terminal['ts'] == last['ts'], 'EXIT_REPRICED_OR_UNLINKED')
            x['terminal']=dict(value=terminal,ref=e['ref'])
            x['missing'] |= not terminal.get('complete_path',False)
    for x in origins.values():
        deltas=[b['bid']-x['origin']['original_ask'] for b in x['later_bids']]
        x['observed_mfe_cents']=max(deltas)*100 if deltas else None
        x['observed_mae_cents']=min(deltas)*100 if deltas else None
        targets={str(t):None for t in (8,10,15,20,30)}; stop=None
        for b,gain in zip(x['later_bids'],deltas):
            if gain <= -.10+1e-12 and stop is None:
                stop=dict(ref=b['ref'],bid=b['bid'],ts=b['ts'],targets_first=[t for t,h in targets.items() if h])
            for t in targets:
                if gain+1e-12 >= int(t)/100 and targets[t] is None:
                    targets[t]=dict(ref=b['ref'],bid=b['bid'],ts=b['ts'],stop_first=stop is not None)
        x['observed_target_stop_telemetry']=dict(targets=targets,stop=stop,authority='OBSERVATIONAL_ONLY')
        tele=x['telemetry'] or {}
        if tele.get('samples') != len(deltas) or any(
            (tele.get(k) is None) != (value is None) or
            (value is not None and abs(tele[k]-value)>1e-8)
            for k,value in [('mfe',max(deltas) if deltas else None),('mae',min(deltas) if deltas else None)]):
            x['errors'].append('PATH_TELEMETRY_MISMATCH');failures['PATH_TELEMETRY_MISMATCH']+=1
        x['status']=('RESOLVED_OBSERVED_PATH' if x['terminal'] and x['terminal']['value']['state']=='EXIT'
                     and not x['missing'] and not x['errors'] else 'UNRESOLVED_OR_GAPPED')
        x['manual_fill']=None;x['realized_profit']=None
        result.append(x)
    return result


def lane_contract(data, lane, opened, scorer):
    contract=ticker(opened); interval=IDENTITIES[lane]['interval']; failures=Counter()
    events=data['by_open'].get(opened,[])
    coverage=next((c for c in data['contracts'] if c['opened']==opened), None)
    times=[e['raw']['published_ts'] for e in events]; missing=[]
    gaps=[dict(previous_publication=a,next_publication=c,seconds=c-a,allowed_interval=interval)
          for a,c in zip(times,times[1:]) if c-a<=0 or c-a>interval]
    if not coverage or coverage['missing']: missing.append('JOURNAL_MISSING_OR_PARTIAL')
    if not times or times[0]-opened > interval or opened+900-times[-1] > interval: missing.append('INCOMPLETE_WINDOW_EDGES')
    if any(b-a <= 0 or b-a > interval for a,b in zip(times,times[1:])): missing.append('OBSERVATION_GAP_OR_TIME_REVERSAL')
    unavailable=[e for e in events if 'unavailable_reason' in e['raw']]
    if unavailable: missing.append('UNAVAILABLE_INTERVALS')
    if not coverage or coverage['observations'] != len(events) or coverage['unavailable'] != len(unavailable): missing.append('COVERAGE_CENSUS_MISMATCH')
    if coverage and times and (coverage['ticker']!=contract or coverage['first_at']!=times[0] or coverage['last_at']!=times[-1]):
        missing.append('COVERAGE_IDENTITY_TIMES_MISMATCH')
    if coverage and (coverage['signals'] != sum(e['raw'].get('event') in ('BUY','SCALP_SIGNAL') for e in events)
                     or coverage['final_calls'] != sum((e['raw'].get('final') or {}).get('ready') is True for e in events)):
        missing.append('SIGNAL_CENSUS_MISMATCH')
    if opened < FIRST_POSSIBLE_OPEN: missing.append('DEPLOYMENT_STARTUP_WINDOW')
    targets=set(); valid=[]
    for e in events:
        r=e['raw']
        if 'unavailable_reason' in r:
            failures[r['unavailable_reason']]+=1
            # Independent FINAL can survive a separate EARLY-manager failure.
        if 'unavailable_reason' not in r or r.get('final'):
            c,o,cl,t=event_identity(r,lane)
            if c != contract or o != opened or cl != opened+900 or not number(t) or t<=0:
                failures['EVENT_CONTRACT_WINDOW_TARGET']+=1;missing.append('EVENT_CONTRACT_WINDOW_TARGET');continue
            targets.add(t);valid.append(e)
    require(len(targets)<=1, 'FIXED_TARGET_MUTATION')
    target=next(iter(targets),None)
    settlement=authoritative(data['settlements'].get(contract,[]),contract,opened,target) if target is not None else None
    early=[];final=[];helpers=[];seen_final={};seen_origins=set();pass_count=0
    for e in valid:
        r=e['raw']
        if lane=='main':
            if 'unavailable_reason' not in r:
                accepted=r.get('event')=='BUY'
                item=dict(contract=contract,provisional_candidate=accepted,ref=e['ref'])
                if accepted:
                    origin=r['origin'];at=origin_check(origin,r,lane,opened,target)
                    require(origin['origin_id'] not in seen_origins,'DUPLICATE_EARLY_ORIGIN');seen_origins.add(origin['origin_id'])
                    ask=origin['original_ask']
                    item.update(origin=origin,signal_ts=at,actual_ask=ask,seconds_remaining=opened+900-at,
                                ask_le50=ask<=.50,ideal_25_to35=.25<=ask<=.35,
                                correct=(origin['side']==settlement['receipt']['side']) if settlement else None)
                early.append(item)
                pass_count += r.get('guidance') == 'PASS'
            f=r.get('final')
            if f:
                key=f['publication_id'];require(f.get('side') in ('UP','DOWN'),'FINAL_SIDE')
                require(key == sha(canonical([CANDIDATE,'FINAL',[r['evidence']['native_epoch'],r['evidence']['native_sequence']]])), 'FINAL_PUBLICATION_ID')
                item=dict(contract=contract,publication_id=key,signal_ts=r['published_ts'],
                          final_status='FINAL CALL' if f['ready'] is True else 'PASS',
                          independent_final=f,ref=e['ref'],
                          correct=(f['side']==settlement['receipt']['side']) if settlement else None)
                if key in seen_final:
                    require(seen_final[key]['independent_final']==f,'FINAL_PUBLICATION_MUTATION')
                else:
                    seen_final[key]=item;final.append(item)
                if f.get('helper'):
                    require(f['helper']['origin_id']==r.get('origin_id')==f.get('early_origin_id'),'HELPER_ORIGIN_LINK')
                    if f['helper']['origin_id'] not in seen_origins:
                        missing.append('ORIGIN_NOT_IN_SNAPSHOT')
                    helpers.append(dict(helper=f['helper'],publication_id=key,ref=e['ref']))
        else:
            pass_count += 'unavailable_reason' not in r and r.get('guidance')=='PASS'
    if lane=='main':
        early_class=scorer.classify_early(early,contract);final_class=scorer.classify_final(final,contract)
        classified=dict(early=early_class,final=final_class,early_helper_events=helpers,
                        final_pass_publications=sum(r['final_status']=='PASS' for r in final))
    else:
        paths=scalp_paths(valid,events+data['rollovers'].get(contract,[]),opened,target,failures)
        classified=dict(scalp=scorer.classify_scalp([dict(contract=contract,**p) for p in paths],contract,coverage_proven=not missing))
        if any(p['status']!='RESOLVED_OBSERVED_PATH' for p in paths): missing.append('UNRESOLVED_SCALP_PATH')
    for key in ('INVALID_LATER_BID','PATH_TELEMETRY_MISMATCH'):
        if failures.get(key): missing.append(key)
    return dict(lane=lane,contract=contract,opened=opened,closed=opened+900,target=target,
                coverage=coverage,observation_count=len(events),pass_publications=pass_count,
                unavailable_publications=len(unavailable),missing=sorted(set(missing)),
                publication_gaps=gaps,
                unavailable_observations=[dict(at=e['raw']['published_ts'],reason=e['raw']['unavailable_reason'],ref=e['ref']) for e in unavailable],
                settlement=settlement,settled=settlement is not None,
                eligible=not missing,fully_scoreable=not missing and settlement is not None,
                failure_clusters=dict(failures),**classified)


def score(main_path, v81_path, output, scorer_path=None, allow_fixture=False):
    scorer=load_scorer(scorer_path)
    lanes={lane:load_snapshot(path,lane,allow_fixture) for lane,path in [('main',main_path),('v81',v81_path)]}
    require(lanes['main']['fixture']==lanes['v81']['fixture'],'MIXED_FIXTURE_PRODUCTION')
    output=Path(output)
    require(not output.resolve().is_relative_to(Path('/data')), 'OUTPUT_MUST_BE_OFF_VOLUME')
    require(not output.exists(),'OUTPUT_EXISTS');output.mkdir(parents=True)
    try:
        with (output/'adapted_events.jsonl').open('x') as out:
            for lane,data in lanes.items():
                for event in data['records']: out.write(canonical(event).decode()+'\n')
        slots=sorted({c['opened'] for d in lanes.values() for c in d['contracts']})
        contracts=[]
        for opened in slots:
            pair={lane:lane_contract(data,lane,opened,scorer) for lane,data in lanes.items()}
            m,v=pair['main'],pair['v81']
            require(m['target'] is None or v['target'] is None or m['target']==v['target'],'LANE_TARGET_CONFLICT')
            if m['settled'] and v['settled']:
                require(m['settlement']['receipt']['side']==v['settlement']['receipt']['side'],'LANE_SETTLEMENT_CONFLICT')
            complete=all(x['fully_scoreable'] for x in pair.values())
            contracts.append(dict(contract=ticker(opened),opened=opened,lanes=pair,
                status='FULLY_SCOREABLE_SETTLED' if complete else 'PARTIAL_OR_MISSING' if any(x['missing'] for x in pair.values()) else 'PENDING_SETTLEMENT'))
        first=next((c for c in contracts if c['status']=='FULLY_SCOREABLE_SETTLED'),None)
        prefix_complete=all(d['receipt']['minimum_sequence']==1 for d in lanes.values())
        proof=bool(first and prefix_complete and not lanes['main']['fixture'])
        counts=Counter(c['status'] for c in contracts)
        early=[q for c in contracts if c['status']=='FULLY_SCOREABLE_SETTLED' for q in c['lanes']['main']['early']['qualified']]
        finals=[c['lanes']['main']['final']['calls'] for c in contracts if c['status']=='FULLY_SCOREABLE_SETTLED']
        first_calls=[calls[0] for calls in finals if calls]
        report=dict(schema=REPORT,candidate=CANDIDATE,evidence_class='FIXTURE' if lanes['main']['fixture'] else 'PRODUCTION',
            scoring_status='VERIFIED' if proof else 'BLOCKED',
            blockers=[] if proof else (['SYNTHETIC_FIXTURE_ONLY'] if lanes['main']['fixture'] else [])+
                ([] if first else ['NO_FULLY_SCOREABLE_SETTLED_CONTRACT'])+([] if prefix_complete else ['RETAINED_PREFIX_COHORT_START_UNKNOWN']),
            production_cohort_start=utc(first['opened']) if proof else None,
            first_complete_contract=first['contract'] if first else None,
            snapshot_receipts={lane:d['receipt'] for lane,d in lanes.items()},
            scorer=dict(path='btc15_cohort_evidence_v1.py',sha256=SCORER_SHA256,
                functions=['classify_early','classify_final','classify_scalp'],
                settlement_compatibility='V2_OFFICIAL_FINALIZED_RECEIPTS; NO_FABRICATED_FINAL60_FIELDS'),
            counts=dict(total_contracts=len(contracts),fully_scoreable_settled=counts['FULLY_SCOREABLE_SETTLED'],
                pending=counts['PENDING_SETTLEMENT'],partial_missing=counts['PARTIAL_OR_MISSING'],
                both_lanes_settled_including_partial=sum(all(x['settled'] for x in c['lanes'].values()) for c in contracts)),
            early_complete_cohort=dict(accepted_signals=len(early),wins=sum(q['correct'] is True for q in early),
                losses=sum(q['correct'] is False for q in early),ask_le50=sum(q['ask_le50'] for q in early),ideal_25_to35=sum(q['ideal_25_to35'] for q in early)),
            final_complete_cohort=dict(qualified_publications=sum(map(len,finals)),qualified_contracts=len(first_calls),
                first_call_wins=sum(q['correct'] is True for q in first_calls),first_call_losses=sum(q['correct'] is False for q in first_calls)),
            contracts=contracts,signal_only=True,orders=False,manual_execution_only=True,
            reliability_claim=None,actual_fills=None,realized_profit=None,
            snapshot_pair_note='Separate consistent lane backups; matching contracts only, not simultaneous backups.',
            forward_mode='Rerun same CLI on fresh pair; stable contract/publication/origin IDs. Retained prefix loss blocks first-cohort certification.',
            adapted_sha256=file_sha(output/'adapted_events.jsonl'))
        # Add independent reporting axes without changing the frozen strict gate.
        report['completeness_diagnostics'] = diagnose(report)
        write_json(output/'checkpoint.json',report)
        return report
    except Exception as exc:
        write_json(output/'BLOCKED.json',dict(scoring_status='BLOCKED',reason=str(exc)))
        raise


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--release-receipt')
    parser.add_argument('--release-sha256')
    sub=parser.add_subparsers(dest='command',required=True)
    p=sub.add_parser('snapshot');p.add_argument('--lane',choices=list(IDENTITIES),required=True);p.add_argument('--output',required=True)
    p=sub.add_parser('score');p.add_argument('--main',required=True);p.add_argument('--v81',required=True);p.add_argument('--output',required=True)
    args=parser.parse_args()
    def execute():
        return production_snapshot(args.lane,args.output) if args.command=='snapshot' else score(args.main,args.v81,args.output)
    if args.release_receipt:
        with product_cohort.configured(sys.modules[__name__],args.release_receipt,args.release_sha256):result=execute()
    else:
        require(not args.release_sha256,'RECEIPT_PATH_REQUIRED');result=execute()
    print(json.dumps({k:result[k] for k in ('schema','scoring_status','production_cohort_start','counts','blockers') if k in result},indent=2))


if __name__=='__main__':
    main()
