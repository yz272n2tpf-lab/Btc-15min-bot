#!/usr/bin/env python3
"""Deterministic unchanged-source cache test for scalp unarmed validator. NO NETWORK."""
import unittest
from unittest.mock import patch
import btc15_scalp_unarmed_live_tape_validator_v1 as v
class T(unittest.TestCase):
 def test_unchanged_source_skips_expensive_reanalysis(self):
  v._LAST_SOURCE_SHA="same";v._LAST_ANALYSIS_AT=1000.0
  v.STATE.clear();v.STATE.update({"ok":True,"orders":False,"sentinel":7})
  with patch.object(v.forward,"fetch_csv_raw",return_value=(b"record_type\\n","same")), patch.object(v.forward,"parse_csv_raw",side_effect=AssertionError("must not parse unchanged source")), patch.object(v.time,"time",return_value=1001.0), patch.object(v.forward,"build_summary",side_effect=AssertionError("must skip")), patch.object(v,"summarize",side_effect=AssertionError("must skip")):
   out=v.cycle()
  self.assertTrue(out["analysis_skipped_unchanged_source"]);self.assertEqual(out["sentinel"],7);self.assertFalse(out["orders"])
 def test_changed_source_parses_once_and_updates_fingerprint(self):
  v._LAST_SOURCE_SHA="old";v._LAST_ANALYSIS_AT=0.0
  rows=[{"record_type":"RESULT"}]
  fake={"ok":True,"orders":False,"baseline_completed_serial_opportunities":1,"projected_completed_serial_opportunities":1,"projected_additional_serial_opportunities":0,"ended_unarmed_n":0,"armed_no_validated_exit_n":0,"armed_no_validated_exit_preserved_blocking":True,"armed_no_validated_exit_reclassified_as_ended_unarmed_n":0,"post_unarmed_later_completed_n":0,"post_unarmed_later_plus10_n":0,"completed_meaningful_10c_candidates":0,"selected_meaningful_10c":0,"blocked_prearm_meaningful_10c":0,"true_post_exit_missed_meaningful_10c":0,"lifecycle_reset_review_ready":True,"tightening_development_nominee_btc30_min":None,"tightening_holdout_review_ready":False,"tightening_holdout_supports_nominee":False,"tightening_development_baseline":{},"tightening_development_nominee":None,"tightening_holdout_baseline":{},"tightening_holdout_nominee":None,"tightening_decision":"NO_DEVELOPMENT_NOMINEE","prearm_reset_completed_primary_n":0,"prearm_reset_failed_primary_n":0,"prearm_reset_grid":{},"protection_audit":{},"forward_audit":{},"blueprint_review_blockers":[]}
  with patch.object(v.forward,"fetch_csv_raw",return_value=(b"new","newsha")), patch.object(v.forward,"parse_csv_raw",return_value=rows) as parse, patch.object(v.time,"time",return_value=2000.0), patch.object(v.forward,"poll_timer_status"), patch.object(v.forward,"build_summary",return_value={}), patch.object(v,"summarize",return_value=fake):
   out=v.cycle()
  parse.assert_called_once_with(b"new");self.assertEqual(v._LAST_SOURCE_SHA,"newsha");self.assertEqual(v._LAST_ANALYSIS_AT,2000.0);self.assertFalse(out["orders"])
if __name__=="__main__":unittest.main()
