#!/usr/bin/env python3
"""Functional denominator equivalence test for bounded Regime state."""
import importlib.util,pathlib
P=pathlib.Path(__file__).with_name("scalp_regime_bounded_state_canary_v1.py")
sp=importlib.util.spec_from_file_location("bs",P);m=importlib.util.module_from_spec(sp);sp.loader.exec_module(m)
raw=("record_type,contract,timestamp_utc,seconds_left,candidate_id\n"
"SNAPSHOT,old,2026-09-16T10:00:00+00:00,850,\n"
"SNAPSHOT,old,2026-09-16T10:14:00+00:00,50,\n"
"SNAPSHOT,newfull,2026-09-16T12:00:00+00:00,850,\n"
"PATH,newfull,2026-09-16T12:14:00+00:00,50,x\n"
"SNAPSHOT,newpartial,2026-09-16T12:30:00+00:00,850,\n").encode()
s=m.State();s.ingest_csv_bytes(raw)
assert s.eligible_full_ids()==["newfull"],s.eligible_full_ids()
assert "old" not in s.by_contract
assert "newpartial" in s.by_contract
assert s.stats()["orders"] is False
print("REGIME_BOUNDED_STATE_DENOMINATOR_OK")
