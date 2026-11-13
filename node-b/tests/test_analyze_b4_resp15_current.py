"""RR15工程判据的纯字典负例；不访问设备，不将RR单通道PASS冒充同步通过。"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from analyze_b4_resp15_current import rr_verdict


class Tests(unittest.TestCase):
    def report(self):
        return {'capture_integrity': 'PASS', 'saved_observations': 110,
                'RR_valid_observations': 110, 'HR_valid_observations': 0,
                'RR_values': {'15': 110}, 'input_quality': {'clipped_frames': 0,
                'diagnostic_clipped_increment_whole_capture': 0},
                'CH1_independent_period': {'status': 'PERIOD_COHERENT_EXPLORATORY_ONLY',
                                          'time_domain_rpm': 15.01}}

    def test_RR_can_pass_with_HR_invalid(self):
        self.assertEqual(rr_verdict(self.report())['analysis_exit_code'], 0)

    def test_one_invalid_saved_observation_fails(self):
        r = self.report(); r['RR_valid_observations'] -= 1
        self.assertIn('NOT_ALL_SAVED_RR_VALID', rr_verdict(r)['RR_failures'])

    def test_clipping_during_warmup_or_evaluation_kept(self):
        for field in ('clipped_frames', 'diagnostic_clipped_increment_whole_capture'):
            r = self.report(); r['input_quality'][field] = 1
            with self.subTest(field=field):
                self.assertIn('NEW_CLIPPED_INPUT', rr_verdict(r)['RR_failures'])

    def test_no_period_cannot_be_patched_with_menu15(self):
        r = self.report(); r['CH1_independent_period'].update(status='NOT_EVALUATED_INPUT_INTEGRITY', time_domain_rpm=None)
        self.assertIn('RAW_PERIOD_UNRESOLVED', rr_verdict(r)['RR_failures'])

    def test_wrong_nominal_rate_not_pass(self):
        r = self.report(); r['RR_values'] = {'20': 110}; r['CH1_independent_period']['time_domain_rpm'] = 20
        self.assertEqual(rr_verdict(r)['analysis_exit_code'], 3)

    def test_integrity_failure_not_masked_by_valid_RR(self):
        r = self.report(); r['capture_integrity'] = 'FAIL'
        self.assertIn('CAPTURE_INTEGRITY', rr_verdict(r)['RR_failures'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
