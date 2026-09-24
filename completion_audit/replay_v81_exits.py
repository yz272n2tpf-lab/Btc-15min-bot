"""Prospective exit comparison on published V8.1 entries, never new entries."""
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from common_journal import scan
from v81_exit_candidate import Lifecycle, POLICIES
from qualify_v81_entry import validate_event_entry, validate_observed_ask


def epoch(value):return datetime.fromisoformat(value.replace('Z','+00:00')).timestamp()


def evaluate(path,start,end,run_id='clean-source-v2-20260923'):
    damage=[];timeline=[];closes={}
    for item in scan(path,damage):
        row=item['record']
        if row.get('run_id')!=run_id:raise ValueError('Mixed run identities')
        if row.get('record_type')=='SNAPSHOT_INPUT':
            close=epoch(row['close_utc']);ticker=row['ticker']
            if ticker in closes and closes[ticker]!=close:raise ValueError('Official close conflict')
            closes[ticker]=close
            timeline.append((epoch(row['observed_utc']),'quote',row))
        elif row.get('record_type')=='OBSERVATION':
            for source in row['sources']:
                if source['service']=='v81' and isinstance(source.get('state'),dict):
                    timeline.append((epoch(source['response_received_utc']),'signal',source['state']))
    seen=set();lives=[];rejected=[];events=[];pending=[];accepted=[]
    for now,kind,row in sorted(timeline,key=lambda item:item[0]):
        if not epoch(start)<=now<epoch(end):continue
        if kind=='signal':
            event=row.get('last_signal_event') or {}
            when=event.get('signal_timestamp_utc')
            if not when or not epoch(start)<=epoch(when)<epoch(end):continue
            key=(event.get('contract'),event.get('side'),event.get('entry_price'),when)
            if key in seen:continue
            seen.add(key);events.append(dict(event,first_observed_utc=datetime.fromtimestamp(now,timezone.utc).isoformat()))
            try:
                if row.get('active') is not True:raise ValueError('No active publication at first observation')
                if row.get('manual_execution_only') is not True or row.get('order_action') is not None:
                    raise ValueError('Signal-only publication required')
                if not 0<=now-epoch(row['generated_utc'])<=3.5:raise ValueError('Publication stale at receipt')
                if key[0] not in closes:raise ValueError('Official close unavailable')
                started=validate_event_entry(event,now,closes[key[0]])
                pending.append(dict(event=event,receipt=now,key=key,started=started))
            except (ValueError,KeyError,TypeError) as exc:
                rejected.append(dict(entry_identity=key,reason=str(exc)))
        else:
            for item in pending[:]:
                event=item['event']
                if row['ticker']!=event['contract']:
                    continue
                # Assess the first same-contract observation, never cherry-pick
                # a later cheaper ask or manufacture a fill at an old price.
                pending.remove(item)
                try:
                    ask=validate_observed_ask(event,row,now,item['receipt'])
                    lives.extend(Lifecycle(policy,event['contract'],event['side'],event['entry_price'],
                        item['started'],now,closes[event['contract']])for policy in POLICIES)
                    accepted.append(dict(entry_identity=item['key'],observed_ask=ask,
                        first_entry_quote_utc=row['observed_utc'],execution_or_fill_proven=False))
                except (ValueError,KeyError,TypeError)as exc:
                    rejected.append(dict(entry_identity=item['key'],reason=str(exc),
                        first_observed_ask=row.get(event['side'].lower()+'_ask'),
                        first_entry_quote_utc=row['observed_utc']))
            quote=dict(observed_ts=now,ticker=row['ticker'],brti_source_ts=row['brti_source_ts_ms']/1000,
                       quote_validated_at_observation=(row.get('quote_transport')=='timestamped_contiguous_ws'
                           and row.get('quote_validation_utc')==row['observed_utc']
                           and row.get('signal_only') is True and row.get('orders') is False),
                       up_bid=row['up_bid'],down_bid=row['down_bid'])
            for life in lives:life.update(quote)
    rejected.extend(dict(entry_identity=x['key'],reason='NO_ENTRY_QUOTE_OBSERVED')for x in pending)
    results=[life.terminal or dict(status='INCOMPLETE_PATH',policy=life.policy.name,ticker=life.ticker,
             side=life.side,entry_ask=life.entry,observed_mfe=life.peak,observed_mae=life.trough,
             complete_path=False,realized_profit=False,orders=False)for life in lives]
    return dict(window=dict(start=start,end=end),published_entries=events,rejected_entries=rejected,
                accepted_entry_observations=accepted,entry_accounting_revision='SOURCE_AND_FIRST_OBSERVED_ASK_V1',
                outcomes=results,counts=dict(Counter(r['status']for r in results)),journal_damage=damage,
                policy_source_sha256=hashlib.sha256(Path(__file__).with_name('v81_exit_candidate.py').read_bytes()).hexdigest(),
                scope='Source-verified entry with first observed ask confirmation to sampled qualified bids; no fills, fees, net profit or full detector/reentry replay.',
                actual_exit_advice_published=False,production_connected=False,orders=False)


if __name__=='__main__':
    import argparse
    parser=argparse.ArgumentParser();parser.add_argument('journal',type=Path)
    parser.add_argument('--start',required=True);parser.add_argument('--end',required=True)
    parser.add_argument('--output',required=True,type=Path);args=parser.parse_args()
    result=evaluate(args.journal,args.start,args.end)
    with args.output.open('x')as stream:json.dump(result,stream,indent=2,allow_nan=False)
    print(json.dumps(dict(published_entries=len(result['published_entries']),rejected_entries=len(result['rejected_entries']),counts=result['counts'],production_connected=False)))
