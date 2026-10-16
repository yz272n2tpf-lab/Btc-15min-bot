"""Research-only native-journal state handoff for EXISTING CampaignVerifier.

Reads already per-envelope SHA/sequence-verified NATIVE_RECORDs produced after
the real original journal commit. Carries compact original journal IDs, native
origin references, declared contract boundaries and literally emitted labels
between 15m reader slices. It NEVER verifies source/quote/settlement
acceptance itself, NEVER invents a decision and NEVER scores an EARLY trade.

The production native record sequence can start at a non-one index when a
campaign begins mid-journal; subsequent observed commits must be contiguous.
"""
from collections import Counter,OrderedDict
import json
import math

from btc15_ladder_journal_v1 import digest
from ops.live_recording.policy import canonical,sha


class NativeJournalWindowHandoff:
    def __init__(self, *, max_journals=64, max_contracts=512,
                 max_origins=12000):
        if not 1<=max_journals<=128 or not 1<=max_contracts<=1024 or not 1<=max_origins<=20000:
            raise ValueError('NATIVE_WINDOW_RESOURCE_LIMIT')
        self.max_journals=max_journals
        self.max_contracts=max_contracts
        self.max_origins=max_origins
        self.journals={}
        self.contracts={}
        self.origins=OrderedDict()
        self.counts=Counter()
        self.labels=Counter()
        self.quarantined=False
        self.gaps=0
        self.carry_crossings=0
        self.max_contracts_used=0
        self.max_origins_used=0
        self.checkpoints=0

    def _qualifying_native(self,n,original):
        """Check only exact local native identity rules already in CampaignVerifier.

        Source, original quote acceptances, V81 owner HTTP inputs, official
        contract and settlements still REQUIRE the existing independent
        association reader and are not assumed by this method.
        """
        kind=n.get('kind')
        if kind=='NATIVE_DECISION':
            f=n['evidence']
            if n.get('origin'):
                o=n['origin']
                if n.get('event')!='BUY':
                    raise ValueError('NATIVE_WINDOW_ORIGIN_WITHOUT_BUY')
                expected=digest([n['candidate'],o['contract'],
                                 [o['native_epoch'],o['native_sequence']],o['side']])
                if o.get('origin_id')!=expected or o.get('entry_provenance')!=f:
                    raise ValueError('NATIVE_WINDOW_MAIN_ORIGIN_IDENTITY')
            if n.get('origin_id'):
                final=n.get('final')
                if not final or final.get('early_origin_id')!=n['origin_id']:
                    raise ValueError('NATIVE_WINDOW_MAIN_FINAL_ORIGIN')
            if n.get('final'):
                expected=digest([n['candidate'],'FINAL',
                                 [f['native_epoch'],f['native_sequence']]])
                if n['final'].get('publication_id')!=expected:
                    raise ValueError('NATIVE_WINDOW_FINAL_HASH')
            t=n.get('terminal')
            if t and (t['origin_id']!=n.get('origin_id') or
                      t['contract']!=f['contract'] or
                      t['decision_ts']>f['captured_ts'] or
                      (n.get('management') or {}).get('terminal')!=t):
                raise ValueError('NATIVE_WINDOW_TERMINAL_IDENTITY')
            return f.get('contract')
        if kind=='SCALP_OBSERVATION':
            if n.get('unavailable_reason'):
                self.counts['scalp_unavailable']+=1
                return n.get('contract')
            p=n['provenance']
            if n.get('origin'):
                o=n['origin'];q=p['quote']
                expected=digest([n['candidate'],o['contract'],o['side'],
                                 o['signal_ts'],q['epoch'],q['sequence']])
                if (o['origin_id']!=expected or o['entry_provenance']!=p or
                    o['original_ask']!=q[o['side'].lower()+'_ask']):
                    raise ValueError('NATIVE_WINDOW_SCALP_ORIGIN_IDENTITY')
            return n.get('contract')
        if kind in ('SETTLEMENT','BRTI_CLOSEOUT','UNAVAILABLE'):
            return n.get('contract')
        return n.get('contract') or (n.get('evidence') or {}).get('contract')

    def accept(self, role,record):
        k=record['kind']
        if k=='EVIDENCE_GAP':
            self.gaps+=1
            self.quarantined=True
            self.counts['original_evidence_gap_envelopes']+=1
        if self.quarantined:
            if k=='NATIVE_RECORD':
                self.counts['unqualified_native_after_gap']+=1
            return
        if k!='NATIVE_RECORD':return

        v=record['payload']
        raw=v.get('raw')
        if not isinstance(raw,str) or sha(raw.encode())!=v.get('sha256'):
            raise ValueError('NATIVE_WINDOW_RAW_HASH')
        if (not v.get('original_journal') or type(v.get('sequence')) is not int
                or v['sequence']<=0):
            raise ValueError('NATIVE_WINDOW_ORIGINAL_JOURNAL_IDENTITY')
        t=v.get('committed_at')
        if type(t) not in (float,int) or not math.isfinite(t):
            raise ValueError('NATIVE_WINDOW_COMMIT_TIME')
        if v.get('record_basis') not in (
            'POST_ORIGINAL_COMMIT','POST_ADMIN_COMMIT_APPLICATION_CLOCK'
        ):
            raise ValueError('NATIVE_WINDOW_COMMIT_BASIS')
        native=json.loads(raw)
        if not isinstance(native,dict):
            raise ValueError('NATIVE_WINDOW_JSON_OBJECT')
        published=native.get('published_ts')
        if type(published) in (float,int) and published>t:
            raise ValueError('NATIVE_WINDOW_PUBLICATION_AFTER_COMMIT')
        journal_id=v['original_journal']
        key=(role,record['session'],journal_id)
        if key not in self.journals:
            if len(self.journals)>=self.max_journals:
                raise ValueError('NATIVE_WINDOW_JOURNAL_LIMIT')
            self.journals[key]=dict(first=v['sequence'],last=v['sequence']-1,
                                    records=0,last_hash=None)
        journal=self.journals[key]
        if v['sequence']!=journal['last']+1:
            raise ValueError('NATIVE_WINDOW_GAP_OR_DUPLICATE_ORIGINAL_COMMIT')
        contract=self._qualifying_native(native,v)
        if contract is not None:
            if not isinstance(contract,str) or not contract:
                raise ValueError('NATIVE_WINDOW_CONTRACT_ID')
            cid=(role,contract)
            if cid not in self.contracts:
                if len(self.contracts)>=self.max_contracts:
                    raise ValueError('NATIVE_WINDOW_CONTRACT_LIMIT')
                self.contracts[cid]=dict(journal=journal_id,
                                        last_original_sequence=v['sequence'],
                                        records=0,
                                        last_original_record_sha256=None,
                                        last_origin_id=None)
                self.max_contracts_used=max(self.max_contracts_used,len(self.contracts))
            state=self.contracts[cid]
            state['last_original_sequence']=v['sequence']
            state['last_original_record_sha256']=v['sha256']
            state['records']+=1
            origin=native.get('origin')
            if isinstance(origin,dict) and origin.get('origin_id'):
                oid=origin['origin_id']
                if oid not in self.origins:
                    if len(self.origins)>=self.max_origins:
                        raise ValueError('NATIVE_WINDOW_ORIGIN_LIMIT')
                    self.origins[oid]=dict(role=role,contract=contract,
                                            journal=journal_id,
                                            original_sequence=v['sequence'])
                    self.max_origins_used=max(self.max_origins_used,len(self.origins))
                else:
                    if self.origins[oid]['contract']!=contract:
                        raise ValueError('NATIVE_WINDOW_ORIGIN_CROSS_CONTRACT')
                state['last_origin_id']=oid
            elif native.get('origin_id'):
                # Carry a reference, but do NOT assert the originating BUY
                # was captured; the original origin may predate the campaign.
                state['last_origin_id']=native['origin_id']
                if native['origin_id'] not in self.origins:
                    self.counts['origin_not_seen_in_recorded_prefix']+=1

        journal['last']=v['sequence']
        journal['records']+=1
        journal['last_hash']=v['sha256']
        self.counts['original_journal_envelopes']+=1
        self.counts['native_kind:'+str(native.get('kind'))]+=1
        for label in (native.get('event'),native.get('guidance'),
                      (native.get('final') or {}).get('state'),
                      (native.get('management') or {}).get('state'),
                      (native.get('terminal') or {}).get('state')):
            if isinstance(label,str) and label:
                self.labels[label]+=1

    def checkpoint(self,role,session,last_sequence):
        self.checkpoints+=1
        entries=sorted((
            dict(journal_id=jid,first_original_sequence=z['first'],
                 last_original_sequence=z['last'],original_commits=z['records'],
                 last_original_raw_sha256=z['last_hash'])
            for (r,s,jid),z in self.journals.items() if r==role and s==session
        ),key=lambda x:x['journal_id'])
        contracts=sorted((
            dict(ticker=ticker,original_commits=z['records'],
                 last_journal_sequence=z['last_original_sequence'],
                 last_origin_id=z['last_origin_id'],
                 last_original_raw_sha256=z['last_original_record_sha256'])
            for (r,ticker),z in self.contracts.items() if r==role
        ),key=lambda x:x['ticker'])
        result=dict(schema='BTC15_NATIVE_WINDOW_HANDOFF_AUDIT_V1',
                    role=role,session=session,
                    last_original_recording_sequence=last_sequence,
                    journal_ranges=entries,contract_states=contracts,
                    emitted_labels=dict(self.labels),original_evidence_gaps=self.gaps,
                    quarantined_on_gap=self.quarantined,
                    exact_source_and_market_associations='NOT_EVALUATED',
                    complete_early_lifecycle=False,
                    authoritative_settlement_verified=False,
                    checkpoint_is_recoverable=False,
                    production_changed=False,orders=False)
        result['audit_sha256']=sha(canonical(result))
        return result

    def finish(self):
        return dict(schema='BTC15_NATIVE_JOURNAL_HANDOFF_RESEARCH_V1',
                    original_commit_counts=dict(self.counts),
                    exact_emitted_labels=dict(self.labels),
                    journal_count=len(self.journals),
                    contract_count=len(self.contracts),
                    origin_count=len(self.origins),
                    max_contracts_used=self.max_contracts_used,
                    max_origins_used=self.max_origins_used,
                    cross_window_checkpoints=self.checkpoints,
                    original_evidence_gap_envelopes=self.gaps,
                    quarantined_on_loss=self.quarantined,
                    source_and_quote_associations_complete=False,
                    outcome_receipts_verified=False,
                    full_early_validation_complete=False,
                    signal_only=True,orders=False)