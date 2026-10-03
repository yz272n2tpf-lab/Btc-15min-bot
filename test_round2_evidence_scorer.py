import unittest
from round2_evidence_scorer import *

Q={"qualification_state":"QUALIFIED","scoring_admissible":True}
S={"final60_complete":True,"final60_count":60,"final60_side":"UP"}

class Round2EvidenceTests(unittest.TestCase):
 def test_rejects_unqualified(self):
  with self.assertRaisesRegex(ValueError,"EVIDENCE_NOT_ADMITTED"):
   score_contract("C",{"qualification_state":"UNQUALIFIED","scoring_admissible":False},S,[],[],[],{})
 def test_rejects_incomplete_settlement(self):
  with self.assertRaisesRegex(ValueError,"SETTLEMENT_INCOMPLETE"):
   score_contract("C",Q,{"final60_complete":True,"final60_count":59,"final60_side":"UP"},[],[],[],{})
 def test_missing_is_not_pass_for_scalp_path(self):
  self.assertEqual(scalp_path({"side":"UP","entry_ask":.3,"ts":10},{"x":[]}.get("x",[]))["status"],"MISSING")
 def test_early_origin_and_economics(self):
  e=first_early([{"provisional_candidate":True,"origin_id":"b","ts":2,"side":"UP","ask":.31,"seconds_left":400},
                 {"provisional_candidate":True,"origin_id":"a","ts":1,"side":"UP","ask":.29,"seconds_left":410}])
  self.assertEqual(e["origin_id"],"a");self.assertTrue(e["le50"]);self.assertTrue(e["ideal25_35"])
 def test_final_requires_exact_origin_link(self):
  e={"status":"QUALIFIED","origin_id":"A","ts":10}
  f=final_protection([{"final_status":"FINAL CALL","ts":20,"side":"UP","early_origin_id":"B"}],e)
  self.assertEqual(f["linked_status"],"UNLINKED")
 def test_final_cannot_precede_early(self):
  e={"status":"QUALIFIED","origin_id":"A","ts":20}
  with self.assertRaisesRegex(ValueError,"FINAL_BEFORE_EARLY"):
   final_protection([{"final_status":"FINAL CALL","ts":10,"side":"UP","early_origin_id":"A"}],e)
 def test_scalp_stop_first_chronology(self):
  e={"entry_id":"x","side":"UP","entry_ask":.30,"ts":0,"stop_c":-10}
  p=scalp_path(e,[{"side":"UP","ts":1,"bid":.19},{"side":"UP","ts":2,"bid":.42}])
  self.assertTrue(p["targets"][10]["hit"]);self.assertTrue(p["targets"][10]["stop_first"])
 def test_no_future_before_entry(self):
  e={"entry_id":"x","side":"UP","entry_ask":.30,"ts":10}
  p=scalp_path(e,[{"side":"UP","ts":9,"bid":.90},{"side":"UP","ts":11,"bid":.31}])
  self.assertLess(p["mfe_c"],2)
 def test_common_union(self):
  cards=[{"early":{"status":"QUALIFIED"},"final":{"status":"PASS"},"scalp":{"status":"PASS"}},
         {"early":{"status":"PASS"},"final":{"status":"PASS"},"scalp":{"status":"QUALIFIED"}},
         {"early":{"status":"PASS"},"final":{"status":"PASS"},"scalp":{"status":"PASS"}}]
  s=union_summary(cards);self.assertEqual((s["contracts"],s["any"],s["pass"]),(3,2,1))

 def test_empty_scorecards_have_safe_denominators(self):
  r=scorecards([])
  self.assertEqual(r["common_universe"]["contracts"],0)
  self.assertIsNone(r["early"]["accuracy_pct"]);self.assertIsNone(r["early"]["coverage_pct"])
  self.assertIsNone(r["final"]["native_accuracy_pct"]);self.assertIsNone(r["scalp"]["avg_mfe_c"])
 def test_scorecards_keep_common_universe_denominator(self):
  cards=[{"early":{"status":"QUALIFIED","correct":True,"ask":.30,"seconds_left":360,"le50":True,"ideal25_35":True},"final":{"status":"QUALIFIED","native_correct":True,"linked_status":"LINKED","delay_s":30},"scalp":{"status":"PASS","events":[]}},{"early":{"status":"PASS"},"final":{"status":"PASS"},"scalp":{"status":"PASS","events":[]}}]
  r=scorecards(cards);self.assertEqual(r["early"]["coverage_pct"],50.0);self.assertEqual(r["early"]["accuracy_pct"],100.0);self.assertEqual(r["common_universe"]["pass"],1)
 def test_scalp_target_counts_preserve_stop_first(self):
  e={"status":"QUALIFIED","mfe_c":12,"mae_c":-11,"targets":{t:{"hit":t in (8,10),"time_s":2,"stop_first":t in (8,10)} for t in TARGETS}}
  cards=[{"early":{"status":"PASS"},"final":{"status":"PASS"},"scalp":{"status":"QUALIFIED","events":[e]}}]
  r=scorecards(cards);self.assertEqual(r["scalp"]["targets"][10]["hit"],1);self.assertEqual(r["scalp"]["targets"][10]["stop_first"],1)

 def test_inventory_missing_is_not_legitimate_pass(self):
  cards=[{"contract":"A","official_side":"UP","early":{"status":"MISSING"},"final":{"status":"PASS"},"scalp":{"status":"PASS","events":[]}},
         {"contract":"B","official_side":"DOWN","early":{"status":"PASS"},"final":{"status":"PASS"},"scalp":{"status":"PASS","events":[]}}]
  s=inventory_summary(contract_inventory(cards))
  self.assertEqual(s["complete"],1);self.assertEqual(s["incomplete"],1);self.assertEqual(s["legitimate_pass"],1);self.assertEqual(s["missing_early"],1)
 def test_inventory_unlinked_final_is_visible_but_complete(self):
  cards=[{"contract":"A","official_side":"UP","early":{"status":"PASS"},"final":{"status":"QUALIFIED","linked_status":"UNLINKED"},"scalp":{"status":"PASS","events":[]}}]
  r=contract_inventory(cards)[0];self.assertTrue(r["complete"]);self.assertEqual(r["final_early_linkage"],"UNLINKED")
  self.assertEqual(inventory_summary([r])["unlinked_final"],1)

 def test_readiness_never_authorizes_strategy_selection(self):
  cards=[{"contract":"A","official_side":"UP","early":{"status":"PASS"},"final":{"status":"QUALIFIED","linked_status":"UNLINKED","native_correct":True,"native":{"side":"UP"}},"scalp":{"status":"PASS","events":[]}}]
  r=research_readiness(cards);self.assertFalse(r["strategy_selection_permitted"])
  self.assertIn("FINAL_EARLY_LINKAGE_UNPROVEN",r["blockers"]);self.assertIn("NO_QUALIFIED_EARLY_CALLS",r["blockers"]);self.assertIn("NO_QUALIFIED_SCALP_SIGNALS",r["blockers"])
 def test_readiness_marks_incomplete_universe(self):
  cards=[{"contract":"A","official_side":"UP","early":{"status":"MISSING"},"final":{"status":"PASS"},"scalp":{"status":"PASS","events":[]}}]
  self.assertIn("INCOMPLETE_COMMON_UNIVERSE",research_readiness(cards)["blockers"])

if __name__=="__main__":unittest.main()
