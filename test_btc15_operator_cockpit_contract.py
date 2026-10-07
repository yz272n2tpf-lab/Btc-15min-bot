"""Strict acceptance for the BTC15 operator cockpit presentation.

Tests the approved visible contract, not legacy dashboard assembly success.
"""
from pathlib import Path
import re
import unittest
import btc15_operator_cockpit_launch as cockpit

class OperatorCockpitContract(unittest.TestCase):
    def setUp(self):
        import tempfile
        self.tmp=tempfile.TemporaryDirectory()
        self.root=Path(self.tmp.name)
        self.d=cockpit.assemble(self.root)
        self.html=(self.d/"BTC_Kalshi_App_Live_v13.html").read_text()
    def tearDown(self): self.tmp.cleanup()

    def test_required_action_surfaces_and_scalp_ladder_exist(self):
        # The live V2 owner still has all explicit SCALP fields; presentation must not
        # hide the scalp card or any of its five operator ladder rows.
        for token in ["scalpEntry","scalpLadderEntry","scalpLadderHold","scalpLadderWatch","scalpLadderProtect","scalpLadderExit"]:
            self.assertIn(token,self.html)
        self.assertNotRegex(self.html,r"#scalp(?:Entry|LadderEntry|LadderHold|LadderWatch|LadderProtect|LadderExit)[^{]*\{[^}]*display\s*:\s*none")

    def test_final_management_ladder_is_not_operator_visible(self):
        for token in ["#finalBuyZone","#finalHoldZone","#finalWatchZone","#finalProtectZone","#finalExitZone"]:
            self.assertIn(token,self.html)

    def test_lower_contract_is_single_health_single_context_details(self):
        self.assertIn("BOT HEALTH",self.html)
        self.assertIn("MARKET CONTEXT",self.html)
        self.assertIn(">DETAILS<",self.html.replace(" ",""))
        self.assertIn("#flipRisk,#flipRiskSub,#evidenceScore",self.html)

    def test_rejected_preview_regressions_are_guarded(self):
        # Preview #1 failed physical acceptance on these exact points.
        self.assertIn("Never hide a legacy parent card by inference",self.html)
        self.assertIn("plainFinal()",self.html)
        self.assertIn("cleanEarlyLanguage()",self.html)
        self.assertIn("cleanBotHealth()",self.html)
        self.assertIn("stripLegacyLowerChrome()",self.html)
        self.assertIn("oppositeTitle",self.html)
        self.assertIn("indicator-row",self.html)

    def test_signal_only_boundary(self):
        import json
        m=json.loads((self.d/"manifest.json").read_text())
        self.assertTrue(m["signal_only"]);self.assertFalse(m["orders"])
        self.assertEqual(m["operator_cockpit"],cockpit.MARKER)

if __name__=="__main__": unittest.main()
