"""Small current executable price projection. No model, action or journal processing."""
import time
from . import REVISION


class QuoteProjection:
    def __init__(self,pool,clock=time.time):self.pool,self.clock=pool,clock
    def capture(self):
        out=dict(schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,
            authority='PRICE_PRESENTATION_ONLY',signal_only=True,orders=False)
        now=self.clock()
        try:
            # Identity and provider are selected atomically by the native market owner.
            with self.pool.lock:p,ident=self.pool.current,self.pool.official
            if p is None or ident is None:raise ValueError('OFFICIAL_IDENTITY_UNAVAILABLE')
            if not ident['official_open']<=now<ident['official_close']:raise ValueError('OUTSIDE_OFFICIAL_WINDOW')
            if not p.lock.acquire(blocking=False):raise ValueError('QUOTE_OWNER_BUSY')
            try:
                if p.ticker!=ident['contract'] or p.book is None or not p.epoch:raise ValueError('QUOTE_BOOTSTRAP_OR_DISCONNECT')
                b=p.book
                if not b.levels['yes'] or not b.levels['no']:raise ValueError('NO_EXECUTABLE_PAIRED_BOOK')
                values=b.quotes(int(now*1000),int(ident['official_close']*1000))
                accepted=getattr(p,'accepted_ts',None)
                if accepted is None or not b.ts_ms/1000<=accepted<=now:raise ValueError('ACCEPTANCE_CLOCK_UNAVAILABLE')
                out.update(status='AVAILABLE',official_identity=dict(ident),epoch=p.epoch,market_id=b.market_id,
                    sid=b.sid,sequence=b.seq,exchange_ts=b.ts_ms/1000,accepted_ts=accepted,
                    published_ts=now,expires_at=min(ident['official_close'],b.ts_ms/1000+6),
                    up_bid=values[0],up_ask=values[1],down_bid=values[2],down_ask=values[3])
            finally:p.lock.release()
            with self.pool.lock:
                if p is not self.pool.current or ident!=self.pool.official:raise ValueError('ROLLOVER_DURING_CAPTURE')
        except (ValueError,TypeError) as exc:
            out={k:out[k] for k in ('schema','revision','authority','signal_only','orders')}
            out.update(status='UNAVAILABLE',reason=str(exc),published_ts=now)
            ident=self.pool.official
            if ident and ident['official_open']<=now<ident['official_close']:
                out['official_identity']=dict(ident)
        out['served_ts']=self.clock()
        return out
