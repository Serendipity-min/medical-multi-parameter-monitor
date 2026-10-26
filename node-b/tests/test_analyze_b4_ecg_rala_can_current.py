"""ECG单通道按CH2/HR判定，保留RR无效及传输独立门禁。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze_b4_ecg_rala_can_current import hr_verdict


class Tests(unittest.TestCase):
    def report(self):
        return {'capture_integrity': 'PASS', 'saved_observations': 110,
                'HR_valid_observations': 110, 'HR_values': {'60': 110},
                'CH2_raw': {'near_rail_frames': 0}, 'RR_valid_observations': 0}

    def test_HR_pass_with_RR_invalid(self):
        self.assertEqual(hr_verdict(self.report())['analysis_exit_code'], 0)

    def test_CH2_near_rail_fails(self):
        r = self.report(); r['CH2_raw']['near_rail_frames'] = 1
        self.assertIn('CH2_NEAR_RAIL', hr_verdict(r)['HR_failures'])

    def test_one_invalid_HR_fails(self):
        r = self.report(); r['HR_valid_observations'] = 109
        self.assertEqual(hr_verdict(r)['analysis_exit_code'], 3)


if __name__ == '__main__':
    unittest.main(verbosity=2)
