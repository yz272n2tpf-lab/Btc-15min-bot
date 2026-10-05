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
            if self.inflight:
                if not self.cached or self.cached.get('binding')!=key:
                    self.condition.wait_for(lambda:not self.inflight,timeout=.45)
                return self.cached
            self.inflight=True
        try:
            self.cached=self.read(key)
        except (OSError,TimeoutError):pass  # apply() still enforces original source expiry.
        except Exception:self.cached=None
        finally:
            with self.condition:self.inflight=False;self.condition.notify_all()
        return self.cached
