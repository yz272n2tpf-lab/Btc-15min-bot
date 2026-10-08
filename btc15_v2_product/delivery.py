"""Read-only source health and explicit failed-attempt publication. NO authority.

Health inspects original receipts. It never ingests prices, changes a source
clock, runs a model or supplies an action frame. A quote wait must not leave an
older BRTI rejection masquerading as the current delivery failure.
"""
import json
import time
from .admin import LOCAL


def snapshot(ns, pool, now=None):
    now = time.time() if now is None else now
    official = pool.official
    state = dict(schema='BTC15_DELIVERY_HEALTH_R1', observed_ts=now,
                 authority='DIAGNOSTIC_ONLY', signal_only=True, orders=False,
                 official='UNAVAILABLE', btc='UNAVAILABLE', brti='UNAVAILABLE',
                 quote='UNAVAILABLE', contract=None)
    if official:
        state['contract'] = official['contract']
        state['official'] = ('CURRENT' if official['official_open'] <= now < official['official_close'] else 'CLOSED')
    owner = ns.get('_brti_delivery')
    if owner is not None:
        b = owner.select(now, now)
        if b:
            state.update(brti='CURRENT' if b.get('ready') else 'UNAVAILABLE',
                         brti_source_ts=b.get('cf_ts'), brti_received_ts=b.get('observed_ts'),
                         brti_reason=b.get('reason'))
    btc = ns.get('_btc_spot_provenance')
    if btc:
        source, received = btc['source_utc'].timestamp(), btc['observed_utc'].timestamp()
        state.update(btc='CURRENT' if source <= received <= now and now-source <= 10 else 'UNAVAILABLE',
                     btc_source_ts=source, btc_received_ts=received)
    p = pool.current
    if p is not None and p.lock.acquire(timeout=.01):
        try:
            state['quote_connection_epoch'] = p.epoch
            state['quote_ticker'] = p.ticker
            if p.book is not None:
                state['quote_source_ts'] = None if p.book.ts_ms is None else p.book.ts_ms/1000
                try:
                    p.book.quotes(int(now*1000), p.close_ms)
                    if official and p.ticker == official['contract']:
                        state['quote']='CURRENT'
                except ValueError as exc:
                    state['quote_reason']=str(exc)
            else:
                state['quote_reason']='NO_QUALIFIED_BOOK'
        finally:
            p.lock.release()
    return state


def finish(ns, pool, worker):
    attempt = getattr(LOCAL, 'attempt', None)
    if attempt is None:
        return
    try:
        state = snapshot(ns, pool)
    except Exception as exc:
        # Diagnostic inspection must never abort native attempt finalization.
        # Missing diagnostic evidence cannot grant or renew any authority.
        state = dict(schema='BTC15_DELIVERY_HEALTH_R1', observed_ts=time.time(),
                     authority='DIAGNOSTIC_ONLY', signal_only=True, orders=False,
                     official='UNAVAILABLE', btc='UNAVAILABLE', brti='UNAVAILABLE',
                     quote='UNAVAILABLE', contract=None, diagnostic_error=type(exc).__name__)
    attempt['delivery'] = state
    # This health value is presentation only, separately from native authority.
    # The runtime endpoint reads an immutable dictionary replacement.
    ns['_v2_delivery_health'] = state
    signature=tuple(state.get(k) for k in ('contract','official','btc','brti','quote','quote_reason'))
    if signature != ns.get('_v2_delivery_signature') or time.time()-ns.get('_v2_delivery_logged',0)>=15:
        ns['_v2_delivery_signature']=signature
        ns['_v2_delivery_logged']=time.time()
        print('BTC15 DELIVERY HEALTH | '+json.dumps(state,separators=(',',':')),flush=True)
    outcome = attempt.get('outcome')
    if outcome in ('PUBLICATION_QUEUED', 'PUBLICATION_REJECTED'):
        return
    if outcome == 'QUOTE_WAIT':
        reason = 'QUOTE_SOURCE_UNAVAILABLE'
    elif attempt.get('failed_stage') == 'get_active_market' or outcome == 'NO_ACTIVE':
        reason = 'OFFICIAL_MARKET_UNAVAILABLE'
    elif attempt.get('failed_stage') == 'get_btc_spot':
        reason = 'BTC_SOURCE_UNAVAILABLE'
    else:
        reason = 'NATIVE_EVALUATION_UNAVAILABLE'
    # The existing durable writer records unavailability, retaining its original
    # lifecycle/history. The next complete native frame recovers normally.
    worker.offer(dict(kind='UNAVAILABLE', reason=reason, contract=state['contract'],
                      delivery=state))
