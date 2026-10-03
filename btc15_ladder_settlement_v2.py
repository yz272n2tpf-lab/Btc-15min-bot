"""Bounded GET-only final-result receipts for the permanent ladder journal.

One batch of at most five known closed contracts per thirty seconds. No book
capture, no model input, no decision feedback, and no settlement inference.
"""
from datetime import datetime
import json
from pathlib import Path
import sqlite3
import threading
import time
from urllib.parse import quote

BASE = 'https://external-api.kalshi.com/trade-api/v2/markets/'


def receipt(ticker, opened, payload, at):
    m = payload.get('market') or {}
    def ts(v):
        return datetime.fromisoformat(v.replace('Z','+00:00')).timestamp()
    if (m.get('ticker') != ticker or ts(m['open_time']) != opened or
            ts(m['close_time']) != opened+900 or at < opened+900):
        raise ValueError('SETTLEMENT_CONTRACT_MISMATCH')
    final = m.get('status') == 'finalized' and m.get('is_provisional') is not True
    result = m.get('result')
    settled = final and result in ('yes','no')
    return dict(source='OFFICIAL_KALSHI_GET_MARKET', endpoint=BASE+quote(ticker,safe=''),
        ticker=ticker, open_ts=opened, close_ts=opened+900, received_ts=at,
        status='AUTHORITATIVE' if settled else 'PENDING_OR_NONBINARY',
        market_status=m.get('status'),result=result,
        side=('UP' if result=='yes' else 'DOWN') if settled else None,
        settlement_ts=m.get('settlement_ts'),settlement_value_dollars=m.get('settlement_value_dollars'),
        expiration_value=m.get('expiration_value'),target=m.get('floor_strike'))


class SettlementReader:
    def __init__(self, root, lane, offer, get=None, clock=time.time):
        self.path=Path(root)/(lane+'.sqlite3');self.offer=offer;self.clock=clock
        if get is None:
            import requests
            get=requests.get
        self.get=get;self.stop=threading.Event()

    def once(self):
        if not self.path.exists(): return
        now=self.clock()
        with sqlite3.connect(self.path.resolve().as_uri()+'?mode=ro',uri=True,timeout=.2) as db:
            rows=db.execute("SELECT ticker,opened FROM contracts WHERE ticker IS NOT NULL AND opened+900 < ? AND settlement_status!='AUTHORITATIVE' AND settlement_checked < ? ORDER BY settlement_checked,opened LIMIT 5", (now,now-300)).fetchall()
        for ticker, opened in rows:
            try:
                r=self.get(BASE+quote(ticker,safe=''),timeout=3,allow_redirects=False)
                r.raise_for_status()
                value=receipt(ticker,opened,r.json(),self.clock())
            except Exception as exc:
                value=dict(source='OFFICIAL_KALSHI_GET_MARKET',ticker=ticker,open_ts=opened,
                    received_ts=self.clock(),status='UNAVAILABLE',reason=type(exc).__name__)
            if not self.offer(dict(kind='SETTLEMENT',contract=ticker,settlement=value)):
                return

    def run(self):
        while not self.stop.is_set():
            try:self.once()
            except (OSError,sqlite3.Error):pass  # Retry; pending stays explicit.
            self.stop.wait(30)
