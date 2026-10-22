"""新零复位卡的必要边界：禁reset/策略、限制go，暂停初态不得自动恢复。"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import capture_resp_checked_b as checked


class CheckedCases(unittest.TestCase):
    def test_reset_and_reset_policy_denied(self):
        link = object.__new__(checked.CheckedLink)
        for name, args in [('JLINKARM_Reset', ()), ('JLINKARM_ExecCommand', (b'SetResetType = 0',))]:
            with self.assertRaisesRegex(RuntimeError, 'RESET'):
                link.call(name, *args)

    def test_only_one_tail_go(self):
        link = object.__new__(checked.CheckedLink); link.counts = {'go_requests': 1}
        with self.assertRaisesRegex(RuntimeError, 'GO_BUDGET'):
            link.call('JLINKARM_Go')

    def test_halted_entry_stops_without_go_or_reset(self):
        class Fake:
            def open(self): pass
            def u32(self, address): return checked.HALT
        # 暂停初态只留下原始状态记录，不调用恢复分支。
        with tempfile.TemporaryDirectory() as name, patch.object(checked, 'identity', return_value={'uid_hex': 'synthetic', 'optcr': 0}), patch.object(checked, 'check_identity'):
            with self.assertRaisesRegex(RuntimeError, 'INITIAL_NOT_RUNNING'):
                checked.running_precheck(Fake(), {'uid_hex': 'synthetic', 'optcr': 0}, Path(name))


if __name__ == '__main__':
    unittest.main()
