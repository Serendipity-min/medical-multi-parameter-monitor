"""RESP-003源/ABI/周期与有限采集负例；所有测试脱机且不构造硬件Link。"""
import copy
import csv
import json
import math
from pathlib import Path
import struct
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'node-b/tools'))
import capture_resp_b as capture
from analyze_resp_b import require_capture_end, replay
from resp_exploratory import FIELDS, SOURCE_SCHEMA, decode, estimate_period, reason_names, validate_source


def source():
    return {'schema': SOURCE_SCHEMA, 'source_type': 'RESP_EXPLORATORY', 'stage': 'E1',
            'data_source': 'ENGINEERING_NONHUMAN', 'acceptance_class': 'EXPLORATORY_NOMINAL_RATE_ONLY',
            'mode': 'INDEPENDENT_RESPIRATION', 'Z0_ohm': None, 'delta_Zpp_ohm': None,
            'dynamic_pair': 'UNVERIFIED', 'impedance_calibration': 'NOT_CALIBRATED',
            'leads': {'R_red': 'RA', 'L_yellow': 'LA', 'F_green': 'RL'},
            'battery_only': True, 'usb_disconnected': True, 'CAN_A_C_human_disconnected': True,
            'nominal_rpm': 15, 'menu_rate_rpm': 15, 'amplitude_literal': '1.5R',
            'menu': {'mode_literal': '呼吸波形', 'rate_literal': '15rbpm', 'amplitude_literal': '1.5R', 'apnea_literal': '未核实'},
            'operator_ready': False, 'menu_confirmed': False, 'safety_confirmed': False}


def rows(rate=15, seconds=60):
    # 合成真值只用于估计器功能验证，绝不登记成模拟器真机数据。
    return [{'source_seq': i + 1, 'device_ms': i * 4, 'irq_cycles': i * 672000,
             'flags_raw': 0, 'status_raw': 0xc00000, 'ch2_raw': 1000,
             'ch1_raw': round(75000 + 1000 * math.sin(2 * math.pi * rate / 60 * i / 250))}
            for i in range(seconds * 250)]


class SourceCases(unittest.TestCase):
    def test_actual_resp_bpm_literal_keeps_mode_and_unknown_Z_gates(self):
        # 实际菜单沿用bpm也必须通过独立呼吸模式门；合成安全记录不能当作现场证据。
        with tempfile.TemporaryDirectory() as name:
            record = Path(name) / 'safety.json'
            record.write_text(json.dumps({'stage': 'E1', 'status': 'CONFIRMED_FOR_BOUNDED_E1',
                'same_ECG_setup': True, 'battery_no_USB': True, 'no_grounded_instrument': True,
                'no_shorts_or_abnormalities': True, 'CAN_A_C_human_disconnected': True,
                'voltage_current_safety_basis': 'SYNTHETIC_TEST_ONLY_NOT_FIELD_EVIDENCE',
                'resp_mode_compatibility_limit_acknowledged': True}), encoding='utf-8')
            s = source();s['menu']['rate_literal'] = '15bpm';s['menu']['apnea_literal'] = '未找到'
            s.update(operator_ready=True, menu_confirmed=True, owner_confirmation='SYNTHETIC_TEST_ONLY',
                     safety_confirmed=True, safety_record=str(record), safety_record_sha256=capture.sha(record))
            self.assertEqual(validate_source(s, 'E1', ready=True), 'RESP_SOURCE_READY')
            self.assertEqual(s['menu']['rate_literal'], '15bpm')
            self.assertIsNone(s['delta_Zpp_ohm'])
            for mode in ('心电波形', 'ORDINARY_ECG'):
                s['menu']['mode_literal'] = mode
                with self.assertRaisesRegex(RuntimeError, 'ACTUAL_MENU'):
                    validate_source(s, 'E1', ready=True)

    def test_unknown_impedance_allowed_only_for_exploration(self):
        s = source()
        self.assertEqual(validate_source(s, 'E1'), 'RESP_SOURCE_OFFLINE_ONLY')
        for key, value in [('source_type', 'ORDINARY_ECG'), ('acceptance_class', 'ABS_IMPEDANCE_CALIBRATED'),
                           ('delta_Zpp_ohm', 1.5), ('Z0_ohm', 1000), ('dynamic_pair', 'RA_LA_VERIFIED'),
                           ('usb_disconnected', False), ('nominal_rpm', float('nan')), ('amplitude_literal', '3.0R')]:
            with self.subTest(key=key):
                bad = copy.deepcopy(s);bad[key] = value
                with self.assertRaises(RuntimeError):
                    validate_source(bad, 'E1')
        del s['Z0_ohm']
        with self.assertRaisesRegex(RuntimeError, 'NULL'):
            validate_source(s, 'E1')

    def test_empty_menu_and_not_ready(self):
        s = source();s['menu']['rate_literal'] = ''
        with self.assertRaisesRegex(RuntimeError, 'EMPTY_MENU'):
            validate_source(s, 'E1')
        with self.assertRaisesRegex(RuntimeError, 'NOT_READY'):
            validate_source(source(), 'E1', ready=True)
        s = source();s.update(operator_ready=True, menu_confirmed=True, owner_confirmation='synthetic', safety_confirmed=False)
        with self.assertRaisesRegex(RuntimeError, 'SAFETY_NOT_CONFIRMED'):
            validate_source(s, 'E1', ready=True)


class DiagnosticCases(unittest.TestCase):
    def test_all_signed_raw_and_reason_fields(self):
        values = [0x324f4942, 2] + list(range(2, 8)) + [-1, -2, -3, -4] + list(range(12, 26)) + [1., 2., .1, .2]
        data = decode(struct.pack('<8I4i14I4f', *values), struct.pack('<12I', *range(12)), bytes(12))
        self.assertEqual(data['resp_raw'], -2)
        self.assertEqual(data['resp_filtered'], -4)
        self.assertEqual(data['rpm'], 13)
        self.assertEqual(data['resp_accepted'], 21)
        self.assertEqual(data['resp_fresh_intervals'], 25)
        self.assertEqual(data['resp_rms_codes'], 2.)
        self.assertEqual(reason_names(1 | 2 | 256), ['WARMUP', 'NO_CYCLES', 'UNKNOWN_BITS'])
        with self.assertRaisesRegex(RuntimeError, 'ABI'):
            decode(bytes(120), bytes(48), bytes(12))
        with self.assertRaisesRegex(RuntimeError, 'LENGTH'):
            decode(bytes(119), bytes(48), bytes(12))

    def test_c_host_struct_layout_and_values(self):
        with tempfile.TemporaryDirectory() as name:
            folder = Path(name);c = folder / 'layout.c';binary = folder / 'layout.exe'
            header = ROOT / 'node-b/firmware/biov2/实验固件/HARDWARE/bio_v2.h'
            (folder / 'bio_v2.h').write_bytes(header.read_bytes())
            # 用真实C头写出结构体字节，验证Python有符号字段和RESP偏移，而非只测试pack/unpack自身。
            # GCC旧宿主不能在include字面量中打开UTF8路径；复制原字节到临时ASCII路径。
            c.write_text('#include <stdio.h>\n#include <io.h>\n#include <fcntl.h>\n#include "bio_v2.h"\n'
                         'int main(void){BioV2Diag d={0};_setmode(_fileno(stdout),_O_BINARY);d.tag=0x324f4942;d.abi_version=2;'
                         'd.resp_raw=-12345;d.resp_filtered=-789;d.rpm=30;d.rpm_valid=1;'
                         'd.resp_candidates=8;d.resp_accepted=7;d.resp_last_cycle_ms=15000;'
                         'd.resp_fresh_intervals=5;d.resp_rms_codes=123.5f;'
                         'if(sizeof(d)!=120)return 9;return fwrite(&d,1,sizeof(d),stdout)==120?0:10;}\n', encoding='utf-8')
            result = subprocess.run(['C:/mingw64/bin/gcc.exe', '-std=c99', '-Wall', '-Wextra', '-Werror', str(c), '-o', str(binary)], capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            output = subprocess.run([str(binary)], capture_output=True)
            self.assertEqual(output.returncode, 0)
            d = decode(output.stdout, bytes(48), bytes(12))
            self.assertEqual((d['resp_raw'], d['resp_filtered'], d['rpm'], d['rpm_valid']), (-12345, -789, 30, 1))
            self.assertEqual((d['resp_candidates'], d['resp_accepted'], d['resp_last_cycle_ms'], d['resp_fresh_intervals']), (8, 7, 15000, 5))
            self.assertEqual(d['resp_rms_codes'], 123.5)


class PeriodCases(unittest.TestCase):
    def test_rate_tracking_independent_of_menu(self):
        for rate in (12, 15, 18, 24, 30):
            with self.subTest(rate=rate):
                result = estimate_period(rows(rate))
                self.assertEqual(result['status'], 'PERIOD_COHERENT_EXPLORATORY_ONLY', result)
                for key in ('time_domain_rpm', 'spectral_rpm', 'autocorrelation_rpm'):
                    self.assertAlmostEqual(result[key], rate, delta=1)
                self.assertIsNone(result['delta_Zpp_ohm'])
                self.assertIsNone(result['Z0_ohm'])

    def test_flat_short_gap_conflict_and_rail(self):
        data = rows(seconds=10)
        for r in data:
            r['ch1_raw'] = 75000
        self.assertEqual(estimate_period(data)['status'], 'NO_RESOLVABLE_CH1_VARIATION')
        self.assertEqual(estimate_period(rows(seconds=4))['status'], 'NOT_EVALUATED_TOO_SHORT')
        data = rows(seconds=10);del data[100]
        self.assertEqual(estimate_period(data)['status'], 'NOT_EVALUATED_INPUT_INTEGRITY')
        data = rows(seconds=10);data[100]['flags_raw'] = 1
        self.assertEqual(estimate_period(data)['status'], 'NOT_EVALUATED_INPUT_INTEGRITY')
        data = rows(seconds=10);data[100]['ch1_raw'] = 8388607
        self.assertIn('CH1_NEAR_RAIL', estimate_period(data)['failures'])
        self.assertEqual(estimate_period(rows(seconds=10), {'multi_repeat_conflicts': 1})['status'], 'NOT_EVALUATED_INPUT_INTEGRITY')

    def test_timestamp_wrap_and_ten_second_uncertainty(self):
        data = rows(seconds=10)
        for r in data:
            r['device_ms'] = (r['device_ms'] + 0xfffff000) & 0xffffffff
        result = estimate_period(data)
        self.assertFalse(result['failures'])
        self.assertGreater(result['finite_window_resolution_rpm'], 6)
        self.assertIn('short_window_limit', result)

    def test_noise_does_not_become_rate_tracking_proof(self):
        import random
        random_source = random.Random(1292)
        data = rows(seconds=60)
        for row in data:
            row['ch1_raw'] = 75000 + random_source.randint(-100, 100)
        self.assertNotEqual(estimate_period(data)['status'], 'PERIOD_COHERENT_EXPLORATORY_ONLY')

    def test_frozen_c_replay_keeps_rr_events_distinct(self):
        with tempfile.TemporaryDirectory() as name:
            derived, events, digest = replay(rows(seconds=40), Path(name))
            self.assertEqual(len(digest), 64)
            self.assertGreater(len(events), 0)
            self.assertIn('resp_last_cycle_ms', events[-1])
            self.assertEqual(events[-1]['origin'], 'FROZEN_C_HOST_REPLAY_NOT_LIVE')
            self.assertEqual(len([k for k in FIELDS if k in derived[-1]]), 30)


class CaptureGateCases(unittest.TestCase):
    def test_real_slot_duplicate_and_conflict_export(self):
        def slot(seq, value=1):
            return b'\xc0\0\0' + value.to_bytes(3, 'big') * 2 + b'\0' * 3 + struct.pack('<III', seq, seq * 672000, seq * 4)
        for conflict in (False, True):
            with self.subTest(conflict=conflict), tempfile.TemporaryDirectory() as name:
                folder = Path(name);block = b''.join(slot(i) for i in range(1, 129))
                altered = slot(1, 2) + block[24:]
                chunks = [block, block, block, altered, altered] if conflict else [block, block]
                (folder / 'running-slots-private.bin').write_bytes(b''.join(chunks))
                ram = bytearray(131072);struct.pack_into('<I', ram, 0x140, 128);ram[0x1f30:0x1f30 + 3072] = block
                (folder / 'final-paused-ram-private.bin').write_bytes(ram)
                result = capture.export(folder)
                self.assertEqual(result['multi_repeat_conflicts'], int(conflict))
                self.assertEqual(result['stable_frames'], 127 if conflict else 128)
                if conflict:
                    with (folder / 'stable-raw-private.csv').open(newline='') as stream:
                        selected = [{k: int(v) for k, v in row.items() if k != 'integrity'} for row in csv.DictReader(stream)]
                    self.assertEqual(estimate_period(selected, result)['status'], 'NOT_EVALUATED_INPUT_INTEGRITY')

    def test_profile_source_identity_layout_duration(self):
        with tempfile.TemporaryDirectory() as name:
            profile = capture.prepare(Path(name) / 'profile.json')
            for key, value in [('schema', 'BIO_V2_CAPTURE_1'), ('layout', {}), ('duration_choices_s', [92]),
                               ('identity_reference_sha256', '0' * 64), ('sdk_call_limit', 9000), ('data_source', 'HUMAN')]:
                with self.subTest(key=key):
                    bad = copy.deepcopy(profile);bad[key] = value
                    with self.assertRaises(RuntimeError):
                        capture.validate(bad)
            bad_identity = json.loads(Path(profile['identity_reference']).read_text('utf-8'))
            bad_identity['device_id'] = 0x999
            with self.assertRaisesRegex(RuntimeError, 'DEVICE_ID_MISMATCH'):
                capture.check_identity(bad_identity)

    def test_tail_resume_exit_codes(self):
        receipt = {'status': 'RESP_CAPTURE_FILES_SAVED', 'tail_halt_confirmed': True, 'resume_confirmed': True, 'process_exit_code': 0}
        supervisor = {'worker_exit_code': 0, 'supervisor_exit_code': 0}
        require_capture_end(receipt, supervisor)
        for key in ('tail_halt_confirmed', 'resume_confirmed'):
            bad = dict(receipt);bad[key] = False
            with self.assertRaisesRegex(RuntimeError, 'UNCONFIRMED'):
                require_capture_end(bad, supervisor)
        with self.assertRaisesRegex(RuntimeError, 'EXIT_NONZERO'):
            require_capture_end(receipt, {'worker_exit_code': 1, 'supervisor_exit_code': 1})

    def test_sdk_write_and_reset_denied_without_dll(self):
        # 不构造Link，不加载DLL；拒绝检查必须先于任何父类SDK调用。
        link = object.__new__(capture.RespLink)
        link.counts = {'sdk_calls': 0, 'halt_requests': 0, 'go_requests': 0}
        with self.assertRaisesRegex(RuntimeError, 'FUNCTION_DENIED'):
            link.call('JLINKARM_Reset')
        with self.assertRaisesRegex(RuntimeError, 'READ_SCOPE'):
            link.read(0x20000004, 4)
        with self.assertRaisesRegex(RuntimeError, 'DEBUG_POLICY_DENIED'):
            link.call('JLINKARM_ExecCommand', b'SetRESET', None, 0)
        self.assertEqual(link.counts['sdk_calls'], 0)


if __name__ == '__main__':
    unittest.main(verbosity=2)
