"""合成数据验证30/固定周期20的源门禁和两档跟踪判据，不打开SDK。"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import resp_rall30_b as capture
from compare_resp_20_30_b import compare, BASELINE_SOURCE_SHA


def source(rate=30):
    return {'schema': capture.SOURCE_SCHEMA, 'source_type': 'RESP_EXPLORATORY',
            'stage': 'RESP_RA_LL30_SINGLE_WINDOW', 'mode': 'INDEPENDENT_RESPIRATION',
            'data_source': 'ENGINEERING_NONHUMAN', 'leads': capture.LEADS.copy(),
            'battery_only': True, 'usb_disconnected': True, 'CAN_A_C_human_disconnected': True,
            'Z0_ohm': None, 'delta_Zpp_ohm': None, 'reference_rpm': None, 'nominal_rpm': rate,
            'impedance_calibration': 'NOT_CALIBRATED', 'dynamic_pair': 'MANUFACTURER_MANUAL_RA_LL',
            'manual_sha256': capture.MANUAL_SHA,
            'acceptance_class': 'RAW_PERIOD_AND_BIO_VALIDITY_NOT_SOURCE_ACCURACY',
            'menu': {'mode_literal': '呼吸波形', 'amplitude_literal': '1.5R',
                     'waveform_period_literal': '20bpm', 'respiration_rate_literal': f'{rate}bpm',
                     'ecg_rate_literal': '60BPM', 'apnea_literal': '0s'},
            'apnea_semantics': 'ZERO_DISPLAY_RECORDED_SEMANTICS_UNVERIFIED'}


def summary(period, valid_exit=3):
    return {'bio_source_sha256': 'SYNTHETIC_UNCHANGED', 'evaluation_device_offsets_ms': [10000, 40000],
            'source_record_sha256': BASELINE_SOURCE_SHA, 'failures': [], 'analysis_exit_code': valid_exit,
            'independent_raw_estimate': {'status': 'PERIOD_COHERENT_EXPLORATORY_ONLY',
                'periods_ms': [period]*8, 'time_domain_rpm': 60000/period}}


class TrackingCases(unittest.TestCase):
    def test30_with_independent_waveform_period20_is_valid(self):
        self.assertEqual(capture.validate_source(source()), 'VALIDITY_SOURCE_RECORDED')

    def test_wrong_rate_path_truth_and_second_menu_change_rejected(self):
        for key, value in [('nominal_rpm', 20), ('source_type', 'ORDINARY_ECG'),
                           ('reference_rpm', 30), ('Z0_ohm', 1000), ('usb_disconnected', False),
                           ('leads', {'R_red': 'RA', 'L_yellow': 'LA', 'F_green': 'RL'})]:
            s = source(); s[key] = value
            with self.assertRaises(RuntimeError): capture.validate_source(s)
        s = source(); s['menu']['waveform_period_literal'] = '30bpm'
        with self.assertRaises(RuntimeError): capture.validate_source(s)

    def test_old_profile_and_changed_duration_rejected(self):
        with self.assertRaises(RuntimeError): capture.validate_profile({'schema': 'RESP_RA_LL20_CAPTURE_45S_1'})
        with self.assertRaisesRegex(RuntimeError, 'DURATION'):
            capture.validate_profile({'schema': capture.PROFILE_SCHEMA, 'source_schema': capture.SOURCE_SCHEMA,
                                      'duration_s': 46, 'slot_limit': 901, 'evaluation_ms': [10000, 40000]})

    def test_tracking_can_pass_while_whole_RR_validity_remains_failed(self):
        # 原码周期跟踪与整段RR有效性是两层结论，不能抹除启动无效样本。
        r = compare(summary(3000), summary(2000), source(20), source(30))
        self.assertEqual(r['status'], 'E2_RATE_TRACKING_SEEN')
        self.assertFalse(r['both_windows_full_RR_validity_pass'])
        self.assertEqual(r['current_window_validity_analysis_exit'], 3)

    def test_unchanged_period_does_not_track(self):
        self.assertEqual(compare(summary(3000), summary(3000), source(20), source(30))['comparison_exit_code'], 3)

    def test_changed_controls_or_firmware_cannot_pass(self):
        s = source(30); s['menu']['waveform_period_literal'] = '30bpm'
        with self.assertRaisesRegex(RuntimeError, 'CHANGED_MENU'): compare(summary(3000), summary(2000), source(20), s)
        current = summary(2000); current['bio_source_sha256'] = 'OTHER_SYNTHETIC'
        with self.assertRaisesRegex(RuntimeError, 'ALGORITHM_CHANGED'):
            compare(summary(3000), current, source(20), source(30))

    def test_frame_failure_or_incoherent_signal_does_not_pass(self):
        current = summary(2000); current['failures'] = ['SEQUENCE_GAP']
        self.assertEqual(compare(summary(3000), current, source(20), source(30))['comparison_exit_code'], 2)
        current = summary(2000); current['independent_raw_estimate']['status'] = 'CH1_VARIATION_PERIOD_UNRESOLVED'
        self.assertEqual(compare(summary(3000), current, source(20), source(30))['comparison_exit_code'], 3)


if __name__ == '__main__':
    unittest.main()
