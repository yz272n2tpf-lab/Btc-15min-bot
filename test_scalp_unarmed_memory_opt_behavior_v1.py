#!/usr/bin/env python3
"""Deterministic unchanged-source cache test for scalp unarmed validator. NO NETWORK."""
import unittest
from unittest.mock import patch
import btc15_scalp_unarmed_live_tape_validator_v1 as v
class T(unittest.TestCase):
 def test_unchanged_source_skips_expensive_reanalysis(self):
  v._LAST_SOURCE_SHA="same";v._LAST_ANALYSIS_AT=1000.0
  v.STATE.clear();v.STATE.update({"ok":True,"orders":False,"sentinel":7})
  with patch.object(v.forward,"fetch_csv_raw",return_value=(b"record_type
","same")), patch.object(v.forward,"parse_csv_raw",side_effect=AssertionError("must not parse unchanged source")), patch.object(v.time,"time",return_value=1001.0), patch.object(v.forward,"build_summary",side_effect=AssertionError("must skip")), patch.object(v,"summarize",side_effect=AssertionError("must skip")):
   out=v.cycle()
  self.assertTrue(out["analysis_skipped_unchanged_source"]);self.assertEqual(out["sentinel"],7);self.assertFalse(out["orders"])
 def test_changed_source_parses_once_and_updates_fingerprint(self):
  v._LAST_SOURCE_SHA="old";v._LAST_ANALYSIS_AT=0.0
  rows=[{"record_type":"RESULT"}]
  fake={"ok":True,"orders":False,"baseline_completed_serial_opportunities":1}
  with patch.object(v.forward,"fetch_csv_raw",return_value=(b"new","newsha")), patch.object(v.forward,"parse_csv_raw",return_value=rows) as parse, patch.object(v.time,"time",return_value=2000.0), patch.object(v.forward,"poll_timer_status"), patch.object(v.forward,"build_summary",return_value={}), patch.object(v,"summarize",return_value=fake):
   out=v.cycle()
  parse.assert_called_once_with(b"new");self.assertEqual(v._LAST_SOURCE_SHA,"newsha");self.assertEqual(v._LAST_ANALYSIS_AT,2000.0);self.assertFalse(out["orders"])
if __name__=="__main__":unittest.main()
