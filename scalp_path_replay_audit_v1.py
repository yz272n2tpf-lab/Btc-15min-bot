#!/usr/bin/env python3
"""Replay/audit harness for scalp path research.

Research-only / signal-only. NO ORDERS.

Reads a CSV containing per-sample scalp path rows and replays each trade through
scalp_profit_protection_shadow_v1.assess_scalp. Produces one compact summary row
per trade so HOLD/WATCH/TAKE_PROFIT/EXIT behavior can be scored without manually
reconstructing a Railway log.

Expected CSV columns (case-insensitive aliases accepted where practical):
trade_id, ticker, side, ts or seconds_open, seconds_left, entry, bid,
btc5, btc15, brti5, brti15.
"""

import argparse
import csv
import math
from collections import defaultdict
from pathlib import Path
from scalp_profit_protection_shadow_v1 import ScalpState, assess_scalp


def f(v):
    try:
        x=float(v)
        return x if math.isfinite(x) else None
    except Exception:
        return None


def pick(row, *names):
    low={str(k).lower():v for k,v in row.items()}
    for n in names:
        if n.lower() in low:
            return low[n.lower()]
    return None


def load(path):
    with Path(path).open(newline='', encoding='utf-8-sig', errors='ignore') as fh:
        rows=list(csv.DictReader(fh))
    groups=defaultdict(list)
    for i,r in enumerate(rows):
        tid=pick(r,'trade_id','candidate_id','id')
        if not tid:
            tid='%s|%s|%s' % (pick(r,'ticker','contract') or 'NA', pick(r,'side') or 'NA', pick(r,'entry_ts','signal_ts') or str(i))
        groups[tid].append(r)
    return groups


def replay(rows):
    entry=f(pick(rows[0],'entry','entry_price','ask_entry'))
    if entry is None:
        return None
    peak=None
    first_watch=first_take=first_exit=None
    first5=first10=first20=None
    last_gain=None
    max_gain=-999
    min_gain=999
    decisions=[]
    for idx,r in enumerate(rows):
        bid=f(pick(r,'bid','current_bid','exec_bid'))
        if bid is None:
            continue
        sec_open=f(pick(r,'seconds_open','age_s','elapsed_s'))
        if sec_open is None:
            sec_open=float(idx)
        sec_left=f(pick(r,'seconds_left','left_s'))
        if sec_left is None:
            sec_left=999.0
        peak=bid if peak is None else max(peak,bid)
        gain=bid-entry
        max_gain=max(max_gain,gain)
        min_gain=min(min_gain,gain)
        last_gain=gain
        if first5 is None and gain>=0.05: first5=sec_open
        if first10 is None and gain>=0.10: first10=sec_open
        if first20 is None and gain>=0.20: first20=sec_open
        s=ScalpState(entry,bid,peak,sec_open,sec_left,
                     btc5=f(pick(r,'btc5')),btc15=f(pick(r,'btc15')),
                     brti5=f(pick(r,'brti5')),brti15=f(pick(r,'brti15')))
        d=assess_scalp(s)
        decisions.append((sec_open,d.state,gain,peak-entry,d.retrace,d.reason))
        if d.state=='WATCH' and first_watch is None: first_watch=decisions[-1]
        if d.state=='TAKE_PROFIT' and first_take is None: first_take=decisions[-1]
        if d.state=='EXIT' and first_exit is None: first_exit=decisions[-1]
    if last_gain is None:
        return None
    style='NO_EXPANSION'
    if first10 is not None and first10<=30: style='BURST'
    elif first10 is not None and first10<=180: style='EXPANSION'
    take_gain=None if first_take is None else first_take[2]
    exit_gain=None if first_exit is None else first_exit[2]
    left_after_take=None if take_gain is None else max_gain-take_gain
    giveback_at_exit=None if first_exit is None else first_exit[3]-first_exit[2]
    return {
        'samples':len(decisions),'style':style,'max_gain':max_gain,'adverse':min_gain,
        'final_gain':last_gain,'t5':first5,'t10':first10,'t20':first20,
        'watch_s':None if first_watch is None else first_watch[0],
        'take_s':None if first_take is None else first_take[0],
        'take_gain':take_gain,'upside_left_after_take':left_after_take,
        'exit_s':None if first_exit is None else first_exit[0],
        'exit_gain':exit_gain,'giveback_at_exit':giveback_at_exit,
    }


def fmt(x):
    if x is None: return ''
    if isinstance(x,float): return '%.4f'%x
    return str(x)


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument('csv_path')
    ap.add_argument('--out', default='scalp_path_replay_audit_v1.csv')
    args=ap.parse_args()
    groups=load(args.csv_path)
    fields=['trade_id','samples','style','max_gain','adverse','final_gain','t5','t10','t20','watch_s','take_s','take_gain','upside_left_after_take','exit_s','exit_gain','giveback_at_exit']
    out=[]
    for tid,rows in groups.items():
        r=replay(rows)
        if r:
            r={'trade_id':tid,**r}
            out.append(r)
    with Path(args.out).open('w',newline='',encoding='utf-8') as fh:
        w=csv.DictWriter(fh,fieldnames=fields)
        w.writeheader()
        for r in out:
            w.writerow({k:fmt(r.get(k)) for k in fields})
    n=len(out)
    bursts=sum(1 for r in out if r['style']=='BURST')
    expands=sum(1 for r in out if r['style']=='EXPANSION')
    takes=sum(1 for r in out if r['take_s'] is not None)
    exits=sum(1 for r in out if r['exit_s'] is not None)
    print('SCALP PATH REPLAY AUDIT | trades %d | burst %d | expansion %d | take_profit %d | exit %d | out %s' % (n,bursts,expands,takes,exits,args.out))

if __name__=='__main__':
    main()
