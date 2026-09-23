import unittest
from unittest.mock import Mock
from btc15_shadow_supervisor_v1 import ShadowChild

class Supervision(unittest.TestCase):
    def test_child_failure_backoff_recovery_and_shutdown(self):
        clock=Mock(return_value=100.)
        dead=Mock();dead.poll.return_value=1;dead.returncode=1
        healthy=Mock();healthy.poll.return_value=None
        spawn=Mock(side_effect=[dead,healthy])
        child=ShadowChild('telemetry.py',clock,spawn)
        child.maintain()
        self.assertEqual(spawn.call_count,1)
        clock.return_value=101;child.maintain();self.assertEqual(spawn.call_count,1)
        clock.return_value=102;child.maintain();self.assertEqual(spawn.call_count,2)
        clock.return_value=163;child.maintain();self.assertEqual(child.delay,2)
        child.stop();healthy.terminate.assert_called_once();healthy.wait.assert_called_once()
        clock.return_value=200;child.maintain();self.assertEqual(spawn.call_count,2)

    def test_shutdown_during_backoff_never_restarts(self):
        process=Mock();process.poll.return_value=1
        spawn=Mock(return_value=process);clock=Mock(return_value=100.)
        child=ShadowChild('telemetry.py',clock,spawn)
        child.maintain();child.stop();clock.return_value=1000;child.maintain()
        self.assertEqual(spawn.call_count,1)

if __name__=='__main__':unittest.main()
