"""串口下载的越界、身份和保护拒绝行为；不打开物理串口。"""
import json
from pathlib import Path
import sys
import unittest
import tempfile

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'tools'))
import field01_e_usb as target


class ROM:
    def __init__(self):
        self.extended_erase = True
        self.memory = bytearray(b'\x37' * target.FLASH_SIZE)
        self.options = b'\xff\xaa' + b'\xff' * 14
        self.writes = []
        self.erases = []
        self.uid = b'\x5a' * 12
        self.corrupt_outside = False
        self.corrupt_options = False

    def get(self): return 0x31
    def get_id(self): return 0x413
    def get_flash_size_and_uid(self): return 1024, self.uid

    def read_memory_data(self, address, length):
        if address == 0x1fffc000:
            return self.options
        offset = address - target.BASE
        return self.memory[offset:offset+length]

    def extended_erase_memory(self, sectors):
        self.erases.append(sectors)
        self.memory[:32768] = b'\xff' * 32768

    def write_memory_data(self, address, data):
        self.writes.append((address, len(data)))
        self.memory[:len(data)] = data
        if self.corrupt_outside: self.memory[32768] ^= 1
        if self.corrupt_options: self.options = b'\0' * 16


class Download(unittest.TestCase):
    def test_updated_image_requires_exact_sha_and_preserves_sector_tail(self):
        candidate=target.image()+b'\0'*8
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/'candidate.bin';path.write_bytes(candidate)
            with self.assertRaises(ValueError):target.image(path)
            with self.assertRaises(ValueError):target.image(path,'0'*64)
            data=target.image(path,target.package.digest(candidate))
        b=ROM();before=bytes(b.memory)
        result=target.install(b,data,target.identity(b),lambda *_:None)
        self.assertEqual(result['candidate_sha256'],target.package.digest(candidate))
        self.assertEqual(bytes(b.memory[:len(candidate)]),candidate)
        self.assertEqual(bytes(b.memory[len(candidate):]),before[len(candidate):])
        self.assertEqual(b.erases,[[0,1]])

    def test_fixed_image_and_exact_sector_preservation(self):
        b = ROM()
        before = bytes(b.memory)
        result = target.install(b, target.image(), target.identity(b), lambda *_: None)
        self.assertEqual(result['status'], 'E_M1_SECTOR01_ROM_FULL_VERIFY_PASS')
        self.assertEqual(b.erases, [[0, 1]])
        self.assertEqual(b.writes, [(target.BASE, 32768)])
        self.assertEqual(bytes(b.memory[:29416]), target.image())
        self.assertEqual(bytes(b.memory[29416:]), before[29416:])

    def test_wrong_identity_and_readout_protection_stop_before_erase(self):
        for wrong_uid in (True, False):
            with self.subTest(wrong_uid=wrong_uid):
                b = ROM()
                expected = target.identity(b)
                if wrong_uid: b.uid = b'\x6b' * 12
                else: b.options = b'\0' * 16
                with self.assertRaises(ValueError):
                    target.install(b, target.image(), expected, lambda *_: None)
                self.assertEqual(b.erases, [])
                self.assertEqual(b.writes, [])

    def test_outside_or_options_change_never_reports_success(self):
        for attribute in ('corrupt_outside', 'corrupt_options'):
            with self.subTest(attribute=attribute):
                b = ROM()
                setattr(b, attribute, True)
                with self.assertRaises(ValueError):
                    target.install(b, target.image(), target.identity(b), lambda *_: None)


if __name__ == '__main__':
    unittest.main()
