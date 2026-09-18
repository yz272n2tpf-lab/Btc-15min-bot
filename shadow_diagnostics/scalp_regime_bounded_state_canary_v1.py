#!/usr/bin/env python3
"""Bounded-state Regime V1.1 canary scaffold.
READ ONLY | DESCRIPTIVE ONLY | NO ORDERS.
Phase A: incremental CSV state reduction; does not replace protected analyzer.
"""
from __future__ import annotations
import csv,io,json,os
from datetime import datetime,timezone
from typing import Any

VERSION="BTC15_REGIME_BOUNDED_STATE_CANARY_V1"
CUTOFF=datetime.fromisoformat(os.environ.get("SCALP_REGIME_FORWARD_CUTOFF_UTC","2026-09-16T11:03:16+00:00")).astimezone(timezone.utc)

# Raw rows are retained only for contracts whose first observed row is >= cutoff.
# This is conservative: it preserves exact downstream semantics while immediately
# dropping all pre-cutoff historical contracts from Python state.
class State:
    def __init__(self):
        self.header:list[str]=[]
        self.by_contract:dict[str,list[dict[str,str]]]={}
        self.first_seen:dict[str,datetime]={}
        self.max_left:dict[str,float]={}
        self.min_left:dict[str,float]={}
        self.rows_seen=0
        self.rows_retained=0
        self.orders=False\n        self.candidates:dict[str,dict[str,str]]={}\n        self.paths:dict[str,list[tuple[float,float,str]]]={}\n        self.results:set[str]=set()
    @staticmethod
    def dt(v:str)->datetime|None:
        try:
            x=datetime.fromisoformat((v or "").replace("Z","+00:00"))
            if x.tzinfo is None:x=x.replace(tzinfo=timezone.utc)
            return x.astimezone(timezone.utc)
        except Exception:return None
    @staticmethod
    def num(v:str)->float|None:
        try:return float(v)
        except Exception:return None
    def ingest_csv_bytes(self,raw:bytes)->None:
        # Phase-A parity scaffold accepts a complete newline-safe chunk.
        text=raw.decode("utf-8","replace")
        rdr=csv.DictReader(io.StringIO(text))
        if not self.header:self.header=list(rdr.fieldnames or [])
        for r in rdr:
            self.rows_seen+=1
            c=(r.get("contract") or "").strip()
            if not c:continue
            ts=self.dt(r.get("timestamp_utc") or "")
            if ts is None:continue
            first=self.first_seen.get(c)
            if first is None:
                self.first_seen[c]=ts;first=ts
            if first < CUTOFF:
                # Contract can never enter prospective denominator.
                self.by_contract.pop(c,None);continue
            self.by_contract.setdefault(c,[]).append(r);self.rows_retained+=1\n            typ=(r.get("record_type") or "").strip().upper(); cid=(r.get("candidate_id") or "").strip()\n            if typ=="CANDIDATE" and cid:\n                self.candidates[cid]=r\n            elif typ=="PATH" and cid:\n                e=self.num(r.get("elapsed_sec") or ""); g=self.num(r.get("exec_gain") or "")\n                if e is not None and g is not None:self.paths.setdefault(cid,[]).append((e,g,r.get("timestamp_utc") or ""))\n            elif typ=="RESULT" and cid:\n                self.results.add(cid)
            left=self.num(r.get("seconds_left") or "")
            if left is not None:
                self.max_left[c]=max(self.max_left.get(c,left),left)
                self.min_left[c]=min(self.min_left.get(c,left),left)
    def eligible_full_ids(self)->list[str]:
        return sorted(c for c in self.by_contract if self.max_left.get(c,-1)>=840 and self.min_left.get(c,9999)<=60)
    def stats(self)->dict[str,Any]:
        return {"version":VERSION,"cutoff_utc":CUTOFF.isoformat(),"rows_seen":self.rows_seen,
                "rows_retained":self.rows_retained,"contracts_retained":len(self.by_contract),
                "eligible_full_contracts":len(self.eligible_full_ids()),"candidate_count":len(self.candidates),\n                "path_candidate_count":len(self.paths),"result_count":len(self.results),"orders":False}

if __name__=="__main__":
    print(json.dumps({"version":VERSION,"status":"SCAFFOLD_ONLY","orders":False},separators=(",",":")))
