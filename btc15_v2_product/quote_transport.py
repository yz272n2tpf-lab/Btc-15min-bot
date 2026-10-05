"""Single-flight loopback transport with a source-expiring immutable quote cache."""
from copy import deepcopy
import json
import threading
import time
from urllib.request import urlopen
from . import REVISION


def read_projection():
    with urlopen('http://127.0.0.1:8766/executable-quote',timeout=.4) as response:raw=response.read(8193)
    if len(raw)>8192:raise ValueError('OVERSIZE_QUOTE')
    return json.loads(raw)


class QuoteTransport:
    def __init__(self,read=read_projection,clock=time.time):
        self.read,self.clock=read,clock
        self.condition=threading.Condition();self.inflight=False;self.cached=None
    def _view(self,reason='QUOTE_PROJECTION_UNAVAILABLE'):
        now=self.clock();v=self.cached
        if v and v['published_ts']<=now<v['expires_at']:
            return dict(deepcopy(v),served_ts=now)
        return dict(schema='BTC15_EXECUTABLE_QUOTE_R1',revision=REVISION,
            authority='PRICE_PRESENTATION_ONLY',signal_only=True,orders=False,
            status='UNAVAILABLE',reason=reason,published_ts=now,served_ts=now)
    def capture(self):
        with self.condition:
            if self.inflight:
                if self.cached is None:self.condition.wait_for(lambda:not self.inflight,timeout=.45)
                return self._view()
            self.inflight=True
        try:
            value=self.read()
            with self.condition:
                # An explicit owner revocation always wins over retained history.
                if value.get('status')=='UNAVAILABLE':
                    self.cached=None
                    return value
                now=self.clock();i=value['official_identity']
                from .bootstrap import identity
                from datetime import datetime,timezone
                m=dict(ticker=i['contract'],open_time=datetime.fromtimestamp(i['official_open'],timezone.utc).isoformat(),
                       close_time=datetime.fromtimestamp(i['official_close'],timezone.utc).isoformat())
                if identity(m,i['target'])!=i:raise ValueError('QUOTE_IDENTITY')
                if (value.get('schema')!='BTC15_EXECUTABLE_QUOTE_R1' or value.get('revision')!=REVISION
                    or value.get('authority')!='PRICE_PRESENTATION_ONLY' or value.get('signal_only') is not True
                    or value.get('orders') is not False or value.get('status')!='AVAILABLE'
                    or not i['official_open']<=value['exchange_ts']<=value['accepted_ts']<=value['published_ts']<=value['served_ts']<=now
                    or not now<value['expires_at']<=min(i['official_close'],value['exchange_ts']+6)):
                    raise ValueError('QUOTE_PROVENANCE')
                self.cached=deepcopy(value)
                return self._view()
        except (OSError,TimeoutError):
            # Transport failure does not revoke already accepted source evidence.
            with self.condition:return self._view()
        except Exception:
            with self.condition:
                self.cached=None
                return self._view('INVALID_QUOTE_PROJECTION')
        finally:
            with self.condition:self.inflight=False;self.condition.notify_all()
