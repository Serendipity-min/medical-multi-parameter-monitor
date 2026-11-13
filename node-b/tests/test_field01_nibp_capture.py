"""血压实收入口定向回归；不连接设备、Broker或服务器。"""
import io
import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from field01_ad_window import ManualNIBPWindow, FiveDiagnosticWindow, read_completed_nibp, five_nodes_online, check_five_diagnostic


def wire_row(timestamp=100001, *, retain=False, node='NODE-E', value=None):
    payload = dict(timestamp=timestamp, seq=1, session_id='synthetic-test-e', validity='VALID',
                   source='MOCK', synthetic=True, unit='mmHg', value=[113.0, 72.0] if value is None else value)
    return json.dumps(dict(topic=f'mpm/v1/GW-B5-001/{node}/telemetry/nibp', retain=retain,
                           arrival_unix_ns=100100000000, payload_hex=json.dumps(payload).encode().hex())) + '\n'


class CompletedNIBP(unittest.TestCase):
    def test_only_new_e_result_qualifies(self):
        wire = io.StringIO(wire_row(retain=True) + wire_row(timestamp=99999)
                           + wire_row(node='NODE-A') + wire_row())
        result = read_completed_nibp(wire, 100000)
        self.assertEqual(result['message']['node_id'], 'NODE-E')
        self.assertEqual(result['message']['value'], [113.0, 72.0])
        self.assertEqual(result['message']['timestamp'], 100001)
        self.assertIsNone(read_completed_nibp(wire, 100000))

    def test_partial_writer_line_is_revisited(self):
        row = wire_row()
        wire = io.StringIO(row[:-1])
        self.assertIsNone(read_completed_nibp(wire, 100000))
        self.assertEqual(wire.tell(), 0)
        wire.seek(0, 2)
        wire.write('\n')
        wire.seek(0)
        self.assertEqual(read_completed_nibp(wire, 100000)['message']['seq'], 1)

    def test_bad_nibp_value_uses_real_model_rejection(self):
        with self.assertRaises(ValueError):
            read_completed_nibp(io.StringIO(wire_row(value=[113.0])), 100000)


class ManualWaiting(unittest.TestCase):
    def test_field_first_start_near_124_seconds_is_not_cut_at_125(self):
        # 重放首次实板的计时位置；后续完成时刻仅为明确的离线夹具。
        window = ManualNIBPWindow(0, 20)
        window.observed_start(20 + 123.906)
        window.check(20 + 125.140)
        window.observed_result(200)
        self.assertEqual(window.end, 295)
        self.assertLess(window.end + 15, 420)

    def test_start_wait_and_completion_wait_are_separate(self):
        window = ManualNIBPWindow(0, 20)
        self.assertEqual(window.start_deadline, 170)
        window.observed_start(169)
        self.assertEqual(window.completion_deadline, 289)
        window.check(288.9)
        with self.assertRaisesRegex(TimeoutError, '120S_AFTER_START'):
            window.check(289)

    def test_no_start_has_a_finite_operator_deadline(self):
        window = ManualNIBPWindow(0, 20)
        window.check(169.9)
        with self.assertRaisesRegex(TimeoutError, 'NO_E_MANUAL_START'):
            window.check(170)

    def test_repeated_measuring_status_does_not_extend_deadline(self):
        window = ManualNIBPWindow(0, 20)
        window.observed_start(30)
        window.observed_start(100)
        self.assertEqual(window.completion_deadline, 150)

    def test_slow_network_does_not_inflate_device_hard_limit(self):
        with self.assertRaisesRegex(TimeoutError, 'INSUFFICIENT_HARD_BUDGET'):
            ManualNIBPWindow(0, 160)
        window = ManualNIBPWindow(0, 100)
        self.assertEqual(window.start_deadline, 180)
        window.observed_start(179)
        window.observed_result(299)
        self.assertEqual(window.end, 394)
        self.assertLess(window.end + 15, 420)

    def test_expiry_observation_is_not_silently_truncated(self):
        window = ManualNIBPWindow(0, 20)
        with self.assertRaisesRegex(TimeoutError, '90S_EXPIRY_OBSERVATION'):
            window.observed_result(301)


class FiveBoardDiagnostic(unittest.TestCase):
    def test_warmup_and_evaluation_fit_existing_420_seconds(self):
        window = FiveDiagnosticWindow(0, 50)
        self.assertEqual(window.evaluation_start, 95)
        self.assertEqual(window.end, 395)
        self.assertLess(window.end + 15, 420)
        with self.assertRaisesRegex(TimeoutError, '420S_BUDGET'):
            FiveDiagnosticWindow(0, 50.1)

    def test_all_four_sources_required_not_three_node_profile(self):
        snapshot = dict(gateway_id='GW-B5-001', node_profile='five', gateway_state='ONLINE',
                        nodes={f'NODE-{n}': 'ONLINE' for n in 'ABDE'})
        self.assertTrue(five_nodes_online(snapshot))
        snapshot['nodes']['NODE-D'] = 'OFFLINE'
        self.assertFalse(five_nodes_online(snapshot))
        snapshot['nodes']['NODE-D'] = 'ONLINE'
        snapshot['node_profile'] = 'three'
        self.assertFalse(five_nodes_online(snapshot))

    def test_source_emcy_and_wrong_bus_stop_the_diagnostic(self):
        check_five_diagnostic('FIVE RX node=4 bus=1 emcy=0 code=0')
        with self.assertRaisesRegex(ValueError, 'SOURCE_EMCY'):
            check_five_diagnostic('FIVE RX node=1 bus=0 emcy=1 code=33040')
        with self.assertRaisesRegex(ValueError, 'NODE_BUS_IDENTITY'):
            check_five_diagnostic('FIVE RX node=5 bus=1 emcy=0 code=0')

    def test_malformed_or_reset_is_not_hidden_as_input_quality(self):
        check_five_diagnostic('FIVE STATE tick=100 wrong_bus=0 malformed=0 resets=0')
        with self.assertRaisesRegex(ValueError, 'MALFORMED_OR_STACK_RESET'):
            check_five_diagnostic('FIVE STATE tick=100 wrong_bus=0 malformed=1 resets=0')

    def test_heartbeat_loss_after_common_ready_stops(self):
        check_five_diagnostic('FIVE RX node=2 bus=1 emcy=0 code=0 nmt=5 hb_age=500', True)
        with self.assertRaisesRegex(ValueError, 'HEARTBEAT_LOST'):
            check_five_diagnostic('FIVE RX node=2 bus=1 emcy=0 code=0 nmt=5 hb_age=1501', True)


if __name__ == '__main__':
    unittest.main()
