"""复位卡的离线边界：只准一次复位，错误入口/未授权不得恢复或采集。"""
from pathlib import Path
import struct
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import recover_resp_runtime_b as recovery


class RecoveryCases(unittest.TestCase):
    def test_reset_entry_and_stack_must_match_real_vectors(self):
        vectors = struct.pack('<II', 0x20002f30, 0x080001a1)+bytes(56)
        recovery.verify_reset_entry({'R15': 0x080001a0, 'MSP': 0x20002f30}, vectors, vectors)
        # 系统ROM入口即使栈值正确，也不得继续go或通过写PC伪装修复。
        for registers in ({'R15': 0x1fff32f0, 'MSP': 0x20002f30},
                          {'R15': 0x080001a0, 'MSP': 0x20001940}):
            with self.assertRaises(RuntimeError):
                recovery.verify_reset_entry(registers, vectors, vectors)
        with self.assertRaisesRegex(RuntimeError, 'ALIAS'):
            recovery.verify_reset_entry({'R15': 0x080001a0, 'MSP': 0x20002f30}, vectors, bytes(64))

    def test_reset_budget_counts_attempt_before_sdk_call(self):
        link = object.__new__(recovery.RecoveryLink)
        link.counts = dict(sdk_calls=0, reset_requests=0, go_requests=0, halt_requests=0, flash_write_requests=0)
        with patch.object(recovery.Link, 'call', side_effect=RuntimeError('SYNTHETIC_SDK_FAILURE')):
            with self.assertRaisesRegex(RuntimeError, 'SYNTHETIC_SDK_FAILURE'):
                link.call('JLINKARM_Reset')
        self.assertEqual(link.counts['reset_requests'], 1)
        with self.assertRaisesRegex(RuntimeError, 'EXECUTION_BUDGET'):
            link.call('JLINKARM_Reset')

    def test_no_arbitrary_write_command_or_address(self):
        link = object.__new__(recovery.RecoveryLink); link.counts = {'sdk_calls': 0}
        for name in ('JLINKARM_WriteMem', 'JLINKARM_WriteReg', 'JLINKARM_EraseChip'):
            with self.assertRaisesRegex(RuntimeError, 'FUNCTION_DENIED'):
                link.call(name)
        with self.assertRaisesRegex(RuntimeError, 'COMMAND_DENIED'):
            link.call('JLINKARM_ExecCommand', b'SupplyPower = 1')
        with self.assertRaisesRegex(RuntimeError, 'READ_SCOPE'):
            link.call('JLINKARM_ReadMemEx', 0x40000000, 4, None, 0)

    def test_running_core_register_reads_denied(self):
        link = object.__new__(recovery.RecoveryLink)
        link.counts = {'sdk_calls': 0}; link.register_reads_allowed = False
        with self.assertRaisesRegex(RuntimeError, 'CORE_READ_REQUIRES_HALT'):
            link.call('JLINKARM_ReadReg', 15)

    def test_existing_connection_is_reused_for_capture(self):
        # 包装层必须保留冻结采集地址，否则恢复成功后首槽会被错误地拒绝。
        self.assertEqual(recovery.READS[0x20001f30], 3072)
        link = object.__new__(recovery.RecoveryLink); link.opened = True
        with patch.object(recovery.runtime.RuntimeLink, 'open', side_effect=AssertionError('unexpected second attach')):
            link.open()


if __name__ == '__main__':
    unittest.main()
