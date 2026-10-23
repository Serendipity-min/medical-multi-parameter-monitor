"""双通道共同窗口判据的合成正负例；不使用真实输入，不访问板卡。"""
import copy
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
from types import SimpleNamespace
import time

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'node-b/tools'))
import b4_sync as sync


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.rows = [{'device_tick_raw': t, 'source_seq': i + 1, 'flags_raw': 0}
                     for i, t in enumerate(range(1000, 138001, 4))]
        self.diags = [{'last_sample_ms': t, 'hr_valid': 1, 'rpm_valid': 1, 'hr': 60, 'rpm': 20,
                       'hr_reason': 0, 'rpm_reason': 0, 'clipped_samples': 0,
                       'adc': {k: 0 for k in ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow', 'long_gap_count')}}
                      for t in range(1000, 138001, 500)]
    def evaluate(self): return sync.evaluate(self.rows, self.diags, 1000)
    def test_joint_window_pass_still_requires_raw_period_review(self):
        r = self.evaluate(); self.assertEqual(r['failures'], [])
        self.assertEqual(r['saved_observations'], 180); self.assertEqual(r['raw_frames'], 22500)
        self.assertEqual(r['CAN_transport'], 'NOT_TESTED_CAN_DISCONNECTED')
        self.assertIn('RAW_PERIOD_REVIEW_REQUIRED', r['status'])
    def test_warmup_not_counted(self):
        for d in self.diags:
            if d['last_sample_ms'] < 46000: d['hr_valid'] = d['rpm_valid'] = 0
        self.assertFalse(self.evaluate()['failures'])
    def test_hr_failure_not_hidden_by_rr(self):
        self.diags[100]['hr_valid'] = 0
        r = self.evaluate(); self.assertIn('JOINT_VALIDITY_OR_RATE', r['failures'])
        self.assertEqual(r['RR_pass_observations'], 180); self.assertEqual(r['joint_pass_observations'], 179)
    def test_wrong_hr(self):
        self.diags[100]['hr'] = 120; self.assertIn('JOINT_VALIDITY_OR_RATE', self.evaluate()['failures'])
    def test_wrong_rr(self):
        self.diags[100]['rpm'] = 15; self.assertIn('JOINT_VALIDITY_OR_RATE', self.evaluate()['failures'])
    def test_gap(self):
        del self.rows[20000]; self.assertIn('RAW_SEQUENCE_GAP', self.evaluate()['failures'])
    def test_adc_error(self):
        self.diags[-1]['adc']['spi_errors'] = 1; self.assertIn('ADC_ERROR_PRESENT', self.evaluate()['failures'])
    def test_no_tail_coverage(self):
        self.rows = self.rows[:33000]; self.assertIn('EVALUATION_NOT_COVERED', self.evaluate()['failures'])
    def test_diag_gap(self):
        del self.diags[100:104]; self.assertIn('DIAGNOSTIC_GAP', self.evaluate()['failures'])
    def test_reason_not_ignored(self):
        self.diags[100]['hr_reason'] = 4; self.assertIn('JOINT_VALIDITY_OR_RATE', self.evaluate()['failures'])
    def test_authorization_disabled(self):
        with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_REQUIRED'): sync.authorize(sync.plan())
    def test_authorized_profile_validation_still_no_sdk(self):
        a = {'enabled': True, 'owner_approved': True, 'scope': sync.SCOPE, 'plan': sync.plan(),
             'expires_unix': sync.time.time() + 60, 'observed_menu': sync.MENU, 'card_sha256': 'fake'}
        a.update({k: True for k in ('battery_no_USB', 'RA_LL_RL_unchanged', 'CAN_A_C_human_disconnected',
                                    'meter_removed_OFF', 'electrical_gate_pass')})
        with patch.object(sync.raw, 'sha', return_value='fake'):
            sync.authorize(a)
            a['plan']['criteria'] = {**sync.CRITERIA, 'HR_range_bpm': [0, 300]}
            with self.assertRaisesRegex(ValueError, 'PROFILE_DRIFT'): sync.authorize(a)
    def test_gain_card_not_reuse_old_resp_schema(self):
        p = sync.plan(); self.assertEqual(p['source_type'], 'ECG_RESP_SIMULTANEOUS_MANUAL_NOMINAL')
        self.assertNotEqual(p['source_type'], 'RESP_EXPLORATORY'); self.assertIsNone(p['delta_Zpp_ohm'])
    def test_target_write_functions_denied(self):
        obj = object.__new__(sync.SyncLink); obj.sdk_calls = 0
        for name in ('JLINKARM_Reset', 'JLINKARM_Halt', 'JLINKARM_Go', 'JLINKARM_WriteMem'):
            with self.assertRaisesRegex(ValueError, 'FUNCTION_DENIED'): obj.call(name)
    def test_final_cpu_check_after_host_export_cannot_resume_new_rom(self):
        # 把采集时钟推进到结束，验证主机落盘后最后一次CPU异常不能沿用早期正常状态。
        out = ROOT / 'node-b/build' / ('b4-sync-final-check-' + str(time.time_ns())); out.mkdir()
        class Link:
            verified_running_flash = False
            def open(self): pass
            def u32(self, address): return 0
            def read(self, address, size): return b''
            def set_close_resume(self, value): self.close_resume_enabled = value
        link = Link()
        first = {'bio': {'last_sample_ms': 1000, 'clipped_samples': 0, 'adc': {k: 0 for k in
                 ('init_errors', 'spi_errors', 'bad_status', 'queue_overflow', 'long_gap_count')}}}
        selection = SimpleNamespace(boots=('boot1',), conflicts=(), multi_repeat_conflicts=(), frames={}, pending=())
        with patch.object(sync.last, 'board'), patch.object(sync, 'digest', side_effect=[sync.last.IMAGE_SHA, sync.runtime.OPTIONS_SHA]), \
             patch.object(sync.last, 'sample', return_value=first) as samples, \
             patch.object(sync.last, 'running', side_effect=[None, ValueError('ROM_AFTER_EXPORT')]), \
             patch.object(sync.time, 'monotonic', side_effect=[0, 138]), \
             patch.object(sync.StableSlots, 'select', return_value=selection):
            with self.assertRaisesRegex(ValueError, 'ROM_AFTER_EXPORT'): sync.capture(link, out)
            self.assertEqual(samples.call_count, 2); self.assertFalse(link.verified_running_flash)


if __name__ == '__main__': unittest.main(verbosity=2)
