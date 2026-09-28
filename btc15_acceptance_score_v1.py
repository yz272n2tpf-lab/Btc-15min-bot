"""Read-only PR40 acceptance scorer CLI. No network, no orders, no writes."""
import argparse, json
from btc15_cohort_evidence_v1 import score_native_contract

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--journal", required=True)
    p.add_argument("--ticker", required=True)
    p.add_argument("--target", required=True, type=float)
    a=p.parse_args()
    print(json.dumps(score_native_contract(a.journal,a.ticker,a.target),sort_keys=True,default=str))

if __name__=="__main__":
    main()
