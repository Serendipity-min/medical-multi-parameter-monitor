"""普通Host负向测试：验证模式漂移/通信失败不重新启用BIAS，不连接设备。"""
import unittest
from observe_bias import FW, observe


def response(mode=0, **changes):
    return {'ok': True, 'fw': FW, 'mode': mode, 'state': mode,
            'faults': 0, 'console_errors': 0, **changes}


class BiasWindowTests(unittest.TestCase):
    def run_window(self, replies, seconds=3):
        # 假时钟只由sleep推进，测试不等待真实时间、不打开串口。
        clock = [0]
        self.commands = []
        self.events = []
        answers = iter(replies)

        def request(command):
            self.commands.append(command)
            reply = next(answers)
            if isinstance(reply, Exception):
                raise reply
            return reply

        def sleep(delay):
            clock[0] += delay

        return observe(request, self.events.append, seconds, lambda: clock[0], sleep)

    def test_normal_window_then_off(self):
        result = self.run_window([response(), response(1), response(1),
                                  response(1), response()])
        self.assertEqual(result['observation'], 'DIGITAL_SAMPLED_WINDOW_COMPLETE')
        self.assertEqual(result['off'], 'CONFIRMED')
        self.assertEqual(self.commands, ['info', 'bias', 'status', 'status', 'off'])

    def test_reset_to_off_is_failure_without_reapply(self):
        result = self.run_window([response(), response(1), response(), response()])
        self.assertEqual(result['observation'], 'FAIL')
        self.assertEqual(self.commands, ['info', 'bias', 'status', 'off'])

    def test_disconnect_preserves_unknown_off(self):
        result = self.run_window([response(), response(1), OSError(), OSError()])
        self.assertEqual(result['off'], 'NOT_CONFIRMED')
        self.assertEqual(result['observation'], 'FAIL')
        self.assertEqual(self.commands.count('bias'), 1)

    def test_wrong_identity_sends_no_actuation(self):
        result = self.run_window([response(fw='other-device')])
        self.assertEqual(self.commands, ['info'])
        self.assertEqual(result['off'], 'NOT_CONFIRMED')

    def test_initial_non_off_never_enables(self):
        result = self.run_window([response(1), response()])
        self.assertEqual(self.commands, ['info', 'off'])
        self.assertEqual(result['observation'], 'FAIL')

    def test_rejected_bias_stops(self):
        result = self.run_window([response(), {'ok': False}, response()])
        self.assertEqual(self.commands, ['info', 'bias', 'off'])
        self.assertEqual(result['observation'], 'FAIL')

    def test_fault_error_and_missing_fields_stop(self):
        cases = [response(1, faults=1), response(1, console_errors=1),
                 response(1, state=0), response(1, fw='other-device')]
        missing = response(1)
        del missing['faults']
        cases.append(missing)
        for reply in cases:
            with self.subTest(reply=reply):
                result = self.run_window([response(), response(1), reply, response()])
                self.assertEqual(result['observation'], 'FAIL')
                self.assertEqual(self.commands, ['info', 'bias', 'status', 'off'])

    def test_off_ack_must_confirm_off(self):
        result = self.run_window([response(), response(1), response(1), response(1)], 1)
        self.assertEqual(result['off'], 'NOT_CONFIRMED')

    def test_invalid_duration_has_no_io(self):
        for seconds in (0, 301, -1, True, 1.5):
            with self.subTest(seconds=seconds), self.assertRaises(ValueError):
                self.run_window([], seconds)
            self.assertEqual(self.commands, [])


if __name__ == '__main__':
    unittest.main(verbosity=2)
