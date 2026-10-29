"""ROM现场只读白名单和监督边界，无DLL/设备访问。"""
import io
import sys
import time
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'tools'))
import b5_c_rom_readonly as r


class Tests(unittest.TestCase):
    def link(self):
        link=object.__new__(r.RomLink);link.counts={};link.sdk_calls=0
        link.verified_running_flash=False;link.register_reads_allowed=False;link.io=io.StringIO()
        return link

    def test_default_no_target(self):
        with patch.object(sys,'argv',['rom']),patch('sys.stdout',io.StringIO()),patch.object(r,'RomLink') as target:
            self.assertEqual(r.main(),0);target.assert_not_called()

    def test_target_actions_and_core_halt_reads_denied(self):
        for name in ('JLINKARM_Halt','JLINKARM_Reset','JLINKARM_Go','JLINKARM_WriteMem',
                     'JLINKARM_BeginDownload','JLINKARM_ReadReg','JLINKARM_GetRegisterList'):
            with self.subTest(name=name),patch.object(r.raw.Link,'call') as native:
                with self.assertRaisesRegex(ValueError,'DENIED'):self.link().call(name)
                native.assert_not_called()

    def test_uart_data_and_arbitrary_ranges_denied(self):
        for address,size in ((0x40004804,4),(0x40004404,4),(0x40011004,4),(0x1fff0000,32768),(0,1048576)):
            with self.subTest(address=address),patch.object(r.raw.Link,'call') as native:
                with self.assertRaisesRegex(ValueError,'RANGE'):self.link().call('JLINKARM_ReadMemEx',address,size,None,0)
                native.assert_not_called()

    def test_unknown_policy_and_unverified_resume_denied(self):
        for cmd in ('ForceAttachTarget = 0','SetRestartOnClose = 1','SetResetType = 0'):
            with patch.object(r.raw.Link,'call') as native:
                with self.assertRaisesRegex(ValueError,'POLICY'):self.link().call('JLINKARM_ExecCommand',cmd.encode(),None,0)
                native.assert_not_called()

    def test_one_rom_read_and_sdk_limit(self):
        link=self.link()
        with patch.object(r.raw.Link,'call',return_value=30720) as native:
            self.assertEqual(link.call('JLINKARM_ReadMemEx',0x1fff0000,30720,None,0),30720)
            with self.assertRaisesRegex(ValueError,'COUNT'):link.call('JLINKARM_ReadMemEx',0x1fff0000,30720,None,0)
            self.assertEqual(native.call_count,1)
        link.sdk_calls=300
        with self.assertRaisesRegex(ValueError,'BUDGET'):link.call('JLINKARM_IsConnected')

    def test_short_read_not_success(self):
        link=self.link()
        with patch.object(link,'call',return_value=3):
            with self.assertRaisesRegex(ValueError,'SHORT_READ'):link.read(0xe000ed08,4)

    def test_scope_or_budget_drift_denied_before_reference(self):
        a=dict(enabled=True,owner_approved=True,scope=r.SCOPE,tools_sha256=r.bindings(),DLL_sha256=r.raw.DLL_SHA,
               probe_sessions=1,session_timeout_s=120,retries=0,reset_halt_go_target_writes=0,expires_unix=time.time()+100,output='synthetic')
        for changes in ({'owner_approved':False},{'session_timeout_s':121},{'retries':1},{'reset_halt_go_target_writes':1}):
            with self.subTest(changes=changes),patch.object(r.recovery,'read') as read:
                with self.assertRaises(ValueError):r.authorize(dict(a,**changes),Path('synthetic'))
                read.assert_not_called()


if __name__=='__main__':unittest.main()
