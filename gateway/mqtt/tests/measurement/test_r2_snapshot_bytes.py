"""用合成 ProbeState 字节验证 ARM 布局、双读哈希和坏样本拒绝；无设备数据。"""

import tempfile
from pathlib import Path
import unittest

from r2_snapshot_bytes import ROOT, InvalidSnapshot, decode, load_layout, verify_pair


# 使用已归档且固定SHA的布局，拉取分支后即可复现，不依赖旧本机忽略产物。
LAYOUT = ROOT / 'doc/P/04_第四阶段_P5_coreMQTT裸机迁移/验收/evidence/c25-r2/probe-layout-v2.json'
TEST_BUILD = ROOT / 'gateway/mqtt/build/h16-diagnostic/r2-offline-tests'


def synthetic_state(layout, variant='P5', ordinal=1, clock_seq=200):
    types = layout['variants'][variant]['types']
    data = bytearray(types['ProbeState']['size'])

    def put(typ, field, value, base=0, width=4):
        offset = base + types[typ]['fields'][field]
        data[offset:offset + width] = value.to_bytes(width, 'little')

    put('ProbeState', 'magic', 0xC25D1A60)
    put('ProbeState', 'profile', 0xC2500001)
    put('ProbeState', 'variant', int(variant[-1]))
    put('ProbeState', 'marker_address', layout['variants'][variant]['marker_address'])
    put('ProbeState', 'core_hz', 16_000_000)
    put('ProbeState', 'initialized', 1)
    put('ProbeState', 'clock_seq', clock_seq)
    put('ProbeState', 'foreground_flags', 64)
    put('ProbeState', 'window_generation', ordinal)
    put('ProbeState', 'recovery_generation', ordinal + 1)
    put('ProbeState', 'network_valid_mask', 0x1ff)
    put('ProbeState', 'cache_snapshot_mask', 3)
    put('ProbeState', 'event_count', 2)
    put('ProbeState', 'heap_peak_bytes', 4096 + ordinal * 100)
    put('ProbeState', 'heap_error_base', 0)
    put('ProbeState', 'heap_enomem_count', 0)
    put('ProbeState', 'tick_head', 200)
    put('ProbeState', 'tick_tail', 200)
    base = types['ProbeState']['fields']['aggregate']
    for scope in (2, 8):
        at = base + scope * types['ProbeAggregate']['size']
        put('ProbeAggregate', 'success', 1, at)
        put('ProbeAggregate', 'min_cycles', 1600, at)
        put('ProbeAggregate', 'max_cycles', 1600, at)
        put('ProbeAggregate', 'inclusive_cycles', 1600, at, 8)
    events = types['ProbeState']['fields']['events']
    for index, scope in enumerate((2, 8)):
        at = events + index * types['ProbeEvent']['size']
        put('ProbeEvent', 'scope', 0x100 | scope, at)
        put('ProbeEvent', 'start', 1000 + index * 2000, at)
        put('ProbeEvent', 'end', 2600 + index * 2000, at)
        put('ProbeEvent', 'bound_ms', 3, at)
    network = types['ProbeState']['fields']['network_us']
    for index in range(9):
        data[network + index * 8:network + index * 8 + 8] = (1000000 + index * 1000000).to_bytes(8, 'little')
    for name, values in (('cache_before', (3, 203, (ordinal - 1) * 3, 0)),
                         ('cache_after', (0, 203, ordinal * 3, 0))):
        at = types['ProbeState']['fields'][name]
        for field, value in zip(('cache', 'lost', 'replay', 'drop'), values):
            put('ProbeCache', field, value, at)
    put('ProbeState', 'replay_observed', 1)
    put('ProbeState', 'live_observed', 1)
    put('ProbeState', 'first_live_us', 9_500_000, width=8)
    put('ProbeState', 'first_replay_us', 9_800_000, width=8)
    put('ProbeState', 'cache_drained_observed', 1)
    return data


class RawSnapshotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        TEST_BUILD.mkdir(parents=True, exist_ok=True)
        cls.layout = load_layout(LAYOUT)

    def test_arm_layout_and_both_variants_decode(self):
        for variant in ('P4', 'P5'):
            result = decode(synthetic_state(self.layout, variant), self.layout, variant)
            self.assertEqual(result['window_generation'], 1)
            self.assertEqual(result['cache_loss_delta'], 0)
            self.assertEqual(result['M04'], 'BLOCKED_UNSAFE_SENTINEL')
            self.assertEqual(result['H16_acceptance'], 'NOT_GRANTED')

    def test_independent_saved_byte_pair_is_hashed(self):
        data = synthetic_state(self.layout)
        with tempfile.TemporaryDirectory(dir=TEST_BUILD) as folder:
            first, second = Path(folder) / 'read1.bin', Path(folder) / 'read2.bin'
            first.write_bytes(data)
            second.write_bytes(data)
            result = verify_pair(first, second, self.layout, 'P5')
            self.assertTrue(result['independent_file_pair_verified'])
            self.assertEqual(result['raw_snapshot_bytes'], 1264)
            second.write_bytes(data[:-1])
            with self.assertRaisesRegex(InvalidSnapshot, 'RAW_SNAPSHOT_BYTES_DISAGREE'):
                verify_pair(first, second, self.layout, 'P5')

    def test_same_file_and_truncated_or_extra_bytes_rejected(self):
        data = synthetic_state(self.layout)
        with self.assertRaisesRegex(InvalidSnapshot, 'INDEPENDENT_FILES_REQUIRED'):
            verify_pair(Path('same.bin'), Path('same.bin'), self.layout, 'P5')
        for bad in (data[:-1], data + b'X'):
            with self.assertRaisesRegex(InvalidSnapshot, 'SNAPSHOT_EXACT_SIZE'):
                decode(bad, self.layout, 'P5')

    def test_wrong_magic_marker_and_variant_rejected(self):
        for field in ('magic', 'marker_address', 'variant'):
            data = synthetic_state(self.layout)
            offset = self.layout['variants']['P5']['types']['ProbeState']['fields'][field]
            data[offset] ^= 1
            with self.assertRaisesRegex(InvalidSnapshot, 'PROBE_IDENTITY_OR_CLOCK'):
                decode(data, self.layout, 'P5')

    def test_odd_clock_or_dropped_tick_rejected(self):
        for field in ('clock_seq', 'tick_dropped'):
            data = synthetic_state(self.layout)
            offset = self.layout['variants']['P5']['types']['ProbeState']['fields'][field]
            data[offset] ^= 1
            with self.assertRaisesRegex(InvalidSnapshot, 'PROBE_LOSS_OR_UNSTABLE_HALT'):
                decode(data, self.layout, 'P5')

    def test_missing_network_or_pending_tick_rejected(self):
        for field in ('network_valid_mask', 'tick_head'):
            data = synthetic_state(self.layout)
            offset = self.layout['variants']['P5']['types']['ProbeState']['fields'][field]
            data[offset] ^= 1
            with self.assertRaisesRegex(InvalidSnapshot, 'INCOMPLETE_WINDOW_OR_PENDING_TICKS'):
                decode(data, self.layout, 'P5')

    def test_network_order_and_cache_counter_regression_rejected(self):
        data = synthetic_state(self.layout)
        offsets = self.layout['variants']['P5']['types']['ProbeState']['fields']
        network = offsets['network_us']
        data[network + 8:network + 16] = (1).to_bytes(8, 'little')
        with self.assertRaisesRegex(InvalidSnapshot, 'NETWORK_EVENT_ORDER'):
            decode(data, self.layout, 'P5')
        data = synthetic_state(self.layout)
        cache = offsets['cache_after'] + self.layout['variants']['P5']['types']['ProbeCache']['fields']['lost']
        data[cache:cache + 4] = (202).to_bytes(4, 'little')
        with self.assertRaisesRegex(InvalidSnapshot, 'CACHE_COUNTER_DRIFT'):
            decode(data, self.layout, 'P5')

    def test_unknown_layout_hash_rejected(self):
        with tempfile.TemporaryDirectory(dir=TEST_BUILD) as folder:
            fake = Path(folder) / 'layout.json'
            fake.write_text('{}', encoding='utf-8')
            with self.assertRaisesRegex(InvalidSnapshot, 'LAYOUT_SHA_MISMATCH'):
                load_layout(fake)


if __name__ == '__main__':
    unittest.main()
