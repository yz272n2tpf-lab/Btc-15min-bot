#!/usr/bin/env python3
"""One-shot heavy scalp research worker. RESEARCH ONLY | NO ORDERS."""
import json,sys
import btc15_scalp_unarmed_live_tape_validator_v1 as v
def main():
 rows,sha=v.forward.fetch_csv_rows();v.forward.poll_timer_status();fwd=v.forward.build_summary(rows,sha);s=v.summarize(rows,sha,fwd)
 compact=dict(s)
 for k in ("ended_unarmed_records","armed_no_validated_exit_records","recovered_handoffs","prearm_reset_failed_primary_candidate_ids","blueprint_review_items"):compact.pop(k,None)
 compact["orders"]=False;compact["research_only"]=True
 json.dump(compact,sys.stdout,separators=(",",":"));sys.stdout.write("\n")
if __name__=="__main__":main()
