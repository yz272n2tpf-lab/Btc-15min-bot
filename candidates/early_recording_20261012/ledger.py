"""Offline association only: no labels, strategy transitions, fees or fills inferred."""
from .archive import canonical, sha, finite, SAFETY,source_events

RESEARCH_KINDS={'SETUP','CONFIRMATION','TICKET','CANCELLATION','EXPIRY'}


def protocol(*, size, reaction_seconds, reserve_cents, evidence_id):
    if not all(finite(x) and x>=0 for x in (size,reaction_seconds,reserve_cents)) or size<=0 or not evidence_id:
        raise ValueError('DECLARED_PROTOCOL_REQUIRED')
    return dict(size=size,size_units='contracts',reaction_seconds=reaction_seconds,
                reserve_cents=reserve_cents,assumption_evidence_id=evidence_id,
                hypothetical=True,fill_evidence=False,**SAFETY)


def fee_evidence(raw, endpoint, received_at, *, formula=None, rounding=None,
                 effective_from=None,effective_to=None,scope=None,authority_ref=None):
    if not isinstance(raw,bytes) or not finite(received_at):raise ValueError('FEE_PROVENANCE')
    supplied=dict(formula=formula,rounding=rounding,effective_from=effective_from,
                  effective_to=effective_to,scope=scope,authority_ref=authority_ref)
    missing=[k for k,v in supplied.items() if v is None]
    return dict(raw_sha256=sha(raw),endpoint=endpoint,received_at=received_at,
                evidence=supplied,missing=missing,applicability_verified=False,
                note='Caller assertions retained; no official applicability verification performed',**SAFETY)


def associate(events, native):
    """Keep every research event, including missing, cancelled and expired cases.

    Native entries must come from a verified detached archive and explicitly carry
    original contract/window/target/side/origin plus native event time and receipt.
    A display snapshot or consumer timestamp cannot create these associations.
    """
    out=[];seen=set()
    for e in events:
        if e.get('evidence_class') not in {'FIXTURE','NATIVE_RESEARCH_OBSERVATION'}:
            raise ValueError('EXPLICIT_RESEARCH_EVIDENCE_CLASS_REQUIRED')
        if e['kind'] not in RESEARCH_KINDS or not e.get('event_id') or e['event_id'] in seen:
            raise ValueError('RESEARCH_EVENT_IDENTITY')
        seen.add(e['event_id'])
        if not e.get('setup_id') or not finite(e['at']):raise ValueError('RESEARCH_SETUP_CLOCK')
        if e['side'] not in {'UP','DOWN'} or e['closed']-e['opened']!=900:raise ValueError('RESEARCH_CONTRACT')
        joins=[];missing=[]
        for n in native:
            if (n.get('evidence_class')=='FIXTURE') != (e['evidence_class']=='FIXTURE'):
                continue
            if n.get('kind') not in {'FINAL','MANAGEMENT','EXIT'}:continue
            identity=('contract','opened','closed','target','side','origin_id')
            if not e.get('origin_id') or not all(n.get(k)==e.get(k) for k in identity):continue
            ref=n.get('ref') or {}
            if not all(ref.get(k) is not None for k in ('snapshot_sha256','journal_id','sequence','record_sha256')):
                missing.append('NATIVE_ARCHIVE_REF_MISSING');continue
            if n.get('provenance')!='VERIFIED_DETACHED_NATIVE':
                missing.append('NATIVE_PROVENANCE_UNVERIFIED');continue
            if not (finite(n.get('source_ts')) and finite(n.get('received_ts')) and
                    e['opened']<=n['source_ts']<e['closed'] and n['source_ts']<=n['received_ts'] and
                    e.get('origin_at') is not None and e['origin_at']<=n['source_ts']):
                missing.append('NATIVE_CHRONOLOGY');continue
            joins.append(dict(kind=n['kind'],ref=ref,source_ts=n['source_ts'],received_ts=n['received_ts']))
        out.append(dict(schema='BTC15_CONTINUATION_ASSOCIATION_V1',research=e,
            evidence_class=e['evidence_class'],archive_authenticity_verified_here=False,
            research_sha256=sha(canonical(e)),native=joins,
            gaps=sorted(set(missing)) or ([] if joins else ['NO_EXACT_NATIVE_ASSOCIATION']),
            fill_evidence=False,**SAFETY))
    return out


def source_association(frame, records):
    """Exact native source/receipt join at the original decision, not latest state."""
    cut=frame['feature_cutoff'];b=frame['brti'];out={}
    requests=dict(BTC=(frame['btc_source'],frame['btc_received'],frame['btc_price'],None),
                  BRTI=(b['cf_ts'],b['delivery']['observed_ts'],b['value'],b['delivery']['owner_epoch']))
    for asset,(source,receipt,value,epoch) in requests.items():
        matches=[]
        for r in source_events(records):
            p=r['payload']
            if p['asset']!=asset or p['basis']!='ORIGINAL' or not p['accepted_by_owner']:continue
            if (p['source_ts'],p['receipt_ts'],p['value'])!=(source,receipt,value):continue
            if epoch is not None and p['epoch']!=epoch:continue
            if not source<=receipt<=p['available_at']<=cut:continue
            matches.append(dict(session=r['session'],sequence=r['sequence'],sha256=r['sha256']))
        out[asset]=dict(ref=matches[0] if len(matches)==1 else None,
                        missing=None if len(matches)==1 else 'MISSING_OR_AMBIGUOUS_EXACT_ORIGINAL_SOURCE')
    return dict(contract=frame['contract'],native_cut=cut,sources=out,**SAFETY)
