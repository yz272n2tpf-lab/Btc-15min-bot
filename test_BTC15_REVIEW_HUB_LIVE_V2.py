#!/usr/bin/env python3
import inspect,unittest
import BTC15_REVIEW_HUB_LIVE_V2 as h
import test_BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1 as f
import test_BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1 as e
import test_BTC15_HANDOFF_V1_FROZEN_REVIEW_REPORT_V1 as a
import test_BTC15_EARLY_EXCURSION_V1_FROZEN_REVIEW_REPORT_V1 as x
class HubV2Tests(unittest.TestCase):
    def z(self):return h.build_hub(f.payload(),e.payload(),a.payload(),x.payload())
    def test_all_four_lanes_integrity(self):
        z=self.z();self.assertTrue(z["ok"]);self.assertEqual(set(z["review_ready"]),{"final","early","handoff","excursion"})
    def test_union_comes_only_from_handoff(self):
        z=self.z();self.assertEqual(z["system"]["union_coverage"],z["handoff"]["common_universe"]["any_signal_coverage"]);self.assertEqual(z["system"]["union_source"],"HANDOFF_COMMON_UNIVERSE_ONLY");self.assertIsNone(z["system"]["blended_accuracy"])
    def test_standalone_early_final_never_create_union(self):
        z=h.build_hub(f.payload(eligible=30,locks=30,settled=20,correct=20,sample_ready=True),e.payload(eligible=30,calls=30,settled=20,same=20,sample_ready=True,asks_le50=30,ideal=10),a.payload(),x.payload());self.assertAlmostEqual(z["system"]["union_coverage"],13/21);self.assertFalse(z["system"]["union_coverage_certified"])
    def test_handoff_ready_controls_union_certification(self):
        z=h.build_hub(f.payload(),e.payload(),a.payload(eligible=30,early=14,final=27,both=11,settled=16,sample_ready=True),x.payload());self.assertTrue(z["system"]["union_coverage_certified"]);self.assertTrue(z["review_ready"]["handoff"])
    def test_excursion_move_metric_not_accuracy(self):
        z=self.z();self.assertFalse(z["excursion"]["excursion"]["metric_is_final_accuracy"]);self.assertFalse(z["excursion"]["excursion"]["checkpoints_are_qualification_rules"])
    def test_one_bad_lane_fails_hub_but_preserves_other_reports(self):
        bad=a.payload();bad["live"]["any_signal_coverage"]=.99;z=h.build_hub(f.payload(),e.payload(),bad,x.payload());self.assertFalse(z["ok"]);self.assertTrue(z["final"]["integrity"]["pass"]);self.assertTrue(z["early"]["integrity"]["pass"]);self.assertFalse(z["handoff"]["integrity"]["pass"])
    def test_private_internal_sources_for_nonpublic_collectors(self):
        self.assertEqual(h.HANDOFF_URL,"http://early-final-handoff-v1.railway.internal:8080/state");self.assertEqual(h.EXCURSION_URL,"http://early-excursion-forward-v1.railway.internal:8080/state")
    def test_network_get_only(self):
        src=inspect.getsource(h);self.assertIn("requests.get",src)
        for q in ("requests.post","requests.put","requests.patch","requests.delete"):self.assertNotIn(q,src)
    def test_numeric_flip_and_promotion_absent(self):
        z=self.z();self.assertIsNone(z["numeric_flip_risk"]);self.assertFalse(z["auto_promote_allowed"]);self.assertFalse(z["threshold_retune_allowed"]);self.assertFalse(z["orders"])
    def test_render_separates_all_roles(self):
        text=h.render_text(self.z());self.assertIn("FINAL V4 FROZEN REVIEW",text);self.assertIn("EARLY V1 FROZEN REVIEW",text);self.assertIn("HANDOFF V1 FROZEN REVIEW",text);self.assertIn("EARLY EXCURSION V1 FROZEN REVIEW",text);self.assertIn("HANDOFF COMMON UNIVERSE ONLY",text);self.assertIn("numeric Flip Risk hidden",text)
if __name__=="__main__":unittest.main()
