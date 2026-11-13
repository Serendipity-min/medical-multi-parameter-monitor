"""同窗有效传输必须同时有B原码/资格和C数值/有效位，不以CAN帧到达替代。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from review_b4_ecg_can_common import review
from test_b4_capture_decode import fixture


class Tests(unittest.TestCase):
    def inputs(self):
        rows = fixture()
        raw = [{'device_ms': t, 'source_seq': t//4+1, 'flags_raw': 0, 'ch2_raw': 100}
               for t in range(0, 180000, 4)]
        d = [{'bio': {'last_sample_ms': t, 'hr': 60, 'hr_valid': 1, 'hr_reason': 0}}
             for t in range(0, 180000, 500)]
        return rows, raw, d

    def test_nominal_valid_transfer(self):
        rows, raw, d = self.inputs(); r = review(rows, raw, d, {'failures': []})
        self.assertEqual(r['analysis_exit_code'], 0)
        self.assertEqual(r['matched_B_raw_points'], 22500)
        self.assertFalse(r['HR_RR_simultaneous_engineering_pass'])
        self.assertFalse(r['RR_valid_transport_pass'])

    def test_received_tick_missing_from_B_raw_rejected(self):
        rows, raw, d = self.inputs(); raw = [r for r in raw if r['device_ms'] != 60000]
        self.assertIn('C_WAVE_B_RAW_TICK_MISSING', review(rows, raw, d, {'failures': []})['failures'])

    def test_one_invalid_B_observation_rejected(self):
        rows, raw, d = self.inputs(); d[150]['bio'].update(hr_valid=0, hr_reason=2)
        self.assertIn('B_COMMON_HR_NOT_ALL_VALID60', review(rows, raw, d, {'failures': []})['failures'])

    def test_transport_errors_propagate(self):
        rows, raw, d = self.inputs()
        self.assertIn('SERIAL_CRC_ERROR', review(rows, raw, d, {'failures': ['SERIAL_CRC_ERROR']})['failures'])

    def test_model_invalid_cannot_pass_even_if_scalar60(self):
        rows, raw, d = self.inputs(); rows = [dict(r, flags=r['flags'] & ~256)
            if r['kind']==8 and r['id']==5 and r['tick']==60000 else r for r in rows]
        self.assertIn('C_MODEL_VALIDITY_5', review(rows, raw, d, {'failures': []})['failures'])

    def test_quality_invalid_cannot_pass_even_if_scalar60(self):
        rows, raw, d = self.inputs(); rows = [dict(r, data='0000000001000000')
            if r['kind']==1 and r['id']==0x682 and r['tick']==60000 else r for r in rows]
        self.assertIn('C_ECG_HR_VALID_BITS', review(rows, raw, d, {'failures': []})['failures'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
