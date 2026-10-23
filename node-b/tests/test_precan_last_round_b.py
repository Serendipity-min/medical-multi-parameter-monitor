"""最后一轮烧录边界的主机负例，不打开实板或DLL。"""
import ctypes as C
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]/'tools'))
import precan_last_round_b as last
from readback_b import Link


class LastRoundTests(unittest.TestCase):
    def link(self, action):
        obj = last.LastLink.__new__(last.LastLink)
        obj.action = action
        obj.counts = {}
        obj.sdk_calls = 0
        obj.download_payload_sha = None
        obj.download_verified = False
        obj.verified_running_flash = False
        obj.register_reads_allowed = False
        return obj

    def test_payload_preserves_all_original_bytes_outside_new_image(self):
        image = b'N' * last.IMAGE_BYTES
        backup = bytes(range(256)) * 4096
        with patch.object(last, 'IMAGE_SHA', last.digest(image)), patch.object(last, 'OLD_FULL_SHA', last.digest(backup)):
            actual = last.payload_for(image, backup)
            self.assertEqual(actual[:len(image)], image)
            self.assertEqual(actual[len(image):], backup[len(image):])
            for bad_image, bad_backup in ((image[:-1], backup), (b'X'+image[1:], backup),
                                           (image, b'X'+backup[1:])):
                with self.assertRaises(RuntimeError):
                    last.payload_for(bad_image, bad_backup)

    def test_observation_has_no_control_or_write_capability(self):
        with patch.object(Link, 'call') as sdk:
            link = self.link('screen')
            for name in ('JLINKARM_Halt', 'JLINKARM_Reset', 'JLINKARM_Go', 'JLINKARM_WriteMem',
                         'JLINKARM_BeginDownload', 'JLINKARM_EndDownload', 'JLINKARM_WriteReg'):
                with self.assertRaises(RuntimeError):
                    link.call(name)
            sdk.assert_not_called()

    def test_backup_and_full_verify_are_required_before_program_or_boot(self):
        with patch.object(Link, 'call') as sdk:
            link = self.link('install')
            for name, args in (('JLINKARM_BeginDownload', (0,)), ('JLINKARM_Reset', ()), ('JLINKARM_Go', ())):
                with self.assertRaises(RuntimeError):
                    link.call(name, *args)
            sdk.assert_not_called()

    def test_only_exact_sector_payload_is_written_once(self):
        buf = (C.c_uint8 * 32768).from_buffer_copy(b'A' * 32768)
        link = self.link('install')
        link.download_payload_sha = last.digest(b'A' * 32768)
        with patch.object(Link, 'call', return_value=32768) as sdk:
            for start, length in ((0x08008000, 32768), (0x08000000, 16384)):
                with self.assertRaises(RuntimeError):
                    link.call('JLINKARM_WriteMem', start, length, buf)
            sdk.assert_not_called()
            link.call('JLINKARM_WriteMem', 0x08000000, 32768, buf)
            with self.assertRaises(RuntimeError):
                link.call('JLINKARM_WriteMem', 0x08000000, 32768, buf)
            self.assertEqual(sdk.call_count, 1)

    def test_arbitrary_policy_and_UART_data_reads_are_denied(self):
        link = self.link('install')
        with patch.object(Link, 'call') as sdk:
            with self.assertRaises(RuntimeError):
                link.call('JLINKARM_ExecCommand', b'SupplyPower = 1')
            with self.assertRaises(RuntimeError):
                link.call('JLINKARM_ReadMemEx', 0x40011004, 4, None, 0)
            sdk.assert_not_called()

    def test_missing_manual_event_is_failure_without_stopping_verified_application(self):
        class FakeLink:
            close_resume_enabled = True
            sdk_calls = 0
            counts = {}
            closed = False

            def set_close_resume(self, enabled):
                self.close_resume_enabled = enabled

            def close(self):
                self.closed = True

        link = FakeLink()
        with tempfile.TemporaryDirectory() as folder, \
                patch.object(last, 'LastLink', return_value=link), \
                patch.object(last, 'observe', side_effect=RuntimeError('LAST_SCREEN_EVENT_NOT_CONFIRMED')):
            args = SimpleNamespace(action='screen', out=Path(folder)/'one')
            self.assertEqual(last.worker(args), 1)
            self.assertTrue(link.close_resume_enabled)
            self.assertTrue(link.closed)


if __name__ == '__main__':
    unittest.main()
