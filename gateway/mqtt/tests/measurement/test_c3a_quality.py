"""逐指标质量负向检查：不用设备，合成字节不会冒充已有两轮真机快照。"""

import copy
from pathlib import Path
import tempfile
import unittest

from analyze_c3a_quality import analyze_pair, extract, halt_interval, rate, tick_quality
from r2_snapshot_bytes import EXPECTED_BIN, ROOT, InvalidSnapshot, load_layout, sha
from test_r2_snapshot_bytes import LAYOUT, synthetic_state


class QualityTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.layout = load_layout(LAYOUT)
        cls.build = ROOT / 'gateway/mqtt/build/c3a-quality-tests'
        cls.build.mkdir(parents=True, exist_ok=True)

    def setUp(self):
        self.data = synthetic_state(self.layout)
        types = self.layout['variants']['P5']['types']
        self.identity = {'node': 1, 'stream': 0, 'seq': 40, 'epoch': 111, 'boot': 65537}
        base = types['ProbeState']['fields']['first_business_id']
        for name, value in self.identity.items():
            at = base + types['ProbeFrameId']['fields'][name]
            self.data[at:at + 4] = value.to_bytes(4, 'little')
        self.raw = extract(self.data, self.layout, 'P5')
        self.meta = {
            'variant': 'P5', 'bin_sha256': EXPECTED_BIN['P5'],
            'snapshot_read1_sha256': sha(self.data), 'snapshot_read2_sha256': sha(self.data),
            'registers_at_halt': {'IPSR': 0, 'XPSR': 0x01000000},
            'host_qpc_events_us': {'D_SENT': 0, 'HALT': 20, 'READ1_DONE': 30,
                                  'READ2_DONE': 40, 'SNAPSHOT_PERSISTED': 50, 'RESUME': 60},
            'pause_control_transaction_upper_bound_us': 50,
            'HALT_request_us_derived_from_recorded_elapsed': 10,
            'first_business_numeric_identity': self.identity,
            'broker_correlated_after_OFFLINE': {'first_VALID_business': {
                'node': 'NODE-A', 'stream': 'PPG', 'seq': 40, 'session_id': 'can-111-65537',
                'synthetic': True, 'validity': 'VALID', 'source': 'MOCK'}},
            'strict_decode_status': 'PROBE_LOSS_OR_UNSTABLE_HALT',
        }

    def analyze(self):
        return rate(self.raw, self.meta)

    def test_historical_tick_loss_is_retained_and_not_new_window_loss(self):
        self.raw.update(irq_flags=32, tick_dropped=5, tick_drop_base=5)
        before = copy.deepcopy(self.raw)
        result = self.analyze()
        self.assertEqual(result['tick_quality']['status'], 'PRE_WINDOW_CUMULATIVE_LOSS_ONLY')
        self.assertEqual(result['tick_quality']['window_new_tick_drops'], 0)
        self.assertEqual(result['raw_observation']['irq_flags'], 32)
        self.assertEqual(result['raw_observation']['tick_dropped'], 5)
        self.assertEqual(self.raw, before)
        self.assertTrue(result['metrics']['M02']['limited_observation_usable'])
        self.assertEqual(result['original_strict_decode_status'], 'PROBE_LOSS_OR_UNSTABLE_HALT')

    def test_new_window_drop_invalidates_M02_without_erasing_heap_or_network(self):
        self.raw.update(irq_flags=32, tick_dropped=6, tick_drop_base=5)
        result = self.analyze()
        self.assertEqual(result['tick_quality']['window_new_tick_drops'], 1)
        self.assertEqual(result['metrics']['M02']['grade'], 'INVALID')
        self.assertEqual(result['metrics']['M05']['grade'], 'LIMITED_OBSERVATION')
        self.assertEqual(result['metrics']['M06']['grade'], 'LIMITED_OBSERVATION')

    def test_current_foreground_loss_flag_is_not_treated_as_startup(self):
        self.raw.update(irq_flags=32, foreground_flags=96, tick_dropped=5, tick_drop_base=5)
        self.assertEqual(self.analyze()['metrics']['M02']['grade'], 'INVALID')

    def test_tick_counter_regression_is_unknown_not_zero(self):
        self.raw.update(irq_flags=32, tick_dropped=4, tick_drop_base=5)
        result = self.analyze()
        self.assertIsNone(result['tick_quality']['window_new_tick_drops'])
        self.assertEqual(result['metrics']['M02']['grade'], 'INVALID')

    def test_lifetime_flag_without_matching_counter_is_rejected(self):
        self.raw['irq_flags'] = 32
        self.assertEqual(tick_quality(self.raw)['status'], 'LIFETIME_FLAG_COUNTER_CONFLICT')
        self.assertEqual(self.analyze()['metrics']['M02']['grade'], 'INVALID')

    def test_pending_tick_is_unfinished_service_not_completed_sample_loss(self):
        self.raw['tick_head'] += 1
        result = self.analyze()
        self.assertEqual(result['tick_quality']['pending_at_freeze'], 1)
        self.assertTrue(result['metrics']['M02']['limited_observation_usable'])
        self.assertFalse(result['metrics']['M02']['full_window_maximum_complete'])
        self.raw['tick_head'] += 16
        self.assertEqual(self.analyze()['metrics']['M02']['grade'], 'INVALID')

    def test_active_span_preserves_completed_calls_but_not_full_window_max(self):
        self.raw.update(depth=1, active_spans=[{'scope': 1, 'generation': 1}])
        result = self.analyze()
        self.assertTrue(result['metrics']['M01']['completed_statistics_usable'])
        self.assertEqual(result['metrics']['M01']['active_scopes'], ['PUBLISH_Q0'])
        self.assertFalse(result['metrics']['M01']['full_window_maximum_complete'])
        self.assertEqual(result['metrics']['M01']['values']['PUBLISH_Q1']['success'], 1)

    def test_bad_span_or_aggregate_does_not_grant_completed_statistics(self):
        self.raw['aggregate'][2]['direct_child_cycles'] = 9999
        result = self.analyze()
        self.assertEqual(result['metrics']['M01']['grade'], 'INVALID')
        self.assertEqual(result['metrics']['M03']['grade'], 'PARTIAL')
        self.assertFalse(result['metrics']['M03']['limited_observation_usable'])
        self.assertEqual(result['metrics']['M05']['grade'], 'LIMITED_OBSERVATION')

    def test_clock_failure_blocks_time_metrics_independently_of_counters(self):
        self.raw['irq_flags'] = 2
        result = self.analyze()
        for key in ('M01', 'M02', 'M06'):
            self.assertEqual(result['metrics'][key]['grade'], 'INVALID')
        self.assertEqual(result['metrics']['M05']['grade'], 'LIMITED_OBSERVATION')
        self.assertEqual(result['metrics']['M07']['grade'], 'LIMITED_OBSERVATION')
        self.assertFalse(result['metrics']['M07']['values']['live_replay_time_usable'])

    def test_M03_PARTIAL_and_M04_BLOCKED_are_never_promoted(self):
        for bits in (0, 2, 256):
            self.raw['irq_flags'] = bits
            result = self.analyze()
            self.assertEqual(result['metrics']['M03']['grade'], 'PARTIAL')
            self.assertEqual(result['metrics']['M04']['grade'], 'BLOCKED')
            self.assertFalse(any(x['acceptance_pass'] for x in result['metrics'].values()))

    def test_missing_network_point_or_wrong_business_identity_only_blocks_M06(self):
        self.raw['network_valid_mask'] = 255
        self.assertEqual(self.analyze()['metrics']['M06']['grade'], 'INVALID')
        self.assertEqual(self.analyze()['metrics']['M05']['grade'], 'LIMITED_OBSERVATION')
        self.raw['network_valid_mask'] = 511
        self.meta['broker_correlated_after_OFFLINE']['first_VALID_business']['seq'] = 99
        self.assertEqual(self.analyze()['metrics']['M06']['grade'], 'INVALID')

    def test_heap_overflow_or_ENOMEM_regression_does_not_corrupt_other_grades(self):
        self.raw['heap_peak_bytes'] = 24577
        self.assertEqual(self.analyze()['metrics']['M05']['grade'], 'INVALID')
        self.assertEqual(self.analyze()['metrics']['M06']['grade'], 'LIMITED_OBSERVATION')
        self.raw.update(heap_peak_bytes=9400, heap_enomem_count=0, heap_error_base=1)
        self.assertIsNone(self.analyze()['metrics']['M05']['values']['window_ENOMEM_delta'])

    def test_cache_regression_and_false_drain_are_rejected(self):
        self.raw['cache_after']['lost'] = 202
        self.assertEqual(self.analyze()['metrics']['M07']['grade'], 'INVALID')
        self.raw['cache_after']['lost'] = 203
        self.raw['cache_after']['cache'] = 32
        self.assertEqual(self.analyze()['metrics']['M07']['grade'], 'INVALID')
        self.assertEqual(self.analyze()['metrics']['M05']['grade'], 'LIMITED_OBSERVATION')

    def test_halt_confirmation_is_an_interval_not_exact_stop_or_pause(self):
        result = halt_interval(self.meta)
        self.assertEqual(result['possible_cpu_stop_us'], [10, 20])
        self.assertFalse(result['confirm_is_actual_stop'])
        self.assertIsNone(result['exact_cpu_stop_us'])
        self.assertIsNone(result['exact_cpu_pause_us'])

    def test_conflicting_halt_request_rejects_timing_without_erasing_heap(self):
        self.meta['HALT_request_us_derived_from_recorded_elapsed'] = 21
        result = self.analyze()
        self.assertEqual(result['halt_timing']['grade'], 'INVALID')
        self.assertEqual(result['metrics']['M05']['grade'], 'LIMITED_OBSERVATION')
        self.assertEqual(result['whole_window_acceptance'], 'NOT_QUALIFIED')

    def test_independent_pair_hash_check_preserves_input_bytes(self):
        with tempfile.TemporaryDirectory(dir=self.build) as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(self.build.resolve()))
            one, two = Path(folder) / 'one.bin', Path(folder) / 'two.bin'
            one.write_bytes(self.data); two.write_bytes(self.data)
            result = analyze_pair(one, two, self.layout, self.meta)
            self.assertEqual(result['snapshot_sha256'], sha(self.data))
            self.assertEqual(one.read_bytes(), self.data)
            self.assertEqual(two.read_bytes(), self.data)
            two.write_bytes(self.data[:-1] + b'X')
            with self.assertRaisesRegex(InvalidSnapshot, 'ORIGINAL_SNAPSHOT_HASH_MISMATCH'):
                analyze_pair(one, two, self.layout, self.meta)

    def test_same_file_or_wrong_firmware_cannot_be_reclassified(self):
        with self.assertRaisesRegex(InvalidSnapshot, 'INDEPENDENT_FILES_REQUIRED'):
            analyze_pair(Path('same.bin'), Path('same.bin'), self.layout, self.meta)
        with tempfile.TemporaryDirectory(dir=self.build) as folder:
            self.assertTrue(Path(folder).resolve().is_relative_to(self.build.resolve()))
            one, two = Path(folder) / 'one.bin', Path(folder) / 'two.bin'
            one.write_bytes(self.data); two.write_bytes(self.data)
            self.meta['bin_sha256'] = '0' * 64
            with self.assertRaisesRegex(InvalidSnapshot, 'MEASUREMENT_FIRMWARE_IDENTITY'):
                analyze_pair(one, two, self.layout, self.meta)


if __name__ == '__main__':
    unittest.main()
