import unittest

import BTC15_DASHBOARD_V14_MOBILE_LAYOUT_AUDIT_V1 as a


class V14MobileLayoutAuditTests(unittest.TestCase):
    def minimal_good(self):
        unique = "".join(a.UNIQUE_ANCHORS)
        req = "".join(a.REQUIRED_SNIPPETS)
        phone = "".join((
            '@media(max-width:700px)',
            '#btcPrice{min-inline-size:8.2ch;}',
            '#timerRemaining{min-inline-size:5.2ch;}',
            '#finalActionSub{min-height:3em!important;height:3em!important;max-height:3em!important;line-height:1.5em!important;}',
            '#earlyEntry,#earlyFlow{min-height:3em;line-height:1.5em;}',
        ))
        return unique + req + phone

    def test_good_fixture_passes(self):
        r = a.audit_html(self.minimal_good())
        self.assertEqual(r["status"], "STATIC_MOBILE_PREFLIGHT_PASS")
        self.assertEqual(r["failed"], 0)
        self.assertTrue(r["human_visual_review_still_required"])

    def test_duplicate_timer_fails(self):
        text = self.minimal_good() + 'id="timerRemaining"'
        r = a.audit_html(text)
        self.assertEqual(r["status"], "STATIC_MOBILE_PREFLIGHT_FAIL")
        self.assertTrue(any(c["check"] == "single-canonical-visible-timer" and not c["pass"] for c in r["checks"]))

    def test_missing_viewport_fails(self):
        text = self.minimal_good().replace('name="viewport"', '')
        r = a.audit_html(text)
        self.assertGreater(r["failed"], 0)

    def test_missing_phone_override_fails(self):
        text = self.minimal_good().replace('#btcPrice{min-inline-size:8.2ch;}', '')
        r = a.audit_html(text)
        self.assertTrue(any(c["check"] == "phone-override-reserves-dynamic-space" and not c["pass"] for c in r["checks"]))

    def test_old_btc_yellow_mutation_fails(self):
        text = self.minimal_good() + "price.style.color=record&&!current?'var(--yellow)':'';"
        r = a.audit_html(text)
        self.assertGreater(r["failed"], 0)

    def test_numeric_flip_risk_surface_fails(self):
        r = a.audit_html(self.minimal_good() + "flip_risk_percent")
        self.assertGreater(r["failed"], 0)

    def test_duplicate_critical_card_anchor_fails(self):
        r = a.audit_html(self.minimal_good() + 'id="finalCard"')
        self.assertGreater(r["failed"], 0)

    def test_report_is_explicitly_non_promotional(self):
        r = a.audit_html(self.minimal_good())
        self.assertFalse(r["changes_signal_logic"])
        self.assertFalse(r["changes_thresholds"])
        self.assertFalse(r["orders"])
        self.assertEqual(r["device_review_targets"]["real_rollover"], "required before any V14 promotion")

    def test_generated_v14_integration(self):
        r = a.audit_generated_v14()
        self.assertEqual(r["status"], "STATIC_MOBILE_PREFLIGHT_PASS")
        self.assertEqual(r["failed"], 0)


if __name__ == "__main__":
    unittest.main()
