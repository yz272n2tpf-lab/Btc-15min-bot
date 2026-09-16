#!/usr/bin/env python3
import unittest

import scalp_event_schema_probe_v1 as s


class SchemaProbeTests(unittest.TestCase):
    def test_probe_reports_nonempty_fields_by_record_type(self):
        rows = [
            {"record_type":"CANDIDATE","contract":"A","btc30":"20","foo":""},
            {"record_type":"PATH","contract":"A","exec_gain":"0.1","foo":"x"},
            {"record_type":"RESULT","contract":"A","peak_gain":"0.2","foo":""},
        ]
        p = s.schema_probe(rows, ["btc30","exec_gain","missing"])
        self.assertEqual(p["record_counts"], {"CANDIDATE":1,"PATH":1,"RESULT":1})
        self.assertIn("btc30", p["by_record_type"]["CANDIDATE"]["nonempty_columns"])
        self.assertNotIn("exec_gain", p["by_record_type"]["CANDIDATE"]["nonempty_columns"])
        self.assertTrue(p["desired_feature_presence"]["btc30"]["nonempty_candidate"])
        self.assertFalse(p["desired_feature_presence"]["exec_gain"]["nonempty_candidate"])
        self.assertFalse(p["desired_feature_presence"]["missing"]["column_exists"])

    def test_probe_never_emits_row_values(self):
        secretish = "DO_NOT_EMIT_THIS_VALUE"
        rows = [{"record_type":"CANDIDATE","contract":"A","foo":secretish}]
        p = s.schema_probe(rows)
        self.assertNotIn(secretish, repr(p))
        self.assertIn("foo", p["columns"])


if __name__ == "__main__":
    unittest.main()
