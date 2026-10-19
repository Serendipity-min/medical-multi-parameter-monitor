"""硬件命令门禁及公开证据脱敏回归；不打开串口、不复位或发送任何实板命令。"""
import importlib.util
from pathlib import Path
import unittest
from unittest.mock import Mock

spec = importlib.util.spec_from_file_location('capture_uart', Path(__file__).resolve().parents[1] / 'bench/capture_uart.py')
capture = importlib.util.module_from_spec(spec)
spec.loader.exec_module(capture)


class CaptureTests(unittest.TestCase):
    def setUp(self):
        self.idle = {'fault': '0', 'BOFF': '0', 'armed': '0', 'A': '0', 'NMT_TXOK': '0'}
        self.ready = dict(self.idle, armed='1', A='1', NMT_TXOK='1')

    def test_start_requires_fresh_unarmed_diagnostics(self):
        self.assertTrue(capture.command_allowed('S', self.idle, 1))
        self.assertFalse(capture.command_allowed('S', self.idle, 4))
        self.assertFalse(capture.command_allowed('S', self.ready, 1))
        self.assertFalse(capture.command_allowed('S', {}, 1))

    def test_fault_and_busoff_block_all_commands(self):
        for field in ('fault', 'BOFF'):
            for command in ('S', 'T'):
                with self.subTest(field=field, command=command):
                    self.assertFalse(capture.command_allowed(command, dict(self.ready, **{field: '1'}), 1))

    def test_test_time_requires_real_ack_and_online_a(self):
        self.assertTrue(capture.command_allowed('T', self.ready, 1))
        for state in (self.idle, dict(self.ready, NMT_TXOK='0'), dict(self.ready, A='0')):
            self.assertFalse(capture.command_allowed('T', state, 1))

    def test_no_restart_or_multi_byte_control(self):
        for command in ('G', 'SS', 'ST', '', 'RESET'):
            self.assertFalse(capture.command_allowed(command, self.ready, 1))

    def test_sample_payload_redacted_but_metadata_preserved(self):
        for ident in ('181', '381'):
            line = f'RX id={ident} n=12 first=1 last=20 dt_min=19 data=0102030405060708'
            safe = capture.public_line(line)
            self.assertIn(f'id={ident} n=12 first=1 last=20 dt_min=19', safe)
            self.assertNotIn('0102030405060708', safe)
        quality = 'RX id=681 n=2 data=9301000001000000'
        self.assertEqual(capture.public_line(quality), quality)

    def test_mirror_sample_redaction_preserves_tick(self):
        line = 'MIRROR epoch=1800000000 values=10,20,30,40 wave=12345/900 Q=00000000'
        safe = capture.public_line(line)
        self.assertNotIn('10,20,30,40', safe)
        self.assertNotIn('12345', safe)
        self.assertIn('wave=REDACTED_SAMPLE/900', safe)

    def test_public_status_does_not_mutate_live_state(self):
        live = {'rx': {'181': {'data': '01020304', 'n': '2'}},
                'mirror': {'values': '10,20,30,40', 'wave': '12345/900'},
                'latest': self.ready}
        safe = capture.public_status(live)
        self.assertEqual(live['rx']['181']['data'], '01020304')
        self.assertEqual(safe['rx']['181']['data'], 'REDACTED_SAMPLE_PAYLOAD')
        self.assertEqual(safe['mirror']['wave'], 'REDACTED_SAMPLE/900')
        self.assertEqual(safe['latest'], self.ready)

    def test_busy_status_reader_does_not_abort_capture(self):
        path = Mock()
        temp = path.with_suffix.return_value
        temp.replace.side_effect = [PermissionError('sharing violation'), None]
        status = {'latest': self.ready}
        self.assertFalse(capture.publish_status(path, status))
        self.assertEqual(status['status_publish_busy'], 1)
        self.assertTrue(capture.publish_status(path, status))

    def test_cold_boot_controls_are_explicit_and_fault_gated(self):
        self.assertTrue(capture.command_allowed('P', self.ready, 1))
        self.assertFalse(capture.command_allowed('G', self.ready, 1))
        paused = dict(self.ready, paused='1', A='0')
        self.assertTrue(capture.command_allowed('G', paused, 1))
        self.assertFalse(capture.command_allowed('T', paused, 1))
        self.assertFalse(capture.command_allowed('P', paused, 1))
        self.assertTrue(capture.command_allowed('D', self.ready, 1))
        for command in ('G', 'P', 'D'):
            self.assertFalse(capture.command_allowed(command, dict(paused, fault='6'), 1))

    def test_report_tracker_distinguishes_line_and_report_gaps(self):
        tracker = capture.ReportTracker()
        # 附着时的半份报告不算丢行；有BEGIN声明后才可判定缺失。
        tracker.feed('BENCH ms=1 rs=4 rl=2')
        tracker.feed('DIAG_END seq=4 lines=2')
        tracker.feed('DIAG_BEGIN seq=5 expected=2')
        tracker.feed('BENCH ms=1 rs=5 rl=1')
        tracker.feed('RXQ hw_fovr=0 rs=5 rl=2')
        tracker.feed('DIAG_END seq=5 lines=2')
        self.assertEqual(tracker.snapshot()['complete_reports'], 1)
        tracker.feed('DIAG_BEGIN seq=7 expected=2')
        tracker.feed('BENCH ms=1 rs=7 rl=1')
        tracker.feed('BENCH ms=1 rs=7 rl=1')
        tracker.feed('DIAG_END seq=7 lines=2')
        result = tracker.snapshot()
        self.assertEqual(result['missing_reports'], 1)
        self.assertEqual(result['missing_lines'], 1)
        self.assertEqual(result['duplicate_lines'], 1)
        self.assertEqual(result['incomplete_reports'], 1)

    def test_report_tracker_keeps_loss_across_real_device_boot_marker(self):
        tracker = capture.ReportTracker()
        tracker.feed('DIAG_BEGIN seq=10 expected=2')
        tracker.feed('BENCH ms=1 rs=10 rl=1')
        tracker.feed('DIAG_BEGIN seq=11 expected=2')
        self.assertEqual(tracker.snapshot()['missing_lines'], 1)
        tracker.feed('CAN_ONLY_BENCH OFFLINE_NO_CONFIG')
        tracker.feed('DIAG_BEGIN seq=1 expected=1')
        tracker.feed('BENCH ms=1 rs=1 rl=1')
        tracker.feed('DIAG_END seq=1 lines=1')
        self.assertEqual(tracker.snapshot()['missing_lines'], 1)
        self.assertEqual(tracker.snapshot()['device_boot_markers'], 1)


if __name__ == '__main__':
    unittest.main()
