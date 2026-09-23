"""Price availability accounting only; never alter registered exit policies."""
from datetime import datetime
import math


def epoch(value):return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()


def finite(value):return type(value)in(int,float)and math.isfinite(value)


def validate_event_entry(event,received,official_close):
    p=event.get('entry_provenance');started=event.get('signal_ts')
    if not isinstance(p,dict) or p.get('schema')!='V81_TIMESTAMPED_INPUTS_V1' or not finite(started):
        raise ValueError('ENTRY_SOURCE_PROVENANCE_MISSING; published price is unverified')
    q=p.get('quote',{});b=p.get('brti',{});side=event.get('side');entry=event.get('entry_price')
    if (not 0<=received-started<=3.5 or not 0<=started-epoch(event['signal_timestamp_utc'])<1
            or side not in ('UP','DOWN') or not finite(entry) or not .30<=entry<=.45
            or not finite(p.get('open_ts')) or p['open_ts']%900!=0
            or p.get('close_ts')!=official_close or official_close-p['open_ts']!=900
            or not p['open_ts']<=started<official_close
            or p.get('ticker')!=event.get('contract') or q.get('ticker')!=event.get('contract')
            or p.get('signal_only')is not True or p.get('orders')is not False
            or not finite(p.get('target')) or p['target']<=0):
        raise ValueError('ENTRY_IDENTITY_TIME_OR_BAND_INVALID')
    if (q.get('transport')!='timestamped_contiguous_ws' or not q.get('epoch') or not q.get('market_id')
            or any(type(q.get(k))is not int for k in ('source_ts_ms','validated_at_ms','sid','sequence'))
            or not p['open_ts']<=q['source_ts_ms']/1000<=q['validated_at_ms']/1000<=started
            or not 0<=started-q['source_ts_ms']/1000<=6
            or q.get(side.lower()+'_ask')!=entry):
        raise ValueError('ENTRY_QUOTE_SOURCE_INVALID')
    if (type(b.get('source_ts_ms'))is not int or not 0<=started-b['source_ts_ms']/1000<=5
            or b.get('status')!='PRIMARY_OK' or b.get('clean_for_qualification')is not True
            or not b.get('owner_epoch') or not finite(b.get('value'))):
        raise ValueError('ENTRY_BRTI_SOURCE_INVALID')
    return started


def validate_observed_ask(event,quote,now,received):
    """First qualified observation after receipt; never search for a better ask."""
    if not received<=now or now-event['signal_ts']>3.5:
        raise ValueError('ENTRY_OBSERVATION_TOO_LATE')
    if (quote.get('ticker')!=event['contract'] or quote.get('target')!=event['entry_provenance']['target']
            or quote.get('quote_transport')!='timestamped_contiguous_ws'
            or quote.get('quote_validation_utc')!=quote.get('observed_utc')
            or quote.get('signal_only')is not True or quote.get('orders')is not False
            or type(quote.get('brti_source_ts_ms'))is not int
            or not 0<=now-quote['brti_source_ts_ms']/1000<=5):
        raise ValueError('ENTRY_OBSERVATION_UNQUALIFIED')
    ask=quote.get(event['side'].lower()+'_ask')
    if not finite(ask) or not 0<=ask<=1:
        raise ValueError('EXECUTABLE_ASK_MISSING')
    if ask>event['entry_price']:
        raise ValueError('PUBLISHED_ENTRY_PRICE_UNAVAILABLE_AT_FIRST_OBSERVED_ASK')
    return ask
