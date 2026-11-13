"""只验证新脱机解析器的真实边界：回绕、口径、样本、时序和演示不得冒充验收。"""
import copy
import json
from pathlib import Path
import unittest

from analyze_h16 import analyze, cycle_delta, unique_object, InvalidObservation

FIXTURE = Path(__file__).parent / 'fixtures/h16-synthetic-demo.json'


class H16OfflineTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text(encoding='utf-8'))

    def test_demo_does_not_grant_hardware_acceptance(self):
        result = analyze(self.data)
        self.assertEqual(result['verdict'], 'SIMULATION_ONLY')
        self.assertEqual(result['H16_acceptance'], 'NOT_GRANTED')
        self.assertFalse(result['hardware_tests_executed'])
        self.assertAlmostEqual(result['network_comparison']['median_regression_percent'], 10)

    def test_fixed_fault_pause_excluded_from_network_comparison(self):
        self.data['runs'][3]['network']['fault_command_us'] = 0
        result = analyze(self.data)
        self.assertEqual(result['network_comparison']['median_regression_percent'], 10)
        self.assertNotEqual(result['runs'][0]['network']['D_to_business_frame_us'],
                            result['runs'][0]['network']['network_reconnect_us'])

    def test_uint32_single_wrap_is_reconstructed(self):
        sample = {'metric': 'M01', 'scope': 'publish_qos1', 'outcome': 'SUCCESS',
                  'start': 0xfffffff0, 'end': 0x20, 'elapsed_upper_bound_us': 10}
        self.assertEqual(cycle_delta(sample, 16_000_000), 48)

    def test_multiple_wrap_cannot_be_guessed(self):
        sample = copy.deepcopy(self.data['runs'][0]['cycle_samples'][0])
        sample['elapsed_upper_bound_us'] = 300_000_000
        with self.assertRaisesRegex(InvalidObservation, 'AMBIGUOUS_COUNTER_WRAP'):
            cycle_delta(sample, 16_000_000)

    def test_counter_interval_bound_is_enforced(self):
        sample = copy.deepcopy(self.data['runs'][0]['cycle_samples'][0])
        sample['end'] = sample['start'] + 1000
        sample['elapsed_upper_bound_us'] = 1
        with self.assertRaisesRegex(InvalidObservation, 'COUNTER_EXCEEDS_INTERVAL_BOUND'):
            cycle_delta(sample, 16_000_000)

    def test_two_runs_are_insufficient(self):
        self.data['runs'].pop()
        result = analyze(self.data)
        self.assertEqual(result['network_comparison']['status'], 'INSUFFICIENT_SAMPLES')
        self.assertNotIn('median_regression_percent', result['network_comparison'])

    def test_environment_drift_blocks_comparison(self):
        self.data['runs'][3]['environment_id'] = 'env-other'
        self.assertEqual(analyze(self.data)['network_comparison']['status'], 'NOT_COMPARABLE')

    def test_endpoint_clock_or_measurement_bin_drift_blocks_comparison(self):
        for key, value in [('endpoint', 'BROKER_RECEIVE'), ('clock_domain', 'HOST_QPC_US')]:
            data = copy.deepcopy(self.data)
            for run in data['runs'][3:]:
                run['network'][key] = value
            self.assertEqual(analyze(data)['network_comparison']['status'], 'NOT_COMPARABLE')
        self.data['runs'][5]['measurement_bin_sha256'] = '3' * 64
        self.assertEqual(analyze(self.data)['network_comparison']['status'], 'NOT_COMPARABLE')

    def test_lost_observations_or_debugger_pause_do_not_count_as_valid_samples(self):
        for key, value in [('dropped_observations', 1), ('observer_paused_run', True), ('valid', False)]:
            data = copy.deepcopy(self.data)
            data['runs'][0][key] = value
            self.assertEqual(analyze(data)['network_comparison']['status'], 'INSUFFICIENT_SAMPLES')

    def test_twenty_percent_is_review_boundary_and_not_auto_pass(self):
        for run in self.data['runs'][3:]:
            run['network']['first_valid_telemetry_us'] = run['network']['recovery_start_us'] + 1_200_000
        comparison = analyze(self.data)['network_comparison']
        self.assertFalse(comparison['review_required_over_20_percent'])
        self.data['runs'][4]['network']['first_valid_telemetry_us'] += 100
        self.data['runs'][5]['network']['first_valid_telemetry_us'] += 100
        result = analyze(self.data)
        self.assertTrue(result['network_comparison']['review_required_over_20_percent'])
        self.assertEqual(result['H16_acceptance'], 'NOT_GRANTED')

    def test_node_status_is_not_first_valid_business_frame(self):
        self.data['runs'][0]['network']['first_stream'] = 'NODE_STATUS'
        with self.assertRaisesRegex(InvalidObservation, 'FIRST_FRAME_NOT_VALID_BUSINESS_STREAM'):
            analyze(self.data)

    def test_invalid_frame_or_crossed_timestamp_is_rejected(self):
        data = copy.deepcopy(self.data)
        data['runs'][0]['network']['validity'] = 'STALE'
        with self.assertRaises(InvalidObservation):
            analyze(data)
        self.data['runs'][0]['network']['tls_ready_us'] = 0
        with self.assertRaisesRegex(InvalidObservation, 'NETWORK_EVENT_ORDER'):
            analyze(self.data)

    def test_unsafe_stack_observation_is_not_accepted(self):
        self.data['runs'][0]['memory']['stack_region_verified'] = False
        with self.assertRaisesRegex(InvalidObservation, 'STACK_REGION_UNVERIFIED'):
            analyze(self.data)

    def test_unmeasured_stack_is_not_reservation_as_measurement(self):
        memory = self.data['runs'][0]['memory']
        memory.update(stack_method='NOT_MEASURED', stack_min_free_bytes=None)
        self.assertIn('M04', analyze(self.data)['not_measured'])
        memory['stack_min_free_bytes'] = 8192
        with self.assertRaisesRegex(InvalidObservation, 'UNMEASURED_STACK_HAS_VALUE'):
            analyze(self.data)

    def test_cache_loss_and_not_drained_remain_visible(self):
        result = analyze(self.data)['runs'][0]['cache']
        self.assertEqual(result['lost'], 3)
        self.assertFalse(result['lossless_observed'])
        self.assertFalse(result['cache_drained_observed'])
        self.data['runs'][0]['cache']['drained_observed'] = True
        with self.assertRaisesRegex(InvalidObservation, 'CACHE_DRAIN_CLAIM_CONFLICT'):
            analyze(self.data)

    def test_unknown_fields_and_non_synthetic_input_are_rejected(self):
        data = copy.deepcopy(self.data)
        data['credential'] = 'DEMO_VALUE_NEVER_PRINTED'
        with self.assertRaisesRegex(InvalidObservation, 'SCHEMA_KEYS'):
            analyze(data)
        self.data['synthetic'] = False
        with self.assertRaisesRegex(InvalidObservation, 'SYNTHETIC_SCOPE'):
            analyze(self.data)

    def test_baseline_drift_and_duplicate_runs_are_rejected(self):
        data = copy.deepcopy(self.data)
        data['baselines']['P5']['production_bin_sha256'] = '0' * 64
        with self.assertRaisesRegex(InvalidObservation, 'BASELINE_IDENTITY'):
            analyze(data)
        self.data['runs'][1]['run_id'] = self.data['runs'][0]['run_id']
        with self.assertRaisesRegex(InvalidObservation, 'DUPLICATE_RUN_ID'):
            analyze(self.data)

    def test_missing_cycles_and_invalid_boolean_counts_do_not_become_measurements(self):
        self.data['runs'][0]['cycle_samples'] = []
        self.assertIn('M01', analyze(self.data)['not_measured'])
        self.data['runs'][0]['core_clock_hz'] = True
        with self.assertRaisesRegex(InvalidObservation, 'INTEGER_RANGE'):
            analyze(self.data)

    def test_unknown_heap_failure_count_is_not_zero(self):
        self.data['runs'][0]['memory']['heap_failure_count'] = None
        result = analyze(self.data)
        self.assertIn('M05_FAILURE_COUNT', result['not_measured'])
        self.assertIsNone(result['runs'][0]['memory']['heap_failure_count'])

    def test_replay_before_live_is_visible_and_does_not_grant_acceptance(self):
        self.data['runs'][0]['cache']['first_replay_us'] = 0
        result = analyze(self.data)
        self.assertFalse(result['runs'][0]['cache']['live_before_replay'])
        self.assertEqual(result['H16_acceptance'], 'NOT_GRANTED')

    def test_duplicate_json_keys_are_not_silently_overwritten(self):
        with self.assertRaisesRegex(InvalidObservation, 'DUPLICATE_JSON_KEY'):
            json.loads('{"valid": false, "valid": true}', object_pairs_hook=unique_object)

    def test_frozen_memory_capacity_or_variant_binary_drift_is_rejected(self):
        data = copy.deepcopy(self.data)
        data['runs'][0]['memory']['heap_limit_bytes'] = 32768
        with self.assertRaisesRegex(InvalidObservation, 'MEMORY_RESERVATION_DRIFT'):
            analyze(data)
        data = copy.deepcopy(self.data)
        data['runs'][0]['cache']['capacity'] = 64
        with self.assertRaisesRegex(InvalidObservation, 'CACHE_CAPACITY_DRIFT'):
            analyze(data)
        for run in self.data['runs'][3:]:
            run['measurement_bin_sha256'] = '1' * 64
        self.assertEqual(analyze(self.data)['network_comparison']['status'], 'NOT_COMPARABLE')


if __name__ == '__main__':
    unittest.main()
