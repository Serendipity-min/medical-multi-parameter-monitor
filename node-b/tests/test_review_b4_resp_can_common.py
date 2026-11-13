"""RR实收时间映射、稳定性与有效数据接收分别裁定；全部输入为合成。"""
from pathlib import Path
import math
import struct
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
from review_b4_resp_can_common import review
from test_b4_capture_decode import fixture
from b4_capture_decode import value_hash


class Tests(unittest.TestCase):
    def inputs(self):
        rows = []
        for r in fixture():
            r = dict(r)
            if r['kind'] == 1 and r['id'] == 0x382:
                r['data'] = struct.pack('<4H', 0, 1500, 0, 0).hex()
            if r['kind'] == 8 and r['id'] == 7:
                r['data'] = struct.pack('<iI', 1500, value_hash([1500])).hex()
            rows.append(r)
        raw = [{'device_ms': t, 'source_seq': t//4+1, 'flags_raw': 0,
                'ch1_raw': int(64000+1200*math.sin(2*math.pi*t/4000)), 'ch2_raw': 100}
               for t in range(0, 180000, 4)]
        d = [{'bio': {'last_sample_ms': t, 'rpm': 15, 'rpm_valid': 1, 'rpm_reason': 0}}
             for t in range(0, 180000, 500)]
        return rows, raw, d

    def test_complete_RR15(self):
        rows, raw, d = self.inputs(); r = review(rows, raw, d, {'failures': []})
        self.assertEqual(r['failures'], [])
        self.assertTrue(r['RR_valid_data_received'])
        self.assertEqual(r['C_received_RESP_wave_points'], 4500)
        self.assertGreater(r['B_common_raw_frames'], 22000)
        self.assertFalse(r['HR_RR_simultaneous_engineering_pass'])

    def test_one_invalid_B_observation_retains_stability_failure(self):
        rows, raw, d = self.inputs(); d[150]['bio'].update(rpm=0, rpm_valid=0, rpm_reason=6)
        r = review(rows, raw, d, {'failures': []})
        self.assertIn('B_COMMON_RR_NOT_ALL_VALID15', r['failures'])
        self.assertTrue(r['RR_valid_data_received'])

    def test_missing_source_tick_rejected(self):
        rows, raw, d = self.inputs(); raw = [r for r in raw if r['device_ms'] != 60000]
        r = review(rows, raw, d, {'failures': []})
        self.assertIn('C_RESP_B_RAW_TICK_MISSING', r['failures'])
        self.assertFalse(r['RR_valid_data_received'])

    def test_model_wrong_value_prevents_valid_data_claim(self):
        rows, raw, d = self.inputs()
        rows = [dict(r, data=struct.pack('<iI', 2000, value_hash([2000])).hex())
                if r['kind'] == 8 and r['id'] == 7 and r['tick'] == 60000 else r for r in rows]
        self.assertFalse(review(rows, raw, d, {'failures': []})['RR_valid_data_received'])

    def test_transport_failure_prevents_valid_transport_claim(self):
        rows, raw, d = self.inputs(); r = review(rows, raw, d, {'failures': ['C_TX_FAILURE_IN_EVALUATION']})
        self.assertFalse(r['RR_valid_data_received'])
        self.assertIn('C_TX_FAILURE_IN_EVALUATION', r['failures'])


if __name__ == '__main__':
    unittest.main(verbosity=2)
