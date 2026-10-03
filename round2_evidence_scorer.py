"""Offline-only Round-2 evidence scorer. No live feeds, strategy evaluation, or orders."""
from collections import defaultdict

TARGETS=(8,10,15,20,30)

def truth(v): return str(v).strip().lower() in ("1","true","yes")

def require_admitted(q):
    if not isinstance(q,dict) or q.get("qualification_state")!="QUALIFIED" or q.get("scoring_admissible") is not True:
        raise ValueError("EVIDENCE_NOT_ADMITTED")

def settlement_side(s):
    if not isinstance(s,dict) or not truth(s.get("final60_complete")) or int(float(s.get("final60_count") or 0))!=60:
        raise ValueError("SETTLEMENT_INCOMPLETE")
    side=str(s.get("final60_side") or "").upper()
    if side not in ("UP","DOWN"): raise ValueError("SETTLEMENT_SIDE")
    return side

def first_early(rows):
    rows=sorted((r for r in rows if r.get("provisional_candidate") is True),key=lambda r:r["ts"])
    if not rows:return {"status":"PASS"}
    r=rows[0]; ask=float(r["ask"])
    return {"status":"QUALIFIED","origin_id":r["origin_id"],"ts":r["ts"],"side":r["side"],
            "ask":ask,"seconds_left":float(r["seconds_left"]),"le50":ask<=.50,
            "ideal25_35":.25<=ask<=.35}

def final_protection(rows,early):
    calls=sorted((r for r in rows if r.get("final_status")=="FINAL CALL"),key=lambda r:r["ts"])
    if not calls:return {"status":"PASS"}
    native=calls[0]
    linked=[r for r in calls if early.get("status")=="QUALIFIED" and r.get("early_origin_id")==early["origin_id"]]
    result={"status":"QUALIFIED","native":native,"linked_status":"LINKED" if linked else "UNLINKED"}
    if linked:
        p=linked[0];result["protection"]=p;result["delay_s"]=float(p["ts"])-float(early["ts"])
        if result["delay_s"]<0:raise ValueError("FINAL_BEFORE_EARLY")
    return result

def scalp_path(entry,path):
    side=entry["side"];ask=float(entry["entry_ask"]);ts=float(entry["ts"])
    obs=sorted((r for r in path if r["side"]==side and float(r["ts"])>=ts),key=lambda r:r["ts"])
    if not obs:return {"status":"MISSING"}
    profits=[float(r["bid"])-ask for r in obs]
    out={"status":"QUALIFIED","mfe_c":100*max(profits),"mae_c":100*min(profits),"targets":{}}
    stop=float(entry.get("stop_c",-10))/100
    stop_ts=next((float(r["ts"]) for r,p in zip(obs,profits) if p<=stop),None)
    for t in TARGETS:
        hit=next((float(r["ts"]) for r,p in zip(obs,profits) if p>=t/100),None)
        out["targets"][t]={"hit":hit is not None,"time_s":None if hit is None else hit-ts,
                           "stop_first":stop_ts is not None and (hit is None or stop_ts<hit)}
    return out

def score_contract(contract,qualification,settlement,early_rows,final_rows,scalp_entries,scalp_paths):
    require_admitted(qualification); official=settlement_side(settlement)
    early=first_early(early_rows);final=final_protection(final_rows,early)
    if early.get("status")=="QUALIFIED":early["correct"]=early["side"]==official
    if final.get("status")=="QUALIFIED":final["native_correct"]=final["native"]["side"]==official
    scalps=[]
    for e in sorted(scalp_entries,key=lambda r:r["ts"]):
        p=scalp_path(e,scalp_paths.get(e["entry_id"],[]));p["entry_id"]=e["entry_id"];p["side"]=e["side"]
        scalps.append(p)
    scalp_status="QUALIFIED" if scalps else "PASS"
    return {"contract":contract,"official_side":official,"early":early,"final":final,
            "scalp":{"status":scalp_status,"events":scalps}}

def union_summary(cards):
    out=defaultdict(int);out["contracts"]=len(cards)
    for c in cards:
        flags=[c["early"]["status"]=="QUALIFIED",c["final"]["status"]=="QUALIFIED",c["scalp"]["status"]=="QUALIFIED"]
        out["early"]+=flags[0];out["final"]+=flags[1];out["scalp"]+=flags[2];out["any"]+=any(flags);out["pass"]+=not any(flags)
    return dict(out)


def pct(n,d): return None if not d else 100.0*n/d

def scorecards(cards):
    """Descriptive common-universe reports; no selection or tuning."""
    n=len(cards)
    early=[c["early"] for c in cards if c["early"]["status"]=="QUALIFIED"]
    finals=[c["final"] for c in cards if c["final"]["status"]=="QUALIFIED"]
    linked=[f for f in finals if f.get("linked_status")=="LINKED"]
    scalps=[e for c in cards for e in c["scalp"]["events"] if e.get("status")=="QUALIFIED"]
    er_correct=sum(bool(e.get("correct")) for e in early)
    ideal=sum(bool(e.get("ideal25_35")) for e in early);le50=sum(bool(e.get("le50")) for e in early)
    fn_correct=sum(bool(f.get("native_correct")) for f in finals)
    targets={t:{"signals":len(scalps),"hit":sum(e["targets"][t]["hit"] for e in scalps),
                "stop_first":sum(e["targets"][t]["stop_first"] for e in scalps)} for t in TARGETS}
    return {
      "common_universe":{"contracts":n,**union_summary(cards)},
      "early":{"calls":len(early),"accuracy_pct":pct(er_correct,len(early)),"coverage_pct":pct(len(early),n),
               "le50":le50,"ideal25_35":ideal,
               "avg_ask":None if not early else sum(e["ask"] for e in early)/len(early),
               "avg_seconds_left":None if not early else sum(e["seconds_left"] for e in early)/len(early)},
      "final":{"native_calls":len(finals),"native_accuracy_pct":pct(fn_correct,len(finals)),
               "linked_protections":len(linked),"linked_pct_of_final":pct(len(linked),len(finals)),
               "avg_link_delay_s":None if not linked else sum(f["delay_s"] for f in linked)/len(linked)},
      "scalp":{"signals":len(scalps),
               "avg_mfe_c":None if not scalps else sum(e["mfe_c"] for e in scalps)/len(scalps),
               "avg_mae_c":None if not scalps else sum(e["mae_c"] for e in scalps)/len(scalps),
               "targets":targets}}


def contract_inventory(cards):
    """One row per admitted common-universe contract; never collapse missing into PASS."""
    rows=[]
    for c in cards:
        e,f,s=c["early"],c["final"],c["scalp"]
        linked=("NOT_APPLICABLE" if f["status"]!="QUALIFIED" else f.get("linked_status","UNLINKED"))
        states=[e["status"],f["status"],s["status"]]
        rows.append(dict(contract=c["contract"],official_side=c.get("official_side"),
            early_status=e["status"],final_status=f["status"],final_early_linkage=linked,
            scalp_status=s["status"],actionable=any(x=="QUALIFIED" for x in states),
            complete=all(x in ("QUALIFIED","PASS") for x in states),
            missing=[name for name,x in zip(("EARLY","FINAL","SCALP"),states) if x=="MISSING"]))
    return rows

def inventory_summary(rows):
    return dict(contracts=len(rows),complete=sum(r["complete"] for r in rows),
        incomplete=sum(not r["complete"] for r in rows),
        actionable=sum(r["actionable"] for r in rows),
        legitimate_pass=sum(r["complete"] and not r["actionable"] for r in rows),
        unlinked_final=sum(r["final_status"]=="QUALIFIED" and r["final_early_linkage"]=="UNLINKED" for r in rows),
        missing_early=sum("EARLY" in r["missing"] for r in rows),
        missing_final=sum("FINAL" in r["missing"] for r in rows),
        missing_scalp=sum("SCALP" in r["missing"] for r in rows))


def research_readiness(cards):
    """Precommitted descriptive readiness only; never selects or tunes strategy."""
    inv=contract_inventory(cards);summary=inventory_summary(inv);reports=scorecards(cards)
    blockers=[]
    if summary["incomplete"]:blockers.append("INCOMPLETE_COMMON_UNIVERSE")
    if summary["unlinked_final"]:blockers.append("FINAL_EARLY_LINKAGE_UNPROVEN")
    if reports["early"]["calls"]==0:blockers.append("NO_QUALIFIED_EARLY_CALLS")
    if reports["scalp"]["signals"]==0:blockers.append("NO_QUALIFIED_SCALP_SIGNALS")
    return {"descriptive_only":True,"strategy_selection_permitted":False,
            "inventory":summary,"blockers":blockers,
            "reportable":{"early":reports["early"],"final":reports["final"],"scalp":reports["scalp"]}}
