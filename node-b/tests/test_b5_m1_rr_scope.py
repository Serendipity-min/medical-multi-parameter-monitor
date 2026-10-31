"""RR批次范围与原评测器的独立输出边界；不连接设备。"""
from collections import Counter
import unittest

import b5_m1_owner_once as owner
import b5_m1_review as review
from test_b5_m1 import rows_and_diagnostics


class RRScope(unittest.TestCase):
    def test_exact_fifteen_preregistered_RR_runs_with_unique_nonce_pins(self):
        self.assertEqual(len(owner.AUTHORIZED_RUNS), 15)
        self.assertEqual(Counter(r['target'] for r in owner.AUTHORIZED_RUNS.values()),
                         {12: 3, 15: 3, 18: 3, 24: 3, 30: 3})
        self.assertEqual(len({r['nonce_sha256'] for r in owner.AUTHORIZED_RUNS.values()}), 15)
        for run_id, spec in owner.AUTHORIZED_RUNS.items():
            self.assertTrue(run_id.startswith('M1-R'))
            self.assertEqual(owner.m.plan(run_id)['target'], spec['target'])

    def test_RR12_rate_pass_keeps_valid_HR_and_unknown_truth(self):
        rows, diagnostics, anchor = rows_and_diagnostics()
        for d in diagnostics:
            d['bio'].update(rpm=12, rpm_valid=1, hr=72, hr_valid=1)
        result = review.evaluate(rows, diagnostics, anchor, 'R12', 12)
        self.assertEqual(result['exit_code'], 0)
        self.assertEqual(result['correct_valid_slots'], 120)
        self.assertEqual(result['HR_valid_native_observations'], 240)
        self.assertEqual(len(result['HR_snapshot_clusters']), 1)
        self.assertFalse(result['whole_RR_window_PASS'])
        self.assertIn('UNRESOLVED', result['HR_truth'])
        self.assertTrue(all(d['bio']['hr_valid'] == 1 and d['bio']['hr'] == 72 for d in diagnostics))

    def test_RR_valid_outlier_is_not_hidden_by_other_correct_slots(self):
        rows, diagnostics, anchor = rows_and_diagnostics()
        for d in diagnostics:
            d['bio'].update(rpm=12, rpm_valid=1)
        diagnostics[91]['bio']['rpm'] = 14
        result = review.evaluate(rows, diagnostics, anchor, 'R12', 12)
        self.assertEqual(result['exit_code'], 3)
        self.assertIn('VALID_VALUE_OUT_OF_TOLERANCE', result['engineering_failures'])

    def test_RR_earliest_invalid_slot_cannot_be_replaced_by_later_valid(self):
        rows, diagnostics, anchor = rows_and_diagnostics()
        for d in diagnostics:
            offset = d['bio']['last_sample_ms']-anchor['ms']
            d['bio'].update(rpm=12, rpm_valid=0 if offset >= 45000 and offset % 1000 == 0 else 1)
        result = review.evaluate(rows, diagnostics, anchor, 'R12', 12)
        self.assertEqual(result['correct_valid_slots'], 0)
        self.assertEqual(result['exit_code'], 3)


if __name__ == '__main__':
    unittest.main()
