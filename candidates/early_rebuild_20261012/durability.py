"""Observed durable-opportunity labels, independent of all EXIT/FINAL outcomes."""
from .assessment import validate_row
from .continuation import EVIDENCE, TARGET, OBSERVED_DOMAINS
from candidates.early_value_20261011.engine import fee

CHECKPOINTS=(60,120,180,240,300,420)


def admissible(r,base):
    return (not validate_row(r) and r['contract']==base['contract'] and r['target']==base['target']
            and abs(r['time']+r['left']-base['time']-base['left'])<=1
            and r['source_epoch']==base['source_epoch'] and 0<=r['received']-r['time']<=6)


def continuous(a,b):
    return (0<b['time']-a['time']<=6 and 0<b['received']-a['received']<=6
            and b['source_epoch']==a['source_epoch'])


def net_cents(decision,entry,sale,side):
    k=side.lower();ask=entry[k+'_ask'];bid=sale[k+'_bid']
    reserve=max(.02,decision[k+'_ask']-decision[k+'_bid'],ask-entry[k+'_bid'],sale[k+'_ask']-bid)
    return 100*(bid-ask-fee(ask)-fee(bid)-reserve)


def label(landmark,tape,*,native=False):
    """tape rows carry causal common eligibility from the unchanged onset reducer.

    No fitted score participates in this target. Unknown native evidence is never
    replaced by a quote-only result. All returned prices are hypothetical observations.
    """
    out={k:landmark[k] for k in ('id','setup_id','contract','side','period','decision_time','context','features')}
    out.update(target=TARGET,evidence_class=EVIDENCE,y=None,status='UNASSESSABLE',
        reasons=[],native_execution_verified=False,label_available_at=None,entry=None,
        episodes=[],checkpoints={},worst_observed_net_cents=None,delayed_liquidation=None,
        first_positive_at=None,first_10c_at=None,adverse_at=None,source_gap_before_event=False,
        price_lost=False,burst_observed=False,observed_path_complete=False)
    if native:
        out['reasons']=['ORIGINAL_RECEIPTS_DEPTH_QUANTITY_AND_APPLICABLE_FEES_REQUIRED'];return out
    i=landmark['index'];d=tape[i]['row'];side=landmark['side'];k=side.lower();sid=landmark['setup_id']
    if d.get('evidence_class')=='SYNTHETIC_FIXTURE':out['evidence_class']='SYNTHETIC_FIXTURE'
    elif d.get('evidence_class') not in OBSERVED_DOMAINS:
        out['reasons']=['UNKNOWN_EVIDENCE_DOMAIN'];return out
    close=d['time']+d['left'];deadline=close-10;start=d['received'];entry_i=None
    delayed_quote=next((t['row'] for t in tape[i+1:] if t['row']['time']>=start+10
                        and t['row']['received']<=start+20 and admissible(t['row'],d)),None)
    out['delayed_price_observation']=(dict(time=delayed_quote['received'],ask=delayed_quote[k+'_ask'],
        elapsed=delayed_quote['received']-start,primary=.25<=delayed_quote[k+'_ask']<=.55)
        if delayed_quote else None)
    for j in range(i+1,len(tape)):
        r=tape[j]['row'];common=tape[j]['sides'].get(side,{})
        if r['received']>start+20:break
        if not common.get('eligible') or common.get('setup_id')!=sid:
            out.update(y=0,status='CANCELED_ENTRY',label_available_at=r['received'],
                       reasons=common.get('reasons') or ['COMMON_QUALIFICATION_LOST'],
                       price_lost=not .25<=r[k+'_ask']<=.55,
                       recheck=dict(time=r['received'],ask=r[k+'_ask'],elapsed=r['received']-start))
            return out
        if r['time']>=start+10 and admissible(r,d):entry_i=j;break
    if entry_i is None:
        out['reasons']=['DELAYED_ENTRY_OBSERVATION_MISSING'];return out
    entry=tape[entry_i]['row'];out['entry']=dict(time=entry['received'],source_time=entry['time'],
        ask=entry[k+'_ask'],index=entry_i,elapsed=entry['received']-start)
    # Evidence prior to entry is also required to establish an admissible delayed wait.
    wait=[t['row'] for t in tape[i:entry_i+1]]
    if any(not admissible(r,d) for r in wait) or any(not continuous(a,b) for a,b in zip(wait,wait[1:])):
        out['source_gap_before_event']=True
    path=[];episodes=[];episode=[];gap=out['source_gap_before_event'];previous=entry
    for j in range(entry_i,len(tape)):
        r=tape[j]['row']
        if r['received']>=close:break
        valid=admissible(r,d)
        linked=(j==entry_i or continuous(previous,r)) and valid
        if not linked:
            gap=True
            if episode:episodes.append(episode);episode=[]
        if valid:
            n=net_cents(d,entry,r,side)
            point=dict(index=j,time=r['received'],source_time=r['time'],net_cents=n,gap_before=gap)
            path.append(point)
            if n>0 and out['first_positive_at'] is None:out['first_positive_at']=r['received']
            if n>=10-1e-8:
                if out['first_10c_at'] is None:out['first_10c_at']=r['received']
                episode.append(point)
            elif episode:episodes.append(episode);episode=[]
            if n<=-10+1e-8 and out['adverse_at'] is None and r['received']<=deadline:
                out['adverse_at']=r['received'];out['adverse_order_known']=not gap
        previous=r
    if episode:episodes.append(episode)
    if path:out['worst_observed_net_cents']=min(p['net_cents'] for p in path)
    out['observed_path_complete']=bool(path and not gap and path[-1]['time']>=deadline)
    out['source_gap_before_event']=gap
    out['covered_seconds']=sum(b['time']-a['time'] for a,b in zip(path,path[1:])
        if b['index']==a['index']+1 and continuous(tape[a['index']]['row'],tape[b['index']]['row']))
    out['elapsed_path_seconds']=path[-1]['time']-entry['received'] if path else 0
    out['coverage_fraction']=out['covered_seconds']/out['elapsed_path_seconds'] if out['elapsed_path_seconds'] else 0
    pairs=[(a,b) for a,b in zip(path,path[1:]) if b['index']==a['index']+1 and
           continuous(tape[a['index']]['row'],tape[b['index']]['row'])]
    measurable=[(a,b) for a,b in pairs if tape[a['index']]['sides'][side].get('short_agreement') is not None]
    total=sum(b['time']-a['time'] for a,b in measurable)
    out['short_agreement_covered_occupancy']=(sum(b['time']-a['time'] for a,b in measurable
        if tape[a['index']]['sides'][side]['short_agreement'])/total if total else None)
    successes=[]
    for ep in episodes:
        span=ep[-1]['time']-ep[0]['time'];spacings=[b['time']-a['time'] for a,b in zip(ep,ep[1:])]
        e=dict(start=ep[0]['time'],end=ep[-1]['time'],span=span,quotes=len(ep),
               max_gap=max(spacings,default=0),coverage_fraction=1. if span else 0.,checkpoints={})
        for seconds in CHECKPOINTS:
            cert=next((p for p in ep if p['time']-ep[0]['time']>=seconds and p['time']<=deadline),None)
            if not cert or len(ep)<3:continue
            sale=next((p for p in path if p['source_time']>=cert['time']+10 and p['time']<=cert['time']+20),None)
            bridge=[t['row'] for t in tape[cert['index']:(sale['index']+1 if sale else cert['index']+1)]]
            ok_bridge=bool(sale and all(admissible(r,d) for r in bridge) and all(continuous(a,b) for a,b in zip(bridge,bridge[1:])))
            accessible=bool(sale and ok_bridge and sale['net_cents']>=10-1e-8)
            c=dict(certificate_at=cert['time'],delayed_accessible=accessible if ok_bridge else None,
                sale_at=sale['time'] if sale else None,net_cents=sale['net_cents'] if sale else None,
                elapsed=sale['time']-cert['time'] if sale else None,
                prior_event_order_known=not cert['gap_before'])
            e['checkpoints'][str(seconds)]=c
            if seconds==60 and accessible:successes.append((sale,cert,c))
        out['episodes'].append(e)
    for seconds in CHECKPOINTS:
        observed=[e['checkpoints'][str(seconds)] for e in out['episodes'] if str(seconds) in e['checkpoints']]
        out['checkpoints'][str(seconds)]=dict(runway_possible=deadline-entry['received']>=seconds,
            observed_certificates=len(observed),accessible=sum(c['delayed_accessible'] is True for c in observed),
            delayed_failed=sum(c['delayed_accessible'] is False for c in observed),
            delayed_unknown=sum(c['delayed_accessible'] is None for c in observed))
    first=next(((sale,cert,c) for sale,cert,c in successes if not cert['gap_before'] and
                (out['adverse_at'] is None or sale['time']<out['adverse_at'])),None)
    if first:
        sale,cert,c=first;out.update(y=1,status='DURABLE_SUCCESS',label_available_at=sale['time'],delayed_liquidation=c)
    elif out['adverse_at'] is not None and out.get('adverse_order_known'):
        out.update(y=0,status='ADVERSE_FIRST',label_available_at=out['adverse_at'])
    elif out['observed_path_complete']:
        out.update(y=0,status='BURST_ONLY' if episodes else 'NO_10C_OPPORTUNITY',label_available_at=path[-1]['time'])
    else:
        out.update(status='CENSORED_PATH',reasons=['EVENT_ORDER_OR_TERMINAL_COVERAGE_UNKNOWN'])
    out['burst_observed']=bool(episodes and not any(e['span']>=60 for e in out['episodes']))
    out['price_window_lost_at']=next((t['row']['received'] for t in tape[entry_i:] if not .25<=t['row'][k+'_ask']<=.55),None)
    return out
