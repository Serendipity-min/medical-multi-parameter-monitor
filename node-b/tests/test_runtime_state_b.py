"""启动核验工具离线门禁：运行态不得隐式取核寄存器，异常不得进入RESP。"""
import copy
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import runtime_state_b as runtime


def good_snapshot(samples=100):
    # 合成状态只验证门禁，绝不作为板上运行或电气安全的证据。
    return {'label': 'after-flash', 'system': {'VTOR': 0x08000000, 'CFSR': 0, 'HFSR': 0, 'DHCSR': 0},
            'DHCSR_after': 0, 'pc_regions': ['BIO_V2_FLASH'],
            'bio': {'samples': samples, 'adc': dict.fromkeys(('init_errors', 'spi_errors', 'bad_status', 'queue_overflow'), 0),
                    'registers_hex': '7301e0f04040ec00ffea030f'}}


class RuntimeCases(unittest.TestCase):
    def test_no_execution_or_target_write_function(self):
        link = object.__new__(runtime.RuntimeLink); link.sdk_calls = 0
        for name in ('JLINKARM_Go', 'JLINKARM_Halt', 'JLINKARM_Reset', 'JLINKARM_WriteMem', 'JLINKARM_WriteReg'):
            with self.assertRaisesRegex(RuntimeError, 'FUNCTION_DENIED'):
                link.call(name)

    def test_reject_unknown_addresses_and_commands(self):
        link = object.__new__(runtime.RuntimeLink); link.sdk_calls = 0
        with self.assertRaisesRegex(RuntimeError, 'READ_SCOPE'):
            link.call('JLINKARM_ReadMemEx', 0x40000000, 4, None, 0)
        with self.assertRaisesRegex(RuntimeError, 'COMMAND_DENIED'):
            link.call('JLINKARM_ExecCommand', b'SetResetType = 0')

    def test_running_target_never_reads_core_register(self):
        class Fake:
            def u32(self, address):
                self.address = address; return 0
            def call(self, *args):
                raise AssertionError('Running target must not call SDK register API')
        link = Fake()
        self.assertEqual(runtime.core_if_halted(link)['status'], 'NOT_READ_RUNNING_USE_PCSR')
        self.assertEqual(link.address, runtime.SYSTEM['DHCSR'])

    def test_register_names_and_pc_regions(self):
        for name in ('R15 (PC)', 'R15(PC)', 'PC'):
            self.assertEqual(runtime.register_name(name), 'R15')
        self.assertEqual(runtime.register_name('LR'), 'R14')
        self.assertEqual(runtime.pc_region(0x1fff32ed), 'SYSTEM_ROM')
        self.assertEqual(runtime.pc_region(0x080001a1), 'BIO_V2_FLASH')
        self.assertEqual(runtime.pc_region(0xffffffff), 'UNAVAILABLE')
        self.assertEqual(runtime.pc_region(0), 'UNAVAILABLE')

    def test_rom_pc_vtor_and_bad_diagnostic_hold(self):
        for field in ('rom_pc', 'vtor', 'abi', 'fault', 'halt', 'reset', 'cache', 'adc'):
            s = good_snapshot()
            if field == 'rom_pc': s['pc_regions'] = ['SYSTEM_ROM']
            if field == 'vtor': s['system']['VTOR'] = 0x1fff0000
            if field == 'abi': s['bio'] = None
            if field == 'fault': s['system']['HFSR'] = 0x40000000
            if field == 'halt': s['DHCSR_after'] = runtime.HALT
            if field == 'reset': s['DHCSR_after'] = runtime.RESET
            if field == 'cache': s['bio']['registers_hex'] = '00'*12
            if field == 'adc': s['bio']['adc']['spi_errors'] = 1
            self.assertEqual(runtime.capture_gate([s])['status'], 'HOLD_RUNTIME_STATE', field)

    def test_no_pc_evidence_and_nonadvancing_samples_hold(self):
        s = good_snapshot(); s['pc_regions'] = ['UNAVAILABLE']
        self.assertIn('NO_BIO_V2_EXECUTION_PC_EVIDENCE', runtime.capture_gate([s])['failures'])
        self.assertIn('BIO_SAMPLES_NOT_ADVANCING', runtime.capture_gate([good_snapshot(), good_snapshot()])['failures'])

    def test_good_running_state_only_prepares_separate_capture(self):
        result = runtime.capture_gate([good_snapshot(100), good_snapshot(225)])
        self.assertEqual(result['status'], 'READY_FOR_NEW_CAPTURE_CARD')
        self.assertTrue(result['does_not_authorize_reset_or_capture'])


if __name__ == '__main__':
    unittest.main()
