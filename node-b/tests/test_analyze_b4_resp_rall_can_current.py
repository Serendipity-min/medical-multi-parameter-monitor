"""共同窗的预热与稳态分开：保留预热削顶，但必须由评价段本身裁定RR资格。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze_b4_resp_rall_can_current import rr_verdict


class Tests(unittest.TestCase):
    def report(self):
        return {'capture_integrity': 'PASS', 'saved_observations': 110, 'RR_valid_observations': 110,
                'RR_values': {'15': 110}, 'CH1_raw': {'near_rail_frames': 0},
                'input_quality': {'clipped_frames': 0, 'diagnostic_clipped_increment_whole_capture': 9},
                'CH1_independent_period': {'status': 'PERIOD_COHERENT_EXPLORATORY_ONLY', 'time_domain_rpm': 15.0}}

    def test_warmup_clip_count_does_not_change_clean_steady_verdict(self):
        self.assertEqual(rr_verdict(self.report())['analysis_exit_code'], 0)

    def test_evaluation_near_rail_fails(self):
        r = self.report(); r['CH1_raw']['near_rail_frames'] = 1
        self.assertIn('EVALUATION_CH1_NEAR_RAIL', rr_verdict(r)['RR_failures'])

    def test_recovery_not_ready_in_steady_window_still_fails(self):
        r = self.report(); r['RR_valid_observations'] = 39
        self.assertIn('NOT_ALL_SAVED_RR_VALID', rr_verdict(r)['RR_failures'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
