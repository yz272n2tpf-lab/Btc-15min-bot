#!/usr/bin/env python3
import unittest

from btc15_dashboard_dom_probe_v1 import relevant_ids, relevant_functions


HTML='''<!doctype html><html><body>
<div id="finalReason">SECRET TEXT</div>
<div id="earlyState">VALUE</div>
<div id="scalpLadderExit">VALUE</div>
<div id="decorativeThing">IGNORE</div>
<script>
function applyState(d){}
function renderFinalCard(d){}
const renderTimer=()=>{};
function unrelatedHelper(){}
</script></body></html>'''


class DashboardDomProbeV1Tests(unittest.TestCase):
    def test_ids_only_no_values(self):
        text=' | '.join(relevant_ids(HTML))
        self.assertIn('div#finalReason',text)
        self.assertIn('div#earlyState',text)
        self.assertIn('div#scalpLadderExit',text)
        self.assertNotIn('SECRET TEXT',text)
        self.assertNotIn('decorativeThing',text)

    def test_render_function_names_only(self):
        x=relevant_functions(HTML)
        self.assertIn('applyState',x)
        self.assertIn('renderFinalCard',x)
        self.assertIn('renderTimer',x)
        self.assertNotIn('unrelatedHelper',x)


if __name__=='__main__':unittest.main()
