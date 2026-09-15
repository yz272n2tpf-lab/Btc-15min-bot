#!/usr/bin/env python3
import unittest

import BTC15_SCALP_FROZEN_GATE_CONSTANTS_V1 as m


class FrozenGateConstantsTests(unittest.TestCase):
    def test_extracts_only_literal_requested_constants(self):
        source = """
BTC15_STRONG = 12.0
BRTI15_FLOOR = 3.0
OTHER = 99
MIN_ACCEL = 1 + unknown
"""
        out = m.extract(source)
        self.assertEqual(out["BTC15_STRONG"], 12.0)
        self.assertEqual(out["BRTI15_FLOOR"], 3.0)
        self.assertNotIn("OTHER", out)
        self.assertNotIn("MIN_ACCEL", out)

    def test_no_order_or_mutation_semantics_exist(self):
        with open(m.__file__, "r", encoding="utf-8") as fh:
            src = fh.read()
        self.assertNotIn("place_order", src)
        self.assertNotIn("create_order", src)
        self.assertNotIn("cancel_order", src)


if __name__ == "__main__":
    unittest.main()
