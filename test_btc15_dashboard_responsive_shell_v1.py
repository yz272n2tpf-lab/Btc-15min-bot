import re,unittest
from pathlib import Path

HTML=Path('mock/BTC15_DASHBOARD_SHELL_V1.html').read_text()

class ResponsiveDashboard(unittest.TestCase):
    def test_mobile_breakpoint_is_single_column(self):
        self.assertRegex(HTML,r'@media\(max-width:560px\).*?\.grid\{grid-template-columns:1fr\}',re.S)
    def test_ipad_breakpoint_is_two_column(self):
        self.assertRegex(HTML,r'@media\(min-width:768px\).*?grid-template-columns:repeat\(2,minmax\(0,1fr\)\)',re.S)
    def test_large_ipad_breakpoint_is_three_column(self):
        self.assertRegex(HTML,r'@media\(min-width:1024px\).*?grid-template-columns:repeat\(3,minmax\(0,1fr\)\)',re.S)
    def test_critical_states_and_safety_copy_exist(self):
        for text in ('WHAT TO DO NOW','DATA STALE','DO NOT USE','SIGNAL ONLY','NO ORDERS','5M CAUTION','3M GUARD','LOCK PROFIT'):
            self.assertIn(text,HTML)
    def test_touch_and_glance_readability_contract(self):
        self.assertIn('min-height:44px',HTML)
        self.assertIn('touch-action:manipulation',HTML)
        self.assertIn('overflow-wrap:anywhere',HTML)
        self.assertIn('.critical{font-size:22px',HTML)
    def test_viewport_meta_exists(self):
        self.assertIn('name="viewport"',HTML)

if __name__=='__main__':unittest.main()
