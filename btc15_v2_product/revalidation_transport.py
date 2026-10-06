"""Bounded single-flight read of ephemeral confirmation, never inference on GET."""
import json
import threading
from urllib.request import urlopen


def read_confirmation(key):
    with urlopen('http://127.0.0.1:8767/revalidation?binding='+key,timeout=.4) as response:
        raw=response.read(16385)
    if len(raw)>16384:raise ValueError('OVERSIZE_CONFIRMATION')
    return json.loads(raw)


class ConfirmationTransport:
    def __init__(self,read=read_confirmation):
        self.read=read;self.condition=threading.Condition();self.inflight=False;self.cached=None
    def capture(self,native):
        from .revalidation import binding
        key=binding(native)
        with self.condition:
            if not self.inflight:
                self.inflight=True
                def read():
                    try:value=self.read(key)
                    except Exception:value=None
                    with self.condition:
                        self.cached=value;self.inflight=False
                threading.Thread(target=read,daemon=True,name='presentation-confirmation').start()
            return self.cached
