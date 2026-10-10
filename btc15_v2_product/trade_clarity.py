"""Durable issued-signal display records. Never creates an entry or renews a lease."""
from copy import deepcopy
from datetime import datetime

SCHEMA = 'BTC15_ISSUED_SIGNALS_V1'
LIMIT = 8  # Display tail only; the complete immutable journals are unchanged.


def early_display_state(state):
    """Presentation only: preserve native management authority and evidence."""
    if state in ('ENTER', 'BUY'):
        return 'BUY'
    if state in ('HOLD', 'WATCH', 'PROTECT'):
        return 'WATCH'
    if state == 'EXIT':
        return 'EXIT'
    return state


def summary(origin, lane, state=None, terminal=None):
    if not origin:
        return None
    early = lane == 'main'
    at = datetime.fromisoformat(origin['signal_timestamp_utc']).timestamp() if early else origin['signal_ts']
    qualification = origin.get('qualification') or {}
    terminal = terminal or {}
    trigger = terminal.get('decision_ts', terminal.get('ts'))
    exit_record = None
    if terminal:
        exit_record = dict(state=terminal.get('state'), trigger_ts=trigger,
            observed_bid=terminal.get('executable_exit_bid'), reason=terminal.get('reason'),
            economics=deepcopy(terminal.get('economics')), recommendation_completed=True,
            manual_exit_confirmed=False, realized_profit=None)
    return dict(origin_id=origin['origin_id'],contract=origin['contract'],side=origin['side'],
        original_ask=origin['original_ask'],signal_ts=at,
        open_ts=origin['official_open'] if early else origin['open_ts'],
        close_ts=origin['official_close'] if early else origin['close_ts'],target=origin['target'],
        serial_index=origin.get('serial_index'),predecessor_id=origin.get('predecessor_id'),
        issued_buy=True,entry_policy=origin.get('entry_policy',origin.get('route')),
        entry_reason=qualification.get('reason') or ('Historical Tier-1 qualification' if early else 'Historical native BTC30 momentum qualification; profit forecast was not established'),
        entry_qualification=deepcopy(qualification.get('conditions',origin.get('entry_features'))),
        management_state=state,display_management_state=early_display_state(state) if early else state,terminal=exit_record,manual_fill=None,realized_profit=None)


def remember(history, origin, lane, state=None, terminal=None, reason=None):
    item=summary(origin,lane,state,terminal)
    if not item:return history
    item['management_reason']=reason
    history=deepcopy(history or [])
    prior=next((x for x in history if x['origin_id']==item['origin_id']),None)
    if prior:
        for k in ('contract','side','original_ask','signal_ts','target','open_ts','close_ts'):
            if prior[k]!=item[k]:raise ValueError('ISSUED_SIGNAL_IDENTITY_CONFLICT')
        if state is None:
            item['management_state']=prior.get('management_state')
            item['display_management_state']=prior.get('display_management_state')
        if reason is None:item['management_reason']=prior.get('management_reason')
        if not terminal:item['terminal']=prior.get('terminal')
        history[history.index(prior)]=item
    else:history.append(item)
    return history[-LIMIT:]


def project(history, origin, lane, view, event=None):
    """All current numbers come from the same accepted native publication."""
    records=deepcopy(history or [])
    now=view['published_ts'];fresh=view.get('status') in ('AVAILABLE','PASS')
    current=None
    for r in records:
        same=bool(origin and r['origin_id']==origin['origin_id'] and r['contract']==view.get('contract') and r['open_ts']<=now<r['close_ts'])
        r['status']='CLOSED_RECOMMENDATION' if r.get('terminal',{} ) and r['terminal']['state']=='EXIT' else 'EXPIRED' if r.get('terminal') or now>=r['close_ts'] else 'ACTIVE' if same else 'HISTORICAL'
        r['entry_authority_current']=bool(same and fresh and event in ('BUY','SCALP_SIGNAL') and not r.get('terminal'))
        r['current_action_authority']=bool(same and fresh and not r.get('terminal'))
        if same:current=r
    last=current or (records[-1] if records else None)
    terminal=last.get('terminal') if last else None
    label=('COMPLETED EXIT — NO NEW ENTRY' if terminal and terminal['state']=='EXIT' else
        'LAST ISSUED SIGNAL — HISTORICAL' if last and last['status']!='ACTIVE' else
        'SOURCE REFRESHING / UNAVAILABLE' if not fresh else
        'CURRENT ACTIONABLE SIGNAL' if last and last['entry_authority_current'] else
        'EXISTING SIGNAL UNDER MANAGEMENT' if current else 'NO ISSUED BUY')
    active=bool(current and fresh and not terminal)
    economics=(view.get('management') or {}).get('economics') if lane=='main' else view.get('economics')
    return dict(schema=SCHEMA,records=records,selected_origin_id=last['origin_id'] if last else None,
        display_state=label,source_available=fresh,source_reason=view.get('reason'),
        current_bid=view.get('executable_current_bid') if active else None,
        economics=deepcopy(economics) if active else None,
        current_management=early_display_state((view.get('early') or {}).get('guidance')) if lane=='main' and active else view.get('guidance') if active else None,
        entry_authority_current=bool(last and last['entry_authority_current']),
        manual_execution_only=True,orders=False)


def historical(view):
    """Strip authority and executable values on transport/lease/source failure."""
    out=deepcopy(view)
    if not out:return None
    out.update(source_available=False,entry_authority_current=False,current_bid=None,economics=None,current_management=None)
    for r in out.get('records',[]):
        r['entry_authority_current']=False;r['current_action_authority']=False
    if out.get('display_state') not in ('COMPLETED EXIT — NO NEW ENTRY','LAST ISSUED SIGNAL — HISTORICAL'):
        out['display_state']='SOURCE REFRESHING / UNAVAILABLE'
    return out
