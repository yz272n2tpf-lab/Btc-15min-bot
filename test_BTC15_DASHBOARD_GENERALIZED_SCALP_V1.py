#!/usr/bin/env python3
import unittest

import BTC15_DASHBOARD_GENERALIZED_SCALP_V1 as m


class GeneralizedScalpDashboardPatchTests(unittest.TestCase):
    def test_feed_points_to_generalized_state_bridge(self):
        self.assertIn("scalp-move-shadow-v1-production.up.railway.app/state", m.FEED_URL)

    def test_payload_envelope_is_signal_only(self):
        js=m.INLINE_JS
        self.assertIn("GENERALIZED_SCALP_INTEGRATION_V3",js)
        self.assertIn("manual_execution_only!==true",js)
        self.assertIn("order_action!==null",js)
        self.assertIn("owns_final_outcome!==false",js)
        self.assertIn("owns_early_opportunity!==false",js)
        self.assertIn("numeric_flip_risk_validated!==false",js)

    def test_no_old_30_45_price_gate(self):
        js=m.INLINE_JS
        self.assertIn("entry<0||entry>1",js)
        self.assertNotIn("entry<0.30",js)
        self.assertNotIn("entry>0.45",js)
        self.assertIn("no price eligibility filter",js)

    def test_management_messages_present(self):
        js=m.INLINE_JS
        self.assertIn("EXIT / PROTECT PROFITS NOW",js)
        self.assertIn("management_message",js)
        self.assertIn("Frozen EXIT at 4¢ giveback after +5¢ arm",js)

    def test_poll_is_fast_enough_for_live_management_display(self):
        self.assertIn("setInterval(poll,500)",m.INLINE_JS)
        self.assertIn("Date.now()-lastOkMs)<=3000",m.INLINE_JS)

    def test_contract_sync_and_main_frame_fail_closed(self):
        js=m.INLINE_JS
        self.assertIn("d.contract!==main.contract",js)
        self.assertIn("usableFrame",js)

    def test_final_conflict_is_label_only(self):
        js=m.INLINE_JS
        self.assertIn("COUNTERTREND vs FINAL",js)
        self.assertNotIn("final_status=",js)
        self.assertNotIn("early_status=",js)

    def test_existing_scalp_card_is_only_ui_target(self):
        js=m.INLINE_JS
        for expected in [
            "scalpState","scalpEntry","scalpCurrentPrice","scalpLadderProtect","scalpLadderExit","scalpFlow"
        ]:
            self.assertIn(expected,js)
        self.assertNotIn("position:fixed",js)


if __name__=="__main__":
    unittest.main()
