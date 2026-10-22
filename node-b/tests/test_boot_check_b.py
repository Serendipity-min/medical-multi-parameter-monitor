"""启动入口保护：ROM入口或Flash漂移时绝不继续运行；不接硬件。"""
import hashlib
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import boot_check_b as module
from readback_b import HALT,identity
from test_readback_b import FakeLink


class BootFake(FakeLink):
    def policy(self,command):self.commands.append(command)
    def read(self,address,size):
        if address==0x08000000 and size==64:
            return (0x20002f30).to_bytes(4,'little')+(0x080001a1).to_bytes(4,'little')+b'\0'*56
        return super().read(address,size)


class Cases(unittest.TestCase):
    def test_rom_entry_stops_without_go(self):
        link=BootFake(halted=True);reference=identity(link)
        with tempfile.TemporaryDirectory() as folder,patch.object(module,'EXPECTED_FLASH',hashlib.sha256(b'\1'*1048576).hexdigest()),patch.object(module,'core',return_value={'R15':0x1fff32ec,'MSP':0x20001940}):
            receipt={}
            with self.assertRaisesRegex(RuntimeError,'RESET_ENTRY_NOT_BIO_V2'):
                module.boot(link,reference,Path(folder),receipt)
            self.assertEqual(receipt['reset_requests'],1)
            self.assertNotIn('JLINKARM_Go',link.commands)

    def test_flash_drift_no_reset(self):
        link=BootFake(halted=True);reference=identity(link)
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(RuntimeError,'FLASH_DRIFT'):module.boot(link,reference,Path(folder),{})
        self.assertNotIn('JLINKARM_Reset',link.commands)
        self.assertNotIn('JLINKARM_Go',link.commands)


if __name__=='__main__':unittest.main(verbosity=2)
