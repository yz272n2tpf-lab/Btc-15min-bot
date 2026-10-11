"""Read-only native adapter; validates original evidence, does not fabricate it."""
from copy import deepcopy
from btc15_v2_product.directional import qualify
from btc15_v2_product.early_entry import fee_valid
from btc15_v2_product.early_management import features as native_features
from candidates.early_opportunity_20261011.qualification import validate_quote, settlement_context
from .engine import Engine, digest


class NativeCandidate:
    def __init__(self, profile=None):
        self.engine=Engine(profile)
        self.last_key=None;self.last_quote=None;self.last_frame=None

    def process(self,f,now):
        out=dict(actionable=False,production_enabled=False,signal_only=True,orders=False,event=None)
        try:
            if f.get('kind')!='NATIVE_DECISION':raise ValueError('NATIVE_DECISION_REQUIRED')
            expires=qualify(f,now);validate_quote(f)
            if not fee_valid(f) or f['fee_schedule']['multiplier']!=1:raise ValueError('CURRENT_PROFILE_FEE_BINDING_REQUIRED')
            if native_features(f) is None:raise ValueError('VERIFIED_CAUSAL_MODEL_FEATURES_REQUIRED')
            key=(f['native_epoch'],f['native_sequence']);q=f['quote']
            if self.last_key and key[0]==self.last_key[0] and key[1]<=self.last_key[1]:raise ValueError('NATIVE_PUBLICATION_ROLLBACK')
            if self.last_quote:
                p=self.last_quote
                if (q['epoch'],q['sid'])==(p['epoch'],p['sid']):
                    if q['seq']<p['seq'] or q['exchange_ts_ms']<p['exchange_ts_ms']:raise ValueError('QUOTE_ROLLBACK')
                    if q['seq']==p['seq'] and (q['quotes']!=p['quotes'] or q['exchange_ts_ms']!=p['exchange_ts_ms']):raise ValueError('CONFLICTING_BOOK_IDENTITY')
            s=settlement_context(f)
            r=dict(contract=f['contract'],target=f['target'],time=f['feature_cutoff'],received=now,
                left=f['official_close']-f['feature_cutoff'],btc=f['btc_price'],brti=f['brti']['value'],
                side=f['fair']['side'],p=f['fair']['fair'],healthy=True,
                publication_id=digest([key,f['contract'],f['feature_cutoff']]),
                source_epoch=digest([key[0],q['epoch'],q['sid'],f['brti']['delivery']['owner_epoch']]),
                evidence_class='VERIFIED_NATIVE_FRAME_OFFLINE',
                **{k:f[k]for k in ('up_bid','up_ask','down_bid','down_ask')})
            if s['phase']=='AVERAGING':
                r['settlement']=dict(verified_causal=not s['missing_elapsed_seconds'],contract=f['contract'],asof=r['time'],
                    hurdle=float(s['raw_unknown_mean_hurdle'])if s['raw_unknown_mean_hurdle'] is not None else None)
            out.update(self.engine.process(r),native_frame_sha256=digest(f),expires_at=expires)
            self.last_key=key;self.last_quote=deepcopy(q);self.last_frame=deepcopy(f)
        except (ValueError,KeyError,TypeError,OverflowError)as e:
            out['reason']=str(e)
            # Failed receipts remove continued confidence; never synthesize an exit BID.
            if self.engine.origin and not self.engine.terminal:
                self.engine.history=[];self.engine.streaks={};self.engine.origin['complete']=False
                self.engine.guidance='WATCH';out.update(guidance='WATCH',reasons=['NATIVE_DATA_UNAVAILABLE'],executable_exit_bid=None)
        return out
