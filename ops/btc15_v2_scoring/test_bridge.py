"""Bridge plumbing tests only. All databases are explicitly SYNTHETIC FIXTURES."""
import copy
from contextlib import closing
import hashlib
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
import zlib

sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from btc15_ladder_journal_v1 import Journal  # unchanged frozen writer, temporary files only
import bridge as b

OPEN=b.FIRST_POSSIBLE_OPEN


def q(at,seq,contract,bid=.34,side='UP'):
    return dict(ticker=contract,epoch='fixture-book',sid=1,sequence=seq,
                source_ts_ms=(at-.02)*1000,validated_at_ms=(at-.01)*1000,
                up_bid=bid if side=='UP' else .5,up_ask=max(.35,round(bid+.01,4)) if side=='UP' else .51,
                down_bid=bid if side=='DOWN' else .5,down_ask=max(.35,round(bid+.01,4)) if side=='DOWN' else .51)


def fixture_rows(lane,opened,signals=True,side='UP',gapped=False):
    contract=b.ticker(opened);step=10 if lane=='main' else 5
    origin=None;path={};terminal=None
    for i,offset in enumerate(range(0,900,step)):
        at=opened+offset+.2
        r=dict(schema=b.JOURNAL,candidate=b.CANDIDATE,contract=contract,published_ts=at,signal_only=True,orders=False)
        if lane=='main':
            r.update(build=b.IDENTITIES[lane]['build'],kind='NATIVE_DECISION')
            p=dict(contract=contract,candidate=b.CANDIDATE,official_open=opened,official_close=opened+900,
                   target=80000.,native_epoch='fixture-native',native_sequence=i+1,up_ask=.35,down_ask=.35)
            r['evidence']=p
            event=None;guidance='PASS'
            if signals and offset==300:
                origin=dict(contract=contract,side=side,original_ask=.35,signal_timestamp_utc=b.utc(at),
                    source_timestamp_utc=b.utc(at-.01),native_epoch='fixture-native',native_sequence=i+1,
                    target=80000.,official_open=opened,official_close=opened+900,entry_provenance=copy.deepcopy(p),manual_fill=None)
                origin['origin_id']=b.sha(b.canonical([b.CANDIDATE,contract,['fixture-native',i+1],side]))
                event='BUY';r['origin']=origin
            if origin: guidance='ENTER' if event=='BUY' else 'HOLD'
            final=dict(publication_id=b.sha(b.canonical([b.CANDIDATE,'FINAL',['fixture-native',i+1]])),
                       ready=signals and offset in (480,490),side=side,probability_up=.95,probability_down=.05)
            if origin:
                final.update(early_origin_id=origin['origin_id'],helper=dict(origin_id=origin['origin_id'],state='HOLD',relation='CONFIRMS'))
            r.update(event=event,guidance=guidance,origin_id=origin['origin_id'] if origin else None,final=final)
        else:
            book=q(at,i+1,contract,side=side)
            p=dict(ticker=contract,target=80000.,open_ts=opened,close_ts=opened+900,quote=book)
            r.update(kind='SCALP_OBSERVATION',provenance=p,guidance='PASS',origin_id=None,path={})
            if signals and offset==300:
                origin=dict(contract=contract,side=side,original_ask=.35,signal_ts=at,decision_ts=at-.01,
                    target=80000.,open_ts=opened,close_ts=opened+900,entry_provenance=copy.deepcopy(p),
                    deadline=at+180,manual_fill=None)
                origin['origin_id']=b.sha(b.canonical([b.CANDIDATE,contract,side,at,book['epoch'],book['sequence']]))
                r.update(event='SCALP_SIGNAL',origin=copy.deepcopy(origin))
                path=dict(samples=0,mfe=None,mae=None,missing=False,targets={},stop=None)
            if origin:
                r.update(origin_id=origin['origin_id'],guidance='EXIT' if terminal else 'ENTER' if offset==300 else 'PROTECT')
            if origin and offset in (305,310):
                bid=.48 if offset==305 else .37;book[side.lower()+'_bid']=bid;book[side.lower()+'_ask']=bid+.01
                gain=round(bid-.35,10)
                hit=dict(ts=at,quote_source_ts=book['source_ts_ms']/1000,bid=bid,delta_cents=gain*100,
                         seconds_since_signal=at-origin['signal_ts'])
                r['later_bid']=dict(hit,side=side,origin_id=origin['origin_id'],quote=copy.deepcopy(book))
                path.update(samples=path['samples']+1,mfe=max(path['mfe'] or gain,gain),
                            mae=min(path['mae'] if path['mae'] is not None else gain,gain),current=hit)
                if offset==305:
                    path['targets']={'8':dict(hit,stop_first=False),'10':dict(hit,stop_first=False),'15':None,'20':None,'30':None}
                if offset==310:
                    terminal=dict(origin=copy.deepcopy(origin),path=copy.deepcopy(path),state='EXIT',ts=at,
                        reason='ARM5_GIVEBACK4',executable_exit_bid=bid,quote=copy.deepcopy(book),
                        complete_path=True,manual_fill=None,realized_profit=None)
                    r.update(terminal=terminal,event='SCALP_EXIT',guidance='EXIT')
            r['path']=copy.deepcopy(path)
        if gapped and offset==100:
            r['unavailable_reason']='FIXTURE_SOURCE_GAP'
            r.pop('final',None)
        yield r
    s=dict(source='OFFICIAL_KALSHI_GET_MARKET',endpoint='https://external-api.kalshi.com/trade-api/v2/markets/'+contract,
           ticker=contract,open_ts=opened,close_ts=opened+900,target=80000.,received_ts=opened+902,
           status='AUTHORITATIVE',market_status='finalized',result='yes',side='UP',settlement_ts=b.utc(opened+901))
    r=dict(schema=b.JOURNAL,candidate=b.CANDIDATE,kind='SETTLEMENT',contract=contract,published_ts=opened+902,
           signal_only=True,orders=False,settlement=s)
    if lane=='main':r['build']=b.IDENTITIES[lane]['build']
    yield r


class BridgeTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.writers={lane:Journal(self.root/'live'/lane/(lane+'.sqlite3'),lane) for lane in ('main','v81')}
        self.n=0

    def tearDown(self):
        for writer in self.writers.values():writer.close()
        self.tmp.cleanup()

    def add(self,opened=OPEN,signals=True,side='UP',gapped=False):
        for lane,w in self.writers.items():
            for r in fixture_rows(lane,opened,signals,side,gapped):w.commit(r,{})

    def snap(self):
        self.n+=1;paths={}
        for lane,w in self.writers.items():
            paths[lane]=self.root/'snapshots'/str(self.n)/(lane+'.sqlite3')
            b.snapshot(w.path,paths[lane],lane,dict(b.IDENTITIES[lane]),evidence_class='FIXTURE')
        return paths

    def score(self,paths):
        self.n+=1
        return b.score(paths['main'],paths['v81'],self.root/'reports'/str(self.n),allow_fixture=True)

    def edit(self,path,change,update_record_hash=True):
        with closing(sqlite3.connect(path)) as db:
            for seq,body in db.execute('SELECT seq,body FROM events').fetchall():
                r=json.loads(zlib.decompress(body))
                if change(r):
                    raw=b.canonical(r)
                    if update_record_hash:db.execute('UPDATE events SET body=?,sha256=? WHERE seq=?',(zlib.compress(raw),b.sha(raw),seq))
                    else:db.execute('UPDATE events SET body=? WHERE seq=?',(zlib.compress(raw),seq))
            db.commit()
        rp=Path(str(path)+'.receipt.json');receipt=json.loads(rp.read_text());receipt['snapshot_sha256']=b.sha(path.read_bytes());rp.write_text(json.dumps(receipt))

    def test_end_to_end_fixture_and_forward_contracts(self):
        self.add();a=self.snap();first=self.score(a)
        self.assertEqual(first['counts']['fully_scoreable_settled'],1)
        self.assertEqual(first['scoring_status'],'BLOCKED')
        self.assertIn('SYNTHETIC_FIXTURE_ONLY',first['blockers'])
        self.assertIsNone(first['production_cohort_start'])
        self.assertEqual(first['early_complete_cohort']['wins'],1)
        self.assertEqual(first['final_complete_cohort']['qualified_publications'],2)
        self.assertEqual(first['final_complete_cohort']['first_call_wins'],1)
        path=first['contracts'][0]['lanes']['v81']['scalp']['events'][0]
        self.assertEqual(path['status'],'RESOLVED_OBSERVED_PATH')
        self.assertAlmostEqual(path['observed_mfe_cents'],13.)
        self.assertAlmostEqual(path['observed_mae_cents'],2.)
        self.assertIsNone(path['realized_profit'])
        self.assertFalse(path['observed_target_stop_telemetry']['targets']['10']['stop_first'])
        self.add(OPEN+900,signals=False);second=self.score(self.snap())
        self.assertEqual(second['counts']['fully_scoreable_settled'],2)
        self.assertEqual(second['early_complete_cohort'],first['early_complete_cohort'])
        quiet=second['contracts'][1]['lanes']
        self.assertEqual(quiet['main']['early']['status'],'PASS');self.assertEqual(quiet['main']['final']['status'],'PASS')
        self.assertEqual(quiet['v81']['scalp']['status'],'PASS')
        self.assertEqual(second['contracts'][0]['lanes']['main']['early']['qualified'][0]['origin'],first['contracts'][0]['lanes']['main']['early']['qualified'][0]['origin'])
        # A repeated identical snapshot is deterministic and never adds calls.
        self.assertEqual(first,self.score(a))

    def test_snapshot_reads_committed_wal_without_source_changes(self):
        self.add();w=self.writers['main'];wal=Path(str(w.path)+'-wal')
        self.assertTrue(wal.is_file())
        before=(w.path.read_bytes(),wal.read_bytes())
        paths=self.snap()
        self.assertEqual(before,(w.path.read_bytes(),wal.read_bytes()))
        data=b.load_snapshot(paths['main'],'main',True)
        self.assertEqual(data['receipt']['event_count'],91)
        with closing(b.readonly(w.path)) as db:
            with self.assertRaises(sqlite3.OperationalError):db.execute("INSERT INTO meta VALUES ('forbidden','1')")
            # An open read-only connection does not take a writer lock.
            with closing(sqlite3.connect(w.path,timeout=.2)) as writer:
                writer.execute("INSERT INTO meta VALUES ('fixture_concurrent_writer','1')")
                writer.commit()

    def test_production_rejects_fixture_and_wrong_runtime(self):
        self.add();p=self.snap()
        with self.assertRaisesRegex(ValueError,'FIXTURE_NOT_PRODUCTION'):b.load_snapshot(p['main'],'main')
        with self.assertRaisesRegex(ValueError,'RUNTIME_IDENTITY'):b.production_snapshot('main',self.root/'not-created.sqlite3')
        rp=Path(str(p['v81'])+'.receipt.json');rec=json.loads(rp.read_text());rec['evidence_class']='PRODUCTION';rec['identity']['service']='725e8200-656a-4576-a62a-0b84fedf9ffd';rp.write_text(json.dumps(rec))
        with self.assertRaisesRegex(ValueError,'WRONG_PRODUCTION_IDENTITY'):b.load_snapshot(p['v81'],'v81')

    def test_pending_not_finalized_and_target_mismatch_not_settled(self):
        self.add();p=self.snap()
        def pending(r):
            if r['kind']=='SETTLEMENT':r['settlement']['market_status']='determined';return True
        self.edit(p['main'],pending)
        report=self.score(p)
        self.assertEqual(report['counts']['pending'],1)
        self.assertEqual(report['early_complete_cohort']['wins'],0)
        self.assertIsNone(report['contracts'][0]['lanes']['main']['early']['qualified'][0]['correct'])

    def test_partial_and_unavailable_never_complete_pass(self):
        self.add(signals=False,gapped=True);r=self.score(self.snap())
        self.assertEqual(r['counts']['partial_missing'],1)
        self.assertEqual(r['counts']['fully_scoreable_settled'],0)
        self.assertEqual(r['contracts'][0]['lanes']['v81']['scalp']['status'],'MISSING')
        self.assertEqual(r['contracts'][0]['lanes']['main']['unavailable_publications'],1)

    def test_directional_losses_and_down_bid(self):
        self.add(side='DOWN');r=self.score(self.snap())
        self.assertEqual(r['early_complete_cohort']['losses'],1)
        self.assertEqual(r['final_complete_cohort']['first_call_losses'],1)
        self.assertEqual(r['contracts'][0]['lanes']['v81']['scalp']['events'][0]['origin']['side'],'DOWN')

    def test_hash_and_old_build_fail_closed(self):
        self.add();p=self.snap()
        def change(r):r['build']='older';return True
        self.edit(p['main'],change,False)
        with self.assertRaisesRegex(ValueError,'EVENT_HASH_MISMATCH'):self.score(p)
        p=self.snap();self.edit(p['main'],change)
        with self.assertRaisesRegex(ValueError,'OLD_PRODUCTION_BUILD'):self.score(p)

    def test_later_bid_cannot_be_equal_to_signal_time_or_wrong_side(self):
        for problem in ('time','side'):
            with self.subTest(problem=problem):
                if problem=='time':self.add()
                p=self.snap()
                def change(r):
                    if r.get('later_bid'):
                        if problem=='time':r['later_bid']['quote']['source_ts_ms']=(OPEN+300.2)*1000
                        else:r['later_bid']['side']='DOWN'
                        # Leave terminal non-executable so invalid bids are reported unresolved.
                        if r.get('terminal'):r['terminal'].update(state='UNAVAILABLE',complete_path=False)
                        return True
                self.edit(p['v81'],change);r=self.score(p)
                self.assertEqual(r['counts']['fully_scoreable_settled'],0)
                self.assertIn('INVALID_LATER_BID',r['contracts'][0]['lanes']['v81']['failure_clusters'])

    def test_incomplete_tail_without_next_rollover_is_excluded(self):
        self.add();p=self.snap()
        path=p['v81']
        with closing(sqlite3.connect(path)) as db:
            db.execute('UPDATE contracts SET missing=1,last_at=?',(OPEN+300,));db.commit()
        rp=Path(str(path)+'.receipt.json');rec=json.loads(rp.read_text());rec['snapshot_sha256']=b.sha(path.read_bytes());rp.write_text(json.dumps(rec))
        self.assertEqual(self.score(p)['counts']['fully_scoreable_settled'],0)

    def test_startup_contract_not_backfilled(self):
        self.add(OPEN-900,signals=False);r=self.score(self.snap())
        self.assertEqual(r['counts']['fully_scoreable_settled'],0)
        self.assertIn('DEPLOYMENT_STARTUP_WINDOW',r['contracts'][0]['lanes']['main']['missing'])

    def test_stop_first_remains_observational_and_unresolved(self):
        self.add();p=self.snap()
        def change(r):
            hit=r.get('later_bid')
            if hit:
                bid=.24 if hit['ts']<OPEN+310 else .48
                hit['bid']=bid;hit['quote']['up_bid']=bid;hit['quote']['up_ask']=max(.35,round(bid+.01,4));hit['delta_cents']=(bid-.35)*100
            path=r.get('path') or {}
            if path.get('samples'):
                path['mae']=-.11;path['mfe']=-.11 if path['samples']==1 else .13
            if r.get('terminal'):
                r['terminal'].update(state='UNAVAILABLE',complete_path=False)
            return True
        self.edit(p['v81'],change);r=self.score(p)
        path=r['contracts'][0]['lanes']['v81']['scalp']['events'][0]
        self.assertTrue(path['observed_target_stop_telemetry']['targets']['10']['stop_first'])
        self.assertEqual(path['observed_target_stop_telemetry']['stop']['targets_first'],[])
        self.assertEqual(path['status'],'UNRESOLVED_OR_GAPPED')
        self.assertEqual(r['counts']['fully_scoreable_settled'],0)


if __name__=='__main__':unittest.main(verbosity=2)
