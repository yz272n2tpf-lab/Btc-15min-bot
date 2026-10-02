"""Fail-closed adapter from admitted passive events to Round-2 scorer records.

No raw archive access, strategy evaluation, inferred origins, or orders.
"""
def _body(e):
    b=e.get("body")
    if not isinstance(b,dict): raise ValueError("EVENT_BODY")
    return b

def _emission(e):
    b=_body(e); x=b.get("emission")
    return x if isinstance(x,dict) else None

def adapt_v81_scalp(events):
    out=[]
    for e in events:
        if e.get("kind")!="LIFECYCLE_EMISSION": continue
        x=_emission(e)
        if not isinstance(x,dict) or x.get("schema")!="BTC15_V81_PASSIVE_EMISSION_V1": continue
        if x.get("event_type")!="STATE_PUBLICATION" or x.get("phase")!="SIGNAL": continue
        original=x.get("original_signal_event")
        if not isinstance(original,dict): continue
        side=str(original.get("side") or "").upper()
        quote=(original.get("entry_provenance") or {}).get("quote") if isinstance(original.get("entry_provenance"),dict) else None
        ask=None if not isinstance(quote,dict) else quote.get(side.lower()+"_ask")
        if side not in ("UP","DOWN") or ask is None or x.get("evidence_origin_id") is None: continue
        ts=original.get("signal_ts")
        if ts is None: continue
        out.append(dict(entry_id=x["evidence_origin_id"],contract=original.get("contract"),side=side,
                        ts=ts,entry_ask=float(ask),source="V81_ORIGINAL_SIGNAL_EVENT",
                        upstream_native_origin_id=x.get("upstream_native_origin_id")))
    return out

def adapt_protected(events):
    """Expose protected observations without inventing accepted EARLY/FINAL origins."""
    out=[]
    for e in events:
        if e.get("kind") not in ("PROTECTED_GENERATION","PROTECTED_FILE_WRITE_COMPLETED"): continue
        b=_body(e);state=b.get("state")
        if not isinstance(state,dict): continue
        early=state.get("early") if isinstance(state.get("early"),dict) else {}
        out.append(dict(kind=e["kind"],generation_id=b.get("generation_id"),
                        eligible_opportunity_id=b.get("eligible_opportunity_id"),
                        early_ready=early.get("ready"),accepted_origin_id=b.get("accepted_origin_id"),
                        upstream_final_origin_id=b.get("upstream_final_origin_id"),
                        state=state))
    return out

def explicit_early_records(protected):
    """Only explicit accepted origin is scoreable; eligibility alone is not an entry."""
    rows=[]
    for p in protected:
        oid=p.get("accepted_origin_id")
        if not oid: continue
        s=p["state"]; early=s.get("early") if isinstance(s.get("early"),dict) else {}
        side=str(early.get("side") or "").upper();ask=early.get("entry_ask");ts=early.get("origin_ts")
        if side not in ("UP","DOWN") or ask is None or ts is None: continue
        rows.append(dict(provisional_candidate=True,origin_id=oid,ts=ts,side=side,ask=float(ask),
                         seconds_left=float(early["seconds_left"]) if early.get("seconds_left") is not None else 0))
    return rows

def explicit_final_records(protected):
    """No chronological inference: linkage requires an explicit upstream EARLY origin."""
    rows=[]
    for p in protected:
        s=p["state"]; final=s.get("final") if isinstance(s.get("final"),dict) else {}
        if final.get("status")!="FINAL CALL": continue
        side=str(final.get("side") or "").upper();ts=final.get("origin_ts")
        if side not in ("UP","DOWN") or ts is None: continue
        rows.append(dict(final_status="FINAL CALL",ts=ts,side=side,
                         early_origin_id=final.get("early_origin_id")))
    return rows


def quote_bid_observations(events):
    """Executable best bids after original book acceptance; no fill inference."""
    out=[]
    for e in events:
        if e.get("kind")!="LIFECYCLE_EMISSION": continue
        x=_emission(e)
        if not isinstance(x,dict) or x.get("schema")!="BTC15_QUOTE_APPLIED_V1" or x.get("valid") is not True: continue
        bids=x.get("best_bids")
        if not isinstance(bids,dict): continue
        ts=x.get("exchange_ts_ms")
        if ts is None: continue
        for key,side in (("yes","UP"),("no","DOWN")):
            level=bids.get(key)
            if not isinstance(level,dict) or level.get("price") is None: continue
            try: bid=float(level["price"])
            except (TypeError,ValueError): continue
            out.append(dict(contract=x.get("ticker"),side=side,ts=float(ts)/1000.0,bid=bid,
                            sequence=x.get("sequence"),source="KALSHI_QUOTE_APPLIED"))
    return out

def scalp_paths_for_entries(entries, quote_events):
    """Join only same-contract/same-side quotes at-or-after signal timestamp."""
    quotes=quote_bid_observations(quote_events);out={}
    for e in entries:
        rows=[q for q in quotes if q["contract"]==e.get("contract") and q["side"]==e.get("side") and q["ts"]>=float(e["ts"])]
        rows.sort(key=lambda r:(r["ts"],r.get("sequence") or -1));out[e["entry_id"]]=rows
    return out
