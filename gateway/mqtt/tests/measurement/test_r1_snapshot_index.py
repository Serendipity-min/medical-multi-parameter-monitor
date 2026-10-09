"""R1只检验拒绝路径；所有样本都是脱机索引样本，不能代表真机快照。"""

import copy
import json
from pathlib import Path
import unittest

from r1_snapshot_index import InvalidIndex, validate_index


FIXTURE = Path(__file__).parent / 'fixtures/r1-snapshot-index-synthetic.json'
EVENTS = Path(__file__).parent / 'fixtures/r2-synthetic-event-log.json'


class SnapshotIndexTests(unittest.TestCase):
    def setUp(self):
        self.data = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.log = json.loads(EVENTS.read_text(encoding='utf-8'))

    def validate(self, data=None):
        # R2起索引必须同时核对独立事件链；旧布尔值不再单独放行。
        return validate_index(self.data if data is None else data, self.log)

    def test_synthetic_index_never_grants_hardware_acceptance(self):
        result = self.validate()
        self.assertEqual(result['status'], 'INDEX_CONSISTENCY_ONLY')
        self.assertEqual(result['H16_acceptance'], 'NOT_GRANTED')
        self.assertFalse(result['physical_identity_verified'])

    def test_next_d_overwrites_first_window(self):
        self.data['runs'][0]['window_generation'] = 2
        with self.assertRaisesRegex(InvalidIndex, 'WINDOW_OVERWRITTEN_OR_GENERATION_GAP'):
            self.validate()

    def test_frozen_snapshot_copies_disagree(self):
        self.data['runs'][0]['snapshot_sha_second'] = 'f' * 64
        with self.assertRaisesRegex(InvalidIndex, 'INCONSISTENT_FROZEN_SNAPSHOT'):
            self.validate()

    def test_missing_one_of_three_windows(self):
        self.data['runs'].pop(1)
        with self.assertRaisesRegex(InvalidIndex, 'THREE_WINDOWS_PER_VARIANT_REQUIRED'):
            self.validate()

    def test_initial_join_or_retry_does_not_mimic_window_generation(self):
        # gateway_network_open在初次入网也计数，失败重试可以跳号；仅要求每轮前进。
        for offset, recovery in enumerate((2, 4, 5)):
            self.data['runs'][offset]['recovery_generation'] = recovery
        self.assertEqual(self.validate()['status'], 'INDEX_CONSISTENCY_ONLY')
        self.data['runs'][1]['recovery_generation'] = 2
        with self.assertRaisesRegex(InvalidIndex, 'RECOVERY_GENERATION_NOT_ADVANCING'):
            self.validate()

    def test_environment_and_firmware_hash_drift(self):
        env = copy.deepcopy(self.data)
        env['runs'][4]['environment_id'] = 'DIFFERENT_ENV'
        with self.assertRaisesRegex(InvalidIndex, 'ENVIRONMENT_OR_PROFILE_DRIFT'):
            self.validate(env)
        self.data['runs'][4]['measurement_bin_sha256'] = '0' * 64
        with self.assertRaisesRegex(InvalidIndex, 'FIRMWARE_IDENTITY_DRIFT'):
            self.validate()

    def test_reused_snapshot_or_unsaved_window(self):
        self.data['runs'][1]['snapshot_sha_first'] = self.data['runs'][0]['snapshot_sha_first']
        self.data['runs'][1]['snapshot_sha_second'] = self.data['runs'][0]['snapshot_sha_second']
        with self.assertRaisesRegex(InvalidIndex, 'REUSED_SNAPSHOT'):
            self.validate()
        self.data = json.loads(FIXTURE.read_text(encoding='utf-8'))
        self.data['runs'][0]['saved_before_next_d'] = False
        with self.assertRaisesRegex(InvalidIndex, 'WINDOW_CAPTURE_INCOMPLETE'):
            self.validate()

    def test_pause_loss_or_partial_points_rejected(self):
        for key, value in [('observer_paused_in_window', True), ('irq_flags', 2),
                           ('tick_dropped_delta', 1), ('network_valid_mask', 255)]:
            data = copy.deepcopy(self.data)
            data['runs'][0][key] = value
            with self.assertRaises(InvalidIndex):
                self.validate(data)

    def test_observer_halt_declaration_mismatch_rejected(self):
        self.data['runs'][0]['observer_halt_us'] -= 1
        with self.assertRaisesRegex(InvalidIndex, 'OBSERVER_EVENT_MISMATCH'):
            self.validate()

    def test_old_metric_names_and_stack_claim_rejected(self):
        for key, value in [('m02_semantics', 'PLANNED_DUE_TO_SERVICE_DONE'),
                           ('m03_semantics', 'PURE_CPU'), ('stack_method', 'EARLY_RESET_SENTINEL')]:
            data = copy.deepcopy(self.data)
            data['runs'][0][key] = value
            with self.assertRaisesRegex(InvalidIndex, 'METRIC_SEMANTICS_DRIFT'):
                self.validate(data)

    def test_event_log_required(self):
        with self.assertRaisesRegex(InvalidIndex, 'ORDER_UNVERIFIED'):
            validate_index(self.data)


if __name__ == '__main__':
    unittest.main()
