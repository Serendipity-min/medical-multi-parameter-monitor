"""只用内存替身验证C只读窗口；不构造DLL/串口，不读取真实C原件。"""
import datetime
import json
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(ROOT / 'node-b/tools'))
import c_b4_readonly as window


class FakeC:
    def __init__(self):
        image = bytearray(b'\xa5' * 1048576); struct.pack_into('<II', image, 0, 0x20020000, 0x08000101)
        self.image = bytes(image); self.full_reads = 0; self.opened = False
        self.verified_running_flash = False; self.close_resume_enabled = False
        self.halted = False; self.rom = False; self.fault = False; self.different = False; self.reset = False
        self.alias = False; self.bad_alias = False; self.pc_unavailable = False; self.unlocked = False

    def open(self): self.opened = True
    def set_close_resume(self, value): self.close_resume_enabled = value
    def read(self, address, size):
        if address == 0x08000000 and size == 1048576:
            self.full_reads += 1
            return self.image[:-1] + b'\x01' if self.different and self.full_reads == 2 else self.image
        if address == 0x08000000 and size == 64: return self.image[:64]
        if address == 0 and size == 64: return b'\x00' * 64 if self.bad_alias else self.image[:64]
        if address == 0x1fffc000 and size == 16: return b'\xaa\x55' * 8
        if address == 0x1fff7a10: return b'\x5a' * 12
        if address == 0x1fff7a22: return (1024).to_bytes(2, 'little')
        return self.u32(address).to_bytes(4, 'little')
    def u32(self, address):
        if address == 0xe000ed00: return 0x410fc241
        if address == 0xe0042000: return 0x10000413
        if address == 0x40023c14: return 0x0fffaaed
        if address == 0x40023c10: return 0 if self.unlocked else 0x80000000
        if address == 0xe000edf0:
            return (window.raw.HALT if self.halted else 0) | (window.raw.RESET if self.reset and self.full_reads else 0)
        if address == window.SYSTEM['DWT_PCSR']: return 0 if self.pc_unavailable else 0x1fff32f0 if self.rom else 0x08000101
        if address == window.SYSTEM['VTOR']: return 0 if self.alias else 0x1fff0000 if self.rom else 0x08000000
        if address == window.SYSTEM['CFSR']: return 1 if self.fault else 0
        return 0


class ReadonlyTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        stamp = datetime.datetime.now(datetime.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ')
        cls.base = ROOT / 'node-b/build' / ('b4-c-readonly-tests-' + stamp); cls.base.mkdir()
    def capture(self, fake=None, blocked='6b' * 12):
        out = self.base / self._testMethodName; out.mkdir()
        return window.capture(fake or FakeC(), out, blocked)
    def test_current_backup_not_assumed_h3(self):
        result = self.capture(); self.assertEqual(result['exit_code'], 0)
        self.assertFalse(result['H3_restore_identity_eligible']); self.assertFalse(result['restore_exercised'])
        self.assertEqual(set(result['region_sha256']), {'sector3', 'sector7', 'sector11'})
    def test_still_on_b(self):
        with self.assertRaisesRegex(ValueError, 'STILL_ON_B'): self.capture(blocked='5a' * 12)
    def test_full_read_mismatch(self):
        fake = FakeC(); fake.different = True
        with self.assertRaisesRegex(ValueError, 'DOUBLE_READ_MISMATCH'): self.capture(fake)
        self.assertEqual(fake.full_reads, 2)
    def test_rom_does_not_read_full_or_resume(self):
        fake = FakeC(); fake.rom = True
        with self.assertRaisesRegex(ValueError, 'ROM_STOP'): self.capture(fake)
        self.assertEqual(fake.full_reads, 0); self.assertFalse(fake.close_resume_enabled)
    def test_halt_does_not_go(self):
        fake = FakeC(); fake.halted = True
        with self.assertRaisesRegex(ValueError, 'HALTED'): self.capture(fake)
        self.assertFalse(fake.close_resume_enabled)
    def test_fault_stop(self):
        fake = FakeC(); fake.fault = True
        with self.assertRaisesRegex(ValueError, 'FAULT'): self.capture(fake)
    def test_unlocked_flash_not_repaired(self):
        fake = FakeC(); fake.unlocked = True
        with self.assertRaisesRegex(ValueError, 'FLASH_CONTROL_NOT_IDLE'): self.capture(fake)
    def test_reset_during_read(self):
        fake = FakeC(); fake.reset = True
        with self.assertRaisesRegex(ValueError, 'NEW_RESET'): self.capture(fake)
        self.assertEqual(fake.full_reads, 1)
    def test_unavailable_pc_not_fabricated(self):
        fake = FakeC(); fake.pc_unavailable = True
        with self.assertRaisesRegex(ValueError, 'PC_NOT_PROVEN'): self.capture(fake)
    def test_zero_vtor_flash_alias_allowed(self):
        fake = FakeC(); fake.alias = True; self.assertEqual(self.capture(fake)['exit_code'], 0)
    def test_wrong_alias_stop(self):
        fake = FakeC(); fake.alias = fake.bad_alias = True
        with self.assertRaisesRegex(ValueError, 'ALIAS_NOT_FLASH'): self.capture(fake)
    def test_disabled_before_sdk(self):
        with self.assertRaisesRegex(ValueError, 'AUTHORIZATION_REQUIRED'): window.validate_authorization(window.plan())
    def test_valid_authorization_validation_is_still_offline(self):
        a = {'enabled': True, 'owner_approved': True, 'scope': window.SCOPE,
             'tools_sha256': window.bindings(), 'DLL_sha256': window.raw.DLL_SHA,
             'expires_unix': window.time.time() + 60, 'card_sha256': 'fake', 'B_reference_sha256': 'fake',
             'field_state': 'C_J5_ONLY_USB_OFF_JTAG_C_CAN_OFF_NO_MIC_TTS_ESP_ISOLATED'}
        with patch.object(window.raw, 'sha', return_value='fake'):
            window.validate_authorization(a)
            a['field_state'] = 'PROBE_STILL_ON_B'
            with self.assertRaisesRegex(ValueError, 'FIELD_NOT_READY'): window.validate_authorization(a)
    def current_authorization(self):
        # 只描述当前已授权事实，不构造串口或SDK，也不能冒用全隔离旧卡。
        return {'enabled': True, 'owner_approved': True, 'scope': window.SCOPE,
                'tools_sha256': window.bindings(), 'DLL_sha256': window.raw.DLL_SHA,
                'expires_unix': window.time.time() + 60, 'B_reference_sha256': 'fake',
                'field_state': window.CURRENT_STATE, 'authorization_basis': 'OWNER_CURRENT_STATE_BACKUP_ONLY',
                'owner_request_sha256': window.OWNER_REQUEST_SHA, 'network_isolation_claimed': False,
                'bench_admission': False, 'site_facts': {'JLink': 'C', 'ESP8266': 'PRESENT_NETWORK_UNVERIFIED',
                'USB_UART': 'LAST_SEEN_COM15_NO_NEW_COMMANDS', 'CAN': 'DISCONNECTED',
                'INMP441': 'DISCONNECTED', 'TTS': 'DISCONNECTED', 'power_action': 'NONE'}}
    def test_current_state_explicit_backup_authorization(self):
        with patch.object(window.raw, 'sha', return_value='fake'):
            window.validate_authorization(self.current_authorization())
    def test_current_state_cannot_claim_bench_or_isolation(self):
        for key in ('network_isolation_claimed', 'bench_admission'):
            a = self.current_authorization(); a[key] = True
            with patch.object(window.raw, 'sha', return_value='fake'):
                with self.assertRaisesRegex(ValueError, 'NOT_BENCH_AUTHORIZATION'): window.validate_authorization(a)
    def test_current_state_needs_exact_owner_and_site(self):
        for key in ('owner_request_sha256', 'authorization_basis', 'site_facts'):
            a = self.current_authorization(); a.pop(key)
            with patch.object(window.raw, 'sha', return_value='fake'):
                with self.assertRaises(ValueError): window.validate_authorization(a)
    def test_sdk_function_deny(self):
        # 不调用构造器；即使未加载任何DLL，禁止操作也应在白名单层立即拒绝。
        obj = object.__new__(window.CReadLink); obj.sdk_calls = 0
        for name in ('JLINKARM_Reset', 'JLINKARM_Halt', 'JLINKARM_Go', 'JLINKARM_WriteMem', 'JLINKARM_WriteReg'):
            with self.assertRaisesRegex(ValueError, 'FUNCTION_DENIED'): obj.call(name)
    def test_no_arbitrary_memory(self):
        obj = object.__new__(window.CReadLink); obj.sdk_calls = 0
        with self.assertRaisesRegex(ValueError, 'ADDRESS_DENIED'): obj.call('JLINKARM_ReadMemEx', 0x40003000, 4, None, 0)


if __name__ == '__main__': unittest.main(verbosity=2)
