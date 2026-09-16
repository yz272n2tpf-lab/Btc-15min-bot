#!/usr/bin/env python3
import inspect
import unittest
import BTC15_REVIEW_HUB_LIVE_V1 as h
import test_BTC15_FINAL_V4_FROZEN_REVIEW_REPORT_V1 as ffix
import test_BTC15_EARLY_V1_FROZEN_REVIEW_REPORT_V1 as efix

class ReviewHubTests(unittest.TestCase):
    def test_waiting_hub_is_safe(self):
        z=h.build_hub(ffix.payload(),efix.payload()); self.assertTrue(z["ok"]); self.assertFalse(z["review_ready"]["final"]); self.assertFalse(z["review_ready"]["early"]); self.assertIsNone(z["blended_accuracy"]); self.assertIsNone(z["union_coverage"]); self.assertFalse(z["orders"])
    def test_final_ready_does_not_make_early_ready(self):
        z=h.build_hub(ffix.payload(eligible=30,locks=16,settled=14,correct=14,sample_ready=True),efix.payload()); self.assertTrue(z["review_ready"]["final"]); self.assertFalse(z["review_ready"]["early"])
    def test_early_ready_does_not_make_final_ready(self):
        z=h.build_hub(ffix.payload(),efix.payload(eligible=30,calls=14,settled=12,same=10,sample_ready=True,asks_le50=14,ideal=6)); self.assertFalse(z["review_ready"]["final"]); self.assertTrue(z["review_ready"]["early"])
    def test_bad_final_integrity_does_not_rewrite_early(self):
        f=ffix.payload(); f["live"]["production_behavior_changed"]=True; z=h.build_hub(f,efix.payload()); self.assertFalse(z["ok"]); self.assertFalse(z["final"]["integrity"]["pass"]); self.assertTrue(z["early"]["integrity"]["pass"])
    def test_bad_early_integrity_does_not_rewrite_final(self):
        e=efix.payload(); e["live"]["price_filter_added"]=True; z=h.build_hub(ffix.payload(),e); self.assertFalse(z["ok"]); self.assertTrue(z["final"]["integrity"]["pass"]); self.assertFalse(z["early"]["integrity"]["pass"])
    def test_no_blended_accuracy_or_union(self):
        z=h.build_hub(ffix.payload(),efix.payload()); self.assertIsNone(z["blended_accuracy"]); self.assertIsNone(z["union_coverage"]); self.assertFalse(z["numeric_flip_risk_validated"])
    def test_network_is_get_only(self):
        src=inspect.getsource(h); self.assertIn("requests.get",src)
        for x in ("requests.post","requests.put","requests.patch","requests.delete"): self.assertNotIn(x,src)
    def test_exact_authoritative_sources(self):
        self.assertIn("final-forward-scorecard-v1-production.up.railway.app/state",h.FINAL_URL); self.assertIn("early-forward-scorecard-v1-production.up.railway.app/state",h.EARLY_URL)
    def test_render_labels_modules_separately(self):
        text=h.render_text(h.build_hub(ffix.payload(),efix.payload())); self.assertIn("FINAL V4 FROZEN REVIEW",text); self.assertIn("EARLY V1 FROZEN REVIEW",text); self.assertIn("SECONDARY, NOT FINAL ACCURACY",text); self.assertIn("No blended accuracy",text)
    def test_no_order_or_promotion_path(self):
        src=inspect.getsource(h)
        for x in ("place_order","create_order","submit_order","auto_promote_allowed=True","threshold_retune_allowed=True"): self.assertNotIn(x,src)
        self.assertIn("NO ORDERS",src)

if __name__=="__main__": unittest.main()
