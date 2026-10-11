"""Reuse unchanged provenance validators; no production wiring or source polling."""
from candidates.early_condition_20261011.native import NativeCandidate as PriorNative
from .engine import Engine


class NativeCandidate(PriorNative):
    def __init__(self,profile=None):
        super().__init__(profile)
        self.engine=Engine(profile)

    def process(self,frame,now):
        out=super().process(frame,now)
        if 'reason' in out:
            self.engine.invalidate(now,['NATIVE_EVIDENCE_INVALID',out['reason']])
        out.update(self.engine.manual_entry(now))
        return out
