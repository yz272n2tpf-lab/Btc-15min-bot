import unittest
from round2_normalize import normalize

Q={"qualification_state":"QUALIFIED","scoring_admissible":True}
S={"final60_complete":True,"final60_count":60,"final60_side":"UP"}
def sig(c="C",ts=10):
 return {"kind":"LIFECYCLE_EMISSION","body":{"emission":{"schema":"BTC15_V81_PASSIVE_EMISSION_V1","event_type":"STATE_PUBLICATION","phase":"SIGNAL","evidence_origin_id":"E","upstream_native_origin_id":None,"original_signal_event":{"contract":c,"side":"UP","signal_ts":ts,"entry_provenance":{"quote":{"up_ask":.30}}}}}}
def quote(c="C",ts=11):
 return {"kind":"LIFECYCLE_EMISSION","body":{"emission":{"schema":"BTC15_QUOTE_APPLIED_V1","ticker":c,"valid":True,"exchange_ts_ms":ts*1000,"sequence":1,"best_bids":{"yes":{"price":"0.42"}}}}}

class NormalizeTests(unittest.TestCase):
 def test_joins_signal_to_same_contract_quote_path(self):
  v=normalize([], [sig(),quote()],Q,{"C":S});c=v["contracts"][0]
  self.assertEqual(c["scalp_entries"][0]["entry_id"],"E");self.assertEqual(c["scalp_paths"]["E"][0]["bid"],.42)
 def test_settlement_universe_retains_contract_with_no_events(self):
  v=normalize([],[],Q,{"C":S});self.assertEqual(v["contracts"][0]["contract"],"C")
 def test_missing_settlement_is_not_normalized(self):
  v=normalize([], [sig()],Q,{});self.assertEqual(v["contracts"],[])
 def test_cross_contract_quote_cannot_enter_path(self):
  v=normalize([], [sig("C"),quote("D")],Q,{"C":S,"D":S})
  c=next(x for x in v["contracts"] if x["contract"]=="C");self.assertEqual(c["scalp_paths"]["E"],[])

if __name__=="__main__":unittest.main()
