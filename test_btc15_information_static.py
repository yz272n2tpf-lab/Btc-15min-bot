"""Static boundary gates plus actual JavaScript render-time expiry."""
import ast
import hashlib
import json
from pathlib import Path
import subprocess
import unittest

ROOT=Path(__file__).resolve().parent


class InformationStaticTests(unittest.TestCase):
    def test_pure_evaluator_never_loads_action_loop_or_shadow_lifecycle(self):
        source=(ROOT/'btc15_information_v1.py').read_text()
        for forbidden in ('FrozenRuntime','PhaseProjection','PhaseLatchProjection','profit_namespace',
                          '_update_profit_shadow','log_unified_subminute','maybe_create_event',
                          '_maybe_true_scalp_signal','append_csv','requests.', 'urlopen'):
            self.assertNotIn(forbidden,source)
        self.assertIn("n.name == '_fair_build_snapshot'",source)

    def test_export_has_no_source_write_or_additional_upstream_reads(self):
        tree=ast.parse((ROOT/'btc15_information_native_v1.py').read_text())
        cls=next(n for n in tree.body if isinstance(n,ast.ClassDef) and n.name=='NativeExport')
        attrs={n.func.attr for n in ast.walk(cls) if isinstance(n,ast.Call) and isinstance(n.func,ast.Attribute)}
        self.assertFalse(attrs & {'consume','accept','remember','select','save_state','to_csv','write_text',
                                 'write_bytes','fit','predict_proba','urlopen'})
        self.assertIn('blocking=False',ast.unparse(cls))

    def test_original_production_entrypoints_remain_byte_identical(self):
        # Compare repository-pinned baseline blobs without executing any runtime.
        names=['bot_two_output_build_v4_13_profit_protection_shadow.py','btc15_brti_delivery_v1.py',
               'btc15_kalshi_quote_provenance_v1.py','BTC15_INSTALL_LIVE_DASHBOARD_V13.py',
               'btc15_run_with_rescue_v2_shadow_v1.py','btc15_final_position_protection_shadow_v3.py',
               'btc15_run_full_validation_v1.py','railway.json']
        for name in names:
            frozen=subprocess.check_output(['git','show','3e552065e34a0a402bc3ca4598b57dff1f1c6e77:'+name],cwd=ROOT)
            self.assertEqual((ROOT/name).read_bytes(),frozen,name)

    def test_opt_in_launcher_and_loopback_only_separate_route(self):
        native=(ROOT/'btc15_information_native_v1.py').read_text()
        service=(ROOT/'btc15_information_service_v1.py').read_text()
        self.assertIn("os.getenv('BTC15_ENABLE_INFORMATION_EXPORT') != '1'",native)
        self.assertIn("HTTPServer(('127.0.0.1', port)",native)
        self.assertIn("HTTPServer(('127.0.0.1', port)",service)
        self.assertNotIn('Access-Control-Allow-Origin',service)
        self.assertNotIn('kalshi_subminute_unified',service)

    def test_browser_expires_information_and_never_updates_native_fields(self):
        program=r'''
const assert = require('node:assert/strict');
const {captureInformation,informationView,twoClockView} = require('./btc15_information_view_v1.js');
const native = Object.freeze({timestamp:100, early_ready:true, position_status:'NOT_LINKED',
    shadow_only:true, shadow_protection_used_as_action:false});
const p = Object.freeze({schema:'BTC15_INFORMATION_V1', authority:'INFORMATIONAL_READ_ONLY',
    status:'AVAILABLE',orders:false,signal_only:true,checked_ts:102,display_until:103,
    expires_at:104,brti_source_ts:99,probability_up:.9,early_ready:true,exit:'EXIT'});
const token=captureInformation(p,1000,1200);
let view=twoClockView(native,token,1500);
assert.equal(view.authoritative,native);
assert.equal(view.information.status,'AVAILABLE');
assert.equal(view.information.assessment.early_ready,undefined);
assert.equal(view.information.assessment.exit,undefined);
for(const t of [1100,2000,3000,4000,NaN]) {
  view=twoClockView(native,token,t);
  assert.equal(view.authoritative,native);
  assert.equal(view.information.status,'WAIT');
  assert.equal(view.information.assessment,null);
}
assert.equal(informationView(captureInformation({...p,authority:'AUTHORITATIVE_ACTION_STATE'},1000,1200),1200).status,'WAIT');
assert.equal(informationView(captureInformation(p,1000,2200),2200).status,'WAIT'); // slow network
assert.equal(informationView(JSON.parse(JSON.stringify(token)),1500).status,'WAIT'); // old-page token
assert.equal(informationView(token,1500).status,'AVAILABLE'); // no Date.now / UTC-clock assumption
assert.equal(informationView(captureInformation(null,1000,1200),1500).status,'WAIT');
assert.equal(informationView(captureInformation({...p,brti_source_ts:103},1000,1200),1500).status,'WAIT');
console.log('render expiry, whitelist, native identity PASS');
'''
        output=subprocess.check_output(['node','-e',program],cwd=ROOT,text=True)
        self.assertIn('PASS',output)


if __name__=='__main__':unittest.main()
