"""Guard EARLY cockpit presentation without changing the independent SCALP lane."""
from pathlib import Path
import unittest

PANEL = Path(__file__).parent/'btc15_v2_product'/'panel.js'


class CockpitDirectionalDisplay(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.source=PANEL.read_text(encoding='utf-8')

    def test_early_visible_actions_are_only_buy_watch_exit(self):
        source=self.source
        self.assertIn("const visibleEarly=x=>",source)
        self.assertIn("x==='HOLD'||x==='WATCH'||x==='PROTECT'?'WATCH'",source)
        self.assertIn("const displayState=o?visibleEarly(e.guidance)",source)
        self.assertIn("pill('earlyState',displayState)",source)

    def test_early_and_final_protect_not_displayed_as_action(self):
        source=self.source
        self.assertIn("WATCH — Could Flip · review directional evidence",source)
        self.assertIn("WATCH — Could Flip · support lost or opposed",source)
        self.assertNotIn("'PROTECT · review exposure at current bid'",source)
        self.assertNotIn("'PROTECT · support lost or opposed'",source)

    def test_final_exit_uses_actual_terminal_and_no_fill_assumption(self):
        self.assertIn("m?.terminal?.state==='EXIT'",self.source)
        self.assertIn("EXIT recommended · manual closure unconfirmed",self.source)

    def test_scalp_display_is_not_remapped_to_early(self):
        self.assertIn("text('scalpLadderProtect'",self.source)
        self.assertIn("text('scalpLadderExit'",self.source)
        self.assertIn("s.guidance==='EXIT'",self.source)


if __name__=='__main__':
    unittest.main()
