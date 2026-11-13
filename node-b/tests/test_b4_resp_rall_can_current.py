"""本次只读窗口的地址/固件/授权和异常边界测试；不加载SDK或访问硬件。"""
import copy
from pathlib import Path
import sys
import time
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import b4_resp_rall_can_current as w
import b4_runtime as live


class Tests(unittest.TestCase):
    def authorization(self):
        return {'enabled': True, 'owner_approved': True, 'plan': w.plan(),
                'observed_menu': w.MENU, 'JLink_on_B': True, 'battery_no_USB': True,
                'expires_unix': time.time() + 60}

    def test_exact_current_image_and_slots(self):
        self.assertEqual(w.READS[0x08000000], {64, 39948})
        self.assertEqual(w.READS[w.SLOTS], {3072})
        self.assertNotIn(0x20001f38, w.READS)

    def test_owner_scope(self):
        w.validate(self.authorization())
        with self.assertRaisesRegex(ValueError, 'OWNER_REQUIRED'):
            w.validate({})

    def test_old_menu_or_binary_cannot_be_reused(self):
        for field in ('menu', 'image_sha256', 'criteria'):
            a = copy.deepcopy(self.authorization()); a['plan'][field] = 'old'
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'DRIFT'):
                w.validate(a)

    def test_source_and_route_mismatch(self):
        for field, value in [('observed_menu', {}), ('JLink_on_B', False), ('battery_no_USB', False)]:
            a = self.authorization(); a[field] = value
            with self.subTest(field=field), self.assertRaisesRegex(ValueError, 'SOURCE_ROUTE'):
                w.validate(a)

    def test_no_target_actions_or_core_register_reads(self):
        obj = object.__new__(w.Link); obj.sdk_calls = 0
        for name in ('JLINKARM_Reset', 'JLINKARM_Halt', 'JLINKARM_Go',
                     'JLINKARM_WriteMem', 'JLINKARM_ReadReg'):
            with self.subTest(name=name), self.assertRaisesRegex(ValueError, 'FUNCTION_DENIED'):
                obj.call(name)

    def test_no_unknown_or_old_slot_reads(self):
        obj = object.__new__(w.Link); obj.sdk_calls = 0
        with self.assertRaisesRegex(ValueError, 'READ_DENIED'):
            obj.read(0x20001f38, 3072)

    def test_implicit_close_resume_requires_healthy_flash(self):
        obj = object.__new__(w.Link); obj.sdk_calls = 0; obj.verified_running_flash = False
        with self.assertRaisesRegex(ValueError, 'CLOSE_NOT_VERIFIED'):
            obj.call('JLINKARM_ExecCommand', b'SetRestartOnClose = 1', None, 0)

    def test_rom_halt_reset_or_fault_rejected(self):
        base = {'DHCSR': 0, 'CFSR': 0, 'HFSR': 0, 'FLASH_CR': 0x80000000,
                'pc_samples': [0x08001000], 'VTOR': 0x08000000}
        obj = object.__new__(w.Link)
        for key, value in [('DHCSR', w.raw.HALT), ('DHCSR', w.raw.RESET),
                           ('pc_samples', [0x1fff32f0]), ('CFSR', 1)]:
            state = dict(base); state[key] = value
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                live.ro.check_running(obj, state)
            self.assertFalse(obj.verified_running_flash)


if __name__ == '__main__':
    unittest.main(verbosity=2)
