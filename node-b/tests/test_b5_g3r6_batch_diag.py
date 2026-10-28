"""批量诊断分支及权限测试；不连接设备。"""
import contextlib
import copy
import io
import json
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import Mock,patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_g3r6_batch_diag as d


def state(halt=False):
    return {'VTOR':0x08000000,'pc_samples':[0xffffffff] if halt else [0x08000100],
        'DHCSR':0x30003 if halt else 0x10001,'DHCSR_after':0x30003 if halt else 0x10001,
        'DISARMED':True,'CFSR':0,'HFSR':0,'DFSR':1 if halt else 0,'DEMCR':1<<24,
        'FP_COMP':[0]*6,'FLASH_CR':0x80000000,'FLASH_SR':0,'RCC_CSR':0,'uptime':100}


CORE={'registers':{'R15':0x08000201,'MSP':0x2001fff0,'XPSR':1<<24}}


class Tests(unittest.TestCase):
    def test_default_has_no_device_actions(self):
        with patch.object(sys,'argv',['diag']),patch.object(d,'run_session') as run,contextlib.redirect_stdout(io.StringIO()):
            self.assertEqual(d.main(),0);run.assert_not_called()
    def test_no_authorization_rejected_before_files(self):
        with self.assertRaises(ValueError):d.validate({})
    def test_read_and_API_scope_never_allow_UART_flash_control_or_reset(self):
        self.assertNotIn(d.q.DR,d.READS)
        self.assertNotIn('JLINKARM_Reset',d.DiagnosticLink.NATIVE_SCOPE)
        self.assertNotIn('JLINKARM_Halt',d.DiagnosticLink.NATIVE_SCOPE)
        self.assertNotIn('JLINKARM_WriteMem',d.DiagnosticLink.NATIVE_SCOPE)
        self.assertNotIn('JLINKARM_CORESIGHT_WriteAPDPReg',d.DiagnosticLink.NATIVE_SCOPE)
        self.assertNotIn(0x40023c04,d.READS)
    def test_normal_halt_rom_fault_unknown_reset_classification(self):
        self.assertEqual(d.classify(state()),'RUNNING_FLASH');self.assertEqual(d.classify(state(True)),'HALT')
        for changed,expected in [({'VTOR':0x1fff0000},'ROM'),({'pc_samples':[0x1fff32f0]},'ROM'),
            ({'CFSR':1},'FAULT_RESET_OR_LOCKUP'),({'DHCSR':1<<19},'FAULT_RESET_OR_LOCKUP'),
            ({'DHCSR_after':1<<25},'FAULT_RESET_OR_LOCKUP'),({'pc_samples':[0xffffffff]},'UNKNOWN'),
            ({'DISARMED':False},'UNKNOWN')]:
            s=state();s.update(changed);self.assertEqual(d.classify(s),expected)
    def test_Go_requires_all_real_core_and_debug_identity_conditions(self):
        self.assertTrue(d.resume_check(state(True),CORE,True))
        for key,value in [('DFSR',2),('DEMCR',1),('FP_COMP',[1]),('CFSR',1),('FLASH_CR',0)]:
            s=state(True);s[key]=value;self.assertFalse(d.resume_check(s,CORE,True))
        for key,value in [('R15',0x1fff32f0),('MSP',0x08002000),('XPSR',0),('XPSR',(1<<24)|3)]:
            core=copy.deepcopy(CORE);core['registers'][key]=value
            self.assertFalse(d.resume_check(state(True),core,True))
        self.assertFalse(d.resume_check(state(True),CORE,False));self.assertFalse(d.resume_check(state(True),{},True))
    def test_Go_marker_is_exclusive_before_native_call_and_shared_across_sessions(self):
        with tempfile.TemporaryDirectory() as folder:
            a={'root':folder,'Go_max':1}
            for i in range(2):
                link=object.__new__(d.DiagnosticLink);link.batch=a;link.resume_eligible=True
                with patch.object(d.q.QueryLink,'_call_native',return_value=None) as native:
                    if i==0:link._call_native('JLINKARM_Go');native.assert_called_once()
                    else:
                        with self.assertRaises(FileExistsError):link._call_native('JLINKARM_Go')
                        native.assert_not_called()
    def test_no_running_ReadReg_and_no_unqualified_Go(self):
        link=object.__new__(d.DiagnosticLink);link.register_reads_allowed=False;link.resume_eligible=False
        for name in ('JLINKARM_ReadReg','JLINKARM_Go'):
            with patch.object(d.q.QueryLink,'_call_native') as native:
                with self.assertRaises(ValueError):link._call_native(name)
                native.assert_not_called()
    def run_fake(self,initial,core=CORE,match=True):
        snapshots=[];image=bytes(1048576);options=bytes(16)
        link=types.SimpleNamespace(open=Mock(),u32=lambda a:0,register_reads_allowed=False,
            native_UART_writes=0,sdk_calls=0,sdk_limit=1400,close_resume_enabled=False,
            verified_running_flash=False,close=Mock(),call=Mock(),set_close_resume=Mock())
        def read(address,size):return b'bad' if not match else bytes(size)
        link.read=read
        def snap(link,out,label):
            snapshots.append(label)
            if label in ('entry','pre-go'):return initial
            s=state();s['uptime']=200 if label=='after-go' else 300;return s
        with tempfile.TemporaryDirectory() as folder:
            out=Path(folder)/'session'
            def save(path,obj):Path(path).write_text(json.dumps(obj))
            with patch.object(d,'DiagnosticLink',return_value=link),patch.object(d,'snapshot',side_effect=snap), \
                patch.object(d,'identity'),patch.object(d.g,'load',return_value={}),patch.object(d.g.private,'read',side_effect=[image,options]), \
                patch.object(d.g.private,'protected'),patch.object(d.g,'save',side_effect=save),patch.object(d.g,'write_private'), \
                patch.object(d.q.runtime,'core_if_halted',return_value=core),patch.object(d.time,'sleep'), \
                contextlib.redirect_stdout(io.StringIO()):
                code=d.run_session({'root':folder,'identity_reference':'fake','image_reference':'fake','options_reference':'fake'},1,out)
            receipt=json.loads((out/'receipt-private.json').read_text())
        return code,receipt,link,snapshots
    def test_normal_branch_no_Go_proves_progress_and_requests_healthy_close(self):
        code,r,link,s=self.run_fake(state())
        self.assertEqual(code,0);link.call.assert_not_called();link.set_close_resume.assert_called_once_with(True)
        self.assertTrue(r['host_budget_rejection_verified']);self.assertEqual(r['explicit_Go_attempts'],0)
    def test_halt_eligible_calls_Go_once_then_verifies_progress(self):
        code,r,link,s=self.run_fake(state(True))
        self.assertEqual(code,0);link.call.assert_called_once_with('JLINKARM_Go');self.assertIn('after-go',s)
    def test_halt_with_missing_core_or_identity_mismatch_is_not_resumed(self):
        for core,match in [({},True),(CORE,False)]:
            code,r,link,s=self.run_fake(state(True),core,match)
            self.assertEqual(code,1);link.call.assert_not_called();link.set_close_resume.assert_not_called()
    def test_ROM_unknown_stops_before_identity_and_Go(self):
        for key,value in [('VTOR',0x1fff0000),('DISARMED',False)]:
            s=state();s[key]=value
            code,r,link,_=self.run_fake(s)
            self.assertEqual(code,1);link.call.assert_not_called();link.set_close_resume.assert_not_called()


if __name__=='__main__':unittest.main()
