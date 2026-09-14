#!/usr/bin/env python3
import unittest

from btc15_main_state_schema_probe_v1 import schema_paths


class MainStateSchemaProbeTests(unittest.TestCase):
    def test_reports_keys_and_types_without_values(self):
        obj = {
            "contract": "SECRET-LIKE-VALUE",
            "market": {"remaining_sec": 321.5, "nested": {"ready": True}},
            "items": [{"side": "UP", "price": .42}],
        }
        p = schema_paths(obj)
        text = " | ".join(p)
        self.assertIn("contract:string", text)
        self.assertIn("market:object", text)
        self.assertIn("market.remaining_sec:number", text)
        self.assertIn("market.nested.ready:bool", text)
        self.assertIn("items:array", text)
        self.assertNotIn("SECRET-LIKE-VALUE", text)
        self.assertNotIn("321.5", text)
        self.assertNotIn("0.42", text)

    def test_depth_limit(self):
        obj = {"a": {"b": {"c": {"d": 1}}}}
        p = schema_paths(obj, max_depth=2)
        self.assertIn("a.b:object", p)
        self.assertNotIn("a.b.c:object", p)

    def test_path_limit(self):
        obj = {str(i): i for i in range(20)}
        self.assertEqual(len(schema_paths(obj, max_paths=5)), 5)


if __name__ == "__main__":
    unittest.main()
