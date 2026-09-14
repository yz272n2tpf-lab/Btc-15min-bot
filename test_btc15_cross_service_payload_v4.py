#!/usr/bin/env python3
import unittest

from btc15_cross_service_payload_v4 import compose_cross_service_payload

MAIN = {
    "contract":"KXBTC15M-T",
    "timer":{"seconds_left":300.0,"minutes_left":5.0},
    "market":{
        "target":78000.0,
        "up_bid":.62,"up_ask":.63,
        "down_bid":.37,"down_ask":.38,
    },
    "early":{
        "ready":True,"side":"UP","ask":.34,"bid":.33,
        "fair":.79,"edge":.45,"status":"QUALIFIED","source":"PROTECTED",
    },
    "final":{
        "ready":True,"side":"UP","confidence":.94,"source":"PROTECTED",
        "recorded_final_call":False,"recorded_side":None,"recorded_confidence":None,
    },
}


def scalp(**kw):
    d={
        "version":"GENERALIZED_SCALP_INTEGRATION_V4",
        "contract":"KXBTC15M-T",
        "state":"ACTIVE","side":"DOWN",
        "entry_price":.40,"current_bid":.43,
        "exec_gain":.03,"peak_exec_gain":.03,
        "entry_seconds_left":420,"contract_seconds_left":298.5,
        "management_message":"SCALP ACTIVE · BUILDING",
        "source_fresh":True,"source_event_age_sec":1.0,
        "integration_ready":True,"manual_execution_only":True,
        "order_action":None,
    }
    d.update(kw)
    return d


class CrossServicePayloadV4Tests(unittest.TestCase):
    def test_nested_main_maps_real_timer_and_protected_modules(self):
        x=compose_cross_service_payload(MAIN,scalp()).to_dict()
        self.assertAlmostEqual(x["canonical_seconds_left"],300.0)
        self.assertAlmostEqual(x["scalp_timer_delta_sec"],1.5)
        self.assertEqual(x["early"]["state"],"QUALIFIED")
        self.assertEqual(x["final"]["state"],"LOCK")
        self.assertEqual(x["scalp"]["state"],"ACTIVE")
        self.assertIn("COUNTERTREND_SCALP",x["context_labels"])

    def test_stale_scalp_does_not_suppress_protected_main(self):
        x=compose_cross_service_payload(
            MAIN,
            scalp(source_fresh=False,integration_ready=False,source_event_age_sec=31,
                  integration_block_reason="SCALP SOURCE STALE"),
        ).to_dict()
        self.assertEqual(x["early"]["state"],"QUALIFIED")
        self.assertEqual(x["final"]["state"],"LOCK")
        self.assertEqual(x["scalp"]["state"],"PASS")
        self.assertEqual(x["scalp_management_message"],"SCALP WAIT · STALE SOURCE")

    def test_contract_mismatch_fails_scalp_closed(self):
        x=compose_cross_service_payload(MAIN,scalp(contract="OTHER")).to_dict()
        self.assertEqual(x["scalp"]["state"],"PASS")
        self.assertFalse(x["scalp_contract_aligned"])
        self.assertEqual(x["scalp_block_reason"],"CONTRACT_MISMATCH")

    def test_recorded_final_call_remains_locked(self):
        f=dict(MAIN["final"],ready=False,side="DOWN",confidence=.55,
               recorded_final_call=True,recorded_side="UP",recorded_confidence=.94)
        x=compose_cross_service_payload(dict(MAIN,final=f),scalp()).to_dict()
        self.assertEqual(x["final"]["state"],"LOCK")
        self.assertEqual(x["final"]["side"],"UP")

    def test_signal_only(self):
        x=compose_cross_service_payload(MAIN,scalp()).to_dict()
        self.assertTrue(x["manual_execution_only"])
        self.assertIsNone(x["order_action"])
        self.assertFalse(x["numeric_flip_risk_validated"])
        self.assertNotIn("flip_risk_percent",x)


if __name__=="__main__":
    unittest.main()
