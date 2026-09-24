"""Exercise the real inline renderer against fresh publications of old prices."""
import ast
import json
from pathlib import Path
import subprocess
import unittest


class SourceProvenance(unittest.TestCase):
    def test_actual_renderer_rejects_unqualified_underlying_quotes_and_brti(self):
        tree=ast.parse(Path('BTC15_DASHBOARD_INLINE_SCALP_DIAG_V2.py').read_text())
        n=next(n for n in tree.body if isinstance(n,ast.Assign)and any(isinstance(t,ast.Name)and t.id=='DIAG_JS'for t in n.targets))
        script=ast.literal_eval(n.value.func.value).replace('__V81_FEED__','https://example.invalid/state')
        script=script[script.index('>')+1:script.rindex('</script>')]
        harness=r'''
const vm=require('vm'),assert=require('assert'),script=JSON.parse(require('fs').readFileSync(0,'utf8'));
const now=Date.parse('2026-09-23T21:22:43.719Z'),ticker='KXBTC15M-26SEP231730-30';
class Clock extends Date {static now(){return now;}}
async function check(change=()=>{}){
 const quote={ticker,epoch:'ws',market_id:'market',sid:1,sequence:3,source_ts_ms:now-200,validated_at_ms:now-100,transport:'timestamped_contiguous_ws',up_bid:.43,up_ask:.44,down_bid:.56,down_ask:.57};
 const p={schema:'V81_TIMESTAMPED_INPUTS_V1',ticker,target:84362.95,open_ts:Date.parse('2026-09-23T21:15:00Z')/1000,close_ts:Date.parse('2026-09-23T21:30:00Z')/1000,quote,brti:{source_ts_ms:now-2000,status:'PRIMARY_OK',clean_for_qualification:true,owner_epoch:'owner',value:84345.17},signal_only:true,orders:false};
 const d={version:'V8.1_GRADUATED_30_45',entry_band:'30-45c',graduated:true,manual_execution_only:true,order_action:null,owns_final_outcome:false,owns_early_opportunity:false,diagnostic_version:'V81_GATE_DIAG_V1',contract:ticker,active:true,status:'WATCH',side:'UP',route:'CORE',entry_price:.44,current_bid:.43,seconds_left:436.281,signal_age_sec:0,generated_utc:new Date(now-100).toISOString(),input_provenance:p,last_signal_event:{contract:ticker,side:'UP',entry_price:.44,signal_ts:now/1000-.1,entry_provenance:JSON.parse(JSON.stringify(p))}};
 change(d);const els=new Map();
 const c={Date:Clock,Number,String,fetch:async()=>({ok:true,json:async()=>d}),setInterval:()=>0,usableFrame:()=>true,freshBrti:()=>true,window:{},document:{readyState:'complete',getElementById:id=>{if(!els.has(id))els.set(id,{textContent:'',classList:{add(){},remove(){}}});return els.get(id);}}};
 vm.runInNewContext(script,c);await new Promise(setImmediate);
 return c.window.renderV81ScalpInline({contract:ticker,market:{target:84362.95}});
}
(async()=>{
 assert.strictEqual(await check(),true);
 const cases=[d=>delete d.input_provenance,d=>d.input_provenance.quote.transport='REST',d=>d.input_provenance.quote.source_ts_ms=now-6001,d=>d.input_provenance.quote.source_ts_ms=now+1,d=>d.input_provenance.brti.source_ts_ms=now-5001,d=>d.input_provenance.brti.source_ts_ms=now+1,d=>d.input_provenance.quote.ticker='OLD',d=>d.input_provenance.target=84362.96,d=>d.input_provenance.close_ts+=900,d=>d.current_bid=.39,d=>d.last_signal_event.entry_provenance.quote.up_ask=.40,d=>d.last_signal_event.signal_ts=now/1000-181];
 for(const change of cases)assert.strictEqual(await check(change),false);
 assert.strictEqual(await check(d=>{d.active=false;d.input_provenance=null;d.primary_wait_reason='TIMESTAMPED_QUOTES_UNAVAILABLE';}),true);
 console.log('14 actual-renderer source cases PASS');
})().catch(e=>{console.error(e);process.exit(1);});
'''
        r=subprocess.run(['node','-e',harness],input=json.dumps(script),text=True,capture_output=True)
        self.assertEqual(r.returncode,0,r.stdout+r.stderr)
        self.assertIn('14 actual-renderer source cases PASS',r.stdout)


if __name__=='__main__':unittest.main()
