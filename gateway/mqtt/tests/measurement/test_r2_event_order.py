"""跨轮事件链负向测试；全部时刻为人工合成，不代表现场 QPC 记录。"""

import copy
import json
from pathlib import Path
import unittest

from r1_snapshot_index import InvalidIndex, _event_digest, validate_index


ROOT = Path(__file__).parent / 'fixtures'


def reseal(log):
    # 改动时刻后重新计算完整链，确保测试真正触及时间规则而非仅靠SHA不匹配拒绝。
    previous = '0' * 64
    for event in log['events']:
        event['prev_sha256'] = previous
        event['sha256'] = _event_digest(event)
        previous = event['sha256']


class EventOrderTests(unittest.TestCase):
    def setUp(self):
        self.index = json.loads((ROOT / 'r1-snapshot-index-synthetic.json').read_text(encoding='utf-8'))
        self.log = json.loads((ROOT / 'r2-synthetic-event-log.json').read_text(encoding='utf-8'))

    def test_complete_chain_is_only_offline_consistency(self):
        result = validate_index(self.index, self.log)
        self.assertEqual(result['H16_acceptance'], 'NOT_GRANTED')
        self.assertIn('NOT_PHYSICAL_AUTHENTICITY', result['order_evidence'])

    def test_overlapping_windows_rejected_even_after_reseal(self):
        first_d = self.log['events'][0]['at_us']
        for event in self.log['events'][6:12]:
            event['at_us'] -= 99_000_000
        self.index['runs'][1]['observer_start_us'] = first_d + 1_000_000
        self.index['runs'][1]['observer_halt_us'] = first_d + 91_000_000
        reseal(self.log)
        with self.assertRaisesRegex(InvalidIndex, 'EVENT_GLOBAL_TIME_ORDER'):
            validate_index(self.index, self.log)

    def test_next_d_before_persisted_snapshot_rejected(self):
        persisted = self.log['events'][4]['at_us']
        self.log['events'][6]['at_us'] = persisted - 1
        self.index['runs'][1]['observer_start_us'] = persisted - 1
        reseal(self.log)
        with self.assertRaisesRegex(InvalidIndex, 'EVENT_GLOBAL_TIME_ORDER'):
            validate_index(self.index, self.log)

    def test_reverse_read_order_rejected(self):
        self.log['events'][2]['at_us'], self.log['events'][3]['at_us'] = (
            self.log['events'][3]['at_us'], self.log['events'][2]['at_us'])
        reseal(self.log)
        with self.assertRaisesRegex(InvalidIndex, 'EVENT_GLOBAL_TIME_ORDER'):
            validate_index(self.index, self.log)

    def test_cross_observer_session_rejected(self):
        self.index['runs'][3]['observer_session_id'] = 'QPC_SESSION_B'
        for event in self.log['events'][18:24]:
            event['observer_session_id'] = 'QPC_SESSION_B'
        reseal(self.log)
        with self.assertRaisesRegex(InvalidIndex, 'OBSERVER_SESSION_DRIFT'):
            validate_index(self.index, self.log)

    def test_missing_event_or_mutated_hash_rejected(self):
        missing = copy.deepcopy(self.log)
        missing['events'].pop(4)
        with self.assertRaisesRegex(InvalidIndex, 'EVENT_LOG_COUNT'):
            validate_index(self.index, missing)
        self.log['events'][1]['at_us'] += 1
        with self.assertRaisesRegex(InvalidIndex, 'EVENT_CHAIN_HASH'):
            validate_index(self.index, self.log)

    def test_duration_drift_in_chained_events_rejected(self):
        for event in self.log['events'][1:6]:
            event['at_us'] -= 10_000_000
        self.index['runs'][0]['observer_halt_us'] -= 10_000_000
        reseal(self.log)
        with self.assertRaisesRegex(InvalidIndex, 'OBSERVER_WINDOW_DURATION_DRIFT'):
            validate_index(self.index, self.log)


if __name__ == '__main__':
    unittest.main()
