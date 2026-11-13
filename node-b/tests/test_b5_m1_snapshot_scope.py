"""真实M1白名单与复用快照的离线集成；仅替换原生传输。"""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import b5_m1_entry as entry
import b5_g3_devices as devices
import c_b4_readonly as snapshot


class SnapshotReadScope(unittest.TestCase):
    def link(self, root):
        cls = entry.link_class()
        with patch.object(devices.BLink, '__init__', return_value=None):
            link = cls(root/'B', root)
        calls = []
        def transport(name, address, size, buf, flags, **kwargs):
            self.assertEqual(name, 'JLINKARM_ReadMemEx')
            self.assertEqual(flags, 0)
            calls.append((address, size)); buf[:] = bytes(size)
            return size
        link.call = transport
        return link, calls

    def test_actual_snapshot_reaches_FLASH_CR_through_real_M1_read_scope(self):
        with tempfile.TemporaryDirectory() as folder:
            link, calls = self.link(Path(folder))
            result = snapshot.snapshot(link)
            self.assertEqual(set(result)-{'pc_samples'}, set(snapshot.SYSTEM))
            self.assertIn((0x40023c10, 4), calls)
            self.assertTrue(all((address, 4) in calls for address in snapshot.SYSTEM.values()))

    def test_nearby_register_and_wrong_size_still_denied(self):
        with tempfile.TemporaryDirectory() as folder:
            link, calls = self.link(Path(folder))
            for address, size in ((0x40023c18, 4), (0x40023c10, 8)):
                with self.subTest(address=address, size=size), self.assertRaisesRegex(ValueError, 'G3_B_READ_SCOPE'):
                    link.read(address, size)
            self.assertEqual(calls, [])


if __name__ == '__main__':
    unittest.main()
