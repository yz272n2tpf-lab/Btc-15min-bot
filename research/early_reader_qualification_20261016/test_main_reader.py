"""Exercise the EXISTING CampaignVerifier, not a replacement strategy validator.

Small declared fixtures use original archive/proof/settlement schemas. Labels
are scripted to test identity/chronology, not strategy or entry-price policy.
"""
import base64
from copy import deepcopy
import json
from pathlib import Path
import tempfile
import unittest

from btc15_kalshi_quote_provenance_v1 import Book
from btc15_ladder_journal_v1 import digest
from ops.live_recording.reader import CampaignVerifier, budgets
from ops.live_recording.policy import canonical, sha
from ops.recording_workflow.evidence import index_run
from ops.recording_workflow.lifecycle import frame_links, rows
from research.main_closeout_incremental_20261015 import test_quote_window_handoff_research as quotes
from research.main_closeout_incremental_20261015 import test_source_contract_window_handoff as sources


def fixture(root, mutate=None):
    a=quotes.setup(root,segment_bytes=4096)
    at=quotes.T0
    sources.source(a,'BTC',source_time=at-.4,received=at-.2)
    sources.source(a,'BRTI',source_time=at-.5,received=at-.3)
    sources.metadata(a,received=at-1)
    events=[quotes.snapshot(),quotes.delta()]
    for i,e in enumerate(events,1):quotes.event(a,e,i)
    book=Book(quotes.TICKER)
    for e in events:book.apply(e)
    origin=None
    terminal=None
    decisions=[]
    for i,label in enumerate(('ENTER','WATCH','HOLD','PROTECT','EXIT','EXIT'),1):
        cut=round(at+.1+i*.1,3)
        consumed=int((cut+.02)*1000)
        values=list(book.quotes(consumed,int(sources.CLOSE*1000)))
        proof=dict(source_time=sources.iso(cut),ticker=quotes.TICKER,epoch=quotes.EPOCH,
                   consumed_ms=consumed,identity=[book.market_id,book.sid,book.seq,book.ts_ms],events=events)
        witness=dict(ticker=quotes.TICKER,source_time=proof['source_time'],epoch=quotes.EPOCH,
                     consumed_ms=consumed,market_id=book.market_id,sid=book.sid,seq=book.seq,
                     exchange_ts_ms=book.ts_ms,close_ms=int(sources.CLOSE*1000))
        raw=json.dumps(proof,separators=(',',':'),allow_nan=False).encode()
        a.proof(proof,witness,raw,sha(raw))
        f=sources.frame()
        f.update(feature_cutoff=cut,captured_ts=cut+.05,native_sequence=i,
                 btc_source=at-.4,btc_received=at-.2,
                 brti=dict(cf_ts=at-.5,value=64201.,delivery=dict(observed_ts=at-.3,owner_epoch='BRTI-EPOCH')),
                 quote=dict(witness,quotes=values),**dict(zip(('up_bid','up_ask','down_bid','down_ask'),values)))
        if i==1:
            origin=dict(origin_id=digest(['MAIN',quotes.TICKER,['NATIVE-EPOCH',i],'UP']),
                        contract=quotes.TICKER,native_epoch='NATIVE-EPOCH',native_sequence=i,
                        side='UP',original_ask=f['up_ask'],entry_provenance=deepcopy(f))
        if label=='EXIT' and terminal is None:
            terminal=dict(state='EXIT',origin_id=origin['origin_id'],contract=quotes.TICKER,
                          side='UP',original_ask=origin['original_ask'],decision_ts=f['captured_ts'],
                          executable_exit_bid=f['up_bid'],quote=deepcopy(f['quote']))
        management=dict(state=label,terminal=deepcopy(terminal),economics=dict(
            original_signal_ask=origin['original_ask'],current_bid=f['up_bid']))
        n=dict(kind='NATIVE_DECISION',candidate='MAIN',contract=quotes.TICKER,
               evidence=f,published_ts=f['captured_ts']+.001,
               event='BUY' if i==1 else None,origin=deepcopy(origin) if i==1 else None,
               origin_id=origin['origin_id'],management=management,terminal=deepcopy(terminal),
               final=dict(publication_id=digest(['MAIN','FINAL',['NATIVE-EPOCH',i]]),
                          early_origin_id=origin['origin_id'],state='WATCH'))
        if mutate:mutate(i,n)
        sources.native(a,n,100+i)
        decisions.append(n)
    sources.outcome(a)
    a.write('STOP',dict(clean=True));a.close()
    return decisions


class MainReaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory();self.addCleanup(self.temp.cleanup)
        self.root=Path(self.temp.name);self.source=self.root/'source';self.source.mkdir()

    def reader(self,mutate=None):
        fixture(self.source,mutate)
        index_run(self.source,self.root/'index')
        v=CampaignVerifier(self.source,self.root/'index',self.root/'verify',budgets('preflight'))
        def close():
            v.db.close()
            for h in (v.fgap,v.fpart,v.fassoc):h.close()
        self.addCleanup(close)
        v.ingest();v.reconstruct()
        self.assertEqual(dict(v.errors),{})
        return v

    def verify_main(self,v):
        for loc,z in rows(v,'decision'):
            v.native_lifecycle(loc,z,frame_links(v,z['native']['evidence'],loc[2]))

    def test_buy_watch_hold_protect_exit_latch_and_official_settlement(self):
        v=self.reader();self.verify_main(v)
        loc,z=next(rows(v,'native_other'));v.outcome(loc,z)
        self.assertEqual(v.outcome_status[quotes.TICKER],'AUTHORITATIVE')
        self.assertEqual(v.metrics['terminal_associations'],2)
        self.assertEqual(v.metrics['origins_outside_recorded_journal_interval'],0)
        self.assertEqual(v.lifecycle['BUY'],1)
        for label in ('ENTER','WATCH','HOLD','PROTECT','EXIT'):self.assertGreater(v.lifecycle[label],0)
        self.assertEqual(v.metrics['outcome_associations'],1)
        self.assertEqual(v.pending,{})
        v.fassoc.flush()
        ledger=[json.loads(x) for x in (v.out/'associations.jsonl').read_text().splitlines()]
        self.assertTrue(all('record_sha256' in r['record'] for r in ledger))
        # Unit association evidence is not a three-role campaign certificate.
        self.assertFalse(v.complete(False,None))

    def test_tampered_signal_ask_fails_even_with_valid_origin_hash(self):
        v=self.reader(lambda i,n:n['origin'].update(original_ask=.25) if i==1 else None)
        with self.assertRaisesRegex(ValueError,'MAIN_ORIGIN_SIGNAL_ASK'):self.verify_main(v)

    def test_frame_price_cannot_disagree_with_exact_replayed_book(self):
        v=self.reader(lambda i,n:n['evidence'].update(up_bid=.99) if i==2 else None)
        with self.assertRaisesRegex(ValueError,'MAIN_FRAME_QUOTE_PRICES'):self.verify_main(v)

    def test_management_cannot_change_original_ask(self):
        v=self.reader(lambda i,n:n['management']['economics'].update(original_signal_ask=.01) if i==3 else None)
        with self.assertRaisesRegex(ValueError,'MAIN_MANAGEMENT_PRICE_BINDING'):self.verify_main(v)

    def test_terminal_cannot_claim_another_executable_bid(self):
        def change(i,n):
            if i==5:
                n['terminal']['executable_exit_bid']=.99
                n['management']['terminal']=deepcopy(n['terminal'])
        v=self.reader(change)
        with self.assertRaisesRegex(ValueError,'MAIN_TERMINAL_EXECUTABLE_BID'):self.verify_main(v)

    def test_other_journal_cannot_supply_missing_entry(self):
        v=self.reader()
        loc,z=next(rows(v,'decision'))
        z['original_journal']='OTHER-JOURNAL'
        v.db.execute('UPDATE facts SET v=? WHERE t="decision" AND s=? AND q=?',(canonical(z),loc[0],loc[1]))
        later=list(rows(v,'decision'))[1]
        v.native_lifecycle(*later,{})
        self.assertEqual(v.metrics['origins_outside_recorded_journal_interval'],1)

    def test_rejected_settlement_does_not_credit_authoritative_status(self):
        v=self.reader();self.verify_main(v)
        v.db.execute('DELETE FROM response')
        loc,z=next(rows(v,'native_other'))
        with self.assertRaisesRegex(ValueError,'ORIGINAL_OUTCOME_RESPONSE_MISSING'):v.outcome(loc,z)
        self.assertNotIn(quotes.TICKER,v.outcome_status)

    def test_acceptance_before_receipt_rejected(self):
        v=self.reader();loc,z=next(rows(v,'OUTCOME_ACCEPTANCE'))
        z['accepted_at']=z['value']['received_ts']-1
        v.db.execute('UPDATE facts SET v=? WHERE t="OUTCOME_ACCEPTANCE"',(canonical(z),))
        with self.assertRaisesRegex(ValueError,'ORIGINAL_OUTCOME_ACCEPTANCE_MISSING'):v.outcome(*next(rows(v,'native_other')))

    def test_response_from_different_session_rejected(self):
        v=self.reader();v.db.execute('UPDATE response SET s="OTHER-CAPTURE"')
        with self.assertRaisesRegex(ValueError,'ORIGINAL_OUTCOME_RESPONSE_MISSING'):v.outcome(*next(rows(v,'native_other')))

    def test_outcome_cannot_precede_its_publication(self):
        v=self.reader();loc,z=next(rows(v,'native_other'));z['committed_at']=z['native']['published_ts']-1
        with self.assertRaisesRegex(ValueError,'OUTCOME_PUBLICATION_COMMIT_ORDER'):v.outcome(loc,z)

    def test_settlement_target_must_match_native_contract(self):
        v=self.reader();self.verify_main(v);v.contracts[quotes.TICKER]['target']+=1
        with self.assertRaisesRegex(ValueError,'OUTCOME_NATIVE_CONTRACT_IDENTITY'):v.outcome(*next(rows(v,'native_other')))
        self.assertNotIn(quotes.TICKER,v.outcome_status)


if __name__=='__main__':unittest.main()
