import unittest
from round2_capture_adapter import *

class AdapterTests(unittest.TestCase):
 def test_v81_signal_requires_original_executable_ask(self):
  e={"kind":"LIFECYCLE_EMISSION","body":{"emission":{"schema":"BTC15_V81_PASSIVE_EMISSION_V1","event_type":"STATE_PUBLICATION","phase":"SIGNAL","evidence_origin_id":"E","upstream_native_origin_id":None,"original_signal_event":{"contract":"C","side":"UP","signal_ts":10,"entry_provenance":{"quote":{"up_ask":.31}}}}}}
  r=adapt_v81_scalp([e]);self.assertEqual(len(r),1);self.assertEqual(r[0]["entry_ask"],.31)
 def test_v81_evaluation_cannot_manufacture_entry(self):
  e={"kind":"LIFECYCLE_EMISSION","body":{"emission":{"schema":"BTC15_V81_PASSIVE_EMISSION_V1","event_type":"EVALUATION","phase":"COMPLETE","row":{"ticker":"C"}}}}
  self.assertEqual(adapt_v81_scalp([e]),[])
 def test_protected_eligibility_is_not_accepted_early(self):
  e={"kind":"PROTECTED_GENERATION","body":{"generation_id":"G","eligible_opportunity_id":"G","accepted_origin_id":None,"state":{"early":{"ready":True,"side":"UP","entry_ask":.30,"origin_ts":10}}}}
  p=adapt_protected([e]);self.assertEqual(explicit_early_records(p),[])
 def test_early_requires_explicit_accepted_origin(self):
  e={"kind":"PROTECTED_GENERATION","body":{"generation_id":"G","accepted_origin_id":"A","state":{"early":{"ready":True,"side":"UP","entry_ask":.30,"origin_ts":10,"seconds_left":360}}}}
  r=explicit_early_records(adapt_protected([e]));self.assertEqual(r[0]["origin_id"],"A")
 def test_final_does_not_infer_early_link(self):
  e={"kind":"PROTECTED_GENERATION","body":{"state":{"final":{"status":"FINAL CALL","side":"UP","origin_ts":20}}}}
  r=explicit_final_records(adapt_protected([e]));self.assertIsNone(r[0]["early_origin_id"])

if __name__=="__main__":unittest.main()
