#!/usr/bin/env python3
"""Offline Round-2 report entry point. Reads normalized admitted evidence only."""
import argparse,json
from pathlib import Path
from round2_evidence_scorer import score_contract,scorecards,contract_inventory,inventory_summary

def load(path):
    v=json.loads(Path(path).read_text())
    if v.get("schema")!="BTC15_ROUND2_NORMALIZED_V1":raise ValueError("NORMALIZED_SCHEMA")
    return v

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("normalized_json")
    ap.add_argument("--output")
    a=ap.parse_args();v=load(a.normalized_json);cards=[]
    for c in v.get("contracts",[]):
        cards.append(score_contract(c["contract"],c["qualification"],c["settlement"],
            c.get("early",[]),c.get("final",[]),c.get("scalp_entries",[]),c.get("scalp_paths",{})))
    inv=contract_inventory(cards)
    report={"schema":"BTC15_ROUND2_REPORT_V1","source_schema":v["schema"],
            "scorecards":scorecards(cards),"inventory_summary":inventory_summary(inv),"contracts":inv}
    raw=json.dumps(report,indent=2,sort_keys=True)
    if a.output:Path(a.output).write_text(raw+"\n")
    print(raw)
if __name__=="__main__":main()
