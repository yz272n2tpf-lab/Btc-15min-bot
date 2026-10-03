"""Normalize already-admitted MAIN/V8.1 events plus authoritative settlements.

This module never opens a capture archive. Callers must supply events returned by
capture2.qualification.admitted_events from closed QUALIFIED runs.
"""
from round2_capture_adapter import adapt_v81_scalp,adapt_protected,explicit_early_records,explicit_final_records,scalp_paths_for_entries

def _contract_from_state(p):
    s=p.get("state") or {}
    for k in ("contract","ticker"):
        if s.get(k):return s[k]
    for part in ("early","final"):
        x=s.get(part)
        if isinstance(x,dict) and (x.get("contract") or x.get("ticker")):return x.get("contract") or x.get("ticker")
    return None

def normalize(main_events,v81_events,qualification,settlements):
    """Return BTC15_ROUND2_NORMALIZED_V1. Missing evidence remains explicit."""
    protected=adapt_protected(main_events)
    early=explicit_early_records(protected);final=explicit_final_records(protected)
    entries=adapt_v81_scalp(v81_events)
    paths=scalp_paths_for_entries(entries,main_events+v81_events)
    contracts=set(settlements)
    contracts.update(x.get("contract") for x in entries if x.get("contract"))
    contracts.update(_contract_from_state(x) for x in protected if _contract_from_state(x))
    out=[]
    for contract in sorted(contracts):
        settlement=settlements.get(contract)
        if settlement is None: continue
        er=[x for x in early if x.get("contract") in (None,contract)]
        fr=[x for x in final if x.get("contract") in (None,contract)]
        se=[x for x in entries if x.get("contract")==contract]
        sp={x["entry_id"]:paths.get(x["entry_id"],[]) for x in se}
        out.append(dict(contract=contract,qualification=qualification,settlement=settlement,
                        early=er,final=fr,scalp_entries=se,scalp_paths=sp))
    return {"schema":"BTC15_ROUND2_NORMALIZED_V1","contracts":out}
