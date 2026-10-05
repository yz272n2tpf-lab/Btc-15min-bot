"""Run only local qualification; no production launch, source requests or deployment."""
import argparse
import os
import re
import json
from pathlib import Path
import subprocess
import sys

ROOT=Path(__file__).resolve().parents[2]
SUITE=['test_btc15_ladder_completion_v1','test_btc15_product_logic_v2','test_btc15_scalp_journal_v1',
       'test_directional_position_manager_v1','test_btc15_frozen_fair_production',
       'test_btc15_information_static','test_btc15_information_integration','test_btc15_information_v1',
       'test_btc15_v2_product_r1','test_btc15_v2_replay_regression','test_btc15_kalshi_quote_provenance_regressions',
       'test_btc15_brti_delivery_v1','test_btc15_decision_clock_v1','test_btc15_product_acceptance_r2',
       'test_btc15_read_only_revalidation']

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--lane',choices=['main','v81'],required=True)
    a=p.parse_args();out=ROOT/'qualification/v2_product_20261004';out.mkdir(parents=True,exist_ok=True)
    def run(args,log):
        with (out/log).open('w') as f:subprocess.run(args,cwd=ROOT,check=True,stdout=f,stderr=subprocess.STDOUT)
        if '-m' in args and 'unittest' in args:
            text=(out/log).read_text()
            if not re.search(r'Ran \d+ tests? in .*\n\nOK(?:\n|$)',text):raise RuntimeError('MISSING_COMPLETED_TEST_SUMMARY:'+log)
        print('PASS',log,flush=True)
    run([sys.executable,'btc15_v2_launch.py','--lane',a.lane,'--directory',str(out/'dashboard')],a.lane+'_release_verify.log')
    run([sys.executable,'-m','ops.v2_product.semantic_inventory','--lane',a.lane],a.lane+'_semantic_inventory.log')
    if a.lane=='v81':
        run([sys.executable,'-m','unittest','test_v81_product_source_r1','-v'],'v81_current_source_tests.log')
        return
    totals=[]
    for name in SUITE:
        log=name+'.log';run([sys.executable,'-m','unittest',name,'-v'],log)
        totals.append(dict(suite=name,tests=int(re.search(r'Ran (\d+) tests?',(out/log).read_text())[1]),status='PASS'))
    (out/'suite_completion_receipts.json').write_text(json.dumps(totals,indent=2)+'\n')
    run([sys.executable,'-m','unittest','discover','-s','ops/btc15_v2_scoring','-p','test_*.py','-v'],'scoring_tests.log')
    subprocess.run([sys.executable,'-m','ops.v2_product.ui_fixtures'],cwd=ROOT,check=True)
    run(['node','ops/v2_product/test_assembled_ui.cjs'],'assembled_ui_tests.log')
    subprocess.run([sys.executable,'-m','ops.v2_product.build_browser_fixture'],cwd=ROOT,check=True)
    run(['node','ops/v2_product/test_rendered_ui.cjs'],'rendered_ui_tests.log')
    run([sys.executable,'-m','ops.v2_product.check_live_fixture'],'assembled_continuity.log')
    print('Offline and rendered Chromium checks complete. Physical Safari and live acceptance are NOT established.')

if __name__=='__main__':main()
