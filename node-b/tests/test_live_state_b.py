"""退出续跑回归：只用模拟 SDK，禁止测试触碰实物。"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import live_state_b as live
from readback_b import Link, HALT


class LiveTests(unittest.TestCase):
    def link(self):
        obj = live.LiveLink.__new__(live.LiveLink)
        obj.sdk_calls = 0
        obj.register_reads_allowed = False
        obj.verified_running_flash = False
        obj.close_resume_enabled = False
        return obj

    def test_controls_and_destructive_reads_rejected_before_SDK(self):
        link = self.link()
        with patch.object(Link, 'call') as sdk:
            for name in ('JLINKARM_Reset', 'JLINKARM_Halt', 'JLINKARM_Go', 'JLINKARM_WriteMem', 'JLINKARM_WriteReg'):
                with self.assertRaises(RuntimeError):
                    link.call(name)
            for address, size in ((0x40011004, 4), (0x20000000, 131072), (0x08000000, 1048576)):
                with self.assertRaises(RuntimeError):
                    link.call('JLINKARM_ReadMemEx', address, size, None, 0)
            sdk.assert_not_called()

    def test_close_resume_requires_verified_application(self):
        link = self.link()
        with patch.object(Link, 'call', return_value=0) as sdk:
            with self.assertRaises(RuntimeError):
                link.set_close_resume(True)
            sdk.assert_not_called()
            link.verified_running_flash = True
            link.set_close_resume(True)
            self.assertTrue(link.close_resume_enabled)

    def test_close_previous_one_is_success_but_native_error_is_not(self):
        link = self.link()
        link.verified_running_flash = True
        with patch.object(Link, 'call', return_value=1):
            link.set_close_resume(True)
        with patch.object(Link, 'call', return_value=-1):
            with self.assertRaises(RuntimeError):
                link.set_close_resume(True)

    def test_ROM_fault_halt_or_unavailable_PC_cannot_enable_resume(self):
        def snap():
            return {'system': {'VTOR': 0x08000000, 'CFSR': 0, 'HFSR': 0, 'DHCSR': 0},
                    'DHCSR_after': 0, 'pc_regions': ['BIO_V2_FLASH']}
        self.assertTrue(live.normal_flash(snap()))
        for key, value in (('VTOR', 0x1fff0000), ('CFSR', 1), ('DHCSR', HALT)):
            s = snap(); s['system'][key] = value
            self.assertFalse(live.normal_flash(s))
        for regions in (['UNAVAILABLE'], ['BIO_V2_FLASH', 'SYSTEM_ROM']):
            s = snap(); s['pc_regions'] = regions
            self.assertFalse(live.normal_flash(s))

    def test_already_halted_core_guard_is_retained(self):
        with patch.object(Link, 'call') as sdk:
            with self.assertRaises(RuntimeError):
                self.link().call('JLINKARM_ReadReg', 15)
            sdk.assert_not_called()

    def test_late_fault_disables_close_resume_and_still_closes(self):
        class FakeLink:
            sdk_calls = 0
            close_resume_enabled = False
            closed = False
            policies = []

            def open(self):
                pass

            def read(self, address, size):
                return b'image' if address == 0x08000000 else b'options'

            def set_close_resume(self, enabled):
                self.policies.append(enabled)
                self.close_resume_enabled = enabled

            def close(self):
                self.closed = True

        link = FakeLink()
        def snap(fault=0):
            return {'system': {'VTOR': 0x08000000, 'CFSR': fault, 'HFSR': 0, 'DHCSR': 0},
                    'DHCSR_after': 0, 'pc_regions': ['BIO_V2_FLASH'], 'bio': {'samples': 10}}
        ident = {'uid_hex': 'test-only', 'optcr': 0}
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(live, 'LiveLink', return_value=link), \
                patch.object(live, 'identity', return_value=ident), \
                patch.object(live, 'check_identity'), \
                patch.object(live, 'CANDIDATE_SHA', live.sha_bytes(b'image')), \
                patch.object(live.old, 'OPTIONS_SHA', live.sha_bytes(b'options')), \
                patch.object(live.old, 'core_if_halted', return_value={}), \
                patch.object(live.time, 'sleep'), \
                patch.object(live, 'snapshot', side_effect=[snap(), snap(), snap(fault=1)]):
            result = live.inspect(Path('unused'), ident, Path(folder))
        self.assertEqual(result['exit_code'], 1)
        self.assertEqual(link.policies, [True, False])
        self.assertTrue(link.closed)
        self.assertFalse(result['P0_pass'])


if __name__ == '__main__':
    unittest.main()
