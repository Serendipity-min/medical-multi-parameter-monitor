"""预览节奏固定回归：虚拟时间测试，不等待真实分钟、不连接外部目标。"""
import math
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from preview_signals import PreviewTimeline, scalar_value, waveform


class PreviewSignalsTests(unittest.TestCase):
    def test_intervals_do_not_duplicate_blood_pressure_measurements(self):
        timeline = PreviewTimeline()
        counts = {name: 0 for name in ('NIBP', 'HR', 'TEMP', 'ECG')}
        for tick in range(600):
            for name in counts:
                if timeline.capture(name, tick * .2) is not None:
                    counts[name] += 1
        self.assertEqual(counts, {'NIBP': 4, 'HR': 120, 'TEMP': 60, 'ECG': 600})

    def test_values_are_varied_and_finite(self):
        for name in ('HR', 'PR', 'RR', 'TEMP', 'SPO2', 'NIBP'):
            values = [scalar_value(name, t) for t in range(0, 180, 2)]
            self.assertGreater(len({str(value) for value in values}), 2, name)
            for value in values:
                self.assertTrue(all(math.isfinite(v) for v in value) if isinstance(value, list) else math.isfinite(value))
        for t in range(0, 180, 30):
            sys_value, dia_value = scalar_value('NIBP', t)
            self.assertGreater(sys_value, dia_value)

    def test_fixed_scenario_and_waveform_packets(self):
        self.assertEqual(scalar_value('HR', 20, fixed=True), 72.0)
        self.assertEqual(scalar_value('NIBP', 60, fixed=True), [118.0, 76.0])
        for name, count in (('ECG', 50), ('PPG', 10), ('RESP', 10)):
            first, second = waveform(name, 1), waveform(name, 1.2)
            self.assertEqual(len(first['samples']), count)
            self.assertTrue(all(math.isfinite(v) for v in first['samples']))
            self.assertNotEqual(first['samples'], second['samples'])

    def test_late_scheduler_skips_history_and_control_changes_are_immediate(self):
        timeline = PreviewTimeline()
        self.assertEqual(timeline.capture('NIBP', 0, 'VALID'), 0)
        self.assertIsNone(timeline.capture('NIBP', 12, 'VALID'))
        self.assertEqual(timeline.capture('NIBP', 12, 'INVALID'), 0)
        # 调度延迟后只发送当前采集槽，不回填 30 秒和 60 秒的假历史。
        self.assertEqual(timeline.capture('NIBP', 95, 'VALID'), 90)
        self.assertIsNone(timeline.capture('NIBP', 96, 'VALID'))


if __name__ == '__main__':
    unittest.main()
