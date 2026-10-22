"""45秒RESP入口只做脱机门禁、有效性边界和伴随ECG周期验证。"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import resp_validity_b as capture
from analyze_resp_validity_b import validity, ecg_period


def source():
    # 15和20是分别记录的菜单项；合成fixture不冒充源实物确认。
    return {'schema': capture.SOURCE_SCHEMA, 'source_type': 'RESP_EXPLORATORY',
            'stage': 'RESP_VALIDITY_SINGLE_WINDOW', 'mode': 'INDEPENDENT_RESPIRATION',
            'data_source': 'ENGINEERING_NONHUMAN', 'leads': capture.LEADS.copy(),
            'battery_only': True, 'usb_disconnected': True, 'CAN_A_C_human_disconnected': True,
            'Z0_ohm': None, 'delta_Zpp_ohm': None, 'reference_rpm': None, 'nominal_rpm': 15,
            'impedance_calibration': 'NOT_CALIBRATED', 'dynamic_pair': 'UNVERIFIED',
            'acceptance_class': 'RAW_PERIOD_AND_BIO_VALIDITY_NOT_SOURCE_ACCURACY',
            'menu': {'mode_literal': '呼吸波形', 'amplitude_literal': '1.5R',
                     'waveform_period_literal': '20bpm', 'respiration_rate_literal': '15bpm',
                     'ecg_rate_literal': '60BPM', 'apnea_literal': '0s'},
            'apnea_semantics': 'ZERO_DISPLAY_RECORDED_SEMANTICS_UNVERIFIED'}


class ValidityCases(unittest.TestCase):
    def test_separate_menu_controls_do_not_create_false_reference(self):
        s = source(); self.assertEqual(capture.validate_source(s), 'VALIDITY_SOURCE_RECORDED')
        self.assertEqual(s['menu']['waveform_period_literal'], '20bpm')
        self.assertEqual(s['nominal_rpm'], 15); self.assertIsNone(s['reference_rpm'])

    def test_unknown_ohms_reference_and_physical_scope_not_relaxed(self):
        for key, value in [('Z0_ohm', 1000), ('delta_Zpp_ohm', 1.5), ('reference_rpm', 15),
                           ('source_type', 'ORDINARY_ECG'), ('usb_disconnected', False),
                           ('mode', 'ORDINARY_ECG'), ('apnea_semantics', 'ZERO_ASSUMED_DISABLED')]:
            s = source(); s[key] = value
            with self.assertRaises(RuntimeError): capture.validate_source(s)
        with self.assertRaisesRegex(RuntimeError, 'NOT_READY'): capture.validate_source(source(), ready=True)

    def test_old_profile_or_wrong_duration_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'NO_ECG_REUSE'):
            capture.validate_profile({'schema': 'BIO_V2_CAPTURE_1'})
        for seconds in (10, 44, 46, 92):
            with self.assertRaisesRegex(RuntimeError, 'DURATION'):
                capture.validate_profile({'schema': capture.PROFILE_SCHEMA, 'source_schema': capture.SOURCE_SCHEMA,
                    'duration_s': seconds, 'slot_limit': 901, 'evaluation_ms': [10000, 40000]})

    def test_reset_unknown_write_and_unapproved_read_denied(self):
        link = object.__new__(capture.ValidityLink)
        with self.assertRaisesRegex(RuntimeError, 'RESET_DENIED'): link.call('JLINKARM_Reset')
        with self.assertRaisesRegex(RuntimeError, 'RESET_POLICY'): link.call('JLINKARM_ExecCommand', b'SetResetType = 0')
        with self.assertRaisesRegex(RuntimeError, 'FUNCTION_DENIED'): link.call('JLINKARM_WriteMem')
        with self.assertRaisesRegex(RuntimeError, 'READ_SCOPE'): link.call('JLINKARM_ReadMemEx', 0x40013800, 4, None, 0)

    def test_validity_needs_coherent_raw_and_all_saved_live_observations(self):
        e = {'status': 'PERIOD_COHERENT_EXPLORATORY_ONLY', 'time_domain_rpm': 15.1}
        live = [{'rpm_valid': 1, 'rpm': 15} for _ in range(5)]
        self.assertEqual(validity(e, live, [])['analysis_exit_code'], 0)
        live[0]['rpm_valid'] = 0
        self.assertEqual(validity(e, live, [])['analysis_exit_code'], 3)
        self.assertEqual(validity(e, live, ['SEQUENCE_GAP'])['analysis_exit_code'], 2)
        self.assertEqual(validity({'status': 'CH1_VARIATION_PERIOD_UNRESOLVED'}, live, [])['status'], 'RESP_PATH_NOT_OBSERVED')

    def test_menu_match_is_not_the_raw_or_live_validity_test(self):
        # 即使真实信号周期相干于20，也只说明本窗RR有效，不能伪称名义15通过。
        e = {'status': 'PERIOD_COHERENT_EXPLORATORY_ONLY', 'time_domain_rpm': 20.0}
        result = validity(e, [{'rpm_valid': 1, 'rpm': 20} for _ in range(6)], [])
        self.assertEqual(result['analysis_exit_code'], 0)
        self.assertFalse(result['nominal_15_match_descriptive_only'])
        self.assertTrue(result['no_calibrated_source_accuracy_claim'])

    def test_companion_ecg_interval_does_not_assume_requested60(self):
        for interval_ms, bpm in ((500, 120), (1000, 60), (3000, 20)):
            rows = [{'device_ms': i*4, 'ch2_raw': 1000 if (i*4) % interval_ms == 0 else 8000} for i in range(7500)]
            self.assertAlmostEqual(ecg_period(rows)['median_bpm'], bpm)


if __name__ == '__main__':
    unittest.main()
