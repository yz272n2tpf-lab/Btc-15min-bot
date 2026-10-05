"""Official identity staging and two bounded instances of the SAME WS decoder.

Preparation performs no consume/frame call, inference, qualification, confirmation
or journal offer. Native callers retain their original clocks and source gates.
"""
import ast
from copy import deepcopy
from datetime import datetime,timezone
import inspect
import math
import threading
import time
from zoneinfo import ZoneInfo
import btc15_kalshi_quote_provenance_v1 as quotes
PREPARE_LEAD_SECONDS=30  # Transport preparation only; never a qualification/timing gate.


def identity(m,target=None):
    def epoch(s):
        d=datetime.fromisoformat(str(s).replace('Z','+00:00'))
        if d.tzinfo is None:raise ValueError('OFFICIAL_CLOCK_TIMEZONE')
        return d.timestamp()
    o,c=epoch(m['open_time']),epoch(m['close_time'])
    ticker='KXBTC15M-'+datetime.fromtimestamp(c,timezone.utc).astimezone(ZoneInfo('America/New_York')).strftime('%y%b%d%H%M-%M').upper()
    if c-o!=900 or o%900 or m.get('ticker')!=ticker:raise ValueError('OFFICIAL_WINDOW_OR_TICKER')
    out=dict(contract=ticker,official_open=o,official_close=c)
    if target is not None:
        if type(target) not in (int,float) or not math.isfinite(target) or target<=0:raise ValueError('OFFICIAL_TARGET')
        out['target']=target
    return out


def _accepted_session():
    """Only insert acceptance-clock metadata after the frozen decoder's publication."""
    tree=ast.parse(inspect.getsource(quotes.Provider))
    fn=next(n for n in tree.body[0].body if isinstance(n,ast.FunctionDef) and n.name=='session')
    class Insert(ast.NodeTransformer):
        count=0
        def visit_Assign(self,n):
            if ast.unparse(n.targets[0])=='(self.events, self.epoch)':
                self.count+=1
                return [n,*ast.parse("self._accepted_clock(evidence.book, epoch)").body]
            return n
    visitor=Insert();fn=visitor.visit(fn)
    if visitor.count!=1:raise RuntimeError('PINNED_PROVIDER_PUBLICATION_SEAM')
    ns=dict(vars(quotes));exec(compile(ast.fix_missing_locations(ast.Module(body=[fn],type_ignores=[])),'<accepted-clock-only>','exec'),ns)
    return ns['session']


class PreparedProvider(quotes.Provider):
    session=_accepted_session()
    @property
    def book(self):return getattr(self,'_book',None)
    @book.setter
    def book(self,value):
        # Disconnect/bootstrap revokes the presentation snapshot immediately.
        if value is None:self.presentation_quote=None
        self._book=value
    def _accepted_clock(self,book,epoch):
        key=(epoch,book.market_id,book.sid,book.seq,book.ts_ms)
        if key!=getattr(self,'accepted_key',None):
            self.accepted_key=key;self.accepted_ts=time.time()
        # Original owner lock is held, after the accepted decoder publication.
        # Detached tuple only: no consume(), frame(), network read or strategy call.
        try:
            if self.book is not book:raise ValueError('BOOK_REVOKED')
            at=time.time();values=book.quotes(int(at*1000),self.close_ms)
            if not book.ts_ms/1000<=self.accepted_ts<=at:raise ValueError('ACCEPTANCE_CLOCK')
            snapshot=(self.ticker,epoch,book.market_id,book.sid,book.seq,book.ts_ms/1000,
                      self.accepted_ts,at,values)
        except (ValueError,TypeError):snapshot=None
        self.presentation_quote=snapshot
    def frame(self,ticker,close_ms):
        # Call the unchanged V81 frame method with this same provider object.
        from btc15_v81_qualified_inputs_v1 import QuoteProvider
        return QuoteProvider.frame(self,ticker,close_ms)


class Pool:
    def __init__(self,factory=PreparedProvider,clock=time.time):
        self.factory,self.clock=factory,clock;self.providers=[];self.current=None;self.lock=threading.RLock()
        self.official=None
    def prepare(self,m):
        ident=identity(m);ticker=ident['contract'];now=self.clock()
        if not now<ident['official_close'] or ident['official_open']>now+PREPARE_LEAD_SECONDS:return None
        with self.lock:
            p=next((p for p in self.providers if p.ticker==ticker),None)
            if p is None:
                # Never disturb the current unexpired subscription.
                p=next((p for p in self.providers if p is not self.current and (p.close_ms or 0)<=now*1000),None)
                if p is None:
                    if len(self.providers)>=2:return None
                    p=self.factory();self.providers.append(p)
                with p.lock:
                    p.ticker=ticker;p.close_ms=int(ident['official_close']*1000)
                    p.book=None;p.events=[];p.epoch=None;p.accepted_key=None;p.accepted_ts=None
            return p
    def select(self,m,target):
        if target is None:raise ValueError('OFFICIAL_TARGET')
        ident=identity(m,target);now=self.clock()
        if not ident['official_open']<=now<ident['official_close']:raise ValueError('NO_PREOPEN_SELECTION')
        with self.lock:
            if self.official and self.official['contract']==ident['contract'] and self.official!=ident:
                raise ValueError('FIXED_OFFICIAL_IDENTITY_CHANGED')
            p=self.prepare(m)
            if p is None:raise ValueError('PREPARATION_SLOT_UNAVAILABLE')
            self.current,self.official=p,ident
        return m
    def consume(self,ticker,source_time,close_ms):
        p=self.current
        if p is None or p.ticker!=ticker or p.close_ms!=close_ms:return None
        return p.consume(ticker,source_time,close_ms)
    def frame(self,ticker,close_ms):
        p=self.current
        if p is None or p.ticker!=ticker or p.close_ms!=close_ms:return None
        return p.frame(ticker,close_ms)
    @property
    def last_product_quote(self):return getattr(self.current,'last_product_quote',None)


class Preparation:
    def __init__(self,get,target,pool,clock=time.time):
        self.get,self.target,self.pool,self.clock=get,target,pool,clock
        self.staged={};self.error=None;self.lock=threading.Lock();self.stop=threading.Event()
    def scan(self):
        now=self.clock()
        data=self.get('/trade-api/v2/markets',params={'status':'unopened','series_ticker':'KXBTC15M','limit':1000})
        candidates=[]
        for m in data.get('markets',[]):
            try:i=identity(m)
            except (ValueError,KeyError,TypeError):continue
            if now<i['official_open']<=now+900:candidates.append((i['official_open'],m))
        if candidates:
            m=min(candidates,key=lambda pair:pair[0])[1]
            self.pool.prepare(m)
            with self.lock:
                self.staged={o:m for o,m in self.staged.items() if identity(m)['official_close']>now}
                self.staged[identity(m)['official_open']]=deepcopy(m)
        self.error=None
    def select(self,fallback):
        now=self.clock()
        with self.lock:m=deepcopy(self.staged.get(int(now//900)*900))
        if m is not None:
            i=identity(m)
            if i['official_open']<=now<i['official_close']:
                # Exact official read at the native attempt; staged target is NEVER used.
                data=self.get('/trade-api/v2/markets/'+i['contract'])
                exact=data.get('market',data)
                e=identity(exact)
                if e!=i:raise ValueError('STAGED_EXACT_IDENTITY_CONFLICT')
                target=self.target(exact)
                if target is not None:return self.pool.select(exact,target)
                # Missing official target remains a genuine failure on native path.
                return exact
        m=fallback()
        if m is not None:
            target=self.target(m)
            if target is not None:self.pool.select(m,target)
        return m
    def run(self):
        while not self.stop.is_set():
            try:self.scan()
            except Exception as exc:self.error=type(exc).__name__
            self.stop.wait(5.)
    def start(self):threading.Thread(target=self.run,daemon=True,name='official-identity-preparation').start()
