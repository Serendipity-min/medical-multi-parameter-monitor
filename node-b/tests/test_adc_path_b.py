"""会话间暂停保护：ROM、fault、lockup时不得发go或读取活动采样区。"""
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import adc_path_b as module
from readback_b import identity,LOCKUP
from test_readback_b import FakeLink


class PathFake(FakeLink):
    def __init__(self,fault=0):super().__init__(halted=True);self.fault=fault
    def u32(self,address):
        if address in (0xe000ed28,0xe000ed2c):return self.fault
        return super().u32(address)


class Cases(unittest.TestCase):
    def test_no_resume_for_rom_fault_or_lockup(self):
        for case,pc,fault,reason in [('rom',0x1fff32ec,0,'PAUSED_OUTSIDE_BIO_V2'),
                                   ('fault',0x08005e38,1,'ACTIVE_FAULT'),
                                   ('lockup',0x08005e38,0,'LOCKUP')]:
            with self.subTest(case=case),tempfile.TemporaryDirectory() as folder:
                link=PathFake(fault);reference=identity(link)
                if case=='lockup':link.state|=LOCKUP
                with patch.object(module,'core',return_value={'R15':pc}):
                    with self.assertRaisesRegex(RuntimeError,reason):
                        module.inspect(link,reference,Path(folder),{'go_requests':0})
                self.assertNotIn('JLINKARM_Go',link.commands)
                self.assertNotIn('JLINKARM_Reset',link.commands)


if __name__=='__main__':unittest.main(verbosity=2)
