"""Detached SAME-provider book projection; never waits for the mutable owner lock."""
import time
from . import REVISION


class QuoteProjection:
    def __init__(self,pool,clock=time.time):self.pool,self.clock=pool,clock
    def capture(self):
        now=self.clock()
        out=dict(schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,
            authority='PRICE_PRESENTATION_ONLY',signal_only=True,orders=False)
        try:
            with self.pool.lock:p,ident=self.pool.current,self.pool.official
            if p is None or ident is None:raise ValueError('OFFICIAL_IDENTITY_UNAVAILABLE')
            if not ident['official_open']<=now<ident['official_close']:raise ValueError('OUTSIDE_OFFICIAL_WINDOW')
            snapshot=getattr(p,'presentation_quote',None)
            if snapshot is None:raise ValueError('QUOTE_BOOTSTRAP_OR_DISCONNECT')
            ticker,epoch,market_id,sid,seq,source,accepted,published,values=snapshot
            if ticker!=ident['contract'] or not epoch:raise ValueError('QUOTE_IDENTITY')
            expires=min(ident['official_close'],source+6)
            if not ident['official_open']<=source<=accepted<=published<=now<expires:
                raise ValueError('QUOTE_SOURCE_EXPIRED_OR_FUTURE')
            out.update(status='AVAILABLE',official_identity=dict(ident),epoch=epoch,market_id=market_id,
                sid=sid,sequence=seq,exchange_ts=source,accepted_ts=accepted,published_ts=published,
                expires_at=expires,up_bid=values[0],up_ask=values[1],down_bid=values[2],down_ask=values[3])
            with self.pool.lock:
                if p is not self.pool.current or ident!=self.pool.official:raise ValueError('ROLLOVER_DURING_CAPTURE')
            if getattr(p,'presentation_quote',None) is None:raise ValueError('QUOTE_REVOKED')
        except (ValueError,TypeError) as exc:
            out={k:out[k] for k in ('schema','revision','authority','signal_only','orders')}
            out.update(status='UNAVAILABLE',reason=str(exc),published_ts=now)
            ident=self.pool.official
            if ident and ident['official_open']<=now<ident['official_close']:out['official_identity']=dict(ident)
        out['served_ts']=self.clock()
        if out.get('status')=='AVAILABLE' and out['served_ts']>=out['expires_at']:
            return dict(schema=out['schema'],revision=REVISION,authority=out['authority'],
                signal_only=True,orders=False,status='UNAVAILABLE',reason='QUOTE_SOURCE_EXPIRED_OR_FUTURE',
                published_ts=out['served_ts'],served_ts=out['served_ts'])
        return out
