"""一次Go入口的纯替身边界测试，不加载DLL。"""
from pathlib import Path
import sys
import unittest
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import b4_resume as w
class Tests(unittest.TestCase):
    def state(self):return {'DHCSR':w.raw.HALT,'VTOR':0x08000000,'CFSR':0,'HFSR':0}
    def core(self):return {'registers':{'R15':0x08001000,'MSP':0x2001fff0}}
    def test_flash_halt_only(self):w.gate_core(self.state(),self.core())
    def test_ROM_rejected(self):
        c=self.core();c['registers']['R15']=0x1fff32f0
        with self.assertRaisesRegex(ValueError,'PC_NOT_CANDIDATE'):w.gate_core(self.state(),c)
    def test_ram_rejected(self):
        c=self.core();c['registers']['R15']=0x20001000
        with self.assertRaises(ValueError):w.gate_core(self.state(),c)
    def test_running_not_resumed_again(self):
        s=self.state();s['DHCSR']=0
        with self.assertRaises(ValueError):w.gate_core(s,self.core())
    def test_fault_rejected(self):
        s=self.state();s['CFSR']=1
        with self.assertRaises(ValueError):w.gate_core(s,self.core())
    def test_no_reset_halt_or_write(self):
        o=object.__new__(w.Link);o.sdk_calls=0
        for name in ('JLINKARM_Reset','JLINKARM_Halt','JLINKARM_WriteMem','JLINKARM_WriteReg','JLINKARM_BeginDownload'):
            with self.assertRaisesRegex(ValueError,'FUNCTION_DENIED'):o.call(name)
    def test_second_Go_forbidden(self):
        o=object.__new__(w.Link);o.sdk_calls=0;o.resume_allowed=True;o.go_count=1
        with self.assertRaisesRegex(ValueError,'GO_GATE_OR_BUDGET'):o.call('JLINKARM_Go')
if __name__=='__main__':unittest.main(verbosity=2)
