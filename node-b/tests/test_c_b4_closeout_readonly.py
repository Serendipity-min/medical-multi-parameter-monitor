"""当前C备份匹配的纯离线负例；不访问串口或加载SDK。"""
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import c_b4_closeout_readonly as w


class Tests(unittest.TestCase):
    def test_disabled(self):
        with self.assertRaisesRegex(ValueError, 'OWNER_REQUIRED'):
            w.validate_authorization({})

    def test_current_match(self):
        r = {'status': 'C_CURRENT_DOUBLE_FULL_READ_PASS', 'exit_code': 0, 'actual_full_sha256': 'new'}
        w.check_current(r, {'role': 'C'}, {'role': 'C'}, 'new')

    def test_old_backup_not_current(self):
        r = {'status': 'C_CURRENT_DOUBLE_FULL_READ_PASS', 'exit_code': 0, 'actual_full_sha256': 'oldH3'}
        with self.assertRaisesRegex(ValueError, 'FLASH_DRIFT'):
            w.check_current(r, {'role': 'C'}, {'role': 'C'}, 'new')

    def test_wrong_probe_board(self):
        r = {'status': 'C_CURRENT_DOUBLE_FULL_READ_PASS', 'exit_code': 0, 'actual_full_sha256': 'new'}
        with self.assertRaisesRegex(ValueError, 'WRONG_IDENTITY'):
            w.check_current(r, {'role': 'B'}, {'role': 'C'}, 'new')

    def test_failed_capture_never_passes(self):
        with self.assertRaisesRegex(ValueError, 'NOT_COMPLETE'):
            w.check_current({'status': 'STOP', 'exit_code': 1}, {}, {}, 'new')


if __name__ == '__main__':
    unittest.main(verbosity=2)
