"""E3协议离线检查；合成波形只验证工具，绝不写成实板通过。"""
import copy
import hashlib
import json
import math
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import resp_matrix_b as capture
import analyze_resp_matrix_b as analysis
from readback_b import Link, sha
from resp_exploratory import estimate_period


def planned_source(cell='12-r1'):
    return {'schema': capture.SOURCE_SCHEMA, 'source_type': 'RESP_EXPLORATORY', 'stage': 'E3',
        'cell': cell, 'target_rpm': int(cell.split('-')[0]), 'nominal_rpm': None,
        'mode': 'INDEPENDENT_RESPIRATION', 'data_source': 'ENGINEERING_NONHUMAN',
        'leads': capture.capture.LEADS.copy(), 'battery_only': True, 'usb_disconnected': True,
        'CAN_A_C_human_disconnected': True, 'Z0_ohm': None, 'delta_Zpp_ohm': None, 'reference_rpm': None,
        'dynamic_pair': 'MANUFACTURER_MANUAL_RA_LL', 'impedance_calibration': 'NOT_CALIBRATED',
        'manual_sha256': capture.capture.MANUAL_SHA, 'acceptance_class': 'NOMINAL_RATE_MATCH',
        'operator_ready': False, 'menu_confirmed': False,
        'apnea_semantics': 'ZERO_DISPLAY_RECORDED_SEMANTICS_UNVERIFIED',
        'menu': {'mode_literal': '呼吸波形', 'amplitude_literal': '1.5R', 'waveform_period_literal': '20bpm',
                 'respiration_rate_literal': None, 'ecg_rate_literal': '60BPM', 'apnea_literal': '0s'}}


def diagnostics(rate=12, anchor=1000):
    # 原始前45秒均无效，评价段每秒一个有效点；验证启动无效不会进入稳态分母。
    return [{'last_sample_ms': (anchor+ms) & 0xffffffff, 'rpm': rate,
             'rpm_valid': int(ms >= 45000), 'rpm_reason': 2 if ms < 45000 else 0}
            for ms in range(0, 137000, 1000)]


def coherent(rate=12):
    return {'status': 'PERIOD_COHERENT_EXPLORATORY_ONLY', 'time_domain_rpm': rate}


def summaries():
    result = []
    for cell in capture.CELLS:
        r = analysis.validity(coherent(int(cell.split('-')[0])), diagnostics(int(cell.split('-')[0]))[45:135], [], int(cell.split('-')[0]), 1000)
        r.update(stage='E3', cell=cell, criteria=copy.deepcopy(capture.CRITERIA), tools_sha256=capture.bindings(),
                 bio_source_sha256=analysis.SOURCE_SHA, independent_raw_estimate=coherent(int(cell.split('-')[0])))
        for key in ('capture_receipt_sha256', 'raw_csv_sha256', 'source_record_sha256', 'profile_sha256', 'card_sha256'):
            r[key] = 'SYNTHETIC-'+cell+'-'+key
        result.append(r)
    return result


class MatrixTests(unittest.TestCase):
    def test_plan_retains_unknown_actual_rate_and_is_not_ready(self):
        source = planned_source()
        capture.validate_source(source, '12-r1')
        with self.assertRaisesRegex(RuntimeError, 'RATE_NOT_SET'):
            capture.validate_source(source, '12-r1', ready=True)

    def test_30_menu_cannot_authorize_12_target(self):
        source = planned_source(); source.update(operator_ready=True, menu_confirmed=True, nominal_rpm=30)
        source['menu']['respiration_rate_literal'] = '30bpm'
        with self.assertRaisesRegex(RuntimeError, 'RATE_NOT_SET'):
            capture.validate_source(source, '12-r1', ready=True)

    def test_truth_controls_and_path_rejected(self):
        for key, value in [('source_type', 'ORDINARY_ECG'), ('Z0_ohm', 1000), ('delta_Zpp_ohm', 1.5),
                           ('reference_rpm', 12), ('usb_disconnected', False), ('cell', '12-r2')]:
            source = planned_source(); source[key] = value
            with self.assertRaises(RuntimeError): capture.validate_source(source, '12-r1')
        source = planned_source(); source['menu']['waveform_period_literal'] = '30bpm'
        with self.assertRaisesRegex(RuntimeError, 'CONTROLS'): capture.validate_source(source, '12-r1')

    def test_ready_source_requires_hashed_owner_and_electrical_basis(self):
        with tempfile.TemporaryDirectory() as directory:
            owner = Path(directory)/'owner.txt'; owner.write_text('已设置12，其余不变，按卡执行两轮', encoding='utf-8')
            safety = Path(directory)/'safety.json'
            facts = {'status': 'CONFIRMED_FOR_E3_RA_LL_137S', 'electrical_basis': '既有源端DC及RA–LL实板记录，非32kHz隔离认证'}
            facts.update({k: True for k in ('RA_LL_setup_owner_reported', 'battery_no_USB', 'no_grounded_instrument',
                'meter_removed_OFF', 'CAN_A_C_human_disconnected', 'no_shorts_or_abnormalities')})
            safety.write_text(json.dumps(facts), encoding='utf-8')
            source = planned_source(); source.update(operator_ready=True, menu_confirmed=True, nominal_rpm=12,
                owner_confirmation=owner.read_text('utf-8'), owner_confirmation_record=str(owner), owner_confirmation_sha256=sha(owner),
                safety_record=str(safety), safety_record_sha256=sha(safety))
            source['menu']['respiration_rate_literal'] = '12bpm'
            capture.validate_source(source, '12-r1', ready=True)
            owner.write_text('变更', encoding='utf-8')
            with self.assertRaisesRegex(RuntimeError, 'CONFIRMATION_BINDING'): capture.validate_source(source, '12-r1', ready=True)

    def test_old_45s_profile_and_old_evaluation_rejected(self):
        with self.assertRaisesRegex(RuntimeError, 'OLD_PROFILE'): capture.validate_profile({'schema': 'RESP_RA_LL30_CAPTURE_45S_1'})
        p = {'schema': capture.PROFILE_SCHEMA, 'source_schema': capture.SOURCE_SCHEMA, 'cell': '12-r1',
             'scope': capture.SCOPE, 'duration_s': 45, 'slot_limit': capture.SLOT_LIMIT, 'criteria': capture.CRITERIA}
        with self.assertRaisesRegex(RuntimeError, 'TIMING_CRITERIA'): capture.validate_profile(p)

    def test_phases_exclude_startup_and_tail_even_across_uint32_wrap(self):
        for anchor in (1000, 0xfffff000):
            live = diagnostics(anchor=anchor)
            rows = [{'device_ms': (anchor+ms) & 0xffffffff} for ms in range(0, 137000, 4)]
            actual_anchor, selected, warmup, steady, eligible = analysis.select_phases(rows, live)
            self.assertEqual((len(selected), len(steady), len(warmup), len(eligible)), (34250, 22500, 45, 90))
            self.assertEqual(actual_anchor, anchor)
            self.assertEqual(analysis.validity(coherent(), eligible, [], 12, anchor)['analysis_exit_code'], 0)

    def test_single_steady_failure_or_bad_reason_cannot_be_dropped(self):
        for field, value in [('rpm_valid', 0), ('rpm_reason', 128), ('rpm', 14)]:
            live = diagnostics()[45:135]; live[20][field] = value
            self.assertEqual(analysis.validity(coherent(), live, [], 12, 1000)['analysis_exit_code'], 3)
        self.assertEqual(analysis.validity(coherent(), diagnostics()[45:135], ['SEQUENCE_GAP'], 12, 1000)['analysis_exit_code'], 2)

    def test_sparse_missing_edges_or_long_gap_cannot_pass(self):
        live = diagnostics()[45:135]
        for subset in (live[::3], live[3:], live[:-3], live[:20]+live[24:]):
            self.assertFalse(analysis.validity(coherent(), subset, [], 12, 1000)['saved_observation_coverage_pass'])

    def test_nominal_match_requires_independent_raw_match(self):
        self.assertEqual(analysis.validity(coherent(20), diagnostics()[45:135], [], 12, 1000)['analysis_exit_code'], 3)

    def test_three_90s_synthetic_periods_without_rate_prior(self):
        for rate in (12, 18, 24):
            # 不向估计器传目标频率；纯正弦只是工具测试，不是模拟器/实板数据。
            rows = [{'source_seq': i+1, 'device_ms': i*4, 'flags_raw': 0,
                     'ch1_raw': int(600*math.sin(2*math.pi*rate/60*i*.004))} for i in range(22500)]
            estimate = estimate_period(rows)
            self.assertEqual(estimate['status'], 'PERIOD_COHERENT_EXPLORATORY_ONLY')
            self.assertLessEqual(abs(estimate['time_domain_rpm']-rate), .2)

    def test_all_six_and_independent_originals_required(self):
        data = summaries()
        self.assertEqual(analysis.aggregate(data)['matrix_exit_code'], 0)
        for bad in (data[:-1], data[:-1]+[data[0]]):
            with self.assertRaisesRegex(RuntimeError, 'SIX_DISTINCT'): analysis.aggregate(bad)
        bad = copy.deepcopy(data); bad[1]['raw_csv_sha256'] = bad[0]['raw_csv_sha256']
        with self.assertRaisesRegex(RuntimeError, 'REUSED_ORIGINAL'): analysis.aggregate(bad)
        bad = copy.deepcopy(data); bad[0].update(analysis_exit_code=3, status='E3_CELL_NOT_PASS')
        self.assertEqual(analysis.aggregate(bad)['matrix_exit_code'], 3)

    def test_repeat_difference_cannot_be_averaged_away(self):
        data = summaries(); data[1]['independent_raw_estimate']['time_domain_rpm'] = 13.1
        self.assertEqual(analysis.aggregate(data)['matrix_exit_code'], 3)

    def fake_link(self):
        link = capture.MatrixLink.__new__(capture.MatrixLink)
        link.counts = {'sdk_calls': 4001, 'reset_requests': 0, 'halt_requests': 0, 'go_requests': 0}
        link.read_counts = {}; link.function_counts = {}; link.reset_phase = False
        link.alias_phase = False; link.register_reads_allowed = False
        return link

    def test_new_sdk_budget_counts_once_and_controls_still_bounded(self):
        link = self.fake_link()
        with patch.object(Link, 'call', return_value=0) as sdk:
            link.call('JLINKARM_Go'); self.assertEqual(link.counts['sdk_calls'], 4002)
            link.call('JLINKARM_Go')
            with self.assertRaisesRegex(RuntimeError, 'CONTROL_BUDGET'): link.call('JLINKARM_Go')
            with self.assertRaisesRegex(RuntimeError, 'RESET_PHASE'): link.call('JLINKARM_Reset')
            link.reset_phase = True; link.call('JLINKARM_Reset')
            with self.assertRaisesRegex(RuntimeError, 'CONTROL_BUDGET'): link.call('JLINKARM_Reset')
            self.assertEqual(sdk.call_count, 3)

    def test_writes_rom_reads_alias_and_repeated_flash_denied(self):
        link = self.fake_link()
        with patch.object(Link, 'call', return_value=0):
            with self.assertRaisesRegex(RuntimeError, 'FUNCTION_DENIED'): link.call('JLINKARM_WriteMem', 0, 4, None)
            for address in (0x1fff0000, 0x40023874):
                with self.assertRaisesRegex(RuntimeError, 'READ_SCOPE'): link.call('JLINKARM_ReadMemEx', address, 4, None, 0)
            with self.assertRaisesRegex(RuntimeError, 'ALIAS_PHASE'): link.call('JLINKARM_ReadMemEx', 0, 64, None, 0)
            for _ in range(2): link.call('JLINKARM_ReadMemEx', 0x08000000, 1048576, None, 0)
            with self.assertRaisesRegex(RuntimeError, 'ADDRESS_READ_BUDGET'): link.call('JLINKARM_ReadMemEx', 0x08000000, 1048576, None, 0)
            link.counts['sdk_calls'] = capture.SDK_LIMIT
            with self.assertRaisesRegex(RuntimeError, 'SDK_BUDGET'): link.call('JLINKARM_Go')

    def test_360s_gate_overrides_old_240s_but_keeps_stop_error(self):
        with tempfile.TemporaryDirectory() as directory:
            link = self.fake_link(); link.out = Path(directory); link.started = 0; link.error = False
            with patch.object(capture.time, 'monotonic', return_value=300): link.gate()
            with patch.object(capture.time, 'monotonic', return_value=361):
                with self.assertRaisesRegex(RuntimeError, 'SESSION_TIMEOUT'): link.gate()
            (link.out/'STOP').touch()
            with self.assertRaisesRegex(RuntimeError, 'OWNER_STOP'): link.gate()

    def test_137s_collector_and_tail_use_one_window_not_old_45s(self):
        # 虚拟时钟和内存替身验证完整新窗口，不等待137秒，也不加载任何SDK。
        clock = [0.0]
        class MemoryLink:
            halted = False
            calls = []
            slots = 0
            def u32(self, address):
                clock[0] += .001
                return capture.HALT if self.halted else 0
            def read(self, address, size):
                clock[0] += .001
                if size == 3072: self.slots += 1
                return bytes(size)
            def call(self, name, **kwargs):
                self.calls.append(name)
                self.halted = name == 'JLINKARM_Halt'
                return 0
            def stable_halt(self):
                if not self.halted: raise RuntimeError('TEST_NOT_HALTED')
        registers = bytes.fromhex('7301e0f04040ec0000ea030c')
        diagnostic = {'resp_raw': 0, 'ecg_raw': 0, 'registers_hex': registers.hex(),
                      'adc': dict.fromkeys(('init_errors', 'spi_errors', 'bad_status', 'queue_overflow'), 0)}
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory); reference = folder/'reference.json'
            reference.write_text(json.dumps({'uid_hex': 'SYNTHETIC', 'optcr': 0}), encoding='utf-8')
            binding = {'flash_sha256': hashlib.sha256(bytes(1048576)).hexdigest(),
                       'options_sha256': hashlib.sha256(bytes(16)).hexdigest(), 'identity_reference': str(reference)}
            link = MemoryLink(); receipt = {}
            with patch.object(capture.time, 'monotonic', side_effect=lambda: clock[0]), \
                 patch.object(capture.time, 'sleep', side_effect=lambda seconds: clock.__setitem__(0, clock[0]+seconds)), \
                 patch.object(capture.base, 'snapshot', return_value=diagnostic), \
                 patch.object(capture, 'identity', return_value={'uid_hex': 'SYNTHETIC', 'optcr': 0}), \
                 patch.object(capture, 'check_identity'):
                capture.collect(link, binding, folder, receipt)
            self.assertGreaterEqual(receipt['window_elapsed_s'], 137)
            self.assertLess(receipt['window_elapsed_s'], 137.1)
            self.assertGreater(link.slots, 2700)
            self.assertLessEqual(link.slots, capture.SLOT_LIMIT)
            self.assertEqual(link.calls, ['JLINKARM_Halt', 'JLINKARM_Go'])
            self.assertTrue(receipt['tail_halt_confirmed'] and receipt['resume_confirmed'])


if __name__ == '__main__':
    unittest.main()
