"""B2-0 真实构建身份及合成负例；不会启动 J-Link 或串口。"""
import copy
import json
import os
from pathlib import Path
import struct
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[2]
sys.path[:0] = [str(ROOT/'node-b/tools'), str(ROOT/'node-b/acquisition/工具')]
from field_profile import prepare, validate_profile, check_observation
from stable_slot_export import StableSlots


class FieldCases(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # 必须显式绑定本轮真实 ARM 目录，不使用模拟 BIN 冒充构建身份。
        cls.arm = Path(os.environ['B_FIELD_ARM'])
        cls.abi = json.loads(Path(os.environ['B_FIELD_ABI']).read_text(encoding='utf-8'))
        cls.profile = prepare(cls.arm, cls.abi)

    def test_real_artifacts(self):
        self.assertEqual(validate_profile(self.profile, self.arm, self.abi), 'PASS_OFFLINE_ONLY')

    def test_old_profile(self):
        p = copy.deepcopy(self.profile)
        p['schema'] = 'legacy'
        with self.assertRaisesRegex(ValueError, '^OLD_PROFILE$'):
            validate_profile(p, self.arm, self.abi)

    def test_address_crosses_ram_end(self):
        p = copy.deepcopy(self.profile)
        p['layout']['slots']['address'] = '0x2001fff0'
        with self.assertRaisesRegex(ValueError, '^ADDRESS_RANGE$'):
            validate_profile(p, self.arm, self.abi)

    def test_address_in_ram_but_wrong_generation(self):
        p = copy.deepcopy(self.profile)
        p['layout']['slots']['address'] = '0x20002038'
        with self.assertRaisesRegex(ValueError, '^ABI_LAYOUT_MISMATCH$'):
            validate_profile(p, self.arm, self.abi)

    def test_tool_drift(self):
        p = copy.deepcopy(self.profile)
        p['tools_sha256'] = {}
        with self.assertRaisesRegex(ValueError, '^TOOL_DRIFT$'):
            validate_profile(p, self.arm, self.abi)

    def test_binary_drift(self):
        # 只构造临时错误副本，不改真实候选或历史构建。
        with tempfile.TemporaryDirectory() as folder:
            arm = Path(folder)
            binary = arm/'firmware/OBJ/BIO_V2.bin'
            binary.parent.mkdir(parents=True)
            original = (self.arm/'firmware/OBJ/BIO_V2.bin').read_bytes()
            binary.write_bytes(bytes([original[0] ^ 1])+original[1:])
            with self.assertRaisesRegex(ValueError, '^ARTIFACT_DRIFT$'):
                validate_profile(self.profile, arm, self.abi)

    def test_device_and_end_negatives(self):
        expected = {'uid': 'SYNTHETIC_NOT_DEVICE', 'flash_sha256': 'SYNTHETIC_NOT_FLASH'}
        good = dict(expected, abi_tag=0x324f4942, abi_version=2, boot_before='fixture-1',
                    boot_after='fixture-1', diag_sequence_before=10, diag_sequence_after=10,
                    tail_halt_confirmed=True, resume_confirmed=True)
        self.assertEqual(check_observation(expected, good), 'METADATA_CONSISTENT_NOT_ACCURACY_PROOF')
        # 每个拒绝均核对原因，不能把缺文件等无关失败当成门禁通过。
        for key, value, reason in [('uid', 'WRONG', 'UID_MISMATCH'),
                                  ('flash_sha256', 'WRONG', 'FLASH_MISMATCH'),
                                  ('abi_version', 1, 'ABI_MISMATCH'),
                                  ('boot_after', 'fixture-2', 'CROSS_GENERATION'),
                                  ('diag_sequence_after', 11, 'TORN_DIAG'),
                                  ('tail_halt_confirmed', False, 'UNCONFIRMED_END'),
                                  ('resume_confirmed', False, 'UNCONFIRMED_END')]:
            with self.subTest(reason=reason, key=key):
                bad = dict(good, **{key: value})
                with self.assertRaisesRegex(ValueError, '^'+reason+'$'):
                    check_observation(expected, bad)
        with self.assertRaisesRegex(ValueError, '^UNBOUND_DEVICE$'):
            check_observation({'uid': None, 'flash_sha256': None}, good)

    def test_conflict_and_unconfirmed_tail(self):
        # 使用既有真实槽重建器，3:2 多版本冲突不能多数投票或用暂停尾段洗掉。
        def slot(value):
            return b'\xc0\x00\x00'+bytes([value])*6+bytes(3)+struct.pack('<III', 1, 672000, 4)
        from collections import Counter
        c = StableSlots(False)
        c.versions[1] = Counter({slot(1): 3, slot(2): 2})
        c.atomic[1] = slot(1)
        self.assertIn(1, c.select().multi_repeat_conflicts)
        self.assertNotIn(1, c.select().frames)
        c = StableSlots(False)
        c.versions[1] = Counter({slot(1): 1})
        self.assertIn(1, c.select().pending)
        self.assertNotIn(1, c.select().frames)

    def test_cross_reset_active_ram_not_certified(self):
        # 同一活动槽块混有复位前后序号，不能靠重复读取拼成同一启动的连续流。
        blob = bytearray(3072)
        for i, seq in enumerate((1000, 1)):
            blob[i*24:(i+1)*24] = b'\xc0\x00\x00'+bytes(9)+struct.pack('<III', seq, seq*672000, seq*4)
        c = StableSlots(False)
        c.add_running_chunk(bytes(blob))
        c.add_running_chunk(bytes(blob))
        self.assertTrue(c.select().ambiguous_reset_chunks)
        self.assertFalse(c.select().frames)


if __name__ == '__main__':
    unittest.main(verbosity=2)
