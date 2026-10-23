"""C一次正常复位的入口/向量/动作预算；只用字典和SDK替身，不接实板。"""
from pathlib import Path
import sys
import unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[2];sys.path.insert(0,str(ROOT/'node-b/tools'))
import c_b4_boot_once as t

class Tests(unittest.TestCase):
    def test_disabled_by_default(self):
        with self.assertRaisesRegex(ValueError,'OWNER_AUTH'):t.validate({})
    def test_unreviewed_vector_stops_without_reset(self):
        with self.assertRaisesRegex(ValueError,'UNREVIEWED'):t.entry_gate({'VTOR':0x20000000})
    def test_healthy_flash_entry_keeps_resume_before_RAM_failure(self):
        class Fake:
            verified_running_flash=False
            close_resume_enabled=False
            def set_close_resume(self,value):self.close_resume_enabled=value
        state={'VTOR':0x08000000,'DHCSR':0,'CFSR':0,'HFSR':0,
               'FLASH_CR':0x80000000,'pc_samples':[0x08001000]}
        f=Fake();t.protect_healthy_entry(f,state);t.entry_gate(state)
        self.assertTrue(f.verified_running_flash);self.assertTrue(f.close_resume_enabled)
    def test_ROM_halt_expected_entry(self):
        t.entry_gate({'VTOR':0x1fff0000,'DHCSR':t.raw.HALT,'CFSR':0,'HFSR':0})
    def test_original_vector_and_ROM_negative(self):
        original=(0x20020000).to_bytes(4,'little')+(0x08001001).to_bytes(4,'little')
        state={'DHCSR':t.raw.HALT,'VTOR':0,'CFSR':0,'HFSR':0}
        core={'registers':{'R15':0x08001000,'MSP':0x20020000}}
        t.reset_core_gate(state,core,original)
        core['registers']['R15']=0x1fff36c0
        with self.assertRaisesRegex(ValueError,'NOT_ORIGINAL_FLASH'):t.reset_core_gate(state,core,original)
    def test_no_download_or_halt_API(self):
        link=object.__new__(t.Link);link.sdk_calls=0
        for name in ('JLINKARM_Halt','JLINKARM_WriteReg','JLINKARM_WriteMem','JLINKARM_BeginDownload'):
            with self.assertRaisesRegex(ValueError,'FUNCTION_DENIED'):link.call(name)
    def test_reset_budget_consumed_even_on_native_error(self):
        link=object.__new__(t.Link);link.sdk_calls=0;link.actions={};link.original_verified=True
        with patch.object(t.raw.Link,'call',return_value=-1):
            self.assertEqual(link.call('JLINKARM_Reset'),-1)
            with self.assertRaisesRegex(ValueError,'BUDGET'):link.call('JLINKARM_Reset')
    def test_no_go_without_original_vector_proof(self):
        link=object.__new__(t.Link);link.sdk_calls=0;link.actions={};link.original_verified=True;link.go_allowed=False
        with self.assertRaisesRegex(ValueError,'WITHOUT_VECTOR'):link.call('JLINKARM_Go')
if __name__=='__main__':unittest.main(verbosity=2)
