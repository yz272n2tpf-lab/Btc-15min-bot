#!/usr/bin/env python3
import unittest

from btc15_scalp_ui_transition_guard_v1 import validate_transition


def s(state, *, contract="C1", opp=1, completed=0, scan=False, fail_closed=False):
    return {
        "contract": contract,
        "display_state": state,
        "opportunity_index": opp,
        "serial_opportunities_completed": completed,
        "scanning_for_next": scan,
        "source": {"fail_closed": fail_closed},
    }


class ScalpUITransitionGuardV1Tests(unittest.TestCase):
    def test_normal_same_opportunity_progression(self):
        self.assertTrue(validate_transition(s("WAIT", opp=None), s("ACTIVE", opp=1)).allowed)
        self.assertTrue(validate_transition(s("ACTIVE"), s("PROTECT")).allowed)
        self.assertTrue(validate_transition(s("PROTECT"), s("EXIT")).allowed)

    def test_same_opportunity_regression_rejected(self):
        d = validate_transition(s("PROTECT"), s("ACTIVE"))
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "SAME_OPPORTUNITY_STATE_REGRESSION")

    def test_later_serial_opportunity_can_restart_active(self):
        d = validate_transition(
            s("EXIT", opp=1, completed=1),
            s("ACTIVE", opp=2, completed=1),
        )
        self.assertTrue(d.allowed)
        self.assertEqual(d.reason, "LATER_SERIAL_OPPORTUNITY")

    def test_scanning_wait_after_terminal_allowed(self):
        d = validate_transition(
            s("EXIT", opp=2, completed=2),
            s("WAIT", opp=None, completed=2, scan=True),
        )
        self.assertTrue(d.allowed)
        self.assertEqual(d.reason, "SCANNING_FOR_NEXT")

    def test_completed_count_cannot_go_backward(self):
        d = validate_transition(
            s("WAIT", opp=None, completed=3, scan=True),
            s("WAIT", opp=None, completed=2, scan=True),
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "SERIAL_COMPLETED_COUNT_REGRESSION")

    def test_opportunity_index_cannot_go_backward(self):
        d = validate_transition(
            s("ACTIVE", opp=3, completed=2),
            s("ACTIVE", opp=2, completed=2),
        )
        self.assertFalse(d.allowed)
        self.assertEqual(d.reason, "OPPORTUNITY_INDEX_REGRESSION")

    def test_contract_rollover_allows_reset(self):
        d = validate_transition(
            s("EXIT", contract="C1", opp=4, completed=4),
            s("WAIT", contract="C2", opp=None, completed=0),
        )
        self.assertTrue(d.allowed)
        self.assertEqual(d.reason, "CONTRACT_ROLLOVER")

    def test_fail_closed_wait_always_allowed(self):
        d = validate_transition(
            s("PROTECT", opp=2, completed=1),
            s("WAIT", opp=2, completed=1, fail_closed=True),
        )
        self.assertTrue(d.allowed)
        self.assertEqual(d.reason, "SOURCE_FAIL_CLOSED_WAIT_ALLOWED")

    def test_no_order_capability(self):
        d = validate_transition(None, s("WAIT", opp=None))
        self.assertTrue(d.manual_execution_only)
        self.assertFalse(d.orders)


if __name__ == "__main__":
    unittest.main()
