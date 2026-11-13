"""只用合成存储器验证复位权限、入口与解码顺序；不加载J-Link DLL。"""
import hashlib
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import recover_resp_rall20_b as recovery
from readback_b import HALT, write_json


class FakeLink:
    def __init__(self, invalid=None):
        self.invalid = invalid; self.calls = []; self.reset_phase = False; self.alias_phase = False
        self.flash = struct.pack('<2I', 0x20002f30, 0x080001a1)+bytes(1048576-8)
        self.options = bytes(16); self.reset_done = False; self.running = False

    def open(self):
        self.calls.append('open')

    def policy(self, value):
        assert self.reset_phase
        self.calls.append(value)

    def call(self, name, **kwargs):
        self.calls.append(name)
        if name == 'JLINKARM_Reset':
            assert self.reset_phase
            self.reset_done = True
        if name == 'JLINKARM_Go':
            self.running = True
        return 0

    def read(self, address, size):
        if address == 0x08000000: return self.flash
        if address == 0x1fffc000: return self.options
        assert address == 0 and self.alias_phase and size == 64
        return bytes(64) if self.invalid == 'alias' else self.flash[:64]

    def u32(self, address):
        if address == 0xe000edf0:
            return HALT if self.reset_done and not self.running and self.invalid != 'halt' else 0
        assert address == 0xe000ed08
        return 0x08000000 if self.running and self.invalid != 'running_vtor' else 0x1fff0000


class RecoveryCases(unittest.TestCase):
    def run_restore(self, invalid=None):
        link = FakeLink(invalid)
        with tempfile.TemporaryDirectory() as directory:
            out = Path(directory); ref = out/'identity.json'
            write_json(ref, {'uid_hex': 'SYNTHETIC', 'optcr': 0})
            binding = {'identity_reference': str(ref), 'flash_sha256': hashlib.sha256(link.flash).hexdigest(),
                       'options_sha256': hashlib.sha256(link.options).hexdigest()}
            core = {'registers': {'R15': 0x080001a0, 'MSP': 0 if invalid == 'stack' else 0x20002f30}}
            with patch.object(recovery, 'identity', return_value={'uid_hex': 'SYNTHETIC', 'optcr': 0}), \
                 patch.object(recovery, 'check_identity'), patch.object(recovery.runtime, 'core_if_halted', return_value=core), \
                 patch.object(recovery.capture, 'ready_snapshot', return_value={'bio': {}}) as snapshot, \
                 patch.object(recovery.capture, 'check_input'), \
                 patch.object(recovery.runtime, 'capture_gate', return_value={'status': 'READY_FOR_NEW_CAPTURE_CARD'}), \
                 patch.object(recovery.time, 'sleep'):
                if invalid:
                    with self.assertRaises(RuntimeError): recovery.restore(link, binding, out)
                    self.assertEqual(snapshot.call_count, 0)
                else:
                    recovery.restore(link, binding, out)
                    self.assertEqual(snapshot.call_count, 2)
        self.assertEqual(link.calls.count('JLINKARM_Reset'), 1)
        self.assertFalse(link.reset_phase); self.assertFalse(link.alias_phase)
        return link

    def test_one_reset_valid_entry_then_go(self):
        self.assertEqual(self.run_restore().calls.count('JLINKARM_Go'), 1)

    def test_bad_stack_never_go(self):
        self.assertNotIn('JLINKARM_Go', self.run_restore('stack').calls)

    def test_bad_alias_never_go(self):
        self.assertNotIn('JLINKARM_Go', self.run_restore('alias').calls)

    def test_reset_not_halted_never_go(self):
        self.assertNotIn('JLINKARM_Go', self.run_restore('halt').calls)

    def test_rom_after_go_rejected_before_ram_decode(self):
        self.assertEqual(self.run_restore('running_vtor').calls.count('JLINKARM_Go'), 1)

    def test_reset_alias_and_writes_rejected_outside_phase(self):
        link = object.__new__(recovery.RecoveryRallLink)
        link.reset_phase = False; link.alias_phase = False
        # 在未创建SDK对象的情况下验证最外层权限拒绝，误调用也不触及硬件。
        with self.assertRaisesRegex(RuntimeError, 'RESET_OUTSIDE'): link.call('JLINKARM_Reset')
        with self.assertRaisesRegex(RuntimeError, 'RESET_OUTSIDE'): link.call('JLINKARM_ExecCommand', b'SetResetType = 0')
        with self.assertRaisesRegex(RuntimeError, 'ALIAS_SCOPE'): link.call('JLINKARM_ReadMemEx', 0, 64, None, 0)
        with self.assertRaisesRegex(RuntimeError, 'FUNCTION_DENIED'): link.call('JLINKARM_WriteMem')


if __name__ == '__main__':
    unittest.main()
