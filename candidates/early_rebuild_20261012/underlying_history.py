"""Causal BTC/BRTI observations only. No contract, quote, target or position state.

Native samples require original clocks for both sources. Normalized retained rows
have a separate, explicit diagnostic path and never acquire native receipt proof.
"""
from dataclasses import dataclass
import math

SCHEMA='INDEPENDENT_UNDERLYING_HISTORY_V1'
NATIVE='ORIGINAL_UNDERLYING_CLOCKS'
FIXTURE='SYNTHETIC_FIXTURE'
PROXY='RETAINED_OBSERVATION_PROXY'


def finite(v):return type(v) in (int,float) and math.isfinite(v)


@dataclass(frozen=True)
class Observation:
    time: float
    received: float
    btc: float
    brti: float
    source_id: str
    source_epoch: str
    record_id: str
    evidence_class: str
    btc_source_time: float = None
    btc_received_time: float = None
    brti_source_time: float = None
    brti_received_time: float = None
    btc_source_id: str = None
    brti_source_id: str = None
    btc_epoch: str = None
    brti_epoch: str = None

    def validate(self,now,*,allow_observation_proxy=False):
        if not all(finite(v) for v in (now,self.time,self.received,self.btc,self.brti)) or min(self.btc,self.brti)<=0:
            raise ValueError('UNDERLYING_INVALID_NUMERIC')
        if not all(isinstance(v,str) and v for v in (self.source_id,self.source_epoch,self.record_id)):
            raise ValueError('UNDERLYING_SOURCE_IDENTITY_MISSING')
        if not self.time<=self.received<=now:raise ValueError('UNDERLYING_FUTURE_OR_REVERSED_CLOCK')
        if not 0<=self.received-self.time<=10:raise ValueError('UNDERLYING_STALE_DELIVERY')
        if self.evidence_class==PROXY:
            if not allow_observation_proxy:raise ValueError('ORIGINAL_UNDERLYING_CLOCKS_REQUIRED')
            if any(v is not None for v in (self.btc_source_time,self.btc_received_time,self.brti_source_time,
                    self.brti_received_time,self.btc_source_id,self.brti_source_id,self.btc_epoch,self.brti_epoch)):
                raise ValueError('PROXY_MUST_NOT_INVENT_ORIGINAL_CLOCKS')
            return
        if self.evidence_class not in (NATIVE,FIXTURE):raise ValueError('UNDERLYING_EVIDENCE_CLASS_INVALID')
        if not 1000<self.brti<1_000_000:raise ValueError('UNDERLYING_BRTI_VALUE_INVALID')
        for key,age in (('btc',10),('brti',5)):
            source=getattr(self,key+'_source_time');receipt=getattr(self,key+'_received_time')
            if not finite(source) or not finite(receipt):raise ValueError('ORIGINAL_UNDERLYING_CLOCKS_REQUIRED')
            if not source<=receipt<=self.time:raise ValueError('UNDERLYING_COMPONENT_CLOCK_INVALID')
            if self.received-source>age:raise ValueError('UNDERLYING_COMPONENT_STALE')
            if not all(isinstance(v,str) and v for v in (getattr(self,key+'_source_id'),getattr(self,key+'_epoch'))):
                raise ValueError('UNDERLYING_COMPONENT_IDENTITY_MISSING')

    def identity(self):
        return (self.source_id,self.source_epoch,self.evidence_class,self.btc_source_id,
                self.brti_source_id,self.btc_epoch,self.brti_epoch)


@dataclass(frozen=True)
class Snapshot:
    observations: tuple
    error: str = None

    def rows_at(self,r,*,allow_observation_proxy=False):
        if self.error:raise ValueError(self.error)
        if not self.observations:raise ValueError('UNDERLYING_HISTORY_UNAVAILABLE')
        for z in self.observations:
            z.validate(r['received'],allow_observation_proxy=allow_observation_proxy)
            if z.time>r['time']:raise ValueError('FUTURE_FEATURE_INPUT')
        last=self.observations[-1]
        if (last.time!=r['time'] or last.received>r['received'] or last.btc!=r['btc'] or last.brti!=r['brti']):
            raise ValueError('UNDERLYING_DECISION_ENDPOINT_MISMATCH')
        if r['received']-last.time>10:raise ValueError('UNDERLYING_CURRENT_ENDPOINT_STALE')
        if last.evidence_class!=PROXY and (r['received']-last.btc_source_time>10 or r['received']-last.brti_source_time>5):
            raise ValueError('UNDERLYING_CURRENT_COMPONENT_STALE')
        if last.evidence_class==FIXTURE and r.get('evidence_class')!=FIXTURE:
            raise ValueError('FIXTURE_HISTORY_CANNOT_SUPPORT_RETAINED_DECISION')
        for a,b in zip(self.observations,self.observations[1:]):
            _link(a,b)
        return [dict(time=z.time,received=z.received,btc=z.btc,brti=z.brti) for z in self.observations]


def _link(a,b):
    if a.identity()!=b.identity():raise ValueError('UNDERLYING_SOURCE_IDENTITY_CHANGED')
    if not 0<b.time-a.time<=15 or b.received<a.received:
        raise ValueError('UNDERLYING_HISTORY_DISCONTINUOUS_OR_OUT_OF_ORDER')
    if b.evidence_class!=PROXY:
        for key in ('btc','brti'):
            at=getattr(a,key+'_source_time');bt=getattr(b,key+'_source_time')
            ar=getattr(a,key+'_received_time');br=getattr(b,key+'_received_time')
            if bt<at or br<ar:raise ValueError('UNDERLYING_COMPONENT_OUT_OF_ORDER')
            if bt==at and (getattr(a,key)!=getattr(b,key) or ar!=br):
                raise ValueError('UNDERLYING_COMPONENT_PUBLICATION_CONFLICT')


class UnderlyingHistory:
    """Owns a bounded independent buffer. Invalid input fails closed until new data.

    Receipt-time ingestion never sorts, interpolates or rewrites clocks. A gap or
    source change starts a new segment, so120s context must genuinely rebuild.
    Contract rollover is not an underlying source change and never clears this buffer.
    """
    def __init__(self,*,allow_observation_proxy=False):
        self.allow_observation_proxy=allow_observation_proxy
        self._observations=[];self.error=None;self.clock=None;self.seen={}

    def invalidate(self,reason):
        self._observations=[];self.error=str(reason)

    def ingest(self,observation,now):
        try:
            if not isinstance(observation,Observation):raise ValueError('UNDERLYING_OBSERVATION_REQUIRED')
            if not finite(now) or self.clock is not None and now<self.clock:raise ValueError('UNDERLYING_INGEST_CLOCK_REVERSED')
            observation.validate(now,allow_observation_proxy=self.allow_observation_proxy)
            if now-observation.time>10:raise ValueError('UNDERLYING_STALE_AT_INGEST')
            identity=(observation.source_id,observation.source_epoch,observation.record_id)
            if identity in self.seen:
                if self.seen[identity]!=observation:raise ValueError('UNDERLYING_DUPLICATE_CONFLICT')
                self.clock=now;return False
            if self._observations:
                old=self._observations[-1]
                if observation.time<=old.time or observation.received<old.received:
                    raise ValueError('UNDERLYING_OUT_OF_ORDER')
                try:_link(old,observation)
                except ValueError as exc:
                    if str(exc) not in ('UNDERLYING_SOURCE_IDENTITY_CHANGED','UNDERLYING_HISTORY_DISCONTINUOUS_OR_OUT_OF_ORDER'):raise
                    self._observations=[]
            self._observations.append(observation)
            self._observations=[z for z in self._observations if z.time>=observation.time-135]
            self.seen={k:v for k,v in self.seen.items() if v.time>=observation.time-135}
            self.seen[identity]=observation;self.clock=now;self.error=None;return True
        except ValueError as exc:
            self.invalidate(exc);raise

    def snapshot(self):return Snapshot(tuple(self._observations),self.error)


def observed_proxy(r,*,source_id):
    """Read-only diagnostic projection. Keeps recorded clocks, missing native clocks.

    source_id identifies the manifest-pinned retained file, not a claimed feed ID.
    It must not be used as a native or fixture-to-empirical bridge.
    """
    if r.get('evidence_class') not in ('OBSERVATION_NO_NATIVE_RECEIPT','COMMON_OBSERVED_NO_NATIVE_RECEIPT'):
        raise ValueError('RETAINED_OBSERVATION_DOMAIN_REQUIRED')
    if r.get('healthy') is not True:
        raise ValueError('RETAINED_UNDERLYING_HEALTH_UNVERIFIED')
    return Observation(time=r['time'],received=r['received'],btc=r['btc'],brti=r['brti'],
        source_id=source_id,source_epoch=r['source_epoch'],record_id=r['publication_id'],evidence_class=PROXY)
