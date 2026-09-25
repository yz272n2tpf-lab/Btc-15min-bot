#!/usr/bin/env python3
"""Combined off-path capture / two-clock seam checks. NO ORDERS."""
import ast, inspect, unittest
import btc15_information_native_offpath_candidate as native
import btc15_kalshi_quote_provenance_offpath_candidate as quote

class Seam(unittest.TestCase):
    def test_native_observer_is_append_only(self):
        src=inspect.getsource(native.instrument)
        self.assertIn(".body.append",src)
        self.assertNotIn("insert(",src)

    def test_native_offer_never_consumes_quote_owner(self):
        src=inspect.getsource(native.NativeExport)
        self.assertNotIn(".consume(",src)

    def test_quote_consume_never_serializes_or_writes(self):
        src=inspect.getsource(quote.Provider.consume)
        for forbidden in ("json.dumps","write_text","write_bytes",".replace("):
            self.assertNotIn(forbidden,src)

    def test_information_api_has_no_order_authority(self):
        import btc15_information_v1 as info
        self.assertTrue(all(x not in info.FIELDS for x in info.AUTHORITATIVE_FIELDS))

    def test_candidate_files_compile(self):
        for mod in (native,quote):
            ast.parse(inspect.getsource(mod))

    def test_installer_binds_offpath_native(self):
        import btc15_information_install_v1 as install
        src=inspect.getsource(install.assemble)
        self.assertIn("btc15_information_native_offpath_candidate.py",src)
        self.assertNotIn("ROOT/'btc15_information_native_v1.py'",src)

if __name__=="__main__":unittest.main()
