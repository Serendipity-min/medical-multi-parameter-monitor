"""端到端合成文件测试：真实读取六对 .bin，核对索引SHA和跨轮计数。"""

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from r2_snapshot_bytes import ROOT, InvalidSnapshot, load_layout
from r2_verify_bundle import verify_bundle
from test_r2_snapshot_bytes import LAYOUT, synthetic_state


FIXTURES = ROOT / 'gateway/mqtt/tests/measurement/fixtures'
BUILD = ROOT / 'gateway/mqtt/build/h16-diagnostic'


class BundleTests(unittest.TestCase):
    def setUp(self):
        self.index = json.loads((FIXTURES / 'r1-snapshot-index-synthetic.json').read_text(encoding='utf-8'))
        self.log = json.loads((FIXTURES / 'r2-synthetic-event-log.json').read_text(encoding='utf-8'))
        self.layout = load_layout(LAYOUT)
        # 只创建本轮临时文件容器；真实Flash备份和旧诊断构建不参与单测。
        BUILD.mkdir(parents=True, exist_ok=True)
        self.temporary = tempfile.TemporaryDirectory(dir=BUILD)
        self.folder = Path(self.temporary.name)
        self.bundle = {'schema_version': 1, 'kind': 'SYNTHETIC_R2_BUNDLE', 'snapshots': []}
        for run in self.index['runs']:
            name = run['run_id']
            data = synthetic_state(self.layout, run['variant'], run['ordinal'], run['clock_seq'])
            first, second = self.folder / f'{name}-read1.bin', self.folder / f'{name}-read2.bin'
            first.write_bytes(data)
            second.write_bytes(data)
            raw_sha = hashlib.sha256(data).hexdigest()
            run['snapshot_sha_first'] = run['snapshot_sha_second'] = raw_sha
            self.bundle['snapshots'].append({'run_id': name,
                                             'read1': first.relative_to(ROOT).as_posix(),
                                             'read2': second.relative_to(ROOT).as_posix()})

    def tearDown(self):
        # 临时目录只在忽略的本次 build 下；不触碰用户的其它工作树或历史产物。
        self.assertTrue(self.folder.resolve().is_relative_to(BUILD.resolve()))
        self.temporary.cleanup()

    def test_six_real_file_pairs_link_to_index_without_hardware_acceptance(self):
        result = verify_bundle(self.index, self.log, self.bundle, self.layout)
        self.assertEqual(len(result['runs']), 6)
        self.assertFalse(result['physical_source_verified'])
        self.assertEqual(result['H16_acceptance'], 'NOT_GRANTED')
        self.assertEqual(result['C3A_entry'], 'HOLD')

    def test_fabricated_index_hash_is_rejected_by_file_bytes(self):
        self.index['runs'][0]['snapshot_sha_first'] = 'f' * 64
        self.index['runs'][0]['snapshot_sha_second'] = 'f' * 64
        with self.assertRaisesRegex(InvalidSnapshot, 'INDEX_RAW_BYTES_MISMATCH'):
            verify_bundle(self.index, self.log, self.bundle, self.layout)

    def test_modified_saved_copy_rejected(self):
        target = ROOT / self.bundle['snapshots'][0]['read2']
        contents = bytearray(target.read_bytes())
        contents[-1] ^= 1
        target.write_bytes(contents)
        with self.assertRaisesRegex(InvalidSnapshot, 'RAW_SNAPSHOT_BYTES_DISAGREE'):
            verify_bundle(self.index, self.log, self.bundle, self.layout)

    def test_cross_window_counter_regression_rejected(self):
        target = self.bundle['snapshots'][1]
        data = bytearray((ROOT / target['read1']).read_bytes())
        offsets = self.layout['variants']['P4']['types']
        before = offsets['ProbeState']['fields']['cache_before'] + offsets['ProbeCache']['fields']['replay']
        data[before:before + 4] = (0).to_bytes(4, 'little')
        for field in ('read1', 'read2'):
            (ROOT / target[field]).write_bytes(data)
        raw_sha = hashlib.sha256(data).hexdigest()
        self.index['runs'][1]['snapshot_sha_first'] = self.index['runs'][1]['snapshot_sha_second'] = raw_sha
        with self.assertRaisesRegex(InvalidSnapshot, 'CROSS_WINDOW_COUNTER_REGRESSION'):
            verify_bundle(self.index, self.log, self.bundle, self.layout)

    def test_path_outside_ignored_build_rejected(self):
        self.bundle['snapshots'][0]['read1'] = 'doc/README.md'
        with self.assertRaisesRegex(InvalidSnapshot, 'SNAPSHOT_OUTSIDE_IGNORED_BUILD'):
            verify_bundle(self.index, self.log, self.bundle, self.layout)


if __name__ == '__main__':
    unittest.main()
