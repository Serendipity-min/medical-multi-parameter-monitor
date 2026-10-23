"""以合成Flash和SDK替身覆盖安装/回退边界；禁止加载任何真实DLL。"""
import ctypes
import hashlib
import json
from pathlib import Path
import struct
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'node-b/tools'))
import b4_swd_install as w


class Fake:
    def __init__(self, image, options):
        self.image = image; self.options = options; self.payload = None
        self.verified_running_flash = False; self.close_resume_enabled = False
        self.halted = False; self.rom = False; self.fault = False; self.corrupt = False
        self.wrong_uid = False; self.counts = {}
    def open(self): pass
    def set_close_resume(self, enabled): self.close_resume_enabled = enabled
    def policy(self, command): assert command == 'SetResetType = 0'
    def stable_halt(self): assert self.halted
    def u32(self, a):
        if a == 0xe000ed00: return 0x410fc241
        if a == 0xe0042000: return 0x10000413
        if a == 0x40023c14: return 0x0fffaaed
        if a == 0x40023c10: return 0x80000000
        if a == 0xe000edf0: return w.raw.HALT if self.halted else 0
        if a == w.readonly.SYSTEM['VTOR']: return 0x1fff0000 if self.rom else 0x08000000
        if a == w.readonly.SYSTEM['DWT_PCSR']: return 0x1fff32f0 if self.rom else 0x08001001
        if a == w.readonly.SYSTEM['CFSR']: return 1 if self.fault else 0
        return 0
    def read(self, a, n):
        if a == 0x08000000 and n == 1048576: return self.image
        if a == 0x1fffc000 and n == 16: return self.options
        if a == 0x1fff7a10: return (b'\x6b' if self.wrong_uid else b'\x5a') * 12
        if a == 0x1fff7a22: return (1024).to_bytes(2, 'little')
        return self.u32(a).to_bytes(n, 'little')
    def call(self, name, *a, **kwargs):
        self.counts[name] = self.counts.get(name, 0) + 1
        if name == 'JLINKARM_Halt': self.halted = True; return 0
        if name == 'JLINKARM_BeginDownload': return None
        if name == 'JLINKARM_WriteMem': self.payload = ctypes.string_at(a[2], a[1]); return a[1]
        if name == 'JLINKARM_EndDownload':
            self.image = self.payload + self.image[len(self.payload):]
            if self.corrupt: self.image = self.image[:-1] + b'\x01'
            return 0
        if name == 'JLINKARM_Reset': self.halted = True; return 0
        if name == 'JLINKARM_Go': self.halted = False; return None
        raise AssertionError(name)


class InstallTests(unittest.TestCase):
    def setUp(self):
        folder = ROOT / 'node-b/build'; folder.mkdir(exist_ok=True)
        self.tmp = tempfile.TemporaryDirectory(dir=folder, prefix='b4-install-fake-')
        self.addCleanup(self.tmp.cleanup)
        self.out = Path(self.tmp.name)
        original = bytearray(b'\xa5' * 1048576)
        struct.pack_into('<II', original, 0, 0x20020000, 0x08000101)
        self.original = bytes(original)
        self.options = b'\xaa\x55' * 8
        self.identity = {'cpuid': 0x410fc241, 'device_id': 0x10000413, 'uid_hex': '5a' * 12,
                         'capacity_kib': 1024, 'optcr': 0x0fffaaed, 'flash_sr': 0}
    def make(self, board):
        candidate = bytearray(b'\x3c' * (39948 if board == 'B' else 21700))
        struct.pack_into('<II', candidate, 0, 0x20020000, 0x08000201)
        return w.package.make_plan(board, self.original, self.original, self.options, self.options,
            self.identity, self.identity, bytes(candidate), hashlib.sha256(candidate).hexdigest())
    def execute(self, board='B', phase='install', transform=None):
        m, payload = self.make(board)
        before = payload['before-full-private.bin' if phase == 'install' else 'expected-full-private.bin']
        fake = Fake(before, self.options)
        if transform: transform(fake)
        expected = payload['expected-full-private.bin' if phase == 'install' else 'before-full-private.bin']
        # 只读取替身复位后向量；测试从不导入或调用原生调试API。
        core = {'registers': {'R15': int.from_bytes(expected[4:8], 'little'),
                             'MSP': int.from_bytes(expected[:4], 'little')}}
        with patch.object(w.time, 'sleep'), patch.object(w.runtime, 'core_if_halted', return_value=core):
            result = w.execute(fake, self.out, {'phase': phase, 'board': board}, m, payload)
        return fake, result, m, payload
    def test_B_48K_install_preserves_tail_and_config(self):
        f, r, m, p = self.execute()
        self.assertEqual(m['sectors'], [0, 1, 2]); self.assertEqual(len(f.payload), 49152)
        self.assertEqual(f.image, p['expected-full-private.bin']); self.assertEqual(r['exit_code'], 0)
        self.assertEqual(f.image[39948:], self.original[39948:])
        self.assertTrue(f.close_resume_enabled)
    def test_C_32K_install_preserves_sector2_and_config(self):
        f, _, m, _ = self.execute('C')
        self.assertEqual(m['sectors'], [0, 1]); self.assertEqual(len(f.payload), 32768)
        self.assertEqual(f.image[21700:], self.original[21700:])
    def test_B_restore_exact_full_original(self):
        f, r, _, _ = self.execute(phase='restore')
        self.assertEqual(f.image, self.original); self.assertEqual(r['phase'], 'restore')
    def test_C_restore_exact_full_original(self):
        f, _, _, _ = self.execute('C', 'restore'); self.assertEqual(f.image, self.original)
    def test_wrong_uid_no_halt_or_download(self):
        with self.assertRaisesRegex(ValueError, 'WRONG_BOARD'): self.execute(transform=lambda f: setattr(f, 'wrong_uid', True))
    def test_ROM_no_recovery(self):
        with self.assertRaisesRegex(ValueError, 'ROM_STOP'): self.execute(transform=lambda f: setattr(f, 'rom', True))
    def test_halted_entry_no_go(self):
        with self.assertRaisesRegex(ValueError, 'HALTED'): self.execute(transform=lambda f: setattr(f, 'halted', True))
    def test_fault_no_download(self):
        with self.assertRaisesRegex(ValueError, 'FAULT'): self.execute(transform=lambda f: setattr(f, 'fault', True))
    def test_original_drift_no_download(self):
        with self.assertRaisesRegex(ValueError, 'CURRENT_FLASH_DRIFT'):
            self.execute(transform=lambda f: setattr(f, 'image', f.image[:-1] + b'\0'))
    def test_verify_failure_no_reset_or_go(self):
        with self.assertRaisesRegex(ValueError, 'FULL_VERIFY_FAILED'):
            self.execute(transform=lambda f: setattr(f, 'corrupt', True))
    def test_disabled_rejected_before_package_or_sdk(self):
        with self.assertRaisesRegex(ValueError, 'OWNER_AUTH'): w.authorize({})
    def guard(self):
        f = object.__new__(w.InstallLink); f.sdk_calls = 0; f.counts = {}
        f.program_size = 49152; f.program_sha = 'a'; f.fully_verified = False
        f.register_reads_allowed = False; f.verified_running_flash = False
        return f
    def test_options_write_denied(self):
        with self.assertRaisesRegex(ValueError, 'WRITE_SCOPE'):
            self.guard().call('JLINKARM_WriteMem', 0x1fffc000, 16, None)
    def test_mass_erase_or_unlock_denied(self):
        for name in ('JLINKARM_EraseChip', 'JLINKARM_UnlockDevice', 'JLINKARM_WriteU32'):
            with self.assertRaisesRegex(ValueError, 'FUNCTION_DENIED'): self.guard().call(name)
    def test_PC_write_denied(self):
        with self.assertRaisesRegex(ValueError, 'FUNCTION_DENIED'): self.guard().call('JLINKARM_WriteReg', 15, 0x08000000)
    def test_arbitrary_read_denied(self):
        with self.assertRaisesRegex(ValueError, 'READ_SCOPE'):
            self.guard().call('JLINKARM_ReadMemEx', 0x40003000, 4, None, 0)
    def test_reset_before_full_verification_denied(self):
        with self.assertRaisesRegex(ValueError, 'BOOT_BEFORE_FULL_VERIFY'): self.guard().call('JLINKARM_Reset')
    def test_repeat_download_denied(self):
        f = self.guard(); f.counts['JLINKARM_BeginDownload'] = 1
        with self.assertRaisesRegex(ValueError, 'ACTION_BUDGET'): f.call('JLINKARM_BeginDownload', 0)
    def test_unverified_close_resume_denied(self):
        with self.assertRaisesRegex(ValueError, 'CLOSE_NOT_VERIFIED'):
            self.guard().call('JLINKARM_ExecCommand', b'SetRestartOnClose = 1', None, 0)


if __name__ == '__main__': unittest.main(verbosity=2)
