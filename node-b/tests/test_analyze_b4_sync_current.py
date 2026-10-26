"""共同窗口不会把RR15、生理失效或缺失样本冒充同步名义验收通过。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze_b4_sync_current import evaluate


class Tests(unittest.TestCase):
    def fixture(self):
        rows = [dict(device_ms=t, source_seq=i+1, flags_raw=0) for i, t in enumerate(range(0, 137001, 4))]
        diagnostics = []
        for t in range(0, 137001, 500):
            bio = dict(last_sample_ms=t, hr=60, rpm=20, hr_valid=1, rpm_valid=1, hr_reason=0, rpm_reason=0,
                       hr_candidates=t//1000, hr_accepted=t//1000, hr_last_cycle_ms=t,
                       resp_candidates=t//3000, resp_accepted=t//3000, resp_last_cycle_ms=t)
            bio['adc'] = {k: 0 for k in ('captured', 'delivered', 'bad_status', 'spi_errors',
                                         'queue_overflow', 'init_errors', 'long_gap_count')}
            diagnostics.append({'bio': bio, 'CAN': {'offered': 0, 'expired': 0, 'high_water': 0}, 'CAN1_ESR': 0})
        return rows, diagnostics

    def test_complete_nominal_joint_window(self):
        rows, d = self.fixture(); r, _, _ = evaluate(rows, d, 0)
        self.assertTrue(r['simultaneous_engineering_pass'])
        self.assertEqual(r['evaluation_raw_frames'], 22500)
        self.assertFalse(r['new_end_to_end_transport_pass'])

    def test_valid15_does_not_satisfy_frozen_manual20(self):
        rows, d = self.fixture()
        for item in d: item['bio']['rpm'] = 15
        r, _, _ = evaluate(rows, d, 0)
        self.assertEqual(r['RR_valid_observations'], 180)
        self.assertFalse(r['simultaneous_engineering_pass'])

    def test_raw_missing_even_if_diagnostic_good(self):
        rows, d = self.fixture(); r, _, _ = evaluate(rows[::2], d, 0)
        self.assertIn('RAW_SEQUENCE_GAP', r['integrity_failures'])
        self.assertFalse(r['simultaneous_engineering_pass'])

    def test_one_invalid_observation_prevents_joint_pass(self):
        rows, d = self.fixture(); d[150]['bio'].update(hr_valid=0, hr_reason=2)
        r, _, _ = evaluate(rows, d, 0)
        self.assertFalse(r['simultaneous_engineering_pass'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
