"""Execute the actual inline gate against stale-but-HTTP200 V8.1 responses."""
import ast
import json
from pathlib import Path
import subprocess
import unittest


class V81PublicationAge(unittest.TestCase):
    def test_actual_inline_script_rejects_stale_future_missing_and_wrong_ticker(self):
        tree=ast.parse(Path('BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py').read_text())
        n=next(n for n in tree.body if isinstance(n,ast.Assign)
               and any(isinstance(t,ast.Name) and t.id=='DIAG_JS' for t in n.targets))
        script=ast.literal_eval(n.value.func.value).replace('__V81_FEED__','https://example.invalid/state')
        script=script[script.index('>')+1:script.rindex('</script>')]
        harness=r'''
const vm=require('vm'),assert=require('assert');
const script=JSON.parse(require('fs').readFileSync(0,'utf8'));
async function check(age,ticker='KXBTC15M-TEST',manual=true){
 const now=Date.now(),els=new Map();
 const d={version:'V8.1_GRADUATED_30_45',entry_band:'30-45c',graduated:true,manual_execution_only:manual,order_action:null,owns_final_outcome:false,owns_early_opportunity:false,diagnostic_version:'V81_GATE_DIAG_V1',contract:ticker,active:true,status:'ACTIONABLE',side:'UP',route:'CORE',entry_price:.35,current_bid:.42,seconds_left:240,signal_age_sec:20,targets:{plus_5c:.4,plus_10c:.45,plus_20c:.55},generated_utc:age===null?undefined:new Date(now-age).toISOString()};
 const context={Date,Number,String,fetch:async()=>({ok:true,json:async()=>d}),setInterval:()=>0,usableFrame:()=>true,freshBrti:()=>true,window:{},document:{readyState:'complete',getElementById:id=>{if(!els.has(id))els.set(id,{textContent:'',classList:{add(){},remove(){}}});return els.get(id);}}};
 vm.runInNewContext(script,context);await new Promise(setImmediate);
 return context.window.renderV81ScalpInline({contract:'KXBTC15M-TEST'});
}
(async()=>{assert.strictEqual(await check(1000),true);for(const age of [600000,4000,-10000,null])assert.strictEqual(await check(age),false);assert.strictEqual(await check(1000,'OLD'),false);assert.strictEqual(await check(1000,'KXBTC15M-TEST',false),false);console.log('7 actual-script publication cases PASS');})().catch(e=>{console.error(e);process.exit(1);});
'''
        r=subprocess.run(['node','-e',harness],input=json.dumps(script),text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('7 actual-script publication cases PASS',r.stdout)


if __name__=='__main__':unittest.main()
