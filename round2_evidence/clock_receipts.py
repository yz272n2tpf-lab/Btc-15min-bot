"""Authenticated certificate receiver, NOT a clock measurement implementation.
Accepts explicitly attested error/drift/read bounds; never estimates drift from
sample variance or creates source time from BRTI age. Uses unchanged Bound.
"""
from dataclasses import asdict
import hashlib,hmac,json
from btc15_external_clock_guard_v1 import Bound,micros
from btc15_directional_signal_authority_v1 import pack

class CertificateRegistry:
    def __init__(self,*,trusted_keys,domains,synthetic_only=True):
        self.keys=dict(trusted_keys);self.domains=dict(domains);self.synthetic_only=synthetic_only
        self.certs={};self.revoked=set();self.last_seq={}
    def ingest(self,packet,*,now_utc):
        body=packet['body'];signer=body['signer_id'];key=self.keys.get(signer)
        if type(key) is not bytes or len(key)<32:raise ValueError('UNTRUSTED_CLOCK_MONITOR')
        expected=hmac.new(key,pack(body).encode(),hashlib.sha256).hexdigest()
        if not isinstance(packet.get('mac'),str) or not hmac.compare_digest(expected,packet['mac']):raise ValueError('CLOCK_ATTESTATION')
        b=Bound(**body['bound']);domain=self.domains.get(b.clock_id)
        if not domain or domain['signer_id']!=signer or domain['runtime_epoch']!=body['runtime_epoch']:raise ValueError('CLOCK_DOMAIN_BINDING')
        if body.get('synthetic') is not self.synthetic_only:raise ValueError('CLOCK_MODE_CONFLICT')
        if not self.synthetic_only:raise ValueError('LIVE_CLOCK_PRODUCER_NOT_QUALIFIED')
        seq=body.get('monitor_sequence')
        if type(seq) is not int or seq<=self.last_seq.get(b.clock_id,0):raise ValueError('CLOCK_REPLAY')
        if body.get('state')!='HEALTHY' or body.get('step_detected') is not False or body.get('suspension_unknown') is not False:
            self.revoked.add((b.clock_id,b.epoch));raise ValueError('CLOCK_EPOCH_REVOKED')
        for premise in ('reference_identity','offset_bound_evidence','rate_bound_evidence','read_bound_evidence','epoch_continuity_evidence'):
            if not isinstance(body.get(premise),str) or not body[premise]:raise ValueError('CLOCK_PREMISE_MISSING:'+premise)
        if not micros(b.valid_from_utc)<=micros(b.reference_utc)<=micros(now_utc)<=micros(b.valid_until_utc):raise ValueError('CLOCK_CERTIFICATE_EXPIRED_OR_FUTURE')
        if (b.clock_id,b.epoch) in self.revoked:raise ValueError('CLOCK_EPOCH_REVOKED')
        b.witness(now_utc)
        if b.measurement_id in self.certs and self.certs[b.measurement_id]!=b:raise ValueError('CLOCK_CERTIFICATE_REWRITE')
        self.certs[b.measurement_id]=b;self.last_seq[b.clock_id]=seq
        return b
    def at(self,measurement_id,label):
        b=self.certs.get(measurement_id)
        if b is None or (b.clock_id,b.epoch) in self.revoked:raise ValueError('CLOCK_BOUND_UNAVAILABLE')
        b.witness(label);return b
    def revoke(self,clock_id,epoch):self.revoked.add((clock_id,epoch))
